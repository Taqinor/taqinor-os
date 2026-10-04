/* SPL292 — racine partagée de la façade `calepinageApi.js` et de ses fragments
   (`api/calepinage/*.js`). Déplacée telle quelle (move only) depuis la façade. */

// Racine du pivot. Écrite UNE fois : toute action ci-dessous s'y accroche, ce
// qui rend une seconde forme d'URL mécaniquement impossible.
export const pivot = (id) => `/calepinage/calepinages/${id}/`
