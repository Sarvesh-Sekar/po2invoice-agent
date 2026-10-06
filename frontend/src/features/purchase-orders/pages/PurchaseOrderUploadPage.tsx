import { useEffect } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { POUploader } from "@/features/purchase-orders/components/POUploader";
import { useUploadStore } from "@/stores/uploadStore";
import { ROUTES } from "@/constants";

export function PurchaseOrderUploadPage() {
  const reset = useUploadStore((state) => state.reset);

  useEffect(() => {
    reset();
  }, [reset]);

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageHeader
        title="Upload Purchase Order"
        description="Upload a document and let the AI agent extract, verify and create a sale."
        actions={
          <Link
            to={ROUTES.PURCHASE_ORDERS}
            className="text-sm font-medium text-indigo-600 hover:text-indigo-700"
          >
            Back to list
          </Link>
        }
      />
      <POUploader />
    </div>
  );
}