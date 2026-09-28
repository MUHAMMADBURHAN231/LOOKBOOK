"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

/* Scroll-driven dressing scene for the landing page.

   A smooth, faceless mannequin stands in the frame. As the page scrolls, each garment enters from
   the right laid flat, the way a garment lies in a flat-lay photo, then puts itself on: the sleeves
   swing down onto the arms and the garment takes on depth from the shoulders down until it sits on
   the body. Every frame is a pure function of scroll progress, so scrolling back undresses her.

   Body and garments are built the same way: a stack of elliptical rings (width, depth and centre
   per height) sampled from a few hand-set keys with Catmull-Rom interpolation. A garment is the
   body's shape grown outward, so layers nest without touching. "Flat" is the same ring stack with
   its depth pressed to a few millimetres, which keeps the silhouette readable in flight. */

export type Garment = { name: string; color: string };

export const GARMENTS: Garment[] = [
  { name: "Silk blouse", color: "#B7C4D1" },
  { name: "Wide-leg trousers", color: "#6B665F" },
  { name: "Tailored blazer", color: "#1C1C1E" },
  { name: "Wool overcoat", color: "#A8875E" },
];

type Props = {
  /** 0..1 across the dressing sequence; read every frame through a ref. */
  progress: React.RefObject<number>;
  /** Index of the garment being put on, or -1 before the first one arrives. */
  onGarment?: (index: number) => void;
  className?: string;
};

/* ------------------------------------------------------------------------------------------ */
/* Shape tables (units: the figure is about 3.4 tall, floor at y = -1.745)                     */

type Key = { y: number; w: number; d: number; cx?: number; cz?: number };
type Ring = { w: number; d: number; cx: number; cz: number };

const TORSO: Key[] = [
  { y: 1.25, w: 0.05, d: 0.05, cz: 0 },
  { y: 1.21, w: 0.11, d: 0.07, cz: -0.005 },
  { y: 1.16, w: 0.175, d: 0.085, cz: -0.01 },
  { y: 1.11, w: 0.205, d: 0.095, cz: -0.01 },
  { y: 1.04, w: 0.2, d: 0.1, cz: -0.005 },
  { y: 0.97, w: 0.18, d: 0.112, cz: 0.005 },
  { y: 0.9, w: 0.168, d: 0.122, cz: 0.015 },
  { y: 0.83, w: 0.152, d: 0.11, cz: 0.01 },
  { y: 0.76, w: 0.135, d: 0.094, cz: 0 },
  { y: 0.68, w: 0.12, d: 0.084, cz: -0.005 },
  { y: 0.6, w: 0.128, d: 0.088, cz: -0.008 },
  { y: 0.52, w: 0.15, d: 0.098, cz: -0.01 },
  { y: 0.44, w: 0.172, d: 0.108, cz: -0.012 },
  { y: 0.36, w: 0.176, d: 0.108, cz: -0.012 },
  { y: 0.28, w: 0.165, d: 0.1, cz: -0.008 },
  { y: 0.22, w: 0.14, d: 0.085, cz: -0.004 },
  { y: 0.17, w: 0.09, d: 0.06, cz: 0 },
  { y: 0.14, w: 0.02, d: 0.015, cz: 0 },
];

const NECK: Key[] = [
  { y: 1.45, w: 0.04, d: 0.044, cz: 0.01 },
  { y: 1.37, w: 0.044, d: 0.046, cz: 0.006 },
  { y: 1.3, w: 0.046, d: 0.048, cz: 0.004 },
  { y: 1.16, w: 0.054, d: 0.054, cz: 0 },
];

