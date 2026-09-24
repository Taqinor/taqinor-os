// CAD152 — le panneau d'appel guidé : le script SOUS LES YEUX pendant
// l'appel. Charges utiles = les exemples COMMITTÉS (PACT10) :
// `panneau_appel.json` (le panneau), `relance_etape_v2.json` (la touche),
// `relance_etape_message.json` (le script rendu) — jamais un objet retapé à
// la main.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { render, screen, cleanup, fireEvent, waitFor, within } from '@testing-library/react'
import {
  exempleContrat, fichierContrat, reponseContrat,
} from '../../../test/fixtures/contractSamples'
import fieldLabels from '../workspace/fieldLabels'
import RelanceEtapeRow from './RelanceEtapeRow'
import PanneauScriptAppel from './PanneauScriptAppel'
import * as guidance from './appelGuidance'
import {
  BANDEAU_PROFIL_SUPPOSE, MENTION_D7, CONSIGNE_ISSUE, ISSUE_VERROUILLEE,
  ORDRE_APPEL_1, QUESTIONS_DU_RAPPEL, scriptTouche, RAMADAN_PAS_DE_SOIR,
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

// ════════════════════════════════════════════════════════════════════════════
// CAD153 — T9 : les tests qui FIGENT le script guidé (moitié écran ; la moitié
// serveur est `apps/crm/tests_cad153_script_guide.py`).
// ════════════════════════════════════════════════════════════════════════════

// `docs/crm/messages_meryem.md`, localisé depuis la racine du dépôt que la
// fixture de contrat sait déjà trouver (…/backend/django_core/apps/crm/…).
// C'est une DOC (la source des textes), jamais du code source.
const RACINE = join(fichierContrat('crm', 'panneau_appel'), '..', '..', '..', '..', '..', '..')
const MESSAGES = readFileSync(join(RACINE, 'docs', 'crm', 'messages_meryem.md'), 'utf8')
  .replace(/\r\n/g, '\n').split('\n')

/** Les lignes `CLE : texte` de la section « Panneau d'appel — consignes
 *  d'écran » du fichier source. */
function consignesDEcran() {
  const debut = MESSAGES.findIndex((l) => l.startsWith('## Panneau d\'appel — consignes d\'écran'))
  expect(debut, 'section des consignes du panneau absente de messages_meryem.md').toBeGreaterThanOrEqual(0)
  const out = {}
  for (const ligne of MESSAGES.slice(debut + 1)) {
    if (ligne.startsWith('#')) break
    const trouve = /^([A-Z][A-Z0-9_]*) : (.*)$/.exec(ligne)
    if (trouve) out[trouve[1]] = trouve[2].trim()
  }
  return out
}

//: Les consignes d'écran livrées par CAD152 (les tâches suivantes en ajoutent :
//: la section les porte toutes, la garde les compare toutes).
const CONSIGNES_CAD152 = [
  'MENTION_D7', 'BANDEAU_PROFIL_SUPPOSE', 'EXPLICATION_PROFIL_SUPPOSE',
  'CONSIGNE_ISSUE', 'ISSUE_VERROUILLEE', 'AUCUNE_QUESTION',
]

//: Les cinq touches d'appel qui n'avaient AUCUN script (Appel 4, Appel 6,
//: suivis J2/J7/J11) — la moitié serveur prouve leur `template_cle`.
const CINQ_TOUCHES = [
  ['contact', 'repondeur'], ['contact', 'appel_dernier'],
  ['apres_devis', 'appel_suivi_j2'], ['apres_devis', 'appel_suivi_j7'],
  ['apres_devis', 'appel_suivi_j11'],
]

describe('CAD153 — les textes du panneau sont ceux du fichier source', () => {
  it('chaque consigne d’écran est re-dérivée de messages_meryem.md, mot pour mot', () => {
    const source = consignesDEcran()
    for (const cle of CONSIGNES_CAD152) expect(source, cle).toHaveProperty(cle)
    for (const [cle, texte] of Object.entries(source)) {
      expect(guidance[cle], `${cle} absent de appelGuidance.js`).toBe(texte)
    }
  })

  it('aucune consigne d’écran ne porte un chiffre ni un crochet', () => {
    for (const [cle, texte] of Object.entries(consignesDEcran())) {
      expect(texte, cle).not.toMatch(/[0-9٠-٩۰-۹]/)
      expect(texte, cle).not.toMatch(/[[\]]/)
    }
  })
})

describe('CAD153 — chaque touche d’appel a son script, sur la ligne', () => {
  it('les cinq touches sans script d’avant CAD67/CAD98 affichent leur titre et leur texte', async () => {
    crmApi.getPanneauAppel.mockResolvedValue({ data: PANNEAU })
    crmApi.getRelanceEtapeMessage.mockResolvedValue(reponseContrat('crm', 'relance_etape_message'))
    for (const [cadence, cle] of CINQ_TOUCHES) {
      const titre = scriptTouche(cle)?.titre
      expect(titre, cle).toBeTruthy()
      const { unmount } = ligne({ ...ETAPE_APPEL, cadence, template_cle: cle })
      fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
      expect(await screen.findByText(titre)).toBeInTheDocument()
      expect(await screen.findByTestId('texte-touche-contenu')).toHaveTextContent(MESSAGE.message)
      unmount()
    }
    expect(crmApi.whatsappRelanceEtape).not.toHaveBeenCalled()
  })
})

describe('CAD153 — tout champ que le panneau écrit est déclaré à l’écran (fieldLabels)', () => {
  it('chaque colonne des étapes (appel, rappel, agricole, pro) a son libellé', () => {
    const champs = [
      ...ORDRE_APPEL_1, ...QUESTIONS_DU_RAPPEL, ...guidance.ORDRE_AGRICOLE, ...guidance.ORDRE_PRO,
    ].flatMap((e) => e.champs)
    expect(champs.length).toBeGreaterThan(0)
    for (const champ of champs) {
      expect(fieldLabels[champ], `${champ} absent de fieldLabels.js`).toBeTruthy()
      expect(fieldLabels[champ].label.trim().length, champ).toBeGreaterThan(0)
    }
  })
})

// ════════════════════════════════════════════════════════════════════════════
// CAD155 — pendant le Ramadan, l'appel du soir n'existe pas : le panneau le dit
// ════════════════════════════════════════════════════════════════════════════
describe('CAD155 — la fenêtre RÉELLE du jour, lue du moteur', () => {
  /** « HH:MM » → minutes. */
  const minutes = (hhmm) => {
    const [h, m] = hhmm.split(':').map(Number)
    return h * 60 + m
  }

  it('en période de Ramadan saisie, le panneau annonce 10 h-14 h et ne propose aucun créneau du soir', async () => {
    const RAMADAN = exempleContrat('crm', 'panneau_appel', 'exemple_ramadan')
    armer({ panneau: RAMADAN })
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    expect(await screen.findByTestId('fenetre-plage')).toHaveTextContent('10:00–14:00')
    expect(screen.getByTestId('ramadan-pas-de-soir')).toHaveTextContent(RAMADAN_PAS_DE_SOIR)
    const creneaux = screen.getAllByTestId('creneau-propose').map((c) => c.textContent)
    expect(creneaux).toEqual(['10:00–14:00'])
    // Aucun créneau ne déborde de la fenêtre servie (donc aucun créneau du soir).
    const fin = minutes(RAMADAN.fenetre_du_jour.fin)
    for (const creneau of creneaux) {
      const [debut, finCreneau] = creneau.split('–')
      expect(minutes(debut)).toBeLessThan(fin)
      expect(minutes(finCreneau)).toBeLessThanOrEqual(fin)
    }
  })

  it('un vendredi ordinaire : la pause de la prière découpe la fenêtre en deux créneaux', async () => {
    const vendredi = exempleContrat('crm', 'panneau_appel', 'exemple_sans_cadence_active').fenetre_du_jour
    armer({ panneau: { ...PANNEAU, fenetre_du_jour: vendredi } })
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    expect(await screen.findByTestId('fenetre-plage'))
      .toHaveTextContent(`${vendredi.debut}–${vendredi.fin} (pause ${vendredi.pause.debut}–${vendredi.pause.fin})`)
    expect(screen.getAllByTestId('creneau-propose').map((c) => c.textContent)).toEqual([
      `${vendredi.debut}–${vendredi.pause.debut}`, `${vendredi.pause.fin}–${vendredi.fin}`,
    ])
    expect(screen.queryByTestId('ramadan-pas-de-soir')).not.toBeInTheDocument()
  })

  it('un jour non ouvré : aucun créneau proposé, le panneau le dit', async () => {
    armer({ panneau: exempleContrat('crm', 'panneau_appel', 'exemple_tout_repondu') })
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    expect(await screen.findByTestId('jour-non-appelable')).toBeInTheDocument()
    expect(screen.queryAllByTestId('creneau-propose')).toHaveLength(0)
  })

  it('horaire illisible côté serveur (null) : le panneau ne dit rien de l’horaire, jamais un supposé', async () => {
    armer({ panneau: { ...PANNEAU, fenetre_du_jour: null } })
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    expect(await screen.findByTestId('mention-d7')).toBeInTheDocument()
    expect(screen.queryByTestId('fenetre-du-jour')).not.toBeInTheDocument()
  })
})

// ════════════════════════════════════════════════════════════════════════════
// CAD157 — dire à l'écran ce qui n'est PAS compté
// ════════════════════════════════════════════════════════════════════════════
describe('CAD157 — les quatre cas « pas compté » affichent leur mention', () => {
  it('D7, charges futures, tranche ONEE et équipement déclaré sans grandeur — aucun calcul touché', async () => {
    armer()
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    const bloc = await screen.findByTestId('non-compte')
    // 1. Orientation, inclinaison, ombrage (décision D7).
    expect(within(bloc).getByTestId('mention-d7')).toHaveTextContent(guidance.MENTION_D7)
    expect(guidance.MENTION_D7).toContain('inclinaison')
    // 2. Charges futures cochées sur le site.
    expect(within(bloc).getByTestId('non-compte-futures-charges'))
      .toHaveTextContent(guidance.NON_COMPTE_FUTURES_CHARGES)
    // 3. Tranche ONEE, texte libre qu'aucun calcul ne lit.
    expect(within(bloc).getByTestId('non-compte-tranche-onee'))
      .toHaveTextContent(guidance.NON_COMPTE_TRANCHE_ONEE)
    // 4. Équipement déclaré sans sa grandeur : le DRAPEAU SERVI décide, et le
    //    champ qui manque est nommé par son libellé d'écran.
    const clim = within(bloc).getByTestId('non-compte-equipement-clim')
    expect(clim).toHaveTextContent('Climatisation : pas compté dans le chiffre')
    expect(clim).toHaveTextContent(fieldLabels.equip_clim_kw.label)
    expect(clim).toHaveTextContent('photo de la plaque pour que ce soit compté')
    expect(within(bloc).getByTestId('non-compte-equipement-chauffe_eau'))
      .toHaveTextContent(fieldLabels.equip_chauffe_eau_kw.label)
    // Une couche comptée, ou un équipement non déclaré : aucune mention.
    expect(within(bloc).queryByTestId('non-compte-equipement-piscine')).not.toBeInTheDocument()
    expect(within(bloc).queryByTestId('non-compte-equipement-ve')).not.toBeInTheDocument()
    // Aucun calcul modifié : l'affichage n'écrit rien.
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })

  it('mentionEquipementNonCompte : une grandeur qui n’est pas une puissance ne parle pas de plaque', () => {
    const ve = { cle: 've', libelle: 'Véhicule électrique', declare: true, compte_dans_etude: false,
      champs_manquants: ['equip_ve_km_semaine'] }
    const texte = guidance.mentionEquipementNonCompte(ve, (c) => fieldLabels[c].label)
    expect(texte).toContain(fieldLabels.equip_ve_km_semaine.label)
    expect(texte).not.toContain('plaque')
    expect(guidance.mentionEquipementNonCompte({ ...ve, compte_dans_etude: true })).toBeNull()
    expect(guidance.mentionEquipementNonCompte({ ...ve, declare: false })).toBeNull()
  })
})

// ════════════════════════════════════════════════════════════════════════════
// CAD175 — seconde livraison : agricole (pompage) et industriel
// ════════════════════════════════════════════════════════════════════════════
describe('CAD175 — le bon jeu de questions, et aucune estimation chiffrée', () => {
  // Les entrées sont construites À PARTIR de celles du contrat (même forme),
  // seul l'ÉTAT (quelles colonnes restent à poser) est posé par le test.
  const AGRICOLE = exempleContrat('crm', 'panneau_appel', 'exemple_sans_cadence_active')
  const nombre = AGRICOLE.champs_a_poser[0]
  const entree = (champ, extra = {}) => ({
    ...nombre, champ, libelle: fieldLabels[champ]?.label ?? champ, question: '', ...extra,
  })
  const occupationServie = PANNEAU.champs_a_poser.find((q) => q.champ === 'occupation_jour')

  /** Une estimation chiffrée : un nombre accolé à une unité d'argent,
   *  d'énergie ou à un pourcentage. */
  const ESTIMATION = /\d[\d\s.,]*\s*(MAD|DH|dirhams?|%|kWh)/i

  it('lead agricole : la pompe d’abord, les consignes à noter, le garde-fou carburant — aucun chiffre', async () => {
    armer({
      panneau: {
        ...AGRICOLE,
        champs_a_poser: [
          occupationServie, entree('pompe_cv'), entree('pompe_hmt_m'), entree('pompe_debit_m3h'),
          ...AGRICOLE.champs_a_poser, entree('carburant_litres_mois'),
        ],
      },
    })
    render(<PanneauScriptAppel mode="fiche" leadId={AGRICOLE.lead_id} />)
    const liste = await screen.findByTestId('questions-appel')
    const posees = [...liste.querySelectorAll('[data-testid^="question-appel-"]')]
      .map((n) => n.getAttribute('data-testid').replace('question-appel-', ''))
    // `pompe_alim_actuelle` est déjà sur la fiche : le carburant la complète.
    expect(posees).toEqual([
      'pompe_cv', 'pompe_hmt_m', 'pompe_debit_m3h', 'pompage_heures_jour', 'carburant_litres_mois',
    ])
    // Une colonne sans question écrite se lit avec le libellé de la FICHE.
    expect(within(liste).getByText(fieldLabels.pompe_cv.label)).toBeInTheDocument()
    // La présence à la maison n'est pas une question de pompage.
    expect(screen.queryByTestId('bandeau-profil-suppose')).not.toBeInTheDocument()
    expect(screen.getByTestId('a-noter')).toHaveTextContent(guidance.A_NOTER_FORCE_MOTRICE)
    const gardeFous = screen.getAllByTestId('garde-fou-segment').map((n) => n.textContent)
    expect(gardeFous).toEqual([guidance.AUCUNE_ESTIMATION_SEGMENT, guidance.CARBURANT_DECLARE_SEUL])
    expect(screen.getByTestId('panneau-script-appel').textContent).not.toMatch(ESTIMATION)
  })

  it('lead industriel : conso, puissance souscrite, surface, décideur — jamais la présence, aucun chiffre', async () => {
    armer({
      panneau: {
        ...PANNEAU,
        segment: 'industriel',
        segment_libelle: 'Industriel',
        champs_a_poser: [
          occupationServie, entree('conso_mensuelle_kwh'), entree('surface_toiture_m2'),
          PANNEAU.champs_a_poser.find((q) => q.champ === 'decideur'),
          entree('compteur_puissance_kva'),
        ],
      },
    })
    render(<PanneauScriptAppel mode="fiche" leadId={PANNEAU.lead_id} />)
    const liste = await screen.findByTestId('questions-appel')
    const posees = [...liste.querySelectorAll('[data-testid^="question-appel-"]')]
      .map((n) => n.getAttribute('data-testid').replace('question-appel-', ''))
    expect(posees).toEqual(['conso_mensuelle_kwh', 'compteur_puissance_kva', 'surface_toiture_m2', 'decideur'])
    expect(screen.queryByTestId('bandeau-profil-suppose')).not.toBeInTheDocument()
    expect(screen.getByTestId('a-noter')).toHaveTextContent(guidance.A_NOTER_TENSION)
    expect(screen.getAllByTestId('garde-fou-segment').map((n) => n.textContent))
      .toEqual([guidance.AUCUNE_ESTIMATION_SEGMENT])
    expect(screen.getByTestId('panneau-script-appel').textContent).not.toMatch(ESTIMATION)
  })

  it('une réponse agricole s’écrit par le chemin de la fiche, normalisée', async () => {
    armer({ panneau: { ...AGRICOLE, champs_a_poser: [entree('pompe_cv')] } })
    crmApi.updateLead.mockResolvedValue({ data: { id: AGRICOLE.lead_id, score: 30 } })
    render(<PanneauScriptAppel mode="fiche" leadId={AGRICOLE.lead_id} />)
    const question = await screen.findByTestId('question-appel-pompe_cv')
    fireEvent.change(within(question).getByRole('textbox'), { target: { value: '7,5' } })
    fireEvent.click(within(question).getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.updateLead)
      .toHaveBeenCalledWith(AGRICOLE.lead_id, { pompe_cv: '7.5' }))
  })
})

