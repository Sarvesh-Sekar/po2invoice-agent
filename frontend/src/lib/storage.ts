const AUTH_TOKENS_KEY = "orderflow.auth.tokens";
const AUTH_USER_KEY = "orderflow.auth.user";

export const storage = {
  getTokens(): { access_token: string; refresh_token: string } | null {
    const raw = localStorage.getItem(AUTH_TOKENS_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as { access_token: string; refresh_token: string };
    } catch {
      return null;
    }
  },

  setTokens(tokens: {
    access_token: string;
    refresh_token: string;
  }): void {
    localStorage.setItem(AUTH_TOKENS_KEY, JSON.stringify(tokens));
  },

  clearTokens(): void {
    localStorage.removeItem(AUTH_TOKENS_KEY);
  },

  getUser(): Record<string, unknown> | null {
    const raw = localStorage.getItem(AUTH_USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return null;
    }
  },

  setUser(user: Record<string, unknown>): void {
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  },

  clearUser(): void {
    localStorage.removeItem(AUTH_USER_KEY);
  },

  clearAuth(): void {
    this.clearTokens();
    this.clearUser();
  },
};