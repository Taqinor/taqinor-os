import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT141 — Brouillon de relance/réponse assisté (NTAI11) : depuis la fiche
   lead, un brouillon éditable est proposé (jamais envoyé seul) ; sans clé,
   un message explicite remplace le bouton — jamais un bouton mort ni une
   erreur brute. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { getLead, rediger } = vi.hoisted(() => ({
  getLead: vi.fn(() => Promise.resolve({ data: { id: 7, nom: 'Karim' } })),
  rediger: vi.fn(),
}))

vi.mock('../../../api/crmApi', () => ({ default: { getLead: (...a) => getLead(...a) } }))
vi.mock('../../../api/aiGovernanceApi', () => ({ default: { rediger: (...a) => rediger(...a) } }))
vi.mock('../../../features/crm/workspace/LeadWorkspace', () => ({
  default: () => <div data-testid="lead-workspace-stub" />,
}))

import LeadDetailPage from './LeadDetailPage'

beforeEach(() => { vi.clearAllMocks(); getLead.mockResolvedValue({ data: { id: 7, nom: 'Karim' } }) })

function withProviders() {
  return render(
    <MemoryRouter initialEntries={['/crm/leads/7']}>
      <ThemeProvider>
        <Routes>
          <Route path="/crm/leads/:id" element={<LeadDetailPage />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('LeadDetailPage — brouillon assisté (PACT141)', () => {
  it('propose un brouillon éditable, jamais envoyé automatiquement', async () => {
    rediger.mockResolvedValue({
      data: {
        content_type: 'crm.lead', object_id: 7, canal: 'email',
        brouillon: 'Bonjour, je reviens vers vous suite à notre échange…',
        entrees_fil: 3, envoye: false, source: 'groq',
      },
    })
    const user = userEvent.setup()
    withProviders()
    await screen.findByTestId('lead-workspace-stub')

    await user.click(screen.getByRole('button', { name: 'Générer un brouillon de relance' }))

    await waitFor(() => expect(rediger).toHaveBeenCalledWith(expect.objectContaining({
      content_type: 'crm.lead', object_id: '7', canal: 'email',
    })))
    const zone = await screen.findByLabelText('Brouillon éditable')
    expect(zone).toHaveValue('Bonjour, je reviens vers vous suite à notre échange…')
    expect(screen.getByText('Brouillon éditable — jamais envoyé automatiquement.')).toBeInTheDocument()
  })

  it('le brouillon reste ÉDITABLE avant tout envoi', async () => {
    rediger.mockResolvedValue({
      data: { brouillon: 'Version initiale', envoye: false },
    })
    const user = userEvent.setup()
    withProviders()
    await screen.findByTestId('lead-workspace-stub')
    await user.click(screen.getByRole('button', { name: 'Générer un brouillon de relance' }))

    const zone = await screen.findByLabelText('Brouillon éditable')
    await user.type(zone, ' — édité par la commerciale')
    expect(zone).toHaveValue('Version initiale — édité par la commerciale')
  })

  it('sans clé LLM configurée, le message serveur remplace le bouton (jamais un bouton mort)', async () => {
    rediger.mockRejectedValue({
      response: {
        status: 503,
        data: {
          detail: "Aucun fournisseur LLM n'est configuré (clé absente) — "
            + 'rédaction manuelle requise.',
        },
      },
    })
    const user = userEvent.setup()
    withProviders()
    await screen.findByTestId('lead-workspace-stub')
    await user.click(screen.getByRole('button', { name: 'Générer un brouillon de relance' }))

    expect(await screen.findByText(
      "Aucun fournisseur LLM n'est configuré (clé absente) — rédaction manuelle requise.",
    )).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Générer un brouillon de relance' })).not.toBeInTheDocument()
  })
})
