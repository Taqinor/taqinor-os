import { describe, it, expect } from 'vitest'

/* WIR17(a) — « Cohortes » (`CohortsPage.jsx`, FG98) avait déjà sa route
   (`/reporting/cohortes`, gatée responsable/admin) mais aucune entrée de menu
   ANALYSE : on vérifie ici — comme `adsengine.test.jsx`/`compta.test.jsx` le
   font pour leur propre module — que route et nav existent et pointent vers
   le même rôle. Le reste des routes `reporting` (ex. archive client/chantier,
   dashboards) reste sans entrée de nav dédiée (ouvertes par clic depuis leur
   écran d'origine) : ce test ne vérifie donc pas de parité totale route↔nav,
   seulement l'ajout WIR17(a). */
describe('reporting — module.config (WIR17 Cohortes)', () => {
  it('déclare /reporting/cohortes en route ET en entrée du menu ANALYSE, gatées responsable/admin', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('reporting')

    const route = config.routes.find((r) => r.path === '/reporting/cohortes')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['responsable', 'admin'])

    const navItem = config.nav.items.find((i) => i.to === '/reporting/cohortes')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe('Cohortes')
    expect(navItem.roles).toEqual(['responsable', 'admin'])
    expect(navItem.icon).toBeTruthy()
  })
})

/* ODY23 — « Reporting/Rapports/Journal → app Rapports ». Le Journal
   d'activité gagne une entrée dans le menu ANALYSE ; sa ROUTE reste déclarée
   dans features/parametres/module.config.jsx (inchangée) — on vérifie donc
   ici seulement l'entrée de nav, pas de parité route/nav dans CE fichier. */
describe('reporting — module.config (ODY23 Journal)', () => {
  it('déclare /journal en entrée du menu ANALYSE, gatée normal/responsable/admin + permission dédiée', async () => {
    const { default: config } = await import('./module.config.jsx')

    const navItem = config.nav.items.find((i) => i.to === '/journal')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe("Journal d'activité")
    expect(navItem.roles).toEqual(['normal', 'responsable', 'admin'])
    expect(navItem.perm).toBe('journal_activite_voir')
    expect(navItem.icon).toBeTruthy()

    // La route /journal n'est PAS redéclarée ici (elle vit dans parametres).
    expect(config.routes.find((r) => r.path === '/journal')).toBeFalsy()
  })
})
