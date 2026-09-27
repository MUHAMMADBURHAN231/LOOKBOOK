/** A tiny set of 1.5px line glyphs drawn for LOOKBOOK (16px grid). Decorative unless labelled. */
const PATHS = {
  arrow: "M3 8h9M8.5 4.5 12 8l-3.5 3.5",
  "arrow-left": "M13 8H4M7.5 4.5 4 8l3.5 3.5",
  plus: "M8 3v10M3 8h10",
  close: "M4 4l8 8M12 4l-8 8",
  check: "M3.5 8.5l3 3 6-7",
  upload: "M8 11V3M4.5 6.5 8 3l3.5 3.5M3 13h10",
  camera: "M2.5 5.5h2.5l1.2-1.5h3.6L11 5.5h2.5v7h-11zM8 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
  send: "M3 8h10M9 4l4 4-4 4",
  trash: "M3.5 4.5h9M6 4.5V3h4v1.5M5 4.5l.5 8.5h5l.5-8.5",
  download: "M8 3v8M4.5 7.5 8 11l3.5-3.5M3 13h10",
} as const;

export type GlyphName = keyof typeof PATHS;

export function Glyph({ name, className = "size-4", label }: { name: GlyphName; className?: string; label?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="square"
      className={className}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
