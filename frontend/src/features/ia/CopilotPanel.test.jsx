import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// AIC8 — contrat partagé (PACT10/PACT13) : la réponse de la note vient de
// l'exemple committé, jamais d'une charge utile tapée à la main.
import CONTRAT from '../../../../backend/django_core/apps/agent/contract_samples/assistant_evenement.json'

vi.mock('../../api/iaApi', () => ({
  default: {
    queryAgent: vi.fn(),
    getChatHistory: vi.fn(() => Promise.resolve({ data: [] })),
    clearChatHistory: vi.fn(() => Promise.resolve({})),
    noterEvenement: vi.fn(),
    getSuggestions: vi.fn(),
    // COP2-W2 — capacités de l'assistant pour ce compte (limite de question, images).
    getCapacitesAssistant: vi.fn(),
  },
}))
// COP2-W2 — jsdom n'a ni canvas ni URL d'objet : la réduction (Image + canvas) est simulée, le reste
// du module (fonctions pures) est le vrai.
vi.mock('./images', async (importOriginal) => ({
  ...(await importOriginal()),
  reduireImage: vi.fn(async () => ({ media_type: 'image/jpeg', data: 'QUJD', apercu: 'blob:apercu-test' })),
}))

import iaApi from '../../api/iaApi'
import { reduireImage } from './images'
import iaReducer from './store/iaSlice'
import CopilotPanel from './CopilotPanel'
import { EVENEMENT_OUVRIR } from './copilotMessages'
import {
  installerEcouteurOuverture, reinitialiserEcouteurOuverture,
} from './ecouteurOuverture'
// TCH118 / A12 — les quatre demandes prêtes de Tâches (client Tâches mocké sur les contrats committés).
import { MemoryRouter } from 'react-router-dom'
import * as tachesApi from '../../api/tachesApi'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/tachesApi', () => ({
  proposerJournee: vi.fn(), lirePriorites: vi.fn(), lirePoint: vi.fn(), saisieRapide: vi.fn(),
  listerToutesLesTaches: vi.fn(), lireAujourdhui: vi.fn(),
}))

/* Nouveau fichier car : aucun module vitest n'héberge le panneau Copilote
   (copilotMessages.test.mjs est un test node pur, sans DOM). */

const EVENEMENT_ID = CONTRAT.exemple.id

function monter({ ouvert = true } = {}) {
  const initial = iaReducer(undefined, { type: '@@init' })
  const store = configureStore({
    reducer: { ia: iaReducer },
    preloadedState: { ia: { ...initial, copilotOpen: ouvert } },
  })
  render(<Provider store={store}><CopilotPanel /></Provider>)
  return store
}

const CONTEXTE_VIDE = { lead_id: null, devis_id: null, touche_id: null, diagnostic: null }

afterEach(() => { reinitialiserEcouteurOuverture() })

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
  iaApi.queryAgent.mockClear()
  iaApi.noterEvenement.mockClear()
  iaApi.queryAgent.mockResolvedValue({
    data: { answer: CONTRAT.exemple.resume_reponse, evenement_id: EVENEMENT_ID },
  })
  iaApi.noterEvenement.mockResolvedValue({ data: CONTRAT.ecriture_commercial.exemple })
  iaApi.getSuggestions.mockResolvedValue({ data: [] })
  iaApi.getCapacitesAssistant.mockReset()
  iaApi.getCapacitesAssistant.mockResolvedValue({ data: { limite_question: 2000, images_acceptees: false } })
})

async function poserUneQuestion(user) {
  await user.type(screen.getByPlaceholderText(/Posez votre question/), CONTRAT.exemple.question)
  await user.click(screen.getByRole('button', { name: 'Envoyer' }))
  await screen.findByText(CONTRAT.exemple.resume_reponse)
}

