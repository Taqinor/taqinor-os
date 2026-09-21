/* AOF174 — helpers partagés de l'écran « Dossier de soumission ».
   Extrait de DossierPage.jsx (react-refresh/only-export-components : un
   fichier de composant ne doit exporter QUE des composants). */

// Visibilités jamais listées dans le dossier de dépôt (économie directeur).
const VISIBILITES_MASQUEES = new Set(['interne', 'directeur'])

export function piecesVisibles(pieces) {
  return (pieces || []).filter((p) => !VISIBILITES_MASQUEES.has(p.visibilite))
}
