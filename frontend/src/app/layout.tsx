import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { Cormorant_Garamond, Manrope } from "next/font/google";
import { SessionProvider } from "@/lib/session";
import "./globals.css";

// Two families: an editorial serif for titles, a clean sans for everything you read or press.
const serif = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  style: ["normal", "italic"],
  variable: "--font-cormorant",
  display: "swap",
});

const sans = Manrope({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-manrope",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "LOOKBOOK", template: "%s · LOOKBOOK" },
  description:
    "Describe any outfit in plain English and see yourself wearing it, from a photo or live on camera.",
};

export const viewport: Viewport = {
  themeColor: "#F3F0E9",
  colorScheme: "light",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await headers();
  return (
    <html
      lang="en"
      className={`${serif.variable} ${sans.variable} antialiased`}
    >
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
