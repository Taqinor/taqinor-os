import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { axe } from 'vitest-axe'
import StudioShell from './StudioShell'

/* AOF73 — la coquille d'atelier est REUTILISABLE : ces tests l'exercent avec des
   slots quelconques (aucun couplage à la toiture ni au calepinage), et prouvent
   les trois exigences du contrat :
     1. responsive — l'inspecteur devient un `Sheet` sous 1024 px ;
     2. clavier — F6 fait tourner le focus entre les 3 zones ;
     3. composition — le rail pose le hook `data-ao-outil` (contrat AOF8) et
        aucun autre hook DOM. */

function mockMatchMedia(compact) {
  window.matchMedia = (query) => ({
    matches: compact,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })
}

const OUTILS = [
  { id: 'selection', label: 'Sélection', raccourci: 's' },
  { id: 'polygone', label: 'Polygone', raccourci: 'p' },
  { id: 'obstacle', label: 'Obstacle', raccourci: 'o', disabled: true },
]

const ONGLETS = [
  { id: 'geometrie', label: 'Géométrie', contenu: <p>Sommets du contour</p> },
  { id: 'obstacles', label: 'Obstacles', contenu: <p>Liste des obstacles</p> },
]

function renderShell(props = {}) {
  return render(
    <StudioShell
      titre="Toiture — Bâtiment C"
      sousTitre="Atelier de relevé"
      outils={OUTILS}
      outilActif="selection"
      onglets={ONGLETS}
      etat={<span>Échelle 1:200</span>}
      verdict={<span>314 modules</span>}
      {...props}
    >
      <div data-testid="surface">canvas</div>
    </StudioShell>,
  )
}

beforeEach(() => {
  mockMatchMedia(false)
})

