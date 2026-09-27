/** Decart realtime virtual try-on model. */
export const LIVE_MODEL = "lucy-vton-latest";

/** Demo catalog used by the Live Try-On page and the demo store. */
export type Garment = {
  id: string;
  name: string;
  price: number;
  image: string;
  /** Instruction sent to the realtime try-on model along with the image. */
  prompt: string;
};

export const CATALOG: Garment[] = [
  {
    id: "black-turtleneck",
    name: "Merino Turtleneck — Black",
    price: 89,
    image: "/garments/black-turtleneck.svg",
    prompt: "Substitute the current top with a sleek fitted black merino turtleneck sweater",
  },
  {
    id: "navy-blazer",
    name: "Tailored Blazer — Navy",
    price: 249,
    image: "/garments/navy-blazer.svg",
    prompt: "Substitute the current top with a tailored navy wool blazer with gold buttons, worn open",
  },
  {
    id: "white-oxford",
    name: "Oxford Shirt — White",
    price: 69,
    image: "/garments/white-oxford.svg",
    prompt: "Substitute the current top with a crisp white button-down oxford shirt",
  },
  {
    id: "red-hoodie",
    name: "Oversized Hoodie — Red",
    price: 95,
    image: "/garments/red-hoodie.svg",
    prompt: "Substitute the current top with an oversized red cotton hoodie with a kangaroo pocket",
  },
  {
    id: "denim-jacket",
    name: "Trucker Jacket — Denim",
    price: 129,
    image: "/garments/denim-jacket.svg",
    prompt: "Substitute the current top with a mid-blue denim trucker jacket with contrast stitching",
  },
  {
    id: "gold-sherwani",
    name: "Embroidered Sherwani — Ivory",
    price: 420,
    image: "/garments/gold-sherwani.svg",
    prompt: "Substitute the current outfit with an ivory sherwani with gold embroidery and gold buttons",
  },
];

/** Plain garment description, e.g. "a tailored navy wool blazer ...". */
export const describe = (g: Garment) =>
  g.prompt.replace(/^Substitute the current (top|outfit) with /i, "");

export const garmentById =(id: string | null | undefined) => CATALOG.find((g) => g.id === id);
