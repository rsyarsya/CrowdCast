import { NextResponse, type NextRequest } from "next/server";

import { isMockSource, TOKEN_COOKIE } from "@/lib/config";

/**
 * Sends visitors without a session cookie to /login before protected pages
 * render. An expired or revoked token is still caught by the page itself,
 * because only the backend can validate it.
 */
export function proxy(request: NextRequest) {
  if (isMockSource() || request.cookies.has(TOKEN_COOKIE)) {
    return NextResponse.next();
  }
  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
