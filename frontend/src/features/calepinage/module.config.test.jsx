import { describe, it, expect, beforeEach, vi } from 'vitest'

/* ============================================================================
   CAL34 — le registre du module Calepinage, vérifié sur le REGISTRE RÉEL.
   ----------------------------------------------------------------------------
   Ce que ce fichier empêche :
     * une clé qui diverge du `module_manifest` backend (`scripts/check_modules.py`
       la relit côté CI ; ici on fige l'intention côté écran) ;
     * une collision d'`order` avec un autre module — qui ferait basculer deux
       apps de place dans le portail sans que personne n'y touche ;
     * une entrée de nav qui ne mène nulle part (incident du 03/08/2026 : 61
       écrans livrés, 7 atteignables) ;
     * un item de nav SANS `roles` — la Sidebar plante à l'ouverture ;
     * l'inversion `/calepinage/:id` avant `/calepinage/nouveau`, qui rendrait
       l'écran de création injoignable.
   ========================================================================== */

beforeEach(() => vi.clearAllMocks())

/* `router/moduleRoutes` importe le registre ENTIER (glob eager sur tous les
   `module.config.jsx` du produit) : sa premiere resolution coute des dizaines
   de secondes sous charge, au-dela des 20 s par defaut de Vitest. Les deux
   tests qui en dependent portent donc leur propre delai — on n'ampute aucune
   assertion pour tenir dans un budget de temps. */
const DELAI_REGISTRE = 120_000

describe('calepinage — module.config (CAL34)', () => {
  it("déclare la clé 'calepinage' — ancrage de corrélation avec le manifest backend", async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('calepinage')
  })

  it("porte l'ordre 98 et un glyphe d'app propre (ODY34)", async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.order).toBe(98)
    expect(config.nav.icon).toBeTruthy()
  })

  /* L'ordre 98 est LIBRE : aucun autre module ne le porte. On n'assène pas
     l'unicité globale des `order` — le registre porte des doublons ANTÉRIEURS
     à cette lane (92 et 96 sont partagés), et une garde qui rougit pour la
     dette d'autrui finit désactivée. On garde donc l'invariant que CETTE lane
     doit tenir : 98 n'appartient qu'à `calepinage`. */
  it("porte un `order` que personne d'autre n'occupe", async () => {
    const { moduleConfigs } = await import('../../router/moduleRoutes')
    expect(moduleConfigs.length, 'registre vide : le glob n’a rien collecté').toBeGreaterThan(0)
    const surLOrdre98 = moduleConfigs.filter((c) => c?.order === 98).map((c) => c?.key)
    expect(surLOrdre98, `ordre 98 partagé : ${surLOrdre98.join(', ')}`).toEqual(['calepinage'])
  }, DELAI_REGISTRE)

  it('le module est bien collecté par le registre, avec sa clé', async () => {
    const { moduleConfigs } = await import('../../router/moduleRoutes')
    expect(moduleConfigs.map((c) => c?.key)).toContain('calepinage')
  }, DELAI_REGISTRE)

  it('aucune entrée de nav orpheline : chaque `to` correspond à une route déclarée', async () => {
    const { default: config } = await import('./module.config.jsx')
    const chemins = new Set(config.routes.map((r) => r.path))
    const orphelines = config.nav.items.filter((item) => !chemins.has(item.to))
    expect(orphelines.map((i) => i.to)).toEqual([])
  })

  it('CHAQUE item de nav déclare ses `roles` — un item sans rôles fait planter la Sidebar', async () => {
    const { default: config } = await import('./module.config.jsx')
    for (const item of config.nav.items) {
      expect(Array.isArray(item.roles), `item de nav sans roles : ${item.to}`).toBe(true)
      expect(item.roles.length, `roles vides : ${item.to}`).toBeGreaterThan(0)
    }
  })

  it('CHAQUE route déclare ses `roles` — une URL tapée à la main doit porter la même garde', async () => {
    const { default: config } = await import('./module.config.jsx')
    for (const route of config.routes) {
      expect(Array.isArray(route.roles), `route sans roles : ${route.path}`).toBe(true)
      expect(route.component, `route sans composant : ${route.path}`).toBeTruthy()
    }
  })

  it('`/calepinage/nouveau` est déclarée AVANT `/calepinage/:id`', async () => {
    const { default: config } = await import('./module.config.jsx')
    const chemins = config.routes.map((r) => r.path)
    const iNouveau = chemins.indexOf('/calepinage/nouveau')
    const iDetail = chemins.indexOf('/calepinage/:id')
    expect(iNouveau, 'route de création absente').toBeGreaterThanOrEqual(0)
    expect(iDetail, 'route d’atelier absente').toBeGreaterThanOrEqual(0)
    expect(iNouveau).toBeLessThan(iDetail)
  })

  it('les trois routes du module vivent toutes sous le préfixe `/calepinage`', async () => {
    const { default: config } = await import('./module.config.jsx')
    for (const route of config.routes) {
      expect(route.path.startsWith('/calepinage')).toBe(true)
    }
    expect(config.sectionLabels).toEqual({ calepinage: 'Calepinage' })
  })

  it('les titres vont du plus SPÉCIFIQUE au plus général (correspondance par préfixe)', async () => {
    const { default: config } = await import('./module.config.jsx')
    const chemins = config.titles.map(([prefixe]) => prefixe)
    for (let i = 0; i < chemins.length; i += 1) {
      for (let j = i + 1; j < chemins.length; j += 1) {
        expect(
          chemins[i].startsWith(chemins[j]) || !chemins[j].startsWith(chemins[i]),
          `« ${chemins[j]} » est plus spécifique que « ${chemins[i] }» et doit passer avant`,
        ).toBe(true)
      }
    }
  })
})
