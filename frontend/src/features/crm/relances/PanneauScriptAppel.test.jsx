// CAD152 — le panneau d'appel guidé : le script SOUS LES YEUX pendant
// l'appel. Charges utiles = les exemples COMMITTÉS (PACT10) :
// `panneau_appel.json` (le panneau), `relance_etape_v2.json` (la touche),
// `relance_etape_message.json` (le script rendu) — jamais un objet retapé à
// la main.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, within } from '@testing-library/react'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'
import PanneauScriptAppel from './PanneauScriptAppel'
import {
  BANDEAU_PROFIL_SUPPOSE, MENTION_D7, CONSIGNE_ISSUE, ISSUE_VERROUILLEE,
} from './appelGuidance'

vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn(), toastSuccess: vi.fn(), toastError: vi.fn() }))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getPanneauAppel: vi.fn(),
    getRelanceEtapeMessage: vi.fn(),
    updateLead: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
    journaliserMessageVisiteOuvert: vi.fn(),
  },
}))

import crmApi from '../../../api/crmApi'

const TOUCHES = exempleContrat('crm', 'relance_etape_v2').results
const ETAPE_APPEL = TOUCHES.find((t) => t.canal === 'appel')
const ETAPE_WHATSAPP = TOUCHES.find((t) => t.canal === 'whatsapp')
const MESSAGE = exempleContrat('crm', 'relance_etape_message')
const PANNEAU = exempleContrat('crm', 'panneau_appel')
const OCCUPATION = PANNEAU.champs_a_poser.find((q) => q.champ === 'occupation_jour')

afterEach(() => { cleanup(); vi.clearAllMocks(); window.sessionStorage.clear() })

function noop() {}

function ligne(etape = ETAPE_APPEL, props = {}) {
  return render(
    <RelanceEtapeRow
      etape={etape} onFait={noop} onSauter={noop} onReporter={noop}
      onOuvrirMessage={noop} {...props}
    />,
  )
}

function armer({ panneau = PANNEAU } = {}) {
  crmApi.getPanneauAppel.mockResolvedValue({ data: panneau })
  crmApi.getRelanceEtapeMessage.mockResolvedValue(reponseContrat('crm', 'relance_etape_message'))
}

describe('CAD152 — sur une touche d’appel, le script et les questions sans quitter la ligne', () => {
  it('la bascule « Script d’appel » déplie le script ET les questions encore à poser', async () => {
    armer()
    const onOuvrirMessage = vi.fn()
    ligne(ETAPE_APPEL, { onOuvrirMessage })
    const bascule = screen.getByRole('button', { name: /Script d’appel/ })
    expect(bascule).toHaveAttribute('aria-expanded', 'false')
    // Replié : rien n'est chargé (la file du jour ne paie aucune requête).
    expect(crmApi.getPanneauAppel).not.toHaveBeenCalled()
    fireEvent.click(bascule)
    expect(await screen.findByTestId('texte-touche-contenu')).toHaveTextContent(MESSAGE.message)
    await waitFor(() => expect(crmApi.getPanneauAppel).toHaveBeenCalledWith(ETAPE_APPEL.lead))
    // Le script est lu par le GET du rendu, jamais par le POST qui journalise.
    expect(crmApi.getRelanceEtapeMessage).toHaveBeenCalledWith(ETAPE_APPEL.id)
    // La question servie (le help_text du champ, jamais réécrit ici).
    expect(await screen.findByText(OCCUPATION.question)).toBeInTheDocument()
    expect(crmApi.whatsappRelanceEtape).not.toHaveBeenCalled()
    expect(onOuvrirMessage).not.toHaveBeenCalled()
  })

  it('Q5 — sans présence en journée : bandeau « profil supposé » et la question EN TÊTE', async () => {
    armer()
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    const bandeau = await screen.findByTestId('bandeau-profil-suppose')
    expect(bandeau).toHaveTextContent(BANDEAU_PROFIL_SUPPOSE)
    expect(within(bandeau).getByText(OCCUPATION.question)).toBeInTheDocument()
    // La question n'est pas répétée dans la liste ordonnée qui suit.
    expect(screen.getAllByTestId('question-appel-occupation_jour')).toHaveLength(1)
  })

  it('présence déjà renseignée : ni bandeau, ni question — elle est RELUE, pas reposée', async () => {
    armer({ panneau: exempleContrat('crm', 'panneau_appel', 'exemple_tout_repondu') })
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    expect(await screen.findByTestId('aucune-question')).toBeInTheDocument()
    expect(screen.queryByTestId('bandeau-profil-suppose')).not.toBeInTheDocument()
  })

  it('la mention D7 est affichée : orientation et ombrage ne font pas le chiffre', async () => {
    armer()
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    expect(await screen.findByTestId('mention-d7')).toHaveTextContent(MENTION_D7)
  })
})

