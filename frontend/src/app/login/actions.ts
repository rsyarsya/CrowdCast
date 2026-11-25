"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { requestLogin } from "@/lib/auth";
import { TOKEN_COOKIE } from "@/lib/config";

export interface LoginState {
  error: string | null;
}

const ERROR_MESSAGES = {
  invalid_credentials: "Email atau password salah.",
  network_error: "Tidak dapat terhubung ke server CrowdCast. Coba lagi nanti.",
  unexpected_response: "Terjadi kesalahan saat masuk. Coba lagi nanti.",
} as const;

/** Only same-site paths, so the login form cannot redirect to another site. */
function safeNextPath(value: FormDataEntryValue | null): string {
  const path = typeof value === "string" ? value : "";
  return path.startsWith("/") && !path.startsWith("//") ? path : "/dashboard";
}

export async function loginAction(
  _previous: LoginState,
  formData: FormData,
): Promise<LoginState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  if (!email || !password) {
    return { error: "Email dan password wajib diisi." };
  }

  const result = await requestLogin(email, password);
  if (!result.ok) return { error: ERROR_MESSAGES[result.error] };

  (await cookies()).set(TOKEN_COOKIE, result.token.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: result.token.expires_in,
  });
  redirect(safeNextPath(formData.get("next")));
}

export async function logoutAction(): Promise<void> {
  (await cookies()).delete(TOKEN_COOKIE);
  redirect("/login");
}
