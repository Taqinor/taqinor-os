import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import {
  PARCOURS, typeEtape, reponsesDeLEtape, reponseComplete, estTache, estTacheSansAppel,
  familleCanal, gestes, organiserReponses, raisonsDuSegment, gesteVisible,
  proposerDarija, confirmationMessageExigee,
} from './parcours'
import RelanceEtapeRow from './RelanceEtapeRow'

/* SUIVI-PARCOURS (30/09/2026) — L'ÉCRAN EST LA TABLE.
   La garde de parcours du serveur (`apps/crm/tests_parcours_suivi.py`) rejoue
   chaque réponse de `parcours_suivi.json` par l'API réelle ; ce test-ci
   prouve que l'écran propose EXACTEMENT ces réponses, avec ces libellés, sur
   la bonne touche — jamais une liste écrite à part. Si les deux gardes sont
   vertes, le guide PDF (généré depuis la même table) dit la vérité. */

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getPanneauAppel: vi.fn(() => Promise.reject(new Error('indisponible'))),
    getRelanceEtapeMessage: vi.fn(() => Promise.resolve({ data: { message: 'x', langue: 'fr' } })),
  },
}))
vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn(), toastSuccess: vi.fn() }))

afterEach(() => { cleanup(); vi.clearAllMocks() })

const TOUCHE = exempleContrat('crm', 'relance_etape_v2').results[0]
const [, DECIDER] = exempleContrat('crm', 'relance_etape_v2', 'exemple_generique').results
const DEBRIEF = exempleContrat('crm', 'relance_etape_v2', 'exemple_debrief_visite').results[0]

/** Une touche REPRÉSENTATIVE de chaque type de la table (clé, libellé,
 *  cadence et canal lus dans `reconnaissance`). */
function toucheDuType(type) {
  const r = type.reconnaissance || {}
  const base = { ...TOUCHE, statut: 'a_faire', overdue: false, suites: {} }
  if (r.cles?.length) {
    const cadence = type.famille === 'Visite technique' ? 'apres_devis' : 'generique'
    const canal = type.id === 'confirmation' || type.id === 'message_creneau' ? 'whatsapp' : 'appel'
    return { ...base, cle: r.cles[0], libelle: r.libelles?.[0] ?? type.nom, cadence, canal }
  }
  if (r.libelles?.length) {
    return { ...base, cle: '', libelle: r.libelles[0], cadence: 'generique', canal: 'appel' }
  }
  return {
    ...base, cle: '', libelle: type.nom, cadence: r.cadences[0],
    canal: r.canaux ? r.canaux[0] : 'appel',
  }
}

function noop() {}

