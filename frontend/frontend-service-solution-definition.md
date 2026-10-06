# OrderFlow Frontend Solution Definition

## 1. Purpose

This document defines the frontend architecture and implementation requirements for **OrderFlow**, an enterprise B2B Order-to-Invoice management application.

**Stack:** React, Vite, TypeScript/TSX, Tailwind CSS, Zustand, TanStack Query, Bun.

The frontend implements the UX Pilot UI while staying aligned with backend API contracts. It owns presentation, interaction, client/global UI state, API communication, query caching, authentication UX, and Human-in-the-Loop interactions. It must not duplicate backend business rules.

---

## 2. UX Pilot UI Verification Baseline

The uploaded UX Pilot export contains 9 pages. The implementation should be explicitly compared against these screens.

### Page 1 — Login
- OrderFlow branding and Enterprise Order-to-Invoice Management
- Google-only sign-in
- Authorized employees only
- No email/password registration flow

### Page 2 — Dashboard
- Total Sales
- Pending Review
- AI Success Rate
- Invoices Sent
- Attention Required
- Recent Sales
- Recent Invoices
- AI Agent active indicator
- User/profile information

### Page 3 — Purchase Orders
- Search
- Status filter
- Date range
- AI confidence filter
- Clear filters
- PO number, customer, amount, status, AI verification, created, actions
- Pagination
- Upload PO CTA

### Page 4 — Human Review / PO Detail
Three-column workspace:
1. Original PO document
2. Extracted/editable data
3. AI verification

Includes customer information, PO date, line items, quantity, unit price, totals, pricing mismatch, verification checklist, auditor notes, Reject, Edit & Re-verify, and Approve.

The UI explicitly says that changes trigger re-verification.

### Page 5 — Invoices
- Total Receivables
- Pending GST Filing
- Invoices Delivered
- Invoice number/customer/PO/amount
- GST IRN status
- Invoice status
- Delivery status
- Export GST Data

### Page 6 — PO Upload
- Drag/drop uploader
- PDF, PNG, JPG and Excel
- 20 MB limit
- Upload → Extract → Verify → Sale stepper
- File selection and processing state

### Page 7 — AI Processing Logs
- System health
- Workflow run
- Triggering user
- Extraction phase
- ERP verification phase
- Human-in-the-Loop
- Sales order creation
- Durations and workflow state

### Page 8 — Sales
- Sale ID
- PO reference
- Customer
- Amount
- Status
- Created
- Created → Confirmed → Processing → Shipped → Delivered timeline

### Page 9 — Customers
- Customer search/list
- Customer overview
- Status
- Customer since
- Total orders
- Lifetime value
- Payment score
- Order History / Contacts / Shipping Addresses

These source observations are grounded in the uploaded UX Pilot export. fileciteturn8file0L2-L7 fileciteturn8file0L56-L65 fileciteturn8file0L68-L107

---

## 3. UI-to-Requirement Verification Matrix

| Screen | Required UI | Frontend implementation |
|---|---|---|
| Login | Google-only | Google sign-in; no registration/password UI |
| Dashboard | KPIs + activity + attention | TanStack Query |
| Purchase Orders | Search/filter/pagination | Query params + server-side querying |
| PO Upload | File upload + stepper | `useMutation` + workflow status |
| PO Detail | Extracted PO + verification | Query PO/run data |
| Human Review | Approve/Reject/Edit | Mutations + confirmation + refetch |
| Sales | Table + timeline | Queries |
| Invoices | Finance table | Queries; canonical invoice statuses |
| Invoice Detail | GST + document + delivery | Separate invoice/GST/delivery state |
| AI Processing | Agent timeline | Query + controlled polling |
| Customers | Search + detail/history | Queries |
| Products | CRUD | Queries + mutations |
| Responsive | Desktop/tablet/mobile | Tailwind responsive utilities |

---

## 4. Critical UI/Backend Consistency

### Invoice status

The canonical invoice status is only:

```text
GENERATED
SENT
```

Do not introduce `PAID`, `UNPAID`, `PROCESSING`, or `FAILED` as invoice statuses unless the backend explicitly defines them.

GST state and WhatsApp delivery state are separate concerns:

