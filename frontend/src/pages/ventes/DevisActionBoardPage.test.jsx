import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

// CHT14 — vérifie que les liens de la carte « Chantiers à facturer »
// naviguent bien vers `/chantiers?id=` (real MemoryRouter préservé via
// `...actual`, comme PremiersPasWidget.test.jsx) : les tests QX29/QX30
// existants ne cliquent jamais un bouton de navigation, donc ce mock ne les
// affecte pas.
const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

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

// CHT14 — carte SÉPARÉE « Chantiers à facturer » (second fetch indépendant,
// endpoint `installations/a-facturer/` EXISTANT, YSERV7). Résolu vide par
// défaut pour ne pas casser les tests QX29/QX30 ci-dessous, qui ne
// s'intéressent qu'au board principal — voir le describe dédié plus bas pour
// les données mockées de cette carte.
vi.mock('../../api/installationsApi', () => ({
  default: { getChantiersAFacturer: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import ventesApi from '../../api/ventesApi'
import installationsApi from '../../api/installationsApi'
import DevisActionBoardPage from './DevisActionBoardPage'

const BOARD = exempleContrat('ventes', 'devis_action_requise')
const IDS = Object.values(BOARD.buckets).flatMap((b) => b.ids)

beforeEach(() => {
  // Repli sûr par défaut à chaque test — une surcharge locale (voir le
  // describe CHT14 plus bas) ne doit jamais fuiter sur les tests suivants.
  installationsApi.getChantiersAFacturer.mockResolvedValue({ data: [] })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DevisActionBoardPage', () => {
  it('affiche les buckets, leurs comptes et les devis servis par le serveur', async () => {
    ventesApi.getDevisActionBoard.mockResolvedValue(
      reponseContrat('ventes', 'devis_action_requise'))
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)
    expect((await screen.findAllByText('Envoyés sans réponse')).length).toBeGreaterThan(0)
    // Chaque devis cité par un panier est rendu sous SA référence — jamais
    // « #42 » : le serveur fournit la ligne, l'écran ne la devine plus.
    for (const id of IDS) {
      const ligne = BOARD.devis[id]
      expect((await screen.findAllByText(new RegExp(ligne.reference))).length).toBeGreaterThan(0)
    }
    // Le compte affiché est celui du serveur, jamais recalculé côté écran.
    const total = Object.values(BOARD.buckets).reduce((s, b) => s + b.count, 0)
    expect(screen.getAllByText(`${total} devis nécessitant une action`).length).toBeGreaterThan(0)
  })

  it('un seul appel réseau : la liste complète des devis n\'est plus retéléchargée', async () => {
    ventesApi.getDevisActionBoard.mockResolvedValue(
      reponseContrat('ventes', 'devis_action_requise'))
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)
    expect((await screen.findAllByText('Envoyés sans réponse')).length).toBeGreaterThan(0)
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
    expect((await screen.findAllByText('Relance engagement')).length).toBeGreaterThan(0)
    const nom = BOARD.devis[engagementId].client_nom
    const waLink = await screen.findByRole('link', { name: `WhatsApp ${nom}` })
    expect(waLink).toHaveAttribute(
      'href',
      `https://wa.me/${numero.replace(/\D/g, '')}?text=${encodeURIComponent(brouillon)}`)
  })
})

describe('DevisActionBoardPage — CHT14 : carte "Chantiers à facturer"', () => {
  // Schéma RÉEL de `installations.services.chantiers_a_facturer` (YSERV7) —
  // une entrée PAR TRANCHE due, jamais un devis_id (endpoint EXISTANT
  // inchangé, zéro backend pour CHT14).
  const CHANTIERS_A_FACTURER = [
    {
      installation_id: 501, reference: 'CH-2026-0007',
      tranche: 'Tranche 2 - Livraison', jalon_id: 12,
      jalon_libelle: 'Livraison matériel',
    },
    {
      installation_id: 502, reference: 'CH-2026-0009',
      tranche: 'Solde', jalon_id: 15, jalon_libelle: 'Réception',
    },
  ]

  beforeEach(() => {
    ventesApi.getDevisActionBoard.mockResolvedValue(
      reponseContrat('ventes', 'devis_action_requise'))
  })

  it('affiche "Aucune tranche due." quand l\'endpoint ne renvoie rien', async () => {
    installationsApi.getChantiersAFacturer.mockResolvedValue({ data: [] })
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)
    expect(await screen.findByText('Chantiers à facturer')).toBeInTheDocument()
    expect(await screen.findByText('Aucune tranche due.')).toBeInTheDocument()
  })

  it('rend une carte séparée (jamais fondue dans BUCKETS) avec le compte et les lignes du serveur', async () => {
    installationsApi.getChantiersAFacturer.mockResolvedValue(
      { data: CHANTIERS_A_FACTURER })
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)

    const titre = await screen.findByText('Chantiers à facturer')
    expect(titre).toBeInTheDocument()
    // Le compte de la carte est celui du serveur — jamais mêlé au total des
    // BUCKETS (« N devis nécessitant une action » reste inchangé). Match
    // EXACT ('2', pas une sous-chaîne de "CH-2026-...") dans l'en-tête.
    const enTete = titre.closest('div')
    expect(within(enTete).getByText('2')).toBeInTheDocument()

    for (const c of CHANTIERS_A_FACTURER) {
      expect(await screen.findByText(
        new RegExp(`${c.reference}.*${c.tranche}.*${c.jalon_libelle}`))).toBeInTheDocument()
    }
  })

  it('le lien de la ligne et le CTA "Facturer" naviguent vers /chantiers?id=<installation_id>', async () => {
    const user = userEvent.setup()
    installationsApi.getChantiersAFacturer.mockResolvedValue(
      { data: CHANTIERS_A_FACTURER })
    render(<MemoryRouter><DevisActionBoardPage /></MemoryRouter>)

    const ligne = await screen.findByText(/CH-2026-0007/)
    await user.click(ligne)
    expect(navigateMock).toHaveBeenLastCalledWith('/chantiers?id=501')

    const facturer = await screen.findAllByRole('button', { name: 'Facturer' })
    await user.click(facturer[0])
    expect(navigateMock).toHaveBeenLastCalledWith('/chantiers?id=501')
  })
})
