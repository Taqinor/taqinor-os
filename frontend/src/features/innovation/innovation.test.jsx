import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { transitionsPour, estTerminal, STATUT_MAP } from './innovationStatus'
import { contexteFromPath, linkedFromLocation } from './linkedContext'
import FilterSelect from './FilterSelect'

function wrap(ui, { route = '/' } = {}) {
  return (
    <MemoryRouter initialEntries={[route]}>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>
  )
}

// ── Stub complet du client API innovation (aucun réseau) ──
const innovationApiMock = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  contextes: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  similaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  examiner: vi.fn(),
  retenir: vi.fn(),
  realiser: vi.fn(),
  fermer: vi.fn(),
  historique: vi.fn(),
  lier: vi.fn(),
  reouvrir: vi.fn(),
  publier: vi.fn(),
  masquer: vi.fn(),
  vote: vi.fn(),
  retirerVote: vi.fn(),
  votesRecents: vi.fn(),
  mesVotes: vi.fn(),
}))
vi.mock('../../api/innovationApi', () => ({ default: innovationApiMock }))

// NTIDE15 (« Mes idées ») lit l'utilisateur connecté via useSelector — pas de
// Provider redux dans `wrap()`, on stub directement (patron
// UsersManagement.test.jsx).
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { id: 1, username: 'demo_user' } } }),
}))

// jsdom n'implémente pas ResizeObserver (Radix Switch/Select).
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

// Historique d'appels remis à zéro entre chaque test (mockClear conserve les
// implémentations par défaut, ex. `contextes`) — sinon un appel `create` d'un
// test précédent fait échouer `not.toHaveBeenCalled()` / `mock.calls[0]`.
beforeEach(() => {
  vi.clearAllMocks()
})

describe('innovation state machine helpers (miroir apps.innovation.services)', () => {
  it('transitionsPour reflète la machine à états backend', () => {
    expect(transitionsPour('ouvert')).toEqual(['examiner', 'fermer'])
    expect(transitionsPour('examinee')).toEqual(['retenir', 'fermer'])
    expect(transitionsPour('retenue')).toEqual(['realiser', 'fermer'])
    expect(transitionsPour('realisee')).toEqual([])
    expect(transitionsPour('fermee')).toEqual([])
  })

  it('estTerminal marque realisee/fermee comme terminaux', () => {
    expect(estTerminal('realisee')).toBe(true)
    expect(estTerminal('fermee')).toBe(true)
    expect(estTerminal('ouvert')).toBe(false)
    expect(estTerminal('retenue')).toBe(false)
  })

  it('STATUT_MAP couvre les 5 statuts backend', () => {
    expect(Object.keys(STATUT_MAP).sort()).toEqual(
      ['examinee', 'fermee', 'ouvert', 'realisee', 'retenue'],
    )
  })
})

describe('linkedContext (NTIDE9/NTIDE11)', () => {
  it('contexteFromPath dérive le contexte du 1er segment', () => {
    expect(contexteFromPath('/crm/leads/12')).toBe('CRM')
    expect(contexteFromPath('/sav')).toBe('SAV')
    expect(contexteFromPath('/ventes/devis')).toBe('Devis')
    expect(contexteFromPath('/ventes/nouveau')).toBe('Ventes')
    expect(contexteFromPath('/route-inconnue')).toBe('')
  })

  it('linkedFromLocation détecte un devis en édition (?edit=)', () => {
    expect(linkedFromLocation('/ventes/devis', '?edit=42'))
      .toEqual({ type: 'devis', id: '42' })
    expect(linkedFromLocation('/ventes/devis', '')).toBeNull()
    expect(linkedFromLocation('/sav', '?edit=42')).toBeNull()
  })
})

