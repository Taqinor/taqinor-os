import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MessageBubble from './MessageBubble'

describe('MessageBubble (S15)', () => {
  it('rend le corps, l’auteur et l’heure pour un message d’un autre', () => {
    render(
      <MessageBubble
        message={{ id: 1, body: 'Bonjour', created_at: '2026-06-21T08:07:00', sender: { id: 2, username: 'sami' } }}
        own={false}
      />,
    )
    expect(screen.getByText('Bonjour')).toBeInTheDocument()
    expect(screen.getByText('sami')).toBeInTheDocument()
    expect(screen.getByText('08:07')).toBeInTheDocument()
  })

  it('affiche le slot pièce jointe (fichier)', () => {
    render(
      <MessageBubble
        message={{ id: 1, body: '', created_at: 'x', sender: { id: 2 },
          attachments: [{ id: 7, name: 'devis.pdf', content_type: 'application/pdf', url: '/f/7' }] }}
        own
      />,
    )
    expect(screen.getByText('devis.pdf')).toBeInTheDocument()
  })

  it('un message supprimé affiche un placeholder', () => {
    render(<MessageBubble message={{ id: 1, deleted: true, created_at: 'x' }} own />)
    expect(screen.getByText('Message supprimé')).toBeInTheDocument()
  })

  it('édition / suppression disponibles uniquement pour ses propres messages', async () => {
    const onEdit = vi.fn(); const onDelete = vi.fn()
    render(
      <MessageBubble
        message={{ id: 1, body: 'à moi', created_at: 'x', sender: { id: 2 } }}
        own onEdit={onEdit} onDelete={onDelete}
      />,
    )
    await userEvent.click(screen.getByLabelText('Modifier'))
    await userEvent.click(screen.getByLabelText('Supprimer'))
    expect(onEdit).toHaveBeenCalled()
    expect(onDelete).toHaveBeenCalled()
  })
})