describe('CopilotPanel — note de la réponse (AIC8)', () => {
  it('clic 👎 puis Envoyer ⇒ noterEvenement(id, −1) et « merci »', async () => {
    const user = userEvent.setup()
    const store = monter()
    await poserUneQuestion(user)
    await user.click(screen.getByRole('button', { name: 'Réponse fausse' }))
    await user.type(screen.getByLabelText('Commentaire sur la réponse'),
      CONTRAT.ecriture_commercial.exemple_corps.commentaire)
    await user.click(screen.getByRole('button', { name: 'Envoyer le retour' }))
    expect(iaApi.noterEvenement).toHaveBeenCalledWith(
      EVENEMENT_ID, -1, CONTRAT.ecriture_commercial.exemple_corps.commentaire)
    await screen.findByText('Merci pour votre retour.')
    const dernier = store.getState().ia.messages.at(-1)
    expect(dernier.note).toBe(-1)
    expect(dernier.evenement_id).toBe(EVENEMENT_ID)
  })

  it('clic 👍 ⇒ noterEvenement(id, 1) sans commentaire', async () => {
    const user = userEvent.setup()
    monter()
    await poserUneQuestion(user)
    await user.click(screen.getByRole('button', { name: 'Réponse utile' }))
    await waitFor(() => expect(iaApi.noterEvenement).toHaveBeenLastCalledWith(EVENEMENT_ID, 1, null))
  })

  it('aucune note proposée sans événement journalisé', async () => {
    iaApi.queryAgent.mockResolvedValue({ data: { answer: 'Sans journal.' } })
    const user = userEvent.setup()
    monter()
    await user.type(screen.getByPlaceholderText(/Posez votre question/), 'bonjour')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    await screen.findByText('Sans journal.')
    expect(screen.queryByTestId('note-reponse')).toBeNull()
  })
})

describe('CopilotPanel — entrée contextuelle (AIC9)', () => {
  it('l\'événement EVENEMENT_OUVRIR ouvre le panneau et transmet le contexte', async () => {
    const store = monter({ ouvert: false })
    window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, {
      detail: { ecran: CONTRAT.exemple.ecran, lead_id: CONTRAT.exemple.lead_id,
        question: CONTRAT.exemple.question, envoyer: true },
    }))
    await screen.findByText(CONTRAT.exemple.resume_reponse)
    expect(store.getState().ia.copilotOpen).toBe(true)
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      CONTRAT.exemple.question,
      { ...CONTEXTE_VIDE, ecran: CONTRAT.exemple.ecran, lead_id: CONTRAT.exemple.lead_id }, expect.any(String))
  })

  it('sans événement, le contexte est la route courante (lead null)', async () => {
    const user = userEvent.setup()
    monter()
    await poserUneQuestion(user)
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      CONTRAT.exemple.question, { ...CONTEXTE_VIDE, ecran: window.location.pathname }, expect.any(String))
  })

  it('affiche les trois questions du manifeste pour l\'écran', async () => {
    iaApi.getSuggestions.mockResolvedValue({ data: ['Q1 du lead ?', 'Q2 du lead ?', 'Q3 du lead ?'] })
    monter()
    await screen.findByRole('button', { name: 'Q1 du lead ?' })
    expect(screen.getByRole('button', { name: 'Q3 du lead ?' })).toBeTruthy()
    expect(iaApi.getSuggestions).toHaveBeenCalledWith(window.location.pathname)
  })
})

describe('CopilotPanel — contexte lu à l\'envoi (COP-F5)', () => {
  it('le contexte d\'un événement ne vaut que pour SA question : la suivante repart de la route', async () => {
    const user = userEvent.setup()
    monter({ ouvert: false })
    window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, {
      detail: { ecran: '/crm/leads/12', lead_id: 12, question: 'Résume ce lead', envoyer: true },
    }))
    await screen.findByText(CONTRAT.exemple.resume_reponse)
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      'Résume ce lead', { ...CONTEXTE_VIDE, ecran: '/crm/leads/12', lead_id: 12 }, expect.any(String))
    await user.type(screen.getByPlaceholderText(/Posez votre question/), 'Et le stock ?')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    await waitFor(() => expect(iaApi.queryAgent).toHaveBeenCalledTimes(2))
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      'Et le stock ?', { ...CONTEXTE_VIDE, ecran: window.location.pathname }, expect.any(String))
  })

  it('PREMIER clic : une demande émise AVANT le montage du panneau ouvre le tiroir et envoie', async () => {
    const initial = iaReducer(undefined, { type: '@@init' })
    const store = configureStore({ reducer: { ia: iaReducer }, preloadedState: { ia: initial } })
    installerEcouteurOuverture(() => Promise.resolve({ store }))
    window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, {
      detail: { ecran: '/crm/leads/7', lead_id: 7, question: 'Résume ce lead', envoyer: true },
    }))
    await waitFor(() => expect(store.getState().ia.copilotOpen).toBe(true))
    // Le panneau (lazy dans l'app) se monte APRÈS : il reprend la demande en attente.
    render(<Provider store={store}><CopilotPanel /></Provider>)
    await screen.findByText(CONTRAT.exemple.resume_reponse)
    expect(iaApi.queryAgent).toHaveBeenCalledTimes(1)
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      'Résume ce lead', { ...CONTEXTE_VIDE, ecran: '/crm/leads/7', lead_id: 7 }, expect.any(String))
  })
})

