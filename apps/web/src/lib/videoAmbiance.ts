/**
 * WAUD54 — garde unique des vidéos d'ambiance (hero.mp4, boucle teaser du
 * chantier) : ordinateur (≥ 1024 px) + 4G ou réseau inconnu, sans économie de
 * données ni reduced-motion. Partout ailleurs l'affiche reste le héros et la
 * vidéo de chantier reste en clic-pour-lire (LiteVideo) : 2,1 + 2,8 Mo en moins
 * sur un téléphone en 3G.
 */
export const LARGEUR_MIN_VIDEO_PX = 1024;

export interface ContexteVideo {
  largeur: number;
  /** navigator.connection.effectiveType : absent sur Safari et Firefox (réseau inconnu). */
  effectiveType?: string;
  saveData: boolean;
  motionOk: boolean;
}

export function videoAmbianceAutorisee(c: ContexteVideo): boolean {
  if (!c.motionOk || c.saveData) return false;
  if (c.largeur < LARGEUR_MIN_VIDEO_PX) return false;
  return c.effectiveType === undefined || c.effectiveType === '4g';
}

/** Lecture du navigateur, côté client seulement. */
export function videoAmbianceDuNavigateur(): boolean {
  const connexion = (navigator as Navigator & {
    connection?: { effectiveType?: string; saveData?: boolean };
  }).connection;
  return videoAmbianceAutorisee({
    largeur: window.innerWidth,
    effectiveType: connexion?.effectiveType,
    saveData: connexion?.saveData === true,
    motionOk: matchMedia('(prefers-reduced-motion: no-preference)').matches,
  });
}
