"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

/* ─────────────────────────────────────────────────────
   LOOKBOOK · WomanScene
   A stylised fashion-mannequin figure that dresses
   itself as the page is scrolled.  Four garments fly
   in one at a time from the right and settle onto the
   figure.  The scene has a pure white/warm-canvas
   background for the editorial-minimal aesthetic.
───────────────────────────────────────────────────── */

export type Garment = { name: string; color: string };

export const GARMENTS: Garment[] = [
  { name: "Silk blouse",        color: "#1A1A2E" }, // midnight navy
  { name: "Wide-leg trousers",  color: "#0D0D0D" }, // jet black
  { name: "Tailored blazer",    color: "#8B2635" }, // deep burgundy
  { name: "Wool overcoat",      color: "#7A6450" }, // dark camel
];

type Props = {
  /** 0..1 across the whole scroll story; read every frame via a ref. */
  progress: React.RefObject<number>;
  onGarment?: (index: number) => void;
  className?: string;
};

/* ── Figure geometry ────────────────────────────────── */
function buildFigure(): THREE.Group {
  const group = new THREE.Group();

  const mat = new THREE.MeshStandardMaterial({
    color: "#EDE9E3",
    roughness: 0.22,
    metalness: 0.0,
  });

  const seg = 24; // cylinder segments
  const add = (geo: THREE.BufferGeometry, x = 0, y = 0, z = 0, rx = 0, rz = 0) => {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z);
    m.rotation.set(rx, 0, rz);
    group.add(m);
    return m;
  };

  // Head
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.205, 32, 24), mat);
  head.position.set(0, 1.64, 0);
  head.scale.set(0.93, 1.08, 0.86);
  group.add(head);

  // Neck
  add(new THREE.CylinderGeometry(0.068, 0.08, 0.22, 16), 0, 1.42, 0);

  // Shoulders (wider, slightly flared)
  const sh = add(new THREE.CylinderGeometry(0.295, 0.265, 0.20, seg), 0, 1.285, 0);
  sh.scale.z = 0.60;

  // Chest
  const ch = add(new THREE.CylinderGeometry(0.258, 0.225, 0.40, seg), 0, 0.98, 0);
  ch.scale.z = 0.62;

  // Waist (noticeably narrower)
  const wa = add(new THREE.CylinderGeometry(0.195, 0.205, 0.30, seg), 0, 0.65, 0);
  wa.scale.z = 0.60;

  // Hips (wider again)
  const hi = add(new THREE.CylinderGeometry(0.245, 0.235, 0.30, seg), 0, 0.31, 0);
  hi.scale.z = 0.63;

  // Upper legs
  for (const s of [-1, 1] as const) {
    const ox = s * 0.115;

    const thigh = add(new THREE.CylinderGeometry(0.112, 0.100, 0.58, 16), ox, -0.14, 0);
    thigh.scale.z = 0.78;

    const calf = add(new THREE.CylinderGeometry(0.082, 0.062, 0.56, 16), ox, -0.76, 0);
    calf.scale.z = 0.76;

    // Foot
    const ft = new THREE.Mesh(new THREE.SphereGeometry(0.058, 12, 8), mat);
    ft.position.set(ox, -1.07, 0.04);
    ft.scale.set(1, 0.48, 1.6);
    group.add(ft);

    // Upper arm
    const ua = add(new THREE.CylinderGeometry(0.068, 0.060, 0.44, 12), s * 0.375, 0.975, 0, 0, s * 0.13);
    ua.scale.z = 0.75;

    // Forearm (slight angle away from body)
    const fa = add(new THREE.CylinderGeometry(0.054, 0.046, 0.40, 12), s * 0.440, 0.58, 0, 0, s * 0.24);
    fa.scale.z = 0.75;

    // Hand
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.046, 10, 10), mat);
    hand.position.set(s * 0.490, 0.36, 0);
    hand.scale.set(1, 0.80, 0.70);
    group.add(hand);
  }

  return group;
}