describe('CopilotPanel — « Signaler un bug » (COP-F7)', () => {
  it('une phrase libre part avec le tampon technique dans contexte.diagnostic', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByRole('button', { name: 'Signaler un bug' }))
    await user.type(screen.getByLabelText('Que faisiez-vous ?'), 'Je cliquais sur Fait')
    await user.click(screen.getByRole('button', { name: 'Envoyer le signalement' }))
    await waitFor(() => expect(iaApi.queryAgent).toHaveBeenCalledTimes(1))
    const [question, contexte] = iaApi.queryAgent.mock.calls[0]
    expect(question).toBe('Signaler un bug : Je cliquais sur Fait')
    expect(Array.isArray(contexte.diagnostic.requetes)).toBe(true)
    expect(Array.isArray(contexte.diagnostic.erreurs)).toBe(true)
  })

  it('le même tampon part tout seul quand le message dit une panne, jamais sinon', async () => {
    const user = userEvent.setup()
    monter()
    await user.type(screen.getByPlaceholderText(/Posez votre question/), 'Le bouton Fait ne marche pas')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    await waitFor(() => expect(iaApi.queryAgent).toHaveBeenCalledTimes(1))
    expect(iaApi.queryAgent.mock.calls[0][1].diagnostic).not.toBeNull()
    await screen.findByText(CONTRAT.exemple.resume_reponse)
    await user.type(screen.getByPlaceholderText(/Posez votre question/), 'Combien de leads aujourd\'hui ?')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    await waitFor(() => expect(iaApi.queryAgent).toHaveBeenCalledTimes(2))
    expect(iaApi.queryAgent.mock.calls[1][1].diagnostic).toBeNull()
  })
})

