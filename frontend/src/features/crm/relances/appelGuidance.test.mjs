import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import {
  documentContrat, exempleContrat, fichierContrat,
} from '../../../test/fixtures/contractSamples.js'
import * as guidance from './appelGuidance.js'
import {
  SEGMENT_RESIDENTIEL, segmentLivre, guidanceAppel, messageSegmentNonLivre,
  MESSAGE_SEGMENT_A_CONFIRMER, ORDRE_APPEL_1, BUDGET_APPEL_1,
  CLES_TOUCHES_APPEL_1, estToucheDeRappel, questionsDeLAppel, texteQuestion,
  OBJECTION_LOI_8221, OBJECTIONS,
} from './appelGuidance.js'

// Les charges utiles viennent du contrat COMMITTÉ (PACT10/PACT13) — jamais
// d'un mock tapé à la main : `panneau_appel.json` (CAD147).
const CONTRAT = ['crm', 'panneau_appel']
const exemple = (variante = 'exemple') => exempleContrat(...CONTRAT, variante)

// ── CAD161 — le résidentiel d'abord ─────────────────────────────────────────

test('CAD161 — le contrat porte le champ `segment` dans chacun de ses exemples', () => {
  const doc = documentContrat(...CONTRAT)
  for (const variante of ['exemple', 'exemple_sans_cadence_active', 'exemple_tout_repondu']) {
    assert.ok('segment' in doc[variante], `« segment » absent de ${variante}`)
    assert.ok('segment_libelle' in doc[variante], `« segment_libelle » absent de ${variante}`)
  }
  assert.equal(doc.exemple.segment, SEGMENT_RESIDENTIEL)
})

test('CAD161 — un lead résidentiel reçoit le panneau guidé', () => {
  const g = guidanceAppel(exemple())
  assert.equal(g.livre, true)
  assert.equal(g.segmentAConfirmer, false)
  assert.equal(g.avertissement, null)
})

test('CAD161 — un lead agricole est refusé PROPREMENT : message explicite, jamais une page vide', () => {
  const panneau = exemple('exemple_sans_cadence_active')
  assert.equal(panneau.segment, 'agricole')
  const g = guidanceAppel(panneau)
  assert.equal(g.livre, false)
  assert.equal(g.segment, 'agricole')
  assert.ok(g.message.trim().length > 0)
  assert.match(g.message, /résidentiel/)
  assert.match(g.message, /« Agricole »/)
  assert.equal(g.questions, undefined, 'aucun script résidentiel déguisé')
})

test('CAD161 — industriel et commercial sont refusés avec le libellé servi', () => {
  for (const [segment, segment_libelle] of [['industriel', 'Industriel'], ['commercial', 'Commercial']]) {
    const g = guidanceAppel({ ...exemple(), segment, segment_libelle })
    assert.equal(g.livre, false, segment)
    assert.match(g.message, new RegExp(`« ${segment_libelle} »`))
  }
})

test('CAD161 — un segment non saisi reçoit le résidentiel, marqué « à confirmer »', () => {
  const g = guidanceAppel({ ...exemple(), segment: null, segment_libelle: null })
  assert.equal(g.livre, true)
  assert.equal(g.segmentAConfirmer, true)
  assert.equal(g.avertissement, MESSAGE_SEGMENT_A_CONFIRMER)
})

test('CAD161 — segmentLivre : seul le résidentiel (ou le vide) est livré', () => {
  assert.equal(segmentLivre('residentiel'), true)
  assert.equal(segmentLivre(null), true)
  assert.equal(segmentLivre(''), true)
  assert.equal(segmentLivre('agricole'), false)
  assert.equal(segmentLivre('industriel'), false)
  assert.equal(segmentLivre('commercial'), false)
})

test('CAD161 — les textes du refus ne portent ni crochet ni chiffre', () => {
  const textes = [
    MESSAGE_SEGMENT_A_CONFIRMER,
    messageSegmentNonLivre({ segment: 'agricole', segment_libelle: 'Agricole' }),
  ]
  for (const texte of textes) {
    assert.doesNotMatch(texte, /[[\]]/)
    assert.doesNotMatch(texte, /[0-9]/)
  }
})

