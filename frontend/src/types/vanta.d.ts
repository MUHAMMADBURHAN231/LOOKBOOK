declare module "vanta/dist/vanta.fog.min" {
  const FOG: (options: Record<string, unknown>) => { destroy: () => void; setOptions: (o: Record<string, unknown>) => void };
  export default FOG;
}
