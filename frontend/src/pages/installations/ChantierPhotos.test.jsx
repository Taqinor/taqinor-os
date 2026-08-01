import { describe, it, expect, vi, afterEach, beforeEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* APX27 — Avant/Après appariés : la preuve qui vend.
   Couvre (1) la galerie UNIFIÉE en lecture (chantier + photos des
   interventions liées, badge d'origine, aucune action d'écriture sur les
   photos d'intervention) ; (2) la vue « Comparer » (paires avant/après CSS
   slider) ; (3) le compteur de complétion VX44 reste scopé au chantier
   (non éteint par une photo d'intervention). Tout le réseau est mocké. */

const { installationsApiMock, recordsApiMock } = vi.hoisted(() => ({
  installationsApiMock: {
    getInterventions: vi.fn(() => Promise.resolve({ data: [] })),
    getPhotos: vi.fn(() => Promise.resolve({ data: { groupes: {} } })),
  },
  recordsApiMock: {
    getAttachments: vi.fn(() => Promise.resolve({ data: [] })),
    uploadAttachment: vi.fn(),
    deleteAttachment: vi.fn(() => Promise.resolve({})),
    setAttachmentPhase: vi.fn(),
  },
}))
vi.mock('../../api/installationsApi', () => ({ default: installationsApiMock }))
vi.mock('../../api/recordsApi', () => ({ default: recordsApiMock }))

import ChantierPhotos from './ChantierPhotos'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

function authReducer(role) {
  return (state = { role }) => state
}

function renderPage(role = 'admin') {
  const store = configureStore({ reducer: { auth: authReducer(role) } })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider>
          <ChantierPhotos installationId={42} />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => cleanup())

describe('ChantierPhotos — galerie unifiée (APX27)', () => {
  it('fusionne les photos chantier + intervention par phase, avec un badge d’origine sur les secondes', async () => {
    recordsApiMock.getAttachments.mockResolvedValueOnce({
      data: [
        { id: 1, filename: 'chantier-avant.jpg', mime: 'image/jpeg', phase: 'avant', url: '/a/1' },
      ],
    })
    installationsApiMock.getInterventions.mockResolvedValueOnce({
      data: [{ id: 9, type_intervention_display: 'Pose', date_realisee: '2026-07-12' }],
    })
    installationsApiMock.getPhotos.mockResolvedValueOnce({
      data: {
        groupes: {
          avant: [{
            cle: 'avant-general', libelle: 'Avant', phase: 'avant', obligatoire: false,
            photos: [{ id: 100, filename: 'interv-avant.jpg', mime: 'image/jpeg', url: '/a/100' }],
          }],
          pendant: [],
          apres: [],
        },
      },
    })

    renderPage()

    await waitFor(() => expect(installationsApiMock.getInterventions)
      .toHaveBeenCalledWith({ installation: 42 }))
    await screen.findByAltText('chantier-avant.jpg')
    await screen.findByAltText('interv-avant.jpg')

    // Badge d'origine : le libellé de l'intervention (type + date) est visible.
    expect(await screen.findByText(/Pose/)).toBeInTheDocument()

    // Seule la photo CHANTIER a un bouton Supprimer (rôle admin) — la photo
    // d'intervention reste EN LECTURE (elle appartient à sa propre fiche).
    expect(screen.getAllByRole('button', { name: 'Supprimer' })).toHaveLength(1)
  })

  it('le compteur VX44 « À compléter » reste scopé au chantier — une photo d’intervention ne l’éteint pas', async () => {
    // Le chantier a lui-même documenté "pendant" et "après", mais RIEN en
    // "avant" — seule une intervention liée en fournit une.
    recordsApiMock.getAttachments.mockResolvedValueOnce({
      data: [
        { id: 2, filename: 'chantier-pendant.jpg', mime: 'image/jpeg', phase: 'pendant', url: '/a/2' },
        { id: 3, filename: 'chantier-apres.jpg', mime: 'image/jpeg', phase: 'apres', url: '/a/3' },
      ],
    })
    installationsApiMock.getInterventions.mockResolvedValueOnce({
      data: [{ id: 9, type_intervention_display: 'Pose', date_realisee: '2026-07-12' }],
    })
    installationsApiMock.getPhotos.mockResolvedValueOnce({
      data: {
        groupes: {
          avant: [{
            cle: 'avant-general', libelle: 'Avant', phase: 'avant', obligatoire: false,
            photos: [{ id: 100, filename: 'interv-avant.jpg', mime: 'image/jpeg', url: '/a/100' }],
          }],
          pendant: [], apres: [],
        },
      },
    })

    renderPage()

    await screen.findByAltText('interv-avant.jpg')
    // La phase "avant" est bien visible (unifiée) dans la galerie…
    // … mais le nudge documentaire reste actif : SEULE la phase "avant" en
    // manque côté chantier (pendant/après sont couvertes par le chantier
    // lui-même) — exactement UN badge « À compléter ».
    expect(screen.getByText('À compléter')).toBeInTheDocument()
  })
})

describe('ChantierPhotos — vue Comparer (APX27)', () => {
  it('bascule sur "Comparer" et rend une paire avant/après avec un curseur natif (aucune paire = message)', async () => {
    const user = userEvent.setup()
    recordsApiMock.getAttachments.mockResolvedValueOnce({
      data: [
        { id: 1, filename: 'avant.jpg', mime: 'image/jpeg', phase: 'avant', url: '/a/1' },
      ],
    })
    installationsApiMock.getInterventions.mockResolvedValueOnce({
      data: [{ id: 9, type_intervention_display: 'Pose', date_realisee: '2026-07-12' }],
    })
    installationsApiMock.getPhotos.mockResolvedValueOnce({
      data: {
        groupes: {
          avant: [],
          pendant: [],
          apres: [{
            cle: 'apres-general', libelle: 'Après', phase: 'apres', obligatoire: false,
            photos: [{ id: 200, filename: 'apres.jpg', mime: 'image/jpeg', url: '/a/200' }],
          }],
        },
      },
    })

    renderPage()
    await screen.findByAltText('avant.jpg')

    await user.click(screen.getByRole('radio', { name: 'Comparer' }))

    const slider = await screen.findByRole('slider')
    expect(slider).toHaveValue(50)
    // Les deux photos sont rendues empilées (avant recadrée par clip-path).
    expect(screen.getByAltText('Avant — avant.jpg')).toBeInTheDocument()
    expect(screen.getByAltText('Après — apres.jpg')).toBeInTheDocument()
  })

  it('sans paire complète (seulement des "avant"), affiche le message au lieu d’inventer une paire', async () => {
    const user = userEvent.setup()
    recordsApiMock.getAttachments.mockResolvedValueOnce({
      data: [
        { id: 1, filename: 'avant.jpg', mime: 'image/jpeg', phase: 'avant', url: '/a/1' },
      ],
    })

    renderPage()
    await screen.findByAltText('avant.jpg')

    await user.click(screen.getByRole('radio', { name: 'Comparer' }))

    expect(await screen.findByText(/Ajoutez au moins une photo/)).toBeInTheDocument()
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
  })
})
