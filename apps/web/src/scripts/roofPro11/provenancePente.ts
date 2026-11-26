// ACAL252 — provenance de la pente d'un pan, sortie À L'IDENTIQUE de `prefill.ts` (ACAL579 : un
// fichier de 2 000 lignes ou plus ne grossit pas).

/** ACAL252 — la pente (°) que décrit une `pitchSource`, ou `null` quand elle ne la détermine pas. */
export function penteDecrite(source: Record<string, unknown>): number | null {
  const n = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
  if (source.mode === 'degres') return n(source.degres);
  if (source.mode === 'pourcentage') {
    const p = n(source.pourcentage);
    return p === null ? null : (Math.atan(p / 100) * 180) / Math.PI;
  }
  if (source.mode === 'cotes') {
    const portee = n(source.porteeM);
    const hauteur = n(source.hauteurFaitageM);
    return portee === null || hauteur === null || portee === 0 ? null : (Math.atan(hauteur / portee) * 180) / Math.PI;
  }
  return null;
}

/**
 * ACAL252 — `{ pitchSource }` à réémettre pour un pan, ou rien. La provenance est conservée
 * VERBATIM tant qu'elle décrit la pente émise ; une pente retouchée à la main dans l'atelier
 * (écart > 1e-6°) n'est plus celle que la source décrit : elle est alors omise, jamais mentie.
 */
/** ACAL1923 — la pente ÉCRITE d'un pan : un toit plat n'en a pas (0), jamais la valeur de départ du curseur
 *  (22°) ni une pente restée d'avant le passage en plat ; un toit en pente garde la sienne. */
export function penteEmise(roofType: string | undefined, pitchDeg: number): number {
  return roofType === 'flat' ? 0 : pitchDeg;
}

export function pitchSourceEmise(source: Record<string, unknown> | undefined, pitchDeg: number): { pitchSource?: Record<string, unknown> } {
  if (!source || typeof source !== 'object' || Array.isArray(source)) return {};
  const decrite = penteDecrite(source);
  if (decrite !== null && Number.isFinite(pitchDeg) && Math.abs(decrite - pitchDeg) > 1e-6) return {};
  return { pitchSource: JSON.parse(JSON.stringify(source)) as Record<string, unknown> };
}
