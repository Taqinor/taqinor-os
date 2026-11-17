import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import process from 'node:process'
import { act, render, screen, within } from '@testing-library/react'
import { Suspense } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MANIFESTES } from '../../lib/apps/appSkus'
import { buildInstalledApps } from '../../lib/apps/useInstalledApps'
import { estAutoriseEntree } from '../../router/moduleGating'
import { moduleConfigs, moduleNavSections } from '../../router/moduleRoutes'
import config from './module.config'
import { useEnLigne } from './lib/enLigne'

/* TCH43 — les 13 routes de api.md §7 rendent leur page DANS la coquille ; `/taches` mène
   à Aujourd'hui ; le module n'a aucune navigation ; `useEnLigne()` suit `offline`. */

// route → titre de page
const ATTENDU = {
  '/taches/aujourdhui': "Aujourd'hui",
  '/taches/a-trier': 'À trier',
  '/taches/projets': 'Projets',
  '/taches/projets/archive': 'Archive',
  '/taches/projets/modeles': 'Modèles',
  '/taches/projets/42': 'Projet',
  '/taches/agenda': 'Agenda',
  '/taches/revue': 'Revue de la semaine',
  '/taches/rythme': 'Mon rythme',
  '/taches/recherche': 'Recherche',
  '/taches/supprimees': 'Supprimées récemment',
  '/taches/reglages': 'Réglages',
  '/taches/reglages/iphone': 'Réglages',
}

function monter(url) {
  const router = createMemoryRouter(
    config.routes.map((route) => {
      const Page = route.component
      return { path: route.path, element: <Suspense fallback={null}><Page /></Suspense> }
    }),
    { initialEntries: [url] },
  )
  const rendu = render(<RouterProvider router={router} />)
  return { router, ...rendu }
}

afterEach(() => { vi.restoreAllMocks() })

