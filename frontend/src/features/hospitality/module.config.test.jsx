import { describe, it, expect, beforeAll, vi } from 'vitest'
import { Suspense } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR57 — le module Hôtellerie (5 écrans construits) n'avait AUCUN registre :
   ni route ni entrée de nav ne l'atteignait. On vérifie ici (1) que la config
   déclare bien les 5 routes + les 5 entrées de nav, et (2) que chaque écran se
   monte réellement via sa route (rendu via `config.routes`, réseau mocké). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('../../api/hospitalityApi', () => ({
  default: {
    tableauBord: () => Promise.resolve({
      data: { adr: 0, revpar: 0, taux_occupation: 0, no_show_rate: 0 },
    }),
    listChambres: () => Promise.resolve({ data: [{ id: 1, numero: '101', nom: '' }] }),
    listReservations: () => Promise.resolve({ data: [] }),
    listMainCourante: () => Promise.resolve({ data: [] }),
    listTachesMenage: () => Promise.resolve({ data: [] }),
  },
}))

import config from './module.config.jsx'

const PATHS = [
  '/hospitality',
  '/hospitality/chambres',
  '/hospitality/reservations',
  '/hospitality/main-courante',
  '/hospitality/menage',
]

function renderRoute(path) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Suspense fallback={<div>chargement…</div>}>
          <Routes>
            {config.routes.map((r) => {
              const C = r.component
              return <Route key={r.path} path={r.path} element={<C />} />
            })}
          </Routes>
        </Suspense>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('hospitality — module.config (WIR57)', () => {
  it('déclare les 5 routes ET les 5 entrées de nav HÔTELLERIE, gatées', () => {
    expect(config.key).toBe('hospitality')
    expect(config.nav.label).toBe('HÔTELLERIE')
    for (const p of PATHS) {
      const route = config.routes.find((r) => r.path === p)
      expect(route, `route ${p}`).toBeTruthy()
      expect(route.roles).toEqual(['normal', 'responsable', 'admin'])
      const nav = config.nav.items.find((i) => i.to === p)
      expect(nav, `nav ${p}`).toBeTruthy()
      expect(nav.icon).toBeTruthy()
    }
    expect(config.sectionLabels.hospitality).toBe('Hôtellerie')
  })

  it('monte le Tableau de bord via /hospitality', async () => {
    renderRoute('/hospitality')
    // Premier montage lazy du module : le chunk (+ Card/Stat) peut mettre plus
    // d'1s à se transformer en environnement de test, d'où un délai généreux.
    await waitFor(() => expect(screen.getByText('ADR (prix moyen/nuit)')).toBeTruthy(), { timeout: 5000 })
  })

  it('monte le Plan des chambres via /hospitality/chambres', async () => {
    renderRoute('/hospitality/chambres')
    await waitFor(() => expect(screen.getByText(/101/)).toBeTruthy(), { timeout: 5000 })
  })

  it('monte les Réservations via /hospitality/reservations', async () => {
    renderRoute('/hospitality/reservations')
    await waitFor(() => expect(screen.getByTestId('cell-1-0')).toBeTruthy(), { timeout: 5000 })
  })

  it('monte la Main courante via /hospitality/main-courante', async () => {
    renderRoute('/hospitality/main-courante')
    await waitFor(() => expect(screen.getByText('Aucune note')).toBeTruthy())
  })

  it('monte le Ménage via /hospitality/menage', async () => {
    renderRoute('/hospitality/menage')
    await waitFor(() => expect(screen.getByText('Aucune tâche à faire')).toBeTruthy())
  })
})
