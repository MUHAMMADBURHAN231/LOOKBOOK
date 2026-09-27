import * as THREE from "three";

/**
 * Verlet cloth: a grid of particles joined by distance constraints (structural + bend),
 * integrated at a fixed 60 Hz step. The top row is pinned to a rail.
 */
export class Cloth {
  readonly cols: number;
  readonly rows: number;
  readonly width: number;
  readonly height: number;
  readonly pos: Float32Array;
  readonly prev: Float32Array;
  private readonly rest: Float32Array;
  private readonly cA: Uint32Array;
  private readonly cB: Uint32Array;
  private readonly cLen: Float32Array;
  private readonly pinned: Uint8Array;

  constructor(cols = 36, rows = 46, width = 3.1, height = 4.2) {
    this.cols = cols;
    this.rows = rows;
    this.width = width;
    this.height = height;
    const n = cols * rows;
    this.pos = new Float32Array(n * 3);
    this.prev = new Float32Array(n * 3);
    this.rest = new Float32Array(n * 3);
    this.pinned = new Uint8Array(n);

    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const i = (y * cols + x) * 3;
        const px = (x / (cols - 1) - 0.5) * width;
        const py = -(y / (rows - 1)) * height;
        this.rest[i] = this.pos[i] = this.prev[i] = px;
        this.rest[i + 1] = this.pos[i + 1] = this.prev[i + 1] = py;
        this.rest[i + 2] = this.pos[i + 2] = this.prev[i + 2] = 0;
      }
    }
    // Gather the top edge along the rail (72% of the cloth's width) with alternating pleats, so the
    // slack falls into real vertical folds instead of hanging as a flat sheet.
    for (let x = 0; x < cols; x++) {
      const u = x / (cols - 1);
      this.pinned[x] = 1;
      this.pos[x * 3] = this.prev[x * 3] = (u - 0.5) * width * 0.72;
      this.pos[x * 3 + 2] = this.prev[x * 3 + 2] = 0.09 * Math.sin(u * Math.PI * 9);
    }

    const pairs: [number, number][] = [];
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const i = y * cols + x;
        if (x + 1 < cols) pairs.push([i, i + 1]);
        if (y + 1 < rows) pairs.push([i, i + cols]);
        if (x + 2 < cols) pairs.push([i, i + 2]); // bend resistance
        if (y + 2 < rows) pairs.push([i, i + 2 * cols]);
      }
    }
    this.cA = new Uint32Array(pairs.map((p) => p[0]));
    this.cB = new Uint32Array(pairs.map((p) => p[1]));
    this.cLen = new Float32Array(
      pairs.map(([a, b]) => {
        const dx = this.rest[a * 3] - this.rest[b * 3];
        const dy = this.rest[a * 3 + 1] - this.rest[b * 3 + 1];
        return Math.hypot(dx, dy);
      }),
    );
  }

  /**
   * @param wind   strength of the gusting breeze along +z
   * @param push   optional point (cloth-local x,y) and z-impulse from the visitor's pointer
   */
  step(dt: number, time: number, wind: number, push?: { x: number; y: number; force: number; radius: number }) {
    const { pos, prev, pinned } = this;
    const damping = 0.985;
    const g = -9.8 * dt * dt;
    const dt2 = dt * dt;
    const n = pinned.length;

    for (let p = 0; p < n; p++) {
      if (pinned[p]) continue;
      const i = p * 3;
      const x = pos[i], y = pos[i + 1], z = pos[i + 2];
      const vx = (x - prev[i]) * damping;
      const vy = (y - prev[i + 1]) * damping;
      const vz = (z - prev[i + 2]) * damping;
      prev[i] = x;
      prev[i + 1] = y;
      prev[i + 2] = z;
      // Layered sines give an irregular, travelling gust rather than a uniform flap.
      const gust =
        wind *
        (0.55 +
          0.3 * Math.sin(time * 1.1 + y * 1.7 + x * 0.6) +
          0.15 * Math.sin(time * 2.9 + x * 2.3 - y * 0.8));
      let fz = gust * 6;
      if (push) {
        const d = Math.hypot(x - push.x, y - push.y);
        if (d < push.radius) fz += push.force * (1 - d / push.radius) * 60;
      }
      pos[i] = x + vx + Math.sin(time * 0.7 + y) * wind * 0.4 * dt2;
      pos[i + 1] = y + vy + g;
      pos[i + 2] = z + vz + fz * dt2;
    }

    const { cA, cB, cLen } = this;
    for (let iter = 0; iter < 10; iter++) {
      for (let c = 0; c < cA.length; c++) {
        const a = cA[c] * 3, b = cB[c] * 3;
        const dx = pos[b] - pos[a], dy = pos[b + 1] - pos[a + 1], dz = pos[b + 2] - pos[a + 2];
        const d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1e-6;
        const diff = ((d - cLen[c]) / d) * 0.5;
        const pa = pinned[cA[c]], pb = pinned[cB[c]];
        // diff already halves the correction: free pairs share it, a pinned partner gives it all away.
        const wa = pa ? 0 : pb ? 2 : 1;
        const wb = pb ? 0 : pa ? 2 : 1;
        pos[a] += dx * diff * wa; pos[a + 1] += dy * diff * wa; pos[a + 2] += dz * diff * wa;
        pos[b] -= dx * diff * wb; pos[b + 1] -= dy * diff * wb; pos[b + 2] -= dz * diff * wb;
      }
    }
  }

  writeTo(geometry: THREE.BufferGeometry) {
    (geometry.attributes.position.array as Float32Array).set(this.pos);
    geometry.attributes.position.needsUpdate = true;
    geometry.computeVertexNormals();
  }
}

