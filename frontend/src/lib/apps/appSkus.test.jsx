/* SOL11 — le miroir des sku/libellés reste ALIGNÉ sur le registre de modules,
   et la grille Applications est bien triée « solaire d'abord ». */
import { describe, it, expect } from 'vitest'

import {
  MANIFESTES, SKU_GENERIC, SKU_OPTIONAL, SKU_SOLAR_CORE,
  estOptionnel, estSolarCore, estVertical, libelleManifeste, rangDe, skuDe,
} from './appSkus'
import { buildInstalledApps } from './useInstalledApps'
import { grouperApps } from './appSearch'
import { moduleConfigs } from '../../router/moduleRoutes'

/* Clés de module FRONTEND sans manifeste backend : surfaces purement front
   (mondes opérationnels d'une app existante, coquilles techniques). Elles sont
   traitées comme `generic` — jamais masquées par ce fichier. Toute NOUVELLE
   clé sans manifeste doit être ajoutée ici DÉLIBÉRÉMENT, ce qui est le but de
   la garde : personne ne perd une app par oubli. */
const SANS_MANIFESTE_BACKEND = new Set([
  'admin', 'auth', 'core', 'customobjects', 'ia', 'kanban', 'logistique',
  'magasin', 'messaging', 'pwa', 'queue', 'workflow',
])

describe('SOL11 — miroir des manifestes', () => {
  it('chaque module du registre est connu (ou toléré explicitement)', () => {
    const inconnus = moduleConfigs
      .map((c) => c.key)
      .filter((k) => k && !MANIFESTES[k] && !SANS_MANIFESTE_BACKEND.has(k))
    expect(inconnus).toEqual([])
  })

  it('une clé sans manifeste est traitée comme générique', () => {
    expect(skuDe('magasin')).toBe(SKU_GENERIC)
    expect(skuDe('cle-qui-nexiste-pas')).toBe(SKU_GENERIC)
    expect(libelleManifeste('cle-qui-nexiste-pas')).toBeNull()
  })

  it('les sku du cœur solaire, du socle et des extensions sont ceux du backend', () => {
    expect(skuDe('crm')).toBe(SKU_SOLAR_CORE)
    expect(skuDe('ventes')).toBe(SKU_SOLAR_CORE)
    expect(skuDe('installations')).toBe(SKU_SOLAR_CORE)
    expect(skuDe('compta')).toBe(SKU_GENERIC)
    expect(skuDe('rh')).toBe(SKU_GENERIC)
    expect(skuDe('pos')).toBe(SKU_OPTIONAL)
    expect(skuDe('scm')).toBe(SKU_OPTIONAL)
    expect(estSolarCore('crm')).toBe(true)
    expect(estOptionnel('douane')).toBe(true)
  })

  it('les six verticaux parqués sont marqués vertical_*', () => {
    for (const cle of ['agriculture', 'education', 'hospitality',
      'immobilier', 'mrp', 'sante']) {
      expect(estVertical(cle)).toBe(true)
    }
    expect(estVertical('crm')).toBe(false)
  })

  it('le rang de tri met le solaire devant, les extensions derrière', () => {
    expect(rangDe('crm')).toBeLessThan(rangDe('compta'))
    expect(rangDe('compta')).toBeLessThan(rangDe('pos'))
  })

  it('les libellés du manifeste sont des libellés FR courts', () => {
    expect(libelleManifeste('compta')).toBe('Comptabilité')
    expect(libelleManifeste('mrp')).toBe('Production (MRP)')
    for (const [cle, entree] of Object.entries(MANIFESTES)) {
      expect(entree.libelle, cle).toBeTruthy()
      expect(entree.libelle.length, cle).toBeLessThanOrEqual(40)
    }
  })
})

function configs(...cles) {
  return cles.map((key, i) => ({
    key,
    order: i,
    nav: { label: key.toUpperCase(), items: [{ to: `/${key}`, roles: ['normal'] }] },
  }))
}

describe('SOL11 — grille Applications triée solaire', () => {
  const opts = { role: 'normal', permissions: [] }

  it('le cœur solaire passe devant le socle et les extensions', () => {
    const apps = buildInstalledApps(
      configs('pos', 'compta', 'crm', 'douane', 'rh', 'ventes'), opts)
    expect(apps.map((a) => a.key)).toEqual(
      ['crm', 'ventes', 'compta', 'rh', 'pos', 'douane'])
  })

  it('le tri est STABLE à rang égal (ordre du registre conservé)', () => {
    const apps = buildInstalledApps(configs('rh', 'compta', 'ged'), opts)
    expect(apps.map((a) => a.key)).toEqual(['rh', 'compta', 'ged'])
  })

  it('chaque app porte son sku et son libellé de manifeste', () => {
    const [app] = buildInstalledApps(configs('crm'), opts)
    expect(app.sku).toBe(SKU_SOLAR_CORE)
    expect(app.libelleManifeste).toBe('CRM')
  })

  it('un module désactivé pour la société reste absent (ODX6 inchangé)', () => {
    const apps = buildInstalledApps(
      configs('crm', 'pos'), { ...opts, disabledModules: ['pos'] })
    expect(apps.map((a) => a.key)).toEqual(['crm'])
  })

  it('les extensions forment leur propre section', () => {
    const apps = buildInstalledApps(
      configs('crm', 'compta', 'pos', 'transport'), opts)
    const sections = grouperApps(apps, { query: '', pinned: [], recent: [] })
    const parId = Object.fromEntries(
      sections.map((s) => [s.id, s.apps.map((a) => a.key)]))
    expect(parId.toutes).toEqual(['crm', 'compta'])
    expect(parId.extensions).toEqual(['pos', 'transport'])
    expect(sections.find((s) => s.id === 'extensions').titre).toBe('Extensions')
  })

  it("pas d'extension installée ⇒ pas de section vide", () => {
    const apps = buildInstalledApps(configs('crm', 'compta'), opts)
    const sections = grouperApps(apps, { query: '', pinned: [], recent: [] })
    expect(sections.map((s) => s.id)).toEqual(['toutes'])
  })

  it('en recherche, une seule section « Résultats » (comportement ODY2)', () => {
    const apps = buildInstalledApps(configs('crm', 'pos'), opts)
    const sections = grouperApps(apps, { query: 'pos', pinned: [], recent: [] })
    expect(sections.map((s) => s.id)).toEqual(['resultats'])
  })
})
