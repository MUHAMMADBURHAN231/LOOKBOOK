import Link from "next/link";

export function Wordmark({ href = "/", className = "" }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={`display-md text-lg tracking-tight text-frost ${className}`} aria-label="LOOKBOOK home">
      LOOK<span className="text-signal">/</span>BOOK
    </Link>
  );
}
