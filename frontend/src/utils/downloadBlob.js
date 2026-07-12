// VX49 — import PARESSEUX du toast : `ui/Toaster` tire `sonner` (dépendance
// externe + JSX), indésirable dans un module utilitaire testé en `node --test`
// SANS bundler ni node_modules. Le dynamic import échoue proprement (catch) en
// environnement de test — le helper reste 100% fonctionnel sans le toast.
async function toastErreur(message) {
  try {
    const { toast } = await import('../ui/Toaster')
    toast.error(message)
  } catch { /* pas d'UI de toast disponible (test / SSR) — silencieux */ }
}

// Télécharge un blob (xlsx, etc.) reçu d'une réponse axios (responseType blob).
// VX49 — un blob invalide (ou un DOM indisponible) ne doit jamais échouer en
// silence : toast FR + `revokeObjectURL` garanti en `finally` (sinon fuite
// mémoire sur des échecs répétés, ex. blob corrompu retenté en boucle).
export function downloadBlob(blob, filename) {
  let url
  try {
    url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || 'export'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } catch {
    toastErreur('Fichier indisponible — réessayez.')
  } finally {
    if (url) setTimeout(() => URL.revokeObjectURL(url), 10000)
  }
}

// VX172 — vrai en iOS Safari OU en PWA installée (standalone) : Safari iOS
// SUPPORTE bien `a.download` sur une URL blob (pas d'échec universel), mais en
// coquille STANDALONE le fichier atterrit dans un gestionnaire de
// téléchargements indécouvrable — l'utilisateur ne voit jamais son export.
// `typeof window === 'undefined'` (SSR/test) renvoie faux : pas de UA à lire.
export function isIosOuStandalone() {
  if (typeof window === 'undefined') return false
  const ua = window.navigator?.userAgent || ''
  const isIos = /iphone|ipad|ipod/i.test(ua)
  const standalone = window.matchMedia?.('(display-mode: standalone)').matches
    || window.navigator?.standalone === true // iOS Safari installé
  return isIos || !!standalone
}

// VX172 — patron `openPdfInGesture` (VX48) généralisé aux exports blob
// (xlsx/csv/json/png…) : sur iOS/standalone, `a.download` télécharge bien le
// fichier mais l'atterrissage est INVISIBLE dans la coquille installée — on
// ouvre donc un onglet vide de façon SYNCHRONE dans le geste de tap (avant tout
// `await`), pour ensuite le rediriger vers le blob une fois prêt (`deliver`) :
// un onglet Safari réel avec le fichier, partageable via le bouton Partager.
// Ailleurs (desktop, Android, Safari mobile hors coquille), `a.download`
// suffit et reste inchangé — repli automatique si la fenêtre pré-ouverte a
// été bloquée/fermée entre-temps.
//
// Usage — appeler en tout DÉBUT de handler (avant le premier `await`) :
//   const pending = downloadBlobInGesture()
//   const res = await api.export(...)
//   pending.deliver(res.data, 'export.xlsx')
export function downloadBlobInGesture() {
  const useTab = isIosOuStandalone()
  const win = useTab ? window.open('', '_blank', 'noopener') : null
  return {
    win,
    deliver(blob, filename) {
      if (!useTab) { downloadBlob(blob, filename); return true }
      if (!win || win.closed) { downloadBlob(blob, filename); return false }
      try {
        const url = URL.createObjectURL(blob)
        setTimeout(() => URL.revokeObjectURL(url), 60000)
        win.location = url
        if (filename) { try { win.document.title = filename } catch { /* cross-origin-safe no-op */ } }
        return true
      } catch {
        downloadBlob(blob, filename)
        return false
      }
    },
  }
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
