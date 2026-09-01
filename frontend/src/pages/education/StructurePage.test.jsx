import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR212 — trombinoscope (NTEDU38) : `classes.trombinoscope` était déjà
   câblé côté backend et même déjà exposé par `educationApi.js`
   (`classes.trombinoscope`), mais AUCUN écran ne l'appelait — action
   ajoutée sur StructurePage.jsx. Un élève sans photo (`photo_url: null`)
   DOIT afficher un avatar générique, jamais une image cassée (`<img
   src={null}>`). */

const {
  anneesScolaires, niveaux, classes,
} = vi.hoisted(() => ({
  anneesScolaires: { list: vi.fn() },
  niveaux: { list: vi.fn() },
  classes: { list: vi.fn(), trombinoscope: vi.fn() },
}))

vi.mock('../../api/educationApi', () => ({
  default: { anneesScolaires, niveaux, classes },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import StructurePage from './StructurePage'

const CLASSE = { id: 5, nom: 'CE1-A', niveau: 2, niveau_nom: 'CE1', effectif: 2, capacite_max: 30 }

function afficher() {
  return render(<ThemeProvider><StructurePage /></ThemeProvider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  anneesScolaires.list.mockResolvedValue({ data: [] })
  niveaux.list.mockResolvedValue({ data: [{ id: 2, nom: 'CE1', cycle: 'primaire' }] })
  classes.list.mockResolvedValue({ data: [CLASSE] })
  classes.trombinoscope.mockResolvedValue({
    data: {
      count: 2,
      results: [
        { id: 8, nom: 'Alami', prenom: 'Yassine', photo_url: '/api/django/records/attachments/40/download/' },
        { id: 9, nom: 'Bennani', prenom: 'Salma', photo_url: null },
      ],
    },
  })
})

describe('StructurePage — trombinoscope (WIR212/NTEDU38)', () => {
  it('rend la liste des classes avec le bouton Trombinoscope', async () => {
    afficher()
    expect(await screen.findByText('CE1-A')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Trombinoscope/i })).toBeInTheDocument()
  })

  it('ouvre le trombinoscope et affiche une photo réelle + un avatar générique (jamais une image cassée)', async () => {
    afficher()
    await screen.findByText('CE1-A')

    fireEvent.click(screen.getByRole('button', { name: /Trombinoscope/i }))

    await waitFor(() => expect(classes.trombinoscope).toHaveBeenCalledWith(5))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Trombinoscope — CE1-A')).toBeInTheDocument()

    // Élève AVEC photo : une vraie <img> pointant sur photo_url.
    const img = within(dialog).getByAltText('Yassine Alami')
    expect(img.tagName).toBe('IMG')
    expect(img).toHaveAttribute('src', '/api/django/records/attachments/40/download/')

    // Élève SANS photo (photo_url: null) : avatar générique (role="img" +
    // aria-label), jamais une balise <img> avec un src vide/null (image cassée).
    expect(within(dialog).queryByAltText('Salma Bennani')).not.toBeInTheDocument()
    expect(within(dialog).getByRole('img', { name: 'Salma Bennani — sans photo' })).toBeInTheDocument()
  })

  it('affiche un état vide propre si la classe n’a aucun élève', async () => {
    classes.trombinoscope.mockResolvedValueOnce({ data: { count: 0, results: [] } })
    afficher()
    await screen.findByText('CE1-A')

    fireEvent.click(screen.getByRole('button', { name: /Trombinoscope/i }))

    expect(await screen.findByText('Aucun élève dans cette classe.')).toBeInTheDocument()
  })
})
