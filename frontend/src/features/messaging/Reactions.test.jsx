import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Reactions from './Reactions'

const CURATED = ['👍', '❤️', '😂', '🎉', '✅']

describe('Reactions (S18)', () => {
  it('agrège une liste plate par emoji avec count + état mine', () => {
    render(
      <Reactions
        reactions={[
          { id: 1, user: 7, emoji: '👍' },
          { id: 2, user: 9, emoji: '👍' },
          { id: 3, user: 9, emoji: '❤️' },
        ]}
        currentUserId={7}
        onToggle={vi.fn()}
      />,
    )
    // 👍 → 2 réactions dont la mienne, ❤️ → 1 réaction (pas la mienne).
    expect(screen.getByLabelText('👍 2 (vous avez réagi)')).toBeInTheDocument()
    expect(screen.getByLabelText('❤️ 1')).toBeInTheDocument()
  })

  it('compare l’utilisateur de façon souple (string vs number)', () => {
    render(<Reactions reactions={[{ id: 1, user: '7', emoji: '✅' }]} currentUserId={7} onToggle={vi.fn()} />)
    expect(screen.getByLabelText('✅ 1 (vous avez réagi)')).toBeInTheDocument()
  })

  it('ignore les lignes sans emoji et une entrée nulle', () => {
    const { container } = render(<Reactions reactions={null} currentUserId={1} onToggle={vi.fn()} />)
    // Aucune puce, seulement le bouton « Ajouter une réaction ».
    expect(container.querySelectorAll('.chat-reaction-chip').length).toBe(0)
  })

  it('cliquer une puce bascule cet emoji', async () => {
    const onToggle = vi.fn()
    render(<Reactions reactions={[{ id: 1, user: 7, emoji: '👍' }]} currentUserId={7} onToggle={onToggle} />)
    await userEvent.click(screen.getByLabelText('👍 1 (vous avez réagi)'))
    expect(onToggle).toHaveBeenCalledWith('👍')
  })

  it('le sélecteur propose le jeu curaté et n’utilise aucune lib de picker', async () => {
    const onToggle = vi.fn()
    render(<Reactions reactions={[]} currentUserId={1} onToggle={onToggle} />)
    await userEvent.click(screen.getByLabelText('Ajouter une réaction'))
    for (const emoji of CURATED) {
      expect(await screen.findByLabelText(`Réagir avec ${emoji}`)).toBeInTheDocument()
    }
    await userEvent.click(screen.getByLabelText('Réagir avec ❤️'))
    expect(onToggle).toHaveBeenCalledWith('❤️')
  })
})
