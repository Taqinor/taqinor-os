import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'

/* P169 — ParrainagePage : refonte sans style={} en dur (Tailwind/tokens). On
   garde un test de non-régression : la page se rend, affiche les stats et le
   formulaire, et ne contient AUCUN attribut style inline. crmApi est mocké. */

vi.mock('../../api/crmApi', () => ({
  default: {
    getParrainages: () => Promise.resolve({ data: [] }),
    parrainageStats: () => Promise.resolve({
      data: {
        total: 5,
        par_statut: { converti: 2 },
        recompenses_total: 1000,
        recompenses_versees: 400,
      },
    }),
    getClients: () => Promise.resolve({ data: [{ id: 1, nom: 'Dupont', prenom: 'Jean' }] }),
    saveParrainage: () => Promise.resolve({ data: {} }),
  },
}))

import ParrainagePage from './ParrainagePage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ParrainagePage (P169 — sans style inline)', () => {
  it('se rend, affiche les stats et le formulaire', async () => {
    const { container } = render(<ParrainagePage />)
    expect(screen.getByRole('heading', { name: 'Parrainage' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Parrainages')).toBeInTheDocument())
    expect(screen.getByText('Convertis')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '+ Ajouter' })).toBeInTheDocument()
    // P169 — aucun attribut style inline ne doit subsister dans le rendu.
    expect(container.querySelectorAll('[style]')).toHaveLength(0)
  })
})
