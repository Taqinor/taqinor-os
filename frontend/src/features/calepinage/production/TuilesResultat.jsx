import { useState } from 'react'
import { formatNumber, formatPercent } from '../../../lib/format'
import '../../../styles/calepinage/54-etape-resultats.css'

/* LA RANGÉE DE QUATRE TUILES de l'étape Résultats (maquette Resultats.dc.html) :
   « Production la première année » (héros sombre), « De la consommation »,
   « Pertes au total », « Écart avec PVGIS ». Aucun calcul : chaque tuile lit
   une valeur SERVIE (`production.total`, `autoconsommation.taux_couverture`,
   `cascade.plages.total`, `validation`) et n'existe que si cette valeur l'est —
   jamais un 0 ni un tiret à sa place. Les phrases sous les chiffres ne se
   disent que si leur fait est servi (portée « année moyenne », verdict de la
   plage, verdict de la tolérance). */

const nombre = (v) => typeof v === 'number' && Number.isFinite(v)

function Heros({ total }) {
  if (!nombre(total?.p50_kwh)) return null
  const moyenne = total?.portee === 'annee_moyenne'
  const parKwc = nombre(total?.specific_yield_kwh_kwc)
    ? `${formatNumber(total.specific_yield_kwh_kwc, { decimals: 0 })} kWh par kWc${moyenne ? ' · année moyenne (P50)' : ''}`
    : null
  return (
    <div className="cal-res-tuile cal-res-heros" data-tuile="heros">
      <span className="cal-res-tuile-label">Production la première année</span>
      <span className="cal-res-tuile-valeur">{`${formatNumber(total.p50_kwh, { decimals: 0 })} kWh`}</span>
      {parKwc && <span className="cal-res-tuile-note">{parKwc}</span>}
    </div>
  )
}

function Consommation({ autoconsommation }) {
  const [ouvert, setOuvert] = useState(false)
  const taux = autoconsommation?.taux_couverture
  if (!nombre(taux)) return null
  const definition = typeof autoconsommation?.definition === 'string' ? autoconsommation.definition : ''
  return (
    <div className="cal-res-tuile" data-tuile="couverture">
      <span className="cal-res-tuile-label">De la consommation</span>
      <span className="cal-res-tuile-valeur">{formatPercent(taux * 100, { decimals: 0 })}</span>
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

function Pertes({ total, plages }) {
  if (!nombre(total?.total_loss_pct)) return null
  const statut = plages?.total?.statut
  const phrase = statut === 'dans_la_plage' ? 'Dans la plage habituelle'
    : (plages?.total ? 'Hors de la plage habituelle' : null)
  return (
    <div className="cal-res-tuile" data-tuile="pertes">
      <span className="cal-res-tuile-label">Pertes au total</span>
      <span className="cal-res-tuile-valeur">{formatPercent(total.total_loss_pct, { decimals: 1 })}</span>
      {phrase && <span className="cal-res-tuile-note">{phrase}</span>}
    </div>
  )
}

function EcartPvgis({ validation }) {
  const pct = validation?.ecart_pct
  if (!nombre(pct)) return null
  const signe = pct < 0 ? '−' : (pct > 0 ? '+' : '')
  const tol = validation?.tolerance_pct
  const tolerance = nombre(tol) ? `±${formatNumber(tol, { decimals: Number.isInteger(tol) ? 0 : 1 })} %` : null
  let phrase = 'Comparé à PVGIS au même endroit'
  if (tolerance && validation.verdict === 'dans_la_tolerance') phrase = `Dans la tolérance de ${tolerance}`
  else if (tolerance && validation.verdict === 'hors_tolerance') phrase = `Hors de la tolérance de ${tolerance}`
  return (
    <div className="cal-res-tuile" data-tuile="ecart-pvgis">
      <span className="cal-res-tuile-label">Écart avec PVGIS</span>
      <span className="cal-res-tuile-valeur">{`${signe} ${formatNumber(Math.abs(pct), { decimals: 1 })} %`.trim()}</span>
      <span className="cal-res-tuile-note">{phrase}</span>
    </div>
  )
}

export default function TuilesResultat({ data }) {
  return (
    <section className="cal-res-tuiles" data-testid="cal-resultats-tuiles" aria-label="Résultats en un coup d'œil">
      <Heros total={data?.production?.total} />
      <Consommation autoconsommation={data?.autoconsommation} />
      <Pertes total={data?.production?.total} plages={data?.cascade?.plages} />
      <EcartPvgis validation={data?.validation} />
    </section>
  )
}
