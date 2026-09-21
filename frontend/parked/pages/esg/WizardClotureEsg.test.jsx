/* NTESG18 — assistant « Clôture de période ESG » (4 étapes).
 *
 * Ce que le test PROUVE :
 *   - les 4 étapes existent et le figeage n'est offert qu'à la DERNIÈRE ;
 *   - un AVERTISSEMENT (couverture faible, pas de période antérieure) est
 *     affiché mais NE BLOQUE PAS — c'est la règle centrale de NTESG18 ;
 *   - un BLOQUANT réel (période déjà figée) coupe la progression ET le
 *     figeage ;
 *   - l'aperçu PDF n'est demandé qu'à l'étape 3 ;
 *   - un aperçu indisponible n'empêche pas de figer (c'est une relecture).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const {
  prerequisCloture, apercuRapportPdf, figer, navigate,
} = vi.hoisted(() => ({
  prerequisCloture: vi.fn(),
  apercuRapportPdf: vi.fn(),
  figer: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('../../api/esgApi', () => ({
  default: { periodes: { prerequisCloture, apercuRapportPdf, figer } },
}))
vi.mock('react-router-dom', async () => {
  const reel = await vi.importActual('react-router-dom')
  return {
    ...reel,
    useNavigate: () => navigate,
    useParams: () => ({ periodeId: '12' }),
  }
})

import WizardClotureEsg from './WizardClotureEsg'

const BASE = {
  periode: {
    id: 12, libelle: 'Exercice 2026', statut: 'brouillon',
    date_debut: '2026-01-01', date_fin: '2026-12-31',
  },
  couverture: {
    piliers: {
      environnement: { total: 10, couverts: 7, pct: 70.0 },
      social: { total: 8, couverts: 3, pct: 37.5 },
    },
    global_pct: 55.6,
  },
  comparaison: null,
  avertissements: ['Couverture du pilier « social » : 37.5 %.'],
  bloquants: [],
  peut_figer: true,
  frequence_reporting: 'annuelle',
}

function monter() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <WizardClotureEsg />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('NTESG18 — assistant de clôture ESG', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    prerequisCloture.mockResolvedValue({ data: { ...BASE } })
    apercuRapportPdf.mockResolvedValue({ data: new Blob(['pdf']) })
    figer.mockResolvedValue({ data: {} })
    if (!globalThis.URL.createObjectURL) {
      globalThis.URL.createObjectURL = vi.fn(() => 'blob:apercu')
      globalThis.URL.revokeObjectURL = vi.fn()
    }
  })

  it('montre la couverture par pilier à l’étape 1', async () => {
    monter()
    expect(await screen.findByTestId('esg-cloture-etape-1'))
      .toBeInTheDocument()
    expect(screen.getByTestId('esg-cloture-pilier-social'))
      .toHaveTextContent('37.5')
    expect(screen.getByTestId('esg-cloture-pilier-environnement'))
      .toHaveTextContent('70')
  })

  it('AVERTIT sans bloquer sur une couverture faible', async () => {
    const user = userEvent.setup()
    monter()
    expect(await screen.findByTestId('esg-cloture-avertissements'))
      .toHaveTextContent('37.5')
    // L'avertissement n'empêche PAS d'avancer.
    expect(screen.getByTestId('esg-cloture-suivant-1')).not.toBeDisabled()
    await user.click(screen.getByTestId('esg-cloture-suivant-1'))
    expect(await screen.findByTestId('esg-cloture-etape-2'))
      .toBeInTheDocument()
  })

  it('dit qu’il n’y a pas de période antérieure, sans bloquer', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('esg-cloture-etape-1')
    await user.click(screen.getByTestId('esg-cloture-suivant-1'))
    expect(await screen.findByTestId('esg-cloture-sans-comparaison'))
      .toBeInTheDocument()
    expect(screen.getByTestId('esg-cloture-suivant-2')).not.toBeDisabled()
  })

  it('affiche les écarts avant/après quand une comparaison existe', async () => {
    prerequisCloture.mockResolvedValue({
      data: {
        ...BASE,
        comparaison: {
          periode_reference: { id: 11, libelle: 'Exercice 2025' },
          periode_n: { id: 12, libelle: 'Exercice 2026' },
          piliers: {
            environnement: [{
              code: 'ENV-CO2', libelle: 'CO2', comparable: true,
              valeur_reference: 120, valeur_n: 96,
              variation_abs: -24, variation_pct: -20,
            }],
          },
        },
      },
    })
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('esg-cloture-etape-1')
    await user.click(screen.getByTestId('esg-cloture-suivant-1'))
    const etape2 = await screen.findByTestId('esg-cloture-etape-2')
    expect(etape2).toHaveTextContent('ENV-CO2')
    expect(etape2).toHaveTextContent('120')
    expect(etape2).toHaveTextContent('96')
    expect(etape2).toHaveTextContent('-20')
  })

  it('ne demande l’aperçu PDF qu’à l’étape 3', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('esg-cloture-etape-1')
    expect(apercuRapportPdf).not.toHaveBeenCalled()
    await user.click(screen.getByTestId('esg-cloture-suivant-1'))
    await user.click(await screen.findByTestId('esg-cloture-suivant-2'))
    await waitFor(() => expect(apercuRapportPdf).toHaveBeenCalledTimes(1))
    expect(await screen.findByTestId('esg-cloture-etape-3'))
      .toBeInTheDocument()
  })

  it('un aperçu indisponible n’empêche pas de figer', async () => {
    apercuRapportPdf.mockRejectedValue({ response: { status: 500 } })
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('esg-cloture-etape-1')
    await user.click(screen.getByTestId('esg-cloture-suivant-1'))
    await user.click(await screen.findByTestId('esg-cloture-suivant-2'))
    expect(await screen.findByTestId('esg-cloture-apercu-erreur'))
      .toBeInTheDocument()
    await user.click(screen.getByTestId('esg-cloture-suivant-3'))
    expect(await screen.findByTestId('esg-cloture-figer')).not.toBeDisabled()
  })

  it('fige à la 4e étape, après l’avertissement d’irréversibilité', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('esg-cloture-etape-1')
    // Le figeage n'est PAS offert avant la dernière étape.
    expect(screen.queryByTestId('esg-cloture-figer')).toBeNull()
    await user.click(screen.getByTestId('esg-cloture-suivant-1'))
    await user.click(await screen.findByTestId('esg-cloture-suivant-2'))
    await user.click(await screen.findByTestId('esg-cloture-suivant-3'))

    const etape4 = await screen.findByTestId('esg-cloture-etape-4')
    expect(etape4).toHaveTextContent(/non réversible/i)
    await user.click(screen.getByTestId('esg-cloture-figer'))
    await waitFor(() => expect(figer).toHaveBeenCalledWith('12'))
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/esg'))
  })

  it('un BLOQUANT réel coupe la progression', async () => {
    prerequisCloture.mockResolvedValue({
      data: {
        ...BASE,
        periode: { ...BASE.periode, statut: 'figee' },
        bloquants: ['Cette période est déjà « Figée ».'],
        peut_figer: false,
      },
    })
    monter()
    expect(await screen.findByTestId('esg-cloture-bloquants'))
      .toHaveTextContent('déjà')
    expect(screen.getByTestId('esg-cloture-suivant-1')).toBeDisabled()
    expect(figer).not.toHaveBeenCalled()
  })
})
