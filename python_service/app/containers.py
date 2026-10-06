"""Application container: constructs the whole dependency graph at startup.

Build order follows the layers (clients -> repositories -> agents ->
orchestrators -> services). Graphs are compiled exactly once here.
"""

from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.agents.extraction_agent import ExtractionAgent
from app.agents.invoice_agent import InvoiceAgent
from app.agents.sales_agent import SalesAgent
from app.agents.verifier_agent import VerifierAgent
from app.clients.bedrock_client import BedrockClient
from app.clients.chat_model import BedrockChatModel
from app.clients.gst_client import GSTClient
from app.clients.s3_client import S3Client
from app.clients.whatsapp_client import WhatsAppClient
from app.config.settings import Settings
from app.orchestrator_service.invoice_orchestrator import InvoiceOrchestrator
from app.orchestrator_service.po_orchestrator import POOrchestrator
from app.repositories.database import get_session_factory
from app.repositories.repositories.agent_run_repository import AgentRunRepository
from app.repositories.repositories.customer_repository import CustomerRepository
from app.repositories.repositories.episodic_memory_repository import EpisodicMemoryRepository
from app.repositories.repositories.field_definition_repository import FieldDefinitionRepository
from app.repositories.repositories.invoice_repository import InvoiceRepository
from app.repositories.repositories.po_field_repository import POHeaderFieldRepository, POLineItemRepository
from app.repositories.repositories.policy_repository import PolicyRepository
from app.repositories.repositories.product_repository import ProductRepository
from app.repositories.repositories.purchase_order_repository import PurchaseOrderRepository
from app.repositories.repositories.sales_repository import SalesRepository
from app.services.agent_service import AgentService
from app.services.hitl_service import HITLService
from app.tools.communication_tools import build_whatsapp_tools
from app.tools.customer_tools import build_customer_tools
from app.tools.extraction_tools import build_extraction_tools
from app.tools.invoice_tools import build_invoice_service_tools, build_invoice_tools
from app.tools.policy_tools import build_policy_tools
from app.tools.product_tools import build_product_tools
from app.tools.purchase_order_tools import build_purchase_order_tools
from app.tools.sales_tools import build_customer_history_tool, build_sales_tools


