import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import crmApi from '../../api/crmApi'

/* P169 — ParrainagePage : refonte sans style={} en dur (Tailwind/tokens). On
   garde un test de non-régression : la page se rend, affiche les stats et le
   formulaire, et ne contient AUCUN attribut style inline. crmApi est mocké. */

vi.mock('../../api/crmApi', () => ({
  default: {
    getParrainages: vi.fn(() => Promise.resolve({ data: [] })),
    parrainageStats: () => Promise.resolve({
      data: {
        total: 5,
        par_statut: { converti: 2 },
        recompenses_total: 1000,
        recompenses_versees: 400,
      },
    }),
    getClients: () => Promise.resolve({ data: [{ id: 1, nom: 'Dupont', prenom: 'Jean' }] }),
    getLeads: () => Promise.resolve({ data: [{ id: 7, nom: 'Karim', prenom: '' }] }),
    saveParrainage: vi.fn(() => Promise.resolve({ data: {} })),
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

  it('affiche le nom du filleul lié plutôt que le texte libre', async () => {
    // ASOC75 — la colonne lit `filleul_display_nom` (DC14 : le lien prime).
    crmApi.getParrainages.mockResolvedValueOnce({ data: [
      { id: 1, parrain_nom: 'Dupont', filleul_nom: 'K.', filleul_display_nom: 'Karim', statut: 'en_attente' },
      { id: 2, parrain_nom: 'Dupont', filleul_nom: 'Libre', filleul_display_nom: 'Libre', statut: 'en_attente' },
      { id: 3, parrain_nom: 'Dupont', filleul_nom: '', filleul_display_nom: '', statut: 'en_attente' },
    ] })
    render(<ParrainagePage />)
    expect(await screen.findByRole('cell', { name: 'Karim' })).toBeInTheDocument()
    expect(screen.queryByText('K.')).not.toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Libre' })).toBeInTheDocument()
    const lignes = screen.getAllByRole('row')
    expect(lignes[lignes.length - 1]).toHaveTextContent(/^Dupont—/)
  })

  it('crée un parrainage lié au lead filleul', async () => {
    // ASOC68 — le lead choisi part en `filleul_lead` (sinon l'acceptation
    // de son devis ne convertit jamais le parrainage).
    render(<ParrainagePage />)
    await waitFor(() => expect(screen.getByRole('option', { name: /Karim/ })).toBeInTheDocument())
    fireEvent.change(screen.getByRole('combobox', { name: 'Filleul (lead)' }),
      { target: { value: '7' } })
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: '+ Ajouter' }))
    await waitFor(() => expect(crmApi.saveParrainage).toHaveBeenCalled())
    expect(crmApi.saveParrainage).toHaveBeenCalledWith(
      null, expect.objectContaining({ parrain: '1', filleul_lead: '7' }))
  })
})
