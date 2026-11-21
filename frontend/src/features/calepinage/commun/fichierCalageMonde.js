/* ACAL424 — le calage d'une orthophoto de drone depuis son fichier « monde »
   (.jgw, .pgw, .wld : 6 nombres, un par ligne, ordre A D B E C F). Lecture et
   calcul PURS : aucune écriture, le calage ne part qu'au clic « Enregistrer le
   calage ». Seules les coordonnées en DEGRÉS (WGS84) sont acceptées : une
   projection en mètres (UTM…) demanderait une reprojection, hors périmètre. */

/** Les 4 coins `[lat, lng]` (NO, NE, SE, SO) d'une orthophoto, ou `{ erreur }`. */
export function coinsDepuisFichierMonde(texte, largeur, hauteur) {
  const nombres = String(texte ?? '').split(/\r?\n/)
    .map((l) => l.trim()).filter(Boolean).map(Number)
  if (nombres.length < 6 || nombres.slice(0, 6).some((n) => !Number.isFinite(n))) {
    return { erreur: 'Fichier de calage illisible : 6 nombres attendus, un par ligne.' }
  }
  if (!(largeur > 0) || !(hauteur > 0)) {
    return { erreur: 'Dimensions de la photo inconnues : attendez son chargement.' }
  }
  const [A, D, B, E, C, F] = nombres
  const point = (col, ligne) => [D * col + E * ligne + F, A * col + B * ligne + C]
  const coins = [
    point(-0.5, -0.5), point(largeur - 0.5, -0.5),
    point(largeur - 0.5, hauteur - 0.5), point(-0.5, hauteur - 0.5),
  ]
  if (coins.some(([lat, lng]) => Math.abs(lat) > 90 || Math.abs(lng) > 180)) {
    return { erreur: 'Coordonnées hors degrés : exportez l’orthophoto en WGS84.' }
  }
  return { coins }
}