```text
Invoice Status: GENERATED
GST: Registered
Delivery: Retry Delivery
```

### WhatsApp failure

If delivery fails:

```text
GENERATED
   ↓
Retry Delivery
   ↓
SENT
```

Never expose `Regenerate Invoice` as the recovery action.

### Human review

```text
APPROVE → Sale creation
REJECT  → Workflow ends
EDIT    → Re-verification
```

The frontend never decides whether AI verification passes.

### Sale delivery

When a sale becomes `DELIVERED`, the backend triggers invoice processing. The browser only displays the resulting state; it must not orchestrate the invoice workflow.

---

## 5. Architecture

```text
React Components
      ↓
Feature Hooks
      ↓
TanStack Query / Zustand
      ↓
Feature api.ts
      ↓
HTTP Client
      ↓
Go API / Python API
```

Components must never contain raw `fetch`/Axios endpoint calls.

Correct:

```text
Component
  ↓
usePurchaseOrders()
  ↓
purchaseOrderApi.getPurchaseOrders()
  ↓
httpClient
  ↓
Backend
```

---

## 6. Folder Structure

```text
orderflow-frontend/
├── public/
├── src/
│   ├── app/
│   │   ├── App.tsx
│   │   ├── router.tsx
│   │   ├── providers.tsx
│   │   └── query-client.ts
│   ├── assets/
│   ├── components/
│   │   ├── ui/
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Select.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── Drawer.tsx
│   │   │   ├── Badge.tsx
│   │   │   ├── Table.tsx
│   │   │   ├── Tabs.tsx
│   │   │   ├── Skeleton.tsx
│   │   │   └── EmptyState.tsx
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── Breadcrumbs.tsx
│   │   └── common/
│   │       ├── StatusBadge.tsx
│   │       ├── PageHeader.tsx
│   │       ├── DataTable.tsx
│   │       ├── ConfirmDialog.tsx
│   │       ├── ErrorState.tsx
│   │       └── LoadingState.tsx
│   ├── features/
│   │   ├── auth/
│   │   │   ├── api.ts
│   │   │   ├── hooks.ts
│   │   │   ├── types.ts
│   │   │   ├── components/
│   │   │   └── pages/LoginPage.tsx
│   │   ├── dashboard/
│   │   │   ├── api.ts
│   │   │   ├── hooks.ts
│   │   │   ├── types.ts
│   │   │   ├── components/
│   │   │   └── pages/DashboardPage.tsx
│   │   ├── purchase-orders/
│   │   │   ├── api.ts
│   │   │   ├── hooks.ts
│   │   │   ├── types.ts
│   │   │   ├── schemas.ts
│   │   │   ├── components/
│   │   │   └── pages/
│   │   │       ├── PurchaseOrdersPage.tsx
│   │   │       ├── PurchaseOrderDetailPage.tsx
│   │   │       ├── PurchaseOrderUploadPage.tsx
│   │   │       └── HumanReviewPage.tsx
│   │   ├── sales/
│   │   │   ├── api.ts
│   │   │   ├── hooks.ts
│   │   │   ├── types.ts
│   │   │   ├── components/
│   │   │   └── pages/
│   │   ├── invoices/
│   │   │   ├── api.ts
│   │   │   ├── hooks.ts
│   │   │   ├── types.ts
│   │   │   ├── components/
│   │   │   └── pages/
│   │   ├── customers/
│   │   │   ├── api.ts
│   │   │   ├── hooks.ts
│   │   │   ├── types.ts
│   │   │   ├── components/
│   │   │   └── pages/
│   │   ├── products/
│   │   │   ├── api.ts
│   │   │   ├── hooks.ts
│   │   │   ├── types.ts
│   │   │   ├── components/
│   │   │   └── pages/
│   │   └── ai-processing/
│   │       ├── api.ts
│   │       ├── hooks.ts
│   │       ├── types.ts
│   │       ├── components/
│   │       └── pages/
│   ├── stores/
│   │   ├── authStore.ts
│   │   ├── uiStore.ts
│   │   ├── reviewStore.ts
│   │   └── uploadStore.ts
│   ├── lib/
│   │   ├── httpClient.ts
│   │   ├── queryKeys.ts
│   │   ├── storage.ts
│   │   └── utils.ts
│   ├── constants.ts
│   ├── types/
│   │   ├── api.ts
│   │   └── common.ts
│   ├── styles/index.css
│   └── main.tsx
├── .env.example
├── .gitignore
├── bun.lock
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── eslint.config.js
├── tailwind.config.ts
├── postcss.config.js
└── README.md
```

