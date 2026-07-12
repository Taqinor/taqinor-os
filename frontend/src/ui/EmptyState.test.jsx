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

describe('EmptyState — tone (VX131a) : un échec de chargement se DISTINGUE d’un « rien à afficher »', () => {
  it('tone="neutral" (défaut) : icône grise, bordure en pointillés — comportement historique inchangé', () => {
    const { container } = render(<EmptyState icon={Inbox} title="Aucune donnée" />)
    const root = container.firstChild
    expect(root.className).toContain('border-dashed')
    const iconWrap = container.querySelector('svg').parentElement
    expect(iconWrap.className).toContain('bg-muted')
    expect(iconWrap.className).toContain('text-muted-foreground')
  })

  it('tone="error" : icône sur fond destructif, même langage que ErrorBoundary', () => {
    const { container } = render(<EmptyState icon={Inbox} tone="error" title="Erreur de chargement" />)
    const root = container.firstChild
    expect(root.className).toContain('border-destructive/40')
    const iconWrap = container.querySelector('svg').parentElement
    expect(iconWrap.className).toContain('bg-destructive/12')
    expect(iconWrap.className).toContain('text-destructive')
  })

  it('tone="warning" : icône sur fond avertissement', () => {
    const { container } = render(<EmptyState icon={Inbox} tone="warning" title="Attention" />)
    const root = container.firstChild
    expect(root.className).toContain('border-warning/40')
    const iconWrap = container.querySelector('svg').parentElement
    expect(iconWrap.className).toContain('bg-warning/12')
    expect(iconWrap.className).toContain('text-warning')
  })
})

describe('EmptyState — action CTA (VX131b)', () => {
  it('rend l’action fournie (même CTA que la toolbar de la liste)', () => {
    render(
      <EmptyState title="Aucun client" action={<button type="button">Nouveau client</button>} />,
    )
    expect(screen.getByRole('button', { name: 'Nouveau client' })).toBeInTheDocument()
  })

  it('sans action fournie, ne rend aucun bouton', () => {
    render(<EmptyState title="Aucun client" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
