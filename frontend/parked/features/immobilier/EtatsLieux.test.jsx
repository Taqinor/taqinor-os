import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT77 — États des lieux d'entrée et de sortie. NTPRO15/16 (`apps/immobilier`)
   livraient déjà `EtatLieuxImmo`/`PieceEtatLieux`/`ElementEtatLieux`/
   `PhotoEtatLieux` SANS AUCUN écran. Vérifie : la création pré-remplie (le
   payload contient SEULEMENT bail/moment/date — jamais des pièces/éléments
   inventés côté client, le pré-remplissage est un service serveur), l'édition
   d'un élément (PATCH, jamais un POST de création — le backend borne
   `pieces-etat-lieux/`/`elements-etat-lieux/` à GET/PATCH), l'ajout de photo
   (multipart), et qu'un état de SORTIE affiche EXACTEMENT les
   `photos_entree` renvoyées par le serveur (aucune jointure locale). */

const { apiGet, apiPost, apiPatch } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPatch: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: (...args) => apiGet(...args),
    post: (...args) => apiPost(...args),
    patch: (...args) => apiPatch(...args),
  },
}))

vi.mock('../../api/immobilierApi', () => ({
  default: {
    baux: {
      list: () => Promise.resolve({
        data: [{ id: 3, local: 1, local_reference: 'LOC-A101', locataire: 2, locataire_nom: 'SARL Atlas' }],
      }),
    },
  },
}))

import EtatsLieux from './EtatsLieux'

const ETAT_ENTREE = {
  id: 10, bail: 3, bail_local_reference: 'LOC-A101', moment: 'entree',
  moment_display: 'Entrée', date: '2026-08-01', statut: 'brouillon',
  pieces: [
    {
      id: 100, etat_lieux: 10, nom_piece: 'Salon', etat_general: 'bon',
      commentaire: '', ordre: 0,
      elements: [
        { id: 1000, piece: 100, element: 'sol', etat: 'bon', commentaire: '', ordre: 0, photos: [], photos_entree: [] },
      ],
    },
  ],
}

const ETAT_SORTIE = {
  ...ETAT_ENTREE, id: 11, moment: 'sortie', moment_display: 'Sortie', date: '2026-09-01',
  pieces: [
    {
      ...ETAT_ENTREE.pieces[0], id: 101, etat_lieux: 11,
      elements: [
        {
          id: 1001, piece: 101, element: 'sol', etat: 'usage_normal', commentaire: '',
          ordre: 0, photos: [],
          photos_entree: [{ id: 5000, element: 1000, filename: 'sol-entree.jpg', size: 1000, mime: 'image/jpeg', created_at: '2026-08-01T10:00:00Z' }],
        },
      ],
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  apiPatch.mockResolvedValue({ data: {} })
  apiGet.mockImplementation((url) => {
    if (url === '/immobilier/etats-lieux/') return Promise.resolve({ data: [ETAT_ENTREE] })
    if (url === '/immobilier/etats-lieux/10/') return Promise.resolve({ data: ETAT_ENTREE })
    if (url === '/immobilier/etats-lieux/11/') return Promise.resolve({ data: ETAT_SORTIE })
    return Promise.resolve({ data: [] })
  })
  apiPost.mockResolvedValue({ data: ETAT_ENTREE })
})

function renderPage() {
  return render(<MemoryRouter><ThemeProvider><EtatsLieux /></ThemeProvider></MemoryRouter>)
}

describe('EtatsLieux (PACT77)', () => {
  it('charge la liste des états des lieux du bail sélectionné', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText(/LOC-A101/)).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Bail'), { target: { value: '3' } })

    await waitFor(() => expect(apiGet).toHaveBeenCalledWith(
      '/immobilier/etats-lieux/', { params: { bail: '3' } },
    ))
    expect(await screen.findByText(/Entrée — 2026-08-01/)).toBeInTheDocument()
  })

  it('crée un état des lieux avec un payload MINIMAL (bail/moment/date) — le pré-remplissage est SERVEUR', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText(/LOC-A101/)).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Bail'), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer l.état des lieux/ }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/immobilier/etats-lieux/', {
      bail: 3, moment: 'entree', date: expect.any(String),
    }))
    // La grille pré-remplie (pièce + élément) apparaît, SANS que le client
    // n'ait jamais posté de pièce/élément.
    expect(await screen.findByText('Salon')).toBeInTheDocument()
    expect(screen.getByText('sol')).toBeInTheDocument()
  })

  it('édite l’état d’un élément par PATCH — jamais une création directe', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText(/LOC-A101/)).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Bail'), { target: { value: '3' } })
    fireEvent.click(await screen.findByText(/Entrée — 2026-08-01/))
    await screen.findByText('Salon')

    fireEvent.change(screen.getByLabelText('État — sol'), { target: { value: 'degrade' } })

    await waitFor(() => expect(apiPatch).toHaveBeenCalledWith(
      '/immobilier/elements-etat-lieux/1000/', { etat: 'degrade' },
    ))
    expect(apiPost).not.toHaveBeenCalledWith(expect.stringContaining('elements-etat-lieux'), expect.anything())
  })

  it('ajoute une photo à un élément (multipart)', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText(/LOC-A101/)).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Bail'), { target: { value: '3' } })
    fireEvent.click(await screen.findByText(/Entrée — 2026-08-01/))
    await screen.findByText('Salon')

    const file = new File(['x'], 'photo.jpg', { type: 'image/jpeg' })
    fireEvent.change(screen.getByLabelText('Ajouter une photo — sol'), { target: { files: [file] } })

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith(
      '/immobilier/etats-lieux/10/elements/1000/photos',
      expect.any(FormData),
      { headers: { 'Content-Type': 'multipart/form-data' } },
    ))
  })

  it('un état de SORTIE affiche EXACTEMENT les photos d’entrée renvoyées par le serveur', async () => {
    apiGet.mockImplementation((url) => {
      if (url === '/immobilier/etats-lieux/') return Promise.resolve({ data: [ETAT_SORTIE] })
      if (url === '/immobilier/etats-lieux/11/') return Promise.resolve({ data: ETAT_SORTIE })
      return Promise.resolve({ data: [] })
    })
    renderPage()
    await waitFor(() => expect(screen.getByText(/LOC-A101/)).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Bail'), { target: { value: '3' } })
    fireEvent.click(await screen.findByText(/Sortie — 2026-09-01/))
    await screen.findByText('Salon')

    const comparaison = await screen.findByTestId('photos-entree-1001')
    expect(comparaison.textContent).toContain('1 photo')
  })
})
