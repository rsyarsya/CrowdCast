import { cookies } from "next/headers";

import { TOKEN_COOKIE } from "@/lib/config";

/**
 * The access token of the current request, read from the httpOnly cookie.
 * Returns undefined outside a request (for example during a static build).
 */
export async function getAccessToken(): Promise<string | undefined> {
  try {
    return (await cookies()).get(TOKEN_COOKIE)?.value || undefined;
  } catch {
    return undefined;
  }
}
