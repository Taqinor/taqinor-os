import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import fieldLabels from './fieldLabels'
import { SECTION_FIELDS, TRACKED_KEYS } from './draftCore'

// RÈGLE FONDATEUR 08/09/2026 — garde-fou anti-dérive de fieldLabels.js : lu
// en TEST contre la SOURCE des sections (même patron que
// hooks/useDuplicateCheckWiring.test.mjs — lecture directe des fichiers,
// aucun rendu nécessaire), donc AUCUN champ édité dans le Lead Workspace ne
// peut se retrouver sans libellé/section/inputId le jour où une erreur
// serveur le cible (SaveChip, useLeadDraft.messageChampErreur).
//
// Fichier en .test.jsx (et non .test.mjs) : vitest.config.js n'inclut QUE
// `src/**/*.test.jsx` par défaut (les .test.mjs sont une couche séparée
// exécutée par `node --test`, jamais par `npm run test:unit`) — ce garde-fou
// doit tourner sous vitest, comme demandé par la lane.
const HERE = dirname(fileURLToPath(import.meta.url))
const SECTIONS_DIR = join(HERE, 'sections')

// Les 6 fichiers de sections du registre qui portent des champs ÉDITABLES.
// SectionOrigine/SectionWebQuestionnaire (dans SectionDivers.jsx) sont de la
// pure LECTURE SEULE (DefinitionList, jamais un FormField/htmlFor) — hors
// périmètre par construction (rien à y trouver).
const SECTION_FILES = [
  'SectionContact.jsx',
  'SectionPipeline.jsx',
  'SectionEnergie.jsx', // porte aussi SectionEquipements + SectionPompage
  'SectionSite.jsx',
  'SectionVisite.jsx',
  'SectionDivers.jsx',
]

const REGISTRY_SECTIONS = [
  'contact', 'pipeline', 'energie', 'equipements', 'pompage', 'toiture', 'visite', 'divers',
]

function htmlForIdsIn(source) {
  const ids = new Set()
  // QJR593 — StructureSelector porte son id en prop (pas de htmlFor externe).
  const re = /htmlFor="([\w-]+)"|<StructureSelector\s+id="([\w-]+)"/g
  let m = re.exec(source)
  while (m) {
    ids.add(m[1] || m[2])
    m = re.exec(source)
  }
  return ids
}

const idsByFile = Object.fromEntries(
  SECTION_FILES.map((f) => [f, htmlForIdsIn(readFileSync(join(SECTIONS_DIR, f), 'utf8'))]),
)
const allKnownIds = new Set(Object.values(idsByFile).flatMap((s) => [...s]))
const mappedInputIds = new Set(Object.values(fieldLabels).map((f) => f.inputId))

describe('fieldLabels — la carte ne dérive pas des sections réelles (règle fondateur 08/09/2026)', () => {
  for (const file of SECTION_FILES) {
    it(`tous les htmlFor de ${file} ont une entrée dans fieldLabels.js`, () => {
      const missing = [...idsByFile[file]].filter((id) => !mappedInputIds.has(id))
      expect(missing).toEqual([])
    })
  }

  it('aucune entrée de fieldLabels ne pointe un inputId absent des sections (pas de fantôme)', () => {
    // CAD174 — `pending` EXEMPTE un champ dont l'écran n'est pas encore
    // dans une des six sections classiques (vague 1 du script d'appel
    // guidé, saisie par `PanneauScriptAppel.jsx` — CAD152/153) : son
    // `inputId` est un nom RÉSERVÉ, pas encore un `htmlFor` réel. Retirer
    // `pending` dès que son `<FormField>` existe quelque part ci-dessus.
    const fantomes = Object.entries(fieldLabels)
      .filter(([, entry]) => !entry.pending && !allKnownIds.has(entry.inputId))
      .map(([key, entry]) => `${key} → ${entry.inputId}`)
    expect(fantomes).toEqual([])
  })

  it('chaque entrée porte un label non vide', () => {
    const sansLabel = Object.entries(fieldLabels)
      .filter(([, entry]) => typeof entry.label !== 'string' || !entry.label.trim())
      .map(([key]) => key)
    expect(sansLabel).toEqual([])
  })

  it('chaque entrée pointe une section du registre SectionsPane', () => {
    const inconnues = Object.entries(fieldLabels)
      .filter(([, entry]) => !REGISTRY_SECTIONS.includes(entry.section))
      .map(([key, entry]) => `${key} → ${entry.section}`)
    expect(inconnues).toEqual([])
  })

  // Incident déclencheur (08/09/2026) — vérifié nommément : la clé au cœur
  // de l'incident garde bien son entrée, avec le libellé exact du FormField.
  it('equip_clim_kw pointe « Puissance totale climatisation (kW) » (equipements, lf-equip-clim-kw)', () => {
    expect(fieldLabels.equip_clim_kw).toEqual({
      label: 'Puissance totale climatisation (kW)',
      section: 'equipements',
      inputId: 'lf-equip-clim-kw',
    })
  })

  // CAD174 — les huit champs de la vague 1 (CAD149) ont chacun une entrée,
  // avec le MÊME libellé que le `verbose_name` serveur (`apps/crm/models.py`)
  // — le garde-fou de la tâche (l'écran et le `help_text` disent la même
  // chose). `pending` est EXPLICITE : ces champs n'ont pas encore leur
  // `<FormField>` dans une des six sections classiques.
  it('les huit champs CAD149 (vague 1) ont une entrée fieldLabels, marquée pending', () => {
    const attendus = {
      type_bien: 'Type de bien',
      objectif_projet: 'Objectif du projet',
      decideur: 'Qui décide',
      devis_concurrents: 'Autres devis en cours',
      equip_ve_statut: 'Véhicule électrique — déjà là ou prévu ?',
      pompage_heures_jour: 'Pompage — heures par jour',
      pompe_alim_actuelle: 'Pompe actuelle — alimentation',
      carburant_litres_mois: 'Carburant consommé (litres/mois)',
    }
    for (const [cle, label] of Object.entries(attendus)) {
      const entree = fieldLabels[cle]
      expect(entree, cle).toBeTruthy()
      expect(entree.label, cle).toBe(label)
      expect(entree.pending, cle).toBeTruthy()
    }
  })
})

