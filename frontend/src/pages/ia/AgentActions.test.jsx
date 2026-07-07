import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* WR8 — Le catalogue d'actions de l'assistant (AG1) liste les actions que
   l'utilisateur peut déclencher, depuis GET /api/django/agent/actions/, avec
   recherche. Métadonnées seules — aucune exécution ici.

   YHARD2 — un rôle non-admin/Directeur voit UNIQUEMENT le catalogue (pas
   d'onglet Historique) ; les tests dédiés à l'historique/annulation vivent
   dans AgentActions.historique.test.jsx. */

vi.mock('../../api/iaApi', () => ({
  default: {
    getAgentActions: vi.fn(() => Promise.resolve({
      data: {
        count: 2,
        actions: [
          {
            key: 'ventes.devis.send_whatsapp', label: 'Envoyer le devis par WhatsApp',
            description: 'Prépare un lien WhatsApp vers le client.',
            method: 'POST', required_permission: 'devis_envoyer', risk: 'outward',
          },
          {
            key: 'ventes.devis.proposal_pdf', label: 'Générer le PDF du devis',
            description: 'Produit le PDF premium du devis.',
            method: 'GET', required_permission: null, risk: 'internal',
          },
        ],
      },
    })),
    getAgentActionLogs: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    undoAgentAction: vi.fn(),
  },
}))

import iaApi from '../../api/iaApi'
import AgentActions from './AgentActions'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderWithRole(role = 'normal') {
  const store = configureStore({
    reducer: { auth: (state = { role, role_nom: '' }) => state },
  })
  return render(
    <Provider store={store}><AgentActions /></Provider>,
  )
}

describe('AgentActions (WR8 — catalogue d\'actions de l\'assistant)', () => {
  it('liste les actions autorisées avec leur niveau de risque', async () => {
    renderWithRole('normal')

    expect(await screen.findByText('Envoyer le devis par WhatsApp')).toBeInTheDocument()
    expect(screen.getByText('Générer le PDF du devis')).toBeInTheDocument()
    // Teintes de risque FR.
    expect(screen.getByText('Sortant')).toBeInTheDocument()
    expect(screen.getByText('Interne')).toBeInTheDocument()

    expect(iaApi.getAgentActions).toHaveBeenCalled()
  })

  it('filtre les actions via la recherche', async () => {
    renderWithRole('normal')
    await screen.findByText('Envoyer le devis par WhatsApp')

    await userEvent.type(screen.getByRole('searchbox', { name: 'Rechercher une action' }), 'whatsapp')

    expect(screen.getByText('Envoyer le devis par WhatsApp')).toBeInTheDocument()
    expect(screen.queryByText('Générer le PDF du devis')).not.toBeInTheDocument()
  })

  it('un rôle non-admin ne voit pas l\'onglet Historique / annuler', async () => {
    renderWithRole('normal')
    await screen.findByText('Envoyer le devis par WhatsApp')
    expect(screen.queryByRole('tab', { name: 'Historique / annuler' })).not.toBeInTheDocument()
  })
})