describe('CAD152 — une réponse écrit le champ, par le chemin de la fiche', () => {
  it('un choix PATCH la fiche, recharge le panneau et affiche le score recalculé par le serveur', async () => {
    armer()
    crmApi.updateLead.mockResolvedValue({ data: { id: ETAPE_APPEL.lead, score: 64 } })
    const onOuvrirMessage = vi.fn()
    ligne(ETAPE_APPEL, { onOuvrirMessage })
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    const bandeau = await screen.findByTestId('bandeau-profil-suppose')
    fireEvent.click(within(bandeau).getByRole('button', { name: OCCUPATION.choix[0].libelle }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(
      ETAPE_APPEL.lead, { occupation_jour: OCCUPATION.choix[0].valeur }))
    expect(await screen.findByTestId('score-recalcule')).toHaveTextContent('64/100')
    // La question répondue disparaît parce que le SERVEUR le dit : relecture.
    await waitFor(() => expect(crmApi.getPanneauAppel).toHaveBeenCalledTimes(2))
    // Garde-fou : aucun envoi, aucune activité « WhatsApp ouvert ».
    expect(crmApi.whatsappRelanceEtape).not.toHaveBeenCalled()
    expect(crmApi.journaliserMessageVisiteOuvert).not.toHaveBeenCalled()
    expect(onOuvrirMessage).not.toHaveBeenCalled()
  })

  it('un refus du serveur s’affiche SOUS le champ, en le nommant', async () => {
    armer()
    crmApi.updateLead.mockRejectedValue({
      response: { status: 400, data: { occupation_jour: ['« xx » n’est pas un choix valide.'] } },
    })
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    const bandeau = await screen.findByTestId('bandeau-profil-suppose')
    fireEvent.click(within(bandeau).getByRole('button', { name: OCCUPATION.choix[1].libelle }))
    const erreur = await screen.findByTestId('erreur-question-occupation_jour')
    expect(erreur).toHaveTextContent(`« ${OCCUPATION.libelle} » : « xx » n’est pas un choix valide.`)
  })

  it('une saisie libre à la française est NORMALISÉE ; une saisie illisible est refusée en nommant le champ', async () => {
    // Même forme que le contrat : l'entrée « nombre » de l'exemple, posée
    // sur la PREMIÈRE étape de l'appel (la facture).
    const libre = PANNEAU.champs_a_poser.find((q) => q.nature === 'nombre')
    const facture = {
      ...libre, champ: 'facture_hiver', section: 'energie', libelle: 'Facture mensuelle', question: '',
    }
    armer({ panneau: { ...PANNEAU, champs_a_poser: [facture], prefill: { occupation_jour: 'present' } } })
    crmApi.updateLead.mockResolvedValue({ data: { id: ETAPE_APPEL.lead, score: 40 } })
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    const question = await screen.findByTestId('question-appel-facture_hiver')
    const champ = within(question).getByRole('textbox')
    fireEvent.change(champ, { target: { value: 'beaucoup' } })
    fireEvent.click(within(question).getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByTestId('erreur-question-facture_hiver'))
      .toHaveTextContent('« Facture mensuelle » : « beaucoup » n’est pas un nombre.')
    expect(crmApi.updateLead).not.toHaveBeenCalled()
    fireEvent.change(champ, { target: { value: '1 200,50' } })
    fireEvent.click(within(question).getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(
      ETAPE_APPEL.lead, { facture_hiver: '1200.50' }))
  })
})

describe('CAD152 — « Appeler » ouvre le panneau AVANT de composer', () => {
  it('le bouton déplie le panneau (jamais un tel: nu) ; on compose depuis le panneau', async () => {
    armer()
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /^Appeler$/ }))
    expect(screen.getByRole('button', { name: /Script d’appel/ })).toHaveAttribute('aria-expanded', 'true')
    expect(await screen.findByRole('button', { name: /Composer le numéro/ })).toBeInTheDocument()
  })

  it('sur une touche WhatsApp aussi, « Appeler » ouvre le panneau — sans le texte WhatsApp comme script', async () => {
    armer()
    const etape = { ...ETAPE_WHATSAPP, lead_telephone: ETAPE_APPEL.lead_telephone }
    ligne(etape)
    // Replié et absent tant qu'on n'appelle pas (le panneau est gaté appel).
    expect(screen.queryByTestId('panneau-script-appel')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^Appeler$/ }))
    expect(await screen.findByTestId('questions-appel')).toBeInTheDocument()
    expect(screen.queryByTestId('texte-touche')).not.toBeInTheDocument()
    expect(crmApi.getRelanceEtapeMessage).not.toHaveBeenCalled()
  })

  it('« Saisir l’issue » mène aux réponses EXISTANTES de la touche (CKP4)', async () => {
    armer()
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    expect(await screen.findByTestId('consigne-issue')).toHaveTextContent(CONSIGNE_ISSUE)
    fireEvent.click(screen.getByRole('button', { name: /Saisir l’issue/ }))
    // Le panneau « Fait » de la ligne, avec son vocabulaire (jamais refait ici).
    expect(screen.getByRole('button', { name: 'Pas de réponse' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Répondeur' })).toBeInTheDocument()
  })

  it('touche À VENIR (CAD44) : le panneau reste ouvert, seule l’issue attend l’échéance', async () => {
    armer()
    ligne(ETAPE_APPEL, { enAvance: true })
    fireEvent.click(screen.getByRole('button', { name: /^Appeler$/ }))
    expect(await screen.findByTestId('consigne-issue')).toHaveTextContent(ISSUE_VERROUILLEE)
    expect(screen.getByRole('button', { name: /Saisir l’issue/ })).toBeDisabled()
  })
})

describe('CAD152 — sur la fiche : le panneau déplié, l’accroche servie par le contrat', () => {
  it('mode fiche : accroche de la prochaine touche, et une réponse prévient la fiche', async () => {
    armer()
    crmApi.updateLead.mockResolvedValue({ data: { id: PANNEAU.lead_id, score: 51 } })
    const onLeadEcrit = vi.fn()
    const onComposer = vi.fn()
    render(
      <PanneauScriptAppel
        mode="fiche" leadId={PANNEAU.lead_id} telephone="0612345678"
        onComposer={onComposer} onLeadEcrit={onLeadEcrit}
      />,
    )
    expect(await screen.findByTestId('script-accroche')).toHaveTextContent(PANNEAU.script.message)
    fireEvent.click(screen.getByRole('button', { name: /Composer le numéro/ }))
    expect(onComposer).toHaveBeenCalled()
    const bandeau = await screen.findByTestId('bandeau-profil-suppose')
    fireEvent.click(within(bandeau).getByRole('button', { name: OCCUPATION.choix[2].libelle }))
    await waitFor(() => expect(onLeadEcrit).toHaveBeenCalledWith({ id: PANNEAU.lead_id, score: 51 }))
  })
})
