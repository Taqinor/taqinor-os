import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* VX248 — la cheatsheet « ? » gagne un champ `roles` optionnel : groupe
   « Pour votre rôle » d'abord, « Autres » en repli — un filtre d'AFFICHAGE
   seulement (jamais une désactivation fonctionnelle), et liste les
   raccourcis du RECORD FOCALISÉ propres à l'écran ACTIF (LeadForm.jsx dans
   ce test — DevisList.jsx/FactureList.jsx suivent le même mécanisme). */

const mockAuth = { role_nom: 'Commercial' }
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: mockAuth }),
}))

// ODY28 — on observe la navigation réelle du gestionnaire de séquences (le
// reste du module react-router-dom, dont MemoryRouter, est conservé).
const navigateMock = vi.fn()
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => navigateMock,
}))

import ShortcutsProvider from './ShortcutsProvider'
import { useFocusedRecordShortcuts } from './focusedRecordShortcuts'

afterEach(() => { cleanup() })

// Simule un écran de détail monté (LeadForm.jsx en vrai) qui enregistre ses
// raccourcis auprès du même mécanisme (`useFocusedRecordShortcuts`).
function LeadFormStub() {
  useFocusedRecordShortcuts('leadForm', {}, true)
  return null
}

function renderWithProvider() {
  return render(
    <MemoryRouter>
      <ShortcutsProvider>
        <LeadFormStub />
      </ShortcutsProvider>
    </MemoryRouter>,
  )
}

