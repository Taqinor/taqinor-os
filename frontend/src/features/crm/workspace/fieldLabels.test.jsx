import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import fieldLabels from './fieldLabels'

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
  const re = /htmlFor="([\w-]+)"/g
  let m = re.exec(source)
  while (m) {
    ids.add(m[1])
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
    const fantomes = Object.entries(fieldLabels)
      .filter(([, entry]) => !allKnownIds.has(entry.inputId))
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
})