const HEAD: Key[] = [
  { y: 1.685, w: 0.012, d: 0.016, cz: -0.012 },
  { y: 1.66, w: 0.055, d: 0.068, cz: -0.012 },
  { y: 1.62, w: 0.085, d: 0.1, cz: -0.01 },
  { y: 1.58, w: 0.098, d: 0.114, cz: -0.005 },
  { y: 1.52, w: 0.1, d: 0.115, cz: 0.005 },
  { y: 1.46, w: 0.092, d: 0.105, cz: 0.015 },
  { y: 1.41, w: 0.075, d: 0.085, cz: 0.025 },
  { y: 1.38, w: 0.04, d: 0.05, cz: 0.02 },
  { y: 1.37, w: 0.01, d: 0.012, cz: 0.02 },
];

/** Right leg; the left one mirrors cx. The top is capped inside the hips so the thigh grows out
 *  of the torso instead of showing a rim. */
const LEG: Key[] = [
  { y: 0.44, cx: 0.07, w: 0.02, d: 0.02 },
  { y: 0.4, cx: 0.08, w: 0.07, d: 0.075 },
  { y: 0.3, cx: 0.087, w: 0.09, d: 0.098 },
  { y: 0.15, cx: 0.09, w: 0.094, d: 0.1 },
  { y: 0.0, cx: 0.087, w: 0.09, d: 0.095 },
  { y: -0.25, cx: 0.08, w: 0.078, d: 0.082 },
  { y: -0.5, cx: 0.074, w: 0.063, d: 0.067 },
  { y: -0.66, cx: 0.071, w: 0.057, d: 0.061 },
  { y: -0.8, cx: 0.069, w: 0.059, d: 0.065, cz: -0.004 },
  { y: -0.98, cx: 0.067, w: 0.057, d: 0.065, cz: -0.01 },
  { y: -1.22, cx: 0.065, w: 0.043, d: 0.047, cz: -0.005 },
  { y: -1.46, cx: 0.063, w: 0.03, d: 0.033 },
  { y: -1.6, cx: 0.062, w: 0.027, d: 0.03 },
  { y: -1.66, cx: 0.062, w: 0.028, d: 0.032 },
  { y: -1.69, cx: 0.062, w: 0.012, d: 0.014 },
];

/** Arm hanging straight down from the shoulder joint (local frame); the hand is flat side-on. */
const ARM: Key[] = [
  { y: 0.075, w: 0.012, d: 0.012 },
  { y: 0.055, w: 0.036, d: 0.038 },
  { y: 0.02, w: 0.05, d: 0.052 },
  { y: -0.05, w: 0.052, d: 0.054 },
  { y: -0.18, w: 0.046, d: 0.048 },
  { y: -0.34, w: 0.038, d: 0.04 },
  { y: -0.42, w: 0.034, d: 0.036 },
  { y: -0.5, w: 0.036, d: 0.038 },
  { y: -0.62, w: 0.031, d: 0.032 },
  { y: -0.74, w: 0.023, d: 0.022 },
  { y: -0.79, w: 0.02, d: 0.03 },
  { y: -0.87, w: 0.017, d: 0.037 },
  { y: -0.93, w: 0.014, d: 0.03 },
  { y: -0.97, w: 0.005, d: 0.01 },
];

const TROUSER_LEG: Key[] = [
  { y: 0.47, cx: 0.08, w: 0.05, d: 0.06 },
  { y: 0.38, cx: 0.088, w: 0.098, d: 0.105 },
  { y: 0.3, cx: 0.09, w: 0.108, d: 0.114 },
  { y: 0.05, cx: 0.093, w: 0.108, d: 0.112 },
  { y: -0.4, cx: 0.096, w: 0.104, d: 0.108 },
  { y: -0.9, cx: 0.099, w: 0.11, d: 0.114 },
  { y: -1.35, cx: 0.101, w: 0.118, d: 0.12 },
  { y: -1.7, cx: 0.103, w: 0.126, d: 0.126 },
];

const COAT_LOWER: Key[] = [
  { y: 0.42, w: 0.229, d: 0.163, cz: -0.012 },
  { y: 0.1, w: 0.246, d: 0.16, cz: -0.01 },
  { y: -0.4, w: 0.258, d: 0.163, cz: -0.008 },
  { y: -0.98, w: 0.274, d: 0.168, cz: -0.006 },
];

