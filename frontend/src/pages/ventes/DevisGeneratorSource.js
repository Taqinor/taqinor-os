// SPL42 — LE LECTEUR UNIQUE DU SOURCE DU GÉNÉRATEUR.
//
// Des tests `node --test` lisent le SOURCE du générateur (DevisGenerator.jsx
// n'est pas exécutable sans React). Le groupe SPL (SPL43-SPL55) découpe ce
// fichier par déplacements purs : sans lecteur unique, chaque déplacement
// casserait les assertions qui visent un bloc déplacé, et rendrait VACUEUSES
// les gardes négatives (elles ne liraient plus que la coquille).
//
// `FILES` liste les fichiers qui COMPOSENT le générateur (chemins relatifs à
// `frontend/src`) ; chaque déplacement SPL n'édite plus QUE cette liste, d'une
// ligne. `lireSourceGenerateur()` concatène ces fichiers (un marqueur de
// fichier entre chaque) ; `lireSourceCoquille()` rend DevisGenerator.jsx seul.
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

//: La racine `frontend/src`.
export const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', '..')

//: Les fichiers qui composent le générateur (la coquille d'abord).
export const FILES = [
  'pages/ventes/DevisGenerator.jsx',
  'features/ventes/quote/ligneFabrique.js',
  'features/ventes/quote/ecranDefauts.js',
  'features/ventes/quote/hooks/usePersistanceDevis.js',
  'features/ventes/quote/hooks/useChargeurEdition.js',
  'features/ventes/quote/hooks/useRegistreOverrides.js',
  'pages/ventes/generator/IndicationRegistre.jsx',
  'pages/ventes/generator/PanneauSurcharges.jsx',
  'pages/ventes/generator/hooks/useLignesEcran.js',
  'pages/ventes/generator/hooks/useCompositionEcran.js',
]

//: Le marqueur posé avant le contenu de chaque fichier concaténé.
export const marqueurFichier = (rel) => `\n/* ==== fichier : ${rel} ==== */\n`

/** Le source concaténé des fichiers du générateur. */
export function lireSourceGenerateur(fichiers = FILES) {
  return fichiers.map((rel) => marqueurFichier(rel) + readFileSync(join(SRC, rel), 'utf8')).join('')
}

/** Le source de la seule coquille (DevisGenerator.jsx). */
export function lireSourceCoquille() {
  return readFileSync(join(SRC, 'pages/ventes/DevisGenerator.jsx'), 'utf8')
}

/** Les entrées de `fichiers` absentes du disque (un renommage ne rétrécit jamais le corpus en silence). */
export function fichiersManquants(fichiers = FILES) {
  return fichiers.filter((rel) => !existsSync(join(SRC, rel)))
}
