import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider, useSelector } from 'react-redux'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { documentContrat, exempleContrat } from '../../../test/fixtures/contractSamples'

/* NOUVEAU FICHIER DE TEST : aucun module de test n'héberge les cartes de
   l'assistant (`features/ia/cartes/` est neuf). Chaque carte est rendue avec
   l'ÉCHANTILLON COMMITTÉ de son contrat (PACT10/PACT13), jamais une charge utile
   tapée à la main : si le serveur change de forme, ce test casse tout seul. */

vi.mock('../../../api/iaApi', () => ({
  default: {
    getToucheAssistant: vi.fn(),
    getFileTouchesAssistant: vi.fn(),
    queryAgent: vi.fn(),
  },
}))
vi.mock('../../../api/ventesApi', () => ({
  default: { getProposalPdf: vi.fn(() => Promise.resolve({ data: new Blob(['%PDF']), headers: {} })) },
}))
vi.mock('../../../api/crmApi', () => ({
  default: {
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    whatsappDevis: vi.fn(() => Promise.resolve({ data: {} })),
    whatsappDevisApercu: vi.fn(),
  },
}))
vi.mock('../../../utils/downloadBlob', () => ({
  downloadBlobInGesture: vi.fn(() => ({ win: null, deliver: vi.fn() })),
  filenameFromResponse: vi.fn((res, repli) => repli),
}))

import iaApi from '../../../api/iaApi'
import ventesApi from '../../../api/ventesApi'
import crmApi from '../../../api/crmApi'
import { downloadBlobInGesture } from '../../../utils/downloadBlob'
import iaReducer from '../store/iaSlice'
import CartesDuMessage from './CartesDuMessage'
import {
  preparerCartes, messageDeReponse, etatAffiche, foyerTouche, lienWhatsAppSur, idDevisSur, ETATS,
} from './cartes'
import { texteDiagnostic } from './diagnosticTexte'

const REPONSE = documentContrat('agent', 'assistant_reponse')
const touche = (nom, variante = 'exemple') => exempleContrat('crm', nom, variante)

function resultat(carte, donnees, extra = {}) {
  return { type: 'resultat', action_key: `test.${carte}`, libelle: carte, carte, donnees, ...extra }
}

// Le message vit DANS le store (comme dans l'app : le parent le lit du store) —
// les patchs d'état d'une carte (`majCarte`) se voient donc à l'écran.
function Vue() {
  const msg = useSelector((s) => s.ia.messages[0])
  return <CartesDuMessage msg={msg} index={0} variant="page" />
}

function Route() {
  return <span data-testid="route">{useLocation().pathname}</span>
}

function monter(cartes, { recuLe = Date.now(), copilotOpen = false } = {}) {
  const initial = iaReducer(undefined, { type: '@@init' })
  const msg = { role: 'agent', content: '', cartes: preparerCartes(cartes, { recuLe }) }
  const store = configureStore({
    reducer: { ia: iaReducer }, preloadedState: { ia: { ...initial, messages: [msg], copilotOpen } },
  })
  const vue = render(
    <Provider store={store}>
      <MemoryRouter><Vue /><Route /></MemoryRouter>
    </Provider>,
  )
  return { store, ...vue }
}

beforeEach(() => {
  vi.clearAllMocks()
  window.open = vi.fn()
})

