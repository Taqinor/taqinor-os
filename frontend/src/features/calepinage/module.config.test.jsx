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

  it('ACAL242 — `/calepinage/reglages/gabarits` est déclarée AVANT `/calepinage/:id`', async () => {
    const { default: config } = await import('./module.config.jsx')
    const chemins = config.routes.map((r) => r.path)
    const iGabarits = chemins.indexOf('/calepinage/reglages/gabarits')
    expect(iGabarits, 'route des gabarits absente').toBeGreaterThanOrEqual(0)
    expect(iGabarits).toBeLessThan(chemins.indexOf('/calepinage/:id'))
    const route = config.routes[iGabarits]
    expect(route.roles.length).toBeGreaterThan(0)
  })

  it('ACAL559 — `/calepinage/reglages/fixation` : route AVANT `/calepinage/:id` et entrée de nav', async () => {
    const { default: config } = await import('./module.config.jsx')
    const chemins = config.routes.map((r) => r.path)
    const iFixation = chemins.indexOf('/calepinage/reglages/fixation')
    expect(iFixation, 'route des systèmes de fixation absente').toBeGreaterThanOrEqual(0)
    expect(iFixation).toBeLessThan(chemins.indexOf('/calepinage/:id'))
    expect(config.nav.items.map((i) => i.to)).toContain('/calepinage/reglages/fixation')
  })

  it('ACAL893 — `/calepinage/reglages/allees` : route AVANT `/calepinage/:id`, entrée de nav et titre', async () => {
    const { default: config } = await import('./module.config.jsx')
    const chemins = config.routes.map((r) => r.path)
    const iAllees = chemins.indexOf('/calepinage/reglages/allees')
    expect(iAllees, 'route des allées absente').toBeGreaterThanOrEqual(0)
    expect(iAllees).toBeLessThan(chemins.indexOf('/calepinage/:id'))
    expect(config.nav.items.map((i) => i.to)).toContain('/calepinage/reglages/allees')
    expect(config.titles.map(([prefixe]) => prefixe)).toContain('/calepinage/reglages/allees')
  })

  it('ACAL1826 — démarrage rapide en plein écran (maquette v2) ; les autres réglages restent dans la coque de l’ERP', async () => {
    const { default: config } = await import('./module.config.jsx')
    const route = (p) => config.routes.find((r) => r.path === p)
    expect(route('/calepinage/reglages/demarrage-rapide')?.plein).toBe(true)
    expect(route('/calepinage/reglages')?.plein).toBeFalsy()
    expect(route('/calepinage/reglages/fixation')?.plein).toBeFalsy()
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

// R2-20 (Q4) — l'app n'est visible que pour qui peut la LIRE (`calepinage_voir`).
describe('calepinage — visibilité par droit de lecture (R2-20)', () => {
  it('items et routes portent perm=calepinage_voir avec repli palier', async () => {
    const { default: config } = await import('./module.config.jsx')
    for (const e of [...config.nav.items, ...config.routes]) {
      expect(e.perm, e.to || e.path).toBe('calepinage_voir')
      expect(e.permRepliPalier, e.to || e.path).toBe(true)
    }
  })

  it('un Technicien (rôle fin sans calepinage_voir) ne voit aucun item ; un commercial les voit tous', async () => {
    const { default: config } = await import('./module.config.jsx')
    const { estAutoriseEntree } = await import('../../router/moduleGating')
    const technicien = ['installation_voir', 'sav_voir', 'stock_voir']
    const commercial = ['ventes_voir', 'calepinage_voir']
    for (const item of config.nav.items) {
      expect(estAutoriseEntree(item, 'normal', technicien), item.to).toBe(false)
      expect(estAutoriseEntree(item, 'normal', commercial), item.to).toBe(true)
      // compte légacy (aucune permission servie) : repli sur le palier responsable/admin.
      expect(estAutoriseEntree(item, 'responsable', []), item.to).toBe(true)
    }
  })
})

// ACAL407 — une adresse par panneau : chaque route profonde redirige vers `?onglet=`.
describe('calepinage — routes profondes redirigées (ACAL407)', () => {
  const CLES = ['fiches', 'pompage', 'plan', 'pente', 'terrain', 'ombriere', 'schema',
    'production', 'pertes', 'horizon', 'course-soleil', 'dossiers', 'affectation']

  async function ouvrir(chemin) {
    const { Suspense } = await import('react')
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter, Routes, Route, useLocation } = await import('react-router-dom')
    const { default: config } = await import('./module.config.jsx')
    const Sonde = () => {
      const l = useLocation()
      return <div data-testid="sonde">{l.pathname + l.search}</div>
    }
    const racine = config.routes.find((r) => r.path === '/calepinage/:id')
    const profondes = config.routes.filter((r) => /^\/calepinage\/:id\/[^/]+$/.test(r.path))
    render(
      <MemoryRouter initialEntries={[chemin]}>
        <Routes>
          <Route path={racine.path} element={<Sonde />} />
          {profondes.map((r) => {
            const C = r.component
            return (
              <Route key={r.path} path={r.path}
                element={<Suspense fallback={null}><C /></Suspense>} />
            )
          })}
        </Routes>
      </MemoryRouter>,
    )
    return screen
  }

  for (const cle of CLES) {
    it(`/calepinage/9/${cle} → /calepinage/9?onglet=${cle}`, async () => {
      const screen = await ouvrir(`/calepinage/9/${cle}`)
      // REP-407 — `RedirectionOnglet` est chargé à la demande (lazy) : le premier cas paie le chargement à froid,
      // au-delà de la seconde par défaut de `findBy` sur un poste chargé.
      expect(await screen.findByTestId('sonde', {}, { timeout: 15_000 }))
        .toHaveTextContent(`/calepinage/9?onglet=${cle}`)
    }, 60_000)
  }

  it('variantes et photos ne redirigent pas', async () => {
    const { default: config } = await import('./module.config.jsx')
    const { default: Redir } = await import('./atelier/RedirectionOnglet')
    for (const fin of ['variantes', 'photos']) {
      const route = config.routes.find((r) => r.path === `/calepinage/:id/${fin}`)
      expect(route.component).not.toBe(Redir)
    }
  })
})