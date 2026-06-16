import api from './axios'

// Import réutilisable CSV/XLSX (leads, clients, produits). Flux en 2 temps :
// preview (dry-run, 10 lignes) → confirm (import complet, création seule).
const importsApi = {
  getSpecs: () => api.get('/imports/specs/'),
  preview: (target, file) => {
    const fd = new FormData()
    fd.append('target', target)
    fd.append('file', file)
    return api.post('/imports/preview/', fd)
  },
  confirm: (target, file) => {
    const fd = new FormData()
    fd.append('target', target)
    fd.append('file', file)
    return api.post('/imports/confirm/', fd)
  },
}

export default importsApi
