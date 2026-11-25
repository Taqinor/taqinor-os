import { useEffect, useState } from 'react'
import { useSimulationFraiche } from './simulationFraiche' // T4-X2-006 — relue aussi tant que la simulation tourne
import { formatNumber } from '../../../lib/format'

/* ACAL401 — résumé vivant de l'atelier, passé en `children` de la barre d'enregistrement :
   panneaux · kWc relus sur le document SÉRIALISÉ (`result.panels`, `result.kwc` —
   contrat roof_layout_v2) toutes les secondes, donc moins de 2 s après un geste. T4-X8-013 — la PRODUCTION est celle de
   l'étape Résultats : « P50 … (simulation) » quand `GET resultat/` est frais (`simule` vrai ET `simulation_perimee` faux,
   résultat publié par l'étape Résultats compris), sinon « — » (le bandeau de provenance au-dessus dit pourquoi) —
   jamais l'estimation du constructeur (`result.annualKwh`), un second chiffre pour la même pose.
   Chiffre absent ⇒ « — », jamais 0 ni une valeur inventée. Affichage seul : aucune écriture. */
const PERIODE_MS = 1000
const nombre = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

function lireResultat(lireLayout) {
  let r = null
  try { r = lireLayout?.()?.result } catch { r = null }
  return { panneaux: nombre(r?.panels), kwc: nombre(r?.kwc) }
}

export default function ResumeAtelier({ lireLayout, calepinageId, rechargerLe }) {
  const [vivant, setVivant] = useState(() => lireResultat(lireLayout))

  useEffect(() => {
    const id = window.setInterval(() => {
      const suivant = lireResultat(lireLayout)
      setVivant((a) => (a.panneaux === suivant.panneaux && a.kwc === suivant.kwc ? a : suivant))
    }, PERIODE_MS)
    return () => window.clearInterval(id)
  }, [lireLayout])

  const p50 = useSimulationFraiche(calepinageId, rechargerLe)

  const production = p50 !== null ? `P50 ${formatNumber(p50, { decimals: 0 })} kWh/an (simulation)` : '—'
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
