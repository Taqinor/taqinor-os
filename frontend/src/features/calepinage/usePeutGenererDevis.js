import useDroitMetier from '../sav/useDroitMetier'

/* D-ACAL-106 — LE droit de « générer le devis » d'un calepinage, lu UNE fois pour tous les endroits qui le proposent (bandeau
   de l'atelier, `BoutonDevis` des étapes Documents et Expert, note de la colonne Documents, vue client).
   Le code est celui que le serveur vérifie sur la route `generer-devis` : `PeutGererCalepinage` (`calepinage_gerer`,
   apps/calepinage/permissions.py), avec le même repli « code, sinon palier » (`_user_has_or_legacy` ≡ `useDroitMetier`).
   Le Technicien (`calepinage_voir` + `calepinage_releve`, jamais `calepinage_gerer`, permissions_registre.py) est refusé
   par CETTE garde — c'est le 403 que le rejeu a vu. Sans Provider (rendu isolé) tout reste visible : le serveur juge. */
export default function usePeutGenererDevis() {
  return useDroitMetier('calepinage_gerer')
}
