// LB24 — Bandeau KPI = filtres (blueprint D5, « le cockpit du matin »).
// Les tuiles 1-3 sont des TOGGLES de filtre — compte FACETTÉ : le chiffre
// affiché est `filterLeads(leads, {…filtres actifs, sa dimension appliquée})`,
// donc cliquer donne EXACTEMENT ce que le chiffre promet (jamais un chiffre
// menteur). La tuile Pipeline est un AFFICHAGE seul (jamais un filtre) :
// Σ latestDevisTotal des leads FILTRÉS non perdus + pondéré via
// STAGE_PROBABILITY — importée de KanbanView, jamais une 2e table déclarée
// ici (même règle que ForecastView, XSAL15).
import { useMemo } from 'react'
import {
  filterLeads, isPerdu, latestDevisTotal, formatMAD,
} from '../../../features/crm/stages'
import { STAGE_PROBABILITY } from './views/KanbanView'

export default function LeadsKpiStrip({ leads, filters, setFilters, myUsername }) {
  const countWith = (overrides) => filterLeads(
    leads, { ...filters, ...overrides }, { myUsername },
  ).length

  const dueTodayCount = useMemo(
    () => countWith({ relance: 'aujourdhui' }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- countWith ferme sur leads/filters/myUsername, déjà listés
    [leads, filters, myUsername],
  )
  const retardCount = useMemo(
    () => countWith({ relance: 'retard' }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [leads, filters, myUsername],
  )
  const chaudsCount = useMemo(
    () => countWith({ score: 'chaud' }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [leads, filters, myUsername],
  )

  // Pipeline : les leads FILTRÉS (état courant, jamais une dimension forcée)
  // non perdus — un lead perdu a 0% de chance de conversion, il ne compte
  // JAMAIS dans le pipeline même si le filtre « perdus » les affiche.
  const { brut, pondere } = useMemo(() => {
    const pool = filterLeads(leads, filters, { myUsername }).filter((l) => !isPerdu(l))
    return {
      brut: pool.reduce((s, l) => s + latestDevisTotal(l), 0),
      pondere: pool.reduce(
        (s, l) => s + latestDevisTotal(l) * (STAGE_PROBABILITY[l.stage] ?? 0), 0,
      ),
    }
  }, [leads, filters, myUsername])

  const dueTodayActive = filters.relance === 'aujourdhui'
  const retardActive = filters.relance === 'retard'
  const chaudsActive = filters.score === 'chaud'

  const toggleRelance = (value) => setFilters((f) => ({
    ...f, relance: f.relance === value ? '' : value,
  }))
  const toggleChauds = () => setFilters((f) => ({
    ...f, score: f.score === 'chaud' ? '' : 'chaud',
  }))

  return (
    <div className="lp-kpi-strip" role="group" aria-label="Indicateurs du pipeline (filtres rapides)">
      <button
        type="button"
        className="lp-kpi-tile"
        aria-pressed={dueTodayActive}
        onClick={() => toggleRelance('aujourdhui')}
      >
        <span className="lp-kpi-value">{dueTodayCount}</span>
        <span className="lp-kpi-label">Dû aujourd’hui</span>
      </button>
      <button
        type="button"
        className="lp-kpi-tile"
        aria-pressed={retardActive}
        onClick={() => toggleRelance('retard')}
      >
        <span className="lp-kpi-value">{retardCount}</span>
        <span className="lp-kpi-label">En retard</span>
      </button>
      <button
        type="button"
        className="lp-kpi-tile"
        aria-pressed={chaudsActive}
        onClick={toggleChauds}
      >
        <span className="lp-kpi-value">{chaudsCount}</span>
        <span className="lp-kpi-label">Chauds</span>
      </button>
      {/* Affichage seul — jamais un `<button>`, jamais un filtre (blueprint D5).
          LB46 (fondateur) : le prévisionnel quitte le libellé visible — il
          vit dans l'infobulle ; la chip n'affiche que le total Pipeline. */}
      <div
        className="lp-kpi-tile lp-kpi-tile-display"
        title={`Prévisionnel pondéré : ${formatMAD(pondere)} (probabilité de conversion par étape)`}
      >
        <span className="lp-kpi-value">{formatMAD(brut)}</span>
        <span className="lp-kpi-label">Pipeline</span>
      </div>
    </div>
  )
}
