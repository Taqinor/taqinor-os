import { describe, it, expect, vi, beforeEach, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* VIS1 (fondateur 14/09/2026) — écran « Visiteurs & alertes ». Même patron que
   `RelancesSuiviPage.test.jsx` : le hook de rôle est mocké (réassignable par
   test) plutôt que de monter un vrai Provider redux. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const isAdminOrResponsableMock = vi.fn(() => false)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))

const {
  getAppareilsVisites, getVisitesExternes, getAppareilsEquipe,
  createAppareilEquipe, deleteAppareilEquipe,
} = vi.hoisted(() => ({
  getAppareilsVisites: vi.fn(),
  getVisitesExternes: vi.fn(),
  getAppareilsEquipe: vi.fn(),
  createAppareilEquipe: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
  deleteAppareilEquipe: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getAppareilsVisites: (...args) => getAppareilsVisites(...args),
    getVisitesExternes: (...args) => getVisitesExternes(...args),
    getAppareilsEquipe: (...args) => getAppareilsEquipe(...args),
    createAppareilEquipe: (...args) => createAppareilEquipe(...args),
    deleteAppareilEquipe: (...args) => deleteAppareilEquipe(...args),
  },
}))

import VisiteursPage from './VisiteursPage'

const APPAREIL_SUSPECT = {
  appareil_id: 'ab12cd34ef56', visites: 6, duree_totale_s: 725,
  premiere: '2026-09-01T10:00:00Z', derniere: '2026-09-10T14:00:00Z',
  propositions: 2, equipe: false,
  leads: [{ id: 1, nom: 'Ahmed Alami' }, { id: 2, nom: 'Sara B.' }],
}
const APPAREIL_EQUIPE = {
  appareil_id: 'ffff0000aaaa', visites: 30, duree_totale_s: 3600,
  premiere: '2026-08-01T10:00:00Z', derniere: '2026-09-12T14:00:00Z',
  propositions: 10, equipe: true,
  leads: [{ id: 3, nom: 'Karim T.' }],
}

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(false)
  getAppareilsVisites.mockResolvedValue({ data: { results: [APPAREIL_SUSPECT, APPAREIL_EQUIPE] } })
  getAppareilsEquipe.mockResolvedValue({
    data: { results: [{ id: 5, appareil_id: 'ffff0000aaaa', libelle: 'Téléphone Reda', created_at: '2026-08-01T00:00:00Z' }] },
  })
  getVisitesExternes.mockResolvedValue({
    data: {
      results: [
        {
          id: 100, point: 'proposition', point_display: 'Proposition', contexte: 'devis #12',
          lead: 1, lead_nom: 'Ahmed Alami', duree_s: 90, ip: '41.1.2.3', created_at: '2026-09-10T14:00:00Z',
        },
      ],
    },
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount(initialEntries = ['/crm/visiteurs']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <VisiteursPage />
    </MemoryRouter>,
  )
}

describe('VisiteursPage (VIS1)', () => {
  it('liste les appareils avec leurs leads touchés et signale le cas multi-prospects', async () => {
    mount()
    await waitFor(() => expect(getAppareilsVisites).toHaveBeenCalled())

    expect(await screen.findByText('Ahmed Alami')).toBeInTheDocument()
    expect(screen.getByText('Sara B.')).toBeInTheDocument()
    expect(screen.getByText('Multi-prospects')).toBeInTheDocument()
    // L'appareil équipe ne porte jamais le badge suspect, même à 2+ leads.
    expect(screen.getAllByText('Équipe')).toHaveLength(1)
  })

  it('masque les actions d’exclusion équipe au rôle normal', async () => {
    isAdminOrResponsableMock.mockReturnValue(false)
    mount()
    await waitFor(() => expect(getAppareilsVisites).toHaveBeenCalled())
    await screen.findByText('Ahmed Alami')

    expect(screen.queryByRole('button', { name: 'Marquer appareil équipe' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Retirer de l’équipe' })).not.toBeInTheDocument()
    // Section « Appareils équipe » réservée elle aussi.
    expect(screen.queryByText('Appareils équipe')).not.toBeInTheDocument()
  })

  it('marque un appareil équipe (responsable/admin) avec un libellé optionnel', async () => {
    isAdminOrResponsableMock.mockReturnValue(true)
    const user = userEvent.setup()
    mount()
    await screen.findByText('Ahmed Alami')

    await user.click(screen.getByRole('button', { name: 'Marquer appareil équipe' }))
    await user.type(screen.getByLabelText('Libellé (optionnel)'), 'Téléphone Reda')
    await user.click(screen.getByRole('button', { name: 'Marquer équipe' }))

    await waitFor(() => expect(createAppareilEquipe).toHaveBeenCalledWith({
      appareil_id: 'ab12cd34ef56', libelle: 'Téléphone Reda',
    }))
    // Refresh des deux listes après la mutation.
    await waitFor(() => expect(getAppareilsVisites).toHaveBeenCalledTimes(2))
    expect(getAppareilsEquipe).toHaveBeenCalledTimes(2)
  })

  it('retire un appareil de l’équipe via la ligne de la section dédiée', async () => {
    isAdminOrResponsableMock.mockReturnValue(true)
    const user = userEvent.setup()
    mount()
    await screen.findByText('Appareils équipe')
    expect(screen.getByText('Téléphone Reda')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Retirer' })[0])
    await waitFor(() => expect(deleteAppareilEquipe).toHaveBeenCalledWith(5))
  })

  it('déplie le détail des visites récentes d’un appareil', async () => {
    const user = userEvent.setup()
    mount()
    await screen.findByText('Ahmed Alami')

    await user.click(screen.getByText('ab12cd34…'))
    await waitFor(() => expect(getVisitesExternes).toHaveBeenCalledWith({ appareil_id: 'ab12cd34ef56' }))
    expect(await screen.findByText('devis #12')).toBeInTheDocument()
  })

  it('pré-filtre sur l’appareil du lien profond (?appareil=)', async () => {
    mount(['/crm/visiteurs?appareil=ab12cd34ef56'])
    await waitFor(() => expect(getAppareilsVisites).toHaveBeenCalledWith({ appareil_id: 'ab12cd34ef56' }))
    expect(screen.getByText(/Filtré sur l’appareil/)).toBeInTheDocument()
  })
})
