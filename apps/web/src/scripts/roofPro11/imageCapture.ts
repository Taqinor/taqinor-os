/**
 * ACAL509 — la DATE DE PRISE DE VUE de l'image saisie (date + source), clé racine `imageCapture`
 * du document. SAISIE, jamais proposée : absente = jamais renseignée (la hauteur par l'ombre et
 * le rapport d'ombrage ne devinent aucune date). Même patron que `underlay.ts` : mémoire +
 * émission + graine à l'ouverture (`fondDocument.ts::semerFondDepuisDocument`).
 */
export interface ImageCapture {
  date: string;
  source: string;
}

export type LectureImageCapture =
  | { ok: true; valeur: ImageCapture }
  | { ok: false; champ: 'date' | 'source'; motif: string };

let memoire: ImageCapture | null = null;

/** Valide une saisie ; le refus NOMME le champ fautif. `aujourdhui` (AAAA-MM-JJ) sert aux tests. */
export function lireImageCapture(
  date: unknown,
  source: unknown,
  aujourdhui: string = new Date().toISOString().slice(0, 10),
): LectureImageCapture {
  const d = typeof date === 'string' ? date.trim() : '';
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
  const reel = m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])) : null;
  if (!m || !reel || reel.toISOString().slice(0, 10) !== d) {
    return { ok: false, champ: 'date', motif: 'Date de la photo illisible : écrire AAAA-MM-JJ (par exemple 2025-03-21).' };
  }
  if (d > aujourdhui) return { ok: false, champ: 'date', motif: 'Date de la photo dans le futur : une photo déjà prise est attendue.' };
  const s = typeof source === 'string' ? source.trim() : '';
  if (!s) return { ok: false, champ: 'source', motif: 'Dire d’où vient cette date (page du fournisseur, par exemple).' };
  return { ok: true, valeur: { date: d, source: s } };
}

/** À l'ouverture : retient la clé du document (illisible ou absente ⇒ rien). */
export function semerImageCapture(json: unknown): void {
  const brut = (json as { imageCapture?: { date?: unknown; source?: unknown } } | null | undefined)?.imageCapture;
  const lu = brut ? lireImageCapture(brut.date, brut.source) : null;
  memoire = lu?.ok ? lu.valeur : null;
}

/** Pose (ou, avec `null`, efface) la date saisie. */
export function poserImageCapture(valeur: ImageCapture | null): void {
  memoire = valeur;
}

/** La date et la source de la photo, ou `null` si jamais renseignées. */
export function dateImageCapturee(): ImageCapture | null {
  return memoire;
}

/** Pour `serializeLayout` : `{imageCapture}` ou rien (aucune clé tant que rien n'est saisi). */
export function imageCapturePourDocument(): { imageCapture?: ImageCapture } {
  return memoire ? { imageCapture: { ...memoire } } : {};
}
