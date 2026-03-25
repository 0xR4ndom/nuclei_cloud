import Cookies from "js-cookie";
import { authApi } from "./api";
import type { User, Token } from "@/types";

const COOKIE_OPTS = { secure: true, sameSite: "strict" as const };

export async function login(email: string, password: string): Promise<User> {
  const { data }: { data: Token } = await authApi.login(email, password);
  Cookies.set("access_token", data.access_token, COOKIE_OPTS);
  Cookies.set("refresh_token", data.refresh_token, COOKIE_OPTS);
  const { data: user } = await authApi.me();
  return user;
}

export function logout() {
  Cookies.remove("access_token");
  Cookies.remove("refresh_token");
  window.location.href = "/auth/login";
}

export function isAuthenticated(): boolean {
  return !!Cookies.get("access_token");
}

export async function getMe(): Promise<User | null> {
  try {
    const { data } = await authApi.me();
    return data;
  } catch {
    return null;
  }
}
