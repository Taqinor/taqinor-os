// Logique PURE de l'aperçu PDF du panneau devis (fiche lead), isolée ici pour
// être testable sans DOM. C'est le coeur de la régression « aperçu cassé » :
//   1. proposalParams() construit les query params /proposal selon le format
//      choisi (Premium « full » / « onepage », +Inclure l'étude) ;
//   2. pdfBlob() emballe les octets reçus en Blob application/pdf — c'est ce
//      Blob qui, via URL.createObjectURL, alimente l'iframe d'aperçu ET le
//      téléchargement (même source, donc aperçu et PDF téléchargé concordent).
// Pointer l'iframe directement sur l'URL /proposal (ancien code) ne rejouait
// pas le refresh silencieux du token -> 401 -> icône « fichier cassé ».

export const PDF_MIME = 'application/pdf'

// Params attendus par GET /ventes/devis/<id>/proposal/ (whitelist serveur).
// include_etude n'est pertinent qu'en Premium ; en 1 page on l'omet (0).
export function proposalParams(pdfMode, includeEtude) {
  const mode = pdfMode === 'onepage' ? 'onepage' : 'full'
  return {
    pdf_mode: mode,
    include_etude: mode === 'full' && includeEtude ? 1 : 0,
  }
}

// Emballe les octets bruts (ArrayBuffer / Blob / typed array renvoyé par axios
// en responseType:'blob') en Blob typé application/pdf, prêt pour
// URL.createObjectURL — l'iframe l'affiche alors comme un vrai PDF.
export function pdfBlob(data) {
  return new Blob([data], { type: PDF_MIME })
}

// ── États d'affichage de la zone d'aperçu ────────────────────────────────────
// Un SEUL endroit décide ce que la zone montre, pour que le test couvre la VRAIE
// logique utilisée par le composant (pas une copie).
export const PREVIEW_VIEW = {
  LOADING: 'loading', // récupération en cours
  PDF: 'pdf', // l'iframe affiche le PDF
  FALLBACK: 'fallback', // aperçu bloqué/indisponible -> repli avec actions
  ERROR: 'error', // le serveur n'a PAS pu générer le PDF (4xx/5xx)
}

// Décide la vue à partir d'indicateurs simples.
//  - serverError : vrai échec de génération côté serveur -> message clair.
//  - blocked     : embed bloqué (bloqueur de pub / timeout de rendu) OU échec
//                  réseau du fetch -> repli gracieux (télécharger / nouvel
//                  onglet / réessayer). JAMAIS un cadre d'erreur brut.
export function previewView({ loading, serverError, blocked, hasUrl }) {
  if (serverError) return PREVIEW_VIEW.ERROR
  if (blocked) return PREVIEW_VIEW.FALLBACK
  if (loading || !hasUrl) return PREVIEW_VIEW.LOADING
  return PREVIEW_VIEW.PDF
}

// Classe un échec de récupération du PDF : le serveur a-t-il répondu en erreur
// (4xx/5xx -> vrai échec de génération, on explique) ou est-ce un problème
// réseau / timeout / connexion coupée (-> repli gracieux téléchargeable) ?
// axios : une réponse HTTP d'erreur porte err.response ; un échec réseau n'en a
// pas (err.request seul, ou code ECONNABORTED pour un timeout).
export function classifyFetchError(err) {
  return err && err.response ? 'server' : 'network'
}
