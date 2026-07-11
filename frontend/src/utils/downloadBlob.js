// Télécharge un blob (xlsx, etc.) reçu d'une réponse axios (responseType blob).
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'export'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

// QD2 — Récupère le nom de fichier cohérent posé par le serveur dans l'en-tête
// Content-Disposition (TAQINOR_Facture_Client_FAC-….pdf), avec repli sur le nom
// fourni. Gère filename* (RFC 5987) et filename="…". Renvoie toujours un nom.
export function filenameFromResponse(res, fallback = 'document.pdf') {
  const cd = res?.headers?.['content-disposition']
    || res?.headers?.get?.('content-disposition') || ''
  if (cd) {
    const star = /filename\*=(?:UTF-8'')?["']?([^;"']+)/i.exec(cd)
    if (star && star[1]) {
      try { return decodeURIComponent(star[1]) } catch { return star[1] }
    }
    const plain = /filename="?([^;"]+)"?/i.exec(cd)
    if (plain && plain[1]) return plain[1].trim()
  }
  return fallback
}

// VX81 — Nom de fichier horodaté pour les exports tableur (XLSX/CSV) qui n'ont
// pas de réponse serveur avec Content-Disposition à lire (cf. filenameFromResponse
// pour le cas PDF/QD2). Deux exports le même jour doivent produire deux noms
// DISTINCTS : `base_societe_AAAAMMJJ.ext` — jamais un nom nu que le navigateur
// désambiguïse en `(1)`/`(2)` (indistinguable une fois dans "Téléchargements").
// `societe` est optionnelle (repli silencieux si absente/vide) ; le résultat est
// toujours slugifié (espaces/accents/caractères spéciaux → `-`) pour rester un
// nom de fichier sûr sur tous les OS.
function slugPart(value) {
  return String(value ?? '')
    .normalize('NFD').replace(/[̀-ͯ]/g, '') // accents -> lettres nues
    .trim()
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function stampedFilename(base, ext, societe, date = new Date()) {
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const parts = [slugPart(base), slugPart(societe), `${yyyy}${mm}${dd}`].filter(Boolean)
  const cleanExt = String(ext ?? '').replace(/^\./, '')
  return `${parts.join('_')}.${cleanExt}`
}
