import { useState } from 'react'
import { formatNumber } from '../../../lib/format'
import { lectureMensuelle } from './GraphiqueMensuel.helpers'

/* LA RANGÉE DE QUATRE TUILES de l'étape Résultats (maquette v2 Resultats.dc.html) :
   « Production la première année » (héros bleu nuit à mini-barres mensuelles), « De la consommation » (anneau),
   « Pertes au total » et « Écart avec PVGIS » (réglettes). Aucun calcul : chaque tuile lit une valeur SERVIE
   (`production.total`, `production.mensuel`, `autoconsommation.taux_couverture`, `cascade.plages.total`,
   `validation`) et n'existe que si cette valeur l'est — jamais un 0 ni un tiret à sa place. Les phrases sous les
   chiffres ne se disent que si leur fait est servi (portée « année moyenne », verdict de la plage, verdict de la
   tolérance). Les anneaux, réglettes et mini-barres ne sont que la GÉOMÉTRIE de la valeur servie (un rapport à
   une échelle), jamais un second chiffre. */

const nombre = (v) => typeof v === 'number' && Number.isFinite(v)
const borne = (v, min = 0, max = 100) => Math.max(min, Math.min(max, v))

/* ACAL1833 — UN GRAND CHIFFRE (maquettes v2 : Archivo 700, unité plus petite et grise sur la même ligne de base).
   L'espace des milliers de `formatNumber` est une espace fine insécable (U+202F) que la police ne dessine pas à
   cette taille : chaque groupe est séparé par un <span> qui lui donne une largeur propre — « 12 950 » reste lisible.
   Le texte du nœud garde l'espace insécable (lecteurs d'écran, copier-coller). */
export function GrosChiffre({ valeur, decimals = 0, unite = null, signe = '' }) {
  const groupes = formatNumber(valeur, { decimals }).split(/\s/)
  return (
    <span className="cal-gros">
      <span className="cal-gros-n">
        {signe}
        {groupes.flatMap((g, i) => (i === 0 ? [g] : [<span key={`s${i}`} className="cal-gros-sep">{'\u202f'}</span>, g]))}
      </span>
      {unite && <>{' '}<span className="cal-gros-u">{unite}</span></>}
    </span>
  )
}

/* ACAL1832 — les douze mini-barres du héros : la production mensuelle SERVIE (celle de « Mois par mois »), un mois
   sans valeur n'a pas de barre, le mois le plus fort est plein. Rien si aucun mois n'est servi. */
function MiniBarres({ data }) {
  const { prod } = lectureMensuelle(data)
  const servis = prod.filter((v) => v !== null)
  if (servis.length === 0) return null
  const max = Math.max(...servis)
  const fort = prod.indexOf(max)
  return (
    <div className="cal-res-minibarres" aria-hidden="true" data-testid="cal-res-minibarres">
      {prod.map((v, i) => (
        <span key={i} data-fort={i === fort ? 'oui' : undefined}
          style={{ height: v === null || !(max > 0) ? 0 : `${borne((v / max) * 100)}%` }} />
      ))}
    </div>
  )
}

function Heros({ total, data, nom }) {
  if (!nombre(total?.p50_kwh)) return null
  const moyenne = total?.portee === 'annee_moyenne'
  const parKwc = nombre(total?.specific_yield_kwh_kwc)
    ? `${formatNumber(total.specific_yield_kwh_kwc, { decimals: 0 })} kWh par kWc${moyenne ? ' · année moyenne (P50)' : ''}`
    : null
  return (
    <div className="cal-res-tuile cal-res-heros" data-tuile="heros">
      <span className="cal-res-tuile-label">{nom ?? 'Production la première année'}</span>
      <span className="cal-res-tuile-corps cal-res-heros-corps">
        <span className="cal-res-tuile-valeur"><GrosChiffre valeur={total.p50_kwh} decimals={0} unite="kWh" /></span>
        <MiniBarres data={data} />
      </span>
      {parKwc && <span className="cal-res-tuile-note">{parKwc}</span>}
    </div>
  )
}

const RAYON = 38
const CIRCONFERENCE = 2 * Math.PI * RAYON

