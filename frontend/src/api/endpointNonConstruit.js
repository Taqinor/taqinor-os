/* ============================================================================
   Un endpoint que le backend n'a PAS construit doit le DIRE.
   ----------------------------------------------------------------------------
   Constat de production du 03/08/2026 (module Appels d'offres) : neuf chemins
   appelés par le client API n'existaient sous aucune route. Le symptôme était
   toujours le même — un 404 anonyme, un écran qui affiche « une erreur est
   survenue », et personne pour deviner que la cause est un endpoint absent.
   C'est ainsi que l'écran Bibliothèque a tenu jusqu'en production.

   `endpointNonConstruit(chemin, raison)` fabrique une fonction d'appel qui :
     * n'émet AUCUNE requête (pas de 404 fantôme dans le journal serveur) ;
     * rejette au FORMAT D'ERREUR AXIOS (`response.data.detail`), le champ que
       tous les écrans lisent déjà — la raison exacte s'affiche donc sans
       modifier un seul composant ;
     * porte un 501 « non implémenté », qui est la vérité.
   ========================================================================== */

export function endpointNonConstruit(chemin, raison) {
  return function appelImpossible() {
    const detail = `Endpoint non construit — ${chemin} : ${raison}`
    return Promise.reject(Object.assign(new Error(detail), {
      response: { status: 501, data: { detail } },
    }))
  }
}

export default endpointNonConstruit
