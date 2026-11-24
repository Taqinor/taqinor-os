// Onglet « Contrats » : les charges utiles viennent TOUTES des exemples du
// contrat (apps/documents/contract_samples/*.json) via contractSamples.js —
// jamais un mock écrit à la main (garde CI check_api_shapes.py).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

const { documentsApiMock } = vi.hoisted(() => ({
  documentsApiMock: {
    dossierContrats: vi.fn(),
    acte: vi.fn(),
    modifierActe: vi.fn(),
    pdfActe: vi.fn(),
    emettreActe: vi.fn(),
    rouvrirActe: vi.fn(),
    signerActe: vi.fn(),
    marquerActeSigne: vi.fn(),
    enregistrerModeleActe: vi.fn(),
  },
}))
vi.mock('../../../api/documentsApi', () => ({ default: documentsApiMock }))
vi.mock('../../../features/installations/SignaturePad', () => ({
  default: () => <div>Zone de signature</div>,
}))

import ContratsChantier from './ContratsChantier'

const dossier = (variante = 'exemple') => structuredClone(exempleContrat('documents', 'dossier_contractuel', variante))
const refus = (variante) => ({
  response: { data: exempleContrat('documents', 'acte_contractuel', variante) },
})

function monter(props = {}) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'responsable', role_nom: 'Commercial responsable', permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <ContratsChantier installation={{ id: 12 }} {...props} />
    </Provider>,
  )
}

const carte = (titre) => screen.getByRole('heading', { name: titre }).closest('.contrats-acte')

beforeEach(() => {
  vi.clearAllMocks()
  documentsApiMock.dossierContrats.mockResolvedValue({ data: dossier() })
})
afterEach(() => cleanup())

