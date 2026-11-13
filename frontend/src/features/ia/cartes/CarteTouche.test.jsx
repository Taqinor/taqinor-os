import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider, useSelector } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* NOUVEAU FICHIER DE TEST : la carte « touche » (COP-F2) est un composant neuf.
   Données = échantillons committés (`assistant_touche.json`, ligne complète de
   `relance_etape_v2.json`) ; les gestes passent par les VRAIES méthodes de
   `crmApi` (mockées ici) — la carte n'invente aucune URL. */

vi.mock('../../../api/iaApi', () => ({
  default: { getToucheAssistant: vi.fn(), getFileTouchesAssistant: vi.fn(), queryAgent: vi.fn() },
}))
vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn(), toastError: vi.fn() }))
vi.mock('../../../api/crmApi', () => ({
  default: {
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    marquerRelanceEtapeFait: vi.fn(),
    marquerRelanceEtapeSautee: vi.fn(),
    reporterRelanceEtape: vi.fn(),
    annulerRelanceEtape: vi.fn(),
    whatsappRelanceEtape: vi.fn(() => Promise.resolve({ data: {} })),
    getRelanceEtapeMessage: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import iaApi from '../../../api/iaApi'
import crmApi from '../../../api/crmApi'
import iaReducer from '../store/iaSlice'
import CartesDuMessage from './CartesDuMessage'
import { preparerCartes, foyerTouche } from './cartes'

const SAMPLE = exempleContrat('crm', 'assistant_touche')
const AUTRES = exempleContrat('crm', 'assistant_touche', 'exemple_proposition')
const REFUS = exempleContrat('crm', 'assistant_touche', 'exemple_refus')
// Ligne COMPLÈTE d'une touche WhatsApp (le sérialiseur sert plus que l'extrait).
const LIGNE_WA = exempleContrat('crm', 'relance_etape_v2').results[1]
const TOUCHE_WA = { ...LIGNE_WA, ...SAMPLE.touche, lead_whatsapp: '+212651971400', lead_telephone: '+212651971400' }
const DONNEES_WA = { ...SAMPLE, touche: TOUCHE_WA }
const TOUCHE_APPEL = { ...exempleContrat('crm', 'relance_etape_v2').results[0], id: AUTRES.touche.id, canal: 'appel' }

function Vue() {
  const msg = useSelector((s) => s.ia.messages[0])
  return <CartesDuMessage msg={msg} index={0} variant="page" />
}

function monter(donnees, { recuLe = Date.now() } = {}) {
  const initial = iaReducer(undefined, { type: '@@init' })
  const carte = { type: 'resultat', action_key: 'crm.suivi.preparer_touche', libelle: 'Préparer', carte: 'touche', donnees }
  const msg = { role: 'agent', content: '', cartes: preparerCartes([carte], { recuLe }) }
  const store = configureStore({
    reducer: { ia: iaReducer }, preloadedState: { ia: { ...initial, messages: [msg] } },
  })
  render(<Provider store={store}><MemoryRouter><Vue /></MemoryRouter></Provider>)
  return store
}

const avecProposition = (geste, corps, libelle = 'Salma Idrissi — Appel : fait') => ({
  ...AUTRES, touche: TOUCHE_APPEL,
  proposition: { geste, libelle, effet: 'Effet annoncé par le serveur.', corps },
})

beforeEach(() => {
  vi.clearAllMocks()
  window.open = vi.fn()
})

describe('carte touche — ce qu\'elle montre', () => {
  it('le lead, la touche, son échéance, son canal et le texte validé (ligne de l\'écran Relances embarquée)', () => {
    monter(DONNEES_WA)
    expect(screen.getByText('Aziz Benali')).toBeInTheDocument()
    expect(screen.getByText(/Relance J\+1/)).toBeInTheDocument()
    expect(screen.getByText('Suivi de proposition (après devis)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /WhatsApp/ })).toBeInTheDocument()
    expect(screen.getByTestId('touche-texte')).toHaveTextContent('Bonjour Aziz, votre proposition est prête')
  })

  it('refus : l\'en-tête dit le lead, la touche, la date prévue et le canal', () => {
    monter(REFUS)
    expect(screen.getByText('Client Opposé')).toBeInTheDocument()
    expect(screen.getByText(/Relance J\+7 · prévue le .* · whatsapp · Devis envoyé/)).toBeInTheDocument()
  })

  it('darija en lettres arabes : texte rendu de droite à gauche', () => {
    monter({ ...DONNEES_WA, message: { ...SAMPLE.message, message: 'السلام عليكم', langue: 'darija' } })
    const texte = screen.getByTestId('touche-texte')
    expect(texte).toHaveAttribute('dir', 'rtl')
    expect(texte).toHaveAttribute('lang', 'ar')
  })

  it('refus : le détail, ni texte, ni ligne, ni bouton d\'ouverture', () => {
    monter(REFUS)
    expect(screen.getByTestId('touche-refus')).toHaveTextContent('a demandé à ne plus être contacté')
    expect(screen.queryByTestId('touche-texte')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /WhatsApp/ })).not.toBeInTheDocument()
  })

  it('le foyer de la conversation = la touche de la dernière carte « touche »', () => {
    const store = monter(DONNEES_WA)
    expect(foyerTouche(store.getState().ia.messages)).toBe(TOUCHE_WA.id)
  })
})

describe('carte touche — WhatsApp (RELANCE-WA)', () => {
  it('un clic ouvre wa.me ET journalise « WhatsApp ouvert » ; la touche reste à faire', async () => {
    monter(DONNEES_WA)
    await userEvent.click(screen.getByRole('button', { name: /WhatsApp/ }))
    expect(window.open).toHaveBeenCalledWith(SAMPLE.message.wa_url, '_blank', 'noopener')
    await waitFor(() => expect(crmApi.whatsappRelanceEtape).toHaveBeenCalledWith(TOUCHE_WA.id))
    expect(screen.queryByTestId('touche-traitee')).not.toBeInTheDocument()
    expect(iaApi.queryAgent).not.toHaveBeenCalled()
  })

  it('un lien non sûr n\'est jamais ouvert : le flux complet de l\'écran prend le relais', async () => {
    monter({ ...DONNEES_WA, message: { ...SAMPLE.message, wa_url: 'https://evil.example/x' } })
    await userEvent.click(screen.getByRole('button', { name: /WhatsApp/ }))
    expect(window.open).not.toHaveBeenCalled()
    await waitFor(() => expect(crmApi.getRelanceEtapeMessage).toHaveBeenCalledWith(TOUCHE_WA.id))
  })

  it('carte ancienne : relue AVANT toute ouverture — un lead qui a dit STOP ne s\'ouvre pas', async () => {
    iaApi.getToucheAssistant.mockResolvedValue({ data: REFUS })
    monter(DONNEES_WA, { recuLe: Date.now() - 10 * 60 * 1000 })
    expect(await screen.findByTestId('touche-refus')).toBeInTheDocument()
    expect(iaApi.getToucheAssistant).toHaveBeenCalledWith(TOUCHE_WA.id)
    expect(screen.queryByRole('button', { name: /WhatsApp/ })).not.toBeInTheDocument()
    expect(window.open).not.toHaveBeenCalled()
  })

  it('carte fraîche : aucune relecture', () => {
    monter(DONNEES_WA)
    expect(iaApi.getToucheAssistant).not.toHaveBeenCalled()
  })
})

describe('carte touche — la proposition du serveur (carte-écho)', () => {
  it('« Enregistrer : <libellé> » + l\'effet ; le doigt poste le corps EXACT au geste « fait »', async () => {
    const corps = { outcome: 'rappel', rappel_le: '2026-11-19', rappel_heure: '11:00', note: 'Rappeler jeudi.' }
    crmApi.marquerRelanceEtapeFait.mockResolvedValue({
      data: { ...TOUCHE_APPEL, statut: 'fait', prochaine_touche: { libelle: 'Appel de rappel', due_date: '2026-11-19' } },
    })
    monter(avecProposition('fait', corps))
    expect(screen.getByRole('button', { name: /Enregistrer : Salma Idrissi — Appel : fait/ })).toBeInTheDocument()
    expect(screen.getByText('Effet annoncé par le serveur.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer :/ }))
    expect(crmApi.marquerRelanceEtapeFait).toHaveBeenCalledWith(TOUCHE_APPEL.id, corps)
    const traitee = await screen.findByTestId('touche-traitee')
    expect(traitee).toHaveTextContent('Fait — prochaine touche : Appel de rappel')
    // La carte est « traitée » : plus aucun bouton d'envoi ni de réponse.
    expect(screen.queryByRole('button', { name: /WhatsApp/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Enregistrer :/ })).not.toBeInTheDocument()
  })

  it('geste « reporter » : la méthode de report, la touche reste à faire', async () => {
    const corps = { rappel_le: '2026-11-19', rappel_heure: '11:00' }
    crmApi.reporterRelanceEtape.mockResolvedValue({ data: { ...TOUCHE_APPEL, due_date: '2026-11-19' } })
    monter(avecProposition('reporter', corps))
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer :/ }))
    expect(crmApi.reporterRelanceEtape).toHaveBeenCalledWith(TOUCHE_APPEL.id, corps)
    await waitFor(() => expect(screen.queryByRole('button', { name: /Enregistrer :/ })).not.toBeInTheDocument())
    expect(screen.queryByTestId('touche-traitee')).not.toBeInTheDocument()
  })

  it('un geste hors de la table fixe (fait / reporter / sauter) n\'offre aucun bouton', () => {
    monter(avecProposition('supprimer', {}))
    expect(screen.queryByRole('button', { name: /Enregistrer :/ })).not.toBeInTheDocument()
    expect(crmApi.marquerRelanceEtapeFait).not.toHaveBeenCalled()
  })

  it('proposition_refus affichée telle quelle', () => {
    monter(exempleContrat('crm', 'assistant_touche', 'exemple_proposition_refusee'))
    expect(screen.getByTestId('proposition-refus'))
      .toHaveTextContent('Date de rappel passée : le 2026-11-10 est avant aujourd\'hui.')
  })

  it('refus du serveur au geste : message sous la carte, la carte reste actionnable', async () => {
    crmApi.marquerRelanceEtapeFait.mockRejectedValue({ response: { status: 409, data: { detail: 'Déjà traitée.' } } })
    monter(avecProposition('fait', { outcome: 'rappel' }))
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer :/ }))
    expect(await screen.findByText(/Enregistrement refusé par le serveur/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Enregistrer :/ })).toBeEnabled()
  })
})

