import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT34 — Reconnaissance du revenu IFRS 15 (NTFIN46-48). Deux formes
   serveur vérifiées dans apps/compta/views.py :
   - `ObligationPerformanceViewSet.generer_echeancier` renvoie la LISTE des
     échéances DIRECTEMENT (`EcheancierReconnaissanceSerializer(many=True)`),
     jamais une enveloppe `{echeances:[...]}` — piège précis que ce groupe
     de tâches existe pour éviter.
   - `ContratRevenuViewSet.allouer` renvoie le contrat avec ses obligations
     mises à jour (`prix_alloue`). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  allouer: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    contratsRevenu: { list: mocks.list, get: mocks.get, allouer: mocks.allouer },
    obligationsPerformance: { create: vi.fn(), genererEcheancier: vi.fn() },
    echeancesReconnaissance: { reconnaitre: vi.fn() },
  },
}))

import RevenuIfrs15Page from './RevenuIfrs15Page.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><RevenuIfrs15Page /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

const CONTRAT = {
  id: 1, reference: 'CR-001', libelle: 'Maintenance solaire 3 ans', client_id: 5,
  client_nom: 'ACME SARL', source_devis_ref: 'DEV-042', montant_transaction: '30000.00',
  devise: 'MAD', statut: 'actif', statut_display: 'Actif',
  obligations: [
    { id: 10, contrat: 1, libelle: 'Matériel livré', prix_vente_specifique: '20000.00',
      prix_alloue: '0.00', methode_reconnaissance: 'a_une_date',
      methode_display: 'À une date (transfert du contrôle)', duree_mois: null,
      date_debut: null, statut: 'en_attente', montant_facture: '0.00',
      montant_reconnu: '0.00', echeances: [] },
  ],
}

describe('RevenuIfrs15Page — allocation du prix de transaction (PACT34)', () => {
  it("montre que la somme allouée égale le prix de transaction après allocation", async () => {
    mocks.list.mockResolvedValue({ data: [CONTRAT] })
    mocks.get.mockResolvedValueOnce({
      data: { ...CONTRAT, obligations: [{ ...CONTRAT.obligations[0], prix_alloue: '30000.00' }] },
    })
    mocks.allouer.mockResolvedValueOnce({ data: {} })
    mount()

    fireEvent.click(await screen.findByText('CR-001'))
    const bouton = await screen.findByRole('button', { name: /Allouer le prix/i })
    fireEvent.click(bouton)

    await waitFor(() => expect(mocks.allouer).toHaveBeenCalledWith(1))
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(1))
    expect(await screen.findByText('(équilibré)')).toBeInTheDocument()
  })
})
