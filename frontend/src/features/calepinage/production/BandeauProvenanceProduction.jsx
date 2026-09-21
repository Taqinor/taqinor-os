import { Link } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatDate, formatNumber } from '../../../lib/format'
import { PARAM_ONGLET } from '../atelier/onglets'

/* ============================================================================
   CALX65 — DIRE, DANS L'ATELIER, LAQUELLE DES DEUX PRODUCTIONS PARLE.
   ----------------------------------------------------------------------------
   Constat : `apps/web/src/lib/roofEstimate.ts:16-21` passe `loss=20` à PVGIS
   `PVcalc` pour la carte « Recommandation » du constructeur (`optimizer.ts`,
   `paintCard`, décision D4 — ce paramètre reste TEL QUEL, ce bandeau ne le
   modifie JAMAIS et ne touche AUCUNE ligne de cette carte). Après CALX5 le
   panneau Production publie un P50 issu de la chaîne de pertes RÉELLE : rien
   ne disait pourquoi les deux nombres diffèrent. Parité OpenSolar, qui NOMME
   le calculateur derrière chaque résultat affiché (PVWatts ou SAM) :
   https://support.opensolar.com/hc/en-us/articles/4410730225177.

   AUCUN CALCUL ICI. `p50_kwh` et `calcule_le` viennent tels quels de
   `GET resultat/` (CALX70, contrat `calepinage_resultat.json`) ; la mention
   « pertes forfaitaires 20 % » est un TEXTE FIXE qui décrit le paramètre
   `loss=20` de la carte du constructeur (D4), jamais une valeur relue dessus.

   SANS SIMULATION, UNE SEULE MENTION (Done). Le bandeau n'affirme jamais
   qu'une simulation existe là où `production.total.p50_kwh` vaut `null` — ce
   qui couvre AUSSI le cas périmé (CALX70 : `production` publiée `null` en
   entier tant que le document a changé depuis le dernier calcul).
   ========================================================================== */

const MENTION_RAPIDE = 'Estimation rapide (PVGIS PVcalc, pertes forfaitaires 20 %)'

export default function BandeauProvenanceProduction({ calepinageId }) {
  const { data } = useResource(
    () => calepinageApi.calepinages.resultat(calepinageId), calepinageId,
    {
      select: (r) => r.data,
      errorMessage: 'Provenance de la production indisponible.',
      enabled: Boolean(calepinageId),
    },
  )

  const p50 = data?.production?.total?.p50_kwh
  const aSimulation = p50 !== null && p50 !== undefined

  return (
    <p className="mt-2 text-xs text-lune-soft" data-testid="calx65-bandeau">
      <span data-testid="calx65-rapide">{MENTION_RAPIDE}</span>
      {aSimulation && (
        <span data-testid="calx65-simulation">
          {' — Simulation : P50 '}
          {formatNumber(p50, { decimals: 0 })}
          {' kWh/an, chaîne de pertes du '}
          {data?.calcule_le ? formatDate(data.calcule_le) : 'date non publiée'}
          {' — '}
          <Link
            to={`/calepinage/${calepinageId}?${PARAM_ONGLET}=production`}
            className="text-brass-300 underline"
            data-testid="calx65-lien-production"
          >
            voir la Production
          </Link>
        </span>
      )}
    </p>
  )
}
