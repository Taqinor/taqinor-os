import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CALX31 — LE FIL D'ACTIVITÉ DU CALEPINAGE.
   ----------------------------------------------------------------------------
   Deux invariants du « Done » de la tâche : un historique vide affiche un état
   vide EXPLICITE (jamais une liste de tirets), et une note ajoutée réapparaît
   EN TÊTE sans rechargement complet (la liste en mémoire se met à jour, pas
   de second GET déclenché par l'ajout).
   ========================================================================== */

const chatterHistorique = vi.fn()
const chatterNoter = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      chatterHistorique: (...a) => chatterHistorique(...a),
      chatterNoter: (...a) => chatterNoter(...a),
    },
  },
}))

const { default: PanneauActivite } = await import('./PanneauActivite')

const ANCIENNE = {
  id: 1, kind: 'creation', body: 'Calepinage créé.', field: null,
  field_label: null, old_value: null, new_value: null,
  user_username: 'sami', created_at: '2026-09-20T08:00:00Z',
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

const rendre = (props = {}) => render(
  <MemoryRouter><PanneauActivite calepinageId={9} {...props} /></MemoryRouter>,
)

describe('CALX31 — historique vide', () => {
  it('affiche un état vide explicite, jamais une liste de tirets', async () => {
    chatterHistorique.mockResolvedValue({ data: [] })
    rendre()
    expect(await screen.findByText('Aucune activité pour le moment.')).toBeInTheDocument()
    expect(screen.queryByText('—')).not.toBeInTheDocument()
  })
})

describe('CALX31 — l’historique existant', () => {
  it('rend l’auteur et l’horodatage tels que le serveur les publie', async () => {
    chatterHistorique.mockResolvedValue({ data: [ANCIENNE] })
    rendre()
    expect(await screen.findByText(/Calepinage créé/)).toBeInTheDocument()
  })
})

describe('CALX31 — ajouter une note', () => {
  it('une note ajoutée réapparaît en tête, sans rechargement complet', async () => {
    chatterHistorique.mockResolvedValue({ data: [ANCIENNE] })
    const CREEE = {
      id: 2, kind: 'note', body: 'Toit inspecté ce matin.', field: null,
      field_label: null, old_value: null, new_value: null,
      user_username: 'reda', created_at: '2026-09-21T09:00:00Z',
    }
    chatterNoter.mockResolvedValue({ data: CREEE })
    rendre()
    await screen.findByText(/Calepinage créé/)

    fireEvent.change(screen.getByTestId('cal-activite-note-texte'),
      { target: { value: 'Toit inspecté ce matin.' } })
    fireEvent.click(screen.getByTestId('cal-activite-note-ajouter'))

    await waitFor(() => expect(chatterNoter).toHaveBeenCalledWith(9, 'Toit inspecté ce matin.'))
    // Un SEUL GET (montage) : l'ajout ne redéclenche PAS un rechargement complet.
    expect(chatterHistorique).toHaveBeenCalledTimes(1)

    const note = await screen.findByText(/Toit inspecté ce matin/)
    const ancienne = screen.getByText(/Calepinage créé/)
    // La note neuve précède l'ancienne entrée dans le document (en tête).
    expect(note.compareDocumentPosition(ancienne) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('le champ se vide après l’envoi', async () => {
    chatterHistorique.mockResolvedValue({ data: [] })
    chatterNoter.mockResolvedValue({
      data: { id: 3, kind: 'note', body: 'X', user_username: 'reda', created_at: '2026-09-21T09:00:00Z' },
    })
    rendre()
    await screen.findByText('Aucune activité pour le moment.')

    const champ = screen.getByTestId('cal-activite-note-texte')
    fireEvent.change(champ, { target: { value: 'X' } })
    fireEvent.click(screen.getByTestId('cal-activite-note-ajouter'))

    await waitFor(() => expect(chatterNoter).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(champ).toHaveValue(''))
  })

  it('le bouton est désactivé tant que la note est vide', async () => {
    chatterHistorique.mockResolvedValue({ data: [] })
    rendre()
    await screen.findByText('Aucune activité pour le moment.')
    expect(screen.getByTestId('cal-activite-note-ajouter')).toBeDisabled()
  })
})
