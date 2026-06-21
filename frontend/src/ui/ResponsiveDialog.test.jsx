import { describe, it, expect, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { ResponsiveDialog } from './ResponsiveDialog'

/* M158 — ResponsiveDialog : adaptateur Dialog (bureau ≥768 px) ↔ Sheet bas
   (mobile <768 px) bâti sur les primitifs existants. On simule `matchMedia`
   aux deux points de rupture et on vérifie quel chemin (modale centrée vs.
   tiroir bas) est rendu. */

// Pose un stub matchMedia déterministe : `mobile=true` => la requête
// `max-width` matche, donc le chemin Sheet ; `mobile=false` => Dialog.
function mockMatchMedia(mobile) {
  window.matchMedia = (query) => ({
    matches: mobile,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })
}

beforeAll(() => {
  // jsdom n'implémente pas matchMedia : on garantit sa présence.
  if (typeof window.matchMedia !== 'function') mockMatchMedia(false)
})

afterEach(() => {
  cleanup()
})

// Repère le conteneur Radix porté dans le <body> (les deux variantes utilisent
// un Portal) puis distingue Sheet (bas) de Dialog (centré) par leurs classes.
function getContent() {
  return document.querySelector('[role="dialog"]')
}

describe('ResponsiveDialog (primitif UI, M158)', () => {
  it('rend la modale Dialog centrée sur bureau (≥768 px)', () => {
    mockMatchMedia(false)
    render(
      <ResponsiveDialog open onOpenChange={() => {}} title="Titre bureau">
        <p>Contenu</p>
      </ResponsiveDialog>,
    )
    const content = getContent()
    expect(content).toBeTruthy()
    // Marqueurs propres au Dialog centré.
    expect(content.className).toContain('top-1/2')
    expect(content.className).toContain('-translate-y-1/2')
    expect(content.className).toContain('max-w-lg')
    // Pas les marqueurs de tiroir bas.
    expect(content.className).not.toContain('rounded-t-2xl')
    expect(screen.getByText('Titre bureau')).toBeTruthy()
    expect(screen.getByText('Contenu')).toBeTruthy()
  })

  it('rend le tiroir bas Sheet sur mobile (<768 px)', () => {
    mockMatchMedia(true)
    render(
      <ResponsiveDialog open onOpenChange={() => {}} title="Titre mobile">
        <p>Contenu</p>
      </ResponsiveDialog>,
    )
    const content = getContent()
    expect(content).toBeTruthy()
    // Marqueurs propres au tiroir bas (Sheet side="bottom").
    expect(content.className).toContain('bottom-0')
    expect(content.className).toContain('rounded-t-2xl')
    // Pas les marqueurs de modale centrée.
    expect(content.className).not.toContain('-translate-y-1/2')
    expect(screen.getByText('Titre mobile')).toBeTruthy()
    expect(screen.getByText('Contenu')).toBeTruthy()
  })

  it('expose la même surface de props (title/description/footer) aux deux variantes', () => {
    for (const mobile of [false, true]) {
      mockMatchMedia(mobile)
      render(
        <ResponsiveDialog
          open
          onOpenChange={() => {}}
          title="Mon titre"
          description="Ma description"
          footer={<button type="button">Enregistrer</button>}
        >
          <p>Corps</p>
        </ResponsiveDialog>,
      )
      expect(screen.getByText('Mon titre')).toBeTruthy()
      expect(screen.getByText('Ma description')).toBeTruthy()
      expect(screen.getByText('Corps')).toBeTruthy()
      expect(screen.getByText('Enregistrer')).toBeTruthy()
      cleanup()
    }
  })

  it('ne rend rien quand open est faux', () => {
    mockMatchMedia(false)
    render(
      <ResponsiveDialog open={false} onOpenChange={() => {}} title="Caché">
        <p>Invisible</p>
      </ResponsiveDialog>,
    )
    expect(getContent()).toBeNull()
  })
})
