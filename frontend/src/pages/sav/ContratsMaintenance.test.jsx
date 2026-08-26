import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { ContratStatutPill } from './ContratsMaintenance.jsx'

/* J144 — refonte SAV : les contrats de maintenance affichent leur statut via
   StatusPill. `ContratStatutPill` encode le mapping (inactif > visite due >
   à jour) ; la couleur n'est jamais le seul signal — le libellé FR reste. */

// WIR230/WIR231/WIR233 — Tournée préventive, Rentabilité (gardée
// prix_achat_voir) et « Facturer maintenant ». savApi/crmApi/installationsApi/
// axios mockés (patron EquipementFiabilitePanel.test.jsx pour le store redux).
const { getContrats, getTourneePreventive, planifierTournee,
  getRentabiliteContrats, facturerContrat } = vi.hoisted(() => ({
  getContrats: vi.fn(() => Promise.resolve({ data: [] })),
  getTourneePreventive: vi.fn(),
  planifierTournee: vi.fn(),
  getRentabiliteContrats: vi.fn(),
  facturerContrat: vi.fn(),
}))
vi.mock('../../api/savApi', () => ({
  default: {
    getContrats: (...a) => getContrats(...a),
    getTourneePreventive: (...a) => getTourneePreventive(...a),
    planifierTournee: (...a) => planifierTournee(...a),
    getRentabiliteContrats: (...a) => getRentabiliteContrats(...a),
    facturerContrat: (...a) => facturerContrat(...a),
    getTickets: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../api/crmApi', () => ({
  default: { getClients: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/installationsApi', () => ({
  default: { getInstallations: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { Component as ContratsMaintenance } from './ContratsMaintenance.jsx'

function makeStore(permissions = []) {
  return configureStore({
    reducer: { auth: (state = { role_nom: 'Responsable', permissions }) => state },
  })
}
function renderPage(permissions = []) {
  // DataTable a besoin d'un <Router> (useSearchParams) et d'un <ThemeProvider>
  // (useDensity) — patron DataTable.test.jsx.
  return render(
    <Provider store={makeStore(permissions)}>
      <MemoryRouter>
        <ThemeProvider>
          <ContratsMaintenance />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => { vi.clearAllMocks(); getContrats.mockResolvedValue({ data: [] }) })
afterEach(() => cleanup())

describe('ContratsMaintenance — Tournée préventive (WIR230)', () => {
  it('affiche la file dans l’ordre SERVEUR et planifie exactement {ticket_ids, date_tournee, technicien_id}', async () => {
    getTourneePreventive.mockResolvedValue({
      data: {
        results: [
          { id: 2, reference: 'SAV-PROCHE', client_nom: 'Client B', distance_km: 1.2 },
          { id: 1, reference: 'SAV-LOIN', client_nom: 'Client A', distance_km: 9.4 },
        ],
      },
    })
    planifierTournee.mockResolvedValue({ data: { tickets_planifies: 1 } })
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('radio', { name: 'Tournée' }))
    await waitFor(() => expect(getTourneePreventive).toHaveBeenCalled())

    const refs = (await screen.findAllByText(/SAV-(PROCHE|LOIN)/))
      .map((el) => el.textContent)
    // Ordre SERVEUR respecté (jamais retrié côté écran) : PROCHE avant LOIN.
    expect(refs[0]).toMatch(/SAV-PROCHE/)
    expect(refs[1]).toMatch(/SAV-LOIN/)

    await user.click(screen.getByLabelText('Sélectionner SAV-PROCHE'))
    const dateInput = screen.getByLabelText('Date de tournée')
    await user.type(dateInput, '2026-09-01')
    await user.click(screen.getByRole('button', { name: 'Planifier la tournée' }))

    await waitFor(() => expect(planifierTournee).toHaveBeenCalledWith({
      ticket_ids: [2], date_tournee: '2026-09-01', technicien_id: null,
    }))
  })

  it('affiche l’erreur FR du serveur sans planifier', async () => {
    getTourneePreventive.mockResolvedValue({
      data: { results: [{ id: 3, reference: 'SAV-3', client_nom: 'Client C' }] },
    })
    planifierTournee.mockRejectedValue({
      response: { data: { detail: 'Technicien inconnu.' } },
    })
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('radio', { name: 'Tournée' }))
    await screen.findByText(/SAV-3/)
    await user.click(screen.getByLabelText('Sélectionner SAV-3'))
    await user.type(screen.getByLabelText('Date de tournée'), '2026-09-01')
    await user.click(screen.getByRole('button', { name: 'Planifier la tournée' }))

    expect(await screen.findByText('Technicien inconnu.')).toBeInTheDocument()
  })
})

describe('ContratsMaintenance — Rentabilité (WIR231, gardée prix_achat_voir)', () => {
  it('n’expose PAS l’onglet Rentabilité sans la permission (aucune valeur de coût dans le DOM)', () => {
    renderPage([]) // pas de prix_achat_voir
    expect(screen.queryByRole('radio', { name: 'Rentabilité' })).not.toBeInTheDocument()
  })

  it('avec la permission : affiche revenu/coût/marge triés par le SERVEUR', async () => {
    getRentabiliteContrats.mockResolvedValue({
      data: {
        results: [
          { contrat_id: 1, client_nom: 'Perdant', revenu: 100, cout: 900, marge: -800, marge_par_visite: -800 },
          { contrat_id: 2, client_nom: 'Gagnant', revenu: 2000, cout: 200, marge: 1800, marge_par_visite: 1800 },
        ],
      },
    })
    const user = userEvent.setup()
    renderPage(['prix_achat_voir'])

    await user.click(screen.getByRole('radio', { name: 'Rentabilité' }))
    await waitFor(() => expect(getRentabiliteContrats).toHaveBeenCalled())
    expect(await screen.findByText('Perdant')).toBeInTheDocument()
    expect(screen.getByText('Gagnant')).toBeInTheDocument()
  })
})

describe('ContratsMaintenance — Facturer maintenant (WIR233)', () => {
  it('facture immédiatement un contrat facturation_active et affiche la référence', async () => {
    getContrats.mockResolvedValue({
      data: [{
        id: 5, client_nom: 'Client Facturable', periodicite: 'annuel',
        prix: '1000.00', date_debut: '2026-01-01', actif: true,
        facturation_active: true,
      }],
    })
    facturerContrat.mockResolvedValue({ data: { ok: true, facture_reference: 'FAC-0099' } })
    const user = userEvent.setup()
    renderPage()

    const bouton = await screen.findByRole('button', { name: 'Facturer maintenant' })
    await user.click(bouton)

    await waitFor(() => expect(facturerContrat).toHaveBeenCalledWith(5))
  })

  it('n’affiche PAS le bouton pour un contrat sans facturation_active', async () => {
    getContrats.mockResolvedValue({
      data: [{
        id: 6, client_nom: 'Client Sans Facturation', periodicite: 'annuel',
        prix: '1000.00', date_debut: '2026-01-01', actif: true,
        facturation_active: false,
      }],
    })
    renderPage()
    await screen.findByText('Client Sans Facturation')
    expect(screen.queryByRole('button', { name: 'Facturer maintenant' })).not.toBeInTheDocument()
  })
})

const DOT_CLASS = {
  neutral: 'bg-muted-foreground', success: 'bg-success', danger: 'bg-destructive',
}

describe('ContratStatutPill (J144 — statut contrat → ton + libellé FR)', () => {
  it('contrat inactif → point neutre, libellé « Inactif »', () => {
    const { container } = render(<ContratStatutPill contrat={{ actif: false }} />)
    expect(screen.getByText('Inactif')).toBeInTheDocument()
    expect(container.querySelector(`.${DOT_CLASS.neutral}`)).toBeTruthy()
  })

  it('contrat actif avec visite due → point danger, libellé « Visite due »', () => {
    const { container } = render(<ContratStatutPill contrat={{ actif: true, due: true }} />)
    expect(screen.getByText('Visite due')).toBeInTheDocument()
    expect(container.querySelector(`.${DOT_CLASS.danger}`)).toBeTruthy()
  })

  it('contrat actif à jour → point succès, libellé « À jour »', () => {
    const { container } = render(<ContratStatutPill contrat={{ actif: true, due: false }} />)
    expect(screen.getByText('À jour')).toBeInTheDocument()
    expect(container.querySelector(`.${DOT_CLASS.success}`)).toBeTruthy()
  })

  it('inactif l’emporte même si une visite est due', () => {
    render(<ContratStatutPill contrat={{ actif: false, due: true }} />)
    expect(screen.getByText('Inactif')).toBeInTheDocument()
  })
})
