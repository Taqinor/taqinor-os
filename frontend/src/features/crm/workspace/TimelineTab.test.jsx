import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { initState } from './draftCore'
import TimelineTab, { matchesTimelineFilter, TIMELINE_FILTERS } from './TimelineTab'

/* LW20 — `TimelineTab` : en-tête multi-touch (points-contact/, silencieux si
   vide), filtre par type persisté, notes épinglées en tête (📌) avec action
   épingler/désépingler, composer (note+fichier+CallLogPopover) dont l'état
   vient EXCLUSIVEMENT des props `composer`/`setComposer`/`resetComposer`
   (jamais un `useState` local pour la note — l'anti-fuite du moteur, D2). */

const { apiGet, apiPost } = vi.hoisted(() => ({
  apiGet: vi.fn(() => Promise.resolve({ data: [] })),
  apiPost: vi.fn(() => Promise.resolve({ data: { id: 99, kind: 'note', body: 'x' } })),
}))
vi.mock('../../../api/axios', () => ({ default: { get: apiGet, post: apiPost } }))

const { getLeadPointsContact } = vi.hoisted(() => ({
  getLeadPointsContact: vi.fn(() => Promise.resolve({ data: { count: 0, timeline: [] } })),
}))
vi.mock('../../../api/crmApi', () => ({ default: { getLeadPointsContact } }))

vi.mock('../../../api/marketingApi', () => ({
  default: {
    campagnes: { list: vi.fn(() => Promise.resolve({ data: [] })) },
    sequences: { list: vi.fn(() => Promise.resolve({ data: [] })) },
    unwrapList: (r) => r.data ?? [],
  },
}))

const { toastError } = vi.hoisted(() => ({ toastError: vi.fn() }))
vi.mock('../../../lib/toast', () => ({
  toastError,
  errorMessageFrom: (err, fallback) => fallback,
}))

afterEach(() => { cleanup(); vi.clearAllMocks(); try { localStorage.clear() } catch { /* noop */ } })

const leadState = () => initState({ lead: { id: 7, nom: 'Karim' }, mode: 'edit' })

const composerBase = (overrides = {}) => ({ note: '', file: null, ...overrides })

function renderTab(props = {}) {
  const setComposer = vi.fn()
  const resetComposer = vi.fn()
  const refreshHistorique = vi.fn()
  const utils = render(
    <TimelineTab
      state={leadState()}
      historique={[]}
      refreshHistorique={refreshHistorique}
      composer={composerBase()}
      setComposer={setComposer}
      resetComposer={resetComposer}
      {...props}
    />,
  )
  return { ...utils, setComposer, resetComposer, refreshHistorique }
}

describe('LW20 — logique pure du filtre (co-localisée, testable sans DOM)', () => {
  it('matchesTimelineFilter route chaque kind vers le bon filtre', () => {
    expect(matchesTimelineFilter('note', 'notes')).toBe(true)
    expect(matchesTimelineFilter('appel', 'notes')).toBe(false)
    expect(matchesTimelineFilter('appel', 'appels')).toBe(true)
    expect(matchesTimelineFilter('email', 'appels')).toBe(false)
    expect(matchesTimelineFilter('email', 'emails')).toBe(true)
    expect(matchesTimelineFilter('devis_signed', 'devis')).toBe(true)
    expect(matchesTimelineFilter('creation', 'systeme')).toBe(true)
    expect(matchesTimelineFilter('modification', 'systeme')).toBe(true)
    expect(matchesTimelineFilter('note', 'tous')).toBe(true)
  })
  it('TIMELINE_FILTERS liste les 6 filtres attendus', () => {
    expect(TIMELINE_FILTERS.map((f) => f.key)).toEqual(['tous', 'notes', 'appels', 'emails', 'devis', 'systeme'])
  })
})

describe('LW20 — en-tête multi-touch (points-contact/, silencieux)', () => {
  it('rend le résumé quand count > 0', async () => {
    getLeadPointsContact.mockResolvedValueOnce({
      data: {
        count: 3,
        timeline: [{ date_contact: '2026-01-01T10:00:00Z' }, { date_contact: '2026-01-10T10:00:00Z' }],
      },
    })
    renderTab()
    expect(await screen.findByText(/3 touches/)).toBeInTheDocument()
  })

  it('silencieux (aucun bloc) quand count = 0 ou en erreur', async () => {
    getLeadPointsContact.mockResolvedValueOnce({ data: { count: 0, timeline: [] } })
    renderTab()
    await waitFor(() => expect(getLeadPointsContact).toHaveBeenCalled())
    expect(screen.queryByText(/touche/)).toBeNull()
  })
})