// ── CAD162 — l'ordre de l'appel 1 ───────────────────────────────────────────

// Un LEAD VIERGE, tel que le serveur le sert : toutes les colonnes des
// sections du questionnaire (dans l'ordre des sections, `tranche_onee`
// retirée — CAD148) puis les questions orales. La FORME de chaque entrée est
// celle du contrat (ses clés sont vérifiées ci-dessous) ; seul l'ÉTAT (quelles
// colonnes manquent) est posé par le test.
const CHAMPS_LEAD_VIERGE = [
  ['email', 'contact'], ['adresse', 'contact'], ['ville', 'contact'],
  ['gps_lat', 'gps'], ['gps_lng', 'gps'],
  ['facture_hiver', 'energie'], ['facture_ete', 'energie'],
  ['ete_differente', 'energie'], ['conso_mensuelle_kwh', 'energie'],
  ['raccordement', 'energie'], ['objectif_projet', 'energie'],
  ['type_toiture', 'toiture'], ['surface_toiture_m2', 'toiture'],
  ['roof_age', 'toiture'], ['ownership', 'toiture'], ['type_bien', 'toiture'],
  ['occupation_jour', 'occupation'], ['nb_personnes_foyer', 'occupation'],
  ['chauffage_electrique_hiver', 'occupation'],
  ['equip_piscine', 'equipements'], ['equip_voiture_electrique', 'equipements'],
  ['equip_clim', 'equipements'], ['equip_chauffe_eau_electrique', 'equipements'],
  ['decideur', null], ['devis_concurrents', null],
  ['frein_principal', null], ['declencheur', null],
]

function leadVierge(touche) {
  const base = exemple()
  const gabarit = base.champs_a_poser[0]
  const champs_a_poser = CHAMPS_LEAD_VIERGE.map(([champ, section]) => ({
    ...gabarit, champ, section, libelle: `libellé ${champ}`, question: '', choix: null,
  }))
  return { ...base, touche, script: touche ? base.script : null, champs_a_poser, prefill: {} }
}

const toucheCle = (template_cle) => ({ ...exemple().touche, template_cle })

const CINQ = ['facture_hiver', 'ete_differente', 'occupation_jour', 'type_bien', 'objectif_projet']

test('CAD162 — l\'entrée construite garde exactement la forme du contrat', () => {
  const contrat = Object.keys(exemple().champs_a_poser[0]).sort()
  for (const entree of leadVierge(null).champs_a_poser) {
    assert.deepEqual(Object.keys(entree).sort(), contrat)
  }
})

test('CAD162 — l\'appel 1 a cinq étapes, dans l\'ordre fondateur', () => {
  assert.equal(BUDGET_APPEL_1, 5)
  assert.deepEqual(ORDRE_APPEL_1.map((e) => e.etape),
    ['facture', 'ete', 'occupation', 'toit_type_bien', 'objectif'])
})

test('CAD162 — lead vierge, appel d\'ouverture : exactement ces cinq questions, dans cet ordre', () => {
  const g = guidanceAppel(leadVierge(toucheCle('appel_ouverture')))
  assert.equal(g.phase, 'appel_1')
  assert.deepEqual(g.questions.map((q) => q.champ), CINQ)
  assert.equal(g.questions.length, BUDGET_APPEL_1)
  assert.ok(!g.questions.some((q) => q.champ === 'ownership'))
  // Le montant de l'été n'est pas une sixième question : il complète la 2e.
  assert.deepEqual(g.questions[1].complements.map((q) => q.champ), ['facture_ete'])
})

test('CAD162 — « propriétaire ou locataire » absent de TOUTE touche de la prise de contact', () => {
  for (const cle of CLES_TOUCHES_APPEL_1) {
    const champs = questionsDeLAppel(leadVierge(toucheCle(cle))).map((q) => q.champ)
    assert.deepEqual(champs, CINQ, cle)
  }
  // Aucune cadence active : le budget de l'appel 1 tient.
  assert.deepEqual(questionsDeLAppel(leadVierge(null)).map((q) => q.champ), CINQ)
})

