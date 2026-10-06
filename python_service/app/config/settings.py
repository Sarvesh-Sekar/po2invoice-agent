from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into the process environment once, so every consumer of os.environ
# (boto3's credential/region chain, the LangChain chat model, workers) sees the
# same values that Settings reads. Real environment variables win over .env.
load_dotenv(override=False)


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "poin-python-service"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_format: str = Field(default="text", description="Application log format: 'text' or 'json'")

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://sarvesh:1234@localhost:5432/poin_db",
        description="Async SQLAlchemy database URL",
    )
    db_echo: bool = False

    # --- Auth: internal service auth ---
    internal_api_key: str | None = Field(
        default=None, description="Shared secret Go sends via X-Internal-API-Key for internal endpoints"
    )

    # --- Auth: frontend-facing user JWT ---
    require_auth: bool = Field(default=True, description="Enforce user authentication on frontend-facing APIs")
    jwt_secret: str | None = Field(default=None, description="HS256 secret shared with Go for access-token checks")
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm for access tokens")
    jwt_issuer: str | None = Field(default=None, description="Expected JWT `iss` claim, when tokens carry one")
    jwt_audience: str | None = Field(default=None, description="Expected JWT `aud` claim, when tokens carry one")

    # --- Upload limits ---
    max_upload_size_mb: int = 10
    allowed_file_extensions: str = "pdf,png,jpg,jpeg,tif,tiff"

    # --- AWS Bedrock ---
    aws_region: str | None = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_bedrock_model_id: str = "amazon.nova-pro-v1:0"
    aws_bedrock_ocr_model_id: str = "amazon.nova-pro-v1:0"
    aws_bedrock_guardrail_id: str | None = None
    aws_bedrock_guardrail_version: str | None = Field(
        default=None, description="Guardrail version; required by the Converse API alongside the identifier"
    )
    # --- Bedrock retry settings ---
    aws_bedrock_max_attempts: int = Field(default=8, description="Botocore max retry attempts for Bedrock")
    aws_bedrock_retry_mode: str = Field(default="adaptive", description="Botocore retry mode: standard|adaptive")
    aws_bedrock_app_retry_attempts: int = Field(default=6, description="App-level tenacity retries for Bedrock calls")
    aws_bedrock_connect_timeout: int = Field(default=10, description="Bedrock connect timeout seconds")
    aws_bedrock_read_timeout: int = Field(default=60, description="Bedrock read timeout seconds")
    aws_bedrock_max_pool_connections: int = Field(default=50, description="Bedrock max pool connections")

    # --- AWS S3 ---
    aws_s3_bucket: str | None = None
    aws_s3_key_prefix: str | None = None

    # --- GST / e-invoice ---
    gst_api_url: str | None = None
    gst_api_key: str | None = None

    # --- WhatsApp ---
    whatsapp_api_url: str | None = None
    whatsapp_token: str | None = None

    # --- Verification (VerifierAgent business rules) ---
    verification_price_tolerance: float = Field(
        default=0.01,
        description="Absolute rupee tolerance for the catalogue price comparison in line-item validation",
    )
    verification_branch_failure_is_blocking: bool = Field(
        default=True,
        description="Treat an unusable validator branch result as a blocking issue (HITL) instead of a run failure",
    )

    # --- Evaluation ---
    mlflow_tracking_uri: str = "mlruns"

    # --- Extraction subgraph ---
    extraction_max_retries: int = Field(default=3, description="Maximum recovery/re-extraction attempts per field")
    extraction_min_evidence_score: float = Field(
        default=0.75, description="Minimum aggregate evidence score required by the quality gate"
    )
    extraction_min_evidence_sources: int = Field(
        default=2, description="Minimum independent evidence sources required by the quality gate"
    )
    extraction_candidate_separation: float = Field(
        default=0.15, description="Minimum score margin between the best candidate and alternatives"
    )
    extraction_validated_confidence: float = Field(
        default=0.8, description="Confidence assigned to newly validated episodic patterns"
    )
    # --- Evaluation tuning (throttling/loop mitigation) ---
    extraction_evaluation_concurrency: int = Field(
        default=2, description="Max concurrent validation calls to Bedrock"
    )
    extraction_evaluation_batch_size: int = Field(
        default=2, description="Number of candidates per evaluation batch call"
    )
    extraction_max_candidates_per_field: int = Field(
        default=3, description="Max candidates to evaluate per field"
    )
    extraction_max_evaluations_total: int = Field(
        default=24, description="Max total evaluation calls/batches per run"
    )
    extraction_evaluation_max_retries: int = Field(
        default=3, description="Max retries for individual evaluation calls on retryable errors"
    )
    extraction_evaluation_backoff_base: float = Field(
        default=0.5, description="Exponential backoff base seconds for evaluation retries"
    )
    extraction_evaluation_backoff_mult: float = Field(
        default=1.5, description="Exponential backoff multiplier for evaluation retries"
    )
    extraction_evaluation_backoff_max: float = Field(
        default=8.0, description="Max backoff seconds for evaluation retries"
    )
    extraction_no_progress_threshold_retries: int = Field(
        default=1, description="Retries allowed after candidate signature becomes stable before failing"
    )
    field_definitions_seed_file: str = "field_definitions.yaml"

    @field_validator("allowed_file_extensions")
    @classmethod
    def _normalize_extensions(cls, value: str) -> str:
        return value.lower().replace(" ", "")

    @property
    def allowed_extensions(self) -> set[str]:
        return set(self.allowed_file_extensions.split(","))

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def psycopg_database_url(self) -> str:
        """Postgres URL accepted by psycopg (LangGraph's AsyncPostgresSaver)."""
        return self.database_url.replace("+asyncpg", "", 1)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