describe('CopilotPanel — les quatre demandes prêtes de Tâches (A12, TCH118)', () => {
  const contrat = (nom) => ({ data: structuredClone(exempleContrat('taches', nom)) })
  const DEMANDES = ['Planifie ma journée', 'Aide-moi à prioriser', 'Range ma liste', 'Où j\'en suis ?']

  function monterAvecDroits(permissions) {
    const initial = iaReducer(undefined, { type: '@@init' })
    const store = configureStore({
      reducer: { ia: iaReducer, auth: (etat = { permissions }) => etat },
      preloadedState: { ia: { ...initial, copilotOpen: true } },
    })
    render(<Provider store={store}><MemoryRouter><CopilotPanel /></MemoryRouter></Provider>)
    return store
  }

  beforeEach(() => {
    vi.clearAllMocks() // appels comptés par test (les réponses posées plus haut restent)
    tachesApi.proposerJournee.mockResolvedValue(contrat('journee_proposition'))
    tachesApi.lirePriorites.mockResolvedValue(contrat('priorites'))
    tachesApi.lirePoint.mockResolvedValue(contrat('point'))
    tachesApi.saisieRapide.mockResolvedValue(contrat('saisie_apercu'))
    tachesApi.listerToutesLesTaches.mockResolvedValue([exempleContrat('taches', 'tache')])
    tachesApi.lireAujourdhui.mockResolvedValue(contrat('aujourdhui'))
    iaApi.getSuggestions.mockRejectedValue(new Error('service IA injoignable'))
  })

  // F3 acceptation ERR 3 — textes du panneau ouvert depuis un écran Tâches (textes.md §5.2), mot pour mot.
  it('ERR 3 — sur /taches : sous-titre « ouvert depuis {écran} » et champ « Écris ou dicte… »', async () => {
    window.history.pushState({}, '', '/taches/a-trier')
    monterAvecDroits(['taches_voir'])
    await screen.findByRole('group', { name: 'Demandes prêtes' })
    expect(screen.getByText('ouvert depuis À trier')).toBeTruthy()
    expect(screen.getByPlaceholderText('Écris ou dicte…')).toBeTruthy()
    expect(screen.queryByText(/Posez une question sur vos données/)).toBeNull()
  })

  it('ERR 3 — hors /taches, rien ne change (sous-titre et champ de l’ERP)', async () => {
    window.history.pushState({}, '', '/crm/relances')
    iaApi.getSuggestions.mockResolvedValue({ data: ['Q1 ?'] })
    monterAvecDroits(['taches_voir'])
    await screen.findByRole('button', { name: 'Q1 ?' })
    expect(screen.getByText('Posez une question sur vos données — réponses en temps réel.')).toBeTruthy()
    expect(screen.getByPlaceholderText('Posez votre question en français…')).toBeTruthy()
    expect(screen.queryByText(/ouvert depuis/)).toBeNull()
  })

  it('ERR 3 — « Planifie ma journée » répond « Tu as gardé {e} essentielles… » avec les nombres du serveur', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    const user = userEvent.setup()
    const store = monterAvecDroits(['taches_voir'])
    await user.click(screen.getByRole('button', { name: 'Planifie ma journée' }))
    await screen.findByTestId('carte-taches-plan_propose')
    // aujourdhui.json : essentiel_prevues 1 ; journee_proposition.json : objectif 5, 2 lignes.
    const attendu = 'Tu as gardé 1 essentielle. Pour atteindre 5, voici 2 tâches de plus, dans cet ordre. '
      + 'Rien ne change tant que tu ne gardes pas.'
    expect(store.getState().ia.messages[1].content).toBe(attendu)
    expect(screen.getByText(attendu)).toBeTruthy()
  })

  it('ERR 3 — sans clé d’IA, la ligne « Écris ou dicte… » devient la phrase de §5.2 ; hors /taches rien ne change', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    iaApi.queryAgent.mockResolvedValue({ data: {
      answer: "L'assistant n'est pas disponible pour le moment (réglage du serveur). Le problème est signalé à "
        + "l'administrateur ; réessaie plus tard.", evenement_id: null } })
    const user = userEvent.setup()
    monterAvecDroits(['taches_voir'])
    await user.type(screen.getByPlaceholderText('Écris ou dicte…'), 'bonjour')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    expect(await screen.findByText(
      "La conversation libre n'est pas branchée sur ce serveur. Les quatre demandes ci-dessus marchent sans elle.",
    )).toBeTruthy()
    expect(screen.queryByPlaceholderText('Écris ou dicte…')).toBeNull()
    for (const q of DEMANDES) expect(screen.getByRole('button', { name: q })).toBeTruthy()
  })

  afterEach(() => { window.history.pushState({}, '', '/') })

  it('sur /taches, les quatre demandes sont là même si le service d\'IA ne répond pas', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    monterAvecDroits(['taches_voir'])
    const liste = await screen.findByRole('group', { name: 'Demandes prêtes' })
    for (const q of DEMANDES) expect(within(liste).getByRole('button', { name: q })).toBeTruthy()
    expect(iaApi.getSuggestions).not.toHaveBeenCalled()
  })

  it('« Aide-moi à prioriser » appelle la route déterministe et rend la carte, sans modèle', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    const user = userEvent.setup()
    const store = monterAvecDroits(['taches_voir'])
    await user.click(screen.getByRole('button', { name: 'Aide-moi à prioriser' }))
    await screen.findByTestId('carte-taches-priorites')
    expect(tachesApi.lirePriorites).toHaveBeenCalledTimes(1)
    expect(iaApi.queryAgent).not.toHaveBeenCalled()
    const [question, reponse] = store.getState().ia.messages
    expect(question).toEqual({ role: 'user', content: 'Aide-moi à prioriser' })
    expect(reponse.cartes[0].donnees).toEqual(exempleContrat('taches', 'priorites'))
  })

  it('« Range ma liste » range les ids À trier lus à l\'API Tâches (jamais devinés)', async () => {
    window.history.pushState({}, '', '/taches/a-trier')
    const user = userEvent.setup()
    monterAvecDroits(['taches_voir'])
    await user.click(screen.getByRole('button', { name: 'Range ma liste' }))
    await screen.findByTestId('carte-taches-capture_apercu')
    expect(tachesApi.listerToutesLesTaches).toHaveBeenCalledWith({ vue: 'boite' })
    expect(tachesApi.saisieRapide).toHaveBeenCalledWith({
      ids: [exempleContrat('taches', 'tache').id], apercu: true })
    expect(iaApi.queryAgent).not.toHaveBeenCalled()
  })

  it('« Range ma liste » sans tâche À trier : « Rien à trier », aucun aperçu', async () => {
    window.history.pushState({}, '', '/taches/a-trier')
    tachesApi.listerToutesLesTaches.mockResolvedValue([])
    const user = userEvent.setup()
    monterAvecDroits(['taches_voir'])
    await user.click(screen.getByRole('button', { name: 'Range ma liste' }))
    await screen.findByText('Rien à trier')
    expect(tachesApi.saisieRapide).not.toHaveBeenCalled()
  })

  it('hors /taches : comportement identique (pas de demandes prêtes, suggestions du manifeste)', async () => {
    window.history.pushState({}, '', '/crm/relances')
    iaApi.getSuggestions.mockResolvedValue({ data: ['Q1 ?', 'Q2 ?', 'Q3 ?'] })
    monterAvecDroits(['taches_voir'])
    await screen.findByRole('button', { name: 'Q1 ?' })
    expect(iaApi.getSuggestions).toHaveBeenCalledWith('/crm/relances')
    expect(screen.queryByRole('group', { name: 'Demandes prêtes' })).toBeNull()
  })

  // Passe visuelle n° 49 — ouvert depuis Tâches : logo ✦, demandes en puces `.ep-demandes` (l'envoyée marquée), et ni
  // l'accueil ni les questions de l'assistant ERP (« Quels produits sont en rupture de stock ? »…).
  it('n° 49 — sur /taches : demandes en puces de la maquette, aucune suggestion de l’assistant ERP', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    const user = userEvent.setup()
    monterAvecDroits(['taches_voir'])
    const liste = await screen.findByRole('group', { name: 'Demandes prêtes' })
    expect(liste.className).toBe('ep-demandes')
    expect(liste.closest('.tch')).not.toBeNull()
    expect(document.querySelector('[data-logo="copilote-taches"]')).not.toBeNull()
    expect(screen.queryByText('Quels produits sont en rupture de stock ?')).toBeNull()
    expect(screen.queryByText('Comment puis-je aider ?')).toBeNull()
    expect(screen.queryByText(/L'agent analyse votre base de données/)).toBeNull()
    await user.click(within(liste).getByRole('button', { name: 'Où j\'en suis ?' }))
    await screen.findByTestId('carte-taches-point')
    expect(within(liste).getByRole('button', { name: 'Où j\'en suis ?' }).className).toBe('envoyee')
    expect(within(liste).getByRole('button', { name: 'Planifie ma journée' }).className).toBe('')
  })

  it('n° 49 — hors /taches, le panneau de l’ERP ne change pas (logo, accueil, suggestions par défaut)', async () => {
    window.history.pushState({}, '', '/crm/relances')
    iaApi.getSuggestions.mockResolvedValue({ data: [] })
    monterAvecDroits(['taches_voir'])
    await screen.findByText('Comment puis-je aider ?')
    expect(screen.getByText("L'agent analyse votre base de données et répond en français.")).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Quels produits sont en rupture de stock ?' })).toBeTruthy()
    expect(document.querySelector('[data-logo="copilote-taches"]')).toBeNull()
    expect(document.querySelector('.ep-demandes')).toBeNull()
  })

  // Passe visuelle n° 50 — une carte Tâches dans le tiroir ouvert depuis Tâches : UNE carte pleine largeur (ni bulle
  // grise, ni cadre ambre autour), la question dans la bulle d'accent, la réponse en texte simple.
  it('n° 50 — sur /taches : la carte n’est prise ni dans une bulle ni dans un cadre', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    const user = userEvent.setup()
    monterAvecDroits(['taches_voir'])
    await user.click(screen.getByRole('button', { name: 'Planifie ma journée' }))
    const carte = await screen.findByTestId('carte-taches-plan_propose')
    const cadre = carte.parentElement
    expect(cadre.dataset.cadre).toBe('attente')
    expect(cadre.className).toBe('mt-2')
    expect(carte.closest('.bg-muted')).toBeNull()
    expect(carte.closest('[class*="max-w-"]')).toBeNull()
    expect(screen.getByText('Planifie ma journée', { selector: 'p' })).toHaveClass('ep-bulle-moi')
    expect(screen.getByText(/Rien ne change tant que tu ne gardes pas\.$/)).toHaveClass('ep-bulle-ia')
  })

  it('n° 50 — hors /taches, la même carte garde sa bulle et son cadre « proposition » (ambre)', async () => {
    window.history.pushState({}, '', '/crm/relances')
    const initial = iaReducer(undefined, { type: '@@init' })
    const store = configureStore({
      reducer: { ia: iaReducer, auth: (etat = { permissions: ['taches_voir'] }) => etat },
      preloadedState: { ia: { ...initial, copilotOpen: true, messages: [{ role: 'agent', content: 'Voici.', cartes: [
        { type: 'resultat', carte: 'plan_propose', donnees: exempleContrat('taches', 'journee_proposition') }] }] } },
    })
    render(<Provider store={store}><MemoryRouter><CopilotPanel /></MemoryRouter></Provider>)
    const carte = await screen.findByTestId('carte-taches-plan_propose')
    expect(carte.parentElement.className).toMatch(/amber/)
    expect(carte.closest('.bg-muted')).not.toBeNull()
    expect(screen.getByText('Voici.')).not.toHaveClass('ep-bulle-ia')
  })

  it('sur /taches sans le droit taches_voir : pas de demandes prêtes', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    iaApi.getSuggestions.mockResolvedValue({ data: ['Q1 ?'] })
    monterAvecDroits(['crm_voir'])
    await screen.findByRole('button', { name: 'Q1 ?' })
    expect(screen.queryByRole('group', { name: 'Demandes prêtes' })).toBeNull()
  })
})