---

## 7. `constants.ts`

All application-wide constants go in:

```text
src/constants.ts
```

Example:

```ts
export const API_BASE_URLS = {
  GO: import.meta.env.VITE_GO_API_BASE_URL,
  PYTHON: import.meta.env.VITE_PYTHON_API_BASE_URL,
} as const;

export const ROUTES = {
  LOGIN: "/login",
  DASHBOARD: "/dashboard",
  PURCHASE_ORDERS: "/purchase-orders",
  SALES: "/sales",
  INVOICES: "/invoices",
  CUSTOMERS: "/customers",
  PRODUCTS: "/products",
  AI_PROCESSING: "/ai-processing",
} as const;

export const PO_FILE_LIMIT_MB = 20;

export const INVOICE_STATUS = {
  GENERATED: "GENERATED",
  SENT: "SENT",
} as const;
```

No scattered magic strings or hardcoded URLs.

---

## 8. Per-Module `api.ts`

Every feature owns its API functions:

```text
features/
└── purchase-orders/
    └── api.ts
```

`api.ts` contains HTTP communication only.

Example:

```ts
export const purchaseOrderApi = {
  getPurchaseOrders: async (
    params: PurchaseOrderFilters
  ): Promise<PurchaseOrderListResponse> => {
    const response = await goHttpClient.get(
      "/api/v1/purchase-orders",
      { params }
    );
    return response.data;
  },

  getPurchaseOrder: async (id: string) => {
    const response = await goHttpClient.get(
      `/api/v1/purchase-orders/${id}`
    );
    return response.data;
  },

  uploadPurchaseOrder: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await pythonHttpClient.post(
      "/api/v1/agents/purchase-orders/process",
      formData
    );
    return response.data;
  },
};
```

Components call hooks; hooks call `api.ts`.

---

## 9. Backend Base URLs

Use two frontend environment variables:

```env
VITE_GO_API_BASE_URL=http://localhost:8080
VITE_PYTHON_API_BASE_URL=http://localhost:8000
```

### Go API

Owns normal application CRUD/auth:

```text
/auth
/customers
/products
/purchase-orders
/sales
/invoices
/dashboard
```

### Python API

Owns AI workflow operations:

```text
/api/v1/agents/purchase-orders/process
/api/v1/agents/purchase-orders/:runId/decision
/api/v1/agents/runs/:runId
```

The frontend must never call:

```text
POST /api/v1/internal/events/sale-delivered
```

That is a backend-to-backend Go → Python event.

---

## 10. HTTP Client

Create centralized clients in:

```text
src/lib/httpClient.ts
```

Recommended:

```text
goHttpClient
pythonHttpClient
```

Responsibilities:
- Base URL
- Authorization
- Common response/error handling
- 401 handling
- Timeout
- Request configuration

No feature-specific business logic.

---

## 11. TanStack Query

Use TanStack Query for all server state.

### `useQuery`

Use for:
- Dashboard
- PO list/detail
- Sales list/detail
- Invoice list/detail
- Customer list/detail
- Product list/detail
- AI workflow run

### `useMutation`

Use for:
- PO upload/process
- Approve
- Reject
- Edit & re-verify
- Customer create/update
- Product create/update
- Sale status update
- WhatsApp retry delivery

Example:

```ts
const approveMutation = useMutation({
  mutationFn: () =>
    purchaseOrderApi.submitDecision(runId, {
      decision: "APPROVE",
    }),
  onSuccess: () => {
    queryClient.invalidateQueries({
      queryKey: queryKeys.purchaseOrders.all,
    });
  },
});
```

---

## 12. Query Keys

Create:

```text
src/lib/queryKeys.ts
```

Example:

