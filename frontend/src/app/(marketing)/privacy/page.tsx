export const metadata = { title: "Privacy" };

const SECTIONS: [string, string[]][] = [
  [
    "What we collect",
    [
      "Your email address, name (optional) and a password hash. We never store your password itself.",
      "Photos you upload for try-on, and the images we generate from them.",
      "Messages you send the stylist and the looks you save.",
      "The network prefix of the address you sign in from (not the full address), so you can recognise your devices.",
    ],
  ],
  [
    "How photos are handled",
    [
      "We ask for explicit consent before your first upload, and record when you gave it.",
      "Photos are encrypted at rest and only used to generate the try-ons you request.",
      "LOOKBOOK never uses your photos to train models.",
      "Uploaded portraits are deleted automatically after 14 days, and generated images after 90 days. Temporary files made during processing are deleted within a day.",
      "Metadata such as GPS location is stripped from every upload.",
      "Photos that appear to show a person under 18 are refused.",
    ],
  ],
  [
    "Live camera try-on",
    ["The camera stream is processed in real time to render the garment on you. It is not recorded or stored by LOOKBOOK."],
  ],
  [
    "Processors",
    [
      "Images are processed by the AI providers that run try-on generation (for example Google Gemini, Replicate or Decart). LOOKBOOK only uses provider plans whose terms exclude training on your images.",
      "Bot protection is provided by Cloudflare Turnstile.",
    ],
  ],
  [
    "Your controls",
    [
      "Download a copy of your data at any time from Account.",
      "Delete individual photos, all your data, or your whole account from Account.",
      "Withdrawing consent deletes every photo and generated image immediately.",
      "Sign out individual devices, or every device at once.",
    ],
  ],
];

export default function PrivacyPage() {
  return (
    <article className="mx-auto max-w-3xl px-5 pt-32 pb-24 md:px-8">
      <p className="label text-mist">Privacy</p>
      <h1 className="display-md mt-5 text-[clamp(2.2rem,5vw,3.6rem)]">Your photo stays yours.</h1>
      <p className="mt-6 text-lg leading-relaxed text-mist">
        This page explains what LOOKBOOK stores, why, and for how long, in plain language.
      </p>
      {SECTIONS.map(([title, items]) => (
        <section key={title} className="mt-14 border-t border-line pt-8">
          <h2 className="text-xl font-semibold text-frost">{title}</h2>
          <ul className="mt-5 space-y-3 leading-relaxed text-mist">
            {items.map((item) => (
              <li key={item} className="flex gap-3">
                <span className="mt-2.5 size-1 shrink-0 bg-signal" aria-hidden />
                {item}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </article>
  );
}
