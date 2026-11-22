import { useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { formatNumber } from '../../../lib/format'

/* ACAL401 — résumé vivant de l'atelier, passé en `children` de la barre d'enregistrement :
   panneaux · kWc · production, relus sur le document SÉRIALISÉ (`result.panels`, `result.kwc`,
   `result.annualKwh` — contrat roof_layout_v2) toutes les secondes, donc moins de 2 s après un
   geste. La production est une « estimation » tant que `GET resultat/` n'est pas frais
   (`simule` vrai ET `simulation_perimee` faux) ; alors elle devient « P50 … (simulation) ».
   Chiffre absent ⇒ « — », jamais 0 ni une valeur inventée. Affichage seul : aucune écriture. */
const PERIODE_MS = 1000
const nombre = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

function lireResultat(lireLayout) {
  let r = null
  try { r = lireLayout?.()?.result } catch { r = null }
  return { panneaux: nombre(r?.panels), kwc: nombre(r?.kwc), kwh: nombre(r?.annualKwh) }
}

export default function ResumeAtelier({ lireLayout, calepinageId, rechargerLe }) {
  const [vivant, setVivant] = useState(() => lireResultat(lireLayout))
  const [p50, setP50] = useState(null)

  useEffect(() => {
    const id = window.setInterval(() => {
      const suivant = lireResultat(lireLayout)
      setVivant((a) => (a.panneaux === suivant.panneaux && a.kwc === suivant.kwc
        && a.kwh === suivant.kwh ? a : suivant))
    }, PERIODE_MS)
    return () => window.clearInterval(id)
  }, [lireLayout])

  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.resultat(calepinageId)).then((rep) => {
      const d = rep?.data
      const frais = d?.simule === true && d?.simulation_perimee === false
      if (!annule) setP50(frais ? nombre(d?.production?.total?.p50_kwh) : null)
    }).catch(() => { if (!annule) setP50(null) })
    return () => { annule = true }
  }, [calepinageId, rechargerLe])

  let production = '—'
  if (p50 !== null) production = `P50 ${formatNumber(p50, { decimals: 0 })} kWh/an (simulation)`
  else if (vivant.kwh !== null) {
    production = `≈ ${formatNumber(vivant.kwh, { decimals: 0 })} kWh/an (estimation)`
  }
  return (
    <p className="text-sm text-muted-foreground" data-testid="cal-resume-atelier">
      <span data-testid="cal-resume-panneaux">
        {vivant.panneaux === null ? '—' : `${formatNumber(vivant.panneaux, { decimals: 0 })} panneaux`}
      </span>
      {' · '}
      <span data-testid="cal-resume-kwc">
        {vivant.kwc === null ? '—' : `${formatNumber(vivant.kwc, { decimals: 2 })} kWc`}
      </span>
      {' · '}
      <span data-testid="cal-resume-production">{production}</span>
    </p>
  )
}
