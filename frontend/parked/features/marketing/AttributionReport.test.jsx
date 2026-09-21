import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const mocks = vi.hoisted(() => ({ comparaison: vi.fn() }))

vi.mock('../../api/marketingApi', () => ({
  default: { attribution: { comparaison: mocks.comparaison } },
}))

import AttributionReport from './AttributionReport'

const REPONSE = {
  devis_id: 42, lead_id: 7, total_revenu: '1200.00', nb_points_contact: 2,
  modele_actuel: 'dernier_touche',
  modeles: {
    dernier_touche: [
      { point_contact_id: 1, canal: 'meta_ads', canal_libelle: 'Meta Ads', date_contact: '2026-08-01', revenu_attribue: '0.00' },
      { point_contact_id: 2, canal: 'site_web', canal_libelle: 'Site web', date_contact: '2026-08-10', revenu_attribue: '1200.00' },
    ],
    premier_touche: [
      { point_contact_id: 1, canal: 'meta_ads', canal_libelle: 'Meta Ads', date_contact: '2026-08-01', revenu_attribue: '1200.00' },
      { point_contact_id: 2, canal: 'site_web', canal_libelle: 'Site web', date_contact: '2026-08-10', revenu_attribue: '0.00' },
    ],
    lineaire: [
      { point_contact_id: 1, canal: 'meta_ads', canal_libelle: 'Meta Ads', date_contact: '2026-08-01', revenu_attribue: '600.00' },
      { point_contact_id: 2, canal: 'site_web', canal_libelle: 'Site web', date_contact: '2026-08-10', revenu_attribue: '600.00' },
    ],
    pondere_temporel: [
      { point_contact_id: 1, canal: 'meta_ads', canal_libelle: 'Meta Ads', date_contact: '2026-08-01', revenu_attribue: '300.00' },
      { point_contact_id: 2, canal: 'site_web', canal_libelle: 'Site web', date_contact: '2026-08-10', revenu_attribue: '900.00' },
    ],
  },
}

describe('AttributionReport (NTMKT21)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('charge et affiche le classement du modèle société par défaut', async () => {
    mocks.comparaison.mockResolvedValue({ data: REPONSE })
    render(<AttributionReport devisId={42} />)
    await waitFor(() => expect(screen.getByTestId('attribution-classement')).toBeInTheDocument())
    const lignes = screen.getAllByRole('row').slice(1)
    expect(lignes[0]).toHaveTextContent('Site web')
    expect(lignes[0]).toHaveTextContent('1200.00')
  })

  it('changer de modèle recalcule le classement SANS nouvel appel réseau', async () => {
    mocks.comparaison.mockResolvedValue({ data: REPONSE })
    const user = userEvent.setup()
    render(<AttributionReport devisId={42} />)
    await waitFor(() => expect(screen.getByTestId('attribution-classement')).toBeInTheDocument())
    expect(mocks.comparaison).toHaveBeenCalledTimes(1)

    await user.click(screen.getByLabelText('Premier touché'))

    const lignes = screen.getAllByRole('row').slice(1)
    expect(lignes[0]).toHaveTextContent('Meta Ads')
    expect(lignes[0]).toHaveTextContent('1200.00')
    expect(mocks.comparaison).toHaveBeenCalledTimes(1)
  })

  it('affiche un message propre si le devis est introuvable/non accepté', async () => {
    mocks.comparaison.mockRejectedValue({ response: { status: 404 } })
    render(<AttributionReport devisId={99} />)
    await waitFor(() => expect(screen.getByTestId('attribution-erreur')).toBeInTheDocument())
  })
})
