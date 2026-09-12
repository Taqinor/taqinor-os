// VT10 — la revue bureau d'études filtre sur `statut` (champ déjà renvoyé par
// la liste, jamais une invention de paramètre), et le renvoi exige un motif
// (garde UI, en plus de la garde serveur).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const { getVisites, getVisite } = vi.hoisted(() => ({
  getVisites: vi.fn(),
  getVisite: vi.fn(),
}))

vi.mock('../../api/visitesApi', () => ({
  default: {
    getVisites: (...a) => getVisites(...a),
    getVisite: (...a) => getVisite(...a),
    validerVisite: vi.fn(),
    renvoyerVisite: vi.fn(),
  },
}))

import VisiteBureauEtudesPage from './VisiteBureauEtudesPage'

beforeEach(() => {
  vi.clearAllMocks()
  getVisites.mockResolvedValue({
    data: [
      { id: 1, lead: 10, lead_nom: 'Lead A', ville: 'Casablanca', statut: 'terminee', date_prevue: null, complet: true, manquants_count: 0 },
      { id: 2, lead: 11, lead_nom: 'Lead B', ville: 'Rabat', statut: 'validee', date_prevue: null, complet: true, manquants_count: 0 },
      { id: 3, lead: 12, lead_nom: 'Lead C', ville: 'Fès', statut: 'en_cours', date_prevue: null, complet: false, manquants_count: 3 },
    ],
  })
  getVisite.mockResolvedValue({
    data: {
      id: 1, lead: 10, statut: 'terminee',
      checklist: [{ categorie: 'toiture', libelle: 'Toiture', slots: [{ code: 's1', libelle: 'Vue', requis: true, etat: 'ok', photos: [] }] }],
      mesures: { toiture: { longueur_m: 12, largeur_m: 8, pente_deg: 15, orientation: 'sud' } },
      client_panel: { lead_nom: 'Lead A' },
    },
  })
})

describe('VisiteBureauEtudesPage — VT10', () => {
  it('ne liste que les visites `terminee` (champ statut déjà fourni par la liste)', async () => {
    render(<MemoryRouter><VisiteBureauEtudesPage /></MemoryRouter>)
    expect(await screen.findByText('Lead A')).toBeInTheDocument()
    expect(screen.queryByText('Lead B')).not.toBeInTheDocument()
    expect(screen.queryByText('Lead C')).not.toBeInTheDocument()
  })

  it('le bouton Renvoyer reste désactivé tant qu’aucun motif n’est saisi', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><VisiteBureauEtudesPage /></MemoryRouter>)
    await user.click(await screen.findByText('Lead A'))
    await user.click(await screen.findByRole('button', { name: /renvoyer/i }))
    const boutonEnvoyer = await screen.findByRole('button', { name: /^renvoyer$/i })
    expect(boutonEnvoyer).toBeDisabled()
  })
})
