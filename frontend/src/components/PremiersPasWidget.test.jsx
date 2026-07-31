import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* WIR59 — widget « Premiers pas », unique tracker d'onboarding du Dashboard.
   Un item sans `event_key` (aucun déclencheur automatique) gagne un bouton
   « Marquer comme fait » manuel ; un item AVEC `event_key` n'en a pas. */

vi.mock('../api/axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

import api from '../api/axios'
import PremiersPasWidget from './PremiersPasWidget'

const RESUME = {
  faits: 2, total: 6, pourcentage: 33, termine: false,
  items: [
    { id: 1, key: 'configurer_societe', libelle: 'Configurer votre société',
      lien: '/parametres', fait: false, event_key: '' },
    { id: 2, key: 'premier_devis', libelle: 'Créer votre 1er devis',
      lien: '/ventes/devis/nouveau', fait: false, event_key: 'devis' },
    { id: 3, key: 'premier_chantier', libelle: 'Suivre votre 1er chantier',
      lien: '/chantiers', fait: true, event_key: 'chantier' },
  ],
}

function renderWidget() {
  return render(<MemoryRouter><PremiersPasWidget /></MemoryRouter>)
}

describe('PremiersPasWidget (NTDMO13/WIR59)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('affiche la checklist avec progression', async () => {
    api.get.mockResolvedValueOnce({ data: RESUME })
    renderWidget()
    expect(await screen.findByText('Premiers pas — 2/6')).toBeInTheDocument()
    expect(screen.getByText('Configurer votre société')).toBeInTheDocument()
  })

  it('un item sans event_key propose « Marquer comme fait » ; un item avec event_key non', async () => {
    api.get.mockResolvedValueOnce({ data: RESUME })
    renderWidget()
    await screen.findByText('Configurer votre société')
    // configurer_societe (event_key='') → bouton présent.
    expect(screen.getByRole('button', { name: 'Marquer comme fait' })).toBeInTheDocument()
    // Un seul bouton (premier_devis a event_key='devis' malgré fait=false ;
    // premier_chantier est déjà fait=true) : les deux sont exclus.
    expect(screen.getAllByRole('button', { name: 'Marquer comme fait' })).toHaveLength(1)
  })

  it('cliquer « Marquer comme fait » appelle marquer-fait et rafraîchit', async () => {
    api.get.mockResolvedValueOnce({ data: RESUME })
    api.post.mockResolvedValueOnce({
      data: { ...RESUME, faits: 3, items: RESUME.items.map((it) => (
        it.key === 'configurer_societe' ? { ...it, fait: true } : it)) },
    })
    renderWidget()
    await screen.findByText('Configurer votre société')
    await userEvent.click(screen.getByRole('button', { name: 'Marquer comme fait' }))
    await waitFor(() => expect(api.post)
      .toHaveBeenCalledWith('/onboarding/progress/1/marquer-fait/'))
    expect(await screen.findByText('Premiers pas — 3/6')).toBeInTheDocument()
  })

  it('ne rend rien si tout est terminé', async () => {
    api.get.mockResolvedValueOnce({ data: { ...RESUME, termine: true } })
    const { container } = renderWidget()
    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(container.querySelector('[data-testid="premiers-pas-widget"]')).toBeNull()
  })
})
