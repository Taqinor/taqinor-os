import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR177 — les liens de notification `publish_annonce`/`sweep_annonce_
   reminders` (apps/notifications/services.py) pointaient vers `/annonces/<pk>`
   (aucun écran) et l'accusé de lecture (accuser-lecture, XKB6) n'avait aucun
   appelant. Cet écran liste les annonces actives, accuse lecture et ouvre
   l'annonce ciblée via `?annonce=<pk>` (le format corrigé côté services.py).
   Réseau mocké — patron du contrat AnnonceSerializer. */

const ANNONCES = [
  {
    id: 12, titre: 'Nouvelle procédure sécurité chantier', corps: 'Détails…',
    auteur_username: 'fondateur', cible_type: 'tous', cible_type_label: 'Toute la société',
    date_publication: '2026-08-01T08:00:00Z', date_expiration: null,
    publiee: true, date_publication_effective: '2026-08-01T08:00:00Z',
    epinglee: true, lecture_obligatoire: true, is_expiree: false, lus_count: 3,
  },
  {
    id: 13, titre: 'Fermeture exceptionnelle vendredi', corps: '',
    auteur_username: 'fondateur', cible_type: 'tous', cible_type_label: 'Toute la société',
    date_publication: '2026-08-05T08:00:00Z', date_expiration: null,
    publiee: true, date_publication_effective: '2026-08-05T08:00:00Z',
    epinglee: false, lecture_obligatoire: false, is_expiree: false, lus_count: 0,
  },
]

vi.mock('../../api/notificationsApi', () => ({
  default: {
    getAnnonces: vi.fn(() => Promise.resolve({ data: ANNONCES })),
    accuserLectureAnnonce: vi.fn(() => Promise.resolve({ data: { lu: true } })),
  },
}))

import notificationsApi from '../../api/notificationsApi'
import AnnoncesPage from './AnnoncesPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage(path = '/annonces') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ThemeProvider>
        <Routes>
          <Route path="/annonces" element={<AnnoncesPage />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('AnnoncesPage (WIR177)', () => {
  it('charge et affiche les annonces actives', async () => {
    renderPage()
    await waitFor(() => expect(notificationsApi.getAnnonces).toHaveBeenCalledWith({ active: 1 }))
    expect(await screen.findByText('Nouvelle procédure sécurité chantier')).toBeInTheDocument()
    expect(screen.getByText('Fermeture exceptionnelle vendredi')).toBeInTheDocument()
  })

  it('accuse lecture d’une annonce à lecture obligatoire, désactive ensuite le bouton', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Nouvelle procédure sécurité chantier')

    const bouton = screen.getByRole('button', { name: "J'ai lu et compris" })
    await user.click(bouton)

    await waitFor(() => expect(notificationsApi.accuserLectureAnnonce).toHaveBeenCalledWith(12))
    expect(await screen.findByRole('button', { name: 'Lu et compris' })).toBeDisabled()
  })

  it('n’affiche aucun bouton d’accusé pour une annonce non obligatoire', async () => {
    renderPage()
    await screen.findByText('Fermeture exceptionnelle vendredi')
    // Une seule annonce (id 12) exige un accusé.
    expect(screen.getAllByRole('button', { name: "J'ai lu et compris" })).toHaveLength(1)
  })

  it('met en avant l’annonce ciblée par ?annonce=<pk> (lien de notification/relance)', async () => {
    renderPage('/annonces?annonce=13')
    await screen.findByText('Fermeture exceptionnelle vendredi')

    const carte = document.getElementById('annonce-13')
    expect(carte).toBeTruthy()
    expect(carte.className).toContain('ring-2')
  })
})
