// Nouveau fichier car : optimizer.ts est un fichier gelé (C20) — géométrie pure du départage du mou (CAL83), sortie telle quelle.

/** Repère (u, v) du pavage à partir de l'azimut d'empilement. */
export function axesDepartage(azimuthDeg: number): { u: [number, number]; v: [number, number] } {
  const az = (azimuthDeg * Math.PI) / 180;
  const f: [number, number] = [Math.sin(az), Math.cos(az)]; // visée (E, N) = progression
  return { u: [-f[1], f[0]], v: f };
}

/** Distance d'un point au bord du tracé (m) — même mesure que le pavage. */
export function distanceAuBord(p: [number, number], ring: [number, number][]): number {
  let min = Infinity;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const ax = ring[j][0];
    const ay = ring[j][1];
    const dx = ring[i][0] - ax;
    const dy = ring[i][1] - ay;
    const len2 = dx * dx + dy * dy;
    let t = len2 === 0 ? 0 : ((p[0] - ax) * dx + (p[1] - ay) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    min = Math.min(min, Math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy)));
  }
  return min;
}
