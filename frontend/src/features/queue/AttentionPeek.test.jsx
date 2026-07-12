import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import AttentionPeek from './AttentionPeek'

/* VX217(a) — <AttentionPeek> : aperçu SANS naviguer, jamais `prix_achat`. */

describe('AttentionPeek', () => {
  it('n’affiche rien de plus que l’enfant tant qu’aucun survol/appui', () => {
    render(
      <AttentionPeek item={{ title: 'Relancer X', link: '/crm/leads?lead=1' }}>
        <button type="button">Relancer X</button>
      </AttentionPeek>,
    )
    expect(screen.getByRole('button', { name: 'Relancer X' })).toBeInTheDocument()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('le survol (desktop) affiche l’aperçu SANS navigation (pas d’appel à onOpen)', () => {
    const onOpen = vi.fn()
    render(
      <AttentionPeek
        item={{
          title: 'Relancer X', client_nom: 'ACME', montant: 15000,
          due: '2026-08-01', link: '/crm/leads?lead=1',
        }}
        onOpen={onOpen}>
        <button type="button">Relancer X</button>
      </AttentionPeek>,
    )
    fireEvent.mouseEnter(screen.getByRole('button').parentElement)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    expect(screen.getByText('ACME')).toBeInTheDocument()
    expect(screen.getByText('15000 DH')).toBeInTheDocument()
    expect(onOpen).not.toHaveBeenCalled()
  })

  it('ne rend JAMAIS prix_achat même si l’objet le porterait par erreur', () => {
    render(
      <AttentionPeek
        item={{
          title: 'Item', client_nom: 'ACME', montant: 100,
          prix_achat: 42, link: '/x',
        }}>
        <button type="button">Item</button>
      </AttentionPeek>,
    )
    fireEvent.mouseEnter(screen.getByRole('button').parentElement)
    expect(screen.queryByText(/42/)).not.toBeInTheDocument()
  })

  it('« Ouvrir » appelle onOpen avec l’item (navigation explicite, pas automatique)', () => {
    const onOpen = vi.fn()
    render(
      <AttentionPeek item={{ title: 'X', link: '/crm/leads?lead=1' }} onOpen={onOpen}>
        <button type="button">X</button>
      </AttentionPeek>,
    )
    fireEvent.mouseEnter(screen.getByRole('button').parentElement)
    fireEvent.click(screen.getByRole('button', { name: 'Ouvrir' }))
    expect(onOpen).toHaveBeenCalledTimes(1)
    expect(onOpen.mock.calls[0][0].link).toBe('/crm/leads?lead=1')
  })

  it('sans item, rend simplement les enfants (dégradation gracieuse)', () => {
    render(
      <AttentionPeek item={null}>
        <button type="button">Sans peek</button>
      </AttentionPeek>,
    )
    expect(screen.getByRole('button', { name: 'Sans peek' })).toBeInTheDocument()
  })
})