describe('Onglet Contrats', () => {
  it('rend les cinq lignes du dossier dans l’ordre, chacune avec son statut en mots', async () => {
    monter()
    await screen.findByText('Contrat d\'installation')
    const titres = screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent)
    expect(titres).toEqual(dossier().actes.map((a) => a.titre))
    expect(titres).toHaveLength(5)
    expect(within(carte('Contrat d\'installation')).getByText('Signé le 24/11/2026 par Youssef EL EXEMPLE')).toBeInTheDocument()
    expect(within(carte('Réception des travaux')).getByText('Brouillon')).toBeInTheDocument()
    expect(documentsApiMock.dossierContrats).toHaveBeenCalledWith(12)
  })

  it('affiche prix, réglé, reste et la prochaine action du serveur', async () => {
    monter()
    await screen.findByText(/Prochaine action/)
    expect(screen.getByText('98 500,00 DH')).toBeInTheDocument()
    expect(screen.getByText('29 550,00 DH')).toBeInTheDocument()
    expect(screen.getByText('68 950,00 DH')).toBeInTheDocument()
    expect(screen.getByText('Faire signer la livraison du matériel')).toBeInTheDocument()
  })

  it('montre côte à côte les deux versions de la livraison (étape 2)', async () => {
    monter()
    await screen.findByText('Livraison du matériel — reste à régler')
    const a = carte('Livraison du matériel — reste à régler')
    const b = carte('Livraison du matériel — 90 % réglés')
    expect(a.parentElement).toBe(b.parentElement)
    expect(a.parentElement).toHaveClass('contrats-parcours__variantes')
  })

  it('met visiblement de côté la version jumelle d’une livraison émise', async () => {
    const d = dossier()
    d.actes[1] = { ...d.actes[1], statut: 'emis', emis_le: '2026-12-15T09:00:00Z', peut_emettre: false, peut_signer: true }
    d.actes[2] = { ...d.actes[2], ecarte: true }
    documentsApiMock.dossierContrats.mockResolvedValue({ data: d })
    monter()
    await screen.findByText('Livraison du matériel — 90 % réglés')
    expect(within(carte('Livraison du matériel — 90 % réglés')).getByText(/Écartée/)).toBeInTheDocument()
    expect(within(carte('Livraison du matériel — reste à régler')).getByText('Émis le 15/12/2026')).toBeInTheDocument()
  })

  it('affiche le detail d’un refus 409 solde_non_regle, sur l’acte', async () => {
    const d = dossier()
    d.actes[4] = { ...d.actes[4], peut_emettre: true }
    documentsApiMock.dossierContrats.mockResolvedValue({ data: d })
    documentsApiMock.emettreActe.mockRejectedValue(refus('exemple_409_solde_non_regle'))
    const user = userEvent.setup()
    monter()
    await screen.findByText('Quitus et certificat de garantie')
    await user.click(within(carte('Quitus et certificat de garantie')).getByRole('button', { name: 'Émettre' }))
    expect(await screen.findByText(/fige le texte et le PDF/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Émettre l’acte' }))
    const detail = exempleContrat('documents', 'acte_contractuel', 'exemple_409_solde_non_regle').detail
    const alerte = await within(carte('Quitus et certificat de garantie')).findByRole('alert')
    expect(alerte).toHaveTextContent(detail)
    expect(documentsApiMock.emettreActe).toHaveBeenCalledWith(35)
  })

  it('le sélecteur de langue demande le PDF arabe (langue ar), français par défaut', async () => {
    documentsApiMock.pdfActe.mockResolvedValue({ data: new Blob(['x']) })
    const ouvrirApercu = vi.fn()
    const user = userEvent.setup()
    monter({ ouvrirApercu })
    await screen.findByText('Contrat d\'installation')
    expect(screen.getByRole('button', { name: 'Français' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(within(carte('Réception des travaux')).getByRole('button', { name: 'Aperçu (PDF)' }))
    await ouvrirApercu.mock.calls[0][2]()
    expect(documentsApiMock.pdfActe).toHaveBeenLastCalledWith(34, 'fr')
    await user.click(screen.getByRole('button', { name: 'العربية' }))
    await user.click(within(carte('Réception des travaux')).getByRole('button', { name: 'Aperçu (PDF)' }))
    await ouvrirApercu.mock.calls[1][2]()
    expect(documentsApiMock.pdfActe).toHaveBeenLastCalledWith(34, 'ar')
  })

  const sansDroits = (d) => {
    d.actes = d.actes.map((a) => ({
      ...a, peut_modifier: false, peut_emettre: false, peut_signer: false, peut_rouvrir: false,
    }))
    return d
  }
  const GESTES_ECRITURE = ['Modifier', 'Émettre', 'Faire signer sur place', 'Signé sur papier', 'Rouvrir']

  it('F8 — un rôle en lecture seule (peut_* à false côté serveur) ne voit aucun bouton d’écriture', async () => {
    documentsApiMock.dossierContrats.mockResolvedValue({ data: sansDroits(dossier()) })
    monter()
    await screen.findByText("Contrat d'installation")
    for (const nom of GESTES_ECRITURE) expect(screen.queryByRole('button', { name: nom })).toBeNull()
    expect(screen.getAllByRole('button', { name: 'Aperçu (PDF)' })).toHaveLength(5)
  })

  it('F8 — les gestes suivent les peut_* du serveur, jamais un drapeau local', async () => {
    monter()
    await screen.findByText("Contrat d'installation")
    expect(within(carte('Réception des travaux')).getByRole('button', { name: 'Modifier' })).toBeInTheDocument()
    expect(within(carte('Réception des travaux')).getByRole('button', { name: 'Émettre' })).toBeInTheDocument()
  })

  it('chantier annulé : bandeau, et les gestes que le serveur retire (peut_* à false) disparaissent', async () => {
    const d = sansDroits(dossier())
    d.chantier.annule = true
    d.prochaine_action = null
    documentsApiMock.dossierContrats.mockResolvedValue({ data: d })
    monter()
    expect(await screen.findByText(/Ce chantier est annulé/)).toBeInTheDocument()
    for (const nom of GESTES_ECRITURE) expect(screen.queryByRole('button', { name: nom })).toBeNull()
  })

  it('chantier sans devis : prix à préciser et avertissement serveur', async () => {
    documentsApiMock.dossierContrats.mockResolvedValue({ data: dossier('exemple_sans_devis') })
    monter()
    expect(await screen.findAllByText(/pas de devis accepté/)).not.toHaveLength(0)
    expect(screen.getAllByText('à préciser')).toHaveLength(3)
  })

  it('erreur de chargement : detail du serveur et bouton Réessayer', async () => {
    documentsApiMock.dossierContrats.mockRejectedValueOnce({
      response: { data: { detail: 'Accès refusé à ce chantier.', code: 'interdit' } },
    })
    const user = userEvent.setup()
    monter()
    expect(await screen.findByText('Accès refusé à ce chantier.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(screen.getByText('Contrat d\'installation')).toBeInTheDocument())
    expect(documentsApiMock.dossierContrats).toHaveBeenCalledTimes(2)
  })

  it('F7 — chaque bouton d’une carte est relié au titre de son acte (aria-describedby)', async () => {
    monter()
    await screen.findByText("Contrat d'installation")
    for (const titre of ['Réception des travaux', "Contrat d'installation"]) {
      const entete = screen.getByRole('heading', { name: titre })
      const boutons = within(carte(titre)).getAllByRole('button')
      expect(boutons.length).toBeGreaterThan(0)
      for (const b of boutons) expect(b).toHaveAccessibleDescription(titre)
      expect(entete.id).toBeTruthy()
    }
  })

  it('F11 — la confirmation d’émission montre les avertissements de l’acte', async () => {
    const d = dossier()
    d.actes[3] = { ...d.actes[3], peut_emettre: true, avertissements: ['La traduction arabe ne suit pas vos changements.'] }
    documentsApiMock.dossierContrats.mockResolvedValue({ data: d })
    const user = userEvent.setup()
    monter()
    await screen.findByText('Réception des travaux')
    await user.click(within(carte('Réception des travaux')).getByRole('button', { name: 'Émettre' }))
    const boite = await screen.findByRole('alertdialog')
    expect(within(boite).getByText('La traduction arabe ne suit pas vos changements.')).toBeInTheDocument()
    expect(within(boite).getByRole('button', { name: 'Émettre l’acte' })).toBeInTheDocument()
  })

  it('F14 — la version écartée n’offre que l’aperçu et aucun avertissement périmé', async () => {
    const d = dossier()
    d.actes[1] = { ...d.actes[1], statut: 'emis', emis_le: '2026-12-15T09:00:00Z', peut_emettre: false, peut_signer: true }
    d.actes[2] = { ...d.actes[2], ecarte: true, peut_modifier: true, peut_emettre: true, avertissements: ['Avertissement périmé.'] }
    documentsApiMock.dossierContrats.mockResolvedValue({ data: d })
    monter()
    await screen.findByText('Livraison du matériel — 90 % réglés')
    const ecartee = carte('Livraison du matériel — 90 % réglés')
    expect(within(ecartee).getAllByRole('button').map((b) => b.textContent)).toEqual(['Aperçu (PDF)'])
    expect(within(ecartee).queryByText('Avertissement périmé.')).toBeNull()
  })

  it('F14 — « Rouvrir » demande confirmation avant d’appeler le serveur', async () => {
    const d = dossier()
    d.actes[1] = { ...d.actes[1], statut: 'emis', emis_le: '2026-12-15T09:00:00Z', peut_rouvrir: true }
    documentsApiMock.dossierContrats.mockResolvedValue({ data: d })
    documentsApiMock.rouvrirActe.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    monter()
    await screen.findByText('Livraison du matériel — reste à régler')
    await user.click(within(carte('Livraison du matériel — reste à régler')).getByRole('button', { name: 'Rouvrir' }))
    expect(documentsApiMock.rouvrirActe).not.toHaveBeenCalled()
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Rouvrir l’acte' }))
    expect(documentsApiMock.rouvrirActe).toHaveBeenCalledWith(d.actes[1].id)
  })

  it('F16 — l’aperçu s’intitule avec la référence de l’ACTE', async () => {
    const ouvrirApercu = vi.fn()
    const user = userEvent.setup()
    monter({ ouvrirApercu })
    await screen.findByText('Réception des travaux')
    const acte = dossier().actes.find((a) => a.titre === 'Réception des travaux')
    await user.click(within(carte('Réception des travaux')).getByRole('button', { name: 'Aperçu (PDF)' }))
    expect(ouvrirApercu.mock.calls[0][0]).toBe(`${acte.titre} — ${acte.reference}`)
  })
})