describe('cartes — tout échantillon du contrat rend sans erreur', () => {
  it('l\'exemple de la réponse (carte touche) et les deux propositions du contrat', () => {
    const msg = messageDeReponse(REPONSE.exemple)
    expect(msg.cartes).toHaveLength(1)
    const deux = messageDeReponse(REPONSE.exemple_deux_propositions)
    expect(deux.cartes.map((c) => c.type)).toEqual(['proposition', 'proposition'])
    expect(deux.cartes[0].apercu).toMatch(/DEV-202611-0045/)
  })

  it.each([
    ['exemple', /Aziz Benali/],
    ['exemple_appel', /Salma Idrissi/],
    ['exemple_proposition', /Enregistrer : Salma Idrissi/],
    ['exemple_proposition_refusee', /Date de rappel passée/],
  ])('touche — %s', (variante, motif) => {
    monter([resultat('touche', touche('assistant_touche', variante))])
    expect(screen.getAllByText(motif).length).toBeGreaterThan(0)
  })

  it('touche — refus : le détail, aucun bouton d\'ouverture', () => {
    monter([resultat('touche', touche('assistant_touche', 'exemple_refus'))])
    expect(screen.getByTestId('touche-refus')).toHaveTextContent(/plus être contacté/)
    expect(screen.queryByRole('button', { name: /WhatsApp/ })).not.toBeInTheDocument()
  })

  it('« Ouvrir la fiche » mène à la fiche ET referme le tiroir (modal, plein écran sur téléphone)', async () => {
    const { store } = monter([resultat('file_touches', touche('assistant_a_relancer'))], { copilotOpen: true })
    expect(store.getState().ia.copilotOpen).toBe(true)
    await userEvent.click(screen.getAllByRole('button', { name: 'Ouvrir la fiche' })[0])
    expect(screen.getByTestId('route')).toHaveTextContent(/^\/crm\/leads\/\d+$/)
    expect(store.getState().ia.copilotOpen).toBe(false)
  })

  it('file de touches : une rangée par touche, « Préparer » quand elle porte un touche_id', () => {
    monter([resultat('file_touches', touche('assistant_a_relancer'))])
    expect(screen.getByText(/Aziz Benali — Relance J\+1/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Préparer' })).toHaveLength(2)
    expect(screen.getAllByRole('button', { name: 'Ouvrir la fiche' })).toHaveLength(2)
    // Libellé d'étape par la constante du front, pas la clé brute.
    expect(screen.getByText(/Devis envoyé · prévue le/)).toBeInTheDocument()
  })

  it('file vide', () => {
    monter([resultat('file_touches', touche('assistant_a_relancer', 'exemple_vide'))])
    expect(screen.getByText(/Rien à relancer/)).toBeInTheDocument()
  })

  it('matin : relances, visites et devis sans réponse (avec Télécharger)', () => {
    monter([resultat('matin', touche('assistant_digest_matin'))])
    expect(screen.getByText('Votre matin')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Préparer' })).toBeInTheDocument()
    expect(screen.getByText(/DEV-202611-0045 — Benali/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Télécharger' })).toBeInTheDocument()
  })

  it('matin sans CRM', () => {
    monter([resultat('matin', touche('assistant_digest_matin', 'exemple_sans_crm'))])
    expect(screen.getByText('Votre matin')).toBeInTheDocument()
  })

  it('recherche de leads : « Préparer » seulement quand une touche est ouverte', () => {
    monter([resultat('liste_leads', touche('assistant_leads_recherche'))])
    expect(screen.getByText('Karim Alami')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Préparer' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: 'Ouvrir la fiche' })).toHaveLength(2)
  })

  it('recherche sans résultat', () => {
    monter([resultat('liste_leads', touche('assistant_leads_recherche', 'exemple_aucun'))])
    expect(screen.getByText('Aucun lead trouvé.')).toBeInTheDocument()
  })

  it('fiche lead : devis téléchargeable, étape libellée, prochaine touche préparable', () => {
    monter([resultat('fiche_lead', touche('assistant_lead_resume'))])
    expect(screen.getByText(/Aziz Benali/)).toBeInTheDocument()
    expect(screen.getByText(/Devis envoyé/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Télécharger' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Préparer' })).toBeInTheDocument()
  })

  it('fiche sans touche ni devis', () => {
    monter([resultat('fiche_lead', touche('assistant_lead_resume', 'exemple_sans_touche'))])
    expect(screen.queryByRole('button', { name: 'Préparer' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Télécharger' })).not.toBeInTheDocument()
  })

  it('suite de touche : la prochaine touche du lead', () => {
    const doc = documentContrat('crm', 'relance_etape_v2').exemple.results[0]
    monter([resultat('suite_touche', { ...doc, prochaine_touche: { libelle: 'Relance J+3', due_date: '2026-11-16' } })])
    expect(screen.getByText(/Prochaine touche : Relance J\+3/)).toBeInTheDocument()
  })

  it('visite planifiée', () => {
    monter([resultat('visite', touche('lead_visite_planifier'))])
    expect(screen.getByText(/Visite \(brouillon\)/)).toBeInTheDocument()
    expect(screen.getByText(/Youssef Alami/)).toBeInTheDocument()
  })

  it('diagnostic : résumé lisible', () => {
    monter([resultat('diagnostic', exempleContrat('reporting', 'assistant_diagnostic'))])
    expect(screen.getByText(/Diagnostic/)).toBeInTheDocument()
    expect(screen.getByText(/replace-lines/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Copier pour Claude Code/ })).toBeInTheDocument()
  })

  it('carte inconnue ou null : carte générique « Action effectuée »', () => {
    monter([resultat(null, { reference: 'X-1' }), resultat('carte_future', { reference: 'Y-2' })])
    expect(screen.getAllByText('Action effectuée')).toHaveLength(2)
    expect(screen.getByText(/X-1/)).toBeInTheDocument()
  })
})

describe('cartes — WhatsApp et documents (COP-F4)', () => {
  it('wa_message : texte visible et « Ouvrir WhatsApp » ; sans texte, « Ouvrir la conversation »', () => {
    const doc = documentContrat('crm', 'assistant_brouillon_suivi')
    const { unmount } = monter([resultat('wa_message', doc.exemple)])
    expect(screen.getByTestId('wa-texte')).toHaveTextContent(/C'est Meryem de TAQINOR/)
    expect(screen.getByRole('link', { name: /Ouvrir WhatsApp/ }))
      .toHaveAttribute('href', 'https://wa.me/212651971400?text=Bonjour%20M.%20Benali')
    unmount()
    monter([resultat('wa_message', doc.exemple_sans_modele)])
    expect(screen.queryByTestId('wa-texte')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ouvrir la conversation' })).toHaveAttribute('href', 'https://wa.me/212651971400')
  })

  it('wa_message : un lien hors wa.me / api.whatsapp.com n\'est jamais ouvert', () => {
    monter([resultat('wa_message', { texte: 'Bonjour', wa_url: 'https://evil.example/x' })])
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText(/Aucun numéro exploitable/)).toBeInTheDocument()
  })

  it('document : télécharge via /proposal authentifié (blob), avec ses options', async () => {
    const doc = documentContrat('agent', 'assistant_document')
    monter([resultat('document', doc.exemple_options)])
    await userEvent.click(screen.getByRole('button', { name: 'Télécharger le devis' }))
    expect(downloadBlobInGesture).toHaveBeenCalled()
    await waitFor(() => expect(ventesApi.getProposalPdf).toHaveBeenCalledWith(45, { pdf_mode: 'onepage' }))
  })

  it('document sans devis_id entier : aucun bouton', () => {
    monter([resultat('document', { devis_id: 'abc', url: '/api/django/ventes/devis/abc/proposal/' })])
    expect(screen.queryByRole('button', { name: /Télécharger/ })).not.toBeInTheDocument()
  })

  it('wa_devis : ouvre WhatsApp PUIS enregistre l\'envoi (commit), une seule fois', async () => {
    const apercu = exempleContrat('crm', 'whatsapp_devis_apercu')
    monter([resultat('wa_devis', { ...apercu, lead_id: 9, devis_ids: [413, 414] })])
    expect(screen.getByTestId('wa-texte')).toHaveTextContent(/DEV-202609-0012/)
    await userEvent.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    expect(window.open).toHaveBeenCalledWith('https://wa.me/212612345678?text=Bonjour%20Amina', '_blank', 'noopener')
    await waitFor(() => expect(crmApi.whatsappDevis).toHaveBeenCalledWith(9, { devis_ids: [413, 414] }))
    expect(crmApi.whatsappDevis).toHaveBeenCalledTimes(1)
    expect(await screen.findByTestId('wa-devis-envoye')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Ouvrir WhatsApp/ })).not.toBeInTheDocument()
  })

  it('wa_devis ancien : revalidé par un nouvel aperçu AVANT d\'ouvrir (la remise a pu changer)', async () => {
    const apercu = exempleContrat('crm', 'whatsapp_devis_apercu')
    crmApi.whatsappDevisApercu.mockResolvedValue({ data: { ...apercu, message: 'Texte à jour.' } })
    monter([resultat('wa_devis', { ...apercu, lead_id: 9, devis_ids: [413] })], { recuLe: Date.now() - 10 * 60 * 1000 })
    await waitFor(() => expect(crmApi.whatsappDevisApercu).toHaveBeenCalledWith(9, { devis_ids: [413] }))
    await screen.findByText('Texte à jour.')
    expect(window.open).not.toHaveBeenCalled()
  })

  it('wa_devis sans lead_id / devis_ids (corps tel que le relais le sert) : AUCUNE ouverture sans enregistrement', async () => {
    monter([resultat('wa_devis', exempleContrat('crm', 'whatsapp_devis_apercu'))])
    const bouton = screen.getByRole('button', { name: /Ouvrir WhatsApp/ })
    expect(bouton).toBeDisabled()
    expect(screen.getByTestId('wa-devis-sans-commit')).toHaveTextContent('Envoi à faire depuis la fiche du lead.')
    await userEvent.click(bouton)
    expect(window.open).not.toHaveBeenCalled()
    expect(crmApi.whatsappDevis).not.toHaveBeenCalled()
  })

  it('wa_devis aux identifiants non entiers : aucune ouverture', () => {
    const apercu = exempleContrat('crm', 'whatsapp_devis_apercu')
    monter([resultat('wa_devis', { ...apercu, lead_id: '9', devis_ids: [413, 'x'] })])
    expect(screen.getByRole('button', { name: /Ouvrir WhatsApp/ })).toBeDisabled()
  })

  it('wa_devis : la langue SERVIE part au commit et à la revalidation (jamais un fr en dur)', async () => {
    const apercu = exempleContrat('crm', 'whatsapp_devis_apercu')
    crmApi.whatsappDevisApercu.mockResolvedValue({ data: apercu })
    monter([resultat('wa_devis', { ...apercu, lead_id: 9, devis_ids: [413], langue: 'darija' })], { recuLe: 0 })
    await waitFor(() => expect(crmApi.whatsappDevisApercu).toHaveBeenCalledWith(9, { devis_ids: [413], langue: 'darija' }))
    expect(screen.getByTestId('wa-texte')).toHaveAttribute('dir', 'rtl')
    await userEvent.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    await waitFor(() => expect(crmApi.whatsappDevis).toHaveBeenCalledWith(9, { devis_ids: [413], langue: 'darija' }))
  })

  it('wa_devis ancien dont l\'aperçu est refusé (garde de remise) : le motif, rien ne s\'ouvre', async () => {
    const apercu = exempleContrat('crm', 'whatsapp_devis_apercu')
    crmApi.whatsappDevisApercu.mockRejectedValue({ response: { data: apercu.exemple_400 ?? documentContrat('crm', 'whatsapp_devis_apercu').exemple_400 } })
    monter([resultat('wa_devis', { ...apercu, lead_id: 9, devis_ids: [413] })], { recuLe: 0 })
    expect(await screen.findByText(/Remise supérieure au plafond/)).toBeInTheDocument()
    expect(window.open).not.toHaveBeenCalled()
  })
})

describe('cartes — Préparer (zéro appel au modèle)', () => {
  it('« Préparer » lit la touche chez Django et AJOUTE la carte à la conversation', async () => {
    iaApi.getToucheAssistant.mockResolvedValue({ data: touche('assistant_touche') })
    const { store } = monter([resultat('file_touches', touche('assistant_a_relancer'))])
    await userEvent.click(screen.getAllByRole('button', { name: 'Préparer' })[0])
    await waitFor(() => expect(store.getState().ia.messages).toHaveLength(2))
    expect(iaApi.getToucheAssistant).toHaveBeenCalledWith(412)
    expect(iaApi.queryAgent).not.toHaveBeenCalled()
    const ajoutee = store.getState().ia.messages[1]
    expect(ajoutee.local).toBe(true)
    expect(ajoutee.cartes[0].carte).toBe('touche')
  })
})

describe('diagnostic — texte « Copier pour Claude Code »', () => {
  it('routes, statuts, identifiants de requête, erreurs — aucune question ni nom', () => {
    const d = exempleContrat('reporting', 'assistant_diagnostic')
    const texte = texteDiagnostic(d, { ecran: '/crm/relances', en_ligne: true, requetes: [
      { methode: 'POST', route: '/api/django/crm/relance-etapes/<id>/fait/', statut: 409, duree_ms: 12, request_id: 'abc' },
    ], erreurs: [{ genre: 'script', message: 'boom' }] })
    expect(texte).toMatch(/POST \/api\/django\/ventes\/devis\/<id>\/replace-lines\/ → 502/)
    expect(texte).toMatch(/request_id=0123456789abcdef0123456789abcdef/)
    expect(texte).toMatch(/\[script\] boom/)
    expect(texte).not.toMatch(/Le bouton Fait ne répond pas/)
  })

  it('le bouton copie ce texte', async () => {
    const ecrire = vi.fn(() => Promise.resolve())
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: ecrire }, configurable: true })
    monter([resultat('diagnostic', exempleContrat('reporting', 'assistant_diagnostic'))])
    await userEvent.click(screen.getByRole('button', { name: /Copier pour Claude Code/ }))
    expect(ecrire).toHaveBeenCalledTimes(1)
    expect(ecrire.mock.calls[0][0]).toMatch(/Diagnostic de l'ERP/)
    const carte = screen.getByTestId('carte-diagnostic')
    expect(within(carte).getByText(/Diagnostic \(1 j\)/)).toBeInTheDocument()
  })
})

describe('cartes — états d\'une proposition et liens sûrs (logique pure)', () => {
  const PROP = { type: 'proposition', action_key: 'a', libelle: 'A', apercu: 'Faire ?', confirm_token: 't', expire_dans_s: 300 }

  it('à confirmer jusqu\'à l\'échéance, puis expirée ; une proposition d\'historique est expirée d\'emblée', () => {
    const [fraiche] = preparerCartes([PROP], { recuLe: 1000 })
    expect(etatAffiche(fraiche, 1000 + 299 * 1000)).toBe(ETATS.A_CONFIRMER)
    expect(etatAffiche(fraiche, 1000 + 300 * 1000)).toBe(ETATS.EXPIREE)
    const [ancienne] = preparerCartes([PROP], { historique: true })
    expect(etatAffiche(ancienne, 1)).toBe(ETATS.EXPIREE)
  })

  it('sans `expire_dans_s`, la durée par défaut s\'applique', () => {
    const [carte] = preparerCartes([{ ...PROP, expire_dans_s: undefined }], { recuLe: 0 + 1 })
    expect(carte.expire_dans_s).toBe(300)
  })

  it('une carte laissée ouverte devient « expirée » toute seule', async () => {
    const msg = { role: 'agent', content: '', cartes: preparerCartes([{ ...PROP, expire_dans_s: 1 }], { recuLe: Date.now() - 800 }) }
    const store = configureStore({
      reducer: { ia: iaReducer },
      preloadedState: { ia: { ...iaReducer(undefined, { type: '@@init' }), messages: [msg] } },
    })
    render(<Provider store={store}><MemoryRouter><Vue /></MemoryRouter></Provider>)
    expect(screen.getByTestId('proposal-card')).toHaveAttribute('data-etat', 'a_confirmer')
    await waitFor(() => expect(screen.getByTestId('proposal-card')).toHaveAttribute('data-etat', 'expiree'),
      { timeout: 2000 })
  })

  it('lienWhatsAppSur / idDevisSur : liste blanche stricte', () => {
    expect(lienWhatsAppSur('https://wa.me/2126')).toBe('https://wa.me/2126')
    expect(lienWhatsAppSur('https://api.whatsapp.com/send?phone=1')).toContain('api.whatsapp.com')
    for (const mauvais of ['http://wa.me/1', 'https://wa.me.evil.example/1', 'javascript:alert(1)', '', null, 12]) {
      expect(lienWhatsAppSur(mauvais)).toBe('')
    }
    expect(idDevisSur(45)).toBe(45)
    expect(idDevisSur('45')).toBe(45)
    for (const mauvais of [0, -1, 1.5, 'abc', null, undefined, '../x']) expect(idDevisSur(mauvais)).toBeNull()
  })

  it('foyerTouche : null sans carte touche, sinon la dernière', () => {
    expect(foyerTouche([])).toBeNull()
    expect(foyerTouche([{ role: 'user', content: 'x' }])).toBeNull()
    const carte = (id) => ({ type: 'resultat', carte: 'touche', donnees: { touche: { id } } })
    expect(foyerTouche([{ cartes: [carte(1)] }, { cartes: [carte(2), { type: 'resultat', carte: 'matin', donnees: {} }] }])).toBe(2)
  })
})
