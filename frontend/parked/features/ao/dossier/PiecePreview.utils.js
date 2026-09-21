/* AOF175 — helper partagé de la prévisualisation de pièce.
   Extrait de PiecePreview.jsx (react-refresh/only-export-components : un
   fichier de composant ne doit exporter QUE des composants).

   **UN SEUL WORKER pdfjs pour toute l'application.** `GlobalWorkerOptions` est
   un SINGLETON de la bibliothèque : le premier module qui pose le port gagne,
   tous les autres le réutilisent. `ensureWorkerPartage()` n'ouvre donc un
   worker QUE si personne (underlay de calepinage, `PdfCanvas`) ne l'a déjà
   fait, et mémoïse sa promesse — deux volets côte à côte en mode comparaison
   n'en ouvrent pas deux. L'import du worker est DYNAMIQUE et n'est évalué que
   dans ce cas : rien à charger quand le port existe déjà. */
import * as pdfjsLib from 'pdfjs-dist'

// Promesse mémoïsée : un worker au plus pour toute la durée de vie de l'onglet.
let workerPromise = null

/** Garantit UN worker pdfjs partagé. Renvoie `true` si CE module l'a posé,
    `false` s'il était déjà posé ailleurs (cas nominal quand l'underlay ou
    `PdfCanvas` a été monté avant). Servi depuis NOTRE origine (Vite `?worker`),
    jamais un CDN blocable. */
export function ensureWorkerPartage(lib = pdfjsLib) {
  const opts = lib.GlobalWorkerOptions
  if (opts.workerPort || opts.workerSrc) return Promise.resolve(false)
  if (!workerPromise) {
    workerPromise = import('pdfjs-dist/build/pdf.worker.min.mjs?worker')
      .then(({ default: PdfWorker }) => {
        if (!opts.workerPort && !opts.workerSrc) opts.workerPort = new PdfWorker()
        return true
      })
  }
  return workerPromise
}
