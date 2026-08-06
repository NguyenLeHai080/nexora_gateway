import { NextResponse } from "next/server";
import { jwtVerify } from "jose";
import { createDashboardAuthToken, shouldUseSecureCookie } from "@/lib/auth/dashboardSession";

export const dynamic = "force-dynamic";

export async function GET(request) {
  try {
    const url = new URL(request.url);
    const token = url.searchParams.get("token");
    if (!token || !process.env.JWT_SECRET) {
      return NextResponse.json({ error: "Nexora SSO is not configured" }, { status: 503 });
    }
    const { payload } = await jwtVerify(token, new TextEncoder().encode(process.env.JWT_SECRET), {
      algorithms: ["HS256"],
      issuer: "nexora",
      audience: "9router-provider-wizard",
    });
    if (payload.purpose !== "provider:manage") {
      return NextResponse.json({ error: "Invalid SSO purpose" }, { status: 403 });
    }
    const embedded = url.searchParams.get("embed") === "1";
    const forwardedHost = request.headers.get("x-forwarded-host") || request.headers.get("host");
    const forwardedProto = request.headers.get("x-forwarded-proto") || "http";
    const publicOrigin = embedded && forwardedHost
      ? `${forwardedProto}://${forwardedHost}`
      : process.env.BASE_URL || process.env.NEXT_PUBLIC_BASE_URL || url.origin;
    const provider = String(payload.provider || "").trim();
    const routePath = provider ? `/dashboard/providers/${encodeURIComponent(provider)}` : "/dashboard/providers";
    const destination = new URL(`${embedded ? "/router-embed" : ""}${routePath}`, publicOrigin);
    destination.searchParams.set("source", "nexora");
    const response = NextResponse.redirect(destination);
    response.cookies.set("auth_token", await createDashboardAuthToken({ source: "nexora" }), {
      httpOnly: true,
      secure: shouldUseSecureCookie(request),
      sameSite: "lax",
      path: "/",
    });
    return response;
  } catch (error) {
    console.error("[Nexora SSO]", error?.code || error?.message || error);
    return NextResponse.json({ error: "SSO link is invalid or expired" }, { status: 401 });
  }
}
