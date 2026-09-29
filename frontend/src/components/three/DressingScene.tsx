"use client";

import gsap from "gsap";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

/* The landing story in real time: a 3D model of her, and three garments that dress her as you
   scroll. Each garment was cloth-simulated offline (scripts/scene3d): its sewing panels fly in from
   the right, fan out around her, close onto her and drape; the blouse and blazer later open and fly
   off to the left. Every frame here is a pure function of scroll position, so it scrubs both ways.

   A garment's frame is rebuilt from its panels' rigid transforms (stored every frame) plus the
   cloth's own motion on top (stored every other frame as int8), then normals are recomputed and
   averaged across seams. Only garments on screen are evaluated, and only when the playhead moves. */

type GarmentName = "blouse" | "blazer" | "coat";

type GarmentInfo = {
  url: string;
  vertices: number;
  frames: number;
  panels: number;
  stored: number[];
  index32: boolean;
  sections: Record<
    | "index"
    | "rest"
    | "panel"
    | "seams"
    | "centre"
    | "track"
    | "scale"
    | "resid",
    [number, number]
  >;
};

export type Scene3DManifest = {
  body: string;
  stride: number;
  timeline: { settled: number; leaveStart: number; leaveEnd: number };
  garments: Record<GarmentName, GarmentInfo>;
};

/** Where each look's spec card points, in model space (metres, Y up, facing +Z). */
export const ANCHORS: [number, number, number][] = [
  [0.215, 1.2, 0.03], // blouse: her left upper sleeve
  [0.1, 1.2, 0.1], // blazer: left lapel
  [0.19, 0.95, 0.11], // coat: left front, by the pocket
];

const ORDER: GarmentName[] = ["blouse", "blazer", "coat"];

const FABRIC: Record<GarmentName, THREE.MeshPhysicalMaterialParameters> = {
  blouse: {
    color: "#9FB3CF",
    roughness: 0.38,
    sheen: 1,
    sheenRoughness: 0.3,
    sheenColor: "#E4ECF7",
  },
  blazer: {
    color: "#18181B",
    roughness: 0.72,
    sheen: 0.7,
    sheenRoughness: 0.55,
    sheenColor: "#4A4A52",
  },
  coat: {
    color: "#A56A38",
    roughness: 0.88,
    sheen: 1,
    sheenRoughness: 0.75,
    sheenColor: "#E0AE7C",
  },
};

const HEIGHT = 1.68;
const FOV = 22;

type Props = {
  manifest: Scene3DManifest;
  /** Target position, 0..1 across the three looks (stations at 1/3, 2/3 and 1). */
  progress: React.RefObject<number>;
  /** Called with the position (0..1) drawn, when it changes. */
  onFrame?: (position: number) => void;
  /** Loading progress (0..1) toward the first look being ready, and whether it is. */
  onLoad?: (fraction: number, ready: boolean) => void;
  /** Screen positions (px, relative to the canvas) of ANCHORS, whenever the view changes. */
  onAnchors?: (points: { x: number; y: number; visible: boolean }[]) => void;
  /** WebGL isn't available; the caller should fall back. */
  onUnsupported?: () => void;
  className?: string;
  label: string;
  follow?: number;
};

async function fetchBinary(url: string): Promise<ArrayBuffer> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  const buf = await res.arrayBuffer();
  const head = new Uint8Array(buf, 0, 2);
  // Shipped gzipped; some hosts already decode it (Content-Encoding), some don't.
  if (head[0] === 0x1f && head[1] === 0x8b) {
    const stream = new Blob([buf])
      .stream()
      .pipeThrough(new DecompressionStream("gzip"));
    return new Response(stream).arrayBuffer();
  }
  return buf;
}

