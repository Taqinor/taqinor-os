import { describe, it, expect } from 'vitest'

/* WIR13 — Territoires (`Territoires.jsx`, NTCRM3) était construit/testé mais
   monté nulle part (ni route, ni menu). On vérifie ici — comme
   `adsengine.test.jsx`/`compta.test.jsx` le font pour leur propre module — que
   la route ET l'entrée de menu existent, pointent vers le même composant/rôle
   et sont bien collectées par le registre générique (`nav`, cf.
   router/moduleRoutes.jsx). Le reste des routes `parametres` reste
   routes-only (documenté en tête de module.config.jsx) : ce test ne vérifie
   donc pas de parité totale route↔nav, seulement l'ajout WIR13. */
describe('parametres — module.config (WIR13 Territoires)', () => {
  it('déclare /parametres/territoires en route ET en entrée de menu, gatées responsable/admin', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('parametres')

    const route = config.routes.find((r) => r.path === '/parametres/territoires')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['responsable', 'admin'])

    const navItem = config.nav.items.find((i) => i.to === '/parametres/territoires')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe('Territoires')
    expect(navItem.roles).toEqual(['responsable', 'admin'])
    expect(navItem.icon).toBeTruthy()
  })
})