describe('LW20 — filtre par type, persisté', () => {
  const entries = [
    { id: 1, kind: 'note', body: 'Une note', user_nom: 'Sami', created_at: new Date().toISOString() },
    { id: 2, kind: 'appel', outcome: 'joint', user_nom: 'Sami', created_at: new Date().toISOString() },
  ]

  it('filtre « Appels » ne montre que les entrées kind=appel (exclut les notes)', async () => {
    const user = userEvent.setup()
    renderTab({ historique: entries })
    expect(screen.getByText(/Une note/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Appels' }))
    expect(screen.queryByText(/Une note/)).toBeNull()
    expect(screen.getByText('Appel')).toBeInTheDocument()
    expect(localStorage.getItem('taqinor.lw.timelineFilter')).toBe('appels')
  })
})

describe('LW20 — notes épinglées (📌) + épingler/désépingler', () => {
  it('une note épinglée est rendue en tête avec l\'icône 📌', () => {
    const entries = [
      { id: 1, kind: 'note', body: 'Note normale', user_nom: 'Sami', pinned: false, created_at: new Date().toISOString() },
      { id: 2, kind: 'note', body: 'Note importante', user_nom: 'Sami', pinned: true, created_at: new Date().toISOString() },
    ]
    renderTab({ historique: entries })
    expect(screen.getByText('📌')).toBeInTheDocument()
  })

  it('cliquer sur épingler/désépingler appelle le bon endpoint puis refreshHistorique', async () => {
    const user = userEvent.setup()
    const entries = [
      { id: 5, kind: 'note', body: 'À épingler', user_nom: 'Sami', pinned: false, created_at: new Date().toISOString() },
    ]
    const { refreshHistorique } = renderTab({ historique: entries })
    await user.click(screen.getByRole('button', { name: 'Épingler cette note' }))
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/crm/leads/7/activites/5/epingler/'))
    await waitFor(() => expect(refreshHistorique).toHaveBeenCalled())
  })
})

describe('LW20 — composer (état MOTEUR via props, jamais local)', () => {
  it('taper dans le champ appelle setComposer({note}) — jamais un state local', () => {
    const { setComposer } = renderTab()
    fireEvent.change(screen.getByPlaceholderText('Écrire une note (appel, commentaire…)'), {
      target: { value: 'Bonjour' },
    })
    expect(setComposer).toHaveBeenCalledWith({ note: 'Bonjour' })
  })

  it('Entrée poste la note (composer.note fourni par le moteur) puis vide via resetComposer', async () => {
    const { resetComposer, refreshHistorique } = renderTab({ composer: composerBase({ note: 'Bonjour client' }) })
    fireEvent.keyDown(screen.getByPlaceholderText('Écrire une note (appel, commentaire…)'), { key: 'Enter' })
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/crm/leads/7/noter/', { body: 'Bonjour client' }))
    await waitFor(() => expect(resetComposer).toHaveBeenCalled())
    expect(refreshHistorique).toHaveBeenCalled()
  })

  it('note vide et sans fichier : Entrée ne poste rien', () => {
    renderTab({ composer: composerBase() })
    fireEvent.keyDown(screen.getByPlaceholderText('Écrire une note (appel, commentaire…)'), { key: 'Enter' })
    expect(apiPost).not.toHaveBeenCalled()
  })

  it('échec de la note : toast, jamais avalé', async () => {
    apiPost.mockRejectedValueOnce({ response: { data: {} } })
    const { resetComposer } = renderTab({ composer: composerBase({ note: 'Bonjour' }) })
    fireEvent.keyDown(screen.getByPlaceholderText('Écrire une note (appel, commentaire…)'), { key: 'Enter' })
    await waitFor(() => expect(toastError).toHaveBeenCalled())
    expect(resetComposer).not.toHaveBeenCalled()
  })

  it('une pièce jointe en cours (composer.file) affiche l\'aperçu nommé', () => {
    const file = new File(['x'], 'photo.jpg', { type: 'image/jpeg' })
    renderTab({ composer: composerBase({ file }) })
    expect(screen.getByTestId('chatter-note-file-preview')).toHaveTextContent('photo.jpg')
  })

  // VX111 (migré de LeadFormVX111NoteAttachment) — une note AVEC pièce jointe
  // part en multipart (FormData), jamais en JSON ; le chemin JSON sans fichier
  // est déjà couvert ci-dessus.
  it('note AVEC pièce jointe : POST multipart FormData (jamais du JSON)', async () => {
    const file = new File(['x'], 'photo.png', { type: 'image/png' })
    renderTab({ composer: composerBase({ note: 'photo toiture', file }) })
    fireEvent.click(screen.getByRole('button', { name: 'Noter' }))
    await waitFor(() => expect(apiPost).toHaveBeenCalled())
    const [url, body, config] = apiPost.mock.calls[0]
    expect(url).toBe('/crm/leads/7/noter/')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('body')).toBe('photo toiture')
    expect(body.get('file')).toBe(file)
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
  })
})

describe('LW20 — source des entrées (chatter_recent en 1er rendu, historique ensuite)', () => {
  it('utilise state.server.chatter_recent quand historique est vide', () => {
    const state = initState({
      lead: { id: 7, nom: 'Karim', chatter_recent: [{ id: 1, kind: 'note', body: 'Depuis chatter_recent', user_nom: 'Sami', created_at: new Date().toISOString() }] },
      mode: 'edit',
    })
    renderTab({ state, historique: [] })
    expect(screen.getByText(/Depuis chatter_recent/)).toBeInTheDocument()
  })

  it('préfère historique dès qu\'il a des entrées', () => {
    const state = initState({
      lead: { id: 7, nom: 'Karim', chatter_recent: [{ id: 1, kind: 'note', body: 'Ancien', user_nom: 'Sami', created_at: new Date().toISOString() }] },
      mode: 'edit',
    })
    renderTab({
      state,
      historique: [{ id: 2, kind: 'note', body: 'À jour', user_nom: 'Sami', created_at: new Date().toISOString() }],
    })
    expect(screen.getByText(/À jour/)).toBeInTheDocument()
    expect(screen.queryByText(/Ancien/)).toBeNull()
  })
})
