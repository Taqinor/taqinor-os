import { describe, it, expect } from 'vitest'

/* WIR13/WIR14 — Territoires (`Territoires.jsx`, NTCRM3) et Playbooks
   (`Playbooks.jsx`, NTCRM13) étaient construits/testés mais montés nulle part
   (ni route, ni menu). On vérifie ici — comme `adsengine.test.jsx`/
   `compta.test.jsx` le font pour leur propre module — que la route ET
   l'entrée de menu existent pour chacun, pointent vers le même rôle et sont
   bien collectées par le registre générique (`nav`, cf.
   router/moduleRoutes.jsx). Le reste des routes `parametres` reste
   routes-only (documenté en tête de module.config.jsx) : ce test ne vérifie
   donc pas de parité totale route↔nav, seulement ces deux ajouts. */
describe.each([
  ['WIR13', '/parametres/territoires', 'Territoires'],
  ['WIR14', '/parametres/playbooks', 'Playbooks'],
])('parametres — module.config (%s %s)', (_task, path, label) => {
  it(`déclare ${path} en route ET en entrée de menu, gatées responsable/admin`, async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('parametres')

    const route = config.routes.find((r) => r.path === path)
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['responsable', 'admin'])

    const navItem = config.nav.items.find((i) => i.to === path)
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe(label)
    expect(navItem.roles).toEqual(['responsable', 'admin'])
    expect(navItem.icon).toBeTruthy()
  })
})
