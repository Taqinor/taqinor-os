import { describe, it, expect } from 'vitest'

/* ODY18 — Passe Chantiers/Installations + Interventions (Groupe ODY,
   checklist commune : « module.config COMPLET — zéro route orpheline vs
   router/index.jsx »). `router/index.jsx` n'a PLUS aucune route chantiers/
   interventions/production en dur (migrées ARC54) : la vérification porte
   donc sur la parité route ↔ nav DE CE FICHIER, comme
   `crm/module.config.test.jsx`/`reporting/module.config.test.jsx` le font
   pour leur propre module. */
describe('installations — module.config (ODY18)', () => {
  it('déclare des métadonnées d\'app (icône/description) miroir du manifest backend', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('installations')
    expect(config.icon).toBeTruthy()
    // Miroir exact de apps/installations/apps.py::module_manifest.description.
    expect(config.description).toBe('Installations et interventions terrain.')
  })

  it('zéro route orpheline : chaque route est en nav OU couverte par MonitoringNav (WR6)', async () => {
    const { default: config } = await import('./module.config.jsx')
    // WR6 (pages/monitoring/MonitoringNav.jsx) : la Sidebar ne porte QU'UNE
    // entrée « Production » (`/production`) ; les 8 écrans de la suite O&M
    // (parc/analytique/garanties/CO₂/nettoyages/rapports/portail-client, plus
    // Abonnements qui a EN PLUS sa propre entrée de nav) restent atteignables
    // via le bandeau de navigation EN PAGE de `/production` — délibéré,
    // « Additif : aucune entrée de Sidebar n'est modifiée » (commentaire WR6
    // d'origine). Ce ne sont donc PAS des orphelines au sens de la Sidebar
    // globale, seulement d'un second niveau de nav propre à l'app (≤ 2
    // niveaux : Sidebar → bandeau `/production`).
    const COUVERTES_PAR_MONITORING_NAV = new Set([
      '/production/parc',
      '/production/analytique',
      '/production/garanties',
      '/production/co2',
      '/production/nettoyages',
      '/production/rapports',
      '/production/portail-client',
    ])
    const navPaths = new Set(config.nav.items.map((i) => i.to))
    const orphelines = config.routes
      .map((r) => r.path)
      .filter((p) => !navPaths.has(p) && !COUVERTES_PAR_MONITORING_NAV.has(p))
    expect(orphelines).toEqual([])
  })

  it('nav ≤ 2 niveaux : les items sont une liste plate (aucun sous-menu imbriqué)', async () => {
    const { default: config } = await import('./module.config.jsx')
    for (const item of config.nav.items) {
      expect(item.items).toBeUndefined()
      expect(item.children).toBeUndefined()
    }
  })
})