export type Weave = "plain" | "twill" | "knit" | "satin";

/** Procedural weave normal map: draw a height field on a canvas, then convert with a Sobel pass. */
export function weaveNormalMap(kind: Weave, size = 256): THREE.Texture | null {
  if (kind === "satin") return null;
  const h = new Float32Array(size * size);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let v = 0;
      if (kind === "plain") {
        const cx = Math.sin((x / size) * Math.PI * 32), cy = Math.sin((y / size) * Math.PI * 32);
        v = 0.5 + 0.5 * cx * cy;
      } else if (kind === "twill") {
        v = 0.5 + 0.5 * Math.sin(((x + y) / size) * Math.PI * 40) * (0.85 + 0.15 * Math.sin((y / size) * Math.PI * 80));
      } else {
        const col = Math.floor((x / size) * 40);
        const local = ((x / size) * 40) % 1;
        const vshape = Math.abs(local - 0.5) * 2;
        v = 0.5 + 0.5 * Math.sin(((y / size) * 72 + vshape * 0.9 + (col % 2) * 0.1) * Math.PI * 2);
      }
      h[y * size + x] = v;
    }
  }
  const data = new Uint8Array(size * size * 4);
  const at = (x: number, y: number) => h[((y + size) % size) * size + ((x + size) % size)];
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = (at(x + 1, y) - at(x - 1, y)) * 2;
      const dy = (at(x, y + 1) - at(x, y - 1)) * 2;
      const len = Math.hypot(dx, dy, 1);
      const i = (y * size + x) * 4;
      data[i] = ((-dx / len) * 0.5 + 0.5) * 255;
      data[i + 1] = ((-dy / len) * 0.5 + 0.5) * 255;
      data[i + 2] = ((1 / len) * 0.5 + 0.5) * 255;
      data[i + 3] = 255;
    }
  }
  const tex = new THREE.DataTexture(data, size, size, THREE.RGBAFormat);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(2, 2.6);
  // Mipmaps + trilinear filtering stop the fine weave from aliasing into moire stripes.
  tex.generateMipmaps = true;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.needsUpdate = true;
  return tex;
}
