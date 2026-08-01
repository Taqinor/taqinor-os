import { describe, it, expect } from 'vitest'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))

/* ODY20 — Passe Compta : le module était DÉJÀ complet (13 routes ↔ 13 items
   de nav, zéro orpheline) avant cette tâche — ce test verrouille l'invariant
   pour la suite, comme `crm/module.config.test.jsx` /
   `reporting/module.config.test.jsx` le font pour leur propre ajout.

   Deux garde-fous explicites (contraintes fondateur de la tâche ODY20) :
   - les notes de frais restent une SECTION de Compta (`/comptabilite/
     notes-de-frais`), jamais une tuile « Frais » séparée ;
   - le portail client (`/portail-contrats/:token`, route PUBLIQUE à jeton,
     router/index.jsx) n'apparaît PAS dans ce module — ce n'est pas une tuile
     d'app. */
describe('compta — module.config (ODY20)', () => {
  it('zéro route orpheline : chaque route a une entrée de nav et réciproquement', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('compta')

    const navPaths = new Set(config.nav.items.map((i) => i.to))
    for (const r of config.routes) {
      expect(navPaths.has(r.path)).toBe(true)
    }
    const routePaths = new Set(config.routes.map((r) => r.path))
    for (const to of navPaths) {
      expect(routePaths.has(to)).toBe(true)
    }
  })

  it('notes de frais = section de Compta, pas de tuile séparée', async () => {
    const { default: config } = await import('./module.config.jsx')
    const navItem = config.nav.items.find((i) => i.to === '/comptabilite/notes-de-frais')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe('Notes de frais')
    // Aucune tuile « Frais » séparée (interdite sans décision fondateur — NE
    // PAS FAIRE Groupe ODY) : pas de dossier features/frais/module.config.jsx.
    expect(existsSync(path.join(HERE, '..', 'frais', 'module.config.jsx'))).toBe(false)
  })

  it('ne référence pas le portail client public à jeton', async () => {
    const { default: config } = await import('./module.config.jsx')
    const hasPortail = config.routes.some((r) => r.path.includes('portail-contrats'))
      || config.nav.items.some((i) => i.to.includes('portail-contrats'))
    expect(hasPortail).toBe(false)
  })
})
