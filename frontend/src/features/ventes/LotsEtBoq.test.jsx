// QJR667 — écrans « Lots / multi-sites » (NTCPQ18) et « Ajouter le BOQ
// électrique » (PV47) de l'Édition complète. Les réponses serveur viennent
// des exemples COMMITTÉS des contrats (PACT10) : `devis_lots.json` et
// `devis_boq_electrique.json` — aucune charge utile inventée.
//
// Run : npx vitest run src/features/ventes/LotsEtBoq.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { documentContrat, reponseContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/ventesApi', () => ({
  default: {
    getLotsDevis: vi.fn(),
    creerLotDevis: vi.fn(),
    getDevisById: vi.fn(),
    ajouterBoqElectrique: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import LotsMultiSites from './LotsMultiSites'
import AjouterBoqElectrique from './AjouterBoqElectrique'
import { bilanBoq, corpsCreationLot, messageErreurLots } from './lotsBoq'

const LIGNES = [
  { id: 412, designation: 'Panneau Canadien Solar 710W', type_ligne: 'produit', lot: null },
  { id: 413, designation: 'Onduleur Huawei 50 kW', type_ligne: 'produit', lot: 31 },
  { id: 414, designation: 'Toiture bâtiment A', type_ligne: 'section', lot: null },
]

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.getLotsDevis.mockResolvedValue(reponseContrat('ventes', 'devis_lots'))
  ventesApi.getDevisById.mockResolvedValue({ data: { id: 7, lignes: LIGNES } })
})

