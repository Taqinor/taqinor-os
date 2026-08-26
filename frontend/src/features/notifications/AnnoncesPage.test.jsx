import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* WIR177 — écran destinataire des annonces internes (XKB5/XKB6).

   Ce que ce module PROUVE :
     - la liste demande bien les annonces ACTIVES (`{ active: 1 }`) ;
     - `?annonce=<pk>` — le motif que les deux `link=` de
       `apps/notifications/services.py` posent — remonte l'annonce visée EN
       TÊTE (la publication et la relance ouvrent donc la bonne annonce) ;
     - « J'ai lu et compris » appelle `accuserLectureAnnonce(<pk>)` (l'accusé
       qui alimente le rapport de conformité XKB6) et l'écran bascule sur la
       confirmation ;
     - le bouton n'apparaît QUE sur une annonce à lecture obligatoire. */

const { getAnnonces, accuserLectureAnnonce } = vi.hoisted(() => ({
  getAnnonces: vi.fn(),
  accuserLectureAnnonce: vi.fn(() => Promise.resolve({ data: { lu: true } })),
}))
vi.mock('../../api/notificationsApi', () => ({
  default: { getAnnonces, accuserLectureAnnonce },
}))
vi.mock('../../ui/Toaster', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}))

import AnnoncesPage from './AnnoncesPage'

// Forme RÉELLE d'AnnonceSerializer (cf. docs/api-contracts.md ::
// notificationsApi.js :: getAnnonces) — jamais un mock inventé.
const ANNONCES = [
  {
    id: 11, titre: 'Fermeture annuelle', corps: 'Du 1er au 15 août.',
    auteur_username: 'reda', epinglee: false, lecture_obligatoire: false,
    publiee: true, date_publication_effective: '2026-07-01T09:00:00Z',
    is_expiree: false, lus_count: 0, cible_type: 'tous',
  },
  {
    id: 12, titre: 'Nouvelle procédure sécurité', corps: 'À appliquer dès lundi.',
    auteur_username: 'reda', epinglee: false, lecture_obligatoire: true,
    publiee: true, date_publication_effective: '2026-06-20T09:00:00Z',
    is_expiree: false, lus_count: 0, cible_type: 'tous',
  },
]

function renderPage(search = '') {
  return render(
    <MemoryRouter initialEntries={[`/annonces${search}`]}>
      <AnnoncesPage />
    </MemoryRouter>,
  )
}

describe('AnnoncesPage (WIR177)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getAnnonces.mockResolvedValue({ data: { results: ANNONCES } })
  })

  it('liste les annonces ACTIVES de la société', async () => {
    renderPage()
    expect(await screen.findByText('Fermeture annuelle')).toBeInTheDocument()
    expect(screen.getByText('Nouvelle procédure sécurité')).toBeInTheDocument()
    expect(getAnnonces).toHaveBeenCalledWith({ active: 1 })
  })

  it('`?annonce=<pk>` remonte l’annonce visée en tête', async () => {
    renderPage('?annonce=12')
    await screen.findByText('Nouvelle procédure sécurité')
    const cartes = screen.getAllByTestId(/^annonce-\d+$/)
    expect(cartes[0]).toHaveAttribute('data-testid', 'annonce-12')
  })

  it('« J’ai lu et compris » enregistre l’accusé et affiche la confirmation', async () => {
    renderPage()
    const bouton = await screen.findByText('J’ai lu et compris')
    await userEvent.click(bouton)
    await waitFor(() => expect(accuserLectureAnnonce).toHaveBeenCalledWith(12))
    expect(await screen.findByTestId('annonce-lue-12')).toBeInTheDocument()
    // Un seul accusé posé : le bouton a laissé place à la confirmation
    // (le POST reste idempotent côté serveur — cf. `acknowledge_annonce`).
    expect(screen.queryByText('J’ai lu et compris')).toBeNull()
    expect(accuserLectureAnnonce).toHaveBeenCalledTimes(1)
  })

  it('aucun bouton d’accusé sur une annonce sans lecture obligatoire', async () => {
    getAnnonces.mockResolvedValue({ data: { results: [ANNONCES[0]] } })
    renderPage()
    await screen.findByText('Fermeture annuelle')
    expect(screen.queryByText('J’ai lu et compris')).toBeNull()
  })

  it('état vide quand aucune annonce active', async () => {
    getAnnonces.mockResolvedValue({ data: { results: [] } })
    renderPage()
    expect(await screen.findByText('Aucune annonce')).toBeInTheDocument()
  })
})