const FLOOR_Y = -1.745;
const SHOULDER = { x: 0.192, y: 1.085, z: -0.008 };
const HIP = { x: 0.09, y: 0.34 };
const ARM_ANGLE = THREE.MathUtils.degToRad(11);
const ARM_FORWARD = 0.05;
const SLEEVE_SPREAD = THREE.MathUtils.degToRad(64);
const LEG_SPREAD = THREE.MathUtils.degToRad(7);
const FLAT_DEPTH = 0.012;

function sampler(keys: Key[]) {
  const n = keys.length;
  const ring = (k: Key): Ring => ({ w: k.w, d: k.d, cx: k.cx ?? 0, cz: k.cz ?? 0 });
  return (y: number): Ring => {
    if (y >= keys[0].y) return ring(keys[0]);
    if (y <= keys[n - 1].y) return ring(keys[n - 1]);
    let i = 0;
    while (i < n - 2 && y < keys[i + 1].y) i++;
    const k0 = keys[Math.max(0, i - 1)];
    const k1 = keys[i];
    const k2 = keys[i + 1];
    const k3 = keys[Math.min(n - 1, i + 2)];
    const t = (k1.y - y) / (k1.y - k2.y);
    const cr = (a: number, b: number, c: number, d: number) =>
      0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t * t * t);
    return {
      w: Math.max(0.002, cr(k0.w, k1.w, k2.w, k3.w)),
      d: Math.max(0.002, cr(k0.d, k1.d, k2.d, k3.d)),
      cx: cr(k0.cx ?? 0, k1.cx ?? 0, k2.cx ?? 0, k3.cx ?? 0),
      cz: cr(k0.cz ?? 0, k1.cz ?? 0, k2.cz ?? 0, k3.cz ?? 0),
    };
  };
}

const torso = sampler(TORSO);
const arm = sampler(ARM);
const leg = sampler(LEG);
const trouserLeg = sampler(TROUSER_LEG);
const coatLower = sampler(COAT_LOWER);

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const smooth = (v: number) => {
  const t = clamp01(v);
  return t * t * (3 - 2 * t);
};
const easeInOut = (v: number) => {
  const t = clamp01(v);
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
};
const grow = (r: Ring, by: number, byDepth = by): Ring => ({ ...r, w: r.w + by, d: r.d + byDepth });

/* ------------------------------------------------------------------------------------------ */
/* Ring-stack geometry                                                                         */

type Frame = "body" | "arm" | "leg";
type Spec = {
  frame: Frame;
  side?: 1 | -1;
  y0: number;
  y1: number;
  shape: (y: number) => Ring;
  /** Half-angle (radians) of an opening at the front, for jackets and coats. */
  gap?: (y: number) => number;
  seg?: number;
  rowStep?: number;
};

type Piece = {
  spec: Spec;
  rows: number;
  cols: number;
  ys: Float32Array;
  rings: Ring[];
  /** Per vertex: sin and cos of the angle around the ring (0 = front centre). */
  sin: Float32Array;
  cos: Float32Array;
  geo: THREE.BufferGeometry;
  pos: Float32Array;
};

