// EDC3 — barre de défilement horizontale COLLANTE (`BarreDefilementCollante`).
// jsdom ne fait aucune mise en page : `scrollWidth`/`clientWidth`/`scrollLeft`
// sont simulés par `Object.defineProperty`, `ResizeObserver` est bouchonné
// (son rappel est déclenché à la main, comme le ferait le navigateur).
// Run : npx vitest run src/ui/BarreDefilementCollante.test.jsx
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, act, fireEvent } from '@testing-library/react'
import { BarreDefilementCollante } from './BarreDefilementCollante'

let observateurs = []
let RO_ORIGINAL

beforeEach(() => {
  observateurs = []
  RO_ORIGINAL = globalThis.ResizeObserver
  globalThis.ResizeObserver = class {
    constructor(cb) { this.cb = cb; this.cibles = []; this.deconnecte = false; observateurs.push(this) }
    observe(el) { this.cibles.push(el) }
    unobserve() {}
    disconnect() { this.deconnecte = true }
  }
})
afterEach(() => { globalThis.ResizeObserver = RO_ORIGINAL })

/** Pose des dimensions de mise en page sur un élément jsdom. */
function dimensionner(el, { scrollWidth, clientWidth }) {
  Object.defineProperty(el, 'scrollWidth', { configurable: true, get: () => scrollWidth })
  Object.defineProperty(el, 'clientWidth', { configurable: true, get: () => clientWidth })
}

/** `scrollLeft` simulé, avec compteur d'écritures (preuve « sans boucle »). */
function defilable(el) {
  const etat = { valeur: 0, ecritures: 0 }
  Object.defineProperty(el, 'scrollLeft', {
    configurable: true,
    get: () => etat.valeur,
    set: (v) => { etat.valeur = v; etat.ecritures += 1 },
  })
  return etat
}

const remesurer = () => act(() => { for (const o of observateurs) o.cb([]) })

function rendre(props = {}) {
  const r = render(
    <div>
      <BarreDefilementCollante className="lines-table-wrap" {...props}>
        <table data-testid="table"><tbody><tr><td>ligne</td></tr></tbody></table>
      </BarreDefilementCollante>
    </div>,
  )
  return {
    ...r,
    wrap: r.container.querySelector('.bdc-wrap'),
    barre: r.container.querySelector('.bdc-proxy'),
  }
}

describe('EDC3 — BarreDefilementCollante', () => {
  it('la table tient : barre proxy cachée, état « tient » sur le conteneur', () => {
    const { wrap, barre } = rendre()
    dimensionner(wrap, { scrollWidth: 800, clientWidth: 800 })
    remesurer()
    expect(wrap).toHaveAttribute('data-deborde', 'false')
    expect(wrap).toHaveClass('bdc-wrap', 'lines-table-wrap')
    expect(barre.hidden).toBe(true)
    // Proxy : collant en bas, hors lecteur d'écran et hors tabulation.
    expect(barre).toHaveAttribute('aria-hidden', 'true')
    expect(barre).toHaveAttribute('tabindex', '-1')
    expect(barre.style.position).toBe('sticky')
    expect(barre.style.bottom).toBe('0px')
    // Frère IMMÉDIAT du conteneur (jamais dedans : il défilerait avec lui).
    expect(wrap.nextElementSibling).toBe(barre)
  })

  it('1 px de tolérance : scrollWidth = clientWidth + 1 compte encore comme « tient »', () => {
    const { wrap, barre } = rendre()
    dimensionner(wrap, { scrollWidth: 801, clientWidth: 800 })
    remesurer()
    expect(wrap).toHaveAttribute('data-deborde', 'false')
    expect(barre.hidden).toBe(true)
  })

  it('la table déborde : barre présente, piste à la largeur défilable', () => {
    const { wrap, barre } = rendre()
    dimensionner(wrap, { scrollWidth: 1200, clientWidth: 800 })
    // La barre n'a pas de bordure : 2 px de plus que le conteneur bordé.
    dimensionner(barre, { scrollWidth: 0, clientWidth: 802 })
    remesurer()
    expect(wrap).toHaveAttribute('data-deborde', 'true')
    expect(barre.hidden).toBe(false)
    // Même course des deux côtés : (1200 − 800) + 802.
    expect(barre.firstElementChild.style.width).toBe('1202px')
  })

  it('synchronisation dans les deux sens, tolérance 0,5 px, sans boucle', () => {
    const { wrap, barre } = rendre()
    dimensionner(wrap, { scrollWidth: 1200, clientWidth: 800 })
    dimensionner(barre, { scrollWidth: 1200, clientWidth: 800 })
    const w = defilable(wrap)
    const b = defilable(barre)
    remesurer()

    // Table → barre : une seule écriture sur la barre.
    w.valeur = 150
    b.ecritures = 0
    fireEvent.scroll(wrap)
    expect(b.valeur).toBe(150)
    expect(b.ecritures).toBe(1)
    // Le `scroll` que cette écriture déclenche sur la barre ne réécrit RIEN.
    w.ecritures = 0
    fireEvent.scroll(barre)
    expect(w.ecritures).toBe(0)

    // Barre → table.
    b.valeur = 60
    fireEvent.scroll(barre)
    expect(w.valeur).toBe(60)
    expect(w.ecritures).toBe(1)

    // Écart sous 0,5 px : aucune écriture (pas de ping-pong sub-pixel).
    b.ecritures = 0
    w.valeur = 60.3
    fireEvent.scroll(wrap)
    expect(b.ecritures).toBe(0)
  })

  it('disparaît quand la table tient, réapparaît quand une colonne s\'ajoute (table observée)', () => {
    const { wrap, barre, getByTestId } = rendre()
    // La TABLE est observée, pas seulement le conteneur : une colonne ajoutée
    // l'élargit sans changer la taille du conteneur.
    const cibles = observateurs.flatMap((o) => o.cibles)
    expect(cibles).toContain(wrap)
    expect(cibles).toContain(getByTestId('table'))
    expect(cibles).toContain(barre)

    dimensionner(wrap, { scrollWidth: 1200, clientWidth: 800 })
    remesurer()
    expect(barre.hidden).toBe(false)
    dimensionner(wrap, { scrollWidth: 800, clientWidth: 800 })
    remesurer()
    expect(barre.hidden).toBe(true)
    expect(wrap).toHaveAttribute('data-deborde', 'false')
    dimensionner(wrap, { scrollWidth: 930, clientWidth: 800 })
    remesurer()
    expect(barre.hidden).toBe(false)
    expect(wrap).toHaveAttribute('data-deborde', 'true')
  })

  it('au passage en « déborde », la barre reprend la position courante de la table', () => {
    const { wrap, barre } = rendre()
    const w = defilable(wrap)
    const b = defilable(barre)
    w.valeur = 90
    dimensionner(wrap, { scrollWidth: 1200, clientWidth: 800 })
    remesurer()
    expect(b.valeur).toBe(90)
  })

  it('`bottom` réglable ; observateur et écouteurs libérés au démontage', () => {
    const { barre, unmount } = rendre({ bottom: 48 })
    expect(barre.style.bottom).toBe('48px')
    unmount()
    expect(observateurs.every((o) => o.deconnecte)).toBe(true)
  })
})