/* ── Garment silhouettes ────────────────────────────── */
function buildGarmentMesh(index: number, color: string): THREE.Mesh {
  const shape = new THREE.Shape();

  switch (index) {
    case 0: { // Silk blouse — fitted, slight flare at hem
      shape.moveTo(-0.10, 0.42);
      shape.bezierCurveTo(-0.22, 0.40, -0.32, 0.28, -0.30, 0.10);
      shape.lineTo(-0.26, -0.24);
      shape.bezierCurveTo(-0.28, -0.30, -0.26, -0.34, -0.20, -0.34);
      shape.lineTo(0.20, -0.34);
      shape.bezierCurveTo(0.26, -0.34, 0.28, -0.30, 0.26, -0.24);
      shape.lineTo(0.30, 0.10);
      shape.bezierCurveTo(0.32, 0.28, 0.22, 0.40, 0.10, 0.42);
      shape.bezierCurveTo(0.06, 0.46, -0.06, 0.46, -0.10, 0.42);
      break;
    }
    case 1: { // Wide-leg trousers — high waist, flared legs
      shape.moveTo(-0.26, 0.20);
      shape.lineTo(-0.38, -0.74);
      shape.lineTo(-0.19, -0.74);
      shape.bezierCurveTo(-0.16, -0.50, -0.13, -0.18, -0.12, -0.04);
      shape.lineTo(0.12, -0.04);
      shape.bezierCurveTo(0.13, -0.18, 0.16, -0.50, 0.19, -0.74);
      shape.lineTo(0.38, -0.74);
      shape.lineTo(0.26, 0.20);
      shape.bezierCurveTo(0.18, 0.24, -0.18, 0.24, -0.26, 0.20);
      break;
    }
    case 2: { // Tailored blazer — structured, single breasted
      shape.moveTo(-0.14, 0.58);
      shape.lineTo(-0.44, 0.50);
      shape.lineTo(-0.48, 0.34);
      shape.lineTo(-0.42, -0.54);
      shape.bezierCurveTo(-0.42, -0.58, -0.38, -0.60, -0.34, -0.58);
      shape.lineTo(0.34, -0.58);
      shape.bezierCurveTo(0.38, -0.60, 0.42, -0.58, 0.42, -0.54);
      shape.lineTo(0.48, 0.34);
      shape.lineTo(0.44, 0.50);
      shape.lineTo(0.14, 0.58);
      shape.bezierCurveTo(0.08, 0.62, -0.08, 0.62, -0.14, 0.58);

      // Lapel cutouts (holes) for a tailored look
      const lapelL = new THREE.Path();
      lapelL.moveTo(-0.13, 0.56);
      lapelL.lineTo(-0.18, 0.40);
      lapelL.lineTo(-0.05, 0.28);
      lapelL.lineTo(0.0, 0.36);
      lapelL.closePath();
      shape.holes.push(lapelL);

      const lapelR = new THREE.Path();
      lapelR.moveTo(0.13, 0.56);
      lapelR.lineTo(0.18, 0.40);
      lapelR.lineTo(0.05, 0.28);
      lapelR.lineTo(0.0, 0.36);
      lapelR.closePath();
      shape.holes.push(lapelR);
      break;
    }
    default: { // Wool overcoat — long, structured, slightly A-line
      shape.moveTo(-0.16, 0.62);
      shape.lineTo(-0.50, 0.52);
      shape.lineTo(-0.54, 0.34);
      shape.lineTo(-0.50, -0.88);
      shape.bezierCurveTo(-0.52, -0.94, -0.46, -0.96, -0.40, -0.92);
      shape.lineTo(0.40, -0.92);
      shape.bezierCurveTo(0.46, -0.96, 0.52, -0.94, 0.50, -0.88);
      shape.lineTo(0.54, 0.34);
      shape.lineTo(0.50, 0.52);
      shape.lineTo(0.16, 0.62);
      shape.bezierCurveTo(0.08, 0.68, -0.08, 0.68, -0.16, 0.62);
      break;
    }
  }

  // Slight extrusion for depth/shadow
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: 0.025,
    bevelEnabled: true,
    bevelThickness: 0.008,
    bevelSize: 0.006,
    bevelSegments: 2,
  });

  const mat = new THREE.MeshPhysicalMaterial({
    color,
    roughness: index === 0 ? 0.38 : index === 3 ? 0.72 : 0.58,
    metalness: 0,
    side: THREE.DoubleSide,
    ...(index === 0 ? { sheen: 0.4, sheenRoughness: 0.5 } : {}),
  });

  return new THREE.Mesh(geo, mat);
}

/* ── Garment world positions (on the figure) ────────── */
const GARMENT_POSES = [
  { y: 0.96, z: 0.13, scale: 1.05 }, // blouse
  { y: 0.14, z: 0.13, scale: 1.10 }, // trousers
  { y: 1.00, z: 0.22, scale: 1.08 }, // blazer
  { y: 0.72, z: 0.32, scale: 1.20 }, // coat
] as const;

/* ── Ease helpers ───────────────────────────────────── */
const easeOutCubic = (t: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);

