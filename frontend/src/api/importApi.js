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
}

export default importApi
