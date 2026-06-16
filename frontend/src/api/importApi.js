import api from './axios'

// T9 — import réutilisable CSV/XLSX. Dry-run (aperçu/mapping) puis commit.
const importApi = {
  dryRun: (file, target) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('target', target)
    return api.post('/imports/dry-run/', fd)
  },
  commit: (file, target) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('target', target)
    return api.post('/imports/commit/', fd)
  },
  // Export Excel générique d'une liste (devis, factures, chantiers,
  // equipements, tickets). ids optionnel = sélection/filtre courant.
  exportList: (entity, ids) =>
    api.post(`/imports/export/${entity}/`, { ids }, { responseType: 'blob' }),
}

// Télécharge un blob .xlsx renvoyé par l'API.
export function downloadXlsx(blobData, filename) {
  const url = URL.createObjectURL(new Blob([blobData]))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default importApi
