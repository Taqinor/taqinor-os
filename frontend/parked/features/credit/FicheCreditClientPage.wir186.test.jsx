import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* WIR186 — Deux trous corrigés sur la fiche crédit d'un client :

   1. La limite n'était JAMAIS modifiable : l'assistant appelait toujours
      `createLimite`, donc sur un client qui en avait déjà une le second POST
      se heurtait à l'unicité `(company, client)` — une erreur d'intégrité, pas
      un message métier.
   2. `GET /credit/limites/<id>/historique/` (NTCRD22) n'avait AUCUN appelant :
      la traçabilité des changements était écrite côté serveur et invisible. */

vi.mock('../../api/creditApi', () => ({
  default: {
    getLimites: vi.fn(),
    createLimite: vi.fn(),
    updateLimite: vi.fn(),
    getLimiteHistorique: vi.fn(),
    getFicheClient: vi.fn(),
    getLimiteSuggeree: vi.fn(),
  },
}))

import creditApi from '../../api/creditApi'
import FicheCreditClientPage from './FicheCreditClientPage'

const FICHE = {
  limite: '50000.00', encours: '12000.00', disponible: '38000.00',
  pct_utilise: 0.24, lettre_score: 'B', mode_hold: 'avertissement',
  depasse: false, derogations: [],
}
const LIMITE = { id: 7, client: 3, montant_limite: '50000.00', mode_hold: 'avertissement' }

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/credit/clients/3']}>
      <Routes>
        <Route path="/credit/clients/:id" element={<FicheCreditClientPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

const allerEtape3 = async () => {
  fireEvent.click(await screen.findByRole('button', { name: /limite/i }))
  fireEvent.click(await screen.findByRole('button', { name: 'Suivant' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Suivant' }))
}

beforeEach(() => {
  vi.clearAllMocks()
  creditApi.getFicheClient.mockResolvedValue({ data: FICHE })
  creditApi.getLimiteSuggeree.mockResolvedValue({ data: { suggestion: '80000' } })
  creditApi.getLimiteHistorique.mockResolvedValue({ data: { count: 0, entries: [] } })
})

describe('FicheCreditClientPage — WIR186 : limite éditable', () => {
  it('client SANS limite : l’assistant CRÉE (branche historique)', async () => {
    creditApi.getLimites.mockResolvedValue({ data: [] })
    creditApi.createLimite.mockResolvedValue({ data: { id: 9 } })
    renderPage()
    await waitFor(() => expect(creditApi.getLimites)
      .toHaveBeenCalledWith({ client: 3 }))
    expect(await screen.findByRole('button', { name: 'Définir la limite' }))
      .toBeInTheDocument()

    await allerEtape3()
    fireEvent.click(await screen.findByRole('button', { name: 'Valider la limite' }))
    await waitFor(() => expect(creditApi.createLimite).toHaveBeenCalledWith({
      client: 3, montant_limite: '80000', mode_hold: 'avertissement',
    }))
    expect(creditApi.updateLimite).not.toHaveBeenCalled()
  })

  it('client AVEC limite : l’assistant MODIFIE, jamais une seconde création', async () => {
    creditApi.getLimites.mockResolvedValue({ data: [LIMITE] })
    creditApi.updateLimite.mockResolvedValue({ data: LIMITE })
    renderPage()
    expect(await screen.findByRole('button', { name: 'Modifier la limite' }))
      .toBeInTheDocument()

    await allerEtape3()
    fireEvent.click(await screen.findByRole('button', { name: 'Enregistrer la limite' }))
    await waitFor(() => expect(creditApi.updateLimite).toHaveBeenCalledWith(7, {
      montant_limite: '50000.00', mode_hold: 'avertissement',
    }))
    // LE point de la tâche : plus AUCUN second POST (donc plus d'erreur
    // d'intégrité sur l'unicité (company, client)).
    expect(creditApi.createLimite).not.toHaveBeenCalled()
    // En édition, la suggestion n'écrase pas la décision déjà prise.
    expect(creditApi.getLimiteSuggeree).not.toHaveBeenCalled()
  })

  it('un refus serveur est affiché TEL QUEL (jamais « Création impossible »)', async () => {
    creditApi.getLimites.mockResolvedValue({ data: [LIMITE] })
    creditApi.updateLimite.mockRejectedValue({
      response: { status: 400, data: { detail: 'Une limite existe déjà pour ce client.' } },
    })
    renderPage()
    await allerEtape3()
    fireEvent.click(await screen.findByRole('button', { name: 'Enregistrer la limite' }))
    expect(await screen.findByText('Une limite existe déjà pour ce client.'))
      .toBeInTheDocument()
  })
})

describe('FicheCreditClientPage — WIR186 : historique de la limite', () => {
  it('rend les entrées du chatter servies par le serveur', async () => {
    creditApi.getLimites.mockResolvedValue({ data: [LIMITE] })
    creditApi.getLimiteHistorique.mockResolvedValue({
      data: {
        count: 1,
        entries: [{
          id: 1, kind: 'modification', field: 'montant_limite',
          field_label: 'Montant', old_value: '30000.00', new_value: '50000.00',
          body: '', created_at: '2026-08-20T09:00:00Z', acteur: 'reda',
        }],
      },
    })
    renderPage()
    await waitFor(() => expect(creditApi.getLimiteHistorique).toHaveBeenCalledWith(7))
    const bloc = await screen.findByTestId('credit-limite-historique')
    expect(bloc).toHaveTextContent('Montant : 30000.00 → 50000.00')
    expect(bloc).toHaveTextContent('reda')
  })

  it('état vide propre quand rien n’a changé', async () => {
    creditApi.getLimites.mockResolvedValue({ data: [LIMITE] })
    renderPage()
    expect(await screen.findByText('Aucun changement consigné.')).toBeInTheDocument()
  })

  it('client sans limite : aucune section historique (rien à tracer)', async () => {
    creditApi.getLimites.mockResolvedValue({ data: [] })
    renderPage()
    await waitFor(() => expect(creditApi.getLimites).toHaveBeenCalled())
    expect(screen.queryByTestId('credit-limite-historique')).toBeNull()
    expect(creditApi.getLimiteHistorique).not.toHaveBeenCalled()
  })
})