function buildPiece(spec: Spec): Piece {
  const seg = spec.seg ?? 72;
  const rows = Math.max(8, Math.round((spec.y0 - spec.y1) / (spec.rowStep ?? 0.016)));
  const cols = seg + 1;
  const ys = new Float32Array(rows + 1);
  const rings: Ring[] = [];
  const mirror = spec.frame === "leg" && spec.side === -1 ? -1 : 1;
  for (let r = 0; r <= rows; r++) {
    const y = spec.y0 + ((spec.y1 - spec.y0) * r) / rows;
    const ring = spec.shape(y);
    ys[r] = y;
    rings.push({ ...ring, cx: ring.cx * mirror });
  }
  // Closed rings run from the back round to the back (seam hidden behind). Rings with a front
  // opening run from one edge of the opening round the back to the other, so the edge is smooth.
  const sin = new Float32Array((rows + 1) * cols);
  const cos = new Float32Array((rows + 1) * cols);
  for (let r = 0; r <= rows; r++) {
    const open = spec.gap ? Math.max(0, spec.gap(ys[r])) : 0;
    for (let c = 0; c < cols; c++) {
      const phi = spec.gap ? open + ((2 * Math.PI - 2 * open) * c) / seg : -Math.PI + (2 * Math.PI * c) / seg;
      sin[r * cols + c] = Math.sin(phi);
      cos[r * cols + c] = Math.cos(phi);
    }
  }

  const index: number[] = [];
  const uv = new Float32Array((rows + 1) * cols * 2);
  for (let r = 0; r <= rows; r++) {
    for (let c = 0; c < cols; c++) {
      uv[(r * cols + c) * 2] = c / seg;
      uv[(r * cols + c) * 2 + 1] = r / rows;
    }
  }
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < seg; c++) {
      const a = r * cols + c;
      const b = a + 1;
      const cc = a + cols;
      const d = cc + 1;
      index.push(a, cc, b, b, cc, d);
    }
  }

  const pos = new Float32Array((rows + 1) * cols * 3);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  geo.setIndex(index);
  return { spec, rows, cols, ys, rings, sin, cos, geo, pos };
}

const armMatrix = (side: 1 | -1, angle: number, out: THREE.Matrix4) => {
  const rz = new THREE.Matrix4().makeRotationZ(side * angle);
  const rx = new THREE.Matrix4().makeRotationX(-ARM_FORWARD);
  return out.makeTranslation(side * SHOULDER.x, SHOULDER.y, SHOULDER.z).multiply(rz).multiply(rx);
};

const legMatrix = (side: 1 | -1, angle: number, out: THREE.Matrix4) => {
  const p = new THREE.Vector3(side * HIP.x, HIP.y, 0);
  return out
    .makeTranslation(p.x, p.y, p.z)
    .multiply(new THREE.Matrix4().makeRotationZ(side * angle))
    .multiply(new THREE.Matrix4().makeTranslation(-p.x, -p.y, -p.z));
};

/** Writes the piece's vertices. depth(rowFraction) is 0 for pressed flat and 1 for worn. */
function layout(p: Piece, depth: (rowFrac: number) => number, m: THREE.Matrix4 | null, ripple: number, time: number) {
  const { rows, cols, ys, rings, sin, cos, pos } = p;
  const e = m?.elements;
  for (let r = 0; r <= rows; r++) {
    const R = rings[r];
    const k = depth(r / rows);
    const ds = FLAT_DEPTH + (R.d - FLAT_DEPTH) * k;
    const zFront = R.cz + R.d;
    const y = ys[r];
    for (let c = 0; c < cols; c++) {
      const v = r * cols + c;
      let x = R.cx + R.w * sin[v];
      let yy = y;
      let z = zFront - ds + ds * cos[v];
      if (e) {
        const nx = e[0] * x + e[4] * yy + e[8] * z + e[12];
        const ny = e[1] * x + e[5] * yy + e[9] * z + e[13];
        const nz = e[2] * x + e[6] * yy + e[10] * z + e[14];
        x = nx;
        yy = ny;
        z = nz;
      }
      if (ripple > 0) z += ripple * Math.sin(x * 5.2 + yy * 3.1 + time * 2.2) * (0.65 + 0.35 * Math.sin(yy * 7 + time));
      const i = (r * cols + c) * 3;
      pos[i] = x;
      pos[i + 1] = yy;
      pos[i + 2] = z;
    }
  }
  p.geo.attributes.position.needsUpdate = true;
  p.geo.computeVertexNormals();
  p.geo.computeBoundingSphere();
}

/* ------------------------------------------------------------------------------------------ */
/* Garment definitions                                                                         */