// QJR656 (contrat QJR506 `lead_provenance_fields.json`) — chaque champ de
// provenance du lead (la bannière « valeurs du lead modifiées ») porte un
// `libelleCourt` non vide : un champ ajouté côté serveur ne s'affiche plus
// sous son nom technique. L'échantillon est égal à
// `crm.selectors.LEAD_PROVENANCE_FIELDS` (garde backend
// `apps/crm/tests_lead_provenance_fields_contract.py`).
describe('QJR656 — un libellé court pour chaque champ de provenance du lead', () => {
  const contrat = JSON.parse(readFileSync(join(HERE, '..', '..', '..', '..', '..',
    'backend', 'django_core', 'apps', 'crm', 'contract_samples',
    'lead_provenance_fields.json'), 'utf8'))
  const champs = contrat.exemple.champs

  it('l’échantillon n’est pas vide', () => {
    expect(champs.length).toBeGreaterThan(10)
  })

  it.each(champs)('%s porte un libelleCourt non vide', (champ) => {
    const court = fieldLabels[champ]?.libelleCourt
    expect(typeof court).toBe('string')
    expect(court.trim().length).toBeGreaterThan(0)
  })
})

// ERR-QJR593-GARDE-SECTION-FIELDS — chaque champ listé dans SECTION_FIELDS doit
// (1) être suivi (TRACKED_KEYS) et (2) porter un libellé dans fieldLabels. Les
// seules exceptions sont NOMMÉES et justifiées ci-dessous ; l'écran n'est pas
// modifié. Décision fondateur à demander : ces 4 clés doivent-elles recevoir un
// libellé ? Tant qu'elle n'est pas prise, toute NOUVELLE clé sans libellé échoue.
const SANS_LIBELLE = {
  owner: 'responsable du lead : sélecteur d’utilisateur, pas un champ libre ciblé par une erreur serveur.',
  regularisation_8221: 'case Loi 82-21 tri-état : aucune erreur de champ ciblée côté serveur.',
  visite_effectuee: 'booléen du flux « visite » (SectionVisite), pas un champ saisi librement.',
  custom_data: 'sac JSON libre (champs personnalisés) : pas de libellé unique, chaque clé a le sien.',
}

describe('ERR-QJR593 — SECTION_FIELDS ⊆ TRACKED_KEYS ∩ fieldLabels', () => {
  const toutes = Object.entries(SECTION_FIELDS).flatMap(([sec, ks]) => ks.map((k) => [sec, k]))

  it.each(toutes)('%s.%s est suivi (TRACKED_KEYS)', (_sec, k) => {
    expect(TRACKED_KEYS).toContain(k)
  })

  it.each(toutes.filter(([, k]) => !(k in SANS_LIBELLE)))(
    '%s.%s porte un libellé dans fieldLabels', (_sec, k) => {
      expect(fieldLabels[k]?.label, `fieldLabels.${k} manquant`).toBeTruthy()
    })

  it('la liste d’exceptions ne contient que des clés réellement sans libellé', () => {
    for (const k of Object.keys(SANS_LIBELLE)) {
      expect(fieldLabels[k]?.label, `${k} a un libellé : retirez-le des exceptions`).toBeFalsy()
      expect(toutes.some(([, kk]) => kk === k)).toBe(true)
    }
  })
})
