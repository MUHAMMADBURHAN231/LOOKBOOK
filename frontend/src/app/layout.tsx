import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { Montserrat, IBM_Plex_Mono } from "next/font/google";
import { SessionProvider } from "@/lib/session";
import "./globals.css";

const montserrat = Montserrat({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  variable: "--font-montserrat",
  display: "swap",
});

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

export const viewport: Viewport = { themeColor: "#F8F8F6", colorScheme: "light" };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  await headers();
  return (
    <html lang="en" className={`${montserrat.variable} ${plexMono.variable} antialiased`}>
      <body className="min-h-dvh">
        <a
          href="#main"
          className="label sr-only z-[100] bg-accent px-4 py-3 text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
        >
          Skip to content
        </a>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