describe('FilterSelect (smoke)', () => {
  it('rend les options de statut et la valeur courante', () => {
    render(wrap(
      <FilterSelect
        value="retenue"
        onChange={() => {}}
        options={Object.entries(STATUT_MAP).map(([value, v]) => ({ value, label: v.label }))}
        aria-label="Statut"
      />,
    ))
    const select = screen.getByRole('combobox', { name: 'Statut' })
    expect(select.value).toBe('retenue')
    expect(screen.getByText('Retenue')).toBeTruthy()
  })
})

describe('IdeeDetail', () => {
  it('affiche titre/contexte/votes/lien et propose les transitions du statut', async () => {
    innovationApiMock.get.mockResolvedValue({
      data: {
        id: 1,
        titre: 'Ajouter un export PDF',
        description: 'Ce serait pratique.',
        contexte: 'SAV',
        statut: 'ouvert',
        votes_count: 3,
        auteur_nom: 'jdupont',
        linked_type: 'devis',
        linked_id: 42,
        date_creation: '2026-07-01T10:00:00Z',
        historique: [],
      },
    })

    const { default: IdeeDetail } = await import('./IdeeDetail')
    render(wrap(
      <Routes><Route path="/innovation/idees/:id" element={<IdeeDetail />} /></Routes>,
      { route: '/innovation/idees/1' },
    ))

    await waitFor(() => expect(screen.getByText('Ajouter un export PDF')).toBeTruthy())
    expect(screen.getByText('Devis #42')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Voter/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Examiner/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Fermer/ })).toBeTruthy()
  })

  it('une idée réalisée est terminale : aucune transition proposée', async () => {
    innovationApiMock.get.mockResolvedValue({
      data: {
        id: 2, titre: 'Idée livrée', statut: 'realisee', votes_count: 5,
        historique: [],
      },
    })
    const { default: IdeeDetail } = await import('./IdeeDetail')
    render(wrap(
      <Routes><Route path="/innovation/idees/:id" element={<IdeeDetail />} /></Routes>,
      { route: '/innovation/idees/2' },
    ))
    await waitFor(() => expect(screen.getByText('Idée livrée')).toBeTruthy())
    expect(screen.queryByRole('button', { name: /Examiner/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Fermer/ })).toBeNull()
  })

  it('vote : POST via innovationApi.vote puis recharge', async () => {
    innovationApiMock.get.mockResolvedValue({
      data: { id: 3, titre: 'Idée à voter', statut: 'ouvert', votes_count: 0, historique: [] },
    })
    innovationApiMock.vote.mockResolvedValue({ data: { id: 99 } })
    const { default: IdeeDetail } = await import('./IdeeDetail')
    render(wrap(
      <Routes><Route path="/innovation/idees/:id" element={<IdeeDetail />} /></Routes>,
      { route: '/innovation/idees/3' },
    ))
    await waitFor(() => expect(screen.getByText('Idée à voter')).toBeTruthy())
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /Voter/ }))
    await waitFor(() => expect(innovationApiMock.vote).toHaveBeenCalledWith('3'))
  })

  it('NTIDE17 — l\'auteur voit « Ré-ouvrir » sur une idée fermée et peut la ré-ouvrir', async () => {
    innovationApiMock.get.mockResolvedValue({
      data: {
        id: 4, titre: 'Idée fermée', statut: 'fermee', votes_count: 1,
        auteur: 1, historique: [],
      },
    })
    innovationApiMock.reouvrir.mockResolvedValue({ data: { id: 4 } })
    const { default: IdeeDetail } = await import('./IdeeDetail')
    render(wrap(
      <Routes><Route path="/innovation/idees/:id" element={<IdeeDetail />} /></Routes>,
      { route: '/innovation/idees/4' },
    ))
    await waitFor(() => expect(screen.getByText('Idée fermée')).toBeTruthy())
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /Ré-ouvrir/ }))
    await waitFor(() => expect(innovationApiMock.reouvrir).toHaveBeenCalledWith('4'))
  })

  it('NTIDE19 — « Masquer » confirmé appelle innovationApi.masquer', async () => {
    innovationApiMock.get.mockResolvedValue({
      data: { id: 6, titre: 'Idée à modérer', statut: 'ouvert', votes_count: 0, historique: [] },
    })
    innovationApiMock.masquer.mockResolvedValue({ data: { id: 6 } })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { default: IdeeDetail } = await import('./IdeeDetail')
    render(wrap(
      <Routes><Route path="/innovation/idees/:id" element={<IdeeDetail />} /></Routes>,
      { route: '/innovation/idees/6' },
    ))
    await waitFor(() => expect(screen.getByText('Idée à modérer')).toBeTruthy())
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /Masquer/ }))
    await waitFor(() => expect(innovationApiMock.masquer).toHaveBeenCalledWith('6'))
  })

  it('NTIDE17 — un non-auteur ne voit pas « Ré-ouvrir » sur une idée fermée', async () => {
    innovationApiMock.get.mockResolvedValue({
      data: {
        id: 5, titre: 'Idée fermée (autre auteur)', statut: 'fermee',
        votes_count: 1, auteur: 99, historique: [],
      },
    })
    const { default: IdeeDetail } = await import('./IdeeDetail')
    render(wrap(
      <Routes><Route path="/innovation/idees/:id" element={<IdeeDetail />} /></Routes>,
      { route: '/innovation/idees/5' },
    ))
    await waitFor(() => expect(screen.getByText('Idée fermée (autre auteur)')).toBeTruthy())
    expect(screen.queryByRole('button', { name: /Ré-ouvrir/ })).toBeNull()
  })
})