test('CAD162 — à partir de la touche de rappel, « propriétaire ou locataire » suit les cinq', () => {
  for (const cle of ['appel_suivi_j2', 'appel_suivi_j7', 'appel_suivi_j11', '']) {
    const g = guidanceAppel(leadVierge(toucheCle(cle)))
    assert.equal(g.phase, 'rappel', cle)
    assert.deepEqual(g.questions.map((q) => q.champ), [...CINQ, 'ownership'], cle)
  }
})

test('CAD162 — ce qui est déjà renseigné ne se repose pas, l\'ordre reste figé', () => {
  const panneau = leadVierge(toucheCle('appel_ouverture'))
  panneau.champs_a_poser = panneau.champs_a_poser.filter(
    (q) => !['occupation_jour', 'facture_hiver'].includes(q.champ))
  panneau.prefill = { occupation_jour: 'present', facture_hiver: 900 }
  assert.deepEqual(questionsDeLAppel(panneau).map((q) => q.champ),
    ['ete_differente', 'type_bien', 'objectif_projet'])
  // Garde défensive : une colonne présente dans `prefill` n'est jamais posée.
  const incoherent = leadVierge(toucheCle('appel_ouverture'))
  incoherent.prefill = { type_bien: 'villa' }
  assert.ok(!questionsDeLAppel(incoherent).some((q) => q.champ === 'type_bien'))
})

test('CAD162 — été déjà répondu « différent » : le montant d\'été devient la question', () => {
  const panneau = leadVierge(toucheCle('appel_ouverture'))
  panneau.champs_a_poser = panneau.champs_a_poser.filter((q) => q.champ !== 'ete_differente')
  panneau.prefill = { ete_differente: true }
  const ete = questionsDeLAppel(panneau).find((q) => q.etape === 'ete')
  assert.equal(ete.champ, 'facture_ete')
  assert.deepEqual(ete.complements, [])
})

test('CAD162 — exemples du contrat : rien d\'inventé, tout répondu = aucune question', () => {
  assert.deepEqual(questionsDeLAppel(exemple('exemple_tout_repondu')), [])
  // `exemple` : touche de suivi, occupation encore à obtenir ; la clim et le
  // décideur ne font pas partie des étapes de l'appel.
  assert.deepEqual(questionsDeLAppel(exemple()).map((q) => q.champ), ['occupation_jour'])
})

test('CAD162 — estToucheDeRappel / texteQuestion', () => {
  assert.equal(estToucheDeRappel(null), false)
  assert.equal(estToucheDeRappel(toucheCle('appel_ouverture')), false)
  assert.equal(estToucheDeRappel(toucheCle('appel_suivi_j2')), true)
  assert.equal(texteQuestion({ question: 'Q ?', libelle: 'L' }), 'Q ?')
  assert.equal(texteQuestion({ question: '', libelle: 'L' }), 'L')
})

// ── CAD163 — la loi 82-21 : rien de spontané ────────────────────────────────

// `docs/crm/messages_meryem.md`, localisé depuis la racine du dépôt que la
// fixture de contrat sait déjà trouver (…/backend/django_core/apps/crm/…).
const RACINE = join(fichierContrat('crm', 'panneau_appel'), '..', '..', '..', '..', '..', '..')
const MESSAGES = readFileSync(join(RACINE, 'docs', 'crm', 'messages_meryem.md'), 'utf8')
  .replace(/\r\n/g, '\n').split('\n')

/** Les lignes étiquetées d'une section `#### <cle>` du fichier source. */
function sectionObjection(cle) {
  const debut = MESSAGES.findIndex((l) => l.startsWith(`#### ${cle} — `))
  assert.ok(debut >= 0, `section « #### ${cle} » absente de messages_meryem.md`)
  const out = { titre: MESSAGES[debut].slice(`#### ${cle} — `.length).trim() }
  for (const ligne of MESSAGES.slice(debut + 1)) {
    if (ligne.startsWith('#')) break
    const m = /^(QUAND|RÉPONSE|JAMAIS|ENSUITE) : (.*)$/.exec(ligne)
    if (m) out[m[1]] = m[2].trim()
  }
  return out
}

