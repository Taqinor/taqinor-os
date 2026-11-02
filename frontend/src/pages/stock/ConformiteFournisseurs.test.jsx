import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { makeAuthStore, renderStockPage } from './stockPage.testHelpers.jsx'

/* ============================================================================
   ENF15 (D-ENF15-STOCK-22) — écran « Conformité fournisseurs » (pièces qui
   expirent NTP2P20, conformité + export Excel NTP2P19, délai réel NTSCM11) et
   relevé des déductions de TVA (XPUR17). Composants réels, API simulée.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getDocumentsFournisseurExpirants: vi.fn(),
    getConformiteFournisseurs: vi.fn(),
    exportConformiteFournisseursXlsx: vi.fn(),
    getAllFournisseurs: vi.fn(),
    getDelaiMesureFournisseur: vi.fn(),
    getReleveDeductionsTva: vi.fn(),
  },
}))
vi.mock('../../utils/downloadBlob', () => ({
  downloadBlob: vi.fn(), stampedFilename: (base, ext) => `${base}.${ext}`,
}))

import stockApi from '../../api/stockApi'
import { downloadBlob } from '../../utils/downloadBlob'
import ConformiteFournisseurs from './ConformiteFournisseurs'
import ReleveDeductionsTva from './ReleveDeductionsTva'

const PERMS = ['stock_voir', 'prix_achat_voir']
const DOCS = [
  { document_id: 1, fournisseur_id: 3, fournisseur_nom: 'Sunrak', type_document: 'ice',
    type_document_display: 'Attestation ICE', date_expiration: '2026-11-10', jours_restants: 8 },
  { document_id: 2, fournisseur_id: 4, fournisseur_nom: 'JA Solar', type_document: 'rc',
    type_document_display: 'Registre de commerce', date_expiration: '2026-10-20', jours_restants: -13 },
]
const CONFORMITE = [
  { fournisseur_id: 3, fournisseur: 'Sunrak', statut_onboarding: 'Validé', score_risque: 82,
    niveau_risque: 'faible', documents_expires: '', documents_manquants: 'RIB',
    dernier_retard_le: '2026-09-01', dernier_retard_jours: 4, montant_achete: '12500.00' },
]

beforeEach(() => {
  vi.clearAllMocks()
  stockApi.getDocumentsFournisseurExpirants.mockResolvedValue({ data: DOCS })
  stockApi.getConformiteFournisseurs.mockResolvedValue({ data: CONFORMITE })
  stockApi.getAllFournisseurs.mockResolvedValue({ data: [{ id: 3, nom: 'Sunrak' }] })
})

describe('ConformiteFournisseurs (ENF15)', () => {
  it('liste les pièces qui expirent (horizon 30 j par défaut) et la conformité', async () => {
    renderStockPage(ConformiteFournisseurs, makeAuthStore({ role: 'responsable', permissions: PERMS }))
    const pieces = await screen.findByRole('grid', { name: 'Pièces fournisseur qui expirent' })
    expect(within(pieces).getByText('Attestation ICE')).toBeInTheDocument()
    expect(within(pieces).getByText(/Expirée \(13 j\)/)).toBeInTheDocument()
    expect(stockApi.getDocumentsFournisseurExpirants).toHaveBeenCalledWith(30)
    const conf = await screen.findByRole('grid', { name: 'Conformité des fournisseurs' })
    expect(within(conf).getByText('Sunrak')).toBeInTheDocument()
    expect(within(conf).getByText(/12\s?500,00\s?MAD/)).toBeInTheDocument()
  })

  it("n'affiche aucun montant d'achat sans le droit prix d'achat", async () => {
    // Compte à rôle fin sans `prix_achat_voir` : le serveur retire la clé, l'écran masque la colonne.
    const { montant_achete: _m, ...sansMontant } = CONFORMITE[0]
    stockApi.getConformiteFournisseurs.mockResolvedValue({ data: [sansMontant] })
    renderStockPage(ConformiteFournisseurs, makeAuthStore({ role: 'responsable', permissions: ['stock_voir'] }))
    const conf = await screen.findByRole('grid', { name: 'Conformité des fournisseurs' })
    expect(within(conf).getByText('Sunrak')).toBeInTheDocument()
    expect(within(conf).queryByText(/Acheté/)).toBeNull()
    expect(within(conf).queryByText(/MAD/)).toBeNull()
  })

  it("exporte l'Excel avec la période choisie", async () => {
    stockApi.exportConformiteFournisseursXlsx.mockResolvedValue({ data: new Blob(['x']) })
    renderStockPage(ConformiteFournisseurs, makeAuthStore({ role: 'responsable', permissions: PERMS }))
    await screen.findByRole('grid', { name: 'Conformité des fournisseurs' })
    await userEvent.type(screen.getByLabelText('Du'), '2026-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Exporter en Excel/ }))
    await waitFor(() => expect(stockApi.exportConformiteFournisseursXlsx).toHaveBeenCalledWith({ debut: '2026-01-01' }))
    expect(downloadBlob).toHaveBeenCalled()
  })

  it('mesure le délai réel contre le délai annoncé', async () => {
    stockApi.getDelaiMesureFournisseur.mockResolvedValue({
      data: { fournisseur_id: 3, fenetre_mois: 12, nb_mesures: 4, delai_annonce_jours: 10,
        delai_mesure_jours: 15, ecart_jours: 5, ecart_pct: '50.00', seuil_ecart_pct: '20.00',
        utiliser_delai_reel: true, delai_retenu_jours: 15 },
    })
    renderStockPage(ConformiteFournisseurs, makeAuthStore({ role: 'responsable', permissions: PERMS }))
    await screen.findByRole('grid', { name: 'Conformité des fournisseurs' })
    await userEvent.click(screen.getByRole('combobox', { name: 'Fournisseur' }))
    await userEvent.click(await screen.findByRole('option', { name: 'Sunrak' }))
    await userEvent.click(screen.getByRole('button', { name: 'Mesurer' }))
    expect(await screen.findByText(/le délai réel est retenu/)).toBeInTheDocument()
    expect(stockApi.getDelaiMesureFournisseur).toHaveBeenCalledWith('3', { fenetre_mois: 12 })
  })

  it('cache la section délai à un compte non responsable', async () => {
    renderStockPage(ConformiteFournisseurs, makeAuthStore({ role: 'normal' }))
    await screen.findByRole('grid', { name: 'Conformité des fournisseurs' })
    expect(screen.queryByRole('button', { name: 'Mesurer' })).toBeNull()
  })
})

describe('ReleveDeductionsTva (ENF15)', () => {
  it('affiche le relevé par taux et le total de TVA déductible', async () => {
    stockApi.getReleveDeductionsTva.mockResolvedValue({
      data: [
        { taux_tva: '20.00', total_ht: '1000.00', total_tva: '200.00', nombre_factures: 2 },
        { taux_tva: '10.00', total_ht: '500.00', total_tva: '50.00', nombre_factures: 1 },
      ],
    })
    renderStockPage(ReleveDeductionsTva, makeAuthStore({ role: 'responsable', permissions: PERMS }))
    await userEvent.type(screen.getByLabelText('Du'), '2026-10-01')
    await userEvent.click(screen.getByRole('button', { name: 'Afficher le relevé' }))
    const table = await screen.findByRole('table', { name: 'Déductions de TVA par taux' })
    expect(within(table).getByText('20 %')).toBeInTheDocument()
    expect(within(table).getByText(/250,00\s?MAD/)).toBeInTheDocument()
    expect(stockApi.getReleveDeductionsTva).toHaveBeenCalledWith({ date_debut: '2026-10-01' })
  })

  it('ne rend rien pour un compte non responsable', () => {
    renderStockPage(ReleveDeductionsTva, makeAuthStore({ role: 'normal' }))
    expect(screen.queryByRole('button', { name: 'Afficher le relevé' })).toBeNull()
  })
})
