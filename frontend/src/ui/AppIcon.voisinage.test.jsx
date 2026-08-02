// ODY34 — VOISINAGE : jamais deux tuiles identiques côte à côte.
// ----------------------------------------------------------------------------
// La variante de teinte (`varianteTuile`, AppIcon.jsx) existe pour que les
// 13 apps « lune » ou les 5 apps « azur » ne se ressemblent pas dans la grille.
// Avec la graine djb2 d'origine (5381) elle ratait justement ce pour quoi elle
// existe : le portail par défaut posait Assurances et FP&A côte à côte dans la
// même couleur, et Santé et Éducation aussi.
//
// L'invariant testé ici est INDÉPENDANT DE LA MISE EN PAGE : deux apps
// CONSÉCUTIVES dans l'ordre du registre ne portent jamais la même couleur.
// Comme la grille remplit les rangées dans cet ordre, deux tuiles voisines
// HORIZONTALEMENT sont toujours consécutives — quelle que soit la largeur
// (3 colonnes au pouce, 4, jusqu'à 8+ en bureau). Il reste des coïncidences
// verticales possibles (une rangée d'écart) : moins gênantes, et impossibles à
// supprimer toutes avec 3 variantes pour 13 apps d'une même voie.
//
// Si une app est ajoutée/déplacée et que ce test rougit : changer `GRAINE_TUILE`
// dans AppIcon.jsx (n'importe quel entier — c'est un tirage, pas une constante
// magique) jusqu'à ce qu'il repasse au vert.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { moduleConfigs } from '../router/moduleRoutes'
import { buildInstalledApps } from '../lib/apps/useInstalledApps'
import { varianteTuile } from './AppIcon'

const TOKENS = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), '../design/tokens.css'), 'utf8',
)

/* `--app-tile-primary-N` est un ALIAS décalé de `--app-tile-brass-M` : deux
   clés d'accent, UNE seule famille de couleurs. Sans résoudre l'alias, ce test
   croirait Santé (`primary`) et Caisse (`brass`) différentes alors qu'elles
   peuvent rendre exactement le même pixel. La table est LUE dans tokens.css —
   jamais recopiée ici, sinon elle dériverait. */
const ALIAS = new Map(
  [...TOKENS.matchAll(/--app-tile-(\w+-\d): var\(--app-tile-(\w+-\d)\)/g)]
    .map((m) => [m[1], m[2]]),
)

/* Couleur RÉELLEMENT rendue par AppIcon pour une app : même expression que le
   composant (`--app-tile-<voie>-<variante>`), alias résolu. */
function couleurDe(app) {
  const voie = app.accent || 'nuit' // `VOIE_SANS_ACCENT` d'AppIcon.jsx
  const brut = `${voie}-${varianteTuile(app.key)}`
  return ALIAS.get(brut) ?? brut
}

// L'ordre du registre = l'ordre de la grille (`useInstalledApps` → HomeMenu).
const apps = buildInstalledApps(moduleConfigs, { role: 'admin', permissions: [] })

describe('ODY34 — voisinage des tuiles', () => {
  it('deux apps CONSÉCUTIVES ne portent jamais la même couleur', () => {
    const couleurs = apps.map(couleurDe)
    const jumelles = []
    for (let i = 1; i < couleurs.length; i += 1) {
      if (couleurs[i] === couleurs[i - 1]) {
        jumelles.push(`${apps[i - 1].key} + ${apps[i].key} (${couleurs[i]})`)
      }
    }
    expect(jumelles, `tuiles jumelles côte à côte : ${jumelles.join(' | ')}`).toEqual([])
  })

  it('toute couleur résolue existe VRAIMENT dans tokens.css', () => {
    // Le piège déjà rencontré : cinq module.config déclaraient `accent:
    // 'primary'` avant que le jeton n'existe — `var()` invalide, tuiles SANS
    // fond. Une nouvelle clé d'accent inventée doit rougir ici, pas à l'écran.
    const manquantes = [...new Set(apps.map(couleurDe))]
      .filter((c) => !TOKENS.includes(`--app-tile-${c}:`))
    expect(manquantes, `jetons absents : ${manquantes.join(', ')}`).toEqual([])
  })

  it('les apps sans accent déclaré ne sont plus toutes de la même couleur', () => {
    // Immobilier et Tiers rendaient exactement `--app-tile-defaut`, comme
    // Comptabilité et Paramètres : quatre tuiles identiques dans la grille.
    const sansAccent = apps.filter((a) => !a.accent)
    expect(sansAccent.length).toBeGreaterThanOrEqual(2)
    expect(new Set(sansAccent.map(couleurDe)).size).toBeGreaterThan(1)
  })
})
