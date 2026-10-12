// XSAL3 — au choix d'un produit (et à chaque changement de quantité/client),
// le générateur interroge `getPrixApplicable` (résolution liste client +
// paliers XSAL1-2) et affiche un badge « Tarif : <liste> » quand une liste de
// prix négociée s'applique (source !== 'standard'). Prix pré-rempli depuis la
// résolution, jamais un blocage/snap de la saisie manuelle ultérieure.

import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'


vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiDuplication())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock({
  getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
  getPrixApplicable: vi.fn(),
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { bancCreation } from './devisGenerator.testHelpers.jsx'

const PRODUITS = [
  { id: 10, nom: 'Smart Meter Huawei DTSU666', prix_vente: 1500, tva: 20, is_archived: false, prix_achat: 900 },
]

const { renderGenerator } = bancCreation({ DevisGenerator, crmApi, stockApi, produits: PRODUITS })


describe('XSAL3 — badge tarif applicable', () => {
  it('affiche « Tarif : <liste> » quand la résolution renvoie une liste', async () => {
    ventesApi.getPrixApplicable.mockResolvedValue({
      data: { produit: 10, quantite: '1', prix: '1350.00', source: 'liste', liste_nom: 'Revendeur' },
    })
    renderGenerator()
    await screen.findByDisplayValue('Smart Meter Huawei DTSU666')
    await waitFor(() => expect(ventesApi.getPrixApplicable).toHaveBeenCalled())
    expect(await screen.findByText(/Tarif : Revendeur/)).toBeInTheDocument()
  })

  it("n'affiche aucun badge quand la source est « standard »", async () => {
    ventesApi.getPrixApplicable.mockResolvedValue({
      data: { produit: 10, quantite: '1', prix: '1500.00', source: 'standard', liste_nom: null },
    })
    renderGenerator()
    await screen.findByDisplayValue('Smart Meter Huawei DTSU666')
    await waitFor(() => expect(ventesApi.getPrixApplicable).toHaveBeenCalled())
    expect(screen.queryByText(/Tarif :/)).not.toBeInTheDocument()
  })
})
