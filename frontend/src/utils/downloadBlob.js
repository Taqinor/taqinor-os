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
