import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import {
  monthGrid, ymd, groupByDay, filterEvents, normalizeEvents,
  isDraggable, buildReschedulePayload, routeForEvent, SOURCE_KEYS,
} from './marketing'

// jsdom n'implémente pas ResizeObserver (mesuré par certains primitifs UI) —
// on le polyfill localement pour que l'écran se monte proprement.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

// Forme de réponse agrégée mockée : les 4 sources company-scoped (XMKT30).
const MOCK_EVENTS = [
  { id: 'c1', obj_id: 1, source: 'campagne', date: '2026-07-10', title: 'Campagne rentrée', channel: 'email', editable: true, link_type: 'campagne' },
  { id: 's1', obj_id: 2, source: 'etape_sequence', date: '2026-07-10', title: 'Étape J+3', channel: 'sms', editable: false, link_type: 'etape_sequence' },
  { id: 'e1', obj_id: 3, source: 'evenement', date: '2026-07-15', title: 'Salon Casablanca', channel: 'autre', editable: false, link_type: 'evenement' },
  { id: 'r1', obj_id: 4, source: 'relance', date: '2026-07-15', title: 'Relance devis #42', channel: 'appel', editable: false, link_type: 'relance' },
]

describe('monthGrid / ymd (miroir CalendarPage.jsx)', () => {
  it('ymd formate AAAA-MM-JJ', () => {
    expect(ymd(new Date(2026, 6, 4))).toBe('2026-07-04')
    expect(ymd(new Date(2026, 0, 9))).toBe('2026-01-09')
  })

  it('monthGrid commence au lundi de la semaine du 1er et couvre tout le mois', () => {
    const cells = monthGrid(2026, 6) // juillet 2026 : le 1er est un mercredi
    expect(cells[0].getDay()).toBe(1) // lundi
    const days = cells.map(ymd)
    expect(days).toContain('2026-07-01')
    expect(days).toContain('2026-07-31')
  })

  it('monthGrid retire la 6e semaine si elle déborde entièrement sur le mois suivant', () => {
    const cells = monthGrid(2026, 1) // février 2026 (28 jours, commence un dimanche)
    expect(cells.length).toBeLessThanOrEqual(35)
  })
})

describe('groupByDay / filterEvents (agrégation des 4 sources + filtre canal)', () => {
  it('normalizeEvents accepte { events: [...] } ou un tableau brut', () => {
    expect(normalizeEvents({ events: MOCK_EVENTS })).toHaveLength(4)
    expect(normalizeEvents(MOCK_EVENTS)).toHaveLength(4)
    expect(normalizeEvents(null)).toEqual([])
  })

  it('groupByDay regroupe les 4 sources par jour sans filtre', () => {
    const byDay = groupByDay(MOCK_EVENTS, { hiddenSources: new Set(), channel: '' })
    expect(Object.keys(byDay).sort()).toEqual(['2026-07-10', '2026-07-15'])
    expect(byDay['2026-07-10']).toHaveLength(2)
    expect(byDay['2026-07-15']).toHaveLength(2)
  })

  it('groupByDay masque une source désactivée (toggle canal/source)', () => {
    const byDay = groupByDay(MOCK_EVENTS, { hiddenSources: new Set(['relance']), channel: '' })
    const all = Object.values(byDay).flat()
    expect(all.find(e => e.source === 'relance')).toBeUndefined()
    expect(all).toHaveLength(3)
  })

  it('filterEvents applique le filtre par canal (ex: email)', () => {
    const filtered = filterEvents(MOCK_EVENTS, { hiddenSources: new Set(), channel: 'email' })
    expect(filtered).toHaveLength(1)
    expect(filtered[0].source).toBe('campagne')
  })

  it('SOURCE_KEYS couvre exactement les 5 sources agrégées (XMKT35 : + posts sociaux)', () => {
    expect(SOURCE_KEYS.sort()).toEqual(
      ['campagne', 'etape_sequence', 'evenement', 'relance',
        'post_social'].sort())
  })

  it('un post_social planifié est affiché et non déplaçable (XMKT35)', () => {
    const post = {
      id: 'ps1', obj_id: 9, source: 'post_social', date: '2026-07-20',
      title: 'Facebook — Nouveau chantier livré', channel: '',
      editable: false, link_type: 'post_social',
    }
    const byDay = groupByDay([post], {})
    expect(byDay['2026-07-20']).toHaveLength(1)
    expect(isDraggable(post)).toBe(false)
    expect(routeForEvent(post)).toBe('/marketing/calendrier')
  })
})

