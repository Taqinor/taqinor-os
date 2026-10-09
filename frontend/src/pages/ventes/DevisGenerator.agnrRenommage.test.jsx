// AGNR32 — « Créer un nouveau produit dans le stock » (`renameAsNewProduct`)
// relie la ligne au clone SANS toucher au prix tapé ni à la TVA de la ligne :
// seuls `produit` et `designation` changent ; le prix négocié reste verrouillé.
// Harnais : celui de DevisGeneratorRename.test.jsx (écran réel).
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrRenommage.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor, within } from '@testing-library/react'

import { installerShimsJsdom } from '../../test/shimsEcran'
import { renderGenerateurRole } from '../../test/generateurEmbarque'

// APIs mockées (aucun appel réseau réel au montage) : fabriques partagées.
vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock({
  dupliquerProduit: vi.fn(),
}))
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'

// Un catalogue minimal : le Smart Meter devient une ligne à produit lié dans la
// table par défaut (defaultProductLines), donc renommable.
const PRODUITS = [
  { id: 10, nom: 'Smart Meter Huawei DTSU666', prix_vente: 1500, tva: 20, is_archived: false, prix_achat: 900 },
]

function renderGenerator(authState) {
  crmApi.getClients.mockResolvedValue({ data: [] })
  crmApi.getLeads.mockResolvedValue({ data: [] })
  stockApi.getProduits.mockResolvedValue({ data: PRODUITS })
  return renderGenerateurRole(authState)
}

// jsdom : shims requis par le générateur (scrollIntoView, matchMedia,
// ResizeObserver via recharts).
beforeEach(() => {
  vi.clearAllMocks()
  installerShimsJsdom()
})

// Trouve l'input de désignation du Smart Meter (ligne à produit lié).
async function findSmartMeterDesignation() {
  const input = await screen.findByDisplayValue('Smart Meter Huawei DTSU666')
  return input
}

describe('AGNR32 — le clone garde le prix tapé et la TVA de la ligne', () => {
  it('P.U. TTC tapé 9 999 et TVA 10 % survivent au clone (prix catalogue du clone ignoré)', async () => {
    stockApi.dupliquerProduit.mockResolvedValue({
      data: { id: 99, nom: 'Smart Meter perso', prix_vente: 9000, tva: 20, prix_achat: 900, is_archived: false },
    })
    renderGenerator({ role_nom: 'Directeur', permissions: ['stock_creer'] })
    const input = await findSmartMeterDesignation()
    const ligne = input.closest('tr')
    const [prix, tva] = [...ligne.querySelectorAll('input[type="number"]')].filter((el) => el.dataset.role !== 'line-qty')
    fireEvent.change(prix, { target: { value: '9999' } })
    fireEvent.change(tva, { target: { value: '10' } })
    fireEvent.change(input, { target: { value: 'Smart Meter perso' } })
    fireEvent.blur(input)
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /Créer un nouveau produit/ }))
    await waitFor(() => expect(stockApi.dupliquerProduit).toHaveBeenCalledWith('10', 'Smart Meter perso'))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    const apres = (await screen.findByDisplayValue('Smart Meter perso')).closest('tr')
    const [prixApres, tvaApres] = [...apres.querySelectorAll('input[type="number"]')].filter((el) => el.dataset.role !== 'line-qty')
    expect(prixApres.value).toBe('9999')
    expect(tvaApres.value).toBe('10')
    // Le prix négocié est verrouillé (indicateur « prix tapé »).
    expect(apres.textContent).not.toMatch(/10 800/)
  })
})
