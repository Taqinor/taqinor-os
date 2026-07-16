import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// AG3 — mock du client IA : la confirmation ne doit pas toucher le réseau.
vi.mock('../../api/iaApi', () => ({
  default: {
    queryAgent: vi.fn(() => Promise.resolve({ data: { answer: '' } })),
    getChatHistory: vi.fn(() => Promise.resolve({ data: [] })),
    clearChatHistory: vi.fn(() => Promise.resolve({})),
    confirmAction: vi.fn(() =>
      Promise.resolve({
        data: {
          ok: true,
          action_key: 'ventes.devis.send_whatsapp',
          detail: 'Action exécutée.',
          data: { reference: 'DEV-2026-07-0007', wa_url: 'https://wa.me/212600000000', devis_id: 9 },
        },
      }),
    ),
  },
}))

import iaApi from '../../api/iaApi'
import iaReducer, {
  parseStructuredPayload,
  buildAgentMessage,
  dismissProposal,
} from '../../features/ia/store/iaSlice'
import AgentChat from './AgentChat'

// jsdom n'implémente pas scrollIntoView (appelé dans un effet d'auto-scroll).
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

// Mock déterministe de matchMedia (prefers-reduced-motion) — surchargé par
// test via `mockMatchMedia`.
function mockMatchMedia(reduced) {
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: reduced,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}

/* ── Couche LOGIQUE : normalisation des payloads agent (proposition / résultat) ── */
describe('iaSlice — normalisation des messages agent (AG3)', () => {
  it('parseStructuredPayload extrait un objet proposition encadré de texte', () => {
    const txt = 'Voici la proposition : {"type":"proposal","action_key":"x","confirm_token":"t1"} merci.'
    expect(parseStructuredPayload(txt)).toMatchObject({ type: 'proposal', confirm_token: 't1' })
  })

  it('parseStructuredPayload renvoie null pour du texte simple', () => {
    expect(parseStructuredPayload('Bonjour, voici votre réponse.')).toBeNull()
    expect(parseStructuredPayload('')).toBeNull()
    expect(parseStructuredPayload(null)).toBeNull()
  })

  it('buildAgentMessage rend une carte proposition depuis un champ dédié', () => {
    const msg = buildAgentMessage({
      answer: 'Confirmation requise.',
      proposal: { type: 'proposal', action_key: 'ventes.devis.proposal_pdf', human_preview: 'Produire le PDF.', confirm_token: 'tok-123' },
    })
    expect(msg.kind).toBe('proposal')
    expect(msg.confirm_token).toBe('tok-123')
    expect(msg.human_preview).toBe('Produire le PDF.')
  })

  it('buildAgentMessage rend une carte résultat avec référence + wa_url + lien /proposal', () => {
    const msg = buildAgentMessage({
      answer: 'Fait.',
      result: { type: 'result', action_key: 'ventes.devis.send_whatsapp', data: { reference: 'DEV-7', wa_url: 'https://wa.me/2126', devis_id: 42 } },
    })
    expect(msg.kind).toBe('result')
    expect(msg.reference).toBe('DEV-7')
    expect(msg.wa_url).toBe('https://wa.me/2126')
    expect(msg.proposal_url).toBe('/api/django/ventes/devis/42/proposal/')
  })

  it('buildAgentMessage retombe sur un message texte simple (N86) sans payload structuré', () => {
    const msg = buildAgentMessage({ answer: 'Réponse normale.', action_performed: true })
    expect(msg.kind).toBeUndefined()
    expect(msg.content).toBe('Réponse normale.')
    expect(msg.action_performed).toBe(true)
  })

  it('dismissProposal transforme la carte en message texte écarté', () => {
    const state = {
      ...iaReducer(undefined, { type: '@@INIT' }),
      messages: [{ role: 'agent', kind: 'proposal', content: 'C', confirm_token: 't' }],
    }
    const next = iaReducer(state, dismissProposal(0))
    expect(next.messages[0].kind).toBeUndefined()
    expect(next.messages[0].dismissed).toBe(true)
  })
})

/* ── Couche COMPOSANT : rendu des cartes + boutons câblés ── */
function makeStore(messages) {
  return configureStore({
    reducer: { ia: iaReducer },
    preloadedState: {
      ia: { ...iaReducer(undefined, { type: '@@INIT' }), messages },
    },
  })
}