describe('StudioShell — les 5 zones', () => {
  it('rend la barre haute, le rail, le canvas, l’inspecteur et la barre d’état', () => {
    renderShell()
    expect(screen.getByRole('heading', { name: 'Toiture — Bâtiment C' })).toBeInTheDocument()
    expect(screen.getByRole('toolbar', { name: "Outils de l'atelier" })).toBeInTheDocument()
    expect(screen.getByTestId('surface')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Géométrie' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: "État de l'atelier" })).toHaveTextContent('Échelle 1:200')
    expect(screen.getByText('314 modules')).toBeInTheDocument()
  })

  it('la barre d’actions haute pilote annuler/rétablir/enregistrer', () => {
    const onAnnuler = vi.fn()
    const onRetablir = vi.fn()
    const onEnregistrer = vi.fn()
    renderShell({
      onAnnuler, onRetablir, onEnregistrer, peutAnnuler: true, peutRetablir: false,
    })
    expect(screen.getByRole('button', { name: 'Rétablir' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(onAnnuler).toHaveBeenCalledTimes(1)
    expect(onRetablir).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(onEnregistrer).toHaveBeenCalledTimes(1)
  })
})

describe('StudioShell — rail d’outils (contrat de hooks AOF8)', () => {
  it('chaque outil porte `data-ao-outil` et signale son état par aria-pressed', () => {
    const { container } = renderShell()
    const boutons = container.querySelectorAll('[data-ao-outil]')
    expect(boutons).toHaveLength(3)
    expect([...boutons].map((b) => b.getAttribute('data-ao-outil')))
      .toEqual(['selection', 'polygone', 'obstacle'])
    expect(container.querySelector('[data-ao-outil="selection"]'))
      .toHaveAttribute('aria-pressed', 'true')
    expect(container.querySelector('[data-ao-outil="polygone"]'))
      .toHaveAttribute('aria-pressed', 'false')
  })

  it('n’introduit AUCUN autre hook `data-ao-*` (le canvas pose le sien — AOF74)', () => {
    const { container } = renderShell()
    const trouves = new Set(
      [...container.querySelectorAll('*')]
        .flatMap((el) => [...el.attributes].map((a) => a.name))
        .filter((n) => n.startsWith('data-ao-')),
    )
    expect([...trouves]).toEqual(['data-ao-outil'])
  })

  it('un clic sur un outil remonte son id', () => {
    const onOutilChange = vi.fn()
    const { container } = renderShell({ onOutilChange })
    fireEvent.click(container.querySelector('[data-ao-outil="polygone"]'))
    expect(onOutilChange).toHaveBeenCalledWith('polygone')
  })

  it('un raccourci à une touche sélectionne l’outil…', () => {
    const onOutilChange = vi.fn()
    const { container } = renderShell({ onOutilChange })
    fireEvent.keyDown(container.firstChild, { key: 'p' })
    expect(onOutilChange).toHaveBeenCalledWith('polygone')
  })

  it('…mais JAMAIS depuis un champ de saisie (taper « p » dans le tableau de géométrie)', () => {
    const onOutilChange = vi.fn()
    renderShell({
      onOutilChange,
      onglets: [{ id: 'geo', label: 'Géométrie', contenu: <input aria-label="x (m)" /> }],
    })
    fireEvent.keyDown(screen.getByLabelText('x (m)'), { key: 'p' })
    expect(onOutilChange).not.toHaveBeenCalled()
  })

  it('un outil désactivé ignore son raccourci', () => {
    const onOutilChange = vi.fn()
    const { container } = renderShell({ onOutilChange })
    fireEvent.keyDown(container.firstChild, { key: 'o' })
    expect(onOutilChange).not.toHaveBeenCalled()
  })
})

describe('StudioShell — navigation clavier entre les 3 zones (F6)', () => {
  it('F6 fait tourner le focus rail → canvas → inspecteur → rail', () => {
    const { container } = renderShell()
    const racine = container.firstChild
    const rail = screen.getByRole('toolbar', { name: "Outils de l'atelier" })
    const canvas = screen.getByRole('region', { name: 'Zone de dessin' })
    const inspecteur = screen.getByRole('region', { name: 'Inspecteur' })

    fireEvent.keyDown(racine, { key: 'F6' })
    expect(document.activeElement).toBe(canvas)
    fireEvent.keyDown(canvas, { key: 'F6' })
    expect(document.activeElement).toBe(inspecteur)
    fireEvent.keyDown(inspecteur, { key: 'F6' })
    expect(document.activeElement).toBe(rail)
  })

  it('Maj+F6 tourne dans l’autre sens', () => {
    const { container } = renderShell()
    const rail = screen.getByRole('toolbar', { name: "Outils de l'atelier" })
    const inspecteur = screen.getByRole('region', { name: 'Inspecteur' })
    rail.focus()
    fireEvent.keyDown(rail, { key: 'F6', shiftKey: true })
    expect(document.activeElement).toBe(inspecteur)
    expect(container).toBeTruthy()
  })
})

describe('StudioShell — responsive (< 1024 px)', () => {
  it('sous 1024 px l’inspecteur n’est plus une colonne : il s’ouvre en Sheet', () => {
    mockMatchMedia(true)
    renderShell()
    // Colonne absente, onglets non montés tant que le tiroir est fermé.
    expect(screen.queryByRole('tab', { name: 'Géométrie' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Inspecteur' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Géométrie' })).toBeInTheDocument()
  })

  it('au-dessus de 1024 px l’inspecteur est une colonne, sans dialogue', () => {
    mockMatchMedia(false)
    renderShell()
    expect(screen.getByRole('tab', { name: 'Géométrie' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Inspecteur' })).not.toBeInTheDocument()
  })
})

describe('StudioShell — réutilisabilité', () => {
  it('sans outils ni onglets, la coquille rend le seul canvas (atelier minimal)', () => {
    render(
      <StudioShell titre="Atelier de calepinage">
        <div data-testid="surface-2">calepinage</div>
      </StudioShell>,
    )
    expect(screen.getByTestId('surface-2')).toBeInTheDocument()
    expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
  })

  it('change d’onglet d’inspecteur sans toucher au canvas', () => {
    renderShell()
    expect(screen.getByText('Sommets du contour')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Obstacles' }))
    expect(screen.getByText('Liste des obstacles')).toBeInTheDocument()
    expect(screen.getByTestId('surface')).toBeInTheDocument()
  })

  it("n'a aucune violation d'accessibilité détectable", async () => {
    const { container } = renderShell()
    const results = await axe(container)
    expect(results.violations).toEqual([])
  })
})
