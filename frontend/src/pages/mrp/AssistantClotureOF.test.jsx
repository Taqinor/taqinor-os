// NTMFG28 — Assistant de clôture d'OF avec saisie qualité groupée. Test e2e
// léger : la saisie groupée des opérations restantes puis une SEULE
// confirmation appelle l'endpoint composite `cloture-assistee` (jamais un
// appel par opération depuis le frontend — le regroupement est le point).
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const { getOrdreFabrication, clotureAssisteeOF } = vi.hoisted(() => ({
  getOrdreFabrication: vi.fn(() => Promise.resolve({
    data: {
      id: 42,
      operations: [
        { id: 1, ordre: 1, libelle: 'Op 1', statut: 'a_faire' },
        { id: 2, ordre: 2, libelle: 'Op 2', statut: 'a_faire' },
        { id: 3, ordre: 3, libelle: 'Op déjà faite', statut: 'terminee' },
      ],
    },
  })),
  clotureAssisteeOF: vi.fn(() => Promise.resolve({
    data: { operations_terminees: [1, 2], erreurs: [] },
  })),
}))

vi.mock('../../api/mrpApi', () => ({
  default: { getOrdreFabrication, clotureAssisteeOF },
}))

import AssistantClotureOF from './AssistantClotureOF'

function renderWizard(ofId = '42') {
  return render(
    <MemoryRouter initialEntries={[`/mrp/ordres-fabrication/${ofId}/cloture-assistee`]}>
      <Routes>
        <Route path="/mrp/ordres-fabrication/:ofId/cloture-assistee" element={<AssistantClotureOF />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('AssistantClotureOF (NTMFG28)', () => {
  it('ne liste que les opérations NON terminées', async () => {
    renderWizard()
    expect(await screen.findByText('1. Op 1')).toBeInTheDocument()
    expect(screen.getByText('2. Op 2')).toBeInTheDocument()
    expect(screen.queryByText(/Op déjà faite/)).not.toBeInTheDocument()
  })

  it('saisie groupée puis confirmation UNIQUE appelle cloture-assistee avec toutes les lignes', async () => {
    const user = userEvent.setup()
    const { container } = renderWizard()
    await screen.findByText('1. Op 1')

    await user.type(container.querySelector('#bonne-1'), '5')
    await user.type(container.querySelector('#bonne-2'), '3')
    await user.type(container.querySelector('#rebut-2'), '2')

    await user.click(screen.getByRole('button', { name: /Vérifier et confirmer/ }))
    expect(clotureAssisteeOF).not.toHaveBeenCalled()

    await user.click(await screen.findByRole('button', { name: /Confirmer la clôture assistée/ }))

    await waitFor(() => expect(clotureAssisteeOF).toHaveBeenCalledTimes(1))
    expect(clotureAssisteeOF).toHaveBeenCalledWith('42', {
      operations: [
        { id: 1, quantite_bonne: '5', quantite_rebut: '0', motif_rebut: '' },
        { id: 2, quantite_bonne: '3', quantite_rebut: '2', motif_rebut: '' },
      ],
    })
    expect(await screen.findByText(/2 opération\(s\) terminée\(s\)/)).toBeInTheDocument()
  })

  it("dégrade proprement quand toutes les opérations sont déjà terminées", async () => {
    getOrdreFabrication.mockResolvedValueOnce({
      data: { id: 99, operations: [{ id: 1, ordre: 1, libelle: 'Op', statut: 'terminee' }] },
    })
    renderWizard('99')
    expect(await screen.findByText(/déjà terminées/)).toBeInTheDocument()
    expect(clotureAssisteeOF).not.toHaveBeenCalled()
  })
})
