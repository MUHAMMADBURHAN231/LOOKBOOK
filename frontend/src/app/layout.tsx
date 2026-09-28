import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { Archivo, IBM_Plex_Mono } from "next/font/google";
import { SessionProvider } from "@/lib/session";
import "./globals.css";

const archivo = Archivo({ subsets: ["latin"], axes: ["wdth"], variable: "--font-archivo", display: "swap" });
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "LOOKBOOK", template: "%s · LOOKBOOK" },
  description: "Describe any outfit in plain English and see yourself wearing it, from a photo or live on camera.",
};

export const viewport: Viewport = { themeColor: "#06080a", colorScheme: "dark" };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Reading request headers opts every page into dynamic rendering, which the per-request CSP
  // nonce set in src/proxy.ts requires (Next.js applies the nonce to its own scripts).
  await headers();
  return (
    <html lang="en" className={`${archivo.variable} ${plexMono.variable} antialiased`}>
      <body className="min-h-dvh">
        <a
          href="#main"
          className="label sr-only z-[100] bg-signal px-4 py-3 text-ink-950 focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
        >
          Skip to content
        </a>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
