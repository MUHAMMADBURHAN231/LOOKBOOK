"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { Cloth, type Weave, weaveNormalMap } from "./cloth";

export type Fabric = {
  name: string;
  color: string;
  roughness: number;
  sheen: number;
  sheenRoughness: number;
  sheenColor: string;
  weave: Weave;
  normalScale: number;
};

/** The story moves through these materials as the page scrolls. */
export const FABRICS: Fabric[] = [
  { name: "Raw cotton", color: "#e4e2da", roughness: 0.9, sheen: 0.5, sheenRoughness: 0.8, sheenColor: "#ffffff", weave: "plain", normalScale: 0.35 },
  { name: "Navy wool twill", color: "#14233b", roughness: 0.96, sheen: 1, sheenRoughness: 0.6, sheenColor: "#7890b4", weave: "twill", normalScale: 0.35 },
  { name: "Indigo denim", color: "#2a4163", roughness: 0.92, sheen: 0.35, sheenRoughness: 0.9, sheenColor: "#a8bfd9", weave: "twill", normalScale: 0.6 },
  { name: "Emerald satin", color: "#0b4a35", roughness: 0.3, sheen: 0.8, sheenRoughness: 0.3, sheenColor: "#4fae86", weave: "satin", normalScale: 0 },
  { name: "Camel cashmere", color: "#a87a4a", roughness: 0.97, sheen: 1, sheenRoughness: 0.45, sheenColor: "#f2d3a8", weave: "knit", normalScale: 0.22 },
];

type Props = {
  /** 0..1 across the whole FABRICS list; read every frame, so a ref avoids React re-renders. */
  progress: React.RefObject<number>;
  onFabric?: (index: number) => void;
  className?: string;
};

