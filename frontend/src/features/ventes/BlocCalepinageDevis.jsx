import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ventesApi from '../../api/ventesApi'

/* ============================================================================
   CAL40 — LE CALEPINAGE QUI PILOTE CE DEVIS, sur la fiche devis.
   ----------------------------------------------------------------------------
   CONSTAT : le lien n'était visible dans AUCUN sens. Un commercial ouvrant un
   devis ne savait pas quel calepinage l'a produit — alors que c'est LUI qui
   porte les versions, les variantes et la planche.

   LE BADGE EST CALCULÉ PAR LE SERVEUR, JAMAIS ICI. `a_jour` vient de
   `apps.ventes.selectors.calepinage_du_devis` (CAL28), qui COMPARE LES DEUX
   EMPREINTES (`layout_hash` du devis et du calepinage) — jamais un recalcul de
   géométrie à l'écran, exactement comme `layout_stale` sur la page client.
   Ses TROIS états sont rendus tels quels :
     * `true`  → « à jour » ;
     * `false` → « à rejouer » ;
     * `null`  → INCONNU (une empreinte manque d'un côté) — on n'affiche alors
       AUCUN badge. Déclarer « à rejouer » ce qu'on n'a pas mesuré serait une
       alerte inventée, et c'est précisément ce que le sélecteur refuse de
       faire côté serveur.

   DISCIPLINE DU NULL (patron CAL213 `CalepinageRetenuCard`) : pas de
   calepinage ⇒ le bloc DISPARAÎT. Jamais un bloc vide, jamais un tiret qui
   laisserait croire à une donnée manquante.

   ÉTAT DU SERVEUR AU MOMENT DE CETTE LANE, à dire et non à cacher :
   `calepinage_du_devis` est un SÉLECTEUR Python (CAL28) qui n'est encore
   publié par AUCUN serializer. La clé `calepinage` du détail devis est donc
   absente aujourd'hui, et ce bloc reste invisible — exactement son
   comportement « aucun calepinage ». Il s'allumera le jour où le détail la
   publiera, sans qu'une ligne d'écran ne change.
   ========================================================================== */

export default function BlocCalepinageDevis({ devisId }) {
  const [calepinage, setCalepinage] = useState(null)

  useEffect(() => {
    if (!devisId) return undefined
    let vivant = true
    Promise.resolve(ventesApi.getDevisById(devisId))
      .then((r) => { if (vivant) setCalepinage(r?.data?.calepinage ?? null) })
      .catch(() => { if (vivant) setCalepinage(null) })
    return () => { vivant = false }
  }, [devisId])

  if (!calepinage?.id) return null

  const aJour = calepinage.a_jour

  return (
    <div className="border-t border-border pt-4" data-testid="cal-bloc-calepinage-devis">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-semibold text-foreground">
          Calepinage de ce devis
        </p>
        {/* Le badge n'apparaît QUE si le serveur a tranché (true/false). */}
        {aJour === true && (
          <span className="text-sm font-medium text-emerald-600"
            data-testid="cal-badge-a-jour">à jour</span>
        )}
        {aJour === false && (
          <span className="text-sm font-medium text-destructive"
            data-testid="cal-badge-a-rejouer">à rejouer</span>
        )}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        {calepinage.titre || 'Calepinage sans titre'}
      </p>
      <Link
        to={`/calepinage/${calepinage.id}`}
        className="mt-1 inline-block text-sm font-medium underline-offset-4 hover:underline"
      >
        Ouvrir le calepinage
      </Link>
    </div>
  )
}
