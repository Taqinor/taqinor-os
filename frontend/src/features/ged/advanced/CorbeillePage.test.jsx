import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import gedApi from '../../../api/gedApi'
import { renderAvecAuth } from '../../../test/renderAvecAuth.jsx'
import { AUTH_COMMERCIAL_RESP, AUTH_DIRECTEUR } from './gedPage.testHelpers.jsx'
import CorbeillePage from './CorbeillePage.jsx'

/* GED26 — Corbeille : liste des documents supprimés, restauration + purge
   confirmée. gedApi mocké : on vérifie que les bons endpoints sont appelés. */

vi.mock('../../../api/gedApi', () => ({
  default: {
    getCorbeille: vi.fn(),
    restaurerCorbeille: vi.fn(() => Promise.resolve({ data: {} })),
    purgerDocument: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }
})

// ADRG85 — purge et legal holds suivent `ged_gouvernance` (Directeur ;
// le Commercial responsable ne le porte pas) : comptes partagés du harnais GED.
function renderPage(auth = AUTH_DIRECTEUR) {
  return renderAvecAuth(<CorbeillePage />, auth, { theme: true })
}

beforeEach(() => {
  vi.clearAllMocks()
  gedApi.getCorbeille.mockResolvedValue({
    data: [{
      id: 3, nom: 'ancien.pdf', folder_nom: 'Archives',
      supprime_par_nom: 'Reda', supprime_le: '2026-06-10T09:00:00Z',
    }],
  })
})

describe('GED26 CorbeillePage', () => {
  it('liste les documents supprimés et restaure', async () => {
    renderPage()
    // ListShell rend une vue table + une vue carte : le nom apparaît 2×.
    expect((await screen.findAllByText('ancien.pdf')).length).toBeGreaterThan(0)

    await userEvent.click(screen.getAllByRole('button', { name: 'Restaurer' })[0])
    await waitFor(() => expect(gedApi.restaurerCorbeille).toHaveBeenCalledWith(3))
  })

  it('purge définitivement après confirmation', async () => {
    renderPage()
    await screen.findAllByText('ancien.pdf')

    await userEvent.click(
      screen.getAllByRole('button', { name: 'Supprimer définitivement' })[0])
    // La modale de confirmation apparaît ; on confirme.
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(
      await within(dialog).findByRole('button', { name: 'Supprimer définitivement' }))

    await waitFor(() => expect(gedApi.purgerDocument).toHaveBeenCalledWith(3))
  })

  it('ADRG85 — palier responsable sans ged_gouvernance : pas de purge', async () => {
    renderPage(AUTH_COMMERCIAL_RESP)
    await screen.findAllByText('ancien.pdf')
    expect(screen.getAllByRole('button', { name: 'Restaurer' }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Supprimer définitivement' })).toBeNull()
  })
})
