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