describe('MesIdeesPage (NTIDE15)', () => {
  it('charge les idées de l\'utilisateur connecté (filtre owner) et les affiche', async () => {
    innovationApiMock.list.mockResolvedValue({
      data: [
        { id: 1, titre: 'Ma première idée', statut: 'ouvert', votes_count: 2, date_creation: '2026-07-01T10:00:00Z' },
      ],
    })
    const { default: MesIdeesPage } = await import('./MesIdeesPage')
    render(wrap(<MesIdeesPage />))

    await waitFor(() => expect(innovationApiMock.list).toHaveBeenCalledWith({ owner: 1 }))
    expect(await screen.findByText('Ma première idée')).toBeTruthy()
  })
})

describe('ProposerIdeeForm (NTIDE8/NTIDE9)', () => {
  it('soumet titre/description/contexte', async () => {
    innovationApiMock.create.mockResolvedValue({ data: { id: 7 } })
    const onCreated = vi.fn()

    const { default: ProposerIdeeForm } = await import('./ProposerIdeeForm')
    render(wrap(<ProposerIdeeForm onCreated={onCreated} />))

    const titreInput = await screen.findByLabelText('Titre')
    const user = userEvent.setup()
    await user.type(titreInput, 'Automatiser les relances')
    await user.type(screen.getByLabelText('Contexte'), 'CRM')

    await user.click(screen.getByRole('button', { name: /Proposer l'idée/ }))

    await waitFor(() => expect(innovationApiMock.create).toHaveBeenCalled())
    const [payload] = innovationApiMock.create.mock.calls[0]
    expect(payload.titre).toBe('Automatiser les relances')
    expect(payload.contexte).toBe('CRM')
    expect(onCreated).toHaveBeenCalled()
  })

  it('NTIDE9 — propose le contexte autodétecté depuis la route courante', async () => {
    const { default: ProposerIdeeForm } = await import('./ProposerIdeeForm')
    render(wrap(<ProposerIdeeForm />, { route: '/crm/leads' }))
    expect((await screen.findByLabelText('Contexte')).value).toBe('CRM')
  })

  it('refuse un titre vide', async () => {
    const { default: ProposerIdeeForm } = await import('./ProposerIdeeForm')
    render(wrap(<ProposerIdeeForm />))
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /Proposer l'idée/ }))
    expect(innovationApiMock.create).not.toHaveBeenCalled()
  })

  it('NTIDE18 — coche « Enregistrer en brouillon » : payload.draft = true', async () => {
    innovationApiMock.create.mockResolvedValue({ data: { id: 10 } })
    const { default: ProposerIdeeForm } = await import('./ProposerIdeeForm')
    render(wrap(<ProposerIdeeForm />))

    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Titre'), 'Idée pas encore prête')
    await user.click(screen.getByRole('checkbox', { name: /Enregistrer en brouillon/ }))
    await user.click(screen.getByRole('button', { name: /Enregistrer en brouillon/ }))

    await waitFor(() => expect(innovationApiMock.create).toHaveBeenCalled())
    const [payload] = innovationApiMock.create.mock.calls[0]
    expect(payload.draft).toBe(true)
  })

  it('NTIDE20 — recherche des idées similaires et vote dessus au lieu de dupliquer', async () => {
    innovationApiMock.similaires.mockResolvedValue({
      data: {
        results: [
          { id: 42, titre: 'Idée déjà proposée', contexte: 'SAV', statut: 'ouvert', votes_count: 4 },
        ],
      },
    })
    innovationApiMock.vote.mockResolvedValue({ data: { id: 1 } })
    const { default: ProposerIdeeForm } = await import('./ProposerIdeeForm')
    render(wrap(<ProposerIdeeForm />))

    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Titre'), 'Export PDF')

    await waitFor(
      () => expect(innovationApiMock.similaires).toHaveBeenCalledWith('Export PDF'),
      { timeout: 2000 },
    )
    expect(await screen.findByText('Idée déjà proposée')).toBeTruthy()

    await user.click(screen.getByRole('button', { name: /4/ }))
    await waitFor(() => expect(innovationApiMock.vote).toHaveBeenCalledWith(42))
  })

  it('NTIDE10 — propose les contextes fréquents en autocomplétion (datalist)', async () => {
    innovationApiMock.contextes.mockResolvedValueOnce({
      data: { results: ['SAV', 'Devis', 'Stock'] },
    })
    const { default: ProposerIdeeForm } = await import('./ProposerIdeeForm')
    const { container } = render(wrap(<ProposerIdeeForm />))
    await waitFor(() => expect(innovationApiMock.contextes).toHaveBeenCalled())
    await waitFor(() => {
      const options = container.querySelectorAll('datalist option')
      expect(Array.from(options).map((o) => o.value)).toEqual(['SAV', 'Devis', 'Stock'])
    })
  })

  it('NTIDE11 — propose de lier l\'idée au devis en édition et l\'inclut au payload', async () => {
    innovationApiMock.create.mockResolvedValue({ data: { id: 8 } })
    const { default: ProposerIdeeForm } = await import('./ProposerIdeeForm')
    render(wrap(<ProposerIdeeForm />, { route: '/ventes/devis?edit=42' }))

    expect(await screen.findByText(/Ajouter une idée liée à ce devis #42/)).toBeTruthy()

    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Titre'), 'Ajouter une remise groupée')
    await user.click(screen.getByRole('button', { name: /Proposer l'idée/ }))

    await waitFor(() => expect(innovationApiMock.create).toHaveBeenCalled())
    const [payload] = innovationApiMock.create.mock.calls[0]
    expect(payload.linked_type).toBe('devis')
    expect(payload.linked_id).toBe('42')
  })

  it('NTIDE11 — décocher « lier » retire linked_type/linked_id du payload', async () => {
    innovationApiMock.create.mockResolvedValue({ data: { id: 9 } })
    const { default: ProposerIdeeForm } = await import('./ProposerIdeeForm')
    render(wrap(<ProposerIdeeForm />, { route: '/ventes/devis?edit=42' }))

    const user = userEvent.setup()
    await user.click(await screen.findByRole('checkbox'))
    await user.type(screen.getByLabelText('Titre'), 'Sans lien')
    await user.click(screen.getByRole('button', { name: /Proposer l'idée/ }))

    await waitFor(() => expect(innovationApiMock.create).toHaveBeenCalled())
    const [payload] = innovationApiMock.create.mock.calls[0]
    expect(payload.linked_type).toBeUndefined()
  })
})
