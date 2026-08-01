// ODY2 — Tests du Menu d'accueil plein écran.
//   • Grille = apps installées ∩ rôle EXACTEMENT (le hook ODY1 est la seule
//     source ; on mocke le registre, pas le hook, pour tester le vrai câblage).
//   • Type-ahead : la frappe filtre, Entrée ouvre la première, ↓ entre dans la
//     grille, Échap efface.
//   • Favoris : MÊME clé localStorage que VX9/VX10, jamais une seconde.
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// Registre mocké — même patron que useInstalledApps.test.jsx (vi.mock hoisté).
vi.mock('../../router/moduleRoutes', () => ({
  moduleConfigs: [
    {
      key: 'crm',
      order: 10,
      nav: {
        label: 'CRM',
        accent: 'azur',
        items: [{ to: '/crm', label: 'Clients', icon: null, roles: ['normal', 'responsable', 'admin'] }],
      },
    },
    {
      key: 'ventes',
      order: 20,
      nav: {
        label: 'Ventes',
        accent: 'brass',
        items: [{ to: '/ventes/devis', label: 'Devis', icon: null, roles: ['normal', 'responsable', 'admin'] }],
      },
    },
    {
      key: 'rh',
      order: 30,
      nav: {
        label: 'Ressources humaines',
        items: [{ to: '/rh', label: 'Employés', icon: null, roles: ['admin'] }],
      },
    },
  ],
}))

// ODY12 — le préchargement au survol/focus est observé, pas exécuté (un vrai
// import() de chunk n'a aucun sens sous jsdom).
const prefetchMock = vi.fn()
vi.mock('../../router/prefetchMap', () => ({
  prefetchRoute: (...args) => prefetchMock(...args),
  PREFETCH_MAP: {},
  shouldSkipPrefetch: () => false,
  _resetPrefetchCacheForTests: () => {},
}))

// ODY14 — la bannière VX36 fait ses propres lectures réseau : on la remplace
// par un espion inerte (on teste QU'ELLE est montée, pas son contenu, déjà
// couvert par ses propres tests).
const { bannerMock } = vi.hoisted(() => ({ bannerMock: vi.fn(() => null) }))
vi.mock('../../components/OnboardingBanner', () => ({ default: bannerMock }))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => navigateMock }
})

import HomeMenu from './HomeMenu'
import { filtrerApps, grouperApps, normalise } from '../../lib/apps/appSearch'
import { PINNED_KEY, RECENT_KEY, ORDER_KEY, applyOrder } from '../../lib/apps/appPrefs'

