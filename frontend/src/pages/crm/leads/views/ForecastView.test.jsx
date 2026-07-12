import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
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

  it('ne casse pas avec une liste de leads vide', () => {
    render(<ForecastView leads={[]} users={[]} />)
    expect(screen.getByText('Non daté')).toBeInTheDocument()
  })
})
