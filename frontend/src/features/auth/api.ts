import { goHttpClient } from "@/lib/httpClient";
import type { AuthTokens, LoginRequest, RefreshRequest, User } from "@/types/api";

export const authApi = {
  async login(payload: LoginRequest): Promise<AuthTokens> {
    return goHttpClient.post<AuthTokens>("/auth/login", payload);
  },

  async refresh(payload: RefreshRequest): Promise<AuthTokens> {
    return goHttpClient.post<AuthTokens>("/auth/refresh", payload);
  },

  async logout(): Promise<void> {
    await goHttpClient.request<void>("/auth/logout", "POST");
  },

  async me(): Promise<User> {
    return goHttpClient.get<User>("/auth/me");
  },
};

export function googleSignInUrl(): string {
  return `${goHttpClient.baseUrl}/auth/google`;
}