describe('parcours.js — la table est saine', () => {
  it('chaque réponse a un modèle, un libellé, un effet et une suite ; aucun libellé en double par étape', () => {
    for (const type of PARCOURS.etapes) {
      const labels = new Set()
      for (const entree of type.reponses) {
        expect(PARCOURS.modeles, `${type.id}/${entree.modele}`).toHaveProperty(entree.modele)
        const r = { ...PARCOURS.modeles[entree.modele], ...entree }
        expect(r.label, `${type.id}/${entree.modele}`).toBeTruthy()
        expect(r.effet, `${type.id}/${entree.modele}`).toBeTruthy()
        expect(r.suite?.type, `${type.id}/${entree.modele}`).toBeTruthy()
        expect(PARCOURS.legende_suite, `${type.id}/${entree.modele} suite.type`).toHaveProperty(r.suite.type)
        expect(labels.has(r.label), `${type.id} doublon « ${r.label} »`).toBe(false)
        labels.add(r.label)
        // Une réponse envoie UNE chose au serveur (une issue OU une clé de
        // réponse) ; un geste de planification peut l'accompagner (« Visite
        // acceptée » : la modale d'abord, l'issue si la date n'est pas fixée)
        // ou la remplacer (« la date est calée », « reportée »).
        const envois = ['outcome', 'reponse'].filter((k) => r[k] !== undefined)
        expect(envois.length === 1 || (envois.length === 0 && Boolean(r.geste)),
          `${type.id}/${entree.modele} envoi`).toBe(true)
      }
      // Les réponses d'APPEL (id ou objet) : un modèle connu ; décrites → une suite légendée.
      for (const entree of type.reponses_appel || []) {
        const r = reponseComplete(typeof entree === 'string' ? { modele: entree } : entree)
        expect(PARCOURS.modeles, `${type.id}/appel/${r.id}`).toHaveProperty(r.id)
        if (typeof entree !== 'string') {
          expect(r.effet, `${type.id}/appel/${r.id}`).toBeTruthy()
          expect(PARCOURS.legende_suite, `${type.id}/appel/${r.id}`).toHaveProperty(r.suite.type)
        }
      }
    }
  })

  it('groupes et « Autre réponse » : déclarés UNE fois dans la table, jamais ailleurs', () => {
    expect(Object.keys(PARCOURS.groupes)).toEqual(['pas_joint', 'plus_tard'])
    expect(PARCOURS.groupes.pas_joint).toMatchObject({ label: 'Pas joint', titre: 'Précision (facultatif)' })
    expect(PARCOURS.groupes.plus_tard.label).toBe('Plus tard…')
    expect(PARCOURS.autre_reponse.label).toBe('Autre réponse')
    const parGroupe = {}
    const autres = []
    for (const [id, modele] of Object.entries(PARCOURS.modeles)) {
      if (modele.groupe) {
        expect(PARCOURS.groupes, `${id}.groupe`).toHaveProperty(modele.groupe)
        if (!parGroupe[modele.groupe]) parGroupe[modele.groupe] = []
        parGroupe[modele.groupe].push(id)
      }
      if (modele.rang) {
        expect(modele.rang, `${id}.rang`).toBe('autre')
        autres.push(id)
      }
      // Jamais à la fois dans un groupe ET derrière « Autre réponse ».
      expect(Boolean(modele.groupe && modele.rang), id).toBe(false)
    }
    expect(parGroupe.pas_joint).toEqual([
      'pas_de_reponse', 'sans_reponse', 'repondeur', 'occupe', 'numero_invalide', 'bloque'])
    expect(parGroupe.plus_tard).toEqual(['rappel', 'plus_tard', 'attente_accord'])
    expect(autres).toEqual([
      'ne_plus_contacter', 'question_prix', 'devis_modifie', 'decision_famille', 'decision_proprietaire'])
  })

  it('un seul libellé « Pas de réponse » pour pas_de_reponse ET sans_reponse (même issue serveur)', () => {
    expect(PARCOURS.modeles.pas_de_reponse.label).toBe('Pas de réponse')
    expect(PARCOURS.modeles.sans_reponse.label).toBe('Pas de réponse')
    expect(PARCOURS.modeles.pas_de_reponse.outcome).toBe('non_joint')
    expect(PARCOURS.modeles.sans_reponse.outcome).toBe('non_joint')
  })

  it('chaque raison d’attente déclare les segments où elle vaut', () => {
    const segments = new Set(['residentiel', 'agricole', 'commercial', 'industriel'])
    const raisons = PARCOURS.modeles.attente_accord.raisons
    for (const r of raisons) {
      expect(r.segments?.length, r.valeur).toBeGreaterThan(0)
      for (const s of r.segments) expect(segments.has(s), `${r.valeur}/${s}`).toBe(true)
    }
    const de = (valeur) => raisons.find((r) => r.valeur === valeur).segments
    for (const v of ['direction', 'bailleur_murs', 'budget_exercice', 'consultation']) {
      expect(de(v), v).toEqual(['commercial', 'industriel'])
    }
    expect(de('administration')).toEqual(['agricole', 'commercial', 'industriel'])
    expect([...de('financement')].sort()).toEqual(['agricole', 'commercial', 'industriel', 'residentiel'])
  })

  it('chaque type est reconnu depuis une touche représentative, et un seul type par touche', () => {
    for (const type of PARCOURS.etapes) {
      expect(typeEtape(toucheDuType(type)).id, type.id).toBe(type.id)
    }
  })

  it('reconnaissance : la clé prime sur le libellé, le libellé sur la cadence, le repli est « generique »', () => {
    expect(typeEtape({ cle: 'devis', libelle: 'Faire le devis', cadence: 'generique', canal: 'appel' }).id).toBe('devis')
    expect(typeEtape({ cle: 'debrief', libelle: 'Rappeler après passage', cadence: 'apres_devis', canal: 'appel' }).id).toBe('debrief')
    expect(typeEtape({ cle: '', libelle: 'Planifier la visite technique convenue', cadence: 'apres_devis', canal: 'appel' }).id).toBe('planifier')
    expect(typeEtape({ cle: '', libelle: 'Appel de suivi', cadence: 'apres_devis', canal: 'appel' }).id).toBe('suivi_appel')
    expect(typeEtape({ cle: '', libelle: 'Le PDF s’ouvre bien ?', cadence: 'apres_devis', canal: 'whatsapp' }).id).toBe('suivi_message')
    expect(typeEtape({ cle: '', libelle: 'Réveil J60', cadence: 'reveil', canal: 'email' }).id).toBe('reveil_message')
    expect(typeEtape({ cle: '', libelle: 'Rappeler le client (il l’a demandé)', cadence: 'generique', canal: 'appel' }).id).toBe('generique')
    expect(typeEtape(DECIDER).id).toBe('decider_suite')
    expect(typeEtape(DEBRIEF).id).toBe('debrief')
    // Le canal historique « visite » (CAD58) est un appel.
    expect(familleCanal('visite')).toBe('appel')
  })

  it('les tâches : jamais un appel d’office sauf « planifier » (qui est un appel pour caler la date)', () => {
    const taches = PARCOURS.etapes.filter(estTache).map((t) => t.id)
    expect(taches).toEqual(['devis', 'decider_suite', 'question_prix', 'planifier', 'devis_modifie'])
    expect(PARCOURS.etapes.filter(estTacheSansAppel).map((t) => t.id))
      .toEqual(['devis', 'decider_suite', 'question_prix', 'devis_modifie'])
  })
})