describe('TCH43 — routes du module', () => {
  it('déclare exactement les 13 routes de la table api.md §7, toutes sous /taches', () => {
    const source = readFileSync(resolve(process.cwd(), '..', 'docs', 'taches', 'reference', 'api.md'), 'utf8')
    const table = source.slice(source.indexOf('## 7. Routes du FRONT'), source.indexOf('## 8. Assistant'))
    const attendus = [
      '/taches', '/taches/aujourdhui', '/taches/a-trier', '/taches/projets', '/taches/projets/:id',
      '/taches/projets/archive', '/taches/projets/modeles', '/taches/agenda', '/taches/revue',
      '/taches/rythme', '/taches/recherche', '/taches/supprimees', '/taches/reglages/:rubrique?',
    ]
    const declares = config.routes.map((r) => r.path)
    expect([...declares].sort()).toEqual([...attendus].sort())
    // et chacune figure dans la table de la référence (`reglages[/:rubrique]` = rubrique facultative)
    for (const chemin of attendus) {
      const dans = chemin.replace('/:rubrique?', '[/:rubrique]')
      expect(table, chemin).toContain(`\`${dans}\``)
    }
  })

  it('n\'a AUCUNE navigation ni tuile d\'app : module invisible', () => {
    expect(config.key).toBe('taches')
    expect(config.nav).toBeUndefined()
    expect(moduleNavSections.some((s) => s.key === 'taches')).toBe(false)
  })

  it('reste invisible malgré sa ligne du miroir des manifestes (non installable, aucune tuile)', () => {
    expect(MANIFESTES.taches).toMatchObject({ sku: 'generic', installable: false })
    const apps = buildInstalledApps(moduleConfigs, { role: 'admin' })
    expect(apps.some((a) => a.key === 'taches')).toBe(false)
  })

  it('garde STRICTE : un compte hérité sans rôle n\'entre pas, `taches_voir` entre', () => {
    for (const route of config.routes) {
      expect(route.permRepliPalier, route.path).toBeUndefined()
      expect(estAutoriseEntree(route, 'admin', []), route.path).toBe(false)
      expect(estAutoriseEntree(route, 'responsable', []), route.path).toBe(false)
      expect(estAutoriseEntree(route, 'admin', ['taches_voir']), route.path).toBe(true)
      expect(estAutoriseEntree(route, 'normal', ['taches_voir']), route.path).toBe(true)
      expect(estAutoriseEntree(route, 'normal', ['crm_voir']), route.path).toBe(false)
    }
  })

  it('chaque route porte son marqueur « contextuelle » (garde écran sans nav)', () => {
    const source = readFileSync(resolve(process.cwd(), 'src', 'features', 'taches', 'module.config.jsx'), 'utf8')
    const lignes = source.split(/\r?\n/)
    const indices = lignes.map((l, i) => (l.trimStart().startsWith('{ path:') ? i : -1)).filter((i) => i >= 0)
    expect(indices).toHaveLength(13)
    for (const i of indices) expect(lignes[i - 1]).toMatch(/contextuelle: module invisible jusqu'à TCH131/)
  })

  it.each(Object.entries(ATTENDU))('%s rend « %s » dans la coquille', async (url, titre) => {
    const { container } = monter(url)
    expect(await screen.findByRole('heading', { level: 1, name: titre }, { timeout: 5000 })).toBeInTheDocument()
    const coquille = container.querySelector('.tch')
    expect(coquille).not.toBeNull()
    expect(within(coquille).getByRole('heading', { level: 1, name: titre })).toBeInTheDocument()
    // la coquille est UNIQUE : un seul bouton « Ajouter une tâche » flottant
    expect(container.querySelectorAll('.tch')).toHaveLength(1)
    expect(container.querySelectorAll('.fab')).toHaveLength(1)
  })

  it('/taches mène à /taches/aujourdhui', async () => {
    const { router } = monter('/taches')
    expect(await screen.findByRole('heading', { level: 1, name: "Aujourd'hui" })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/taches/aujourdhui')
  })

  it('?tache=<id> monte la fiche ; la saisie s\'ouvre par le bouton et par l\'événement', async () => {
    const { container } = monter('/taches/aujourdhui?tache=12')
    await screen.findByRole('heading', { level: 1, name: "Aujourd'hui" })
    expect(container.querySelector('[data-fiche="12"]')).not.toBeNull()
    expect(screen.queryByRole('dialog', { name: 'Ajouter une tâche' })).toBeNull()
    await act(async () => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisir')) })
    expect(screen.getByRole('dialog', { name: 'Ajouter une tâche' })).toBeInTheDocument()
    await act(async () => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })) })
    expect(screen.queryByRole('dialog', { name: 'Ajouter une tâche' })).toBeNull()
  })

  it('le jour s\'affiche au-dessus du titre d\'Aujourd\'hui, en majuscule initiale', async () => {
    const { container } = monter('/taches/aujourdhui')
    await screen.findByRole('heading', { level: 1, name: "Aujourd'hui" })
    expect(container.querySelector('.entete-date').textContent).toMatch(/^[A-ZÉ][a-zéû]+ \d{1,2} [a-zéû]+$/)
  })
})

describe('TCH43 — useEnLigne', () => {
  function Sonde() {
    return <p>{useEnLigne() ? 'en ligne' : 'hors ligne'}</p>
  }

  it('est faux sur « offline », vrai de nouveau sur « online »', async () => {
    const etat = vi.spyOn(window.navigator, 'onLine', 'get')
    etat.mockReturnValue(true)
    render(<Sonde />)
    expect(screen.getByText('en ligne')).toBeInTheDocument()
    etat.mockReturnValue(false)
    await act(async () => { window.dispatchEvent(new Event('offline')) })
    expect(screen.getByText('hors ligne')).toBeInTheDocument()
    etat.mockReturnValue(true)
    await act(async () => { window.dispatchEvent(new Event('online')) })
    expect(screen.getByText('en ligne')).toBeInTheDocument()
  })

  it('la coquille dit « Hors ligne » sous forme de statut', async () => {
    const etat = vi.spyOn(window.navigator, 'onLine', 'get')
    etat.mockReturnValue(false)
    monter('/taches/aujourdhui')
    const message = await screen.findByText(/Hors ligne/)
    expect(message.closest('[role="status"]')).not.toBeNull()
  })
})
