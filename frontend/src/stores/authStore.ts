import { create } from "zustand";
import { storage } from "@/lib/storage";
import type { AuthTokens, User } from "@/types/api";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  setAuth: (tokens: AuthTokens, user: User) => void;
  setUser: (user: User) => void;
  setTokens: (tokens: AuthTokens) => void;
  logout: () => void;
  hydrate: () => void;
}

function parseStoredUser(): User | null {
  const raw = storage.getUser();
  if (!raw) return null;
  return raw as unknown as User;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,

  hydrate: () => {
    const tokens = storage.getTokens();
    const user = parseStoredUser();
    set({
      user,
      accessToken: tokens?.access_token ?? null,
      isAuthenticated: Boolean(tokens?.access_token),
    });
  },

  setAuth: (tokens, user) => {
    storage.setTokens(tokens);
    storage.setUser(user as unknown as Record<string, unknown>);
    set({ user, accessToken: tokens.access_token, isAuthenticated: true });
  },

  setUser: (user) => {
    storage.setUser(user as unknown as Record<string, unknown>);
    set({ user });
  },

  setTokens: (tokens) => {
    storage.setTokens(tokens);
    set({ accessToken: tokens.access_token, isAuthenticated: true });
  },

  logout: () => {
    storage.clearAuth();
    set({ user: null, accessToken: null, isAuthenticated: false });
  },
}));