describe('RelanceEtapeRow — l’écran propose exactement les réponses de la table', () => {
  for (const type of PARCOURS.etapes) {
    it(`${type.id} : la question et les réponses sont celles de la table`, () => {
      const etape = toucheDuType(type)
      render(
        <RelanceEtapeRow etape={etape} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
      )
      fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
      const reponses = reponsesDeLEtape(type, etape)
      const items = organiserReponses(reponses)
      const attendues = items.map((it) => (it.genre === 'reponse' ? it.reponse.label : it.label))
      const groupe = screen.getByRole('group', { name: type.question })
      const affichees = [...groupe.querySelectorAll('button')].map((b) => b.textContent)
      expect(affichees).toEqual(attendues)
      // Chaque réponse de la table reste ATTEIGNABLE : à plat, ou dans la seconde
      // rangée de son groupe (« Pas joint », « Plus tard… », « Autre réponse »).
      let atteignables = items.filter((it) => it.genre === 'reponse').length
      for (const it of items.filter((i) => i.genre !== 'reponse')) {
        fireEvent.click(screen.getByRole('button', { name: it.label }))
        const sous = screen.getByTestId(`sous-reponses-${it.cle}`)
        expect([...sous.querySelectorAll('button')].map((b) => b.textContent))
          .toEqual(it.membres.map((m) => m.reponse.label))
        atteignables += it.membres.length
      }
      expect(atteignables).toBe(reponses.length)
      // Une tâche ne se « saute » pas ; une touche ordinaire, si.
      const sauter = screen.queryByRole('button', { name: /Sauter/ })
      if (estTache(type)) expect(sauter).toBeNull()
    })
  }

  it('sur le type générique, les précisions d’appel (Répondeur, Occupé…) s’ajoutent seulement à un appel', () => {
    const generique = PARCOURS.etapes.find((t) => t.id === 'generique')
    const appel = { ...toucheDuType(generique), canal: 'appel' }
    const message = { ...toucheDuType(generique), canal: 'whatsapp' }
    expect(reponsesDeLEtape(generique, appel).map((r) => r.label)).toContain('Répondeur')
    expect(reponsesDeLEtape(generique, message).map((r) => r.label)).not.toContain('Répondeur')
  })
})