class Garment {
  readonly mesh: THREE.Mesh;
  private readonly geometry = new THREE.BufferGeometry();
  private readonly pos: Float32Array;
  private readonly rest: Float32Array;
  private readonly panel: Uint8Array;
  private readonly seams: Uint16Array | Uint32Array;
  private readonly centre: Float32Array;
  private readonly track: Float32Array;
  private readonly scale: Float32Array;
  private readonly resid: Int8Array;
  private readonly stored: number[];
  private readonly frames: number;
  private readonly panels: number;
  private readonly n: number;
  private shown = -1;
  private readonly q0 = new THREE.Quaternion();
  private readonly q1 = new THREE.Quaternion();
  private readonly m = new THREE.Matrix3();
  private readonly m4 = new THREE.Matrix4();
  private readonly rot = new Float32Array(9 * 8);
  private readonly tr = new Float32Array(3 * 8);
  private readonly edges: Uint32Array;
  private readonly smooth: Float32Array;

  constructor(info: GarmentInfo, buf: ArrayBuffer, material: THREE.Material) {
    const s = info.sections;
    const I = info.index32 ? Uint32Array : Uint16Array;
    this.n = info.vertices;
    this.frames = info.frames;
    this.panels = info.panels;
    this.stored = info.stored;
    this.rest = new Float32Array(buf, s.rest[0], s.rest[1]);
    this.panel = new Uint8Array(buf, s.panel[0], s.panel[1]);
    this.seams = new I(buf, s.seams[0], s.seams[1]);
    this.centre = new Float32Array(buf, s.centre[0], s.centre[1]);
    this.track = new Float32Array(buf, s.track[0], s.track[1]);
    this.scale = new Float32Array(buf, s.scale[0], s.scale[1]);
    this.resid = new Int8Array(buf, s.resid[0], s.resid[1]);
    this.pos = new Float32Array(this.n * 3);
    const index = new I(buf, s.index[0], s.index[1]);
    this.geometry.setIndex(new THREE.BufferAttribute(index, 1));
    // Triangle edges (each interior edge twice; harmless) for smoothing normals.
    this.edges = new Uint32Array(index.length * 2);
    for (let f = 0; f < index.length; f += 3) {
      const [a, b, c] = [index[f], index[f + 1], index[f + 2]];
      this.edges.set([a, b, b, c, c, a], f * 2);
    }
    this.smooth = new Float32Array(this.n * 3);
    this.geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage),
    );
    this.mesh = new THREE.Mesh(this.geometry, material);
    // Casts onto her and the floor, but doesn't receive: the generated surface has patches whose
    // normals face inward, and the body's shadow would print through them as blotches.
    this.mesh.castShadow = true;
    this.mesh.receiveShadow = false;
    this.mesh.frustumCulled = false;
    this.mesh.visible = false;
  }

  /** Pose the garment at a fractional simulation frame. */
  setFrame(frame: number) {
    const f = Math.min(this.frames - 1, Math.max(0, frame));
    if (Math.abs(f - this.shown) < 1e-3) return;
    this.shown = f;
    const f0 = Math.floor(f);
    const f1 = Math.min(f0 + 1, this.frames - 1);
    const a = f - f0;
    const P = this.panels;
    for (let p = 0; p < P; p++) {
      const o0 = (f0 * P + p) * 7;
      const o1 = (f1 * P + p) * 7;
      const t = this.track;
      this.q0.set(t[o0], t[o0 + 1], t[o0 + 2], t[o0 + 3]);
      this.q1.set(t[o1], t[o1 + 1], t[o1 + 2], t[o1 + 3]);
      this.q0.slerp(this.q1, a);
      this.m.setFromMatrix4(this.m4.makeRotationFromQuaternion(this.q0));
      this.rot.set(this.m.elements, p * 9); // column-major
      for (let k = 0; k < 3; k++)
        this.tr[p * 3 + k] = t[o0 + 4 + k] * (1 - a) + t[o1 + 4 + k] * a;
    }
    // Stored residual frames either side.
    const S = this.stored;
    let k = 0;
    while (k < S.length - 2 && S[k + 1] <= f) k++;
    const b =
      S[k + 1] === S[k]
        ? 0
        : Math.min(1, Math.max(0, (f - S[k]) / (S[k + 1] - S[k])));
    const n = this.n;
    const r0 = k * n * 3;
    const r1 = (k + 1) * n * 3;
    const { rest, panel, centre, rot, tr, resid, scale, pos } = this;
    for (let v = 0; v < n; v++) {
      const p = panel[v];
      const c = p * 3;
      const x = rest[v * 3] - centre[c];
      const y = rest[v * 3 + 1] - centre[c + 1];
      const z = rest[v * 3 + 2] - centre[c + 2];
      const R = p * 9;
      const s0 = scale[k * P + p] * (1 - b);
      const s1 = scale[(k + 1) * P + p] * b;
      const i = v * 3;
      pos[i] =
        rot[R] * x +
        rot[R + 3] * y +
        rot[R + 6] * z +
        centre[c] +
        tr[c] +
        resid[r0 + i] * s0 +
        resid[r1 + i] * s1;
      pos[i + 1] =
        rot[R + 1] * x +
        rot[R + 4] * y +
        rot[R + 7] * z +
        centre[c + 1] +
        tr[c + 1] +
        resid[r0 + i + 1] * s0 +
        resid[r1 + i + 1] * s1;
      pos[i + 2] =
        rot[R + 2] * x +
        rot[R + 5] * y +
        rot[R + 8] * z +
        centre[c + 2] +
        tr[c + 2] +
        resid[r0 + i + 2] * s0 +
        resid[r1 + i + 2] * s1;
    }
    this.geometry.attributes.position.needsUpdate = true;
    this.geometry.computeVertexNormals();
    // Smooth shading across seams once the two sides meet.
    const nrm = this.geometry.attributes.normal.array as Float32Array;
    const sm = this.seams;
    for (let j = 0; j < sm.length; j += 2) {
      const ia = sm[j] * 3;
      const ib = sm[j + 1] * 3;
      const dx = pos[ia] - pos[ib];
      const dy = pos[ia + 1] - pos[ib + 1];
      const dz = pos[ia + 2] - pos[ib + 2];
      if (dx * dx + dy * dy + dz * dz > 1e-4) continue;
      const nx = nrm[ia] + nrm[ib];
      const ny = nrm[ia + 1] + nrm[ib + 1];
      const nz = nrm[ia + 2] + nrm[ib + 2];
      const l = Math.hypot(nx, ny, nz) || 1;
      nrm[ia] = nrm[ib] = nx / l;
      nrm[ia + 1] = nrm[ib + 1] = ny / l;
      nrm[ia + 2] = nrm[ib + 2] = nz / l;
    }
    // One pass of normal smoothing over neighbours, flipping any neighbour that faces the other
    // way first, so creases and orientation seams in the generated surface don't print as lines.
    const acc = this.smooth;
    acc.set(nrm);
    const E = this.edges;
    for (let j = 0; j < E.length; j += 2) {
      const a = E[j] * 3;
      const b = E[j + 1] * 3;
      const sg =
        nrm[a] * nrm[b] + nrm[a + 1] * nrm[b + 1] + nrm[a + 2] * nrm[b + 2] < 0
          ? -1
          : 1;
      acc[a] += sg * nrm[b];
      acc[a + 1] += sg * nrm[b + 1];
      acc[a + 2] += sg * nrm[b + 2];
      acc[b] += sg * nrm[a];
      acc[b + 1] += sg * nrm[a + 1];
      acc[b + 2] += sg * nrm[a + 2];
    }
    for (let i = 0; i < acc.length; i += 3) {
      const l = Math.hypot(acc[i], acc[i + 1], acc[i + 2]) || 1;
      nrm[i] = acc[i] / l;
      nrm[i + 1] = acc[i + 1] / l;
      nrm[i + 2] = acc[i + 2] / l;
    }
  }

  dispose() {
    this.geometry.dispose();
  }
}

