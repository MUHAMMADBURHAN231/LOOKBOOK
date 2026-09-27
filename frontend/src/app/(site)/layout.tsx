import Nav from "@/components/Nav";

export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Nav />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
      <footer className="py-6 text-center text-xs text-zinc-400">
        LOOKBOOK · Photos are stored only to generate your looks and auto-deleted after 30 days.
      </footer>
    </>
  );
}