/** `{cle: texte FR}` des gabarits (`### cle` + `FR : `), même lecture que
 *  les tests Python du catalogue (MRY12). */
function gabaritsFr() {
  const out = {}
  let cle = null
  for (const ligne of MESSAGES) {
    if (ligne.startsWith('### ')) cle = ligne.slice(4).split(' ')[0].trim()
    else if (cle && ligne.startsWith('FR : ')) out[cle] = ligne.slice(5).trim()
  }
  return out
}

const PHRASE_FONDATEUR = 'la loi permet de revendre une part du surplus ; je vous confirme les conditions par écrit'

test('CAD163 — la phrase est celle de la décision fondateur, mot pour mot', () => {
  const sansPonctuationFinale = OBJECTION_LOI_8221.reponse.replace(/[.\s]+$/, '')
  assert.equal(sansPonctuationFinale.toLowerCase(), PHRASE_FONDATEUR)
})

test('CAD163 — le module suit le fichier source messages_meryem.md (re-dérivé, jamais retapé)', () => {
  const source = sectionObjection(OBJECTION_LOI_8221.cle)
  assert.equal(OBJECTION_LOI_8221.titre, source.titre)
  assert.equal(OBJECTION_LOI_8221.quand, source.QUAND)
  assert.equal(OBJECTION_LOI_8221.reponse, source['RÉPONSE'])
  assert.equal(OBJECTION_LOI_8221.jamais, source.JAMAIS)
  assert.equal(OBJECTION_LOI_8221.ensuite, source.ENSUITE)
})

test('CAD163 — aucun chiffre dans la phrase : ni tarif, ni pourcentage, ni délai', () => {
  const { reponse } = OBJECTION_LOI_8221
  assert.doesNotMatch(reponse, /[0-9٠-٩۰-۹]/)
  assert.doesNotMatch(reponse, /%/)
  assert.doesNotMatch(reponse, /[[\]]/)
  assert.doesNotMatch(reponse, /centime|dirham|\bMAD\b|\bDH\b|kWh/i)
})

test('CAD163 — réponse d\'OBJECTION uniquement : nulle part ailleurs dans le module', () => {
  const trouvees = []
  const parcourir = (valeur, chemin) => {
    if (typeof valeur === 'string') {
      if (/revendre une part du surplus/i.test(valeur)) trouvees.push(chemin)
    } else if (valeur && typeof valeur === 'object') {
      for (const [k, v] of Object.entries(valeur)) parcourir(v, `${chemin}.${k}`)
    }
  }
  for (const [nom, valeur] of Object.entries(guidance)) {
    if (nom !== 'OBJECTIONS') parcourir(valeur, nom)
  }
  assert.deepEqual(trouvees, ['OBJECTION_LOI_8221.reponse'])
  assert.ok(OBJECTIONS.includes(OBJECTION_LOI_8221))
  // Le panneau la sert parmi les objections, jamais parmi les questions.
  const g = guidanceAppel(leadVierge(toucheCle('appel_ouverture')))
  assert.ok(g.objections.includes(OBJECTION_LOI_8221))
  assert.ok(!g.questions.some((q) => /surplus/i.test(texteQuestion(q))))
})

test('CAD163 — jamais dans un script d\'ouverture : aucun gabarit d\'appel ne parle de la loi', () => {
  const gabarits = gabaritsFr()
  const clesAppel = [...CLES_TOUCHES_APPEL_1, 'appel_suivi_j2', 'appel_suivi_j7', 'appel_suivi_j11']
  for (const cle of clesAppel) {
    assert.ok(cle in gabarits, `gabarit ${cle} introuvable dans messages_meryem.md`)
    assert.doesNotMatch(gabarits[cle], /82-21|surplus/i, cle)
  }
  // Et la phrase n'est le texte d'AUCUN gabarit de message.
  for (const [cle, texte] of Object.entries(gabarits)) {
    assert.doesNotMatch(texte, /revendre une part du surplus/i, cle)
  }
})
