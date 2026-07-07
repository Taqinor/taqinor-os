import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* XPLT18 — "Générer une règle (IA)" : propose→confirme. La proposition
   appelle POST /api/django/agent/actions/automation-draft/ (via
   automationApi.proposeDraft) qui crée TOUJOURS une règle désactivée ; la
   confirmation reste le bouton "Activer" déjà existant de la liste. */

const { proposeDraft, getRules, getRuns, getApprovals, getTemplates } = vi.hoisted(() => ({
  proposeDraft: vi.fn(() => Promise.resolve({
    data: { id: 99, nom: 'Relance J+2', enabled: false, trigger_type: 'devis_accepted', action_type: 'create_activity' },
  })),
  getRules: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  getRuns: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  getApprovals: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  getTemplates: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('../../api/automationApi', () => ({
  default: { proposeDraft, getRules, getRuns, getApprovals, getTemplates },
}))

import AutomatisationsSection from './AutomatisationsSection'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AutomatisationsSection — XPLT18 générer une règle (IA)', () => {
  it('propose un brouillon désactivé et le signale confirmable', async () => {
    // delay:null — supprime le délai inter-frappe de userEvent : `user.type`
    // (30 caractères) + re-rendus Radix rendaient ce test lent (~9 s) et il
    // dépassait le timeout de 20 s sous forte charge parallèle. Sans délai il
    // tombe à ~1-2 s, avec une large marge.
    const user = userEvent.setup({ delay: null })
    render(<AutomatisationsSection />)

    await screen.findByText('Automatisations')
    await user.click(screen.getByRole('button', { name: /Générer une règle \(IA\)/ }))

    const desc = screen.getByPlaceholderText(/Décrivez la règle/)
    await user.type(desc, 'Relance J+2 après devis accepté')
    await user.click(screen.getByRole('button', { name: 'Proposer le brouillon' }))

    await waitFor(() => expect(proposeDraft).toHaveBeenCalledWith(expect.objectContaining({
      nom: 'Relance J+2 après devis accepté',
      trigger_type: 'lead_stage_change',
      action_type: 'create_activity',
    })))
    expect(await screen.findByText(/désactivé — activez-le/)).toBeInTheDocument()
    // Recharge la liste des règles après la proposition (pour voir le brouillon désactivé).
    expect(getRules).toHaveBeenCalledTimes(2)
  })

  it("refuse de proposer sans description", async () => {
    const user = userEvent.setup({ delay: null })
    render(<AutomatisationsSection />)

    await screen.findByText('Automatisations')
    await user.click(screen.getByRole('button', { name: /Générer une règle \(IA\)/ }))
    await user.click(screen.getByRole('button', { name: 'Proposer le brouillon' }))

    expect(await screen.findByText('Décrivez la règle souhaitée.')).toBeInTheDocument()
    expect(proposeDraft).not.toHaveBeenCalled()
  })
})
