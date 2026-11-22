import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PVGIS_LIVE_LOSS_PCT } from '@rooflib/systemLoss'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatDate, formatNumber, formatPercent } from '../../../lib/format'
import { PARAM_ONGLET } from '../atelier/onglets'
import { estProfilDepart, MENTION_PUBLIEE } from '../reglages/profilDepart'
import { estIncomplet } from './BandeauProvenanceProduction.helpers'
import Pourquoi from '../commun/Pourquoi'

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

/* ACAL894 — PVGIS n'est nommé que s'il a répondu pour la carte (attribut
   `data-source-prod` de `#rp9-reco-why`, posé par `optimizer.ts::paintCard`) ;
   la perte citée est la constante réellement passée au service, importée. */
const MENTION_PVGIS = `Estimation rapide (PVGIS PVcalc, pertes forfaitaires ${PVGIS_LIVE_LOSS_PCT} %)`
const MENTION_ATELIER = "Estimation rapide de l'atelier — avant la simulation"
const pvgisARepondu = (source) => /PVGIS/.test(source || '') && !/indisponible|table/i.test(source || '')

function useSourceCarte() {
  const lire = () => document.getElementById('rp9-reco-why')?.dataset?.sourceProd ?? ''
  const [source, setSource] = useState(lire)
  useEffect(() => {
    const obs = new MutationObserver(() => setSource(lire()))
    obs.observe(document.body, { subtree: true, childList: true, attributeFilter: ['data-source-prod'] })
    return () => obs.disconnect()
  }, [])
  return source
}

export default function BandeauProvenanceProduction({ calepinageId, chiffrage = null }) {
  const source = useSourceCarte()
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
    <p className="mt-2 text-xs text-foreground" data-testid="calx65-bandeau">
      <span data-testid="calx65-rapide">{pvgisARepondu(source) ? MENTION_PVGIS : MENTION_ATELIER}</span>
      {aSimulation && (
        <span data-testid="calx65-simulation">
          {' — Simulation : P50 '}
          {formatNumber(p50, { decimals: 0 })}
          {' kWh/an, chaîne de pertes du '}
          {data?.calcule_le ? formatDate(data.calcule_le) : 'date non publiée'}
          {' — '}
          <Link
            to={`/calepinage/${calepinageId}?${PARAM_ONGLET}=production`}
            className="text-primary-text underline"
            data-testid="calx65-lien-production"
          >
            voir la Production
          </Link>
        </span>
      )}
      <EcartDevis ecart={data?.ecart_devis} />
      <DevisAnnonce chiffrage={chiffrage} p50={aSimulation ? p50 : null} />
    </p>
  )
}

/* ACAL995 — ce que le devis ANNONCERA (`chiffrage` de design-context, ACAL993,
   reçu de l'atelier qui l'a déjà lu : jamais un second appel), SEULEMENT quand
   il n'imprime pas la pose réelle (« standard ville ») ; non chiffré ⇒ le motif
   servi. Écart = (simulation − devis) ÷ devis, à l'affichage. */
