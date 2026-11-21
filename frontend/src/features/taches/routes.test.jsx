import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import process from 'node:process'
import { act, render, screen, within } from '@testing-library/react'
import { Suspense } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { appNavItems } from '../../lib/apps/ActiveAppContext'
import { MANIFESTES } from '../../lib/apps/appSkus'
import { buildInstalledApps } from '../../lib/apps/useInstalledApps'
import { estAutoriseEntree } from '../../router/moduleGating'
import { moduleConfigs, moduleNavSections } from '../../router/moduleRoutes'
import { configurerGestes, proposerAnnuler, reinitialiserGestes } from './lib/gestes'
import config, { CHARGEURS, prechargerEcrans, reinitialiserPrechargement } from './module.config'
import CoquilleTaches from './coquille/CoquilleTaches'
import { useEnLigne } from './lib/enLigne'

/* TCH43 — les 13 routes de api.md §7 rendent leur page DANS la coquille ; `/taches` mène
   à Aujourd'hui ; `useEnLigne()` suit `offline`. TCH131 — activation : 4 onglets gardés par
   `taches_voir`, le module n'apparaît qu'à un compte qui porte le droit. */

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
  '/taches/supprimees': 'Supprimées',
  '/taches/reglages': 'Réglages',
  '/taches/reglages/iphone': 'Réglages',
}

// R2-084 — les écrans qui portent le bouton flottant « Ajouter une tâche »
const AVEC_FAB = new Set(['/taches/aujourdhui', '/taches/a-trier', '/taches/projets', '/taches/projets/42', '/taches/agenda'])

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

/* R4-41 — PREMIER describe du fichier, exprès : un écran paresseux ne suspend qu'à son premier rendu (ensuite son morceau
   est là) ; ces deux tests voient donc des morceaux pas encore arrivés. */
