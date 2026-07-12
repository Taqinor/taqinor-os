import api from './axios'
import { downloadBlobInGesture } from '../utils/downloadBlob'

// T9 — import réutilisable CSV/XLSX. Dry-run (aperçu/mapping) puis commit.
// XPLT1/XPLT2 — mode upsert + mapping sauvegardé, envoyés en options (jamais
// la société, toujours forcée côté serveur).
const importApi = {
  dryRun: (file, target, options = {}) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('target', target)
    if (options.mapping) fd.append('mapping', options.mapping)
    return api.post('/imports/dry-run/', fd)
  },
  commit: (file, target, options = {}) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('target', target)
    // XPLT1 — mode d'import optionnel (creer=défaut, maj, upsert).
    if (options.mode) fd.append('mode', options.mode)
    if (options.external_system) fd.append('external_system', options.external_system)
    if (options.mapping) fd.append('mapping', options.mapping)
    if (options.rollback_on_error) fd.append('rollback_on_error', 'true')
    return api.post('/imports/commit/', fd)
  },
  // XPLT2 — mappings colonne→champ sauvegardés (sélecteur), optionnellement
  // filtrés par cible.
  getSavedMappings: (target) =>
    api.get('/imports/mappings/', { params: target ? { target } : {} }),
  saveMapping: (target, nom, mapping) =>
    api.post('/imports/mapping/', { target, nom, mapping }),
  // XPLT2 — CSV des seules lignes en échec d'un job d'import (ré-importable).
  jobErreursCsv: (jobId) =>
    api.get(`/imports/jobs/${jobId}/erreurs.csv`, { responseType: 'blob' }),
  // Export Excel générique d'une liste (devis, factures, chantiers,
  // equipements, tickets). ids optionnel = sélection/filtre courant.
  exportList: (entity, ids) =>
    api.post(`/imports/export/${entity}/`, { ids }, { responseType: 'blob' }),

  // N97 — export configurable & sauvegarde (admin uniquement). Catalogue des
  // objets exportables + formats, export d'un objet, et bundle ZIP complet.
  getExportObjects: () => api.get('/imports/export-objects/'),
  exportObject: (object, format) =>
    api.post('/imports/export-object/', { object, format },
      { responseType: 'blob' }),
  sauvegarde: (objects, format) =>
    api.post('/imports/sauvegarde/', { objects, format },
      { responseType: 'blob' }),
}

// Télécharge un blob générique (CSV/XLSX/JSON/ZIP) en forçant le download.
// VX172 — appelé avec le blob déjà résolu (post-`await` de l'appelant) : pas
// de fenêtre pré-ouverte possible d'ici, mais `downloadBlobInGesture()`
// tente quand même l'onglet visible en iOS/standalone (repli `a.download`
// automatique si bloqué) au lieu du téléchargement invisible d'avant.
export function downloadBlob(blobData, filename) {
  downloadBlobInGesture().deliver(new Blob([blobData]), filename)
}

// Récupère le nom de fichier proposé par le serveur (Content-Disposition).
export function filenameFromResponse(res, fallback) {
  const cd = res?.headers?.['content-disposition'] || ''
  const m = /filename="?([^"]+)"?/.exec(cd)
  return m ? m[1] : fallback
}

// Télécharge un blob .xlsx renvoyé par l'API. VX172 — même traitement que
// downloadBlob() ci-dessus (helper générique partagé par les 2 noms).
export function downloadXlsx(blobData, filename) {
  downloadBlob(blobData, filename)
}

export default importApi