/* COP2-W2 — longueur maximale lue chez le serveur, compteur, images jointes. Les capacités viennent de
   `iaApi.getCapacitesAssistant` (GET /sql-agent/capacites) ; absentes ou en échec : 2000 caractères, pas d'image. */
describe('CopilotPanel — limite de question et images jointes (COP2-W2)', () => {
  const capacites = (c) => iaApi.getCapacitesAssistant.mockResolvedValue({ data: c })
  const champ = () => screen.getByPlaceholderText(/Posez votre question/)
  const png = (nom = 'capture.png') => new File(['x'], nom, { type: 'image/png' })
  const reduite = (data) => ({ media_type: 'image/jpeg', data, apercu: `blob:${data}` })

  afterEach(() => { vi.mocked(reduireImage).mockClear() })

  it('compteur : invisible loin de la limite, visible près d\'elle, rouge au-delà ; la limite vient du serveur', async () => {
    capacites({ limite_question: 100, images_acceptees: false })
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(iaApi.getCapacitesAssistant).toHaveBeenCalledTimes(1))
    await user.click(champ())
    await user.paste('a'.repeat(50))
    expect(screen.queryByTestId('compteur-question')).toBeNull()
    await user.paste('a'.repeat(35))
    await waitFor(() => expect(screen.getByTestId('compteur-question')).toHaveTextContent('85 / 100'))
    await user.paste('a'.repeat(16))
    expect(screen.getByTestId('compteur-question')).toHaveTextContent('Trop long : 101 / 100 caractères.')
    expect(screen.getByRole('button', { name: 'Envoyer' })).toBeDisabled()
  })

  it('une question trop longue n\'est ni envoyée ni effacée (Entrée)', async () => {
    capacites({ limite_question: 100, images_acceptees: false })
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(iaApi.getCapacitesAssistant).toHaveBeenCalled())
    await user.click(champ())
    await user.paste('b'.repeat(101))
    await user.keyboard('{Enter}')
    expect(iaApi.queryAgent).not.toHaveBeenCalled()
    expect(champ()).toHaveValue('b'.repeat(101))
  })

  it('sans réponse du serveur (route absente), la limite par défaut est 2000 et aucune image n\'est proposée', async () => {
    iaApi.getCapacitesAssistant.mockRejectedValue(new Error('404'))
    const user = userEvent.setup()
    monter()
    await waitFor(() => expect(iaApi.getCapacitesAssistant).toHaveBeenCalled())
    await user.click(champ())
    await user.paste('c'.repeat(1700))
    expect(screen.getByTestId('compteur-question')).toHaveTextContent('1700 / 2000')
    expect(screen.queryByRole('button', { name: 'Joindre une image' })).toBeNull()
  })

  it('le bouton « Joindre une image » n\'existe que si le serveur accepte les images', async () => {
    capacites({ limite_question: 6000, images_acceptees: true })
    monter()
    expect(await screen.findByRole('button', { name: 'Joindre une image' })).toBeInTheDocument()
    expect(screen.getByTestId('images-input')).toHaveAttribute('accept', 'image/*')
    expect(screen.getByTestId('images-input')).toHaveAttribute('multiple')
  })

  it('image jointe : miniature, avertissement, envoi `images` sans l\'aperçu, magasin sans base64, « [image jointe] »', async () => {
    capacites({ limite_question: 6000, images_acceptees: true })
    vi.mocked(reduireImage).mockResolvedValueOnce(reduite('QUJD'))
    const user = userEvent.setup()
    const store = monter()
    await screen.findByRole('button', { name: 'Joindre une image' })
    await user.upload(screen.getByTestId('images-input'), png())
    expect(await screen.findByAltText('Image jointe 1')).toBeInTheDocument()
    expect(screen.getByTestId('images-avertissement')).toHaveTextContent('Jamais de facture ni de pièce d\'identité.')
    await user.type(champ(), 'Prépare-lui un devis')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    await screen.findByText('[image jointe]')
    expect(iaApi.queryAgent).toHaveBeenCalledTimes(1)
    const [question, , , images] = iaApi.queryAgent.mock.calls[0]
    expect(question).toBe('Prépare-lui un devis')
    expect(images).toEqual([{ media_type: 'image/jpeg', data: 'QUJD' }])
    // Le magasin ne garde que le nombre : ni le base64, ni l'URL d'objet.
    const etat = JSON.stringify(store.getState().ia)
    expect(etat).not.toContain('QUJD')
    expect(etat).not.toContain('blob:')
    expect(store.getState().ia.messages[0]).toMatchObject({ role: 'user', images_jointes: 1 })
    // La saisie est vidée : plus de miniature ni d'avertissement.
    expect(screen.queryByAltText('Image jointe 1')).toBeNull()
    expect(screen.queryByTestId('images-avertissement')).toBeNull()
  })

  it('sans image, la requête garde sa forme d\'avant (trois arguments, aucune clé `images`)', async () => {
    capacites({ limite_question: 6000, images_acceptees: true })
    const user = userEvent.setup()
    monter()
    await screen.findByRole('button', { name: 'Joindre une image' })
    await user.type(champ(), 'Bonjour')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    await waitFor(() => expect(iaApi.queryAgent).toHaveBeenCalledTimes(1))
    expect(iaApi.queryAgent.mock.calls[0]).toHaveLength(3)
  })

  it('retirer une miniature la supprime ; trois images au plus', async () => {
    capacites({ limite_question: 6000, images_acceptees: true })
    vi.mocked(reduireImage)
      .mockResolvedValueOnce(reduite('A')).mockResolvedValueOnce(reduite('B'))
      .mockResolvedValueOnce(reduite('C')).mockResolvedValueOnce(reduite('D'))
    const user = userEvent.setup()
    monter()
    await screen.findByRole('button', { name: 'Joindre une image' })
    await user.upload(screen.getByTestId('images-input'), [png('1.png'), png('2.png'), png('3.png'), png('4.png')])
    await waitFor(() => expect(screen.getAllByRole('img')).toHaveLength(3))
    expect(screen.getByTestId('images-erreur')).toHaveTextContent('3 images au maximum.')
    expect(screen.getByRole('button', { name: 'Joindre une image' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Retirer l\'image 2' }))
    expect(screen.getAllByRole('img')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Joindre une image' })).toBeEnabled()
  })

  it('un fichier qui n\'est pas une image est refusé avec une phrase', async () => {
    capacites({ limite_question: 6000, images_acceptees: true })
    const user = userEvent.setup({ applyAccept: false })
    monter()
    await screen.findByRole('button', { name: 'Joindre une image' })
    await user.upload(screen.getByTestId('images-input'), new File(['x'], 'note.pdf', { type: 'application/pdf' }))
    expect(await screen.findByTestId('images-erreur')).toHaveTextContent('Seules les images sont acceptées.')
    expect(reduireImage).not.toHaveBeenCalled()
  })

  it('coller une image dans le champ la joint ; coller du texte reste un collage normal', async () => {
    capacites({ limite_question: 6000, images_acceptees: true })
    vi.mocked(reduireImage).mockResolvedValueOnce(reduite('P'))
    const user = userEvent.setup()
    monter()
    await screen.findByRole('button', { name: 'Joindre une image' })
    fireEvent.paste(champ(), { clipboardData: { files: [png('colle.png')], getData: () => '' } })
    expect(await screen.findByAltText('Image jointe 1')).toBeInTheDocument()
    await user.click(champ())
    await user.paste('du texte')
    expect(champ()).toHaveValue('du texte')
    expect(reduireImage).toHaveBeenCalledTimes(1)
  })

  describe('réduction réelle (Image + canvas simulés)', () => {
    let vraie
    let appels
    let contexte
    const AncienneImage = globalThis.Image
    const ancienGetContext = HTMLCanvasElement.prototype.getContext
    const ancienToDataURL = HTMLCanvasElement.prototype.toDataURL

    beforeEach(async () => {
      vraie = (await vi.importActual('./images')).reduireImage
      appels = []
      contexte = { fillRect: vi.fn(), drawImage: vi.fn(), fillStyle: '' }
      URL.createObjectURL = vi.fn(() => 'blob:apercu')
      URL.revokeObjectURL = vi.fn()
      globalThis.Image = class {
        constructor() { this.naturalWidth = 4000; this.naturalHeight = 3000 }
        set src(v) { this._src = v; queueMicrotask(() => this.onload?.()) }
      }
      HTMLCanvasElement.prototype.getContext = () => contexte
    })
    afterEach(() => {
      globalThis.Image = AncienneImage
      HTMLCanvasElement.prototype.getContext = ancienGetContext
      HTMLCanvasElement.prototype.toDataURL = ancienToDataURL
      delete URL.createObjectURL
      delete URL.revokeObjectURL
    })

    it('4000×3000 → 1280×960, JPEG qualité 0,8, base64 SANS préfixe data:', async () => {
      HTMLCanvasElement.prototype.toDataURL = function (type, qualite) {
        appels.push([this.width, this.height, type, qualite])
        return 'data:image/jpeg;base64,QUJD'
      }
      const r = await vraie(png())
      expect(appels).toEqual([[1280, 960, 'image/jpeg', 0.8]])
      expect(r).toEqual({ media_type: 'image/jpeg', data: 'QUJD', apercu: 'blob:apercu' })
      expect(contexte.drawImage).toHaveBeenCalledWith(expect.anything(), 0, 0, 1280, 960)
    })

    it('trop lourde à 0,8 : qualité réduite ; toujours trop lourde : refusée et l\'URL d\'objet révoquée', async () => {
      const lourde = `data:image/jpeg;base64,${'A'.repeat(1900001)}`
      HTMLCanvasElement.prototype.toDataURL = (type, qualite) => { appels.push(qualite); return qualite > 0.7 ? lourde : 'data:image/jpeg;base64,PETIT' }
      expect((await vraie(png())).data).toBe('PETIT')
      expect(appels).toEqual([0.8, 0.6])
      HTMLCanvasElement.prototype.toDataURL = () => lourde
      await expect(vraie(png())).rejects.toThrow('image trop lourde')
      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:apercu')
    })
  })

  it('un message d\'historique qui portait une image montre « [image jointe] »', async () => {
    const initial = iaReducer(undefined, { type: '@@init' })
    const store = configureStore({
      reducer: { ia: iaReducer },
      preloadedState: { ia: { ...initial, copilotOpen: true, messages: [
        { role: 'user', content: 'Prépare-lui un devis', images_jointes: 1 },
        { role: 'user', content: 'Et celle-ci', images_jointes: 2 },
      ] } },
    })
    render(<Provider store={store}><CopilotPanel /></Provider>)
    expect(await screen.findByText('[image jointe]')).toBeInTheDocument()
    expect(screen.getByText('[2 images jointes]')).toBeInTheDocument()
  })
})
