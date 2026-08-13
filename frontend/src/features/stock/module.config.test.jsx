import { describe, it, expect } from 'vitest'

/* ODY17 — Passe Stock + Magasin/Logistique (Groupe ODY, checklist commune :
   « module.config COMPLET — zéro route orpheline vs router/index.jsx »).
   `router/index.jsx` n'a PLUS aucune route stock en dur (migrées ARC48) :
   la vérification porte donc sur la parité route ↔ nav DE CE FICHIER, comme
   `crm/module.config.test.jsx`/`reporting/module.config.test.jsx` le font
   pour leur propre module. Les routes paramétrées (`:id`) restent, comme
   ailleurs, ouvertes par un LIEN depuis leur écran d'origine plutôt que par
   une entrée de menu dédiée — documenté ici, pas un oubli. */
describe('stock — module.config (ODY17)', () => {
  it('déclare des métadonnées d\'app (icône/description) miroir du manifest backend', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('stock')
    expect(config.icon).toBeTruthy()
    // Miroir exact de apps/stock/apps.py::module_manifest.description.
    expect(config.description).toBe('Gestion des stocks, mouvements et fournisseurs.')
  })

  it('zéro route orpheline : chaque route non paramétrée a une entrée de nav', async () => {
    const { default: config } = await import('./module.config.jsx')
    // Seule route paramétrée du module : la fiche 360 fournisseur, atteinte
    // par un lien depuis /stock/fournisseurs (comme FournisseurFiche360
    // partout ailleurs dans l'app) — jamais une entrée de nav dédiée.
    const PARAM_ROUTES_EXEMPTES = new Set(['/stock/fournisseurs/:id/360'])
    const navPaths = new Set(config.nav.items.map((i) => i.to))
    const orphelines = config.routes
      .map((r) => r.path)
      .filter((p) => !PARAM_ROUTES_EXEMPTES.has(p) && !navPaths.has(p))
    expect(orphelines).toEqual([])
  })

  it('sous-groupe ACHATS (ODX20) : nav et routes portent le MÊME tag group="achats"', async () => {
    const { default: config } = await import('./module.config.jsx')
    const navAchats = config.nav.items.filter((i) => i.group === 'achats').map((i) => i.to).sort()
    const routesAchats = config.routes.filter((r) => r.group === 'achats').map((r) => r.path).sort()
    // PACT51 a ajouté le registre consolidé des paiements fournisseur au
    // sous-groupe ACHATS (nav ET routes, même tag `group: 'achats'`) —
    // liste élargie de 5 à 6 écrans en conséquence.
    const attendu = [
      '/stock/bons-commande-fournisseur',
      '/stock/factures-fournisseur',
      '/stock/modeles-bcf',
      '/stock/paiements-fournisseur',
      '/stock/receptions-fournisseur',
      '/stock/retours-fournisseur',
    ].sort()
    expect(navAchats).toEqual(attendu)
    expect(routesAchats).toEqual(attendu)
    // « Fournisseurs » (répertoire) et « Import OCR » restent hors du lot —
    // PrixFournisseur mis à part, le module-map ODX19/20 ne les déplace pas.
    expect(navAchats).not.toContain('/stock/fournisseurs')
    expect(navAchats).not.toContain('/stock/ocr-import')
  })

  it('nav ≤ 2 niveaux : les items sont une liste plate (aucun sous-menu imbriqué)', async () => {
    const { default: config } = await import('./module.config.jsx')
    for (const item of config.nav.items) {
      expect(item.items).toBeUndefined()
      expect(item.children).toBeUndefined()
    }
  })
})
