// ACAL506 / ACAL507 — coordonnées collées dans le champ « Adresse » de l'atelier.
// Fonctions PURES (aucun DOM, aucun réseau). L'ordre lu est latitude puis longitude,
// celui des liens de carte. Aucune boîte géographique n'est codée ici.

export interface CoordonneesCollees {
  latitude: number;
  longitude: number;
}
export interface CoordonneesRefusees {
  refus: string;
}

const NOMBRE = '(-?\\d+(?:\\.\\d+)?)';
// `@lat,lng` (Google Maps), `q=lat,lng`, `ll=lat,lng`.
const LIEN = new RegExp(`(?:@|[?&]q=|[?&]ll=)${NOMBRE},${NOMBRE}`);
const COUPLE = new RegExp(`^${NOMBRE}\\s*[,;\\s]\\s*${NOMBRE}$`);

/** `{latitude, longitude}` si le texte est un couple (ou un lien de carte) en bornes ;
 *  `{refus}` s'il en est un hors bornes ; `null` pour tout autre texte (adresse). */
export function lireCoordonneesCollees(texte: string): CoordonneesCollees | CoordonneesRefusees | null {
  const t = (texte ?? '').trim();
  const m = LIEN.exec(t) ?? COUPLE.exec(t);
  if (!m) return null;
  const latitude = Number(m[1]);
  const longitude = Number(m[2]);
  if (Math.abs(latitude) > 90) return { refus: 'Latitude hors de -90 à 90 : vérifiez les coordonnées collées.' };
  if (Math.abs(longitude) > 180) return { refus: 'Longitude hors de -180 à 180 : vérifiez les coordonnées collées.' };
  return { latitude, longitude };
}

/** Libellé de la ligne de suggestion. */
export function libelleCoordonnees(c: CoordonneesCollees): string {
  return `Coordonnées collées : ${c.latitude}, ${c.longitude}`;
}

/** ACAL507 — proposer d'échanger les deux nombres ? Seulement quand le couple tel quel
 *  ne tombe dans aucun lieu du pays alors que le couple échangé en rend un ; un réseau
 *  en échec (`null`) ne propose rien. Ne décide JAMAIS d'échanger seul. */
export function proposerEchange(c: CoordonneesCollees, telQuel: boolean | null, echange: boolean | null): CoordonneesCollees | null {
  if (telQuel !== false || echange !== true) return null;
  if (Math.abs(c.longitude) > 90) return null; // le couple échangé serait hors bornes
  return { latitude: c.longitude, longitude: c.latitude };
}

/** Libellé de la seconde ligne : « Vouliez-vous dire 33.5731, -7.5898 ? ». */
export function libelleEchange(c: CoordonneesCollees): string {
  return `Vouliez-vous dire ${c.latitude}, ${c.longitude} ?`;
}
