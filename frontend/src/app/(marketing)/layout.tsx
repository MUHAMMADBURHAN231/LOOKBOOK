import { SiteFooter } from "@/components/marketing/SiteFooter";
import { SiteNav } from "@/components/marketing/SiteNav";
import { SmoothScroll } from "@/components/marketing/SmoothScroll";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <SmoothScroll>
      <SiteNav />
      <main id="main">{children}</main>
      <SiteFooter />
    </SmoothScroll>
  );
}