```ts
export const queryKeys = {
  purchaseOrders: {
    all: ["purchase-orders"] as const,
    list: (filters: PurchaseOrderFilters) =>
      ["purchase-orders", "list", filters] as const,
    detail: (id: string) =>
      ["purchase-orders", "detail", id] as const,
  },
  sales: {
    all: ["sales"] as const,
    list: (filters: SaleFilters) =>
      ["sales", "list", filters] as const,
    detail: (id: string) =>
      ["sales", "detail", id] as const,
  },
  invoices: {
    all: ["invoices"] as const,
    list: (filters: InvoiceFilters) =>
      ["invoices", "list", filters] as const,
    detail: (id: string) =>
      ["invoices", "detail", id] as const,
  },
};
```

Avoid hardcoded query keys in components.

---

## 13. Zustand

Zustand is for client/global UI state, not server state.

Good candidates:

```text
Sidebar collapsed state
Modal/drawer state
Review editor state
Temporary upload UI state
Unsaved form/UI preferences
```

Do not store server collections in Zustand:

```text
customers → TanStack Query
purchaseOrders → TanStack Query
sales → TanStack Query
invoices → TanStack Query
```

The authoritative data always comes from the backend.

---

## 14. Human Review

The Human Review page is a critical workflow.

Suggested UI state:

```ts
interface ReviewState {
  isEditMode: boolean;
  selectedLineItemId: string | null;
  auditorNote: string;
  isConfirmDialogOpen: boolean;
}
```

Authoritative PO/run data comes from TanStack Query.

Flow:

```text
Fetch workflow
    ↓
Render extracted data
    ↓
User edits
    ↓
Submit EDIT mutation
    ↓
Backend re-verifies
    ↓
Refetch workflow + PO
```

The frontend does not decide whether the PO passes verification.

---

## 15. PO Upload

Support the UX source requirements:

```text
PDF
PNG
JPG
Excel
```

Maximum:

```text
20 MB
```

Client-side validation is for immediate UX feedback; backend validation remains authoritative.

UI states:

```text
IDLE
SELECTED
UPLOADING
PROCESSING
COMPLETED
FAILED
```

Stepper:

```text
Upload → Extract → Verify → Sale
```

Do not display fake progress.

---

## 16. AI Processing

Show backend workflow state:

```text
Extraction
  ✓ Completed
  1.2s

Verification
  ✓ Completed
  0.8s

Human Review
  ● Pending

Sales Order Creation
  ○ Waiting
```

While active:
- Poll/refetch through TanStack Query
- Stop polling at terminal state
- Use backend timestamps/durations
- Show real errors
- Do not invent progress percentages

Example:

```text
RUNNING
  ↓ polling
WAITING_FOR_HUMAN
  ↓ stop polling
```

---

## 17. Dashboard

Use TanStack Query for:
- Summary KPIs
- Recent sales
- Recent invoices
- Pending reviews

The dashboard should retain the source hierarchy:

```text
KPI Cards
Attention Required
Recent Sales
Recent Invoices
```

Do not ship mock data in production.

---

## 18. Purchase Order List

Required:
- Search
- Status filter
- Date range
- AI confidence filter
- Clear filters
- Pagination
- Upload PO
- Row action

Prefer server-side filtering/pagination for large datasets.

Example:

```text
/purchase-orders?search=PO-4421&status=PENDING_REVIEW&page=1
```

Use URL state for navigable filters where practical.

---

## 19. Sales

List fields:

```text
Sale ID
PO Reference
Customer
Amount
Status
Created
```

Timeline:

```text
Created
Confirmed
Processing
Shipped
Delivered
```

Only show actions permitted by backend state/transition rules.

---

## 20. Invoices

Separate these concepts:

### Invoice status

```text
GENERATED
SENT
```

### GST/e-Invoice status

```text
Processing
Registered
```

### Delivery status

```text
Pending
Delivered
Retry Delivery
```

The frontend should render these as separate fields if returned by the API.

Invoice workflow:

```text
Sale Delivered
  ↓
Generate Invoice
  ↓
GST/e-Invoice
  ↓
Store Document
  ↓
GENERATED
  ↓
WhatsApp
  ↓
SENT
```

If WhatsApp fails:

```text
GENERATED + Retry Delivery
```

---

## 21. Customers

Support:
- Search
- Customer list
- Customer detail
- Status
- Customer since
- Total orders
- Lifetime value
- Payment score if returned
- Order History
- Contacts
- Shipping Addresses

