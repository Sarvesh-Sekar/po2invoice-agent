import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useSearchParams } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { ROUTES } from "@/constants";

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const setAuth = useAuthStore((state) => state.setAuth);

  useEffect(() => {
    const accessToken = searchParams.get("access_token");
    const refreshToken = searchParams.get("refresh_token");

    if (accessToken && refreshToken) {
      setAuth(
        { access_token: accessToken, refresh_token: refreshToken, token_type: "Bearer" },
        { id: "", name: "", email: "", role: "USER", is_active: true, created_at: "", updated_at: "" }
      );
      navigate(ROUTES.DASHBOARD, { replace: true });
      return;
    }

    const error = searchParams.get("error");
    if (error) {
      navigate(`${ROUTES.LOGIN}?error=${encodeURIComponent(error)}`, { replace: true });
      return;
    }

    navigate(ROUTES.LOGIN, { replace: true });
  }, [searchParams, navigate, setAuth]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
        <p className="text-sm text-gray-500">Completing Google sign-in…</p>
      </div>
    </div>
  );
}