/* SIMPLIFICATION DES RÉPONSES (17/11/2026) — comment l'écran PROPOSE les
   réponses : groupes, « Autre réponse », filtres de contexte. Présentation
   seulement : chaque réponse garde sa clé serveur. */
describe('organiserReponses — pastilles, groupes et « Autre réponse »', () => {
  const type = (id) => PARCOURS.etapes.find((t) => t.id === id)
  const sur = (id, etape = {}) => organiserReponses(reponsesDeLEtape(type(id), { ...TOUCHE, ...etape }))
  const etiquettes = (items) => items.map((it) => (it.genre === 'reponse' ? it.reponse.label : it.label))

  it('premier contact (appel) : 6 pastilles dont « Pas joint » (5), « Plus tard… » (3) et « Autre réponse » (1)', () => {
    const items = sur('contact_appel', { canal: 'appel' })
    expect(etiquettes(items)).toEqual([
      'Client joint', 'Visite acceptée', 'Pas joint', 'Plus tard…', 'Refus', 'Autre réponse'])
    expect(items.find((i) => i.cle === 'pas_joint').membres.map((m) => m.reponse.label)).toEqual([
      'Pas de réponse', 'Répondeur', 'Occupé', 'Numéro invalide', 'A bloqué / signalé'])
    expect(items.find((i) => i.cle === 'plus_tard').membres.map((m) => m.reponse.label)).toEqual([
      'À rappeler le…', 'Plus tard — pas maintenant', "En attente d'un accord (DPA / banque)"])
    expect(items.find((i) => i.genre === 'autre').membres.map((m) => m.reponse.label))
      .toEqual(['Ne plus me contacter'])
  })

  it('après devis (appel) : 6 pastilles ; Numéro invalide et A bloqué n’y sont plus', () => {
    const items = sur('suivi_appel', { canal: 'appel' })
    expect(etiquettes(items)).toEqual([
      'Client joint', 'Visite acceptée', 'Pas joint', 'Plus tard…', 'Refuse la proposition', 'Autre réponse'])
    expect(items.find((i) => i.cle === 'pas_joint').membres.map((m) => m.reponse.label))
      .toEqual(['Pas de réponse', 'Répondeur', 'Occupé'])
    expect(items.find((i) => i.genre === 'autre').membres).toHaveLength(5)
    const ids = reponsesDeLEtape(type('suivi_appel'), TOUCHE).map((r) => r.id)
    expect(ids).not.toContain('numero_invalide')
    expect(ids).not.toContain('bloque')
  })

  it('un groupe d’un seul membre n’est pas groupé : pastille ordinaire, libellé propre', () => {
    const items = sur('devis', { canal: 'appel' })
    expect(etiquettes(items)).toEqual([
      'Devis envoyé — passer à la suite', 'Visite d’abord', 'Pas encore — à rappeler le…',
      'Client refuse', 'Autre réponse'])
    expect(items.some((i) => i.genre === 'groupe')).toBe(false)
    // « Autre réponse » même avec UNE seule réponse derrière.
    expect(items.find((i) => i.genre === 'autre').membres).toHaveLength(1)
    expect(etiquettes(sur('planifier', { canal: 'appel' }))).toContain('Pas de réponse')
  })

  it('le premier membre d’un groupe est celui de la table (présélection de l’écran)', () => {
    const items = sur('contact_appel', { canal: 'appel' })
    for (const g of items.filter((i) => i.genre === 'groupe')) {
      expect(g.membres[0].reponse.id).toBe(g.cle === 'pas_joint' ? 'pas_de_reponse' : 'rappel')
    }
  })

  it('« Visite acceptée » / « Visite d’abord » disparaissent quand une visite est déjà prévue', () => {
    for (const id of ['contact_appel', 'devis', 'suivi_appel']) {
      const sans = reponsesDeLEtape(type(id), { ...TOUCHE, canal: 'appel', visite_prevue_le: null })
      const avec = reponsesDeLEtape(type(id), { ...TOUCHE, canal: 'appel', visite_prevue_le: '2099-01-05' })
      expect(sans.some((r) => r.id === 'visite'), id).toBe(true)
      expect(avec.some((r) => r.id === 'visite'), id).toBe(false)
      expect(avec).toHaveLength(sans.length - 1)
    }
  })

  it('raisons d’attente : résidentiel (ou sans segment) = financement seul ; pros = les six', () => {
    const raisons = (lead_segment) => reponsesDeLEtape(type('contact_appel'), { ...TOUCHE, canal: 'appel', lead_segment })
      .find((r) => r.id === 'attente_accord').raisons.map((r) => r.valeur)
    expect(raisons('')).toEqual(['financement'])
    expect(raisons(undefined)).toEqual(['financement'])
    expect(raisons('residentiel')).toEqual(['financement'])
    expect(raisons('agricole')).toEqual(['financement', 'administration'])
    for (const s of ['commercial', 'industriel']) {
      expect(raisons(s)).toEqual([
        'direction', 'financement', 'bailleur_murs', 'budget_exercice', 'consultation', 'administration'])
    }
    expect(raisonsDuSegment([{ valeur: 'x' }], 'agricole')).toEqual([{ valeur: 'x' }])
  })

  it('« Pièce reçue » : masqué sur le suivi après devis et les tâches qui ne l’attendent pas', () => {
    for (const id of ['suivi_appel', 'suivi_message', 'question_prix', 'devis_modifie', 'decider_suite']) {
      expect(gesteVisible('piece_recue', type(id)), id).toBe(false)
    }
    for (const id of ['contact_appel', 'devis', 'planifier', 'pieces_recues', 'generique']) {
      expect(gesteVisible('piece_recue', type(id)), id).toBe(true)
    }
    expect(gesteVisible('sauter', type('suivi_appel'))).toBe(true)
  })

  it('darija : seulement une réponse « client joint », jamais sur une tâche', () => {
    const rep = (id) => reponseComplete({ modele: id })
    for (const id of ['joint', 'a_repondu', 'joint_telephone', 'visite']) {
      expect(proposerDarija(type('contact_appel'), rep(id)), id).toBe(true)
    }
    for (const id of ['pas_de_reponse', 'refus', 'rappel', 'ne_plus_contacter']) {
      expect(proposerDarija(type('contact_appel'), rep(id)), id).toBe(false)
    }
    expect(proposerDarija(type('devis'), rep('visite'))).toBe(false)
    expect(proposerDarija(type('contact_appel'), null)).toBe(false)
  })

  it('« message non ouvert » n’est pas exigé pour un refus, « Ne plus me contacter », le téléphone, la pièce', () => {
    const rep = (id) => reponseComplete({ modele: id })
    for (const id of ['refus', 'ne_plus_contacter', 'joint_telephone', 'piece']) {
      expect(confirmationMessageExigee(rep(id)), id).toBe(false)
    }
    for (const id of ['a_repondu', 'pas_de_reponse', 'rappel', 'plus_tard']) {
      expect(confirmationMessageExigee(rep(id)), id).toBe(true)
    }
    expect(confirmationMessageExigee(null)).toBe(true)
  })
})