// ════════════════════════════════════════════════════════════════════════════
// CAD168 — les deux lignes fixes de la facture, enfin dites (sans chiffre)
// ════════════════════════════════════════════════════════════════════════════
describe('CAD168 — la question des lignes fixes figure au script', () => {
  it('résidentiel : la question de découverte et sa consigne, sans aucun montant', async () => {
    armer()
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    const bloc = await screen.findByTestId('question-charges-fixes')
    expect(bloc).toHaveTextContent(guidance.QUESTION_CHARGES_FIXES)
    expect(bloc).toHaveTextContent(guidance.CONSIGNE_CHARGES_FIXES)
    // AUCUN chiffre prononçable : le montant vit au barème, jamais ici.
    expect(bloc.textContent).not.toMatch(/[0-9]/)
  })

  it('agricole : pas de ligne fixe BT domestique à demander', async () => {
    armer({ panneau: exempleContrat('crm', 'panneau_appel', 'exemple_sans_cadence_active') })
    render(<PanneauScriptAppel mode="fiche" leadId={1} />)
    expect(await screen.findByTestId('questions-appel')).toBeInTheDocument()
    expect(screen.queryByTestId('question-charges-fixes')).not.toBeInTheDocument()
  })
})

describe('CAD153 — une question déjà répondue n’est JAMAIS reposée', () => {
  it('même si le serveur la servait encore, une colonne présente en prefill ne s’affiche pas', async () => {
    // Incohérence simulée À PARTIR du contrat : la présence est à la fois
    // « à poser » et « déjà sur la fiche » — le prefill gagne toujours.
    armer({ panneau: { ...PANNEAU, prefill: { ...PANNEAU.prefill, occupation_jour: 'present' } } })
    ligne()
    fireEvent.click(screen.getByRole('button', { name: /Script d’appel/ }))
    expect(await screen.findByTestId('mention-d7')).toBeInTheDocument()
    expect(screen.queryByTestId('bandeau-profil-suppose')).not.toBeInTheDocument()
    expect(screen.queryByTestId('question-appel-occupation_jour')).not.toBeInTheDocument()
  })
})
