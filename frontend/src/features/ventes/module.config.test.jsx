import { describe, it, expect } from 'vitest'

/* ODY16 — passe Ventes (Groupe ODY, checklist commune « module.config
   COMPLET, zéro route orpheline ») : comme `compta.test.jsx`/`adsengine.test.jsx`
   le font pour leur propre module, on vérifie ici la parité route↔nav de
   `ventes`, l'ajout du cockpit (porte d'entrée de l'app) et le sous-groupe
   `navGroup: 'facturation'` préparé pour ODX18 (`features/facturation/`).

   Deux routes RESTENT volontairement sans entrée de nav DÉDIÉE, ni bug ni
   oubli (mêmes patrons que le reste de l'ERP — actions atteintes depuis un
   écran, jamais un item de menu à part) :
     - `/ventes/devis/nouveau` — le générateur de devis (DevisGenerator),
       ouvert depuis le bouton « Nouveau devis » (DevisList, ce cockpit) ;
     - `/ventes/devis/:id` n'existe pas dans ce registre (les vues détail
       `/ventes/devis/:id/3d` et `/devis-design/:id` restent NON-MIGRABLES
       dans `router/index.jsx`, hors du périmètre de ce fichier). */
describe('ventes — module.config (ODY16 : cockpit + parité route↔nav)', () => {
  it('déclare /ventes/cockpit en route ET en PREMIER item du menu Ventes (convention nav.items[0] = cockpit)', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('ventes')

    const route = config.routes.find((r) => r.path === '/ventes/cockpit')
    expect(route).toBeTruthy()

    expect(config.nav.items[0].to).toBe('/ventes/cockpit')
    expect(config.nav.items[0].label).toBe('Cockpit')
    expect(config.nav.items[0].roles).toEqual(['normal', 'responsable', 'admin'])
    expect(config.nav.items[0].icon).toBeTruthy()

    // Le titre de page fonctionne réellement (aucun `/ventes` générique dans
    // routes.meta.js pour le masquer, contrairement à un sous-chemin de /crm).
    const title = config.titles?.find(([path]) => path === '/ventes/cockpit')
    expect(title?.[1]).toBe('Cockpit Ventes')
  })

  it('ODY16 — Factures/Avoirs/Encaissements/Relances portent `navGroup: \'facturation\'` (préparation ODX18)', async () => {
    const { default: config } = await import('./module.config.jsx')
    const FACTURATION_TARGETS = [
      '/ventes/factures', '/ventes/avoirs', '/ventes/paiements', '/ventes/relances',
    ]
    for (const to of FACTURATION_TARGETS) {
      const item = config.nav.items.find((i) => i.to === to)
      expect(item, `item ${to} introuvable`).toBeTruthy()
      expect(item.navGroup).toBe('facturation')
    }
    // Bons de commande n'est PAS de la facturation (chaîne devis→BC, pas
    // devis→facture) : aucun navGroup posé dessus.
    const bc = config.nav.items.find((i) => i.to === '/ventes/bons-commande')
    expect(bc.navGroup).toBeUndefined()
  })

  it('zéro route orpheline hors de l’exception documentée (générateur, atteint depuis un bouton)', async () => {
    const { default: config } = await import('./module.config.jsx')
    const staticRoutes = config.routes.map((r) => r.path)
    const navTargets = config.nav.items.map((i) => i.to)
    const ACTION_EXCEPTIONS = ['/ventes/devis/nouveau']

    const orphans = staticRoutes.filter(
      (p) => !navTargets.includes(p) && !ACTION_EXCEPTIONS.includes(p),
    )
    expect(orphans).toEqual([])

    // Chaque item de nav DOIT porter `roles` (BottomTabBar/Sidebar font
    // `it.roles.includes(role)` sans garde — un item sans `roles` crashe).
    for (const item of config.nav.items) {
      expect(Array.isArray(item.roles)).toBe(true)
      expect(item.roles.length).toBeGreaterThan(0)
    }
  })
})