describe('LotsMultiSites', () => {
  it('replié au montage : aucun appel serveur', () => {
    render(<LotsMultiSites devisId={7} modifiable />)
    expect(ventesApi.getLotsDevis).not.toHaveBeenCalled()
  })

  it('ouvert : sous-totaux par lot, hors lot et total consolidé du contrat', async () => {
    render(<LotsMultiSites devisId={7} modifiable />)
    await userEvent.click(screen.getByRole('button', { name: 'Afficher' }))
    const exemple = documentContrat('ventes', 'devis_lots').exemple
    const lot = exemple.lots[0]
    expect(await screen.findByTestId(`lot-${lot.id}`)).toHaveTextContent(lot.nom_lot)
    expect(screen.getByTestId('lot-hors-lot')).toBeInTheDocument()
    expect(screen.getByTestId('lot-total-consolide')).toHaveTextContent('Total consolidé')
    // Seules les lignes PRODUIT sont proposées au rattachement.
    expect(screen.getByLabelText('Panneau Canadien Solar 710W')).toBeInTheDocument()
    expect(screen.queryByLabelText('Toiture bâtiment A')).toBeNull()
  })

  it('devis sans lot : le message mono-site', async () => {
    ventesApi.getLotsDevis.mockResolvedValue(
      reponseContrat('ventes', 'devis_lots', 'exemple_sans_lot'))
    render(<LotsMultiSites devisId={7} modifiable />)
    await userEvent.click(screen.getByRole('button', { name: 'Afficher' }))
    expect(await screen.findByText(/mono-site/)).toBeInTheDocument()
  })

  it('créer un lot : POST du corps du contrat, puis relecture du devis', async () => {
    ventesApi.creerLotDevis.mockResolvedValue(reponseContrat('ventes', 'devis_lots'))
    const onChange = vi.fn()
    render(<LotsMultiSites devisId={7} modifiable onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Afficher' }))
    await screen.findByLabelText('Panneau Canadien Solar 710W')
    await userEvent.type(screen.getByLabelText('Nom du lot'), 'Bâtiment B')
    await userEvent.type(screen.getByLabelText('Ordre'), '1')
    await userEvent.click(screen.getByLabelText('Panneau Canadien Solar 710W'))
    await userEvent.click(screen.getByRole('button', { name: 'Créer le lot' }))
    await waitFor(() => expect(ventesApi.creerLotDevis).toHaveBeenCalledWith(
      7, { nom_lot: 'Bâtiment B', ordre: 1, lignes: [412] }))
    expect(onChange).toHaveBeenCalled()
    // Les clés envoyées sont celles du contrat (jamais une clé inventée).
    const corpsContrat = documentContrat('ventes', 'devis_lots').requete_post.corps
    const envoye = ventesApi.creerLotDevis.mock.calls[0][1]
    Object.keys(envoye).forEach(k => expect(corpsContrat).toHaveProperty(k))
  })

  it('refus serveur : le message est affiché, rien n’est relu', async () => {
    ventesApi.creerLotDevis.mockRejectedValue(
      { response: { data: { nom_lot: ['Ce lot existe déjà sur ce devis.'] } } })
    const onChange = vi.fn()
    render(<LotsMultiSites devisId={7} modifiable onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Afficher' }))
    await screen.findByLabelText('Nom du lot')
    await userEvent.type(screen.getByLabelText('Nom du lot'), 'A')
    await userEvent.click(screen.getByRole('button', { name: 'Créer le lot' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ce lot existe déjà')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('devis non modifiable : lecture seule, aucun formulaire', async () => {
    render(<LotsMultiSites devisId={7} modifiable={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'Afficher' }))
    await screen.findByTestId('lot-total-consolide')
    expect(screen.queryByTestId('lot-formulaire')).toBeNull()
  })

  it('corpsCreationLot : champs vides omis, ordre en nombre', () => {
    expect(corpsCreationLot({ nom_lot: ' A ', adresse_site: '', ordre: '', lignes: [] }))
      .toEqual({ nom_lot: 'A' })
    expect(corpsCreationLot({ nom_lot: 'A', adresse_site: 'Rabat', ordre: '2', lignes: [5] }))
      .toEqual({ nom_lot: 'A', adresse_site: 'Rabat', ordre: 2, lignes: [5] })
  })

  it('messageErreurLots : detail 409 du contrat', () => {
    const refus = documentContrat('ventes', 'devis_lots').requete_post.refus_409
    expect(messageErreurLots({ response: { data: refus } })).toBe(refus.detail)
  })
})

describe('AjouterBoqElectrique', () => {
  it('devis non modifiable : aucun bouton', () => {
    const { container } = render(<AjouterBoqElectrique devisId={7} modifiable={false} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('clic : POST, bilan du contrat, manques listés, relecture du devis', async () => {
    ventesApi.ajouterBoqElectrique.mockResolvedValue(
      reponseContrat('ventes', 'devis_boq_electrique'))
    const onAjoute = vi.fn()
    render(<AjouterBoqElectrique devisId={7} modifiable onAjoute={onAjoute} />)
    expect(ventesApi.ajouterBoqElectrique).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: /Ajouter le BOQ électrique/ }))
    const exemple = documentContrat('ventes', 'devis_boq_electrique').exemple
    expect(ventesApi.ajouterBoqElectrique).toHaveBeenCalledWith(7)
    expect(await screen.findByRole('status')).toHaveTextContent(bilanBoq(exemple))
    expect(screen.getByText(exemple.manques[0].designation)).toBeInTheDocument()
    expect(onAjoute).toHaveBeenCalled()
  })

  it('sans conception électrique : le detail 400 du contrat est affiché', async () => {
    const refus = documentContrat('ventes', 'devis_boq_electrique').refus['400_sans_conception']
    ventesApi.ajouterBoqElectrique.mockRejectedValue({ response: { data: refus } })
    const onAjoute = vi.fn()
    render(<AjouterBoqElectrique devisId={7} modifiable onAjoute={onAjoute} />)
    await userEvent.click(screen.getByRole('button', { name: /Ajouter le BOQ électrique/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent(refus.detail)
    expect(onAjoute).not.toHaveBeenCalled()
  })

  it('bilanBoq : rien de neuf sur un second clic', () => {
    expect(bilanBoq({ creees: 0, lignes: [], manques: [], deja_presentes: ['X', 'Y'] }))
      .toBe('Aucune ligne ajoutée · 2 déjà présentes.')
    expect(bilanBoq(documentContrat('ventes', 'devis_boq_electrique').exemple))
      .toBe('2 lignes ajoutées · 1 à chiffrer faute de produit au catalogue · 1 déjà présente.')
  })
})
