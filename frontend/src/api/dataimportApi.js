// WR5 — client de l'API `imports/` (export configurable + sauvegarde ZIP).
// Les wrappers existent déjà dans importApi.js (getExportObjects / exportObject
// / sauvegarde) et sont pleinement utilisés par la page Paramètres
// « Export / Sauvegarde » (ExportSauvegarde.jsx). On les ré-expose ici sous le
// nom de module attendu par la surface « Données » sans dupliquer la logique
// (une seule source de vérité). Aucun endpoint nouveau, aucun secret / prix
// d'achat n'est jamais exporté (garanti côté serveur).
import importApi, { downloadBlob, filenameFromResponse } from './importApi'

const dataimportApi = {
  // GET  /imports/export-objects/  → { objects, formats, default_format }.
  getExportObjects: () => importApi.getExportObjects(),
  // POST /imports/export-object/   → un fichier (blob) pour UN objet.
  exportObject: (object, format) => importApi.exportObject(object, format),
  // POST /imports/sauvegarde/      → bundle ZIP des objets choisis (blob).
  sauvegarde: (objects, format) => importApi.sauvegarde(objects, format),
}

export { downloadBlob, filenameFromResponse }
export default dataimportApi
