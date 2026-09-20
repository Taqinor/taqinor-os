/* eslint-disable react-refresh/only-export-components --
   `estPerime` est une fonction PURE (un `layout_stale` du contrat → un
   booléen strict) : le test jumeau l'exerce directement, sans monter React —
   même dérogation que `RemplissageProuve.jsx` (CAL79) du même module. */

/* ============================================================================
   CAL188 — LE BADGE « CALEPINAGE PÉRIMÉ » DANS L'ERP (parité PVUNI).
   ----------------------------------------------------------------------------
   Constat de la tâche : la péremption est calculée CÔTÉ SERVEUR et rendue au
   CLIENT (`builder.py` `layout_stale`, bloc `#roof3d-stale` de la page
   publique, CAL189) — mais aucun écran ERP ne l'affichait : le commercial
   apprenait le décalage par la page de SON client, jamais avant.

   LU DU MÊME CHAMP SERVEUR, JAMAIS RECALCULÉ ICI. `layoutStale` vient soit
   du détail devis (`apps.ventes.serializers`, CAL189), soit de la liste/du
   détail calepinage (`CalepinageSerializer`/`detail_calepinage`, CAL189/
   CAL188) — TOUS lisent `apps.ventes.selectors.peremption_layout_devis`, le
   MÊME calcul que la page client. Ce composant ne compare rien : il AFFICHE.

   TROIS ÉTATS, RENDUS TELS QUELS (discipline « zéro chiffre inventé ») :
     * `true`  → le badge « Calepinage périmé » ;
     * `false` → RIEN (à jour n'est pas une alerte) ;
     * `null`  → RIEN (INCONNU — sans devis, il n'y a rien à comparer ; un
       badge affiché sur un `null` afficherait « périmé » là où le serveur
       n'a rien pu mesurer).
   ========================================================================== */

/**
 * `true` UNIQUEMENT si le serveur a AFFIRMÉ la péremption — jamais sur
 * `null`/`undefined`/toute autre valeur que le booléen `true` strict.
 */
export function estPerime(layoutStale) {
  return layoutStale === true
}

export default function BadgePerime({ layoutStale, layoutNbPanneaux = null }) {
  if (!estPerime(layoutStale)) return null

  return (
    <span
      data-testid="cal-badge-perime"
      title={
        layoutNbPanneaux != null
          ? `Cette vue 3D a été étudiée pour ${layoutNbPanneaux} panneau(x) : `
            + 'les chiffres du devis ne correspondent plus à cette conception.'
          : 'Les chiffres du devis ne correspondent plus à cette conception.'
      }
      className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-xs font-semibold text-amber-300"
    >
      Calepinage périmé
    </span>
  )
}
