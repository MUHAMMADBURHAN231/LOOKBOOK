import { createDecartClient } from "@decartai/sdk";
import { LIVE_MODEL } from "@/lib/catalog";

/**
 * Mints a short-lived Decart client token so the browser can open a realtime try-on session
 * without ever seeing DECART_API_KEY. Without a key, reports mock mode.
 */
export async function GET() {
  const apiKey = process.env.DECART_API_KEY;
  if (!apiKey) return Response.json({ mock: true });

  try {
    const client = createDecartClient({ apiKey });
    const token = await client.tokens.create({
      expiresIn: 600,
      allowedModels: [LIVE_MODEL],
      constraints: { realtime: { maxSessionDuration: 300 } },
    });
    return Response.json({ mock: false, apiKey: token.apiKey, expiresAt: token.expiresAt });
  } catch (err) {
    const message =
      (err as { message?: string } | null)?.message || String(err) || "Unknown error";
    return Response.json({ error: `Could not start a live session: ${message}` }, { status: 502 });
  }
}
