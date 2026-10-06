import { useSearchParams } from "react-router-dom";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { ROUTES } from "@/constants";
import { GoogleSignInButton } from "@/features/auth/components/GoogleSignInButton";

export function LoginPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const [searchParams] = useSearchParams();
  const error = searchParams.get("error");

  if (isAuthenticated) {
    return <Navigate to={ROUTES.DASHBOARD} replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <div className="rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
          <div className="mb-6 flex flex-col items-center text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-indigo-600 text-xl font-bold text-white">
              OF
            </div>
            <h1 className="text-2xl font-semibold text-gray-900">OrderFlow</h1>
            <p className="mt-1 text-sm text-gray-500">
              Enterprise Order-to-Invoice Management
            </p>
          </div>

          <GoogleSignInButton />

          <div className="mt-4">
            {error ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                Could not complete authentication. {error}
              </div>
            ) : (
              <p className="text-center text-xs text-gray-400">
                Authorized employees only. Access is managed by your organization.
              </p>
            )}
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-gray-400">
          OrderFlow · Enterprise Order-to-Invoice Management
        </p>
      </div>
    </div>
  );
}