function renderHome({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  const store = configureStore({
    reducer: { auth: (s = { role, permissions, modulesDesactives, user: null }) => s },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <HomeMenu />
      </MemoryRouter>
    </Provider>,
  )
}

const tuiles = () => screen.getAllByRole('listitem').map((n) => n.textContent)
// Bouton d'OUVERTURE d'une cellule (l'étoile est son frère, pas son enfant).
const ouvreur = (cellule) => within(cellule).getAllByRole('button')[0]
const celluleDe = (label) => screen.getAllByRole('listitem').find((n) => n.textContent.includes(label))

describe('ODY2 — HomeMenu (fonctions pures)', () => {
  const APPS = [
    { key: 'crm', label: 'CRM', to: '/crm', description: 'Clients et leads' },
    { key: 'ventes', label: 'Ventes', to: '/ventes/devis', description: '' },
    { key: 'rh', label: 'Ressources humaines', to: '/rh', description: '' },
  ]

  it('normalise ignore casse et accents', () => {
    expect(normalise('Ressources Humaines')).toBe('ressources humaines')
    expect(normalise('Éclairé')).toBe('eclaire')
  })

  it('filtrerApps : requête vide = liste inchangée', () => {
    expect(filtrerApps(APPS, '')).toHaveLength(3)
  })

  it('filtrerApps : filtre sur libellé, clé et description', () => {
    expect(filtrerApps(APPS, 'vent').map((a) => a.key)).toEqual(['ventes'])
    expect(filtrerApps(APPS, 'rh').map((a) => a.key)).toEqual(['rh'])
    expect(filtrerApps(APPS, 'leads').map((a) => a.key)).toEqual(['crm'])
    // insensible aux accents : « humaines » sans accent trouve quand même.
    expect(filtrerApps(APPS, 'humaines').map((a) => a.key)).toEqual(['rh'])
  })

  it('grouperApps : Favoris puis Récents puis le reste, sans doublon', () => {
    const sections = grouperApps(APPS, { pinned: ['ventes'], recent: ['rh', 'ventes'] })
    expect(sections.map((s) => s.id)).toEqual(['favoris', 'recents', 'toutes'])
    expect(sections[0].apps.map((a) => a.key)).toEqual(['ventes'])
    // `ventes` est déjà en favori : il n'est PAS répété dans Récents.
    expect(sections[1].apps.map((a) => a.key)).toEqual(['rh'])
    expect(sections[2].apps.map((a) => a.key)).toEqual(['crm'])
  })

  it('grouperApps : en recherche, une seule section « Résultats »', () => {
    const sections = grouperApps(APPS, { query: 'vent', pinned: ['ventes'] })
    expect(sections).toHaveLength(1)
    expect(sections[0].id).toBe('resultats')
    expect(sections[0].apps.map((a) => a.key)).toEqual(['ventes'])
  })

  // ODY13 — l'ordre personnel : jamais une app perdue parce qu'elle manque à
  // un ordre enregistré il y a six mois.
  it('applyOrder : réordonne, et met les apps inconnues de l’ordre à la fin', () => {
    expect(applyOrder(APPS, ['rh', 'crm']).map((a) => a.key)).toEqual(['rh', 'crm', 'ventes'])
    expect(applyOrder(APPS, []).map((a) => a.key)).toEqual(['crm', 'ventes', 'rh'])
    expect(applyOrder(APPS, ['inconnue']).map((a) => a.key)).toEqual(['crm', 'ventes', 'rh'])
  })
})

describe('ODY2 — HomeMenu (rendu)', () => {
  beforeEach(() => {
    window.localStorage.clear()
    navigateMock.mockClear()
    prefetchMock.mockClear()
    bannerMock.mockClear()
  })

  it('ODY12 — le survol d’une tuile précharge le chunk de son cockpit', () => {
    renderHome()
    fireEvent.mouseEnter(ouvreur(celluleDe('CRM')))
    expect(prefetchMock).toHaveBeenCalledWith('/crm')
  })

  it('ODY12 — le focus clavier précharge aussi (pas seulement la souris)', () => {
    renderHome()
    fireEvent.focus(ouvreur(celluleDe('Ventes')))
    expect(prefetchMock).toHaveBeenCalledWith('/ventes/devis')
  })

  it('la grille = les apps installées ∩ rôle (source ODY1, pas un 2e registre)', () => {
    renderHome({ role: 'normal' })
    // `rh` exige le rôle admin → absente pour un rôle « normal ».
    expect(tuiles().join('|')).toContain('CRM')
    expect(tuiles().join('|')).toContain('Ventes')
    expect(tuiles().join('|')).not.toContain('Ressources humaines')
  })

  it('une app désactivée pour la société disparaît de la grille (ODX6)', () => {
    renderHome({ modulesDesactives: ['ventes'] })
    expect(tuiles().join('|')).not.toContain('Ventes')
    expect(tuiles().join('|')).toContain('CRM')
  })

  it('type-ahead : taper filtre la grille', () => {
    renderHome()
    const input = screen.getByRole('searchbox', { name: /Rechercher une application/ })
    fireEvent.change(input, { target: { value: 'vent' } })
    expect(tuiles()).toHaveLength(1)
    expect(tuiles()[0]).toContain('Ventes')
    expect(screen.getByText('Résultats')).toBeInTheDocument()
  })

  it('type-ahead : Entrée ouvre la première app filtrée', () => {
    renderHome()
    const input = screen.getByRole('searchbox', { name: /Rechercher une application/ })
    fireEvent.change(input, { target: { value: 'vent' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis')
  })

  it('type-ahead : Échap efface la requête', () => {
    renderHome()
    const input = screen.getByRole('searchbox', { name: /Rechercher une application/ })
    fireEvent.change(input, { target: { value: 'vent' } })
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(input.value).toBe('')
    expect(tuiles().length).toBeGreaterThan(1)
  })

  it('recherche sans résultat : message dédié, aucune tuile', () => {
    renderHome()
    fireEvent.change(
      screen.getByRole('searchbox', { name: /Rechercher une application/ }),
      { target: { value: 'zzzz' } },
    )
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    expect(screen.getByText(/Aucune application ne correspond/)).toBeInTheDocument()
  })

  it('flèche bas depuis le champ donne le focus à la première tuile', () => {
    renderHome()
    const input = screen.getByRole('searchbox', { name: /Rechercher une application/ })
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    expect(document.activeElement).toBe(ouvreur(screen.getAllByRole('listitem')[0]))
  })

  it('flèche droite déplace le focus à la tuile suivante', () => {
    renderHome()
    const cellules = screen.getAllByRole('listitem')
    fireEvent.keyDown(ouvreur(cellules[0]), { key: 'ArrowRight' })
    expect(document.activeElement).toBe(ouvreur(cellules[1]))
  })

  it('clic sur une tuile navigue vers le cockpit et alimente les récents', () => {
    renderHome()
    fireEvent.click(ouvreur(celluleDe('CRM')))
    expect(navigateMock).toHaveBeenCalledWith('/crm')
    expect(JSON.parse(window.localStorage.getItem(RECENT_KEY))).toEqual(['crm'])
  })

  it('tuile, étoile et poignée sont des boutons FRÈRES (aucun contrôle imbriqué)', () => {
    renderHome()
    const cellule = celluleDe('CRM')
    const boutons = within(cellule).getAllByRole('button')
    // ODY13 — trois contrôles : ouvrir, favori, déplacer.
    expect(boutons).toHaveLength(3)
    boutons.forEach((a) => boutons.forEach((b) => {
      if (a !== b) expect(a.contains(b)).toBe(false)
    }))
  })

  it('ODY13 — chaque cellule porte une poignée de déplacement nommée', () => {
    renderHome()
    expect(screen.getByRole('button', { name: 'Déplacer CRM' })).toBeInTheDocument()
  })

  it('ODY13 — en recherche, plus de poignée : on ne réordonne pas une vue filtrée', () => {
    renderHome()
    fireEvent.change(
      screen.getByRole('searchbox', { name: /Rechercher une application/ }),
      { target: { value: 'vent' } },
    )
    expect(screen.queryByRole('button', { name: /^Déplacer/ })).not.toBeInTheDocument()
  })

  it('ODY13 — un ordre personnel enregistré gouverne la grille', () => {
    window.localStorage.setItem(ORDER_KEY, JSON.stringify(['ventes', 'crm']))
    renderHome()
    const labels = screen.getAllByRole('listitem').map((n) => n.textContent)
    expect(labels[0]).toContain('Ventes')
    expect(labels[1]).toContain('CRM')
  })

  it('ODY13 — une app absente de l’ordre enregistré reste visible, à la fin', () => {
    window.localStorage.setItem(ORDER_KEY, JSON.stringify(['ventes']))
    renderHome()
    const labels = screen.getAllByRole('listitem').map((n) => n.textContent)
    expect(labels[0]).toContain('Ventes')
    expect(labels.join('|')).toContain('CRM')
  })

  it('favoris : l’étoile écrit LA clé partagée VX9/VX10, jamais une seconde', () => {
    renderHome()
    const crm = celluleDe('CRM')
    fireEvent.click(within(crm).getByRole('button', { name: /Ajouter CRM aux favoris/ }))
    expect(JSON.parse(window.localStorage.getItem(PINNED_KEY))).toEqual(['crm'])
    expect(PINNED_KEY).toBe('taqinor.sidebar.pinned')
    // Le clic sur l'étoile n'ouvre PAS l'app (stopPropagation).
    expect(navigateMock).not.toHaveBeenCalled()
    // Et la section « Favoris » apparaît en tête.
    expect(screen.getByText('Favoris')).toBeInTheDocument()
  })

  // ODY14 — le premier matin : état vide illustré + onboarding.
  it('aucune app visible : état vide dédié, pas de grille', () => {
    renderHome({ role: 'inconnu' })
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    expect(screen.getByText('Aucune app activée')).toBeInTheDocument()
  })

  it('ODY14 — état vide ADMIN : CTA vers Applications', () => {
    // Rôle admin mais toutes les apps désactivées pour la société.
    renderHome({ role: 'admin', modulesDesactives: ['crm', 'ventes', 'rh'] })
    expect(screen.getByText('Aucune app activée')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ouvrir Applications' }))
      .toHaveAttribute('href', '/parametres')
  })

  it('ODY14 — état vide NON-ADMIN : aucun CTA, renvoi vers l’administrateur', () => {
    renderHome({ role: 'normal', modulesDesactives: ['crm', 'ventes', 'rh'] })
    expect(screen.queryByRole('link', { name: 'Ouvrir Applications' })).not.toBeInTheDocument()
    expect(screen.getByText(/Demandez à votre administrateur/)).toBeInTheDocument()
  })

  it('ODY14 — la bannière de prise en main (VX36) est montée sur le Menu d’accueil', () => {
    renderHome()
    expect(bannerMock).toHaveBeenCalled()
  })

  it('ODY14 — la grille normale ne rend AUCUN état vide (pas de flash)', () => {
    renderHome()
    expect(screen.queryByText('Aucune app activée')).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem').length).toBeGreaterThan(0)
  })
})