Do not calculate financial metrics in the browser unless explicitly required.

---

## 22. Products

Feature structure:

```text
products/
├── api.ts
├── hooks.ts
├── types.ts
├── components/
└── pages/
```

Support list, search, detail, create and update.

---

## 23. Component Management

### UI components

Generic reusable:

```text
Button
Input
Modal
Badge
Table
Tabs
Drawer
Skeleton
```

### Common components

Application-wide:

```text
PageHeader
DataTable
StatusBadge
ConfirmDialog
ErrorState
```

### Feature components

Domain-specific:

```text
VerificationPanel
POUploader
SaleTimeline
InvoiceTimeline
CustomerHistory
```

Do not build entire pages as monolithic components.

---

## 24. TypeScript

Enable strict mode.

Rules:
- Avoid `any`
- Define API request/response types
- Define component prop types
- Use discriminated unions
- Keep feature types near the feature
- Match backend enums exactly

Example:

```ts
type InvoiceStatus = "GENERATED" | "SENT";
```

Avoid:

```ts
type InvoiceStatus = string;
```

---

## 25. Tailwind CSS

Tailwind is the primary styling system.

Visual direction:
- Light enterprise SaaS
- White surfaces
- Subtle borders
- Compact spacing
- Blue/indigo primary action
- Green success
- Amber review/pending
- Red destructive/error
- Blue processing
- Dense but readable tables

Avoid:
- Excessive gradients
- Glassmorphism
- Large decorative illustrations
- Chatbot aesthetics
- Excessive animation

Use shared Tailwind theme tokens where appropriate.

---

## 26. Responsive Design

Support:

```text
Desktop
Tablet
Mobile
```

Human Review desktop:

```text
Document | Extracted Data | Verification
```

Mobile:

```text
Document
↓
Extracted Data
↓
Verification
```

For tables:
- Horizontal scroll when appropriate
- Hide low-priority columns
- Preserve readable primary information
- Provide detail navigation

Sidebar:
- Desktop: expanded/collapsed
- Mobile: drawer

---

## 27. Routing

Recommended routes:

```text
/login

/dashboard

/purchase-orders
/purchase-orders/upload
/purchase-orders/:id
/purchase-orders/:id/review

/sales
/sales/:id

/invoices
/invoices/:id

/customers

/products

/ai-processing
/ai-processing/:runId
```

Protected routes require authenticated application state.

---

## 28. Authentication

UI requirement:

```text
Google Sign-In only
```

No:
- Email/password login
- Registration
- Create-account screen

Frontend:
1. Display Google sign-in
2. Start backend-supported OAuth flow
3. Handle authenticated session/callback
4. Keep minimum required auth state
5. Redirect authenticated users to dashboard
6. Redirect unauthenticated users to login

User creation is never a frontend responsibility.

---

## 29. Loading / Error / Empty States

Every API screen must support:

```text
Loading
Success
Empty
Error
```

Use skeletons where practical.

Error example:

```text
Something went wrong
Unable to load purchase orders.
Retry
```

Empty example:

```text
No purchase orders found
Try changing your filters or upload a new purchase order.
```

---

## 30. Mutation UX

Business-critical actions need feedback.

Reject:
- Confirmation dialog

Approve:
- Loading state
- Disable duplicate submission
- Success feedback

Edit:
- Clearly state that changes trigger re-verification

After mutation:
- Toast/notification
- Invalidate relevant queries
- Refetch authoritative state
- Navigate only when appropriate

---

## 31. Query Optimization

Configure TanStack Query centrally.

Use:
- Stable query keys
- Appropriate stale times
- Query invalidation after mutations
- Avoid duplicate requests
- Controlled workflow polling
- Stop polling at terminal states
- Prefetch detail data where useful
- Preserve previous data for paginated lists where appropriate

---

## 32. Environment

`.env.example`:

```env
VITE_GO_API_BASE_URL=http://localhost:8080
VITE_PYTHON_API_BASE_URL=http://localhost:8000
```

Never hardcode environment-specific URLs.

Never place secrets in Vite environment variables because browser-exposed `VITE_*` values are public.

---

## 33. Bun

Use Bun for dependency management and scripts.

