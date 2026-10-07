/* eslint-disable react-refresh/only-export-components --
   `estIncomplet` est une fonction PURE (un bloc `total` → booléen) que les écrans
   Production / Pertes importent avec les composants du bandeau. */
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
      <EcartDevis ecart={data?.ecart_devis} />
    </p>
  )
}

/* ============================================================================
   ACAL105 (D-ACAL-6) — LA PRODUCTION DU DEVIS ET L'ÉCART, SERVIS PAR LE SERVEUR.
   ----------------------------------------------------------------------------
   `GET resultat/` porte `ecart_devis` (ACAL104, contrat
   `calepinage_resultat.json`) : la production IMPRIMÉE au client (moteur du
   devis) et l'écart au P50 de l'étude. AUCUN calcul ici : les deux nombres
   sont affichés tels que servis ; `null` ⇒ rien.
   ========================================================================== */
function EcartDevis({ ecart }) {
  if (!ecart) return null
  const pct = ecart.ecart_pct
  const signe = typeof pct === 'number' && pct > 0 ? '+' : ''
  return (
    <span className="block" data-testid="acal-ecart-devis">
      {'Devis : '}
      {formatNumber(ecart.production_devis_kwh, { decimals: 0 })}
      {' kWh/an (production imprimée au client)'}
      {pct !== null && pct !== undefined && (
        <>{' — écart '}{signe}{formatNumber(pct, { decimals: 1 })}{' %'}</>
      )}
    </span>
  )
}

/* ============================================================================
   ACAL52 — LA BORNE HAUTE ET LES RÉGLAGES UTILISÉS, DITS SUR L'ÉCRAN.
   ----------------------------------------------------------------------------
   `production.total.complete === false` (ACAL49) veut dire que des postes de
   perte du socle n'ont pas été renseignés : le P50 servi est une BORNE HAUTE.
   Le bandeau reprend la mention SERVIE, la liste `socle_manquant` et le lien
   vers les réglages ; PR / P75 / P90 / P95 s'affichent « — non publié » (motif
   en infobulle), jamais un nombre. Rien n'est recalculé ici : la complétude est
   celle du serveur. `complete === true` : ni bandeau ni masquage.
   ========================================================================== */

/** Résultat simulé mais incomplet : le P50 existe, le socle de pertes non. */
export function estIncomplet(total) {
  return Boolean(total) && total.complete === false
    && total.p50_kwh !== null && total.p50_kwh !== undefined
}

export function BandeauBorneHaute({ total }) {
  if (!estIncomplet(total)) return null
  const manquants = Array.isArray(total.socle_manquant) ? total.socle_manquant : []
  const mention = total.mention
    || `borne haute — ${manquants.length} pertes non renseignées`
  return (
    <div
      className="flex flex-col gap-1 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm"
      role="status"
      data-testid="acal52-borne-haute"
    >
      <p className="font-medium" data-testid="acal52-mention">{mention}</p>
      {manquants.length > 0 && (
        <ul className="list-disc pl-5 text-xs text-muted-foreground" data-testid="acal52-socle-manquant">
          {manquants.map((poste) => <li key={poste}>{poste}</li>)}
        </ul>
      )}
      <Link
        to="/calepinage/reglages"
        className="w-fit text-xs font-medium text-primary underline"
        data-testid="acal52-lien-reglages"
      >
        Ouvrir les réglages de simulation
      </Link>
    </div>
  )
}

function texteReglage(valeur) {
  if (valeur === null || valeur === undefined) return '—'
  if (typeof valeur === 'object') return JSON.stringify(valeur)
  return String(valeur)
}

/** Les réglages FIGÉS au calcul (`simulation.reglages_utilises`, D-ACAL-8) :
    clé, valeur, source — tels que le serveur les a gravés. */
export function ReglagesUtilises({ simulation }) {
  const reglages = simulation?.reglages_utilises
  const cles = reglages && typeof reglages === 'object' ? Object.keys(reglages) : []
  if (cles.length === 0) return null
  return (
    <details className="text-sm" data-testid="acal52-reglages-utilises">
      <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
        Réglages utilisés
      </summary>
      <table className="mt-1 w-full text-xs">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="py-1 font-normal">Réglage</th>
            <th className="py-1 font-normal">Valeur</th>
            <th className="py-1 font-normal">Source</th>
          </tr>
        </thead>
        <tbody>
          {cles.map((cle) => (
            <tr key={cle} className="border-t border-border/60" data-testid="acal52-reglage">
              <td className="py-1">{cle}</td>
              <td className="py-1 tabular-nums" title={reglages[cle]?.reference || undefined}>
                {texteReglage(reglages[cle]?.valeur)}
              </td>
              <td className="py-1">{texteReglage(reglages[cle]?.source)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}
