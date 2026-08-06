import { NextResponse } from "next/server";
import REGISTRY from "open-sse/providers/registry/index.js";

export const dynamic = "force-dynamic";

// Public-safe metadata used by the Nexora control plane. Credentials and
// provider-specific configuration are deliberately excluded.
export async function GET() {
  const providers = REGISTRY
    .filter((provider) => !provider.hidden)
    .filter((provider) => provider.category === "apikey" || provider.oauth || provider.authModes?.includes("apikey"))
    .map((provider) => ({
      id: provider.id,
      name: provider.display?.name || provider.name || provider.uiAlias || provider.alias || provider.id,
      authModes: [
        ...(provider.category === "apikey" || provider.authModes?.includes("apikey") ? ["apikey"] : []),
        ...(provider.oauth ? ["oauth"] : []),
      ],
      authHint: provider.authHint || provider.display?.authHint || "API key",
    }))
    .sort((a, b) => a.name.localeCompare(b.name));

  return NextResponse.json({ providers });
}