describe('R4-41 — pas de page blanche au premier passage sur un écran', () => {
  // le préchargement lancé par le montage d'un écran ne tourne pas pour de vrai pendant ces tests (il appellerait les espions)
  beforeEach(() => { reinitialiserPrechargement(); vi.stubGlobal('requestIdleCallback', () => 0) })
  afterEach(() => { vi.unstubAllGlobals(); reinitialiserPrechargement() })

  it('pendant le morceau d\'un écran, la coquille du module reste montée : titre, même enveloppe, squelette', async () => {
    const { container } = monter('/taches/projets')
    // synchrone : le morceau n'est pas encore là ; le repli du module (pas le vide, pas celui de l'ERP) tient la place
    const repli = container.querySelector('.tch.tch-chargement')
    expect(repli).not.toBeNull()
    expect(repli).toHaveAttribute('data-ecran', 'projets')
    expect(repli.querySelector('.entete-titre')).toHaveTextContent('Projets')
    expect(within(repli).queryByRole('heading')).toBeNull() // le repli ne pose pas de titre : le vrai écran a le sien
    expect(within(repli).getByRole('status', { name: 'Chargement' })).toBeInTheDocument() // squelette dès la 1re image
    // le vrai écran remplace le repli : une seule coquille, plus de repli
    expect(await screen.findByRole('button', { name: 'Chercher dans mes tâches' }, { timeout: 5000 })).toBeInTheDocument()
    expect(container.querySelector('.tch-chargement')).toBeNull()
    expect(container.querySelectorAll('.tch')).toHaveLength(1)
  })

  it('les écrans qui s\'ouvrent en pleine largeur gardent cette largeur dans leur repli ; la page d\'un projet, sans titre connu, a une barre', () => {
    const agenda = monter('/taches/agenda')
    expect(agenda.container.querySelector('.tch-chargement')).toHaveAttribute('data-largeur', 'pleine')
    agenda.unmount()
    const projet = monter('/taches/projets/42')
    const repli = projet.container.querySelector('.tch-chargement')
    expect(repli.querySelector('.entete-titre .os')).not.toBeNull()
    expect(repli.querySelector('.entete-titre').textContent).toBe('')
  })

  it('à l\'entrée dans le module, les écrans des onglets se chargent à l\'inactivité, un par un, une seule fois', async () => {
    vi.stubGlobal('requestIdleCallback', (rappel) => setTimeout(rappel, 0))
    const espions = ['atrier', 'projets', 'agenda', 'aujourdhui', 'projet'].map((cle) => vi.spyOn(CHARGEURS, cle).mockResolvedValue({ default: () => null }))
    const fin = prechargerEcrans()
    // rien avant l'inactivité : ni le premier rendu ni le réseau du premier écran n'attendent après lui
    espions.forEach((espion) => expect(espion).not.toHaveBeenCalled())
    expect(prechargerEcrans()).toBe(fin) // un second appel ne relance rien
    await fin
    espions.forEach((espion) => expect(espion).toHaveBeenCalledTimes(1))
    await prechargerEcrans()
    espions.forEach((espion) => expect(espion).toHaveBeenCalledTimes(1))
  })

  it('un échec de réseau n\'arrête rien : le préchargement se retente à l\'écran suivant', async () => {
    vi.stubGlobal('requestIdleCallback', (rappel) => setTimeout(rappel, 0))
    const echec = vi.spyOn(CHARGEURS, 'atrier').mockRejectedValueOnce(new Error('réseau'))
    const projets = vi.spyOn(CHARGEURS, 'projets').mockResolvedValue({ default: () => null })
    ;['agenda', 'aujourdhui', 'projet'].forEach((cle) => vi.spyOn(CHARGEURS, cle).mockResolvedValue({ default: () => null }))
    await prechargerEcrans()
    expect(echec).toHaveBeenCalledTimes(1)
    expect(projets).not.toHaveBeenCalled() // arrêté au premier échec
    await prechargerEcrans() // le prochain écran monté relance
    expect(echec).toHaveBeenCalledTimes(2)
    expect(projets).toHaveBeenCalledTimes(1)
  })
})

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

  it('TCH131 — 4 onglets dans l\'ordre de spec-7 §2, libellés traduits, glyphe d\'app propre', () => {
    expect(config.key).toBe('taches')
    expect(config.nav).toMatchObject({ label: 'Tâches', labelKey: 'nav.section.taches' })
    expect(config.nav.icon).toBeTruthy()
    expect(config.nav.items.map((it) => [it.to, it.label, it.k])).toEqual([
      ['/taches/aujourdhui', "Aujourd'hui", 'nav.taches_aujourdhui'],
      ['/taches/a-trier', 'À trier', 'nav.taches_a_trier'],
      ['/taches/projets', 'Projets', 'nav.taches_projets'],
      ['/taches/agenda', 'Agenda', 'nav.taches_agenda'],
    ])
    expect(moduleNavSections.filter((s) => s.key === 'taches')).toHaveLength(1)
  })

  it('TCH131 — chaque onglet est gardé STRICTEMENT par `taches_voir`, comme les routes', () => {
    for (const item of config.nav.items) {
      expect(item.perm, item.to).toBe('taches_voir')
      expect(item.permRepliPalier, item.to).toBeUndefined()
      expect(estAutoriseEntree(item, 'admin', []), item.to).toBe(false)
      expect(estAutoriseEntree(item, 'admin', ['crm_voir']), item.to).toBe(false)
      expect(estAutoriseEntree(item, 'admin', ['taches_voir']), item.to).toBe(true)
    }
  })

  it('TCH131 — installable ; tuile, barre latérale et épinglés SEULEMENT pour un compte qui a `taches_voir`', () => {
    expect(MANIFESTES.taches).toMatchObject({ sku: 'generic', installable: true })
    // lanceur, épinglés, Menu d'accueil : tous lisent `buildInstalledApps`
    const visible = (role, permissions) => buildInstalledApps(moduleConfigs, { role, permissions })
      .some((a) => a.key === 'taches')
    expect(visible('admin', [])).toBe(false) // compte hérité sans rôle fin
    expect(visible('responsable', [])).toBe(false)
    expect(visible('admin', ['crm_voir', 'roles_gerer'])).toBe(false) // rôle fin sans le droit
    const avec = buildInstalledApps(moduleConfigs, { role: 'admin', permissions: ['taches_voir'] })
      .find((a) => a.key === 'taches')
    expect(avec).toMatchObject({ key: 'taches', to: '/taches/aujourdhui', icon: config.nav.icon })
    // barre latérale et barre d'onglets : `appNavItems` (ActiveAppContext)
    expect(appNavItems(config, 'admin', [])).toEqual([])
    expect(appNavItems(config, 'normal', ['crm_voir'])).toEqual([])
    expect(appNavItems(config, 'admin', ['taches_voir']).map((it) => it.to)).toEqual([
      '/taches/aujourdhui', '/taches/a-trier', '/taches/projets', '/taches/agenda',
    ])
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

  it.each(Object.entries(ATTENDU))('%s rend « %s » dans la coquille', async (url, titre) => {
    const { container } = monter(url)
    expect(await screen.findByRole('heading', { level: 1, name: titre }, { timeout: 5000 })).toBeInTheDocument()
    const coquille = container.querySelector('.tch')
    expect(coquille).not.toBeNull()
    expect(within(coquille).getByRole('heading', { level: 1, name: titre })).toBeInTheDocument()
    // la coquille est UNIQUE ; R2-084 — le + flottant seulement sur les listes où l'on ajoute (un seul)
    expect(container.querySelectorAll('.tch')).toHaveLength(1)
    expect(container.querySelectorAll('.fab'), url).toHaveLength(AVEC_FAB.has(url) ? 1 : 0)
  })

  it.each([
    ['/taches/projets/42?planifier=1', 'Planifier le projet'],
    ['/taches/agenda?vue=semaine&placer=1', 'Planifier ma semaine'],
  ])('R2-084 — %s (%s) : pas de + dans un parcours', async (url) => {
    const { container } = monter(url)
    await screen.findByRole('heading', { level: 1 }, { timeout: 5000 })
    expect(container.querySelector('.tch')).not.toBeNull()
    expect(container.querySelectorAll('.fab')).toHaveLength(0)
  })

  it('R2-086 — Recherche : un seul champ, pas de loupe vers… la recherche, pas d\'« Ajouter une tâche »', async () => {
    const { container } = monter('/taches/recherche')
    await screen.findByRole('heading', { level: 1, name: 'Recherche' }, { timeout: 5000 })
    const coquille = container.querySelector('.tch')
    expect(within(coquille).queryByRole('button', { name: 'Chercher dans mes tâches' })).toBeNull()
    expect(coquille.querySelector('.saisie-bureau')).toBeNull()
  })

  it('R2-086 — hors de la Recherche, la loupe et « Ajouter une tâche » restent', async () => {
    const { container } = monter('/taches/a-trier')
    await screen.findByRole('heading', { level: 1, name: 'À trier' }, { timeout: 5000 })
    const coquille = container.querySelector('.tch')
    expect(within(coquille).getByRole('button', { name: 'Chercher dans mes tâches' })).toBeInTheDocument()
    expect(coquille.querySelector('.saisie-bureau')).not.toBeNull()
  })

  it.each([
    '/taches/projets/modeles', '/taches/projets/archive', '/taches/revue', '/taches/reglages', '/taches/rythme',
    '/taches/supprimees',
  ])('R3-087 — %s : pas de « Ajouter une tâche » en tête (la touche n reste)', async (url) => {
    const { container } = monter(url)
    await screen.findByRole('heading', { level: 1 }, { timeout: 5000 })
    expect(container.querySelector('.tch .saisie-bureau'), url).toBeNull()
  })

  it.each(['/taches/a-trier', '/taches/agenda'])('R3-087 — %s : on y range des tâches, la ligne « Ajouter une tâche » reste', async (url) => {
    const { container } = monter(url)
    await screen.findByRole('heading', { level: 1 }, { timeout: 5000 })
    expect(container.querySelector('.tch .saisie-bureau'), url).not.toBeNull()
  })

  it('R3-082 — `largeur="pleine"` pose `data-largeur` sur la coquille ; sans elle, rien', () => {
    const router = createMemoryRouter([
      { path: '/a', element: <CoquilleTaches ecran="agenda" titre="Agenda" largeur="pleine"><p>grille</p></CoquilleTaches> },
      { path: '/b', element: <CoquilleTaches ecran="rythme" titre="Mon rythme"><p>colonne</p></CoquilleTaches> },
    ], { initialEntries: ['/a'] })
    const { container } = render(<RouterProvider router={router} />)
    expect(container.querySelector('.tch')).toHaveAttribute('data-largeur', 'pleine')
    act(() => { router.navigate('/b') })
    expect(container.querySelector('.tch')).not.toHaveAttribute('data-largeur')
  })

  it('couture L7 — R3-007 et R3-026 pliés : l\'aide d\'Aujourd\'hui et d\'un projet redit « Alt+↑/↓ Réorganiser »', async () => {
    for (const ecran of ['aujourdhui', 'projet']) {
      const router = createMemoryRouter([
        { path: '/x', element: <CoquilleTaches ecran={ecran} titre="Écran"><p>liste</p></CoquilleTaches> },
      ], { initialEntries: ['/x'] })
      const { unmount } = render(<RouterProvider router={router} />)
      await act(async () => { document.body.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true, cancelable: true })) })
      const aide = screen.getByRole('dialog', { name: 'Touches de Tâches' })
      const ligne = within(aide).getByText('Réorganiser').closest('.touches-ligne')
      expect(ligne.querySelector('dt')).toHaveTextContent('Alt+↑/↓')
      unmount()
    }
  })

  it('R2-087 — « ? » montre les touches de Tâches ; « / » va à la Recherche', async () => {
    const aideErp = vi.fn()
    window.addEventListener('keydown', aideErp) // l'aide générale de l'ERP écoute sur `window`
    try {
      const { router } = monter('/taches/a-trier')
      await screen.findByRole('heading', { level: 1, name: 'À trier' }, { timeout: 5000 })
      await act(async () => { document.body.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true, cancelable: true })) })
      const aide = screen.getByRole('dialog', { name: 'Touches de Tâches' })
      expect(within(aide).getByText('Ajouter ici')).toBeInTheDocument()
      // couture r2 — l'aide dit ce que l'écran OUVERT fait : À trier traite Quand, mais ni Fait, ni ★, ni Ctrl Z
      expect(within(aide).getByText('Quand')).toBeInTheDocument()
      expect(within(aide).queryByText('Fait')).toBeNull()
      expect(within(aide).queryByText('Essentiel')).toBeNull()
      expect(within(aide).queryByText('Annuler (hors champ)')).toBeNull()
      expect(within(aide).queryByText(/\+15 min/)).toBeNull()
      // R3-095 — les touches les plus utilisées en TÊTE : j/k, Entrée, Échap ; « Réorganiser » (Alt+↑/↓) n'est pas promis à À trier
      expect([...aide.querySelectorAll('dt')].slice(0, 3).map((dt) => dt.textContent)).toEqual(['j / k', 'Entrée', 'Échap'])
      expect(within(aide).getByText('Ligne suivante / précédente')).toBeInTheDocument()
      expect(within(aide).getByText('Ouvrir')).toBeInTheDocument()
      expect(within(aide).getByText('Fermer')).toBeInTheDocument()
      expect(within(aide).queryByText('Réorganiser')).toBeNull()
      expect(aideErp).not.toHaveBeenCalled()
      await act(async () => { aide.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })) })
      expect(screen.queryByRole('dialog', { name: 'Touches de Tâches' })).toBeNull()
      await act(async () => { document.body.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true, cancelable: true })) })
      expect(router.state.location.pathname).toBe('/taches/recherche')
    } finally {
      window.removeEventListener('keydown', aideErp)
    }
  })

  it('R2-088 — « Messages sans délai » vaut dès l\'ouverture (après un rechargement), sans repasser par Réglages', async () => {
    const CLE = 'taqinor:taches:sans-delai:anonyme' // compte de test : aucun utilisateur connecté
    reinitialiserGestes()
    window.localStorage.removeItem(CLE)
    try {
      // 1) Réglages l'allume (configurerGestes) pendant que la coquille est montée : la valeur est gardée sur l'appareil
      const premier = monter('/taches/a-trier')
      await screen.findByRole('heading', { level: 1, name: 'À trier' }, { timeout: 5000 })
      await act(async () => { configurerGestes({ sansDelai: true }) })
      expect(window.localStorage.getItem(CLE)).toBe('1')
      premier.unmount()
      // 2) « rechargement » : le magasin des gestes repart à zéro ; la coquille rend le réglage dès son montage
      reinitialiserGestes()
      monter('/taches/a-trier')
      await screen.findByRole('heading', { level: 1, name: 'À trier' }, { timeout: 5000 })
      await act(async () => { proposerAnnuler({ message: 'Faite', onAnnuler: () => {} }) })
      // « sans délai » : le toast porte sa croix « Fermer » et ne part pas seul
      const toast = screen.getByRole('group', { name: 'Geste effectué' })
      expect(within(toast).getByRole('button', { name: 'Fermer' })).toBeInTheDocument()
    } finally {
      reinitialiserGestes()
      window.localStorage.removeItem(CLE)
    }
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

  describe('vague 2 — la fiche en panneau (non modal, bureau large)', () => {
    const large = () => vi.stubGlobal('matchMedia', (q) => ({
      matches: q === '(min-width: 1024px)', media: q, addEventListener() {}, removeEventListener() {},
    }))
    afterEach(() => { vi.unstubAllGlobals() })
    const touche = (key) => act(async () => {
      document.body.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))
    })

    it('fermer la fiche retire `tache`, `section` et `focus` de l\'adresse', async () => {
      large()
      const { router } = monter('/taches/aujourdhui?tache=12&section=decouper&focus=titre&vue=x')
      await screen.findByRole('heading', { level: 1, name: "Aujourd'hui" })
      const panneau = await screen.findByRole('dialog', { name: /Fiche d'une tâche|.+/ })
      expect(panneau).toHaveAttribute('aria-modal', 'false')
      await touche('Escape')
      const restes = new URLSearchParams(router.state.location.search)
      expect([...restes.keys()]).toEqual(['vue'])
    })

    it('`n`, `?` et `/` marchent, panneau de la fiche ouvert', async () => {
      large()
      const { router } = monter('/taches/aujourdhui?tache=12')
      await screen.findByRole('heading', { level: 1, name: "Aujourd'hui" })
      expect(await screen.findByRole('dialog')).toHaveAttribute('aria-modal', 'false')
      await touche('n')
      expect(screen.getByRole('dialog', { name: 'Ajouter une tâche' })).toBeInTheDocument()
      await touche('Escape') // ferme la saisie (la plus haute), pas la fiche
      expect(screen.queryByRole('dialog', { name: 'Ajouter une tâche' })).toBeNull()
      expect(new URLSearchParams(router.state.location.search).get('tache')).toBe('12')
      await touche('?')
      expect(screen.getByRole('dialog', { name: 'Touches de Tâches' })).toBeInTheDocument()
      await touche('Escape')
      expect(screen.queryByRole('dialog', { name: 'Touches de Tâches' })).toBeNull()
      await touche('/')
      expect(router.state.location.pathname).toBe('/taches/recherche')
    })
  })

  it('le jour s\'affiche au-dessus du titre d\'Aujourd\'hui, en majuscule initiale', async () => {
    const { container } = monter('/taches/aujourdhui')
    await screen.findByRole('heading', { level: 1, name: "Aujourd'hui" })
    expect(container.querySelector('.entete-date').textContent).toMatch(/^[A-ZÉ][a-zéû]+ \d{1,2} [a-zéû]+$/)
  })
})