/* AGR533 — variantes de SEGMENT de la table : seuls libellé / précision /
   effet changent ; la clé serveur (`reponse`) et la suite restent. */
describe('AGR533 — libellés agricoles de la table du parcours', () => {
  const touche = exempleContrat('crm', 'relance_etape_v2').results[0]
  const suiviAppel = PARCOURS.etapes.find((e) => e.id === 'suivi_appel')

  it('agricole : « associés / coopérative », même `reponse` que decision_famille', () => {
    const r = reponsesDeLEtape(suiviAppel, { ...touche, canal: 'appel', lead_segment: 'agricole' })
      .find((x) => x.id === 'decision_famille')
    expect(r.label).toBe('Décision à plusieurs — associés / coopérative')
    expect(r.reponse).toBe('decision_famille')
  })

  it('résidentiel (ou segment absent) : le libellé actuel', () => {
    for (const lead_segment of ['residentiel', '', undefined]) {
      const r = reponsesDeLEtape(suiviAppel, { ...touche, canal: 'appel', lead_segment })
        .find((x) => x.id === 'decision_famille')
      expect(r.label).toBe('Décision à plusieurs — en famille')
      expect(r.reponse).toBe('decision_famille')
    }
  })

  it('une variante ne change ni la clé serveur ni la suite', () => {
    const entree = { modele: 'decision_famille', suite: { type: 'barreau_suivant' } }
    const r = reponseComplete(entree, 'agricole')
    expect(r.reponse).toBe('decision_famille')
    expect(r.suite).toEqual({ type: 'barreau_suivant' })
  })

  it('le geste « Pièce reçue » : plaque, forage, ABH pour un agricole', () => {
    expect(gestes('agricole').find((g) => g.id === 'piece_recue').label)
      .toBe('Pièce reçue : plaque, forage, ABH')
    expect(gestes().find((g) => g.id === 'piece_recue').label).toBe('Pièce reçue')
  })
})

