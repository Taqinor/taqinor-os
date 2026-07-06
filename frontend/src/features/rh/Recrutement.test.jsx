import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import Recrutement from './Recrutement.jsx'

/* XRH17-23 / ZRH7-9 — ATS complet : smoke de rendu + présence des nouveaux
   onglets (Vivier / Statistiques / Gabarits) branchés sur les endpoints ATS.
   Le module ne doit jamais planter au chargement, même quand tout est vide. */

const empty = () => Promise.resolve({ data: [] })

vi.mock('../../api/rhApi', () => ({
  default: {
    getEpiCatalogue: vi.fn(empty),
    getDotationsEpi: vi.fn(empty),
    getOuverturesPoste: vi.fn(empty),
    getCandidatures: vi.fn(empty),
    getVivier: vi.fn(empty),
    getRecrutementStatistiques: vi.fn(() => Promise.resolve({ data: {} })),
    getGabaritsEmailRecrutement: vi.fn(empty),
    getModelesEvaluation: vi.fn(empty),
    getCampagnesEvaluation: vi.fn(empty),
    getEvaluationsEmploye: vi.fn(empty),
    getSanctions: vi.fn(empty),
  },
}))

function renderRecrutement() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Recrutement />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('Recrutement — ATS (XRH17-23)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module et charge les endpoints ATS (vivier + statistiques)', async () => {
    renderRecrutement()
    expect(
      await screen.findByText('EPI, recrutement & évaluations'),
    ).toBeInTheDocument()
    // Les nouveaux endpoints ATS sont bien appelés au montage.
    expect(rhApi.getVivier).toHaveBeenCalled()
    expect(rhApi.getRecrutementStatistiques).toHaveBeenCalled()
    expect(rhApi.getGabaritsEmailRecrutement).toHaveBeenCalled()
    expect(rhApi.getModelesEvaluation).toHaveBeenCalled()
  })

  it('propose les onglets Vivier / Statistiques / Gabarits', async () => {
    renderRecrutement()
    await screen.findByText('EPI, recrutement & évaluations')
    expect(screen.getByRole('radio', { name: 'Vivier' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Statistiques' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Gabarits' })).toBeInTheDocument()
  })
})
