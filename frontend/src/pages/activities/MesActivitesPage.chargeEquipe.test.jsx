import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* ALEA20 — « Charge de l'équipe » est calculée sur TOUTES les activités
   ouvertes de la société, pas sur la première page. Serveur factice qui
   applique la VRAIE pagination DRF de `core/pagination.py` (50 par défaut,
   200 au plus via `page_size`) : on contrôle le TOTAL AFFICHÉ, jamais un
   espion d'appel. */

const ACTIVITES = Array.from({ length: 70 }, (_, i) => ({
  id: i + 1,
  done: false,
  due_date: '2020-01-01',
  assigned_to_nom: i % 2 === 0 ? 'Meryem' : 'Sami',
}))

function paginer(params = {}) {
  const taille = Math.min(Number(params.page_size) || 50, 200)
  const page = Number(params.page) || 1
  const debut = (page - 1) * taille
  const results = ACTIVITES.slice(debut, debut + taille)
  return {
    count: ACTIVITES.length,
    next: debut + taille < ACTIVITES.length ? `?page=${page + 1}` : null,
    previous: page > 1 ? `?page=${page - 1}` : null,
    results,
  }
}

vi.mock('../../api/recordsApi', () => ({
  default: {
    getMyActivities: () => Promise.resolve({ data: { en_retard: [], aujourdhui: [], a_venir: [] } }),
    getMaFile: () => Promise.resolve({ data: { items: [], total: 0, resume: {} } }),
    getActivities: (model, id, extra) => Promise.resolve({ data: paginer(extra) }),
  },
}))

import MesActivitesPage from './MesActivitesPage'

afterEach(cleanup)

describe('ALEA20 — Charge de l’équipe sur toutes les activités ouvertes', () => {
  it('somme 70 (et non 50) sur 2 responsables', async () => {
    const store = configureStore({
      reducer: { auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [], user: { id: 1 } }) => s },
    })
    render(
      <Provider store={store}>
        <MemoryRouter><MesActivitesPage /></MemoryRouter>
      </Provider>,
    )
    const titre = await screen.findByText(/Charge de l'équipe/)
    // Le badge d'en-tête (frère du titre) porte le TOTAL de toutes les pages.
    await waitFor(() => expect(titre.parentElement).toHaveTextContent('70'))
    // Deux responsables, 35 chacun.
    expect(screen.getByText('Meryem').parentElement).toHaveTextContent('35')
    expect(screen.getByText('Sami').parentElement).toHaveTextContent('35')
  })
})