function Consommation({ autoconsommation, phraseTailles = null }) {
  const [ouvert, setOuvert] = useState(false)
  const taux = autoconsommation?.taux_couverture
  // ACAL1631 — la part n'est pas servie : la tuile reste, « — » et le MOTIF servi (la phrase de la tuile jumelle
  // `TuileCouverture` à défaut), jamais un 0 % ni une tuile qui disparaît en laissant un trou à droite.
  if (!nombre(taux)) {
    const motif = typeof autoconsommation?.motif_absence === 'string' && autoconsommation.motif_absence
      ? autoconsommation.motif_absence : 'Aucune consommation connue.'
    return (
      <div className="cal-res-tuile" data-tuile="couverture">
        <span className="cal-res-tuile-label">De la consommation</span>
        <span className="cal-res-tuile-corps"><span className="cal-res-tuile-valeur">—</span></span>
        <span className="cal-res-tuile-note">{motif}</span>
      </div>
    )
  }
  // T4-X9-008 — la part servie est celle de la CONCEPTION du lead : à une autre taille que la pose, la phrase la remplace
  // (jamais un pourcentage d'une autre taille à côté de la production simulée de la pose).
  if (phraseTailles) {
    return (
      <div className="cal-res-tuile" data-tuile="couverture">
        <span className="cal-res-tuile-label">De la consommation</span>
        <p className="cal-res-tuile-note">{phraseTailles}</p>
      </div>
    )
  }
  const definition = typeof autoconsommation?.definition === 'string' ? autoconsommation.definition : ''
  const pct = taux * 100
  const arc = CIRCONFERENCE * borne(taux, 0, 1)
  return (
    <div className="cal-res-tuile" data-tuile="couverture">
      <span className="cal-res-tuile-label">De la consommation</span>
      <span className="cal-res-tuile-corps cal-res-tuile-anneau">
        <svg width="92" height="92" viewBox="0 0 92 92" role="img" aria-label={`${formatNumber(pct, { decimals: 0 })} % de la consommation couverte`}>
          <circle cx="46" cy="46" r={RAYON} fill="none" strokeWidth="10" className="cal-res-anneau-piste" />
          <circle cx="46" cy="46" r={RAYON} fill="none" strokeWidth="10" strokeLinecap="round" className="cal-res-anneau-arc"
            strokeDasharray={`${arc} ${CIRCONFERENCE}`} transform="rotate(-90 46 46)" />
        </svg>
        <span className="cal-res-tuile-valeur"><GrosChiffre valeur={pct} decimals={0} unite="%" /></span>
      </span>
      {definition && (
        <>
          <button type="button" className="cal-res-lien" style={{ alignSelf: 'flex-start', minHeight: 0 }}
            aria-expanded={ouvert} onClick={() => setOuvert((o) => !o)}
            data-tuile="pourquoi">
            Pourquoi ce chiffre ?
          </button>
          {ouvert && <p className="cal-res-explication" data-tuile="pourquoi-texte">{definition}</p>}
        </>
      )}
    </div>
  )
}

/* Réglette des pertes : la bande habituelle SERVIE (`plages.total` : min, max) en vert pâle, un repère à la valeur.
   Échelle : de 0 au double de la plus grande des deux grandeurs servies, jamais un chiffre de plus à l'écran. */
function ReglettePertes({ valeur, plage }) {
  if (!nombre(plage?.min) || !nombre(plage?.max)) return null
  const haut = Math.max(plage.max, valeur) * 1.35
  const g = (v) => borne((v / haut) * 100)
  return (
    <span className="cal-res-regle" aria-hidden="true" data-testid="cal-res-regle-pertes">
      <span className="cal-res-regle-plage" style={{ left: `${g(plage.min)}%`, width: `${g(plage.max) - g(plage.min)}%` }} />
      <span className="cal-res-regle-repere" style={{ left: `${g(valeur)}%` }} />
    </span>
  )
}

function Pertes({ total, plages }) {
  if (!nombre(total?.total_loss_pct)) return null
  const statut = plages?.total?.statut
  const phrase = statut === 'dans_la_plage' ? 'Dans la plage habituelle'
    : (plages?.total ? 'Hors de la plage habituelle' : null)
  return (
    <div className="cal-res-tuile" data-tuile="pertes">
      <span className="cal-res-tuile-label">Pertes au total</span>
      <span className="cal-res-tuile-corps">
        <span className="cal-res-tuile-valeur"><GrosChiffre valeur={total.total_loss_pct} decimals={1} unite="%" /></span>
        <ReglettePertes valeur={total.total_loss_pct} plage={plages?.total} />
      </span>
      {phrase && <span className="cal-res-tuile-note" data-ton={statut === 'dans_la_plage' ? 'ok' : 'hors'}>{phrase}</span>}
    </div>
  )
}