export default function ClothScene({ progress, onFabric, className = "" }: Props) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    } catch {
      el.dataset.webgl = "off"; // no WebGL: the page keeps its solid background
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.92;
    renderer.setClearColor("#06080a");
    const canvas = renderer.domElement;
    canvas.setAttribute("role", "img");
    canvas.setAttribute(
      "aria-label",
      "A length of fabric hanging from a steel rail. It changes material as you scroll: cotton, wool, denim, satin and cashmere.",
    );
    el.appendChild(canvas);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog("#06080a", 9, 16);
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50);

    scene.add(new THREE.HemisphereLight("#cfe6ee", "#0b0f12", 0.35));
    const key = new THREE.DirectionalLight("#fff0dd", 1.7);
    key.position.set(3.5, 4, 5);
    scene.add(key);
    const rim = new THREE.DirectionalLight("#bfe3ee", 2.4);
    rim.position.set(-4, 2.5, -3.5);
    scene.add(rim);
    const under = new THREE.PointLight("#ff5b1f", 1.2, 8);
    under.position.set(0.4, -3.2, 1.8); // faint warm bounce from the signal colour
    scene.add(under);

    const cloth = new Cloth();
    const geometry = new THREE.PlaneGeometry(cloth.width, cloth.height, cloth.cols - 1, cloth.rows - 1);
    const normalMaps = new Map<Weave, THREE.Texture | null>(
      (["plain", "twill", "knit", "satin"] as Weave[]).map((w) => [w, weaveNormalMap(w)]),
    );
    const aniso = renderer.capabilities.getMaxAnisotropy();
    normalMaps.forEach((t) => t && (t.anisotropy = aniso));
    const material = new THREE.MeshPhysicalMaterial({
      side: THREE.DoubleSide,
      envMapIntensity: 0.55,
      normalScale: new THREE.Vector2(0.5, 0.5),
    });
    const mesh = new THREE.Mesh(geometry, material);

    const rig = new THREE.Group();
    rig.add(mesh);
    const rail = new THREE.Mesh(
      new THREE.CylinderGeometry(0.022, 0.022, cloth.width + 0.7, 24),
      new THREE.MeshStandardMaterial({ color: "#c9d1d6", metalness: 1, roughness: 0.28 }),
    );
    rail.rotation.z = Math.PI / 2;
    rail.position.y = 0.02;
    rig.add(rail);
    rig.position.y = 2.05;
    scene.add(rig);

    // Settle the drape before the first frame so it never "drops" into place on load.
    for (let i = 0; i < 300; i++) cloth.step(1 / 60, i / 60, 0.35);
    cloth.writeTo(geometry);

    const colorA = new THREE.Color();
    const colorB = new THREE.Color();
    let smoothed = progress.current ?? 0;
    let lastFabric = -1;

    const applyFabric = (p: number) => {
      const f = p * (FABRICS.length - 1);
      const i = Math.min(FABRICS.length - 2, Math.floor(f));
      const t = f - i;
      const a = FABRICS[i], b = FABRICS[i + 1];
      material.color.copy(colorA.set(a.color).lerp(colorB.set(b.color), t));
      material.sheenColor.copy(colorA.set(a.sheenColor).lerp(colorB.set(b.sheenColor), t));
      material.roughness = THREE.MathUtils.lerp(a.roughness, b.roughness, t);
      material.sheen = THREE.MathUtils.lerp(a.sheen, b.sheen, t);
      material.sheenRoughness = THREE.MathUtils.lerp(a.sheenRoughness, b.sheenRoughness, t);
      // Swap weave maps at the midpoint while their strength dips to zero, so the change is invisible.
      const near = t < 0.5 ? a : b;
      const map = normalMaps.get(near.weave) ?? null;
      if (material.normalMap !== map) {
        material.normalMap = map;
        material.needsUpdate = true;
      }
      const s = near.normalScale * Math.abs(t - 0.5) * 2;
      material.normalScale.set(s, s);
      const nearest = Math.round(f);
      if (nearest !== lastFabric) {
        lastFabric = nearest;
        onFabric?.(nearest);
      }
    };

    // Pointer: brushing past the fabric pushes it, like a hand moving through a rail of clothes.
    const pointer = { ndc: new THREE.Vector2(), last: new THREE.Vector2(), speed: 0, active: false };
    const raycaster = new THREE.Raycaster();
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    const hit = new THREE.Vector3();
    const onPointer = (e: PointerEvent) => {
      pointer.ndc.set((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
      pointer.speed = Math.min(1.5, pointer.speed + pointer.ndc.distanceTo(pointer.last) * 6);
      pointer.last.copy(pointer.ndc);
      pointer.active = true;
    };
    if (!reduced) window.addEventListener("pointermove", onPointer, { passive: true });

    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    let visible = true;
    const io = new IntersectionObserver(([entry]) => (visible = entry.isIntersecting));
    io.observe(el);

    let raf = 0;
    let acc = 0;
    let simTime = 3;
    let lastTs = performance.now();
    const loop = (ts: number) => {
      raf = requestAnimationFrame(loop);
      const dt = Math.min(0.1, (ts - lastTs) / 1000);
      lastTs = ts;
      if (!visible || document.hidden) return;

      const target = progress.current ?? 0;
      smoothed += (target - smoothed) * (reduced ? 1 : 1 - Math.exp(-dt * 6));
      applyFabric(smoothed);

      // Framing: fabric sits right of the headline on wide screens, centred on narrow ones.
      const wide = camera.aspect > 1.1;
      const baseX = wide ? 2.3 : 0;
      rig.position.x = baseX - smoothed * (wide ? 0.6 : 0);
      // On narrow screens lift the fabric into the upper half so body copy sits on dark ink.
      rig.position.y = wide ? 2.05 : 2.9;
      rig.scale.setScalar(wide ? 1 : 0.82);
      rig.rotation.y = -0.38 + smoothed * 0.76;
      camera.position.set(Math.sin(smoothed * Math.PI) * 0.6, 0.05, (wide ? 11 : 13) - Math.sin(smoothed * Math.PI) * 1.4);
      camera.lookAt(wide ? 0.6 : 0, -0.1, 0);

      if (!reduced) {
        let push: { x: number; y: number; force: number; radius: number } | undefined;
        if (pointer.active && pointer.speed > 0.02) {
          raycaster.setFromCamera(pointer.ndc, camera);
          const inv = new THREE.Matrix4().copy(rig.matrixWorld).invert();
          const localRay = raycaster.ray.clone().applyMatrix4(inv);
          if (localRay.intersectPlane(plane, hit)) push = { x: hit.x, y: hit.y, force: pointer.speed, radius: 0.7 };
        }
        pointer.speed *= Math.exp(-dt * 4);
        acc += dt;
        let steps = 0;
        while (acc >= 1 / 60 && steps < 3) {
          simTime += 1 / 60;
          cloth.step(1 / 60, simTime, 0.35, push);
          acc -= 1 / 60;
          steps++;
        }
        if (steps) cloth.writeTo(geometry);
      }
      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onPointer);
      ro.disconnect();
      io.disconnect();
      geometry.dispose();
      material.dispose();
      normalMaps.forEach((t) => t?.dispose());
      pmrem.dispose();
      renderer.dispose();
      canvas.remove();
    };
  }, [progress, onFabric]);

  return <div ref={host} className={className} />;
}
