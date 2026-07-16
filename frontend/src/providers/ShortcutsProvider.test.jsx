import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, cleanup, within } from '@testing-library/react'
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