/* CIQ509 — libellés PROS de la table (commercial / industriel) ; résidentiel
   inchangé, octet pour octet. `message` d'une variante : l'accusé PROPOSÉ. */
describe('CIQ509 — libellés pros de la table du parcours', () => {
  const touche = exempleContrat('crm', 'relance_etape_v2').results[0]
  const suiviAppel = PARCOURS.etapes.find((e) => e.id === 'suivi_appel')
  const trouver = (etape, id) => reponsesDeLEtape(suiviAppel, etape).find((x) => x.id === id)

  it('commercial et industriel : « Décision à plusieurs — direction / associés », même clé serveur', () => {
    for (const lead_segment of ['commercial', 'industriel']) {
      const r = trouver({ ...touche, canal: 'appel', lead_segment }, 'decision_famille')
      expect(r.label).toBe('Décision à plusieurs — direction / associés')
      expect(r.reponse).toBe('decision_famille')
      const p = trouver({ ...touche, canal: 'appel', lead_segment }, 'decision_proprietaire')
      expect(p.label).toBe('Décision à plusieurs — bailleur / propriétaire des murs')
      expect(p.reponse).toBe('decision_proprietaire')
    }
  })

  it('résidentiel : le libellé actuel', () => {
    for (const lead_segment of ['residentiel', '', undefined]) {
      const etape = { ...touche, canal: 'appel', lead_segment }
      expect(trouver(etape, 'decision_famille').label).toBe('Décision à plusieurs — en famille')
      expect(trouver(etape, 'decision_proprietaire').label).toBe('Décision à plusieurs — le propriétaire')
      expect(trouver(etape, 'attente_accord').label).toBe("En attente d'un accord (DPA / banque)")
      expect(trouver(etape, 'attente_accord').message).toBeUndefined()
    }
  })

  it('« En attente d’un accord » pro : libellé neutre, accusé proposé, raisons de la table', () => {
    for (const lead_segment of ['commercial', 'industriel']) {
      const r = trouver({ ...touche, canal: 'appel', lead_segment }, 'attente_accord')
      expect(r.label).toBe("En attente d'un accord")
      expect(r.message).toBe('attente_accord_accuse')
      expect(r.reponse).toBe('attente_accord')
      expect(r.raison).toBe(true)
      expect(r.raisons.map((x) => x.valeur)).toEqual([
        'direction', 'financement', 'bailleur_murs', 'budget_exercice', 'consultation',
        'administration',
      ])
    }
  })

  it('le geste « Pièce reçue » : factures, schéma, pièces de la société pour un pro', () => {
    const effet = gestes('industriel').find((g) => g.id === 'piece_recue').effet
    expect(effet).toContain('ses factures ou relevés, un schéma électrique ou les pièces de la société')
    expect(gestes().find((g) => g.id === 'piece_recue').label).toBe('Pièce reçue')
  })

  it('une variante pro ne change ni la clé serveur ni la suite', () => {
    const entree = { modele: 'attente_accord', suite: { type: 'meme_etape', jour: 'date_choisie' } }
    const r = reponseComplete(entree, 'industriel')
    expect(r.reponse).toBe('attente_accord')
    expect(r.suite).toEqual({ type: 'meme_etape', jour: 'date_choisie' })
  })
})