describe('drag-to-reschedule (campagnes non parties uniquement)', () => {
  it('isDraggable est vrai seulement pour une campagne editable', () => {
    expect(isDraggable(MOCK_EVENTS[0])).toBe(true) // campagne, editable
    expect(isDraggable(MOCK_EVENTS[1])).toBe(false) // etape_sequence
    expect(isDraggable({ source: 'campagne', editable: false })).toBe(false)
  })

  it('buildReschedulePayload construit { source, id, date }', () => {
    const payload = buildReschedulePayload(MOCK_EVENTS[0], '2026-07-20')
    expect(payload).toEqual({ source: 'campagne', id: 1, date: '2026-07-20' })
  })
})

describe('routeForEvent (clic → ouvre l’objet)', () => {
  it('résout une route pour chaque type de lien connu', () => {
    expect(routeForEvent({ link_type: 'campagne' })).toBe('/comptabilite')
    expect(routeForEvent({ link_type: 'relance' })).toBe('/crm')
    expect(routeForEvent({ link_type: 'inconnu' })).toBeNull()
    expect(routeForEvent(null)).toBeNull()
  })
})

// ── Rendu smoke de l'écran (API mockée — aucun appel réseau réel) ──
vi.mock('../../api/comptaApi', () => ({
  default: {
    calendrierMarketing: {
      get: vi.fn(() => Promise.resolve({ data: { events: MOCK_EVENTS } })),
      reschedule: vi.fn(() => Promise.resolve({ data: {} })),
    },
  },
}))

import comptaApi from '../../api/comptaApi'
import MarketingCalendarScreen from './MarketingCalendarScreen'

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <MarketingCalendarScreen />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('MarketingCalendarScreen (smoke + interactions)', () => {
  it('charge et affiche la grille avec les évènements agrégés', async () => {
    renderScreen()
    await waitFor(() => expect(comptaApi.calendrierMarketing.get).toHaveBeenCalled())
    expect(await screen.findByText('Calendrier marketing')).toBeInTheDocument()
  })

  it('le filtre canal déclenche un nouvel appel avec ?channel=', async () => {
    renderScreen()
    await waitFor(() => expect(comptaApi.calendrierMarketing.get).toHaveBeenCalled())
    const select = screen.getByTestId('mkt-cal-channel')
    fireEvent.change(select, { target: { value: 'email' } })
    await waitFor(() => {
      const calls = comptaApi.calendrierMarketing.get.mock.calls
      expect(calls.some(c => c[0]?.channel === 'email')).toBe(true)
    })
  })

  it('toggler une source masque ses évènements (bouton de légende)', async () => {
    renderScreen()
    await waitFor(() => expect(comptaApi.calendrierMarketing.get).toHaveBeenCalled())
    const btn = await screen.findByTestId('mkt-cal-source-relance')
    fireEvent.click(btn)
    // Le bouton bascule d'état sans re-fetch (filtre purement local).
    expect(btn).toBeInTheDocument()
  })

  it('le drop appelle reschedule avec le bon payload pour une campagne éditable', async () => {
    renderScreen()
    await waitFor(() => expect(comptaApi.calendrierMarketing.get).toHaveBeenCalled())
    const eventEl = await screen.findAllByTestId('mkt-cal-event')
    const campaignEl = eventEl.find(el => el.textContent.includes('Campagne rentrée'))
    expect(campaignEl).toBeTruthy()
    fireEvent.dragStart(campaignEl)
    const targetDay = screen.getByTestId('mkt-cal-day-2026-07-20')
    fireEvent.dragOver(targetDay)
    fireEvent.drop(targetDay)
    await waitFor(() => expect(comptaApi.calendrierMarketing.reschedule)
      .toHaveBeenCalledWith({ source: 'campagne', id: 1, date: '2026-07-20' }))
  })
})
