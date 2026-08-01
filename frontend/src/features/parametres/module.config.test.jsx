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
  // WIR21 — /parametres/vues (NTUX23) existait en route sans lien de menu ;
  // le rapport de gouvernance des vues sauvegardées n'a de données qu'une
  // fois les 4 écrans (devis/tickets/produits/factures) basculés au système
  // serveur (`uxviews.SavedView`), fait dans le même lot.
  ['WIR21', '/parametres/vues', 'Vues sauvegardées'],
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

/* WIR153 — Paramètres → IA : panneau de diagnostic (`IaDiagnostic.jsx`),
   admin-only (contrairement à Territoires/Playbooks ci-dessus, réservés
   responsable/admin). Même vérification route + nav collectées ensemble. */
describe('parametres — module.config (WIR153 /parametres/ia)', () => {
  it('déclare /parametres/ia en route ET en entrée de menu, gatées admin uniquement', async () => {
    const { default: config } = await import('./module.config.jsx')

    const route = config.routes.find((r) => r.path === '/parametres/ia')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['admin'])

    const navItem = config.nav.items.find((i) => i.to === '/parametres/ia')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe('IA (diagnostic)')
    expect(navItem.roles).toEqual(['admin'])
    expect(navItem.icon).toBeTruthy()
  })
})

/* ODY23 — « admin/roles/users/paramètres → app Paramètres » : le cockpit
   (/parametres, 1er item du menu) et les écrans /parametres/* qui avaient une
   route mais aucune entrée de menu gagnent enfin la leur, à l'identique du
   gating de leur route. */
describe.each([
  ['ODY23(a)', '/parametres', 'Aperçu', ['responsable', 'admin']],
  ['ODY23(c)', '/parametres/alertes-kpi', 'Alertes KPI', ['responsable', 'admin']],
  ['ODY23(c)', '/parametres/hospitality/taxe-sejour', 'Taxe de séjour', ['responsable', 'admin']],
])('parametres — module.config (%s %s)', (_task, path, label) => {
  it(`déclare ${path} en route ET en entrée de menu, gatées identiquement`, async () => {
    const { default: config } = await import('./module.config.jsx')

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

/* ODY23(c) — /parametres/export : la ROUTE reste sans `roles` (authLoader,
   préservé tel quel — cf. commentaire N97 en tête de fichier), seule la
   VISIBILITÉ du menu est admin-only ; on ne peut donc pas asserter l'égalité
   route.roles === navItem.roles comme les autres, juste l'existence. */
describe('parametres — module.config (ODY23(c) /parametres/export)', () => {
  it('déclare /parametres/export en route (sans rôle, inchangé) ET en entrée de menu admin-only', async () => {
    const { default: config } = await import('./module.config.jsx')

    const route = config.routes.find((r) => r.path === '/parametres/export')
    expect(route).toBeTruthy()
    expect(route.roles).toBeUndefined()

    const navItem = config.nav.items.find((i) => i.to === '/parametres/export')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe('Export / Sauvegarde')
    expect(navItem.roles).toEqual(['admin'])
    expect(navItem.icon).toBeTruthy()
  })
})

/* ODY23(b) — les 4 écrans réellement « Administration » (Utilisateurs/Rôles/
   Sécurité & Identité/Gouvernance des accès) rejoignent le menu de l'app
   Paramètres ; leur ROUTE reste déclarée dans
   features/admin/module.config.jsx (inchangée) — on vérifie donc seulement
   l'entrée de menu ici, pas de parité route/nav DANS ce fichier (comme pour
   Journal dans reporting). */
describe.each([
  ['/admin/users', 'Utilisateurs', ['responsable', 'admin']],
  ['/admin/roles', 'Rôles', ['responsable', 'admin']],
  ['/admin/securite-identite', 'Sécurité & Identité', ['admin']],
  ['/admin/gouvernance-acces', 'Gouvernance des accès', ['admin']],
])('parametres — module.config (ODY23(b) %s)', (path, label, roles) => {
  it(`déclare ${path} en entrée de menu "${label}" (route déjà dans features/admin/module.config.jsx)`, async () => {
    const { default: config } = await import('./module.config.jsx')
    const navItem = config.nav.items.find((i) => i.to === path)
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe(label)
    expect(navItem.roles).toEqual(roles)
    expect(navItem.icon).toBeTruthy()
    expect(config.routes.find((r) => r.path === path)).toBeFalsy()
  })
})
