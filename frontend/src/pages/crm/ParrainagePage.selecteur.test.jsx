import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'

/* ALEA20 — le sélecteur « Parrain (client) » liste TOUS les clients : le client
   le plus ancien (au-delà de la page 1) est trouvable. Serveur factice avec la
   VRAIE pagination DRF de `core/pagination.py` (50 par défaut, 200 au plus). */

const CLIENTS = Array.from({ length: 60 }, (_, i) => ({
  id: i + 1, nom: i === 59 ? 'Ancien' : `Client${i + 1}`, prenom: '',
}))

function paginer(params = {}) {
  const taille = Math.min(Number(params.page_size) || 50, 200)
  const page = Number(params.page) || 1
  const debut = (page - 1) * taille
  return {
    count: CLIENTS.length,
    next: debut + taille < CLIENTS.length ? `?page=${page + 1}` : null,
    previous: null,
    results: CLIENTS.slice(debut, debut + taille),
  }
}

vi.mock('../../api/crmApi', () => ({
  default: {
    getParrainages: () => Promise.resolve({ data: [] }),
    parrainageStats: () => Promise.resolve({ data: { total: 0, par_statut: {} } }),
    getClients: (params) => Promise.resolve({ data: paginer(params) }),
    saveParrainage: () => Promise.resolve({ data: {} }),
  },
}))

import ParrainagePage from './ParrainagePage'

afterEach(cleanup)

describe('ALEA20 — ParrainagePage : sélecteur sans troncature à 50', () => {
  it('le client le plus ancien (60e) est proposé', async () => {
    render(<ParrainagePage />)
    await waitFor(() => {
      expect(screen.getByRole('option', { name: /Ancien/ })).toBeInTheDocument()
    })
    expect(screen.getAllByRole('option').length).toBeGreaterThan(60)
  })
})
