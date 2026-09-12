import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* NTAI10 — Copilote contextuel de fiche.
   Ce qui compte : le résumé et les actions s'affichent, l'indisponibilité
   (503 sans clé LLM) est dite en français SANS casser les actions, et le
   composant ne parle à personne quand l'URL ne désigne aucune fiche. */

const { resumeFiche, prochainesActions, rediger } = vi.hoisted(() => ({
  resumeFiche: vi.fn(() => Promise.resolve({
    data: { resume: 'Lead en attente de relance depuis 5 jours.', faits: {} },
  })),
  prochainesActions: vi.fn(() => Promise.resolve({
    data: {
      execute: false,
      actions: [
        { action: 'relancer', label: 'Relancer le client', priorite: 70,
          raison: 'Devis en attente depuis 5 j',
          action_key: 'crm.lead.whatsapp_prepare' },
      ],
    },
  })),
  rediger: vi.fn(() => Promise.resolve({
    data: { brouillon: 'Bonjour, …', envoye: false },
  })),
}))

vi.mock('../../api/aiGovernanceApi', () => ({
  default: { resumeFiche, prochainesActions, rediger },
}))

import CopilotContext, { ficheDepuisChemin } from './CopilotContext'

function renderAt(chemin) {
  const store = configureStore({
    reducer: { ia: (state = {}) => state },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[chemin]}>
        <CopilotContext />
      </MemoryRouter>
    </Provider>,
  )
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ficheDepuisChemin (NTAI10)', () => {
  it('reconnaît une fiche lead et un contrat', () => {
    expect(ficheDepuisChemin('/crm/leads/12')).toEqual({
      contentType: 'crm.lead', objectId: 12,
    })
    expect(ficheDepuisChemin('/contrats/7')).toEqual({
      contentType: 'contrats.contrat', objectId: 7,
    })
  })

  it('ne reconnaît rien ailleurs', () => {
    expect(ficheDepuisChemin('/crm/leads')).toBeNull()
    expect(ficheDepuisChemin('/parametres')).toBeNull()
    expect(ficheDepuisChemin('')).toBeNull()
  })
})

describe('CopilotContext (NTAI10)', () => {
  it('affiche le résumé et les actions de la fiche ouverte', async () => {
    renderAt('/crm/leads/12')

    expect(await screen.findByText(
      'Lead en attente de relance depuis 5 jours.')).toBeInTheDocument()
    expect(screen.getByText('Relancer le client')).toBeInTheDocument()
    expect(resumeFiche).toHaveBeenCalledWith({
      content_type: 'crm.lead', object_id: 12,
    })
  })

  it('dit l\'indisponibilité sans perdre les actions', async () => {
    resumeFiche.mockReturnValueOnce(Promise.reject({
      response: { status: 503, data: { detail: 'Résumé indisponible.' } },
    }))
    renderAt('/crm/leads/12')

    expect(await screen.findByText('Résumé indisponible.')).toBeInTheDocument()
    expect(screen.getByText('Relancer le client')).toBeInTheDocument()
  })

  it('ne parle à personne hors d\'une fiche', () => {
    const { container } = renderAt('/parametres')
    expect(container).toBeEmptyDOMElement()
    expect(resumeFiche).not.toHaveBeenCalled()
  })
})
