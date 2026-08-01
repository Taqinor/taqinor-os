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

const navigateMock = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => navigateMock }
})

import HomeMenu from './HomeMenu'
import { filtrerApps, grouperApps, normalise } from '../../lib/apps/appSearch'
import { PINNED_KEY, RECENT_KEY } from '../../lib/apps/appPrefs'

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
})

describe('ODY2 — HomeMenu (rendu)', () => {
  beforeEach(() => {
    window.localStorage.clear()
    navigateMock.mockClear()
    prefetchMock.mockClear()
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

  it('l’étoile et la tuile sont des boutons FRÈRES (aucun contrôle imbriqué)', () => {
    renderHome()
    const cellule = celluleDe('CRM')
    const boutons = within(cellule).getAllByRole('button')
    expect(boutons).toHaveLength(2)
    expect(boutons[0].contains(boutons[1])).toBe(false)
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

  it('aucune app visible : message d’accueil vide, pas de grille', () => {
    renderHome({ role: 'inconnu' })
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    expect(screen.getByText('Aucune application activée.')).toBeInTheDocument()
  })
})