/* 16/11/2026 — l'étape « Relancer le client pour ses pièces » (clé moteur
   `pieces_recues`, lead pro joint sans facture) a SON type : la question dit ce
   qu'on attend, et « Oui — pièce reçue » ouvre le panneau « Pièce reçue » au
   lieu de répondre « Fait ». */
describe('« Relancer le client pour ses pièces » — type propre de la table', () => {
  const type = PARCOURS.etapes.find((t) => t.id === 'pieces_recues')
  const touche = {
    ...TOUCHE, statut: 'a_faire', overdue: false, suites: {}, cle: 'pieces_recues',
    libelle: 'Pièces reçues ?', cadence: 'generique', canal: 'whatsapp', message_ouvert_le: null,
  }

  it('reconnu par sa clé — même sous l’ancien libellé encore ouvert en base', () => {
    expect(type.famille).toBe('Après l’appel (avant devis)')
    expect(type.nom).toBe('Relancer le client pour ses pièces')
    expect(typeEtape(touche).id).toBe('pieces_recues')
    expect(typeEtape({ ...touche, libelle: 'Relancer le client pour ses pièces (factures, schéma)' }).id)
      .toBe('pieces_recues')
    expect(estTache(type)).toBe(false)
    // Le type générique ne le cite plus parmi ses exemples.
    const generique = PARCOURS.etapes.find((t) => t.id === 'generique')
    expect(generique.exemples.join(' ')).not.toMatch(/Pièces reçues/)
  })

  it('la question et les six réponses, dans l’ordre', () => {
    expect(type.question).toBe('Le client a-t-il envoyé ses pièces ?')
    expect(reponsesDeLEtape(type, touche).map((r) => r.label)).toEqual([
      'Oui — pièce reçue', 'Relance envoyée — pas encore de pièce', 'À rappeler le…',
      'Visite acceptée', 'Client refuse', 'Ne plus me contacter',
    ])
  })

  it('« Oui — pièce reçue » ouvre le panneau « Pièce reçue » et n’envoie rien', () => {
    const onFait = vi.fn()
    render(
      <RelanceEtapeRow etape={touche} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Oui — pièce reçue' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(screen.getByTestId('panneau-piece-recue')).toBeInTheDocument()
    expect(onFait).not.toHaveBeenCalled()
  })
})