/* Réglette de l'écart : repère au centre (= 0), segment bleu du centre à l'écart servi ; échelle ± le double de la
   tolérance servie (à défaut, du double de l'écart). */
function ReglettePvgis({ ecart, tolerance }) {
  const demi = (nombre(tolerance) && tolerance > 0 ? tolerance : Math.abs(ecart) || 1) * 2
  const x = borne(50 + (ecart / demi) * 50)
  return (
    <span className="cal-res-regle" aria-hidden="true" data-testid="cal-res-regle-pvgis">
      <span className="cal-res-regle-zero" />
      <span className="cal-res-regle-ecart" style={{ left: `${Math.min(x, 50)}%`, width: `${Math.abs(x - 50)}%` }} />
    </span>
  )
}

function EcartPvgis({ validation }) {
  const pct = validation?.ecart_pct
  if (!nombre(pct)) return null
  const signe = pct < 0 ? '−' : (pct > 0 ? '+' : '')
  const tol = validation?.tolerance_pct
  const tolerance = nombre(tol) ? `±${formatNumber(tol, { decimals: Number.isInteger(tol) ? 0 : 1 })} %` : null
  // Le bloc `validation` n'est publié que pour le MÊME site et la MÊME puissance crête (validation.py :
  // `_memes_puissances`) : la phrase de la maquette est donc exacte ; un verdict servi s'y ajoute.
  // `pertes_totales.egales` (servi depuis ACAL1606) : le serveur a comparé les pertes système des deux côtés ; seul un
  // « vrai » autorise la mention « à pertes système égales » (jamais affirmée sans cette clé).
  // ACAL1933 — `pertes_totales.omises_vs_pvgis` (servi) : les étapes que PVGIS compte et que notre chaîne a omises faute
  // de donnée, nommées par leur `designation` ; dites ici, jamais déduites.
  const omises = (Array.isArray(validation.pertes_totales?.omises_vs_pvgis) ? validation.pertes_totales.omises_vs_pvgis : [])
    .map((o) => o?.designation).filter((d) => typeof d === 'string' && d)
  const memes = `Même site, mêmes panneaux${validation.pertes_totales?.egales === true ? ', à pertes système égales' : ''}`
    + (omises.length > 0 ? `, sans ${omises.length > 1 ? `${omises.slice(0, -1).join(', ')} ni ${omises[omises.length - 1]}` : omises[0]}, que PVGIS compte` : '')
  let phrase = memes
  if (tolerance && validation.verdict === 'dans_la_tolerance') phrase = `${memes} · dans ±${tolerance.slice(1)}`
  else if (tolerance && validation.verdict === 'hors_tolerance') phrase = `${memes} · hors de ${tolerance}`
  return (
    <div className="cal-res-tuile" data-tuile="ecart-pvgis">
      <span className="cal-res-tuile-label">Écart avec PVGIS</span>
      <span className="cal-res-tuile-corps">
        <span className="cal-res-tuile-valeur">
          <GrosChiffre valeur={Math.abs(pct)} decimals={1} unite="%" signe={signe ? `${signe} ` : ''} />
        </span>
        <ReglettePvgis ecart={pct} tolerance={tol} />
      </span>
      <span className="cal-res-tuile-note">{phrase}</span>
    </div>
  )
}

/** `nomProduction` (relecture E5 M1) : le nom exact de la production du héros quand une AUTRE production est à
    l'écran (la conception) — `null` : le libellé historique. */
export default function TuilesResultat({ data, nomProduction = null, phraseCouverture = null }) {
  return (
    <section className="cal-res-tuiles" data-testid="cal-resultats-tuiles" aria-label="Résultats en un coup d'œil">
      <Heros total={data?.production?.total} data={data} nom={nomProduction} />
      <Consommation autoconsommation={data?.autoconsommation} phraseTailles={phraseCouverture} />
      <Pertes total={data?.production?.total} plages={data?.cascade?.plages} />
      <EcartPvgis validation={data?.validation} />
    </section>
  )
}