describe('AgentChat — cartes proposition / résultat (AG3)', () => {
  beforeEach(() => {
    iaApi.confirmAction.mockClear()
  })

  it('rend une carte de proposition avec Confirmer/Annuler et le preview', () => {
    const store = makeStore([
      { role: 'agent', kind: 'proposal', content: '', human_preview: 'Envoyer le devis par WhatsApp ?', confirm_token: 'tok-9' },
    ])
    render(<Provider store={store}><AgentChat /></Provider>)
    const card = screen.getByTestId('proposal-card')
    expect(within(card).getByText(/Envoyer le devis par WhatsApp/)).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: /Confirmer/ })).toBeEnabled()
    expect(within(card).getByRole('button', { name: /Annuler/ })).toBeInTheDocument()
  })

  it('Confirmer appelle confirmAction avec le token et remplace la carte par le résultat', async () => {
    const store = makeStore([
      { role: 'agent', kind: 'proposal', content: '', human_preview: 'Envoyer ?', confirm_token: 'tok-9' },
    ])
    render(<Provider store={store}><AgentChat /></Provider>)
    await userEvent.click(screen.getByRole('button', { name: /Confirmer/ }))
    expect(iaApi.confirmAction).toHaveBeenCalledWith('tok-9')
    // La carte proposition est remplacée par une carte résultat.
    const result = await screen.findByTestId('result-card')
    expect(within(result).getByText(/DEV-2026-07-0007/)).toBeInTheDocument()
  })

  it('Annuler écarte la carte sans appel réseau', async () => {
    const store = makeStore([
      { role: 'agent', kind: 'proposal', content: 'msg', human_preview: 'Envoyer ?', confirm_token: 'tok-9' },
    ])
    render(<Provider store={store}><AgentChat /></Provider>)
    await userEvent.click(screen.getByRole('button', { name: /Annuler/ }))
    expect(iaApi.confirmAction).not.toHaveBeenCalled()
    expect(screen.queryByTestId('proposal-card')).not.toBeInTheDocument()
  })

  it('rend une carte résultat avec liens PDF (/proposal) et WhatsApp fonctionnels', () => {
    const store = makeStore([
      {
        role: 'agent', kind: 'result', content: '',
        reference: 'DEV-2026-07-0007',
        wa_url: 'https://wa.me/212600000000',
        proposal_url: '/api/django/ventes/devis/9/proposal/',
      },
    ])
    render(<Provider store={store}><AgentChat /></Provider>)
    const card = screen.getByTestId('result-card')
    expect(within(card).getByText(/DEV-2026-07-0007/)).toBeInTheDocument()
    const pdf = within(card).getByRole('link', { name: /Télécharger le devis/ })
    expect(pdf).toHaveAttribute('href', '/api/django/ventes/devis/9/proposal/')
    const wa = within(card).getByRole('link', { name: /Ouvrir WhatsApp/ })
    expect(wa).toHaveAttribute('href', 'https://wa.me/212600000000')
  })

  it('carte proposition sans token : Confirmer désactivé', () => {
    const store = makeStore([
      { role: 'agent', kind: 'proposal', content: '', human_preview: 'X', confirm_token: null },
    ])
    render(<Provider store={store}><AgentChat /></Provider>)
    expect(screen.getByRole('button', { name: /Confirmer/ })).toBeDisabled()
  })
})

/* ── VX37 — reveal incrémental + mini-tableau de lignes structurées ── */
describe('AgentChat — reveal texte + mini-tableau (VX37)', () => {
  it('reduced-motion : le texte du dernier message agent est instantané', () => {
    mockMatchMedia(true)
    const store = makeStore([
      { role: 'agent', content: 'Réponse complète immédiate.' },
    ])
    render(<Provider store={store}><AgentChat /></Provider>)
    expect(screen.getByText('Réponse complète immédiate.')).toBeInTheDocument()
  })

  it('rend un mini-tableau inline quand le message porte des lignes structurées', () => {
    mockMatchMedia(true)
    const store = makeStore([
      {
        role: 'agent',
        content: 'Voici les produits en rupture.',
        rows: [
          { produit: 'Panneau 450W', stock: 0 },
          { produit: 'Onduleur 5kW', stock: 2 },
        ],
      },
    ])
    render(<Provider store={store}><AgentChat /></Provider>)
    const table = screen.getByTestId('structured-rows-table')
    expect(within(table).getByText('produit')).toBeInTheDocument()
    expect(within(table).getByText('Panneau 450W')).toBeInTheDocument()
    expect(within(table).getByText('Onduleur 5kW')).toBeInTheDocument()
  })

  it('pas de mini-tableau quand aucune ligne structurée n\'est portée', () => {
    mockMatchMedia(true)
    const store = makeStore([
      { role: 'agent', content: 'Réponse texte simple.' },
    ])
    render(<Provider store={store}><AgentChat /></Provider>)
    expect(screen.queryByTestId('structured-rows-table')).not.toBeInTheDocument()
  })
})
