import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
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

const mine = vi.hoisted(() => ({ value: { en_retard: [], aujourdhui: [], a_venir: [] } }))

vi.mock('../../api/recordsApi', () => ({
  default: {
    getMyActivities: () => Promise.resolve({ data: mine.value }),
    getMaFile: () => Promise.resolve({ data: { items: [], total: 0, resume: {} } }),
    getActivities: (model, id, extra) => Promise.resolve({ data: paginer(extra) }),
  },
}))

import MesActivitesPage from './MesActivitesPage'

afterEach(() => {
  cleanup()
  mine.value = { en_retard: [], aujourdhui: [], a_venir: [] }
})

const Lieu = () => <span data-testid="lieu">{useLocation().pathname}</span>

const rendre = () => {
  const store = configureStore({
    reducer: { auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [], user: { id: 1 } }) => s },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter><MesActivitesPage /></MemoryRouter>
    </Provider>,
  )
}

describe('AMSG102 — brouillon WhatsApp de la note', () => {
  const WA = 'https://wa.me/212612345678?text=Bonjour%20Sami'
  it('montre « Ouvrir WhatsApp » vers le lien de la note, sans target_phone', async () => {
    mine.value = {
      en_retard: [],
      a_venir: [],
      aujourdhui: [
        { id: 1, summary: 'Envoyer ce WhatsApp', target_model: 'installations.livraison', target_phone: null, note: `Bonjour Sami\n\n${WA}` },
        { id: 2, summary: 'Sans lien', target_model: 'installations.livraison', target_phone: null, note: 'Rien à envoyer' },
      ],
    }
    rendre()
    const lien = await screen.findByTitle('Ouvrir WhatsApp')
    expect(lien).toHaveAttribute('href', WA)
    expect(screen.getAllByTitle('Ouvrir WhatsApp')).toHaveLength(1)
  })
})

describe('AMSG103 — lien des tâches de chantier', () => {
  it('mène une tâche de livraison à /chantiers et une d’intervention à /interventions', async () => {
    mine.value = {
      en_retard: [],
      a_venir: [],
      aujourdhui: [
        { id: 1, summary: 'Livr', target_model: 'installations.livraison', target_label: 'Livraison L1' },
        { id: 2, summary: 'Interv', target_model: 'installations.intervention', target_label: 'Intervention I1' },
      ],
    }
    const store = configureStore({
      reducer: { auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [], user: { id: 1 } }) => s },
    })
    render(
      <Provider store={store}>
        <MemoryRouter>
          <MesActivitesPage />
          <Lieu />
        </MemoryRouter>
      </Provider>,
    )
    fireEvent.click(await screen.findByRole('button', { name: /Livraison L1/ }))
    expect(screen.getByTestId('lieu')).toHaveTextContent('/chantiers')
    fireEvent.click(screen.getByRole('button', { name: /Intervention I1/ }))
    expect(screen.getByTestId('lieu')).toHaveTextContent('/interventions')
  })
})

describe('AMSG104 — type absent', () => {
  it('affiche « — » sans « null », et garde l’icône et le nom d’une tâche typée', async () => {
    mine.value = {
      en_retard: [],
      a_venir: [],
      aujourdhui: [
        { id: 1, summary: 'Sans type', activity_type_icone: null, activity_type_nom: null },
        { id: 2, summary: 'Typée', activity_type_icone: '📞', activity_type_nom: 'Appel' },
      ],
    }
    rendre()
    await screen.findByText('Sans type')
    expect(document.body.textContent).not.toMatch(/null|undefined/)
    expect(screen.getByText('📞 Appel')).toBeTruthy()
    expect(screen.getByText('Sans type').closest('tr')).toHaveTextContent('—')
  })
})

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
