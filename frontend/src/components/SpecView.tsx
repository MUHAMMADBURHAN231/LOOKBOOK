import type { OutfitSpec } from "@/lib/api";

const REGION: Record<string, string> = {
  upper_body: "Top",
  lower_body: "Bottom",
  dresses: "Full body",
};

/** Shows what the Outfit Interpreter understood from the description. */
export default function SpecView({ spec }: { spec: OutfitSpec }) {
  return (
    <div className="space-y-3 text-sm">
      <ul className="space-y-1.5">
        {spec.garments.map((g, i) => (
          <li key={i} className="flex items-baseline gap-2">
            <span className="w-16 shrink-0 text-xs uppercase tracking-wide text-zinc-400">
              {REGION[g.category]}
            </span>
            <span className="text-zinc-800">
              {[g.fit, g.color, g.material, g.type].filter(Boolean).join(" ")}
              {g.details && <span className="text-zinc-500"> · {g.details}</span>}
            </span>
          </li>
        ))}
        {spec.footwear && <Row label="Shoes" value={spec.footwear} />}
        {spec.accessories.length > 0 && <Row label="Extras" value={spec.accessories.join(", ")} />}
        {spec.scene && <Row label="Scene" value={spec.scene} />}
      </ul>
      {spec.style_tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {spec.style_tags.map((t) => (
            <span key={t} className="chip">
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <li className="flex items-baseline gap-2">
      <span className="w-16 shrink-0 text-xs uppercase tracking-wide text-zinc-400">{label}</span>
      <span className="text-zinc-800">{value}</span>
    </li>
  );
}
