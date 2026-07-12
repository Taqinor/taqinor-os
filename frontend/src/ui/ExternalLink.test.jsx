import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ExternalLink } from './ExternalLink'

/* VX177 — un chemin interne (`/…`) doit passer par react-router (jamais un
   `<a href>` nu qui ÉJECTE hors de la coquille PWA standalone) ; un chemin
   externe garde `target="_blank"` + `noopener` (comportement voulu — ouvre
   un onglet sans quitter la coquille). */
describe('VX177 — ExternalLink', () => {
  it('chemin interne (commence par /) -> <a> react-router, jamais target=_blank', () => {
    render(
      <MemoryRouter>
        <ExternalLink href="/crm/leads">Voir les leads</ExternalLink>
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: 'Voir les leads' })
    expect(link).toHaveAttribute('href', '/crm/leads')
    expect(link).not.toHaveAttribute('target')
  })

  it('URL externe -> target=_blank + rel=noopener noreferrer', () => {
    render(
      <MemoryRouter>
        <ExternalLink href="https://icecnie.ma/rncicerecherche">Registre ICE</ExternalLink>
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: 'Registre ICE' })
    expect(link).toHaveAttribute('href', 'https://icecnie.ma/rncicerecherche')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })

  it('wa.me (protocol-relative absent, schéma https) reste externe', () => {
    render(
      <MemoryRouter>
        <ExternalLink href="https://wa.me/212600000000">WhatsApp</ExternalLink>
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'WhatsApp' })).toHaveAttribute('target', '_blank')
  })

  it('/api/… (fichier backend, pas une route SPA) reste target=_blank malgré le / initial', () => {
    render(
      <MemoryRouter>
        <ExternalLink href="/api/django/rh/bulletins/42/">Bulletin</ExternalLink>
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: 'Bulletin' })
    expect(link).toHaveAttribute('href', '/api/django/rh/bulletins/42/')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('/media/… (fichier backend) reste aussi target=_blank', () => {
    render(
      <MemoryRouter>
        <ExternalLink href="/media/documents/x.pdf">Document</ExternalLink>
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Document' })).toHaveAttribute('target', '_blank')
  })
})
