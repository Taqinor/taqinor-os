import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* CAD50 — « Annuler » (retour arrière 24h) et « Arrêter la cadence » (motif
   obligatoire) directement sur la ligne du Suivi des relances : les deux
   actions n'existaient auparavant que sur la fiche du lead. Contrairement
   au Cockpit (RelancesDuJourWidget.jsx), cet écran sert TOUS les statuts —
   une touche fait/sautée récente est donc directement dans la réponse
   serveur, sans suivi local séparé. */
import { exempleContrat } from '../../test/fixtures/contractSamples'

const ETAPE_MODELE = exempleContrat('crm', 'relance_etapes_suivi').results[0]

const isAdminOrResponsableMock = vi.fn(() => false)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { id: 42 } } }),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesSuivi: vi.fn(),
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    marquerRelanceEtapeFait: vi.fn(),
    marquerRelanceEtapeSautee: vi.fn(),
    reporterRelanceEtape: vi.fn(),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
    getMesureCadence: vi.fn(() => Promise.reject(new Error('non pertinent ici'))),
    annulerRelanceEtape: vi.fn(),
    arreterCadence: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import RelancesSuiviPage from './RelancesSuiviPage'

function casaISO(d) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca' }).format(d)
}

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(false)
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesSuiviPage />
    </MemoryRouter>,
  )
}

describe('RelancesSuiviPage — CAD50 (« Annuler »/« Arrêter » hors fiche)', () => {
  it('une touche « a_faire » porte « Arrêter la cadence », motif obligatoire, appelle crmApi.arreterCadence(leadId, {motif})', async () => {
    crmApi.getRelanceEtapesSuivi.mockResolvedValue({
      data: {
        results: [{ ...ETAPE_MODELE, id: 900, statut: 'a_faire', traite_le: null, due_date: casaISO(new Date()) }],
        resume: { a_faire: 1, en_retard: 0, fait: 0, sautee: 0, annulee: 0 },
      },
    })
    crmApi.arreterCadence.mockResolvedValue({ data: { arretees: 1 } })
    mount()
    await screen.findAllByTestId('relance-etape-row')

    fireEvent.click(screen.getByRole('button', { name: 'Arrêter la cadence' }))
    const confirmer = screen.getByRole('button', { name: 'Confirmer' })
    expect(confirmer).toBeDisabled()

    fireEvent.change(screen.getByTestId('cad50-arreter-motif'), { target: { value: 'Client injoignable' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))

    await waitFor(() => expect(crmApi.arreterCadence).toHaveBeenCalledWith(
      ETAPE_MODELE.lead, { motif: 'Client injoignable' },
    ))
    await waitFor(() => expect(screen.queryByTestId('cad50-arreter-motif')).not.toBeInTheDocument())
  })

  it('une touche « fait » traitée il y a moins de 24h porte « Annuler », qui appelle crmApi.annulerRelanceEtape', async () => {
    const ilYA2H = new Date(Date.now() - 2 * 3600 * 1000).toISOString()
    crmApi.getRelanceEtapesSuivi.mockResolvedValue({
      data: {
        results: [{
          ...ETAPE_MODELE, id: 901, statut: 'fait', traite_le: ilYA2H, due_date: casaISO(new Date()),
        }],
        resume: { a_faire: 0, en_retard: 0, fait: 1, sautee: 0, annulee: 0 },
      },
    })
    mount()
    await screen.findAllByTestId('relance-etape-row')

    const bouton = screen.getByRole('button', { name: 'Annuler' })
    fireEvent.click(bouton)
    await waitFor(() => expect(crmApi.annulerRelanceEtape).toHaveBeenCalledWith(901))
  })

  it('une touche « fait » traitée il y a plus de 24h ne porte PAS « Annuler »', async () => {
    const ilYA48H = new Date(Date.now() - 48 * 3600 * 1000).toISOString()
    crmApi.getRelanceEtapesSuivi.mockResolvedValue({
      data: {
        results: [{
          ...ETAPE_MODELE, id: 902, statut: 'fait', traite_le: ilYA48H, due_date: casaISO(new Date()),
        }],
        resume: { a_faire: 0, en_retard: 0, fait: 1, sautee: 0, annulee: 0 },
      },
    })
    mount()
    await screen.findAllByTestId('relance-etape-row')
    expect(screen.queryByRole('button', { name: 'Annuler' })).not.toBeInTheDocument()
  })
})
