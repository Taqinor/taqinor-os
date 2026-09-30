// QJR534 — le panneau devis du cockpit lead : « Édition complète » seulement si
// le serveur dit le devis modifiable, sinon « Réviser » ; un envoyé s'ouvre en
// édition sur SON id (DevisGenerator monté avec editId). Droits lus de
// l'exemple COMMITTÉ `devis_modifiabilite.json` (PACT10).
// Run : npx vitest run src/pages/crm/leads/LeadDevisPanelEdition.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(),
    // Aperçu jamais résolu : seul l'état des boutons est sous test.
    getProposalPdf: vi.fn(() => new Promise(() => {})),
    reviserDevis: vi.fn(),
  },
}))
vi.mock('../../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../ventes/DevisGenerator', () => ({
  default: ({ editId }) => <div data-testid="generateur-monte">editId={String(editId)}</div>,
}))

import ventesApi from '../../../api/ventesApi'
import LeadDevisPanel from './LeadDevisPanel'

const LEAD = { id: 77, nom: 'Khalid' }

function rendre(props = {}) {
  const store = configureStore({ reducer: { r: (s = {}) => s } })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <LeadDevisPanel lead={LEAD} mode="view" onClose={vi.fn()} existingDevisId={414} {...props} />
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.getProposalPdf.mockImplementation(() => new Promise(() => {}))
})

describe('QJR534 — LeadDevisPanel : Édition complète ou Réviser selon le serveur', () => {
  it('accepté → pas d\'« Édition complète », « Réviser » présent et appelle le serveur', async () => {
    ventesApi.getDevisById.mockResolvedValue({
      data: exempleContrat('ventes', 'devis_modifiabilite', 'exemple_accepte'),
    })
    ventesApi.reviserDevis.mockResolvedValue({ data: { id: 99, reference: 'DEV-V2' } })
    rendre()
    const reviser = await screen.findByRole('button', { name: /Réviser/ })
    expect(screen.queryByRole('button', { name: /Édition complète/ })).toBeNull()
    await userEvent.click(reviser)
    await waitFor(() => expect(ventesApi.reviserDevis).toHaveBeenCalledWith(414))
  })

  it('envoyé → « Édition complète » ; le clic monte DevisGenerator avec editId', async () => {
    ventesApi.getDevisById.mockResolvedValue({
      data: exempleContrat('ventes', 'devis_modifiabilite', 'exemple_envoye'),
    })
    rendre({ existingDevisId: 413 })
    const edition = await screen.findByRole('button', { name: /Édition complète/ })
    expect(screen.queryByRole('button', { name: /Réviser/ })).toBeNull()
    await userEvent.click(edition)
    expect((await screen.findByTestId('generateur-monte')).textContent).toBe('editId=413')
  })

  it('mode edit sur un devis existant → ouvre directement l\'édition sur son id', async () => {
    ventesApi.getDevisById.mockResolvedValue({
      data: exempleContrat('ventes', 'devis_modifiabilite', 'exemple_envoye'),
    })
    rendre({ existingDevisId: 413, mode: 'edit' })
    expect((await screen.findByTestId('generateur-monte')).textContent).toBe('editId=413')
  })
})