const sides = [1, -1] as const;
const sleeves = (y0: number, y1: number, shape: (y: number) => Ring): Spec[] =>
  sides.map((side) => ({ frame: "arm" as const, side, y0, y1, shape, seg: 48, rowStep: 0.018 }));
const trouserLegs: Spec[] = sides.map((side) => ({
  frame: "leg" as const,
  side,
  y0: 0.47,
  y1: -1.7,
  shape: trouserLeg,
  seg: 56,
  rowStep: 0.02,
}));

const GARMENT_SPECS: Spec[][] = [
  // Silk blouse: round collar, slight flare at the hem, long sleeves with a fuller cuff.
  [
    {
      frame: "body",
      y0: 1.235,
      y1: 0.4,
      shape: (y) => {
        const r = grow(torso(y), 0.011 + (y < 0.55 ? (0.55 - y) * 0.035 : 0));
        return y > 1.18 ? { ...r, w: Math.max(r.w, 0.084), d: Math.max(r.d, 0.078) } : r;
      },
    },
    ...sleeves(0.075, -0.73, (y) => grow(arm(y), 0.011 + (y < -0.6 ? (-0.6 - y) * 0.05 : 0))),
  ],
  // Wide-leg trousers: high waist, legs flaring from the knee.
  [
    {
      frame: "body",
      y0: 0.74,
      y1: 0.15,
      // Fuller through the hip so the tops of the legs stay inside the seat.
      shape: (y) => grow(torso(y), 0.022 + 0.016 * smooth((0.52 - y) / 0.14)),
    },
    ...trouserLegs,
  ],
  // Tailored blazer: padded shoulders, deep V, hip length.
  [
    {
      frame: "body",
      y0: 1.225,
      y1: 0.25,
      shape: (y) => {
        const r = torso(y);
        const pad = 0.014 * Math.exp(-Math.pow((y - 1.13) / 0.05, 2));
        // Extra room through the hip so the trousers' seat stays underneath.
        const seat = 0.02 * smooth((0.52 - y) / 0.14);
        let w = Math.max(r.w + 0.03 + pad + seat, 0.158);
        if (y < 0.42) w = Math.max(w, 0.215);
        return { ...r, w, d: Math.max(r.d + 0.03 + seat, 0.118) };
      },
      gap: (y) => (y > 0.72 ? 0.1 + 0.55 * smooth((y - 0.72) / 0.5) : 0.1 * smooth((y - 0.62) / 0.1)),
    },
    ...sleeves(0.08, -0.7, (y) => grow(arm(y), 0.028)),
  ],
  // Wool overcoat: below the knee, opens toward the hem.
  [
    {
      frame: "body",
      y0: 1.235,
      y1: -0.98,
      shape: (y) => {
        if (y < 0.42) return coatLower(y);
        const r = torso(y);
        const pad = 0.012 * Math.exp(-Math.pow((y - 1.13) / 0.05, 2));
        return { ...r, w: Math.max(r.w + 0.056 + pad, 0.19), d: Math.max(r.d + 0.055, 0.15) };
      },
      gap: (y) =>
        y > 0.7 ? 0.14 + 0.5 * smooth((y - 0.7) / 0.53) : y > 0.3 ? 0.06 : 0.06 + 0.22 * smooth((0.3 - y) / 1.28),
      rowStep: 0.02,
    },
    ...sleeves(0.085, -0.705, (y) => grow(arm(y), 0.054)),
  ],
];

const MATERIALS: Partial<THREE.MeshPhysicalMaterialParameters>[] = [
  { roughness: 0.42, sheen: 0.9, sheenRoughness: 0.35, sheenColor: new THREE.Color("#E8EEF4") },
  { roughness: 0.82 },
  { roughness: 0.86 },
  { roughness: 0.9 },
];

/* ------------------------------------------------------------------------------------------ */

type GarmentRuntime = {
  group: THREE.Group;
  pieces: Piece[];
  key: string;
};

