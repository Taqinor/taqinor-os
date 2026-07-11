import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
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
})
