/**
 * ACAL417 — LA PENTE 22° ET LA FACE SUD DE DÉPART NE SONT PAS « CHOISIES ».
 *
 * Un pan neuf démarre à 22° face Sud (valeurs de CALCUL, `zones.ts::panVierge`), mais les puces
 * « ~22° » et « Sud » s'affichaient pressées comme un choix, et rien dans le document ne séparait
 * ce défaut d'un relevé. Ce module dit ce qui est confirmé : la pente l'est dès qu'une
 * `pitchSource` existe (onglet Pente, clic sur une puce, curseur), la face dès qu'elle est réglée
 * à la main (`facingManual`) ou relevée (`facingAzimuthSource`). Tant que non : AUCUNE puce
 * pressée et une mention « … par défaut — à confirmer » ; le calcul continue sur ces valeurs,
 * nommées. Un clic écrit `pitchSource = { mode: 'degres', degres }` : la source voyage au document.
 */
export interface EtatHypotheses {
  pitched: boolean;
  pitchDeg: number;
  pitchSource?: unknown;
  facingAzimuthDeg: number;
  facingManual: boolean;
  facingAzimuthSource?: unknown;
  facingAutoInferred: boolean;
}

const presente = (v: unknown): boolean => v != null && typeof v === 'object' && !Array.isArray(v);
const NOMS = ['Nord', 'Nord-Est', 'Est', 'Sud-Est', 'Sud', 'Sud-Ouest', 'Ouest', 'Nord-Ouest'];

/** Le nom de la face d'un pan, au huitième de tour le plus proche (0° = Nord). ACAL1970 : partagé (motif de pan vide). */
export function nomDeFace(azimutDeg: number): string {
  return NOMS[Math.round((((azimutDeg % 360) + 360) % 360) / 45) % 8];
}

export function etatHypotheses(e: EtatHypotheses): {
  penteConfirmee: boolean;
  faceConfirmee: boolean;
  notePente: string;
  noteFace: string;
} {
  const penteConfirmee = presente(e.pitchSource);
  const faceConfirmee = e.facingManual || presente(e.facingAzimuthSource);
  const nom = nomDeFace(e.facingAzimuthDeg);
  return {
    penteConfirmee,
    faceConfirmee,
    notePente: e.pitched && !penteConfirmee ? `Pente : ${Math.round(e.pitchDeg)}° par défaut — à confirmer` : '',
    noteFace:
      e.pitched && !faceConfirmee
        ? `Face : ${e.facingAutoInferred ? 'déduite des pans voisins' : `${nom} par défaut`} — à confirmer`
        : '',
  };
}

/** La source de pente écrite par un clic sur une puce ou le curseur. */
export const sourcePenteClic = (degres: number): Record<string, unknown> => ({ mode: 'degres', degres });

/** Rend l'état : puces pressées seulement si confirmées, mentions (la mention de pente est
 *  créée au besoin, juste avant celle de la face). */
export function appliquerHypotheses(e: EtatHypotheses, noteFace: HTMLElement | null): void {
  if (typeof document === 'undefined') return;
  const s = etatHypotheses(e);
  const presse = (sel: string, attr: string, confirmee: boolean, valeur: number) =>
    document.querySelectorAll<HTMLButtonElement>(sel).forEach((b) =>
      b.setAttribute('aria-pressed', String(confirmee && Number(b.getAttribute(attr)) === Math.round(valeur))),
    );
  presse('[data-pitch]', 'data-pitch', s.penteConfirmee, e.pitchDeg);
  presse('[data-facing]', 'data-facing', s.faceConfirmee, e.facingAzimuthDeg);
  let np = document.getElementById('rp9-pitch-note');
  if (!np && noteFace?.parentElement) {
    np = document.createElement('p');
    np.id = 'rp9-pitch-note';
    np.className = noteFace.className;
    noteFace.parentElement.insertBefore(np, noteFace);
  }
  if (np) np.textContent = s.notePente;
}