export default function WomanScene({ progress, onGarment, className = "" }: Props) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    } catch {
      el.dataset.webgl = "off";
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    const canvas = renderer.domElement;
    canvas.setAttribute("role", "img");
    canvas.setAttribute(
      "aria-label",
      "A mannequin being dressed as you scroll: a silk blouse, wide-leg trousers, a tailored blazer and a wool overcoat.",
    );
    el.appendChild(canvas);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 60);

    scene.add(new THREE.HemisphereLight("#ffffff", "#e9e4dd", 1.25));
    const key = new THREE.DirectionalLight("#fff8f0", 1.9);
    key.position.set(-2.2, 4.2, 4.5);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.left = -2.5;
    key.shadow.camera.right = 2.5;
    key.shadow.camera.top = 2.5;
    key.shadow.camera.bottom = -2.5;
    key.shadow.camera.near = 1;
    key.shadow.camera.far = 14;
    key.shadow.bias = -0.0008;
    key.shadow.normalBias = 0.03;
    key.shadow.radius = 4;
    scene.add(key);
    const rim = new THREE.DirectionalLight("#ffffff", 0.9);
    rim.position.set(3, 2.5, -3.5);
    scene.add(rim);
    const fill = new THREE.DirectionalLight("#f3f1ee", 0.45);
    fill.position.set(3.5, 0.5, 3);
    scene.add(fill);

    const ground = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), new THREE.ShadowMaterial({ opacity: 0.07 }));
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = FLOOR_Y;
    ground.receiveShadow = true;
    scene.add(ground);

    const figure = new THREE.Group();
    scene.add(figure);

    const disposables: { dispose: () => void }[] = [];
    const skin = new THREE.MeshPhysicalMaterial({
      color: "#E7E3DD",
      roughness: 0.48,
      clearcoat: 0.3,
      clearcoatRoughness: 0.4,
    });
    disposables.push(skin);

    const bodySpecs: Spec[] = [
      { frame: "body", y0: 1.25, y1: 0.14, shape: torso, rowStep: 0.012 },
      { frame: "body", y0: 1.45, y1: 1.16, shape: sampler(NECK), seg: 40 },
      { frame: "body", y0: 1.685, y1: 1.37, shape: sampler(HEAD), rowStep: 0.008 },
      ...sides.map((side) => ({ frame: "leg" as const, side, y0: 0.44, y1: -1.69, shape: leg, seg: 48 })),
      ...sides.map((side) => ({ frame: "arm" as const, side, y0: 0.075, y1: -0.97, shape: arm, seg: 40, rowStep: 0.012 })),
    ];
    const m = new THREE.Matrix4();
    for (const spec of bodySpecs) {
      const piece = buildPiece(spec);
      layout(piece, () => 1, spec.frame === "arm" ? armMatrix(spec.side!, ARM_ANGLE, m) : null, 0, 0);
      const mesh = new THREE.Mesh(piece.geo, skin);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      figure.add(mesh);
      disposables.push(piece.geo);
    }
    const footGeo = new THREE.SphereGeometry(1, 32, 20);
    disposables.push(footGeo);
    for (const side of sides) {
      const foot = new THREE.Mesh(footGeo, skin);
      foot.scale.set(0.034, 0.026, 0.088);
      foot.position.set(side * 0.064, FLOOR_Y + 0.028, 0.045);
      foot.rotation.y = side * 0.14;
      foot.castShadow = true;
      figure.add(foot);
    }

    const garments: GarmentRuntime[] = GARMENTS.map((g, i) => {
      // Back faces cast the shadows, so a garment never shadows its own outer surface (no acne).
      const mat = new THREE.MeshPhysicalMaterial({
        color: g.color,
        side: THREE.DoubleSide,
        shadowSide: THREE.BackSide,
        ...MATERIALS[i],
      });
      disposables.push(mat);
      const group = new THREE.Group();
      group.visible = false;
      const pieces = GARMENT_SPECS[i].map((spec) => {
        const piece = buildPiece(spec);
        const mesh = new THREE.Mesh(piece.geo, mat);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.frustumCulled = false;
        group.add(mesh);
        disposables.push(piece.geo);
        return piece;
      });
      figure.add(group);
      return { group, pieces, key: "" };
    });

    /* Layout: figure right of centre on wide screens, lower and centred on tall ones. */
    let enterX = 4;
    const resize = () => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      const aspect = w / h;
      camera.aspect = aspect;
      const halfTan = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      let dist: number;
      let targetY: number;
      if (aspect >= 1) {
        dist = 8.3;
        targetY = -0.04;
        const halfW = dist * halfTan * aspect;
        figure.position.x = Math.min(halfW * 0.4, 1.9);
        enterX = halfW - figure.position.x + 1.1;
      } else {
        // Figure fills the lower ~55% of the screen, leaving the top for text.
        const visibleH = 3.45 / 0.55;
        dist = visibleH / (2 * halfTan);
        targetY = -0.03 + 0.215 * visibleH;
        figure.position.x = 0;
        enterX = dist * halfTan * aspect + 1.0;
      }
      camera.position.set(0, targetY + 0.05, dist);
      camera.lookAt(0, targetY, 0);
      camera.updateProjectionMatrix();
      garments.forEach((g) => (g.key = ""));
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    let visible = true;
    const io = new IntersectionObserver(([entry]) => (visible = entry.isIntersecting));
    io.observe(el);

    const N = garments.length;
    let label = -2;
    let raf = 0;
    const matrix = new THREE.Matrix4();

    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      if (!visible || document.hidden) return;
      const time = now / 1000;
      const P = clamp01(progress.current ?? 0);
      figure.rotation.y = reduced ? 0 : Math.sin(time * 0.32) * 0.14;

      let current = -1;
      garments.forEach((g, i) => {
        const s = clamp01(P * N - i);
        if (s <= 0.001) {
          g.group.visible = false;
          return;
        }
        g.group.visible = true;
        if (s > 0.25) current = i;

        const travel = easeInOut(s / 0.45);
        const wrap = easeInOut((s - 0.38) / 0.47);
        const inFlight = travel < 1 || wrap < 1;
        const ripple = reduced ? 0 : 0.045 * (1 - travel) + 0.012 * Math.sin(Math.PI * wrap);

        g.group.position.set(enterX * (1 - travel), 0.35 * (1 - travel), 0);
        g.group.rotation.set(0, -0.5 * (1 - travel), -0.08 * (1 - travel));
        // Laid flat, a garment reads slightly wider; it narrows as it fits. Width only, so the rings
        // stay at the height of the body they cover.
        g.group.scale.set(1 + 0.06 * (1 - wrap), 1, 1);

        const stateKey = `${travel.toFixed(4)}|${wrap.toFixed(4)}`;
        if (!inFlight && g.key === stateKey) return;
        g.key = stateKey;

        const stagger = 0.4;
        const depth = (rowFrac: number) => smooth((wrap - stagger * rowFrac) / (1 - stagger));
        const limbs = easeInOut(wrap / 0.7);
        for (const piece of g.pieces) {
          const { frame, side } = piece.spec;
          const mm =
            frame === "arm"
              ? armMatrix(side!, ARM_ANGLE + SLEEVE_SPREAD * (1 - limbs), matrix)
              : frame === "leg"
                ? legMatrix(side!, LEG_SPREAD * (1 - limbs), matrix)
                : null;
          layout(piece, depth, mm, inFlight ? ripple : 0, time);
        }
      });

      if (current !== label) {
        label = current;
        onGarment?.(current);
      }
      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      disposables.forEach((d) => d.dispose());
      renderer.dispose();
      canvas.remove();
    };
  }, [progress, onGarment]);

  return <div ref={host} className={className} />;
}
