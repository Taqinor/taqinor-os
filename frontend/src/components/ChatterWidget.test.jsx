import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

vi.mock('../api/recordsApi', () => ({
  default: {
    getComments: vi.fn(() => Promise.resolve({ data: [
      { id: 1, body: 'Bonjour', author_display: 'Sami', author_username: 'sami', created_at: '2026-06-21T09:00:00' },
    ] })),
    createComment: vi.fn(),
    deleteComment: vi.fn(),
  },
}))

import recordsApi from '../api/recordsApi'
import ChatterWidget from './ChatterWidget'

function renderWidget(user = { username: 'sami', role: 'commerciale' }) {
  const store = configureStore({ reducer: { auth: () => ({ user }) } })
  return render(
    <Provider store={store}>
      <ChatterWidget model="crm.lead" id={1} />
    </Provider>,
  )
}

describe('ChatterWidget (VX196)', () => {
  it('annonce la liste des commentaires via une région log/live', async () => {
    renderWidget()
    expect(await screen.findByText('Bonjour')).toBeInTheDocument()
    const log = screen.getByText('Bonjour').closest('[role="log"]')
    expect(log).not.toBeNull()
    expect(log).toHaveAttribute('aria-live', 'polite')
    expect(log).toHaveAttribute('aria-relevant', 'additions')
  })

  it('le bouton supprimer a un aria-label explicite (le title reste pour VX52)', async () => {
    renderWidget()
    const btn = await screen.findByLabelText('Supprimer le commentaire')
    expect(btn).toHaveAttribute('title', 'Supprimer')
  })

  it('VX204 — un échec de chargement affiche un message + Réessayer (jamais une liste vide muette)', async () => {
    recordsApi.getComments.mockRejectedValueOnce(new Error('boom'))
    renderWidget()
    expect(await screen.findByRole('alert')).toHaveTextContent('Impossible de charger les commentaires.')
    expect(screen.queryByText('Aucun commentaire.')).not.toBeInTheDocument()

    // Réessayer relance le chargement et efface l'erreur en cas de succès.
    recordsApi.getComments.mockResolvedValueOnce({ data: [
      { id: 2, body: 'Ça marche', author_display: 'Sami', author_username: 'sami', created_at: '2026-06-21T09:00:00' },
    ] })
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByText('Ça marche')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('VX204 — un échec d\'envoi de commentaire affiche un message d\'erreur visible', async () => {
    recordsApi.createComment.mockRejectedValueOnce(new Error('boom'))
    renderWidget()
    await screen.findByText('Bonjour')
    fireEvent.change(screen.getByPlaceholderText(/Ajouter un commentaire/), { target: { value: 'salut' } })
    fireEvent.click(screen.getByTitle('Envoyer (Ctrl+Entrée)'))
    await waitFor(() => {
      expect(screen.getByText('Envoi impossible — réessayez.')).toBeInTheDocument()
    })
  })
})
