// QS1 — ouvre un PDF (Blob) dans un NOUVEL ONGLET (window.open) ; si le
// navigateur bloque la popup, retombe sur le téléchargement `openPdfBlob`.
// Retourne 'open' | 'download' (utile aux tests).
export function ouvrirPdfBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const win = window.open(url, '_blank', 'noopener')
  setTimeout(() => URL.revokeObjectURL(url), 60000)
  if (win) return 'open'
  openPdfBlob(blob, filename)
  return 'download'
}

// QS1 — vrai si la réponse est bien un PDF (et pas une page HTML d'erreur…).
export function estBlobPdf(blob) {
  return blob instanceof Blob && (blob.type || '').includes('pdf')
}

// QS1 — extrait un message FR lisible d'une erreur axios `responseType: 'blob'`.
// L'erreur DRF arrive alors dans un Blob que les helpers JSON classiques ne
// savent pas lire (d'où les « PDF indisponible » génériques) : on relit le
// Blob, on parse le JSON, puis on choisit le message le plus honnête
// (detail serveur > permission 403 > repli fourni).
export async function messageErreurBlob(err, {
  fallback = 'Une erreur est survenue. Réessayez.',
  forbidden = 'Accès refusé : vous n\'avez pas la permission de générer ce document.',
} = {}) {
  const resp = err?.response
  if (!resp) return 'Serveur injoignable — vérifiez la connexion puis réessayez.'
  let data = resp.data
  if (data instanceof Blob) {
    try { data = JSON.parse(await data.text()) } catch { data = null }
  }
  if (data) {
    if (typeof data === 'string') return data
    if (data.detail) return data.detail
    if (Array.isArray(data.non_field_errors) && data.non_field_errors[0]) {
      return data.non_field_errors[0]
    }
    for (const v of Object.values(data)) {
      const m = Array.isArray(v) ? v[0] : v
      if (typeof m === 'string') return m
    }
  }
  if (resp.status === 403) return forbidden
  return fallback
}

// Ouvre/télécharge un blob PDF reçu d'une réponse axios (responseType blob).
export function openPdfBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.target = '_blank'
  a.rel = 'noopener'
  if (filename) a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}