```bash
bun install
bun add <package>
bun add -d <package>
bun run dev
```

Do not mix npm/yarn/pnpm installation workflows.

Lockfile:

```text
bun.lock
```

---

## 34. Package Scripts

Recommended:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "format": "prettier --write .",
    "format-check": "prettier --check .",
    "type-check": "tsc --noEmit",
    "check": "bun run type-check && bun run lint && bun run format-check && bun run build"
  }
}
```

---

## 35. Testing

### Unit
- Utility functions
- Zustand stores
- Status mapping
- Form validation
- Query helpers

### Component
- PO table
- Verification panel
- Upload component
- Invoice status
- Sale timeline
- Human Review actions

### Integration
Test:

```text
Upload PO
→ Processing
→ Human Review
→ Approve
→ Sale created
```

```text
Human Review
→ Edit
→ Re-verification
→ Fail
→ Human Review again
```

```text
Sale Delivered
→ Invoice GENERATED
→ Retry WhatsApp
→ Invoice SENT
```

---

## 36. UI Verification Checklist

### Visual
- [ ] Matches UX Pilot layout
- [ ] Navigation hierarchy matches
- [ ] Typography hierarchy is consistent
- [ ] Spacing is consistent
- [ ] Cards/tables have consistent borders/radius
- [ ] Status badges use consistent semantics
- [ ] Button hierarchy is correct
- [ ] Responsive behavior works

### Functional
- [ ] Navigation works
- [ ] Search works
- [ ] Filters work
- [ ] Pagination works
- [ ] Detail navigation works
- [ ] Upload works
- [ ] Approve works
- [ ] Reject works
- [ ] Edit & re-verify works
- [ ] Sale status renders correctly
- [ ] Invoice status renders correctly
- [ ] Retry delivery works
- [ ] Duplicate mutation submission is prevented

### Data
- [ ] No production mock data
- [ ] API types match backend
- [ ] Loading states work
- [ ] Error states work
- [ ] Empty states work
- [ ] Query invalidation is correct
- [ ] Workflow polling stops at terminal state

### Business
- [ ] Invoice status is only GENERATED/SENT
- [ ] GST state is separate
- [ ] Delivery state is separate
- [ ] WhatsApp failure does not suggest regeneration
- [ ] Frontend never decides AI verification outcome
- [ ] Frontend never creates users during Google authentication
- [ ] Frontend never calls the internal sale-delivered endpoint

---

## 37. Implementation Order

```text
1. Vite + React + TypeScript setup
2. Bun configuration
3. Tailwind + design tokens
4. HTTP clients
5. TanStack Query provider
6. Zustand stores
7. Router + protected routes
8. Shared UI components
9. App layout/sidebar/header
10. Google authentication
11. Dashboard
12. Purchase Order list
13. PO upload
14. PO detail
15. Human Review
16. Sales
17. Invoices
18. Customers
19. Products
20. AI Processing
21. Responsive pass
22. Loading/error/empty states
23. API integration verification
24. End-to-end workflow verification
25. Production build validation
```

---

## 38. Definition of Done

The frontend is complete when:

```text
UX Pilot reference
      ↓
React implementation
      ↓
Actual backend APIs
      ↓
TanStack Query for server state
      ↓
Zustand for client/global UI state
      ↓
Per-feature api.ts
      ↓
constants.ts
      ↓
Tailwind styling
      ↓
Strict TypeScript
      ↓
Lint/type/build checks
      ↓
Responsive verification
      ↓
Business workflow verification
```

Final user journey:

```text
Google Sign-In
      ↓
Dashboard
      ↓
Upload Purchase Order
      ↓
AI Extraction
      ↓
AI Verification
      ↓
PASS → Sale Created
          ↓
       Delivered
          ↓
    Invoice Generated
          ↓
      GST/e-Invoice
          ↓
       GENERATED
          ↓
     WhatsApp Send
          ↓
         SENT

FAIL
 ↓
Human Review
 ├── Reject → Workflow Ends
 ├── Approve → Sale Created
 └── Edit
      ↓
 Re-verification
      ↓
 Pass → Sale Created
 Fail → Human Review again
```

The frontend provides a faithful, responsive representation of the UX Pilot design while treating backend APIs as the source of truth for data, status and business decisions.
