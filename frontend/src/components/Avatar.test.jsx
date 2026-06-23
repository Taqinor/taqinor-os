import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import Avatar from './Avatar'

describe('Avatar — photo de profil (T-U13)', () => {
  it('rend la PHOTO via <img> quand une URL src est fournie', () => {
    render(<Avatar name="Reda Kasri" src="/api/django/users/avatar-image/?key=avatars/x.png" />)
    const img = screen.getByRole('img')
    expect(img).toBeInTheDocument()
    expect(img.getAttribute('src')).toBe('/api/django/users/avatar-image/?key=avatars/x.png')
  })

  it('retombe sur les INITIALES quand aucune URL n’est fournie', () => {
    render(<Avatar name="Reda Kasri" />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('RK')).toBeInTheDocument()
  })

  it('retombe proprement sur les initiales si l’image échoue à charger (onError)', () => {
    render(<Avatar name="Reda Kasri" src="/api/django/users/avatar-image/?key=avatars/broken.png" />)
    const img = screen.getByRole('img')
    // Simule un 404/erreur réseau sur la photo.
    fireEvent.error(img)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('RK')).toBeInTheDocument()
  })

  it('réessaie d’afficher la photo quand src change (nouvelle photo téléversée)', () => {
    const { rerender } = render(
      <Avatar name="Reda Kasri" src="/api/django/users/avatar-image/?key=avatars/old.png" />,
    )
    fireEvent.error(screen.getByRole('img'))
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    // Nouvelle URL → on retente l’<img>, plus les initiales.
    rerender(
      <Avatar name="Reda Kasri" src="/api/django/users/avatar-image/?key=avatars/new.png" />,
    )
    expect(screen.getByRole('img')).toBeInTheDocument()
  })
})