export default function DressingScene({
  manifest,
  progress,
  onFrame,
  onLoad,
  onAnchors,
  onUnsupported,
  className = "",
  label,
  follow = 5,
}: Props) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
      });
    } catch {
      onUnsupported?.();
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap; // soft via shadow.radius
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.setAttribute("aria-label", label);
    renderer.domElement.style.display = "block";
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = envTex;
    scene.environmentIntensity = 0.55;

    const key = new THREE.DirectionalLight("#fff4e8", 2.4);
    // High and in front: soft modelling on her, and a short contact shadow at her feet.
    key.position.set(-1.1, 4.4, 2.4);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.left = -1.2;
    key.shadow.camera.right = 1.2;
    key.shadow.camera.top = 2.1;
    key.shadow.camera.bottom = -0.2;
    key.shadow.camera.near = 0.5;
    key.shadow.camera.far = 8;
    key.shadow.bias = -0.0004;
    key.shadow.normalBias = 0.03;
    key.shadow.radius = 4;
    key.target.position.set(0, 0.9, 0);
    scene.add(key, key.target);
    const fill = new THREE.DirectionalLight("#e8eefc", 0.7);
    fill.position.set(2.4, 1.6, 1.8);
    const rim = new THREE.DirectionalLight("#ffffff", 1.1);
    rim.position.set(0.6, 2.6, -2.6);
    scene.add(fill, rim);

    const ground = new THREE.Mesh(
      new THREE.CircleGeometry(1.1, 48),
      new THREE.ShadowMaterial({ opacity: 0.1 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 50);
    let dist = 5;
    let width = 1;
    let height = 1;
    const resize = () => {
      width = Math.max(1, el.clientWidth);
      height = Math.max(1, el.clientHeight);
      const mobile = width < 768;
      // Phones: fewer pixels and a smaller shadow map keep the frame rate up.
      renderer.setPixelRatio(
        Math.min(window.devicePixelRatio || 1, mobile ? 1.5 : 2),
      );
      if (key.shadow.mapSize.x !== (mobile ? 1024 : 2048)) {
        key.shadow.mapSize.set(mobile ? 1024 : 2048, mobile ? 1024 : 2048);
        key.shadow.map?.dispose();
        key.shadow.map = null;
      }
      renderer.setSize(width, height, false);
      // Frame her like the video it replaces: right of centre on desktop, low and centred on phones.
      const share = mobile ? 0.46 : 0.73;
      const cx = mobile ? 0.5 : 0.64;
      const cy = mobile ? 0.7 : 0.5;
      dist = HEIGHT / (2 * share * Math.tan(THREE.MathUtils.degToRad(FOV / 2)));
      camera.aspect = width / height;
      camera.setViewOffset(
        width,
        height,
        width * (0.5 - cx),
        height * (0.5 - cy),
        width,
        height,
      );
      camera.updateProjectionMatrix();
      dirty = true;
    };

    const garments: Partial<Record<GarmentName, Garment>> = {};
    const materials = ORDER.map(
      (g) =>
        new THREE.MeshPhysicalMaterial({
          ...FABRIC[g],
          // Single-layer cloth: both sides show, but only the inner side goes into the shadow
          // map, or the thin surface shadows itself in patches.
          side: THREE.DoubleSide,
          shadowSide: THREE.BackSide,
        }),
    );
    let bodyReady = false;
    let cancelled = false;
    let dirty = true;
    const total = 2;
    let done = 0;
    const report = () => {
      if (!cancelled) onLoad?.(done / total, bodyReady && !!garments.blouse);
    };

    const loader = new GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);
    loader.load(
      manifest.body,
      (gltf) => {
        if (cancelled) return;
        gltf.scene.traverse((o) => {
          const mesh = o as THREE.Mesh;
          if (mesh.isMesh) {
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            const mat = mesh.material as THREE.MeshStandardMaterial;
            mat.envMapIntensity = 0.8;
          }
        });
        scene.add(gltf.scene);
        bodyReady = true;
        done++;
        dirty = true;
        report();
      },
      undefined,
      () => onUnsupported?.(),
    );
    // Blouse first (it's needed for the first look), then the others.
    (async () => {
      for (const [i, name] of ORDER.entries()) {
        try {
          const buf = await fetchBinary(manifest.garments[name].url);
          if (cancelled) return;
          const g = new Garment(manifest.garments[name], buf, materials[i]);
          garments[name] = g;
          scene.add(g.mesh);
          if (name === "blouse") done++;
          dirty = true;
          report();
        } catch {
          if (name === "blouse") onUnsupported?.();
        }
      }
    })();

    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    // Only render while the stage is on screen.
    let onScreen = true;
    const io = new IntersectionObserver(([e]) => {
      onScreen = e.isIntersecting;
      dirty = true;
    });
    io.observe(el);

    const { settled, leaveStart, leaveEnd } = manifest.timeline;
    const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
    const anchor = new THREE.Vector3();
    let shown = -1;
    let reported = -1;
    let clock = 0;

    const tick = (_t: number, deltaMs: number) => {
      if (!onScreen) return;
      clock += deltaMs / 1000;
      // NaN-proof: a NaN here would stick in the eased playhead for good.
      const raw = progress.current ?? 0;
      const target = (Number.isFinite(raw) ? clamp01(raw) : 0) * 3;
      const before = shown;
      if (shown < 0 || !Number.isFinite(shown) || reduced) shown = target;
      else if (shown !== target) {
        const k = 1 - Math.exp(-(Math.min(deltaMs, 100) / 1000) * follow);
        shown += (target - shown) * k;
        if (Math.abs(target - shown) < 1e-4) shown = target;
      }
      const moving = shown !== before;

      // Garments: chapter c (0..2) brings garment c on; from the second chapter the previous one
      // leaves first, and the new one starts arriving a moment later.
      const c = Math.min(
        2,
        Math.floor(shown - 1e-6) < 0 ? 0 : Math.floor(shown - 1e-6),
      );
      const u = shown - c;
      ORDER.forEach((name, i) => {
        const g = garments[name];
        if (!g) return;
        let frame = -1;
        if (i === c)
          frame = c === 0 ? u * settled : clamp01((u - 0.18) / 0.82) * settled;
        else if (i < c)
          frame =
            i === c - 1
              ? leaveStart + clamp01(u / 0.55) * (leaveEnd - leaveStart)
              : leaveEnd;
        else frame = 0;
        const visible = frame > 0.3 && frame < leaveEnd - 0.5;
        g.mesh.visible = visible;
        if (visible && (moving || dirty)) g.setFrame(frame);
      });

      // Camera: swing around her during each move, face her at each station, breathe when idle.
      const swing = Math.sin(Math.PI * clamp01(u)) * (c % 2 === 0 ? 1 : -1);
      const idle = reduced ? 0 : Math.sin(clock * 0.35) * 0.018;
      const az = swing * 0.42 + idle;
      const lift =
        Math.sin(Math.PI * clamp01(u)) * 0.12 +
        (reduced ? 0 : Math.sin(clock * 0.27) * 0.02);
      camera.position.set(
        Math.sin(az) * dist,
        0.86 + lift,
        Math.cos(az) * dist,
      );
      camera.lookAt(0, 0.86, 0);

      if (!bodyReady) return;
      renderer.render(scene, camera);
      dirty = false;

      if (onAnchors) {
        onAnchors(
          ANCHORS.map(([x, y, z]) => {
            anchor.set(x, y, z).project(camera);
            return {
              x: ((anchor.x + 1) / 2) * width,
              y: ((1 - anchor.y) / 2) * height,
              visible: anchor.z < 1,
            };
          }),
        );
      }
      const p = shown / 3;
      if (onFrame && Math.abs(p - reported) > 0.0003) {
        reported = p;
        onFrame(p);
      }
    };
    gsap.ticker.add(tick);

    return () => {
      cancelled = true;
      gsap.ticker.remove(tick);
      ro.disconnect();
      io.disconnect();
      Object.values(garments).forEach((g) => g?.dispose());
      materials.forEach((m) => m.dispose());
      envTex.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [
    manifest,
    progress,
    onFrame,
    onLoad,
    onAnchors,
    onUnsupported,
    label,
    follow,
  ]);

  return <div ref={host} className={className} />;
}
