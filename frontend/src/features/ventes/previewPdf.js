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