class AppContainer:
    """Immutable-ish service graph for the FastAPI application."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session_factory = get_session_factory()

        # --- repositories ---
        self.agent_run_repository = AgentRunRepository(self.session_factory)
        self.customer_repository = CustomerRepository(self.session_factory)
        self.product_repository = ProductRepository(self.session_factory)
        self.sales_repository = SalesRepository(self.session_factory)
        self.invoice_repository = InvoiceRepository(self.session_factory)
        self.purchase_order_repository = PurchaseOrderRepository(self.session_factory)
        self.policy_repository = PolicyRepository(settings)
        self.field_definition_repository = FieldDefinitionRepository(self.session_factory)
        self.po_header_field_repository = POHeaderFieldRepository(self.session_factory)
        self.po_line_item_repository = POLineItemRepository(self.session_factory)
        self.episodic_memory_repository = EpisodicMemoryRepository(self.session_factory)

        # --- checkpointer (durable Postgres-backed) ---
        self.checkpointer: AsyncPostgresSaver | None = None
        self._checkpoint_conn: AsyncConnection | None = None

        # --- clients ---
        self.bedrock_client = BedrockClient(settings)
        self.s3_client = S3Client(settings)
        self.gst_client = GSTClient(settings)
        self.whatsapp_client = WhatsAppClient(settings)

        # --- tools (agent-callable repository adapters) ---
        self.customer_tools = build_customer_tools(self.customer_repository)
        self.product_tools = build_product_tools(self.product_repository)
        self.sales_tools = build_sales_tools(self.sales_repository)
        # Read-only sale lookups for the verifier; verification never writes.
        self.customer_history_tools = build_customer_history_tool(self.sales_repository)
        self.purchase_order_tools = build_purchase_order_tools(self.purchase_order_repository)
        self.policy_tools = build_policy_tools(self.policy_repository)
        self.invoice_tools = build_invoice_tools(
            sales_repository=self.sales_repository,
            invoice_repository=self.invoice_repository,
            purchase_order_repository=self.purchase_order_repository,
            po_header_field_repository=self.po_header_field_repository,
            po_line_item_repository=self.po_line_item_repository,
            field_definition_repository=self.field_definition_repository,
        )
        # GST IRN and invoice messaging are out of the current business scope:
        # the clients and tools below are still built so either capability can be
        # re-attached without reintroducing the wiring.
        self.invoice_service_tools = build_invoice_service_tools(self.gst_client, self.s3_client)
        self.whatsapp_tools = build_whatsapp_tools(self.whatsapp_client)
        self.extraction_tools = build_extraction_tools(
            customer_repository=self.customer_repository,
            field_definition_repository=self.field_definition_repository,
            po_header_field_repository=self.po_header_field_repository,
            po_line_item_repository=self.po_line_item_repository,
            product_repository=self.product_repository,
            episodic_memory_repository=self.episodic_memory_repository,
        )

        # --- chat model (LangChain adapter over Bedrock) ---
        self.chat_model = BedrockChatModel(client=self.bedrock_client, max_tokens=2048)

        # --- agents ---
        self.extraction_agent = ExtractionAgent(
            bedrock_client=self.bedrock_client,
            s3_client=self.s3_client,
            chat_model=self.chat_model,
            settings=settings,
            customer_repository=self.customer_repository,
            field_definition_repository=self.field_definition_repository,
            po_header_field_repository=self.po_header_field_repository,
            po_line_item_repository=self.po_line_item_repository,
            product_repository=self.product_repository,
            episodic_memory_repository=self.episodic_memory_repository,
        )
        self.verifier_agent = VerifierAgent(
            header_tools=self.customer_tools,
            line_item_tools=self.product_tools,
            commercial_tools=self.policy_tools + self.customer_history_tools,
            chat_model=self.chat_model,
            settings=settings,
        )
        self.sales_agent = SalesAgent(self.purchase_order_tools + self.sales_tools, self.chat_model)
        self.invoice_agent = InvoiceAgent(self.invoice_tools + self.invoice_service_tools, self.chat_model)

        # --- orchestrators (built + compiled at startup) ---
        self.po_orchestrator: POOrchestrator | None = None
        self.invoice_orchestrator: InvoiceOrchestrator | None = None

        # --- services (built at startup once orchestrators exist) ---
        self.agent_service: AgentService | None = None
        self.hitl_service: HITLService | None = None

    async def startup(self) -> None:
        """Open the checkpointer, build the graph once, and wire services.

        Compilation happens exactly once at startup, never per request.
        """
        if self.checkpointer is None:
            conn = await AsyncConnection.connect(
                self.settings.psycopg_database_url,
                autocommit=True,
                row_factory=dict_row,
            )
            self._checkpoint_conn = conn
            self.checkpointer = AsyncPostgresSaver(conn)
            await self.checkpointer.setup()

        self.po_orchestrator = POOrchestrator(
            extraction_agent=self.extraction_agent,
            verifier_agent=self.verifier_agent,
            sales_agent=self.sales_agent,
            checkpointer=self.checkpointer,
        )
        self.invoice_orchestrator = InvoiceOrchestrator(
            invoice_agent=self.invoice_agent,
            checkpointer=self.checkpointer,
        )
        await self.po_orchestrator.compile()
        await self.invoice_orchestrator.compile()

        self.agent_service = AgentService(
            po_orchestrator=self.po_orchestrator,
            invoice_orchestrator=self.invoice_orchestrator,
            agent_run_repository=self.agent_run_repository,
            settings=self.settings,
            s3_client=self.s3_client,
            invoice_repository=self.invoice_repository,
        )
        self.hitl_service = HITLService(
            po_orchestrator=self.po_orchestrator,
            agent_run_repository=self.agent_run_repository,
        )

    async def shutdown(self) -> None:
        """Close the checkpointer's database connection, if this container owns one."""
        if self._checkpoint_conn is not None:
            await self._checkpoint_conn.close()
            self._checkpoint_conn = None
