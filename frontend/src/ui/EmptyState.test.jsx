import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Inbox } from 'lucide-react'
import { EmptyState } from './EmptyState'

// VX40 — Le délice mesuré : la variante `illustrated` remplace le cercle
// d'icône lucide par un pictogramme SVG solaire inline (aucune lib externe),
// réservée aux 4-5 écrans les plus vus. `icon` reste le comportement par
// défaut pour tous les autres écrans (aucune régression de rendu).

describe('EmptyState — variante illustrated (VX40)', () => {
  it('rend le pictogramme SVG solaire quand illustrated=true (icon ignoré)', () => {
    const { container } = render(
      <EmptyState illustrated icon={Inbox} title="Aucun devis" description="desc" />,
    )
    expect(screen.getByText('Aucun devis')).toBeTruthy()
    // Le pictogramme est un <svg> inline, pas l'icône lucide passée en prop.
    expect(container.querySelector('svg[viewBox="0 0 64 64"]')).toBeTruthy()
  })

  it('rend le cercle icône lucide classique par défaut (illustrated absent)', () => {
    const { container } = render(
      <EmptyState icon={Inbox} title="Aucune donnée" />,
    )
    expect(container.querySelector('svg[viewBox="0 0 64 64"]')).toBeFalsy()
    expect(container.querySelector('svg')).toBeTruthy()
  })

  it('sans icon ni illustrated, ne rend aucun pictogramme', () => {
    const { container } = render(<EmptyState title="Vide" />)
    expect(container.querySelector('svg')).toBeFalsy()
  })
})
