import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { configureStore } from '@reduxjs/toolkit'
import { Provider } from 'react-redux'
import ChartsView from './ChartsView'

/* VX144(e) — les 4 graphiques de ChartsView pesaient tous pareil (grille 2×2
   stricte) ; l'entonnoir « Leads par étape » (le plus lu du module) passe en
   pleine largeur en desktop. On vérifie que sa Card porte `ch-card-wide` et
   qu'elle est bien la SEULE des 4 à le porter.
   LB30 — ChartsView rend `CrmInsightsPanel`, qui lit désormais la company
   active (`useSelector`, cache session) : un Provider minimal est requis
   pour TOUT rendu de ChartsView (même motif que CrmInsightsPanel.test.jsx). */

function makeStore() {
  return configureStore({
    reducer: { auth: (state = { user: { id: 1, active_company_id: 1 } }) => state },
  })
}
function renderWithStore(ui) {
  return render(<Provider store={makeStore()}>{ui}</Provider>)
}

vi.mock('../../../../api/crmApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getCanaux: vi.fn(() => Promise.resolve({ data: [] })),
      getObjectifsAttainment: vi.fn(() => Promise.resolve({ data: [] })),
      getRoiSources: vi.fn(() => Promise.resolve({ data: [] })),
      getSlaBreach: vi.fn(() => Promise.resolve({ data: [] })),
    },
  }
})

// jsdom n'implémente pas ResizeObserver (mesuré par recharts ResponsiveContainer).
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  window.matchMedia = window.matchMedia || ((query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  }))
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

const leads = [
  { id: 1, stage: 'NEW', nom: 'A' },
  { id: 2, stage: 'CONTACTED', nom: 'B' },
]

describe('ChartsView — VX144(e) entonnoir pleine largeur', () => {
  it('« Leads par étape » porte ch-card-wide, les 3 autres graphiques non', () => {
    const { container } = renderWithStore(<ChartsView leads={leads} />)
    const titles = [...container.querySelectorAll('.ch-card')].map((card) => ({
      title: card.querySelector('[class*="CardTitle"], h3, h2')?.textContent
        ?? card.textContent.slice(0, 40),
      wide: card.classList.contains('ch-card-wide'),
    }))
    const wideCards = [...container.querySelectorAll('.ch-card-wide')]
    expect(wideCards).toHaveLength(1)
    expect(wideCards[0].textContent).toContain('Leads par étape')
    // aucune autre carte de graphique ne porte la classe
    const others = [...container.querySelectorAll('.ch-card:not(.ch-card-wide)')]
    expect(others).toHaveLength(3)
    expect(titles.length).toBeGreaterThan(0)
  })
})

describe('ChartsView — LB30 ligne de contexte filtres', () => {
  it('affiche « Ces graphiques suivent les filtres actifs (N leads) » avec le compte réel', () => {
    renderWithStore(<ChartsView leads={leads} />)
    expect(screen.getByText('Ces graphiques suivent les filtres actifs (2 leads)')).toBeInTheDocument()
  })

  it('accord singulier à 1 lead', () => {
    renderWithStore(<ChartsView leads={[leads[0]]} />)
    expect(screen.getByText('Ces graphiques suivent les filtres actifs (1 lead)')).toBeInTheDocument()
  })
})
