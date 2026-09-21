import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render as rtlRender, screen, fireEvent, waitFor, within }
  from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// NTESG18 — le cockpit navigue désormais vers l'assistant de clôture
// (`useNavigate`) : il lui faut un Router, comme dans l'application
// réelle où il est toujours monté sous le routeur de module.
const render = (ui) => rtlRender(<MemoryRouter>{ui}</MemoryRouter>)

const PERIODES = [
  { id: 1, libelle: 'Exercice 2025', date_debut: '2025-01-01', date_fin: '2025-12-31', statut: 'brouillon' },
  { id: 2, libelle: 'Exercice 2026', date_debut: '2026-01-01', date_fin: '2026-12-31', statut: 'brouillon' },
]

vi.mock('../../api/esgApi', () => ({
  default: {
    catalogue: {
      couverture: vi.fn(() => Promise.resolve({ data: { piliers: {} } })),
      badgeMaturite: vi.fn(() => Promise.resolve({ data: null })),
    },
    periodes: {
      list: vi.fn(() => Promise.resolve({ data: PERIODES })),
      create: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
      comparer: vi.fn(() => Promise.resolve({ data: {
        periode_reference: { id: 1, libelle: 'Exercice 2025' },
        periode_n: { id: 2, libelle: 'Exercice 2026' },
        piliers: {
          environnement: [
            { code: 'co2', libelle: 'Émissions CO2', comparable: true, valeur_reference: 100, valeur_n: 90, variation_abs: -10, variation_pct: -10 },
          ],
        },
      } })),
      dpef: vi.fn(() => Promise.resolve({ data: new Blob(['# DPEF']) })),
      // AUDV26 (NTESG9) — ratios carbone dépliés depuis la liste des périodes.
      indicateurs: vi.fn(() => Promise.resolve({ data: {
        intensite_carbone: {
          ratios: {
            par_mad_ca: { disponible: false, valeur: null, unite: 'tCO2e/MAD CA', raison: 'Bilan carbone indisponible.' },
            par_kwc_installe: { disponible: true, valeur: 0.05, unite: 'tCO2e/kWc installé', raison: null },
            par_etp: { disponible: false, valeur: null, unite: 'tCO2e/ETP', raison: 'ETP indisponible.' },
          },
        },
      } })),
    },
    documentsPolitique: {
      list: vi.fn(() => Promise.resolve({ data: [] })),
      create: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    },
  },
}))
vi.mock('../../api/importApi', () => ({ downloadXlsx: vi.fn() }))
vi.mock('../../utils/downloadBlob', () => ({ downloadBlob: vi.fn() }))

import esgApi from '../../api/esgApi'
import { downloadBlob } from '../../utils/downloadBlob'
import EsgCockpit from './EsgCockpit'

describe('EsgCockpit (WIR129)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('crée une période depuis le dialogue', async () => {
    render(<EsgCockpit />)
    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle période/ }))
    const dialog = within(await screen.findByRole('dialog'))
    fireEvent.change(dialog.getByLabelText('Libellé'), { target: { value: 'Exercice 2027' } })
    fireEvent.change(dialog.getByLabelText('Date de début'), { target: { value: '2027-01-01' } })
    fireEvent.change(dialog.getByLabelText('Date de fin'), { target: { value: '2027-12-31' } })
    fireEvent.click(dialog.getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(esgApi.periodes.create).toHaveBeenCalledWith({
      libelle: 'Exercice 2027', date_debut: '2027-01-01', date_fin: '2027-12-31',
    }))
  })

  it('compare deux périodes et affiche les écarts', async () => {
    render(<EsgCockpit />)
    await screen.findByText('Comparer deux périodes')
    fireEvent.change(screen.getByLabelText('Période (N)'), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Référence (N-1)'), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Comparer' }))
    await waitFor(() => expect(esgApi.periodes.comparer).toHaveBeenCalledWith('2', '1'))
    expect(await screen.findByText('Émissions CO2')).toBeInTheDocument()
  })

  it('télécharge le DPEF d\'une période', async () => {
    render(<EsgCockpit />)
    const dpefButtons = await screen.findAllByRole('button', { name: /DPEF/ })
    fireEvent.click(dpefButtons[0])
    await waitFor(() => expect(esgApi.periodes.dpef).toHaveBeenCalled())
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled())
  })

  /* AUDV26 (NTESG9) — les 3 ratios carbone, jusqu'ici sans appelant. */
  describe('ratios carbone (AUDV26)', () => {
    it('déplie les 3 ratios, dégradés proprement quand une donnée manque', async () => {
      render(<EsgCockpit />)
      const boutons = await screen.findAllByRole('button', { name: /Ratios carbone/ })
      fireEvent.click(boutons[0])

      await waitFor(() => expect(esgApi.periodes.indicateurs).toHaveBeenCalledWith(1))
      expect(await screen.findByText('0.05')).toBeInTheDocument()
      expect(screen.getByText('Bilan carbone indisponible.')).toBeInTheDocument()
      expect(screen.getByText('ETP indisponible.')).toBeInTheDocument()
    })

    it('replie au second clic sans réappeler le serveur', async () => {
      render(<EsgCockpit />)
      const boutons = await screen.findAllByRole('button', { name: /Ratios carbone/ })
      fireEvent.click(boutons[0])
      await waitFor(() => expect(esgApi.periodes.indicateurs).toHaveBeenCalledTimes(1))
      await screen.findByText('0.05')

      fireEvent.click(boutons[0])
      expect(screen.queryByText('0.05')).not.toBeInTheDocument()

      fireEvent.click(boutons[0])
      expect(await screen.findByText('0.05')).toBeInTheDocument()
      // Remise en cache : un second dépliage ne réappelle pas le serveur.
      expect(esgApi.periodes.indicateurs).toHaveBeenCalledTimes(1)
    })
  })
})