/* Une coque d'ERP minimale (en-tête + cloche) posée dans le document, comme le fait `components/layout/Layout.jsx`. */
function poserEnteteErp({ notifications = 0 } = {}) {
  const main = document.createElement('div')
  main.className = 'layout-main'
  main.innerHTML = `<header class="header"><button type="button" class="header-menu-btn" aria-label="Ouvrir le menu"></button>
    <div class="nb-wrap"><button type="button" class="nb-btn" aria-label="Notifications (${notifications})"></button></div></header>`
  document.body.appendChild(main)
  const menu = vi.fn()
  const cloche = vi.fn()
  main.querySelector('.header-menu-btn').addEventListener('click', menu)
  main.querySelector('.nb-btn').addEventListener('click', cloche)
  return { main, menu, cloche, boutonCloche: main.querySelector('.nb-btn') }
}

describe('R2-080 — sur iPhone, la rangée du haut de Tâches remplace la barre de l\'ERP', () => {
  afterEach(() => { document.querySelectorAll('body > .layout-main').forEach((n) => n.remove()) })

  it('☰ ouvre le tiroir de l\'ERP par son propre bouton', async () => {
    const erp = poserEnteteErp()
    const { container } = monter('/taches/aujourdhui')
    await screen.findByRole('heading', { level: 1, name: "Aujourd'hui" })
    const coquille = container.querySelector('.tch')
    await act(async () => { within(coquille).getByRole('button', { name: 'Ouvrir le menu' }).click() })
    expect(erp.menu).toHaveBeenCalledTimes(1)
  })

  it('la cloche de l\'ERP s\'atteint en un toucher : compteur lu sur l\'ERP, son panneau ouvert', async () => {
    const erp = poserEnteteErp({ notifications: 3 })
    const { container } = monter('/taches/aujourdhui')
    await screen.findByRole('heading', { level: 1, name: "Aujourd'hui" })
    const coquille = container.querySelector('.tch')
    const cloche = within(coquille).getByRole('button', { name: 'Notifications : 3' })
    await act(async () => { cloche.click() })
    expect(erp.cloche).toHaveBeenCalledTimes(1)
    // le compteur suit celui de l'ERP
    await act(async () => { erp.boutonCloche.setAttribute('aria-label', 'Notifications (5)') })
    expect(within(coquille).getByRole('button', { name: 'Notifications : 5' })).toBeInTheDocument()
    // au-delà de 99, le nom lu dit ce que la pastille écrit (« 99+ ») : jamais un nom qui contredit le texte visible
    await act(async () => { erp.boutonCloche.setAttribute('aria-label', 'Notifications (120)') })
    expect(within(coquille).getByRole('button', { name: 'Notifications : 99+' })).toHaveTextContent('99+')
  })

  it('le titre compact (rangée du haut) répète le titre de la page, caché aux lecteurs d\'écran', async () => {
    const { container } = monter('/taches/a-trier')
    await screen.findByRole('heading', { level: 1, name: 'À trier' })
    const compact = container.querySelector('.entete-barre .entete-compact')
    expect(compact?.textContent).toBe('À trier')
    expect(compact.getAttribute('aria-hidden')).toBe('true')
  })
})

