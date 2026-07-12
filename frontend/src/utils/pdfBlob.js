// VX49 — import PARESSEUX du toast : `ui/Toaster` tire `sonner` (dépendance
// externe + JSX), indésirable dans un module utilitaire testé en `node --test`
// SANS bundler ni node_modules. Le dynamic import échoue proprement (catch) en
// environnement de test — le helper reste 100% fonctionnel sans le toast.
async function toastErreur(message, options) {
  try {
    const { toast } = await import('../ui/Toaster')
    toast.error(message, options)
  } catch { /* pas d'UI de toast disponible (test / SSR) — silencieux */ }
}

// VX172 — import PARESSEUX (même contrainte node --test/SSR que le toast
// ci-dessus) : `isIosOuStandalone` décide si `openPdfBlob` doit éviter la
// combinaison `download`+`_blank` (fragile dans les mêmes conditions iOS
// standalone que les exports blob — cf. downloadBlob.js).
async function iosOuStandalone() {
  try {
    const { isIosOuStandalone } = await import('./downloadBlob.js')
    return isIosOuStandalone()
  } catch { return false }
}

// VX49 — Safari renvoie parfois un objet fenêtre non-null mais INERTE (popup
// silencieusement bloquée) : `win.closed` vaut déjà `true`, ou `win.closed`
// n'est même pas défini sur l'objet renvoyé. Un simple `if (win)` rate ce cas.
function isFenetreInerte(win) {
  return win == null || win.closed || typeof win.closed === 'undefined'
}

// QS1 — ouvre un PDF (Blob) dans un NOUVEL ONGLET (window.open) ; si le
// navigateur bloque la popup (détection VX49 : null OU fenêtre inerte),
// affiche un toast d'action « Ouverture bloquée — Télécharger le PDF » au
// lieu d'échouer en silence, ET retombe sur le téléchargement `openPdfBlob`.
// Retourne 'open' | 'download' (utile aux tests).
export function ouvrirPdfBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const win = window.open(url, '_blank', 'noopener')
  setTimeout(() => URL.revokeObjectURL(url), 60000)
  if (!isFenetreInerte(win)) return 'open'
  openPdfBlob(blob, filename)
  toastErreur('Ouverture bloquée — Télécharger le PDF', {
    action: { label: 'Télécharger', onClick: () => openPdfBlob(blob, filename) },
  })
  return 'download'
}

// VX48 — [BUG iOS] Safari iOS bloque en silence tout `window.open()` qui suit
// un `await` : le PDF n'apparaît jamais et rien ne le signale. Le seul geste
// que Safari accepte sans blocage est un `window.open` SYNCHRONE, appelé
// directement dans le handler de tap/clic (avant tout `await`).
//
// Usage — appeler dans le handler AVANT l'appel async, puis rediriger la
// fenêtre pré-ouverte quand le blob est prêt :
//
//   const pending = openPdfInGesture()          // synchrone, dans le tap
//   const res = await api.getPdf(id)            // await : OK après coup
//   const ok = pending.deliver(pdfBlob(res.data), filename)
//   if (!ok) toast.error('Ouverture bloquée — Télécharger le PDF', { action... })
//
// `deliver()` redirige l'onglet pré-ouvert vers l'URL du blob ; renvoie
// `false` (et ne fait AUCUN fallback lui-même) si la fenêtre pré-ouverte a été
// bloquée/fermée entre-temps (l'appelant décide alors du repli — toast ou
// téléchargement direct), pour ne jamais régresser QG1.
export function openPdfInGesture() {
  const win = window.open('', '_blank', 'noopener')
  return {
    win,
    deliver(blob, filename) {
      const url = URL.createObjectURL(blob)
      setTimeout(() => URL.revokeObjectURL(url), 60000)
      if (!win || win.closed) return false
      try {
        win.location = url
      } catch {
        return false
      }
      if (filename) {
        try { win.document.title = filename } catch { /* cross-origin-safe no-op */ }
      }
      return true
    },
  }
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
// VX49 — un blob invalide (ou un DOM indisponible) ne doit jamais échouer en
// silence : toast FR + `revokeObjectURL` garanti en `finally` (sinon fuite
// mémoire sur des échecs répétés, ex. blob corrompu retenté en boucle).
// VX172 — `target=_blank` + `download` combinés est fragile dans les mêmes
// conditions iOS/standalone que les exports blob (VX172) : en repli terminal
// (ce chemin d'OUVERTURE seulement — jamais le moteur `/proposal`, règle #4),
// on retire `_blank` en iOS/standalone pour ne garder qu'un `a.download` pur.
export async function openPdfBlob(blob, filename) {
  let url
  try {
    const standalone = await iosOuStandalone()
    url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    if (!standalone) {
      a.target = '_blank'
      a.rel = 'noopener'
    }
    if (filename) a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } catch {
    toastErreur('Fichier indisponible — réessayez.')
  } finally {
    if (url) setTimeout(() => URL.revokeObjectURL(url), 10000)
  }
}