/* ── Component ──────────────────────────────────────── */
export default function WomanScene({ progress, onGarment, className = "" }: Props) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        powerPreference: "high-performance",
        alpha: false,
      });
    } catch {
      el.dataset.webgl = "off";
      return;
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.setClearColor("#F8F7F5");
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    const canvas = renderer.domElement;
    canvas.setAttribute("role", "img");
    canvas.setAttribute(
      "aria-label",
      "A fashion mannequin being dressed in silk blouse, wide-leg trousers, blazer and overcoat as you scroll."
    );
    el.appendChild(canvas);

    /* Scene */
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#F8F7F5");

    /* Camera */
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 60);
    camera.position.set(0, 0.22, 9.0);
    camera.lookAt(0, 0.22, 0);

    /* Studio lighting */
    scene.add(new THREE.AmbientLight("#ffffff", 0.75));

    const key = new THREE.DirectionalLight("#fffaf4", 2.0);
    key.position.set(2.5, 4, 4);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.near = 0.5;
    key.shadow.camera.far = 20;
    scene.add(key);

    const fill = new THREE.DirectionalLight("#eef2ff", 1.0);
    fill.position.set(-3.5, 1.5, 2.5);
    scene.add(fill);

    const rim = new THREE.DirectionalLight("#ffffff", 0.5);
    rim.position.set(0, 3, -4);
    scene.add(rim);

    /* Ground plane (soft shadow catcher) */
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(12, 12),
      new THREE.ShadowMaterial({ opacity: 0.06 })
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -1.12;
    ground.receiveShadow = true;
    scene.add(ground);

    /* Figure */
    const figure = buildFigure();
    figure.traverse((c) => { if (c instanceof THREE.Mesh) c.castShadow = true; });
    scene.add(figure);

    /* Garments */
    const OFF_X = 20;
    const garmentMeshes = GARMENTS.map((g, i) => {
      const mesh = buildGarmentMesh(i, g.color);
      const pose = GARMENT_POSES[i];
      mesh.scale.setScalar(pose.scale);
      mesh.position.set(OFF_X, pose.y, pose.z);
      mesh.castShadow = true;
      scene.add(mesh);
      return mesh;
    });

    /* Smooth x-position target per garment */
    const currentX = GARMENTS.map(() => OFF_X);

    let lastGarment = -1;

    /* Resize */
    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    /* Visibility */
    let visible = true;
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting));
    io.observe(el);

    /* Render loop */
    let raf = 0;
    let lastTs = performance.now();
    const SEG = 1 / GARMENTS.length; // scroll fraction per garment

    const loop = (ts: number) => {
      raf = requestAnimationFrame(loop);
      const dt = Math.min(0.1, (ts - lastTs) / 1000);
      lastTs = ts;
      if (!visible || document.hidden) return;

      const p = progress.current ?? 0;
      const wide = camera.aspect > 1.1;

      /* Figure position: right half on wide, centred on narrow */
      const figTargetX = wide ? 1.4 : 0;
      figure.position.x += (figTargetX - figure.position.x) * (1 - Math.exp(-dt * 6));

      /* Subtle camera drift following figure */
      camera.position.x += (figTargetX * 0.18 - camera.position.x) * (1 - Math.exp(-dt * 3));
      camera.lookAt(figTargetX * 0.5, 0.22, 0);

      /* Garment animation */
      let activeGarment = -1;

      GARMENTS.forEach((_, i) => {
        const segStart = i * SEG;
        const segEnd   = segStart + SEG * 0.65; // enter in first 65% of segment
        const t        = easeOutCubic((p - segStart) / Math.max(0.001, segEnd - segStart));

        const pose = GARMENT_POSES[i];
        const pose_x = figTargetX; // garment sits on figure

        /* Target X: off-screen until its turn, then on figure */
        const targetX = t >= 0.01 ? pose_x : OFF_X;
        currentX[i] += (targetX - currentX[i]) * (reduced ? 1 : 1 - Math.exp(-dt * (t > 0.01 ? 12 : 2)));

        garmentMeshes[i].position.x = currentX[i];
        /* Slight arc: garment drops slightly as it settles */
        garmentMeshes[i].position.y = pose.y + Math.max(0, (1 - t) * 0.4) * (t > 0.01 ? 1 : 0);
        /* Slight tilt that resolves on landing */
        garmentMeshes[i].rotation.z = Math.max(0, (1 - t) * 0.25) * (t > 0.01 ? 1 : 0);

        if (t > 0.5) activeGarment = i;
      });

      if (activeGarment !== lastGarment) {
        lastGarment = activeGarment;
        if (activeGarment >= 0) onGarment?.(activeGarment);
      }

      renderer.render(scene, camera);
    };

    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      garmentMeshes.forEach((m) => {
        m.geometry.dispose();
        (m.material as THREE.Material).dispose();
      });
      renderer.dispose();
      canvas.remove();
    };
  }, [progress, onGarment]);

  return <div ref={host} className={className} />;
}