describe('R2-093 — écran enfant : « ‹ parent » au-dessus du titre, ni loupe ni Copilote', () => {
  function monterEnfant(props) {
    const router = createMemoryRouter([
      { path: '/taches/projets/:id', element: <CoquilleTaches ecran="projet" titre="Chantier Benali 9 kWc" {...props}><p>contenu</p></CoquilleTaches> },
      { path: '/taches/projets', element: <p>liste des projets</p> },
    ], { initialEntries: ['/taches/projets/7'] })
    return { router, ...render(<RouterProvider router={router} />) }
  }

  it('rend le retour AVANT le titre et mène au parent', async () => {
    const { router, container } = monterEnfant({ retour: { libelle: 'Projets', vers: '/taches/projets' } })
    const titre = screen.getByRole('heading', { level: 1, name: 'Chantier Benali 9 kWc' })
    const retour = screen.getByRole('button', { name: 'Projets' })
    expect(retour.compareDocumentPosition(titre) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // écran enfant : pas de loupe, pas de Copilote ; le ⋯ reste ; ☰ cède sa place au retour
    expect(screen.queryByRole('button', { name: 'Chercher dans mes tâches' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Copilote' })).toBeNull()
    expect(screen.getByRole('button', { name: "Plus d'actions" })).toBeInTheDocument()
    expect(within(container.querySelector('.tch')).queryByRole('button', { name: 'Ouvrir le menu' })).toBeNull()
    await act(async () => { retour.click() })
    expect(router.state.location.pathname).toBe('/taches/projets')
  })

  it('sans `retour`, l\'écran garde loupe, Copilote et ☰', () => {
    monterEnfant({})
    expect(screen.getByRole('button', { name: 'Chercher dans mes tâches' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copilote' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ouvrir le menu' })).toBeInTheDocument()
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

describe('ACAL482 — la région « annonce » masquée ne crée pas de défilement horizontal (WebKit 390 px)', () => {
  it('`.tch .annonce` est ancrée (left/top) avec une marge négative : pas de position statique au bord droit', () => {
    const css = readFileSync(resolve(process.cwd(), 'src', 'styles', 'taches', 'base.css'), 'utf8')
    const regle = /\.tch \.annonce\s*\{([^}]*)\}/.exec(css)?.[1] ?? ''
    expect(regle).toMatch(/position:\s*absolute/)
    expect(regle).toMatch(/left:\s*0/)
    expect(regle).toMatch(/top:\s*0/)
    expect(regle).toMatch(/margin:\s*-1px/)
  })
})
