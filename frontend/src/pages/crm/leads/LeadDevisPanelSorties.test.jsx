// EDC6 — sorties protégées de l'Édition complète : Échap, clic sur le voile et ✕
// ne jettent plus l'ouvrier dehors sans prévenir quand le générateur annonce
// des modifications non enregistrées (`onDirtyChange(true)`). Les phases autres
// que `edit` gardent la fermeture Radix d'origine. `DevisGenerator` est mocké,
// mais il porte un VRAI ProduitPicker (Popover Radix) : Échap dans le popover
// ouvert ne ferme QUE le popover (pile de DismissableLayer), sans confirmation.
// Run : npx vitest run src/pages/crm/leads/LeadDevisPanelSorties.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ProduitPicker from '../../../components/ProduitPicker'
import {
  preparerApisPanneau, rendrePanneau, ouvrirEdition as ouvrirEditionPanneau, envoye,
} from '../../../test/panneauDevis'

// jsdom n'implémente pas scrollIntoView (utilisé par le picker).
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// EDC (gardes CI) : fabriques partagées — src/test/mocksApiDevis.js.
vi.mock('../../../api/ventesApi', async () => (await import('../../../test/mocksApiDevis.js')).ventesApiPanneauMock())
vi.mock('../../../api/stockApi', async () => (await import('../../../test/mocksApiDevis.js')).stockApiMock())

const PRODUITS = [
  { id: 1, nom: 'Onduleur Hybride Deye 6kW', prix_vente: 8000, tva: 20, is_archived: false },
  { id: 3, nom: 'Panneau Solaire 550W', prix_vente: 900, tva: 10, is_archived: false },
]
// Le générateur simulé garde ses props dans `generateur` et porte un VRAI picker.
vi.mock('../../ventes/DevisGenerator', async () => (await import('../../../test/mocksApiDevis.js'))
  .generateurSimule(() => <ProduitPicker produits={PRODUITS} value="" onChange={() => {}} />))

import ventesApi from '../../../api/ventesApi'
import stockApi from '../../../api/stockApi'
import { jumpToField } from '../../../features/crm/workspace/jumpToField'
import { missingFieldTarget } from '../../../features/crm/workspace/missingFields'
import { libelleSuccesDevisAuto } from '../../../features/ventes/autoQuote'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

// ALEA48 — le saut DOM est espionné : seul l'appel (cible) compte ici.
vi.mock('../../../features/crm/workspace/jumpToField', () => ({ jumpToField: vi.fn() }))

// Ces tests montent un Magasinier dans le store (`auth: true`).
const rendre = (props) => rendrePanneau(props, { auth: true })
const ouvrirEdition = (options) => ouvrirEditionPanneau({ auth: true, ...options })

const voile = () => document.querySelector('[class*="inset-0"]')
const cliquerVoile = () => userEvent.click(voile())
const echap = () => userEvent.keyboard('{Escape}')
const croix = () => screen.getByRole('button', { name: '✕' })
const boiteQuitter = () => screen.findByRole('alertdialog')
const enEdition = () => screen.queryByTestId('generateur-monte') !== null
const enApercu = () => screen.queryByRole('button', { name: /Télécharger le PDF/ }) !== null

beforeEach(() => preparerApisPanneau({ ventesApi }))

