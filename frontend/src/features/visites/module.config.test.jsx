/* VTA12 — le module.config de l'app Visites : parité route↔nav et GATING.

   L'enjeu de tout le groupe VTA tient ici : un « Commercial terrain » (palier
   `normal`, permissions `visites_voir/creer/modifier` + `app_visites_voir`,
   SANS aucune permission crm) doit pouvoir ouvrir SON app — et ne doit voir
   NI les vues d'équipe NI le CRM. La règle de visibilité est celle de
   `router/moduleGating.js::estAutoriseEntree` (source unique, partagée avec
   la Sidebar, la BottomTabBar, l'AppLauncher et le roleLoader) : on la rejoue
   telle quelle plutôt que d'en réécrire une copie.
*/
import { describe, it, expect } from 'vitest'
import { estAutoriseEntree } from '../../router/moduleGating'
import config from './module.config.jsx'
import crmConfig from '../crm/module.config.jsx'

const TERRAIN = {
  role: 'normal',
  permissions: ['visites_voir', 'visites_creer', 'visites_modifier', 'app_visites_voir'],
}
const RESPONSABLE = {
  role: 'responsable',
  permissions: ['visites_voir', 'visites_valider', 'crm_voir'],
}

const visible = (entree, qui) => estAutoriseEntree(entree, qui.role, qui.permissions)

describe('visites — module.config (VTA8/VTA16)', () => {
  it('porte la clé du manifeste backend et a « Ma journée » pour porte d’entrée', () => {
    expect(config.key).toBe('visites')
    expect(config.nav.items[0].to).toBe('/visites')
    expect(config.nav.items[0].label).toBe('Ma journée')
  })

  it('n’utilise PAS /ma-journee (chemin déjà pris par installations)', () => {
    for (const r of config.routes) expect(r.path).not.toBe('/ma-journee')
    for (const i of config.nav.items) expect(i.to).not.toBe('/ma-journee')
  })

  it('parité : chaque entrée de nav a sa route (zéro menu mort)', () => {
    const chemins = new Set(config.routes.map((r) => r.path))
    for (const item of config.nav.items) expect(chemins.has(item.to)).toBe(true)
  })

  it('les vues d’ÉQUIPE et l’administration sont gatées `visites_valider`', () => {
    for (const chemin of ['/visites/toutes', '/visites/revue', '/visites/planifier']) {
      const item = config.nav.items.find((i) => i.to === chemin)
      const route = config.routes.find((r) => r.path === chemin)
      expect(item.perm).toBe('visites_valider')
      expect(route.perm).toBe('visites_valider')
    }
  })
})

describe('visites — gating du rôle « Commercial terrain »', () => {
  it('voit son app : « Ma journée » et le wizard lui sont ouverts', () => {
    expect(visible(config.nav.items[0], TERRAIN)).toBe(true)
    const wizard = config.routes.find((r) => r.path === '/visites/:id')
    expect(visible(wizard, TERRAIN)).toBe(true)
  })

  it('est REFUSÉ proprement sur les vues d’équipe et la planification', () => {
    for (const chemin of ['/visites/toutes', '/visites/revue', '/visites/planifier']) {
      const route = config.routes.find((r) => r.path === chemin)
      expect(visible(route, TERRAIN)).toBe(false)
    }
  })

  it('ne voit AUCUNE entrée du menu CRM (il n’a aucune permission crm)', () => {
    // Le CRM garde ses entrées au palier `normal` : ce qui ferme la porte à
    // un terrain est le refus SERVEUR (403 sur /crm/leads/, VTA4) — on vérifie
    // surtout qu'aucune entrée visite n'est RESTÉE côté CRM après le move.
    const restees = crmConfig.nav.items.filter((i) => String(i.to).includes('visite'))
    expect(restees).toEqual([])
    const routesRestees = crmConfig.routes.filter((r) => String(r.path).includes('visite'))
    expect(routesRestees).toEqual([])
  })

  it('un responsable, lui, voit les vues d’équipe', () => {
    for (const chemin of ['/visites/toutes', '/visites/revue', '/visites/planifier']) {
      const route = config.routes.find((r) => r.path === chemin)
      expect(visible(route, RESPONSABLE)).toBe(true)
    }
  })
})
