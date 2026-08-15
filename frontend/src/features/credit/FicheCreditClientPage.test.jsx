import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* WIR186 — la limite de crédit n'était modifiable NULLE PART : le wizard
   appelait toujours `createLimite`, et `LimiteCredit` étant unique par
   (société, client), une seconde définition partait en erreur d'intégrité.
   L'historique NTCRD22 (`/credit/limites/<id>/historique/`) n'avait lui aucun
   consommateur.

   Charges utiles alignées sur les sérialiseurs serveur réels
   (`LimiteCreditSerializer` : id/client/montant_limite/mode_hold,
   l'historique : {count, entries[{id, kind, field, field_label, old_value,
   new_value, body, created_at, acteur}]}). */

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
  client_id: 7, client_nom: 'ACME', encours: '12000.00',
  lettre_score: 'B', montant_limite: '50000.00', disponible: '38000.00',
}

const LIMITE = {
  id: 42, client: 7, montant_limite: '50000.00', mode_hold: 'avertissement',
}

const HISTORIQUE = {
  count: 1,
  entries: [{
    id: 5, kind: 'field_change', field: 'montant_limite',
    field_label: 'Montant de la limite', old_value: '30000.00',
    new_value: '50000.00', body: '', created_at: '2026-07-01T09:00:00Z',
    acteur: 'reda',
  }],
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/credit/clients/7']}>
      <Routes>
        <Route path="/credit/clients/:id" element={<FicheCreditClientPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  creditApi.getFicheClient.mockResolvedValue({ data: FICHE })
  creditApi.getLimiteSuggeree.mockResolvedValue({ data: { suggestion: '60000' } })
  creditApi.getLimiteHistorique.mockResolvedValue({ data: HISTORIQUE })
})
afterEach(() => { cleanup() })

async function ouvrirWizardJusquAuBout(user) {
  await user.click(await screen.findByRole('button', { name: /limite/i }))
  await user.click(await screen.findByRole('button', { name: 'Suivant' }))
  await user.click(await screen.findByRole('button', { name: 'Suivant' }))
}

describe('FicheCreditClientPage — limite modifiable (WIR186)', () => {
  it('limite EXISTANTE : le wizard la MODIFIE, jamais une seconde création', async () => {
    creditApi.getLimites.mockResolvedValue({ data: [LIMITE] })
    creditApi.updateLimite.mockResolvedValue({ data: { ...LIMITE, montant_limite: '70000' } })
    const user = userEvent.setup()
    renderPage()

    // Le libellé du bouton dit ce qui va se passer.
    expect(await screen.findByRole('button', { name: 'Modifier la limite' }))
      .toBeInTheDocument()

    await ouvrirWizardJusquAuBout(user)
    await user.click(screen.getByRole('button', { name: 'Enregistrer la limite' }))

    await waitFor(() => expect(creditApi.updateLimite).toHaveBeenCalledTimes(1))
    expect(creditApi.updateLimite.mock.calls[0][0]).toBe(42)
    // LA garde : aucune seconde création, donc aucune erreur d'intégrité.
    expect(creditApi.createLimite).not.toHaveBeenCalled()
  })

  it('AUCUNE limite : le wizard crée (comportement historique préservé)', async () => {
    creditApi.getLimites.mockResolvedValue({ data: [] })
    creditApi.createLimite.mockResolvedValue({ data: LIMITE })
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByRole('button', { name: 'Définir la limite' }))
      .toBeInTheDocument()

    await ouvrirWizardJusquAuBout(user)
    await user.click(screen.getByRole('button', { name: 'Valider la limite' }))

    await waitFor(() => expect(creditApi.createLimite).toHaveBeenCalledTimes(1))
    expect(creditApi.createLimite.mock.calls[0][0]).toMatchObject({ client: 7 })
    expect(creditApi.updateLimite).not.toHaveBeenCalled()
  })

  it('rend l’historique NTCRD22 de la limite', async () => {
    creditApi.getLimites.mockResolvedValue({ data: [LIMITE] })
    renderPage()

    expect(await screen.findByText('Historique de la limite')).toBeInTheDocument()
    await waitFor(() => expect(creditApi.getLimiteHistorique).toHaveBeenCalledWith(42))
    expect(await screen.findByText(/Montant de la limite/)).toBeInTheDocument()
    expect(screen.getByText(/30000\.00 → 50000\.00/)).toBeInTheDocument()
    expect(screen.getByText(/par reda/)).toBeInTheDocument()
  })

  it('sans limite : pas de section historique, aucun appel historique', async () => {
    creditApi.getLimites.mockResolvedValue({ data: [] })
    renderPage()

    await screen.findByRole('button', { name: 'Définir la limite' })
    expect(screen.queryByText('Historique de la limite')).toBeNull()
    expect(creditApi.getLimiteHistorique).not.toHaveBeenCalled()
  })

  it('400 métier sur la modification : message FR, jamais du JSON brut', async () => {
    creditApi.getLimites.mockResolvedValue({ data: [LIMITE] })
    creditApi.updateLimite.mockRejectedValue({
      response: { status: 400, data: { montant_limite: ['Montant invalide.'] } },
    })
    const user = userEvent.setup()
    renderPage()

    await ouvrirWizardJusquAuBout(user)
    await user.click(screen.getByRole('button', { name: 'Enregistrer la limite' }))

    const alerte = await screen.findByRole('alert')
    expect(alerte).toBeInTheDocument()
    expect(alerte.textContent).not.toMatch(/\{"montant_limite"/)
  })
})
