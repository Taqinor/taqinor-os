import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import {
  PARCOURS, typeEtape, reponsesDeLEtape, reponseComplete, estTache, estTacheSansAppel,
  familleCanal, gestes,
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
      const attendues = reponsesDeLEtape(type, etape).map((r) => r.label)
      const groupe = screen.getByRole('group', { name: type.question })
      const affichees = [...groupe.querySelectorAll('button')].map((b) => b.textContent)
      expect(affichees).toEqual(attendues)
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