describe('EDC6 — sans modification (dirty === false) : on sort directement', () => {
  it('Échap sur un devis existant ⇒ aperçu, sans confirmation, sans fermer', async () => {
    const { onClose } = await ouvrirEdition()
    await echap()
    expect(await screen.findByRole('button', { name: /Télécharger le PDF/ })).toBeInTheDocument()
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(enEdition()).toBe(false)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('Échap en création (pas de devis) ⇒ fermeture du panneau', async () => {
    const { onClose } = await ouvrirEdition({ existingDevisId: null })
    await echap()
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('clic sur le voile sur un devis existant ⇒ aperçu', async () => {
    const { onClose } = await ouvrirEdition()
    await cliquerVoile()
    expect(await screen.findByRole('button', { name: /Télécharger le PDF/ })).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('clic sur le voile en création ⇒ fermeture', async () => {
    const { onClose } = await ouvrirEdition({ existingDevisId: null })
    await cliquerVoile()
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })

  it('✕ ⇒ fermeture du panneau (même sur un devis existant)', async () => {
    const { onClose } = await ouvrirEdition()
    await userEvent.click(croix())
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })
})

describe('EDC6 — avec modifications non enregistrées : « Quitter sans enregistrer ? »', () => {
  it('Échap ⇒ confirmation ; « Rester » garde l\'éditeur ouvert', async () => {
    const { onClose } = await ouvrirEdition({ dirty: true })
    await echap()
    const boite = await boiteQuitter()
    expect(boite).toHaveTextContent('Quitter sans enregistrer ?')
    await userEvent.click(within(boite).getByRole('button', { name: 'Rester' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(enEdition()).toBe(true)
    expect(enApercu()).toBe(false)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('Échap puis « Quitter » ⇒ aperçu quand le devis existe', async () => {
    const { onClose } = await ouvrirEdition({ dirty: true })
    await echap()
    await userEvent.click(within(await boiteQuitter()).getByRole('button', { name: 'Quitter' }))
    expect(await screen.findByRole('button', { name: /Télécharger le PDF/ })).toBeInTheDocument()
    expect(enEdition()).toBe(false)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('Échap puis « Quitter » en création ⇒ fermeture du panneau', async () => {
    const { onClose } = await ouvrirEdition({ dirty: true, existingDevisId: null })
    await echap()
    await userEvent.click(within(await boiteQuitter()).getByRole('button', { name: 'Quitter' }))
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })

  it('clic sur le voile ⇒ confirmation ; « Quitter » ⇒ aperçu, « Rester » ⇒ éditeur', async () => {
    const { onClose } = await ouvrirEdition({ dirty: true })
    await cliquerVoile()
    await userEvent.click(within(await boiteQuitter()).getByRole('button', { name: 'Rester' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(enEdition()).toBe(true)
    expect(onClose).not.toHaveBeenCalled()

    await cliquerVoile()
    await userEvent.click(within(await boiteQuitter()).getByRole('button', { name: 'Quitter' }))
    expect(await screen.findByRole('button', { name: /Télécharger le PDF/ })).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('✕ ⇒ confirmation ; « Rester » garde l\'éditeur, « Quitter » ferme le panneau', async () => {
    const { onClose } = await ouvrirEdition({ dirty: true })
    await userEvent.click(croix())
    await userEvent.click(within(await boiteQuitter()).getByRole('button', { name: 'Rester' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(enEdition()).toBe(true)
    expect(onClose).not.toHaveBeenCalled()

    await userEvent.click(croix())
    await userEvent.click(within(await boiteQuitter()).getByRole('button', { name: 'Quitter' }))
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })

  it('Échap pressé dans la confirmation ne ferme QUE la confirmation (= « Rester »)', async () => {
    const { onClose } = await ouvrirEdition({ dirty: true })
    await echap()
    await boiteQuitter()
    await echap()
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(enEdition()).toBe(true)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('le drapeau est remis à zéro à la sortie : revenir à l\'éditeur puis Échap ne redemande rien', async () => {
    await ouvrirEdition({ dirty: true })
    await echap()
    await userEvent.click(within(await boiteQuitter()).getByRole('button', { name: 'Quitter' }))
    await userEvent.click(await screen.findByRole('button', { name: /Édition complète/ }))
    await screen.findByTestId('generateur-monte')
    await act(async () => { await new Promise((r) => setTimeout(r, 5)) })
    await echap()
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(await screen.findByRole('button', { name: /Télécharger le PDF/ })).toBeInTheDocument()
  })
})

describe('EDC6 — Échap dans un popover imbriqué (ProduitPicker)', () => {
  it('ferme SEULEMENT le popover : ni confirmation, ni sortie (éditeur modifié)', async () => {
    const { onClose } = await ouvrirEdition({ dirty: true })
    const picker = within(screen.getByTestId('generateur-monte')).getByRole('button')
    await userEvent.click(picker)
    expect(await screen.findByText('Panneau Solaire 550W')).toBeInTheDocument()
    await echap()
    await waitFor(() => expect(screen.queryByText('Panneau Solaire 550W')).toBeNull())
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(enEdition()).toBe(true)
    expect(onClose).not.toHaveBeenCalled()
    // Le popover refermé, l'Échap SUIVANT concerne bien le panneau.
    await echap()
    expect(await boiteQuitter()).toHaveTextContent('Quitter sans enregistrer ?')
  })

  it('même chose sans modification : le popover seul se ferme, on reste dans l\'éditeur', async () => {
    const { onClose } = await ouvrirEdition()
    await userEvent.click(within(screen.getByTestId('generateur-monte')).getByRole('button'))
    await screen.findByText('Panneau Solaire 550W')
    await echap()
    await waitFor(() => expect(screen.queryByText('Panneau Solaire 550W')).toBeNull())
    expect(enEdition()).toBe(true)
    expect(enApercu()).toBe(false)
    expect(onClose).not.toHaveBeenCalled()
  })
})

describe('EDC6 — le garde `defaultPrevented` et les clics qui ne sont pas un « dehors »', () => {
  let ecouteur
  afterEach(() => {
    if (ecouteur) document.removeEventListener('keydown', ecouteur, true)
    ecouteur = null
    document.querySelectorAll('[data-sonner-toaster]').forEach((n) => n.remove())
  })

  it('un Échap déjà annulé en amont (defaultPrevented) n\'ouvre aucune confirmation et ne sort pas', async () => {
    // Écouteur de CAPTURE posé AVANT le montage : il passe avant celui de Radix.
    ecouteur = (e) => { if (e.key === 'Escape') e.preventDefault() }
    document.addEventListener('keydown', ecouteur, true)
    const { onClose } = await ouvrirEdition({ dirty: true })
    await echap()
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(enEdition()).toBe(true)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('un clic sur un toast (hors panneau) ne renvoie pas à l\'aperçu', async () => {
    const { onClose } = await ouvrirEdition()
    const toaster = document.createElement('ol')
    toaster.setAttribute('data-sonner-toaster', 'true')
    const toast = document.createElement('li')
    toast.setAttribute('data-sonner-toast', 'true')
    toast.textContent = 'Modifications enregistrées.'
    toaster.appendChild(toast)
    document.body.appendChild(toaster)
    // Un vrai clic (userEvent refuse : <body> est en pointer-events: none sous
    // le Dialog modal). Le Dialog Radix attend le `click` pour décider
    // (deferPointerDownOutside) : on joue donc toute la séquence.
    fireEvent.pointerDown(toast)
    fireEvent.mouseDown(toast)
    fireEvent.pointerUp(toast)
    fireEvent.mouseUp(toast)
    fireEvent.click(toast)
    await act(async () => { await new Promise((r) => setTimeout(r, 20)) })
    expect(enEdition()).toBe(true)
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(onClose).not.toHaveBeenCalled()
  })
})

describe('EDC6 — les autres phases gardent leur comportement actuel', () => {
  it('aperçu : Échap ferme le panneau (Radix inchangé)', async () => {
    const { onClose } = rendre({ mode: 'view' })
    await screen.findByRole('button', { name: /Télécharger le PDF/ })
    await act(async () => { await new Promise((r) => setTimeout(r, 5)) })
    await echap()
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('aperçu : clic sur le voile ferme le panneau', async () => {
    const { onClose } = rendre({ mode: 'view' })
    await screen.findByRole('button', { name: /Télécharger le PDF/ })
    await act(async () => { await new Promise((r) => setTimeout(r, 5)) })
    await cliquerVoile()
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })

  it('aperçu : ✕ ferme le panneau', async () => {
    const { onClose } = rendre({ mode: 'view' })
    await screen.findByRole('button', { name: /Télécharger le PDF/ })
    await userEvent.click(croix())
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('erreur (création automatique échouée) : Échap ferme le panneau', async () => {
    ventesApi.creerDevisAuto.mockRejectedValueOnce({ response: { status: 422, data: { detail: 'Données insuffisantes.' } } })
    const { onClose } = rendrePanneau({
      lead: { id: 91, nom: 'Usine', type_installation: 'industriel' },
      mode: 'auto', existingDevisId: undefined,
    })
    await screen.findByText('Données insuffisantes.')
    await act(async () => { await new Promise((r) => setTimeout(r, 5)) })
    await echap()
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })
})

// ALEA48 — le 409 du devis auto garde son `field` jusqu'à l'écran : bouton
// « Compléter : <champ> » qui saute au champ du lead (même geste que DevisTab).
describe('ALEA48 — 409 du devis automatique : bouton « Compléter »', () => {
  const LEAD_RESIDENTIEL = { id: 92, nom: 'Maison', type_installation: 'residentiel' }
  const rejeter409 = (data) => ventesApi.creerDevisAuto.mockRejectedValueOnce({ response: { status: 409, data } })

  beforeEach(() => jumpToField.mockClear())

  it('409 avec `field` ⇒ message serveur + bouton, le clic saute au champ', async () => {
    rejeter409({ detail: "Contrat d'électricité manquant.", field: 'contrat_electricite' })
    const { onClose } = rendrePanneau({ lead: LEAD_RESIDENTIEL, mode: 'auto', existingDevisId: undefined })
    expect(await screen.findByText("Contrat d'électricité manquant.")).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: "Compléter : Contrat d'électricité" }))
    expect(onClose).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(jumpToField).toHaveBeenCalledWith(missingFieldTarget('contrat_electricite')))
  })

  it('409 sans `field` ⇒ message seul, aucun bouton', async () => {
    rejeter409({ detail: 'Données insuffisantes.' })
    rendrePanneau({ lead: LEAD_RESIDENTIEL, mode: 'auto', existingDevisId: undefined })
    expect(await screen.findByText('Données insuffisantes.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Compléter/ })).toBeNull()
  })

  it('409 avec un `field` inconnu ⇒ message seul, aucun bouton', async () => {
    rejeter409({ detail: 'Champ exotique.', field: 'champ_inconnu_xyz' })
    rendrePanneau({ lead: LEAD_RESIDENTIEL, mode: 'auto', existingDevisId: undefined })
    expect(await screen.findByText('Champ exotique.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Compléter/ })).toBeNull()
  })
})

// T4-X1-011 — un 500 du devis automatique : le panneau dit que le SERVEUR n'a
// pas répondu (pas la fiche) et offre « Réessayer », qui relance la création.
describe('T4-X1-011 — 500 du devis automatique : « Réessayer »', () => {
  it('500 ⇒ message serveur sans « vérifiez la fiche », le bouton relance un 2e appel', async () => {
    ventesApi.creerDevisAuto.mockRejectedValueOnce({ response: { status: 500, data: {} } })
    ventesApi.creerDevisAuto.mockResolvedValueOnce({ data: { id: 777, reference: 'DEV-RETRY' } })
    rendrePanneau({ lead: { id: 93, nom: 'Maison', type_installation: 'residentiel' },
      mode: 'auto', existingDevisId: undefined })
    const alerte = await screen.findByRole('alert')
    expect(alerte.textContent).toMatch(/serveur/)
    expect(alerte.textContent).not.toMatch(/vérifiez la fiche/)
    await userEvent.click(screen.getByTestId('ldp-reessayer'))
    await waitFor(() => expect(ventesApi.creerDevisAuto).toHaveBeenCalledTimes(2))
    expect(screen.queryByTestId('ldp-reessayer')).toBeNull()
  })

  it('422 nommant un champ : pas de « Réessayer » (la fiche est bien en cause)', async () => {
    ventesApi.creerDevisAuto.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Facture manquante.', field: 'facture_hiver' } } })
    rendrePanneau({ lead: { id: 94, nom: 'Maison', type_installation: 'residentiel' },
      mode: 'auto', existingDevisId: undefined })
    expect(await screen.findByText('Facture manquante.')).toBeInTheDocument()
    expect(screen.queryByTestId('ldp-reessayer')).toBeNull()
  })
})

// ALEA51 — après le devis automatique : une phrase de SUCCÈS (jamais la boîte
// rouge des erreurs), les alertes du serveur en avertissement dessous.
describe('ALEA51 — devis automatique créé : bannière de succès', () => {
  const normaliser = (t) => t.replace(/[\u202f\u00a0]/g, ' ')
  // COP2-W3 — la base est l'échantillon du contrat (référence, kWc, total TTC) ; seuls les champs que
  // l'échantillon ne porte pas (économie, retour, postes, alerte) sont posés ici pour tester le bandeau.
  const BASE = exempleContrat('ventes', 'assistant_devis_cree')
  const REPONSE = {
    ...BASE,
    economie_an_1_ht: 102040, retour_ans: null,
    postes_apres_visite: ['Structure C&I', 'Câble solaire DC', 'Câble AC'],
    alertes: [{ code: 'a_chiffrer_visite', message: 'À chiffrer après la visite.', interne: true }],
  }

  it('réf. · kWc · TTC · économie ≈ · postes à chiffrer, alertes en avertissement', async () => {
    ventesApi.creerDevisAuto.mockResolvedValueOnce({ data: REPONSE })
    rendrePanneau({
      lead: { id: 91, nom: 'Usine', type_installation: 'industriel' },
      mode: 'auto', existingDevisId: undefined,
    })
    const banniere = await screen.findByTestId('ldp-succes-auto')
    // T4-U1-026 — l'échantillon sert kwc = 7.1 : le bandeau dit la puissance du devis, jamais l'entier arrondi.
    // T4-V2-015 — l'échantillon est une option unique avec batterie (imposée, pas un souhait de la fiche).
    expect(normaliser(banniere.textContent)).toContain(
      `${BASE.reference} · 7,1 kWc · 73 000 MAD TTC · option unique : avec batterie · économie ≈ 102 000 MAD/an · 3 postes à chiffrer après la visite`)
    // retour_ans null (investissement incomplet) ⇒ aucun « retour » inventé.
    expect(banniere.textContent).not.toMatch(/retour/)
    const alertes = screen.getByTestId('ldp-alertes-auto')
    expect(alertes).toHaveTextContent('À chiffrer après la visite.')
    expect(document.querySelector('.form-error-box')).toBeNull()
  })

  it('les informations au-dessus du devis se replient (dépliées par défaut) et disent ce qu’elles cachent', async () => {
    ventesApi.creerDevisAuto.mockResolvedValueOnce({ data: REPONSE })
    rendrePanneau({
      lead: { id: 91, nom: 'Usine', type_installation: 'industriel' },
      mode: 'auto', existingDevisId: undefined,
    })
    await screen.findByTestId('ldp-succes-auto')
    const bascule = screen.getByTestId('ldp-infos-bascule')
    // Dépliées par défaut : succès et alertes visibles, l’en-tête propose « Replier ».
    expect(bascule).toHaveAttribute('aria-expanded', 'true')
    expect(bascule).toHaveTextContent('Informations du devis — 1 alerte')
    expect(bascule).toHaveTextContent('Replier')
    expect(screen.getByTestId('ldp-alertes-auto')).toBeInTheDocument()
    await userEvent.click(bascule)
    // Repliées : plus rien ne prend de hauteur, mais le nombre d’alertes reste dit.
    expect(bascule).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByTestId('ldp-succes-auto')).toBeNull()
    expect(screen.queryByTestId('ldp-alertes-auto')).toBeNull()
    expect(bascule).toHaveTextContent('Informations du devis — 1 alerte')
    expect(bascule).toHaveTextContent('Afficher')
    await userEvent.click(bascule)
    expect(screen.getByTestId('ldp-alertes-auto')).toHaveTextContent('À chiffrer après la visite.')
  })

  it('ADEV123 — résidentiel : les suppositions du serveur s’affichent comme celles du C&I', async () => {
    // Vu en direct (T3-VAGUED) : la réponse portait quatre suppositions, le panneau aucune.
    ventesApi.creerDevisAuto.mockResolvedValueOnce({ data: {
      ...BASE,
      alertes: [{ code: 'suppose_presence', champ_lead: 'occupation_jour',
                  message: 'Présence en journée supposée (profil « présent »).' }],
    } })
    rendrePanneau({
      lead: { id: 93, nom: 'Maison', type_installation: 'residentiel', facture_hiver: '600' },
      mode: 'auto', existingDevisId: undefined,
    })
    const alertes = await screen.findByTestId('ldp-alertes-auto')
    expect(alertes).toHaveTextContent('Présence en journée supposée')
    expect(within(alertes).getByTestId('alerte-champ-lead')).toHaveTextContent(
      "À compléter sur la fiche : Y a-t-il quelqu'un à la maison en journée ?")
    expect(screen.getByTestId('ldp-infos-bascule')).toHaveTextContent('1 alerte')
  })

  it('ADEV123/ADEV125 — rouvert, le devis remontre les suppositions rangées à sa création', async () => {
    // Contrat devis_journal_auto.json : etude_params.journal_auto.alertes.
    const rangees = exempleContrat('ventes', 'devis_journal_auto')
    ventesApi.getDevisById.mockResolvedValue({ data: {
      ...exempleContrat('ventes', 'devis_modifiabilite', 'exemple_envoye'),
      etude_params: rangees.etude_params,
    } })
    rendrePanneau({ mode: 'view', lead: { id: 77, nom: 'Khalid', type_installation: 'residentiel' } })
    const alertes = await screen.findByTestId('ldp-alertes-auto')
    for (const a of rangees.etude_params.journal_auto.alertes) {
      expect(alertes).toHaveTextContent(a.message)
    }
    expect(within(alertes).getAllByTestId('alerte-champ-lead')[0]).toHaveTextContent(
      "À compléter sur la fiche : Y a-t-il quelqu'un à la maison en journée ?")
  })

  it('le libellé omet ce que le serveur ne sert pas et garde le retour chiffré', () => {
    expect(libelleSuccesDevisAuto(null)).toBe('')
    const texte = normaliser(libelleSuccesDevisAuto({
      reference: 'DEV-1', kwc: 5, total_ttc: 41000, economie_an_1_ht: null,
      retour_ans: 4.26, postes_apres_visite: ['Structure C&I'],
    }))
    expect(texte).toBe('DEV-1 · 5 kWc · 41 000 MAD TTC · retour ≈ 4,3 ans · 1 poste à chiffrer après la visite')
  })
})

// ALEA52 — l'aperçu PDF porte « Envoyer au client » : la MÊME boîte que la carte
// devis (canaux d'abord, réglages sous « Avancé »), sans les options réservées
// au résidentiel pour un devis commercial / industriel / agricole.
describe('ALEA52 — aperçu : « Envoyer au client » ouvre la boîte partagée', () => {
  const ouvrirApercu = async (lead) => {
    rendre({ mode: 'view', lead: { id: 77, nom: 'Khalid', email: 'k@example.com', ...lead } })
    await userEvent.click(await screen.findByRole('button', { name: /Envoyer au client/ }))
    return screen.findByRole('dialog', { name: /Envoyer au client/ })
  }
  const boiteFermee = () => waitFor(() => expect(
    screen.queryByRole('dialog', { name: /Envoyer au client/ })).toBeNull())

  it('résidentiel : trois canaux, « Avancé » replié, options 1/2/3 et case étude proposées', async () => {
    const boite = await ouvrirApercu({ type_installation: 'residentiel' })
    expect(within(boite).getByRole('button', { name: 'WhatsApp' })).toBeInTheDocument()
    expect(within(boite).getByRole('button', { name: /E-mail/ })).toBeEnabled()
    expect(within(boite).getByRole('button', { name: /Copier le lien/ })).toBeInTheDocument()
    expect(within(boite).queryByText('Options présentées au client :')).toBeNull()
    await userEvent.click(within(boite).getByRole('button', { name: /Avancé/ }))
    expect(within(boite).getByText('Options présentées au client :')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    await boiteFermee()
    expect(screen.getByText("Inclure l'étude")).toBeInTheDocument()
    // T4-V2-017 — cochée, la case dit AVANT de générer quand la page s'ajoute.
    expect(screen.queryByTestId('ldp-etude-condition')).toBeNull()
    await userEvent.click(screen.getByText("Inclure l'étude"))
    expect(screen.getByTestId('ldp-etude-condition')).toHaveTextContent('sinon le PDF garde ses 3 pages')
  })

  it('industriel : ni « Inclure l’étude » ni options 1/2/3 (sans effet en C&I)', async () => {
    const boite = await ouvrirApercu({ type_installation: 'industriel' })
    await userEvent.click(within(boite).getByRole('button', { name: /Avancé/ }))
    expect(within(boite).getByText('Ce que le client reçoit :')).toBeInTheDocument()
    expect(within(boite).queryByText('Options présentées au client :')).toBeNull()
    expect(within(boite).queryByRole('button', { name: /Modifier les options…/ })).toBeNull()
    await userEvent.keyboard('{Escape}')
    await boiteFermee()
    expect(screen.queryByText("Inclure l'étude")).toBeNull()
  })
})

// ALEA55 — nettoyages : plus de préchargement du catalogue avant le devis auto,
// étapes visibles pendant la création, format PDF choisi sur la carte.
describe('ALEA55 — devis automatique : pas de préchargement, étapes, format PDF', () => {
  const LEAD_PRO = { id: 91, nom: 'Usine', type_installation: 'industriel' }

  it('aucune lecture du catalogue ni des gammes avant (ni pendant) l’appel serveur', async () => {
    ventesApi.creerDevisAuto.mockResolvedValueOnce({ data: { id: 413, reference: 'DEV-1', kwc: 10 } })
    rendrePanneau({ lead: LEAD_PRO, mode: 'auto', existingDevisId: undefined })
    await screen.findByTestId('ldp-succes-auto')
    expect(ventesApi.creerDevisAuto).toHaveBeenCalledTimes(1)
    expect(stockApi.getProduits).not.toHaveBeenCalled()
    expect(ventesApi.getParametresGammes).not.toHaveBeenCalled()
    // Le corps part tel quel : le lead, la remise — jamais un catalogue.
    expect(ventesApi.creerDevisAuto.mock.calls[0][0]).toEqual({ lead: 91, remise_globale: '0' })
  })

  it('pendant la création : Étude → Composition → PDF, l’étape courante marquée', async () => {
    ventesApi.creerDevisAuto.mockReturnValueOnce(new Promise(() => {}))
    rendrePanneau({ lead: LEAD_PRO, mode: 'auto', existingDevisId: undefined })
    const etapes = await screen.findByTestId('ldp-etapes-creation')
    expect(etapes).toHaveTextContent(/Étude.*Composition.*PDF/s)
    expect(etapes.querySelector('[aria-current="step"]')).toHaveAttribute('data-etape', 'Étude')
  })

  it('un format « 1 page » choisi sur la carte ouvre le devis EXISTANT en 1 page, sans création', async () => {
    rendrePanneau({ mode: 'view', existingDevisId: 413, pdfInitial: 'onepage' })
    await screen.findByRole('button', { name: /Télécharger le PDF/ })
    expect(screen.getByRole('radio', { name: '1 page' })).toHaveAttribute('aria-checked', 'true')
    expect(ventesApi.creerDevisAuto).not.toHaveBeenCalled()
  })

  it('même en mode « onepage », un devis existant n’est jamais recréé', async () => {
    rendrePanneau({ mode: 'onepage', existingDevisId: 413 })
    await screen.findByRole('button', { name: /Télécharger le PDF/ })
    expect(ventesApi.creerDevisAuto).not.toHaveBeenCalled()
  })
})

describe('Devis final C&I — choix enregistré sur le devis (etude_params.devis_final)', () => {
  // Le devis tel que le panneau le garde : la réponse brute de `getDevisById`
  // (exemple « envoyé » du contrat) + les champs de marché servis par le détail.
  const devisServi = (marche, etudeParams) => ({
    data: { ...envoye().data, mode_installation: marche, etude_params: etudeParams },
  })
  const boite = () => screen.findByTestId('ldp-devis-final')
  const ouvrirApercu = async (marche, etudeParams) => {
    ventesApi.getDevisById.mockResolvedValue(devisServi(marche, etudeParams))
    rendrePanneau({ mode: 'view', existingDevisId: 413 })
    await screen.findByRole('button', { name: /Télécharger le PDF/ })
  }

  it('commercial : coché quand le devis servi porte devis_final: true, dans les deux formats', async () => {
    await ouvrirApercu('commercial', { devis_final: true })
    expect(await boite()).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(screen.getByRole('radio', { name: '1 page' }))
    expect(await boite()).toHaveAttribute('aria-checked', 'true')
  })

  it('industriel : décoché sans la clé ; cocher envoie { devis_final: true } puis relit et relance l’aperçu', async () => {
    await ouvrirApercu('industriel', {})
    expect(await boite()).toHaveAttribute('aria-checked', 'false')
    ventesApi.patchEtudeParams.mockResolvedValueOnce({ data: {} })
    ventesApi.getDevisById.mockResolvedValue(devisServi('industriel', { devis_final: true }))
    const appelsApercu = ventesApi.getProposalPdf.mock.calls.length
    await userEvent.click(await boite())
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalledWith(413, { devis_final: true }))
    await waitFor(() => expect(screen.getByTestId('ldp-devis-final')).toHaveAttribute('aria-checked', 'true'))
    await waitFor(() => expect(ventesApi.getProposalPdf.mock.calls.length).toBeGreaterThan(appelsApercu))
  })

  it('décocher envoie { devis_final: null }', async () => {
    await ouvrirApercu('commercial', { devis_final: true })
    ventesApi.patchEtudeParams.mockResolvedValueOnce({ data: {} })
    ventesApi.getDevisById.mockResolvedValue(devisServi('commercial', {}))
    await userEvent.click(await boite())
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalledWith(413, { devis_final: null }))
    await waitFor(() => expect(screen.getByTestId('ldp-devis-final')).toHaveAttribute('aria-checked', 'false'))
  })

  it('un refus du serveur affiche son message sous la case, qui garde son état', async () => {
    await ouvrirApercu('commercial', {})
    ventesApi.patchEtudeParams.mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'Ce devis est figé : révisez-le d’abord.' } },
    })
    await userEvent.click(await boite())
    expect(await screen.findByTestId('ldp-devis-final-erreur'))
      .toHaveTextContent('Ce devis est figé : révisez-le d’abord.')
    expect(screen.getByTestId('ldp-devis-final')).toHaveAttribute('aria-checked', 'false')
  })

  it('résidentiel : la même case enregistre (Premium seulement), indice « paiement + RIB s’il est renseigné »', async () => {
    await ouvrirApercu('residentiel', { devis_final: true })
    const c = await boite()
    expect(c).toHaveAttribute('aria-checked', 'true')
    // T4-U1-009 — le RIB n'est imprimé que s'il est au profil société : jamais promis sans condition.
    expect(c.closest('label')).toHaveTextContent('(paiement + RIB s’il est renseigné au profil société)')
    ventesApi.patchEtudeParams.mockResolvedValueOnce({ data: {} })
    ventesApi.getDevisById.mockResolvedValue(devisServi('residentiel', {}))
    await userEvent.click(c)
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalledWith(413, { devis_final: null }))
    await userEvent.click(screen.getByRole('radio', { name: '1 page' }))
    expect(screen.queryByTestId('ldp-devis-final')).toBeNull()
  })

  it('agricole : case enregistrée en Premium, indice « à confirmer par la visite », absente en 1 page', async () => {
    await ouvrirApercu('agricole', {})
    const c = await boite()
    expect(c.closest('label')).toHaveTextContent('sans « à confirmer par la visite »')
    await userEvent.click(screen.getByRole('radio', { name: '1 page' }))
    expect(screen.queryByTestId('ldp-devis-final')).toBeNull()
  })

  it('« PDF ▾ → Devis final » de la carte reste un rendu seul : aucune écriture', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisServi('residentiel', {}))
    rendrePanneau({ mode: 'view', existingDevisId: 413, pdfInitial: 'final' })
    await screen.findByRole('button', { name: /Télécharger le PDF/ })
    await waitFor(() => expect(ventesApi.getProposalPdf).toHaveBeenCalled())
    expect(ventesApi.getProposalPdf.mock.calls[0][1]).toMatchObject({ devis_final: 1 })
    expect(ventesApi.patchEtudeParams).not.toHaveBeenCalled()
  })
})

// T4-X6-017 — un devis sans onduleur : le serveur refuse le document à options
// (409, contrat devis_proposal_refus.json) et sert le format possible en CHAMP.
// Le panneau l'offre par un bouton en mots de vendeur ; aucun « Réessayer » qui
// redemanderait le même format, aucun paramètre d'adresse à l'écran.
describe('T4-X6-017 — devis sans onduleur : le panneau offre le format une page', () => {
  it('409 « format_possible: onepage » : « Voir le devis une page » bascule en 1 page, sans « Réessayer »', async () => {
    const refus = exempleContrat('ventes', 'devis_proposal_refus')
    ventesApi.getProposalPdf.mockImplementation((_id, params) => (params?.pdf_mode === 'onepage'
      ? new Promise(() => {})
      : Promise.reject({ response: { status: 409, data: new Blob([JSON.stringify(refus)], { type: 'application/json' }) } })))
    rendrePanneau({ mode: 'view', existingDevisId: 413 })
    const alerte = await screen.findByRole('alert')
    await waitFor(() => expect(alerte).toHaveTextContent(refus.detail))
    expect(alerte.textContent).not.toMatch(/pdf_mode|\?/)
    expect(within(alerte).queryByRole('button', { name: /Réessayer/ })).toBeNull()
    await userEvent.click(within(alerte).getByRole('button', { name: 'Voir le devis une page' }))
    await waitFor(() => expect(ventesApi.getProposalPdf.mock.calls.at(-1)[1]).toMatchObject({ pdf_mode: 'onepage' }))
    expect(screen.getByRole('radio', { name: '1 page' })).toBeChecked()
  })
})