describe('carte touche — après une réponse', () => {
  const traiter = async () => {
    crmApi.marquerRelanceEtapeFait.mockResolvedValue({
      data: { ...TOUCHE_APPEL, statut: 'fait', prochaine_touche: null },
    })
    const store = monter(avecProposition('fait', { outcome: 'non_joint' }))
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer :/ }))
    await screen.findByTestId('touche-traitee')
    return store
  }

  it('« Annuler » relit la touche (annuler/) et la remet à faire', async () => {
    await traiter()
    crmApi.annulerRelanceEtape.mockResolvedValue({ data: { ...TOUCHE_APPEL, statut: 'a_faire' } })
    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(crmApi.annulerRelanceEtape).toHaveBeenCalledWith(TOUCHE_APPEL.id)
    await waitFor(() => expect(screen.queryByTestId('touche-traitee')).not.toBeInTheDocument())
  })

  it('« Touche suivante » relit la file et prépare la première ligne (sans le modèle)', async () => {
    const store = await traiter()
    iaApi.getFileTouchesAssistant.mockResolvedValue({
      data: { lignes: [{ touche_id: TOUCHE_APPEL.id }, { touche_id: 9001 }] },
    })
    iaApi.getToucheAssistant.mockResolvedValue({ data: SAMPLE })
    await userEvent.click(screen.getByRole('button', { name: 'Touche suivante' }))
    await waitFor(() => expect(store.getState().ia.messages).toHaveLength(2))
    expect(iaApi.getToucheAssistant).toHaveBeenCalledWith(9001)
    expect(iaApi.queryAgent).not.toHaveBeenCalled()
    // Le foyer suit la dernière carte touche affichée.
    expect(foyerTouche(store.getState().ia.messages)).toBe(SAMPLE.touche.id)
  })

  it('« Touche suivante » : file vide', async () => {
    await traiter()
    iaApi.getFileTouchesAssistant.mockResolvedValue({ data: { lignes: [] } })
    await userEvent.click(screen.getByRole('button', { name: 'Touche suivante' }))
    expect(await screen.findByText('Plus de touche à faire pour le moment.')).toBeInTheDocument()
  })
})
