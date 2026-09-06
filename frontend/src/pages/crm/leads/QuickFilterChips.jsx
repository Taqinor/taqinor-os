import { useMemo } from 'react'
import { Button } from '../../../ui'
import { filterLeads } from '../../../features/crm/stages'

// LB51 — UN jeu homogène de chips-filtres comptées (blueprint cockpit,
// patron « quick-filter pills » Pipedrive/HubSpot compacté dans la rangée
// de contrôle) : fusion des 3 tuiles KPI-toggles (Dû aujourd'hui/En retard/
// Chauds — ex-LeadsKpiStrip, mêmes calculs facettés sur le pool équipe) et
// des 2 chips fréquentes (Mes leads — VX224, ☎ Rappels — VX223, ex-
// FilterBar). Chaque chip lit/écrit le MÊME état `filters` (invariant D6-I7,
// un seul état de filtres) ; le badge numérique ne rend que s'il est > 0
// (règle de repli du blueprint : bruit zéro le matin calme).
export default function QuickFilterChips({ leads, filters, setFilters, myUsername }) {
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
  // MRY16 — moteur de relances (crm.RelanceEtape) : distinct des chips
  // « Dû aujourd'hui »/« En retard » ci-dessus (qui lisent `relance_date`,
  // le rappel manuel unique) — ceux-ci lisent la cadence structurée.
  const toucheDueCount = useMemo(
    () => countWith({ touche: 'due' }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [leads, filters, myUsername],
  )
  const tentatives7PlusCount = useMemo(
    () => countWith({ tentatives: '7plus' }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [leads, filters, myUsername],
  )

  const toggleRelance = (val) => setFilters((f) => ({
    ...f, relance: f.relance === val ? '' : val,
  }))
  const toggleChauds = () => setFilters((f) => ({
    ...f, score: f.score === 'chaud' ? '' : 'chaud',
  }))
  const mesLeadsActif = !!filters.mesLeads
  const toggleMesLeads = () => setFilters((f) => ({ ...f, mesLeads: !f.mesLeads }))
  const rappelsActifs = filters.contact_preference === 'phone_ok'
  const toggleRappels = () => setFilters((f) => ({
    ...f, contact_preference: rappelsActifs ? '' : 'phone_ok',
  }))
  const toggleToucheDue = () => setFilters((f) => ({
    ...f, touche: f.touche === 'due' ? '' : 'due',
  }))
  const toggleTentatives7Plus = () => setFilters((f) => ({
    ...f, tentatives: f.tentatives === '7plus' ? '' : '7plus',
  }))

  const chips = [
    { key: 'mes-leads', label: 'Mes leads', pressed: mesLeadsActif, onClick: toggleMesLeads, className: 'fb-chip-mes-leads' },
    { key: 'rappels', label: '☎ Rappels', pressed: rappelsActifs, onClick: toggleRappels, className: 'fb-chip-rappels' },
    { key: 'due-today', label: 'Dû aujourd’hui', pressed: filters.relance === 'aujourdhui', onClick: () => toggleRelance('aujourdhui'), count: dueTodayCount },
    { key: 'retard', label: 'En retard', pressed: filters.relance === 'retard', onClick: () => toggleRelance('retard'), count: retardCount },
    { key: 'chauds', label: 'Chauds', pressed: filters.score === 'chaud', onClick: toggleChauds, count: chaudsCount },
    { key: 'touche-due', label: 'Touche due', pressed: filters.touche === 'due', onClick: toggleToucheDue, count: toucheDueCount },
    { key: 'tentatives-7plus', label: '≥ 7 tentatives', pressed: filters.tentatives === '7plus', onClick: toggleTentatives7Plus, count: tentatives7PlusCount },
  ]

  return (
    <div className="lp-quick-chips" role="group" aria-label="Filtres rapides du pipeline">
      {chips.map((c) => (
        <Button
          key={c.key}
          type="button"
          variant={c.pressed ? 'default' : 'outline'}
          size="sm"
          className={c.className}
          aria-pressed={c.pressed}
          onClick={c.onClick}
        >
          {c.label}
          {c.count > 0 && <span className="count-badge">{c.count}</span>}
        </Button>
      ))}
    </div>
  )
}
