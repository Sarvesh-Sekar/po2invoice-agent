import { Suspense, lazy, type ComponentType } from "react";
import { Navigate, Outlet, RouterProvider, createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { LoadingState } from "@/components/common/LoadingState";
import { useAuthStore } from "@/stores/authStore";
import { ROUTES } from "@/constants";

function lazyPage(loader: () => Promise<{ default: ComponentType }>) {
  const Component = lazy(async () => {
    const mod = await loader();
    return { default: mod.default };
  });

  function Page() {
    return (
      <Suspense
        fallback={
          <div className="p-0">
            <LoadingState title="Loading" />
          </div>
        }
      >
        <Component />
      </Suspense>
    );
  }
  Page.displayName = "LazyPage";
  return Page;
}

const LoginPage = lazyPage(() =>
  import("@/features/auth/pages/LoginPage").then((m) => ({ default: m.LoginPage }))
);
const AuthCallbackPage = lazyPage(() =>
  import("@/features/auth/pages/AuthCallbackPage").then((m) => ({
    default: m.AuthCallbackPage,
  }))
);
const DashboardPage = lazyPage(() =>
  import("@/features/dashboard/pages/DashboardPage").then((m) => ({
    default: m.DashboardPage,
  }))
);
const PurchaseOrdersPage = lazyPage(() =>
  import("@/features/purchase-orders/pages/PurchaseOrdersPage").then((m) => ({
    default: m.PurchaseOrdersPage,
  }))
);
const PurchaseOrderUploadPage = lazyPage(() =>
  import("@/features/purchase-orders/pages/PurchaseOrderUploadPage").then((m) => ({
    default: m.PurchaseOrderUploadPage,
  }))
);
const HumanReviewPage = lazyPage(() =>
  import("@/features/purchase-orders/pages/HumanReviewPage").then((m) => ({
    default: m.HumanReviewPage,
  }))
);
const SalesPage = lazyPage(() =>
  import("@/features/sales/pages/SalesPage").then((m) => ({ default: m.SalesPage }))
);
const InvoiceListPage = lazyPage(() =>
  import("@/features/invoices/pages/InvoicesPage").then((m) => ({
    default: m.InvoicesPage,
  }))
);
const CustomerListPage = lazyPage(() =>
  import("@/features/customers/pages/CustomersPage").then((m) => ({
    default: m.CustomersPage,
  }))
);
const ProductListPage = lazyPage(() =>
  import("@/features/products/pages/ProductsPage").then((m) => ({
    default: m.ProductsPage,
  }))
);
const AiProcessingPage = lazyPage(() =>
  import("@/features/ai-processing/pages/AiProcessingPage").then((m) => ({
    default: m.AiProcessingPage,
  }))
);

function RequireAuth() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  if (!isAuthenticated) return <Navigate to={ROUTES.LOGIN} replace />;
  return <Outlet />;
}

export const router = createBrowserRouter([
  {
    path: ROUTES.LOGIN,
    element: <LoginPage />,
  },
  {
    path: "/",
    element: <AuthCallbackPage />,
  },
  {
    path: ROUTES.AUTH_CALLBACK,
    element: <AuthCallbackPage />,
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: ROUTES.DASHBOARD, element: <DashboardPage /> },
          { path: ROUTES.PURCHASE_ORDERS, element: <PurchaseOrdersPage /> },
          { path: ROUTES.PURCHASE_ORDER_UPLOAD, element: <PurchaseOrderUploadPage /> },
          { path: ROUTES.PURCHASE_ORDER_REVIEW, element: <HumanReviewPage /> },
          { path: ROUTES.SALES, element: <SalesPage /> },
          { path: ROUTES.INVOICES, element: <InvoiceListPage /> },
          { path: ROUTES.CUSTOMERS, element: <CustomerListPage /> },
          { path: ROUTES.PRODUCTS, element: <ProductListPage /> },
          { path: ROUTES.AI_PROCESSING, element: <AiProcessingPage /> },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <Navigate to={ROUTES.DASHBOARD} replace />,
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