describe('ShortcutsProvider — cheatsheet « ? » (VX248)', () => {
  it("un rôle qui MATCH (Commercial) voit ses raccourcis de fiche EN TÊTE, avant « Général »", () => {
    mockAuth.role_nom = 'Commercial'
    renderWithProvider()
    fireEvent.keyDown(document, { key: '?' })
    const dialog = screen.getByLabelText('Aide des raccourcis clavier')
    const focusedHeading = within(dialog).getByText(/pour votre rôle/)
    const generalHeading = within(dialog).getByText('Général')
    // Le groupe « … — pour votre rôle » apparaît AVANT « Général » dans le DOM.
    expect(focusedHeading.compareDocumentPosition(generalHeading) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy()
    expect(within(dialog).getByText('Archiver / restaurer le lead')).toBeInTheDocument()
  })

  it('un rôle qui NE matche PAS (Magasinier) voit les mêmes raccourcis en repli « autres rôles » — jamais masqués', () => {
    mockAuth.role_nom = 'Magasinier'
    renderWithProvider()
    fireEvent.keyDown(document, { key: '?' })
    const dialog = screen.getByLabelText('Aide des raccourcis clavier')
    // Toujours listés (filtre d'AFFICHAGE seulement, jamais une désactivation
    // fonctionnelle) — juste sous le libellé « (autres rôles) ».
    expect(within(dialog).getByText(/\(autres rôles\)/)).toBeInTheDocument()
    expect(within(dialog).getByText('Archiver / restaurer le lead')).toBeInTheDocument()
  })

  it("sans écran de détail monté, la cheatsheet reste correcte (Général/Navigation/Créer seulement)", () => {
    render(
      <MemoryRouter>
        <ShortcutsProvider>
          <div />
        </ShortcutsProvider>
      </MemoryRouter>,
    )
    fireEvent.keyDown(document, { key: '?' })
    const dialog = screen.getByLabelText('Aide des raccourcis clavier')
    expect(within(dialog).getByText('Général')).toBeInTheDocument()
    expect(within(dialog).queryByText('Archiver / restaurer le lead')).not.toBeInTheDocument()
  })
})

/* ============================== NTUX18 — CHEATSHEET ENRICHIE + RECHERCHE ============================== */

describe('ShortcutsProvider — cheatsheet « ? » enrichie (NTUX18)', () => {
  it('liste désormais un groupe « Édition » (NTUX8 navigation clavier en grille)', () => {
    mockAuth.role_nom = 'Commercial'
    renderWithProvider()
    fireEvent.keyDown(document, { key: '?' })
    const dialog = screen.getByLabelText('Aide des raccourcis clavier')
    expect(within(dialog).getByText('Édition')).toBeInTheDocument()
    expect(within(dialog).getByText('Cellule éditable suivante (grille)')).toBeInTheDocument()
  })

  it('taper « créer » dans la recherche filtre INSTANTANÉMENT vers les raccourcis de création', async () => {
    const user = userEvent.setup()
    mockAuth.role_nom = 'Commercial'
    renderWithProvider()
    fireEvent.keyDown(document, { key: '?' })
    const dialog = screen.getByLabelText('Aide des raccourcis clavier')
    await user.type(within(dialog).getByLabelText('Rechercher un raccourci'), 'créer')
    expect(within(dialog).getByText('Créer')).toBeInTheDocument()
    expect(within(dialog).getByText('Créer un lead')).toBeInTheDocument()
    // Un groupe sans correspondance (ex. Général) disparaît de l'affichage.
    expect(within(dialog).queryByText('Général')).not.toBeInTheDocument()
  })

  it('une recherche sans correspondance affiche un message clair (jamais une liste vide muette)', async () => {
    const user = userEvent.setup()
    mockAuth.role_nom = 'Commercial'
    renderWithProvider()
    fireEvent.keyDown(document, { key: '?' })
    const dialog = screen.getByLabelText('Aide des raccourcis clavier')
    await user.type(within(dialog).getByLabelText('Rechercher un raccourci'), 'zzz-introuvable')
    expect(within(dialog).getByText(/aucun raccourci ne correspond/i)).toBeInTheDocument()
  })

  it('fermer puis rouvrir la cheatsheet réinitialise la recherche', async () => {
    const user = userEvent.setup()
    mockAuth.role_nom = 'Commercial'
    renderWithProvider()
    fireEvent.keyDown(document, { key: '?' })
    let dialog = screen.getByLabelText('Aide des raccourcis clavier')
    await user.type(within(dialog).getByLabelText('Rechercher un raccourci'), 'créer')
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.keyDown(document, { key: '?' })
    dialog = screen.getByLabelText('Aide des raccourcis clavier')
    expect(within(dialog).getByLabelText('Rechercher un raccourci')).toHaveValue('')
    expect(within(dialog).getByText('Général')).toBeInTheDocument()
  })
})

/* ================= ODY28 — UN SEUL gestionnaire de séquences ================= */

// Tape une séquence « <préfixe> puis lettre » sur le gestionnaire global.
function typeSequence(prefix, letter) {
  fireEvent.keyDown(document, { key: prefix })
  fireEvent.keyDown(document, { key: letter })
}

describe('ShortcutsProvider — ODY28 : séquences « g + lettre » unifiées', () => {
  it('« g g » ramène au Menu d’accueil (sortie clavier de l’immersion)', () => {
    navigateMock.mockClear()
    renderWithProvider()
    typeSequence('g', 'g')
    expect(navigateMock).toHaveBeenCalledWith('/apps')
  })

  it('« g o » OUVRE le lanceur (événement window) sans naviguer', () => {
    navigateMock.mockClear()
    const listener = vi.fn()
    window.addEventListener('taqinor:app-launcher', listener)
    renderWithProvider()
    typeSequence('g', 'o')
    expect(listener).toHaveBeenCalled()
    expect(navigateMock).not.toHaveBeenCalled()
    window.removeEventListener('taqinor:app-launcher', listener)
  })

  it('« g a » navigue vers les approbations et n’ouvre PLUS le lanceur (fin de la collision)', () => {
    navigateMock.mockClear()
    const listener = vi.fn()
    window.addEventListener('taqinor:app-launcher', listener)
    renderWithProvider()
    typeSequence('g', 'a')
    expect(navigateMock).toHaveBeenCalledWith('/approbations')
    // C'était LE bug : les deux gestionnaires tiraient sur la même frappe.
    expect(listener).not.toHaveBeenCalled()
    window.removeEventListener('taqinor:app-launcher', listener)
  })

  it('une séquence inconnue ne fait rien', () => {
    navigateMock.mockClear()
    renderWithProvider()
    typeSequence('g', 'q')
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('la frappe est ignorée dans un champ de saisie', () => {
    navigateMock.mockClear()
    renderWithProvider()
    const input = document.createElement('input')
    document.body.appendChild(input)
    fireEvent.keyDown(input, { key: 'g' })
    fireEvent.keyDown(input, { key: 'g' })
    expect(navigateMock).not.toHaveBeenCalled()
    input.remove()
  })

  it('l’aide « ? » documente la sortie « g g » et le lanceur « g o »', () => {
    renderWithProvider()
    fireEvent.keyDown(document, { key: '?' })
    const dialog = screen.getByLabelText('Aide des raccourcis clavier')
    expect(within(dialog).getByText(/Menu d’accueil/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Ouvrir le lanceur d’applications/)).toBeInTheDocument()
  })
})
