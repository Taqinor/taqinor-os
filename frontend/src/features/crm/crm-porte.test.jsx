// APX1 — LE VERROU de la porte du CRM (fondateur 2026-08-01 : « the Lead part
// is the opening of the CRM »).
// ----------------------------------------------------------------------------
// Constat qui a motivé cette tâche : le CRM avait DEUX portes contradictoires.
// Le lanceur (VX9), les épinglés (VX10) et la préférence d'atterrissage (VX46)
// dérivent tous leur cible de `nav.items[0].to`, tandis que le fil d'Ariane
// (`routes.meta.js`) pointait en DUR sur `/crm` (Clients). Selon la surface
// empruntée, entrer dans « CRM » ouvrait Calendrier, puis Cockpit (ODY15), ou
// Clients — jamais les Leads.
//
// Ce fichier verrouille les QUATRE surfaces sur `/crm/leads` d'un seul coup.
// Il teste les RÉSOLVEURS RÉELS (`buildInstalledApps`, `resolveLandingPath`,
// `SECTION_LABELS`), jamais une copie de leur logique : si l'un d'eux change de
// convention, ce test rougit — c'est exactement son rôle.
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import crmConfig from './module.config.jsx'
import { buildInstalledApps } from '../../lib/apps/useInstalledApps'
import { iconNodeForApp } from '../../lib/apps/appIcon'
import { resolveLandingPath, LANDING_KEY } from '../../pages/preferences/prefs'
import { SECTION_LABELS } from '../../components/layout/routes.meta'

const PORTE_CRM = '/crm/leads'

beforeEach(() => { window.localStorage.clear() })
afterEach(() => { window.localStorage.clear() })

describe('APX1 — la porte du CRM est /crm/leads sur les 4 surfaces', () => {
  it('surface 1/4 — module.config : Leads est items[0] (convention « cockpit du module »)', () => {
    expect(crmConfig.nav.items[0].to).toBe(PORTE_CRM)
    expect(crmConfig.nav.items[0].label).toBe('Leads')
    // La route existe bel et bien (une porte qui 404 n'est pas une porte).
    expect(crmConfig.routes.some((r) => r.path === PORTE_CRM)).toBe(true)
  })

  it('surface 2/4 — lanceur d’apps + épinglés : useInstalledApps() résout le CRM sur /crm/leads', () => {
    // Les deux surfaces consomment la MÊME entrée (`entry.to`) de ce résolveur.
    const apps = buildInstalledApps([crmConfig], { role: 'normal', permissions: [] })
    const crm = apps.find((a) => a.key === 'crm')
    expect(crm).toBeTruthy()
    expect(crm.to).toBe(PORTE_CRM)
  })

  it('surface 3/4 — atterrissage post-login (VX46) : la préférence « crm » mène aux Leads', () => {
    window.localStorage.setItem(LANDING_KEY, 'crm')
    expect(resolveLandingPath([crmConfig], '')).toBe(PORTE_CRM)
    // ... et le « dernier module visité » (VX11) aussi.
    window.localStorage.setItem(LANDING_KEY, '__dernier__')
    expect(resolveLandingPath([crmConfig], 'crm')).toBe(PORTE_CRM)
  })

  it('surface 4/4 — fil d’Ariane : tous les segments étiquetés « CRM » pointent la même porte', () => {
    const crmSections = Object.entries(SECTION_LABELS).filter(([, v]) => v?.label === 'CRM')
    // Au minimum `crm`, `activites`, `calendrier` (routes.meta.js).
    expect(crmSections.length).toBeGreaterThanOrEqual(3)
    for (const [segment, meta] of crmSections) {
      expect(`${segment}:${meta.to}`).toBe(`${segment}:${PORTE_CRM}`)
    }
  })

  it('l’icône de l’app CRM est celle du MODULE : stable si les items sont réordonnés', () => {
    expect(crmConfig.nav.icon).toBeTruthy()

    const iconApp = buildInstalledApps([crmConfig], { role: 'normal', permissions: [] })[0].icon
    // Les 4 surfaces ODY9 passent soit par useInstalledApps(), soit par
    // iconNodeForApp() : les deux doivent rendre le MÊME nœud.
    expect(iconApp).toBe(crmConfig.nav.icon)

    // Ordre inversé : le glyphe ne bouge pas (c'est tout l'intérêt de nav.icon).
    const inverse = { ...crmConfig, nav: { ...crmConfig.nav, items: [...crmConfig.nav.items].reverse() } }
    expect(buildInstalledApps([inverse], { role: 'normal', permissions: [] })[0].icon).toBe(crmConfig.nav.icon)
  })

  it('iconNodeForApp(‘crm’) — la 4ᵉ surface ODY9 (écran Applications) rend le même glyphe', () => {
    expect(iconNodeForApp('crm')).toBe(crmConfig.nav.icon)
  })

  it('un module SANS nav.icon garde le comportement ODY1 (icône du 1er item visible)', () => {
    const sansIcone = {
      key: 'demo',
      nav: { label: 'Démo', items: [{ to: '/demo', icon: 'GLYPHE', roles: ['normal'] }] },
    }
    const apps = buildInstalledApps([sansIcone], { role: 'normal', permissions: [] })
    expect(apps[0].icon).toBe('GLYPHE')
  })
})

describe('APX1 — les liens morts /crm/clients/:id sont éradiqués', () => {
  it('aucune route `/crm/clients/...` n’existe côté routeur (le 404 était réel)', () => {
    expect(crmConfig.routes.some((r) => r.path.startsWith('/crm/clients'))).toBe(false)
    // Le lien profond vivant, lu par ClientList.jsx (VX220).
    expect(crmConfig.routes.some((r) => r.path === '/crm')).toBe(true)
  })
})
