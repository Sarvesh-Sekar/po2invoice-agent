import { useLocation, useNavigate } from "react-router-dom";
import { authApi } from "@/features/auth/api";
import { ROUTES } from "@/constants";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { queryClient } from "@/app/query-client";
import { initials } from "@/lib/utils";

export function Header() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);
  const setMobileNavOpen = useUIStore((state) => state.setMobileNavOpen);
  const logout = useAuthStore((state) => state.logout);

  const pathLabel = location.pathname.split("/").filter(Boolean)[0] ?? "Dashboard";
  const title = pathLabel.charAt(0).toUpperCase() + pathLabel.slice(1).replace(/-/g, " ");

  async function handleLogout() {
    try {
      await authApi.logout();
    } catch {
      // logout still proceeds locally even if the server call fails
    }
    logout();
    queryClient.clear();
    navigate(ROUTES.LOGIN);
  }

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-gray-200 bg-white px-4">
      <button
        type="button"
        className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 lg:hidden"
        onClick={() => setMobileNavOpen(true)}
        aria-label="Open navigation"
      >
        <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z"
            clipRule="evenodd"
          />
        </svg>
      </button>
      <button
        type="button"
        className="hidden rounded-md p-1.5 text-gray-500 hover:bg-gray-100 lg:block"
        onClick={toggleSidebar}
        aria-label="Toggle sidebar"
      >
        <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      <div>
        <h1 className="text-sm font-semibold text-gray-900">{title}</h1>
        <p className="hidden text-xs text-gray-500 sm:block">Enterprise Order-to-Invoice Management</p>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <div className="hidden items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-1 sm:flex">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
          </span>
          <span className="text-xs font-medium text-green-700">AI Agent Active</span>
        </div>

        <div className="flex items-center gap-2">
          {user && (
            <div className="hidden text-right leading-tight sm:block">
              <p className="text-sm font-medium text-gray-800">{user.name}</p>
              <p className="text-xs text-gray-500">{user.role}</p>
            </div>
          )}
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
            {user ? initials(user.name) : "?"}
          </div>
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className="rounded-md px-2.5 py-1.5 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}