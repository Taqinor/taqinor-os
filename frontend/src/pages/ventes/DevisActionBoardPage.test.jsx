import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* QX29/QX30 — « Relances du jour » : tableau d'action des devis, miroir de
   SavActionBoardPage.test.jsx (ZSAV6). ventesApi mocké.

   PACT13/PACT17 — la charge utile n'est PLUS tapée à la main : elle vient de
   l'exemple de contrat committé dans l'app
   (`apps/ventes/contract_samples/devis_action_requise.json`), le même fichier
   que `scripts/check_api_shapes.py` compare au dictionnaire RÉELLEMENT renvoyé
   par `selectors.devis_action_requise`, et que le test backend
   (`tests/test_pact17_devis_action_requise.py`) affirme égal à sa vraie
   réponse. Si le serveur change de forme, l'exemple change et ce test casse
   tout seul — sans réunion, sans discipline humaine. */

vi.mock('../../api/ventesApi', () => ({
  default: { getDevisActionBoard: vi.fn(), getDevis: vi.fn() },
}))

import ventesApi from '../../api/ventesApi'
import DevisActionBoardPage from './DevisActionBoardPage'

const BOARD = exempleContrat('ventes', 'devis_action_requise')
const IDS = Object.values(BOARD.buckets).flatMap((b) => b.ids)

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DevisActionBoardPage', () => {
  it('affiche les buckets, leurs comptes et les devis servis par le serveur', async () => {
    ventesApi.getDevisActionBoard.mockResolvedValue(
      reponseContrat('ventes', 'devis_action_requise'))
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)
    expect(await screen.findByText('Envoyés sans réponse')).toBeInTheDocument()
    // Chaque devis cité par un panier est rendu sous SA référence — jamais
    // « #42 » : le serveur fournit la ligne, l'écran ne la devine plus.
    for (const id of IDS) {
      const ligne = BOARD.devis[id]
      expect(await screen.findByText(new RegExp(ligne.reference))).toBeInTheDocument()
    }
    // Le compte affiché est celui du serveur, jamais recalculé côté écran.
    const total = Object.values(BOARD.buckets).reduce((s, b) => s + b.count, 0)
    expect(screen.getByText(`${total} devis nécessitant une action`)).toBeInTheDocument()
  })

  it('un seul appel réseau : la liste complète des devis n\'est plus retéléchargée', async () => {
    ventesApi.getDevisActionBoard.mockResolvedValue(
      reponseContrat('ventes', 'devis_action_requise'))
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)
    expect(await screen.findByText('Envoyés sans réponse')).toBeInTheDocument()
    expect(ventesApi.getDevis).not.toHaveBeenCalled()
  })

  it('affiche le raccourci « Appeler » depuis le téléphone servi par le serveur', async () => {
    ventesApi.getDevisActionBoard.mockResolvedValue(
      reponseContrat('ventes', 'devis_action_requise'))
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)
    const avecTel = IDS.filter((id) => BOARD.devis[id].client_telephone)
    const liens = await screen.findAllByRole('link', { name: /Appeler/ })
    expect(liens.length).toBe(avecTel.length)
    expect(liens[0]).toHaveAttribute(
      'href', `tel:${BOARD.devis[avecTel[0]].client_telephone}`)
  })

  it('affiche "Aucun devis." pour un bucket vide (5 buckets, dont la file QX30)', async () => {
    // `exemple_vide` = un AUTRE ÉTAT du serveur (société sans devis à traiter),
    // jamais une autre FORME : les 5 clés restent celles du contrat.
    ventesApi.getDevisActionBoard.mockResolvedValue(
      reponseContrat('ventes', 'devis_action_requise', 'exemple_vide'))
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)
    expect((await screen.findAllByText('Aucun devis.')).length).toBe(5)
  })
})

describe('DevisActionBoardPage — QX30 : file déclenchée par l\'engagement + wa.me pré-rempli', () => {
  it('rend la file "Relance engagement" et pré-remplit wa.me depuis board.wa_drafts', async () => {
    const engagementId = BOARD.buckets.engagement_relance.ids[0]
    const brouillon = BOARD.wa_drafts[engagementId]
    const numero = BOARD.devis[engagementId].client_whatsapp
    ventesApi.getDevisActionBoard.mockResolvedValue(
      reponseContrat('ventes', 'devis_action_requise'))
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)
    expect(await screen.findByText('Relance engagement')).toBeInTheDocument()
    const nom = BOARD.devis[engagementId].client_nom
    const waLink = await screen.findByRole('link', { name: `WhatsApp ${nom}` })
    expect(waLink).toHaveAttribute(
      'href',
      `https://wa.me/${numero.replace(/\D/g, '')}?text=${encodeURIComponent(brouillon)}`)
  })
})