function DevisAnnonce({ chiffrage, p50 }) {
  const prod = chiffrage?.production_annuelle_kwh
  if (!prod) return null
  if (prod.etat === 'non_servi' || prod.etat === 'indisponible') {
    const motif = chiffrage.omissions?.find((o) => o.grandeur === 'production_annuelle_kwh')?.motif
    return <span className="block" data-testid="acal995-devis-annonce">{`Le devis n’est pas encore chiffré : ${motif || 'motif non publié'}`}</span>
  }
  if (prod.etat !== 'servi' || prod.source !== 'standard_ville' || !prod.valeur) return null
  const ecart = typeof p50 === 'number' ? ((p50 - prod.valeur) / prod.valeur) * 100 : null
  return (
    <span className="block" data-testid="acal995-devis-annonce">
      {`Le devis annonce : ${formatNumber(prod.valeur, { decimals: 0 })} kWh/an — production standard de la ville`}
      {ecart !== null && ` (étude technique : ${ecart < 0 ? '−' : '+'}${formatNumber(Math.abs(ecart), { decimals: 1 })} %)`}
    </span>
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

/* ACAL980 — « Ce qui est supposé » : les replis cachés du moteur (`suppose[]` de
   `GET resultat/`, contrat `calepinage_resultat.json`), chacun avec sa valeur et
   le champ à renseigner. Rien n'est calculé ici ; liste vide ou absente ⇒ rien. */
export function Suppose({ suppose }) {
  if (!Array.isArray(suppose) || suppose.length === 0) return null
  return (
    <div className="text-sm" data-testid="acal980-suppose">
      <p className="text-xs font-medium text-muted-foreground">Ce qui est supposé</p>
      <ul className="list-disc pl-5 text-xs">
        {suppose.map((repli) => (
          <li key={repli.code} data-testid={`acal980-${repli.code}`}>
            {repli.libelle}
            <span className="block text-muted-foreground">{`À renseigner : ${repli.champ}`}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/* ACAL854 — l'écart à PVGIS que la simulation calcule déjà (`validation`,
   `services/validation.py::ecart_vs_pvcalc`) : la valeur servie, une décimale,
   signée. Aucun seuil ici : sans tolérance réglée par la société, pas de verdict. */
export function EcartPvgis({ validation }) {
  const pct = validation?.ecart_pct
  if (typeof pct !== 'number') return null
  const signe = pct < 0 ? '−' : (pct > 0 ? '+' : '')
  const sansVerdict = validation.tolerance_pct == null && validation.verdict == null
  return (
    <p className="text-sm text-muted-foreground" data-testid="acal854-ecart-pvgis">
      {'Comparé à PVGIS au même endroit : '}{signe}{formatNumber(Math.abs(pct), { decimals: 1 })}{' %'}
      <Pourquoi cle="production.ecart_pvgis" valeurs={{ validation }} />{/* ACAL873 */}
      {sansVerdict && (
        <span className="block text-xs" data-testid="acal854-sans-verdict">
          {'écart publié sans verdict — la tolérance n\'est pas réglée ('}
          <Link to="/calepinage/reglages#calx69-tolerance_validation_pct" className="text-primary-text underline"
            data-testid="acal854-lien-tolerance">régler la tolérance</Link>{')'}
        </span>
      )}
      <VoyantPvgis validation={validation} />
    </p>
  )
}

/* ACAL855 — le voyant affiche le `verdict` SERVI et la tolérance de la société ;
   il ne décide d'aucun seuil. */
function VoyantPvgis({ validation }) {
  const { verdict, tolerance_pct: tol, avertissement } = validation
  if (verdict !== 'dans_la_tolerance' && verdict !== 'hors_tolerance') return null
  const tolerance = `±${formatNumber(tol, { decimals: Number.isInteger(tol) ? 0 : 1 })} %`
  if (verdict === 'dans_la_tolerance') {
    return (
      <span className="mt-1 block w-fit rounded bg-success/10 px-2 py-1 text-xs text-success-text"
        data-testid="acal855-voyant" data-verdict="vert">
        {`Dans la tolérance de ${tolerance} réglée par votre société`}
      </span>
    )
  }
  return (
    <span className="mt-1 block w-fit rounded border border-warning/40 bg-warning/10 px-2 py-1 text-xs text-warning"
      data-testid="acal855-voyant" data-verdict="orange">
      {`Hors de la tolérance de ${tolerance} : vérifiez les pertes et la météo `}
      <Link to={`?${PARAM_ONGLET}=pertes`} className="underline" data-testid="acal855-lien-pertes">voir les pertes</Link>
      {avertissement && <span className="block" data-testid="acal855-avertissement">{avertissement}</span>}
    </span>
  )
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
        to="/calepinage/reglages#calx69-section-simulation"
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
    clé, valeur, source — tels que le serveur les a gravés. ACAL698 : `ouvert`
    (facultatif) est piloté par `LigneValeursPubliees` ; absent = comportement
    d'origine (`<details>` non contrôlé). */
export function ReglagesUtilises({ simulation, ouvert, onBascule }) {
  const reglages = simulation?.reglages_utilises
  const cles = reglages && typeof reglages === 'object' ? Object.keys(reglages) : []
  if (cles.length === 0) return null
  return (
    <details
      className="text-sm"
      data-testid="acal52-reglages-utilises"
      open={ouvert === undefined ? undefined : ouvert}
      onToggle={onBascule ? (e) => onBascule(e.currentTarget.open) : undefined}
    >
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
                {estProfilDepart(reglages[cle]?.reference) && (
                  <span className="block text-muted-foreground" data-testid="acal405-publiee">
                    {MENTION_PUBLIEE}
                  </span>
                )}
              </td>
              <td className="py-1">{texteReglage(reglages[cle]?.source)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}

/* ============================================================================
   ENF15 — LA SOURCE MÉTÉO ET L'INCERTITUDE, TELLES QUE SERVIES.
   ----------------------------------------------------------------------------
   `GET resultat/` publie `meteo` (contrat `calepinage_meteo.json`, CALX143) et
   `incertitude` (contrat `calepinage_incertitude.json`, CALX144) depuis CALX70,
   mais aucun écran ne les lisait : le P90 s'affichait sans dire de quoi son σ
   est fait ni de quelle base météo il sort. AUCUN CALCUL ICI : chaque valeur
   est affichée telle que servie ; `null` ⇒ « non publié », jamais un zéro.
   ========================================================================== */
const nonPublie = (v) => (v === null || v === undefined || v === '' ? 'non publié' : String(v))

/** Le bloc `meteo` : service, bases, fenêtre, horizon, fuseau, date d'obtention. */
/** ACAL745 — « Deuxième source météo » : l'écart annuel servi entre deux bases
    (`meteo.comparaison_base`), son motif quand il est `null`, et le détail
    mensuel replié. Aucun verdict, aucune couleur : les valeurs telles que
    servies. Clé absente : rien. */
export function EcartBases({ comparaison }) {
  if (!comparaison || typeof comparaison !== 'object') return null
  const ecart = comparaison.ecart_pct
  const mois = Array.isArray(comparaison.mensuel) ? comparaison.mensuel : []
  if (ecart === null || ecart === undefined) {
    return (
      <p className="text-sm" data-testid="acal745-ecart">
        {`Deuxième source météo non comparée : ${comparaison.motif || 'motif non publié'}`}
      </p>
    )
  }
  return (
    <div className="text-sm" data-testid="acal745-ecart">
      <p>
        {`Deuxième source météo (${comparaison.base_comparee}) : ${formatPercent(ecart, { decimals: 1 })} `
          + `de rayonnement par an par rapport à ${comparaison.base_principale}`}
      </p>
      {mois.length > 0 && (
        <details data-testid="acal745-mensuel">
          <summary className="min-h-11 cursor-pointer text-sm">Mois par mois</summary>
          <ul className="text-sm">
            {mois.map((m) => (
              <li key={m.mois} data-testid={`acal745-mois-${m.mois}`}>
                {`Mois ${m.mois} : ${formatPercent(m.ecart_pct, { decimals: 1 })}`}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

export function SourceMeteo({ meteo }) {
  if (!meteo?.service) return null
  const horizon = meteo.horizon?.origine
    ? `${meteo.horizon.origine}${meteo.horizon.base_horizon ? ` (${meteo.horizon.base_horizon})` : ''}`
    : null
  const obtenue = meteo.obtenue_le
    ? `${formatDate(meteo.obtenue_le)}${meteo.depuis_cache ? ' (depuis le cache)' : ''}`
    : null
  const lignes = [
    ['Service PVGIS', meteo.service],
    ['Base de rayonnement', meteo.base_rayonnement],
    ['Base météo', meteo.base_meteo],
    ['Mode', meteo.mode],
    ['Fenêtre', meteo.fenetre_annees],
    ['Horizon', horizon],
    ['Fuseau du site', meteo.heure?.fuseau_site],
    ['Obtenue le', obtenue],
  ]
  return (
    <>
    <details className="text-sm" data-testid="enf15-source-meteo">
      <summary className="cursor-pointer text-xs font-medium text-muted-foreground">Source météo</summary>
      <dl className="mt-1 grid grid-cols-2 gap-x-3 text-xs">
        {lignes.map(([libelle, valeur]) => (
          <div key={libelle} className="contents">
            <dt className="text-muted-foreground">{libelle}</dt>
            <dd data-testid="enf15-meteo-valeur">{nonPublie(valeur)}</dd>
          </div>
        ))}
      </dl>
    </details>
    <EcartBases comparaison={meteo.comparaison_base} />
    </>
  )
}

/** Le bloc `incertitude` : composantes sourcées, σ composé, ou le refus nommé. */
export function IncertitudeSigma({ incertitude }) {
  if (!incertitude) return null
  const composantes = Array.isArray(incertitude.composantes) ? incertitude.composantes : []
  const sigma = incertitude.sigma_total
  return (
    <details className="text-sm" data-testid="enf15-incertitude">
      <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
        {'Incertitude (σ) : '}
        {sigma === null || sigma === undefined ? 'non composée' : formatPercent(sigma * 100, { decimals: 2 })}
        {incertitude.methode ? ` · ${incertitude.methode}` : ''}
        {incertitude.portee ? ` · portée ${incertitude.portee}` : ''}
      </summary>
      {incertitude.motif_refus && (
        <p className="mt-1 text-xs text-warning" data-testid="enf15-incertitude-refus">{incertitude.motif_refus}</p>
      )}
      {composantes.length > 0 && (
        <table className="mt-1 w-full text-xs">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th className="py-1 font-normal">Composante</th>
              <th className="py-1 text-right font-normal">σ</th>
              <th className="py-1 font-normal">Source</th>
              <th className="py-1 font-normal">Référence</th>
            </tr>
          </thead>
          <tbody>
            {composantes.map((c) => (
              <tr key={c.nom} className="border-t border-border/60" data-testid="enf15-composante">
                <td className="py-1">{c.nom}</td>
                <td className="py-1 text-right tabular-nums">
                  {formatPercent(c.sigma_relatif * 100, { decimals: 1 })}
                </td>
                <td className="py-1">{nonPublie(c.source)}</td>
                <td className="py-1">{nonPublie(c.reference)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </details>
  )
}
