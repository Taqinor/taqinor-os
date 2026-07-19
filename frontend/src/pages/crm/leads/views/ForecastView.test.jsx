import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import ForecastView from './ForecastView'

/* XSAL15 — Vue kanban « Prévision » : regroupement par mois de
   date_cloture_prevue + colonne Non daté + totaux brut/pondéré en tête.
   Le glisser-déposer lui-même (dnd-kit) n'est pas simulé ici (comme
   KanbanView.test.jsx) — on vérifie le rendu/groupement, pas le geste.
   LeadCard est mocké (présentation pure ailleurs testée en isolation via
   node:test structurel) pour garder ce test concentré sur le groupement. */

vi.mock('./LeadCard', () => ({
  default: ({ lead }) => <div data-testid={`lead-${lead.id}`}>{lead.nom}</div>,
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

const now = new Date()
const thisMonthKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const thisMonthDate = `${thisMonthKey}-15`

const leads = [
  {
    id: 1, nom: 'Ouvert daté', stage: 'QUOTE_SENT', perdu: false,
    date_cloture_prevue: thisMonthDate,
    devis: [{ total_ttc: '100000' }],
  },
  {
    id: 2, nom: 'Ouvert sans date', stage: 'NEW', perdu: false,
    date_cloture_prevue: null,
    devis: [],
  },
  {
    id: 3, nom: 'Perdu', stage: 'COLD', perdu: true,
    date_cloture_prevue: thisMonthDate,
    devis: [{ total_ttc: '50000' }],
  },
  {
    id: 4, nom: 'Déjà signé', stage: 'SIGNED', perdu: false,
    date_cloture_prevue: thisMonthDate,
    devis: [{ total_ttc: '80000' }],
  },
]

describe('ForecastView (XSAL15)', () => {
  it('groupe les leads OUVERTS par mois (exclut perdu + déjà signé)', () => {
    render(<ForecastView leads={leads} users={[]} />)
    // Le lead ouvert daté ce mois-ci doit apparaître.
    expect(screen.getByText('Ouvert daté')).toBeInTheDocument()
    // Le lead perdu et le lead déjà signé ne doivent PAS apparaître.
    expect(screen.queryByText('Perdu')).not.toBeInTheDocument()
    expect(screen.queryByText('Déjà signé')).not.toBeInTheDocument()
  })

  it('affiche une colonne « Non daté » pour les leads sans date_cloture_prevue', () => {
    render(<ForecastView leads={leads} users={[]} />)
    expect(screen.getByText('Non daté')).toBeInTheDocument()
    expect(screen.getByText('Ouvert sans date')).toBeInTheDocument()
  })

  it('affiche un total brut + prévisionnel pondéré en tête de colonne quand > 0', () => {
    render(<ForecastView leads={leads} users={[]} />)
    // QUOTE_SENT → STAGE_PROBABILITY 0.5 × 100000 = 50000 pondéré.
    expect(screen.getByText(/Prév\./)).toBeInTheDocument()
  })

  it('LB28 — affiche un EmptyState (plus le board) quand la liste de leads est vide', () => {
    render(<ForecastView leads={[]} users={[]} />)
    expect(screen.getByText('Aucun lead')).toBeInTheDocument()
    expect(screen.queryByText('Non daté')).not.toBeInTheDocument()
  })

  it('LB28 — affiche un EmptyState quand tous les leads sont fermés (perdus/signés, 0 lead OUVERT)', () => {
    // « Tous filtrés/fermés » : leads.length > 0 mais aucun n'est ouvert —
    // avant LB28, ForecastView affichait quand même 7 colonnes vides.
    render(
      <ForecastView
        leads={[
          { id: 10, nom: 'Perdu', stage: 'COLD', perdu: true, date_cloture_prevue: null, devis: [] },
          { id: 11, nom: 'Signé', stage: 'SIGNED', perdu: false, date_cloture_prevue: null, devis: [] },
        ]}
        users={[]}
      />,
    )
    expect(screen.getByText('Aucun lead')).toBeInTheDocument()
    expect(screen.queryByText('Non daté')).not.toBeInTheDocument()
  })

  it('LB28 — équivalent clavier du glisser : le <select> mois réutilise onInlineSave (même PATCH que le drag)', async () => {
    const onInlineSave = vi.fn(() => Promise.resolve({}))
    render(<ForecastView leads={leads} users={[]} onInlineSave={onInlineSave} />)
    const select = screen.getByLabelText('Replanifier Ouvert daté')
    // Le mois du mois PROCHAIN existe toujours parmi les options (colonnes des
    // 6 prochains mois, blueprint D2) — jamais le même mois que la valeur
    // courante, sinon le changement serait un no-op.
    const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1)
    const nextMonthKey = `${nextMonth.getFullYear()}-${String(nextMonth.getMonth() + 1).padStart(2, '0')}`
    fireEvent.change(select, { target: { value: nextMonthKey } })
    await waitFor(() => expect(onInlineSave).toHaveBeenCalledWith(
      expect.objectContaining({ id: 1 }), 'date_cloture_prevue', `${nextMonthKey}-01`,
    ))
  })

  it('LB28 — « Non daté » n\'est jamais une option sélectionnable pour un lead déjà daté', () => {
    render(<ForecastView leads={leads} users={[]} onInlineSave={vi.fn()} />)
    const select = screen.getByLabelText('Replanifier Ouvert daté')
    const optionLabels = [...select.options].map((o) => o.textContent)
    expect(optionLabels).not.toContain('Non daté')
  })

  it('LB28 — un lead sans date affiche « Non daté » comme valeur courante du select (assignable, jamais une cible depuis un autre mois)', () => {
    render(<ForecastView leads={leads} users={[]} onInlineSave={vi.fn()} />)
    const select = screen.getByLabelText('Replanifier Ouvert sans date')
    expect(select.value).toBe('undated')
    expect([...select.options].map((o) => o.textContent)).toContain('Non daté')
  })
})
