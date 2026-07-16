import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { transitionsPour, estTerminal, STATUT_MAP } from './innovationStatus'
import { contexteFromPath } from './linkedContext'
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
  examiner: vi.fn(),
  retenir: vi.fn(),
  realiser: vi.fn(),
  fermer: vi.fn(),
  historique: vi.fn(),
  vote: vi.fn(),
  retirerVote: vi.fn(),
  votesRecents: vi.fn(),
  mesVotes: vi.fn(),
}))
vi.mock('../../api/innovationApi', () => ({ default: innovationApiMock }))

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

describe('linkedContext (NTIDE9)', () => {
  it('contexteFromPath dérive le contexte du 1er segment', () => {
    expect(contexteFromPath('/crm/leads/12')).toBe('CRM')
    expect(contexteFromPath('/sav')).toBe('SAV')
    expect(contexteFromPath('/ventes/devis')).toBe('Devis')
    expect(contexteFromPath('/ventes/nouveau')).toBe('Ventes')
    expect(contexteFromPath('/route-inconnue')).toBe('')
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
})
