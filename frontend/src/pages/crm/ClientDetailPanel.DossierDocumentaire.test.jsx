// WIR17(b) — bouton « Voir dossier documentaire » sur la fiche client, même
// motif que le bouton dossier chantier d'InstallationDetail.jsx:883 (route
// /reporting/archive/client/:id déjà enregistrée, N32).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn() },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const navigateSpy = vi.fn()
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => navigateSpy,
}))

import api from '../../api/axios'
import ClientDetailPanel from './ClientDetailPanel'
import { renderAvecAuth } from '../../test/renderAvecAuth'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPanel(client) {
  api.get.mockImplementation((url) => {
    if (url.includes('/documents/')) return Promise.resolve({ data: { devis: [], factures: [], chantiers: [] } })
    if (url.includes('/consolidation/')) return Promise.resolve({ data: { filiales: [] } })
    return Promise.resolve({ data: {} })
  })
  return renderAvecAuth(<ClientDetailPanel client={client} onClose={() => {}} onNewDevis={() => {}} onChanged={() => {}} />, { role: 'admin' })
}

const client = { id: 21, nom: 'Tazi', prenom: 'Nabil' }

describe('ClientDetailPanel — WIR17(b) : dossier documentaire', () => {
  it('navigue vers /reporting/archive/client/<id> au clic', async () => {
    renderPanel(client)
    await waitFor(() => expect(api.get).toHaveBeenCalled())
    await userEvent.click(screen.getByRole('button', { name: 'Voir dossier documentaire' }))
    expect(navigateSpy).toHaveBeenCalledWith('/reporting/archive/client/21')
  })
})

// VX152 — fin des moteurs de table parallèles : la fiche client rend ses
// Devis / Factures / Chantiers avec le primitif `Table` partagé (reporting),
// jamais une <table> écrite à la main. Données réelles dans le panneau réel :
// chaque <table> montée porte la classe et l'enveloppe du primitif.
describe('ClientDetailPanel — VX152 : tables du primitif partagé', () => {
  it('Devis, Factures et Chantiers sont rendus par le primitif Table (aucune table maison)', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/documents/')) {
        return Promise.resolve({
          data: {
            devis: [
              { id: 1, reference: 'DEV-001', statut: 'envoye', date: '2026-08-01', total_ttc: '12000.00' },
              { id: 2, reference: 'DEV-002', statut: 'accepte', date: '2026-08-02', total_ttc: '8000.00' },
            ],
            factures: [
              { id: 3, reference: 'FAC-001', statut: 'payee', statut_key: 'payee', date: '2026-08-05', total_ttc: '12000.00' },
            ],
            chantiers: [{ id: 4, reference: 'CH-001', statut: 'en_cours' }],
          },
        })
      }
      if (url.includes('/consolidation/')) return Promise.resolve({ data: { filiales: [] } })
      return Promise.resolve({ data: {} })
    })
    renderAvecAuth(
      <ClientDetailPanel client={client} onClose={() => {}} onNewDevis={() => {}} onChanged={() => {}} />,
      { role: 'admin' },
    )
    const devis = await screen.findByRole('table', { name: 'Devis' })
    const factures = screen.getByRole('table', { name: 'Factures' })
    const chantiers = screen.getByRole('table', { name: 'Chantiers' })
    const toutes = [...document.querySelectorAll('table')]
    // Les trois sections sont là, et RIEN d'autre n'est une table.
    expect(toutes).toHaveLength(3)
    for (const table of [devis, factures, chantiers]) {
      expect(table).toHaveClass('report-table')
      // Enveloppe scrollable du primitif (invariant PWA 375 px).
      expect(table.parentElement).toHaveClass('overflow-x-auto')
    }
    expect(screen.getByRole('cell', { name: 'DEV-002' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'CH-001' })).toBeInTheDocument()
  })
})
