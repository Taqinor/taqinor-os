import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* WIR150 — `FeedbackProduitViewSet`/`FeedbackResumeView`/`AnnonceProduitViewSet`
   n'avaient aucun consommateur admin : seul `.feedback.create` (bouton
   discret côté utilisateur) était appelé, et `AnnonceProduit` n'était même
   pas dans le client API. Cet écran (palier IdeasSeeAll) liste les retours,
   affiche le résumé par thème, crée des annonces et clôture un retour en le
   liant à une annonce (existante ou créée à la volée). */

const {
  listFeedback, resume, listAnnonces, createAnnonce, lierAnnonce,
  hotspot, etoiler, masquer,
} = vi.hoisted(() => ({
  listFeedback: vi.fn(() => Promise.resolve({
    data: [{
      id: 5, titre: 'Export PDF trop lent', theme: 'performance', theme_display: 'Performance',
      statut: 'envoye', statut_display: 'Envoyé', auteur_nom: 'Amine', date_creation: '2026-07-20T10:00:00Z',
    }],
  })),
  resume: vi.fn(() => Promise.resolve({
    data: { results: [{ theme: 'performance', theme_display: 'Performance', total: 4, non_lus: 2, exemples: [] }] },
  })),
  listAnnonces: vi.fn(() => Promise.resolve({ data: [{ id: 8, titre: 'PDF v2 déployé' }] })),
  createAnnonce: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
  lierAnnonce: vi.fn(() => Promise.resolve({ data: {} })),
  // NTIDE46 — pages les plus commentées : tirée au montage (dans le
  // `Promise.all` de l'écran), donc obligatoire dans le stub.
  hotspot: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  // NTIDE45/NTIDE47 — étoiler / masquer : appelées depuis les actions de ligne.
  etoiler: vi.fn(() => Promise.resolve({ data: {} })),
  masquer: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/innovationApi', () => ({
  default: {
    feedback: { list: listFeedback, resume, lierAnnonce, hotspot, etoiler, masquer },
    annonces: { list: listAnnonces, create: createAnnonce },
  },
}))

import RetoursProduitPage from './RetoursProduitPage'

beforeEach(() => { vi.clearAllMocks() })

describe('RetoursProduitPage (WIR150)', () => {
  it('liste les retours et le résumé par thème', async () => {
    renderPage(<RetoursProduitPage />)
    // DataTable rend à la fois la table desktop et le repli carte mobile (CSS
    // seul, les deux existent dans le DOM en jsdom) : on cible le PREMIER
    // match, même patron que ModelesBcf.test.jsx / qhse.render.test.jsx.
    expect((await screen.findAllByText('Export PDF trop lent'))[0]).toBeInTheDocument()
    expect(screen.getByText('2 non lu(s)')).toBeInTheDocument()
  })

  it('crée une annonce produit', async () => {
    const user = userEvent.setup()
    renderPage(<RetoursProduitPage />)
    await screen.findAllByText('Export PDF trop lent')

    await user.click(screen.getByRole('button', { name: /Nouvelle annonce/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Titre'), 'Cache PDF activé')
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(createAnnonce).toHaveBeenCalledWith(expect.objectContaining({ titre: 'Cache PDF activé' })))
  })

  it('clôture un retour en le liant à une annonce existante', async () => {
    const user = userEvent.setup()
    renderPage(<RetoursProduitPage />)
    await screen.findAllByText('Export PDF trop lent')

    await user.click(screen.getAllByRole('button', { name: 'Lier une annonce' })[0])
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('combobox', { name: 'Annonce' }))
    await user.click(await screen.findByRole('option', { name: 'PDF v2 déployé' }))
    await user.click(within(dialog).getByRole('button', { name: 'Clôturer' }))

    await waitFor(() => expect(lierAnnonce).toHaveBeenCalledWith(5, expect.objectContaining({ annonce_id: 8 })))
  })
})
