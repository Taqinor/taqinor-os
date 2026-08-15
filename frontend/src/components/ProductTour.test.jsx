import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// NTDMO15 — visite guidée par écran : apparaît une fois pour un utilisateur
// récent sur un écran cible, puis ne réapparaît plus après fermeture
// (persistée côté serveur via l'API mockée ci-dessous).
vi.mock('../api/axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

import api from '../api/axios'
import { invalidateToursCache } from '../features/onboarding/productTours'
import ProductTour from './ProductTour'

const RECENT_USER = { id: 1, date_joined: new Date().toISOString() }
const OLD_USER = { id: 2, date_joined: '2020-01-01T00:00:00Z' }

const TOURS = [
  {
    tour_key: 'devis', ecran_cible: '/ventes/devis/nouveau', vu: false,
    etapes: [
      { ordre: 10, selecteur: '', titre: 'Créer un devis', texte: 'Composez votre devis.' },
      { ordre: 20, selecteur: '[data-tour="x"]', titre: 'Ajoutez vos produits', texte: 'Chaque ligne se calcule.' },
    ],
  },
]

// Second tour du catalogue (autre écran) — sert à vérifier qu'un changement
// d'écran repart bien du tour de l'écran affiché.
const LEADS_TOUR = {
  tour_key: 'leads', ecran_cible: '/crm/leads', vu: false,
  etapes: [
    { ordre: 10, selecteur: '', titre: 'Suivre vos prospects', texte: 'Le kanban CRM.' },
    { ordre: 20, selecteur: '[data-tour="leads-kanban"]', titre: 'Faites glisser une carte', texte: 'Déplacez un lead.' },
  ],
}

function renderTour(user, path = '/ventes/devis/nouveau', extra = null) {
  const store = configureStore({ reducer: { auth: (s = { user }) => s } })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[path]}>
        <ProductTour />
        {extra}
      </MemoryRouter>
    </Provider>,
  )
}

// Bascule le point de rupture mobile de l'application (`useIsMobile`,
// `max-width: 767px`) : jsdom ne fournit pas de `matchMedia` utilisable, on le
// simule comme les autres specs du dépôt (RFQ.test.jsx…). Renvoie la fonction
// de restauration.
function simulerMobile() {
  const original = window.matchMedia
  window.matchMedia = (query) => ({
    matches: /max-width:\s*767px/.test(query),
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })
  return () => {
    if (original) window.matchMedia = original
    else delete window.matchMedia
  }
}

// productTours.js met en cache la promesse `/onboarding/tours/` au niveau du
// module (un seul appel réseau par session, NTDMO14) — voulu en production,
// mais ce cache doit être invalidé entre chaque test sinon les tests suivants
// réutilisent silencieusement la réponse mockée du premier test.
// `clearAllMocks` vide `mock.calls` mais NE DRAINE PAS les files
// `mockResolvedValueOnce`. Or plusieurs tests d'ici en empilent une SANS
// que le composant la consomme (utilisateur ancien / tour déjà vu : aucun
// appel réseau). La valeur survivait alors au test suivant, qui lisait la
// réponse du précédent — d'où un échec MOUVANT (un test différent à chaque
// exécution, tous verts en isolation). `mockReset` draine la file.
beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockReset()
  api.post.mockReset()
  invalidateToursCache()
})
afterEach(() => cleanup())

describe('ProductTour (NTDMO15)', () => {
  it("s'affiche sur l'écran cible pour un utilisateur récent", async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    renderTour(RECENT_USER)
    expect(await screen.findByText('Créer un devis')).toBeInTheDocument()
  })

  it('ne s’affiche jamais pour un utilisateur ancien', async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    renderTour(OLD_USER)
    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(screen.queryByText('Créer un devis')).not.toBeInTheDocument()
  })

  it('ne s’affiche jamais si déjà vu', async () => {
    api.get.mockResolvedValueOnce({
      data: [{ ...TOURS[0], vu: true }],
    })
    renderTour(RECENT_USER)
    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(screen.queryByText('Créer un devis')).not.toBeInTheDocument()
  })

  it("Échap ferme le tour et appelle l'API vu/ (ne réapparaît plus)", async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    api.post.mockResolvedValueOnce({ data: [{ ...TOURS[0], vu: true }] })
    renderTour(RECENT_USER)
    await screen.findByText('Créer un devis')
    fireEvent.keyDown(window, { key: 'Escape' })
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/onboarding/tours/devis/vu/'))
    expect(screen.queryByText('Créer un devis')).not.toBeInTheDocument()
  })

  // Régression e2e E4 (PR #518) : une étape sans cible (`selecteur: ''` — la 1re
  // étape de CHAQUE tour du catalogue) rendait un voile plein écran qui avalait
  // TOUS les clics de l'écran réel (`+ Nouveau lead` injoignable pendant 15 s).
  // Le contrat en tête de ProductTour.jsx est « jamais bloquant » : on l'épingle.
  it("ne bloque jamais l'écran : voile et calque ne captent aucun clic", async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    renderTour(RECENT_USER)
    await screen.findByText('Créer un devis')
    const calque = screen.getByRole('dialog')
    expect(calque.className).toContain('pointer-events-none')
    const voile = calque.querySelector('.backdrop-blur-sm')
    expect(voile).not.toBeNull()
    expect(voile.className).toContain('pointer-events-none')
    // La bulle, elle, reste bien interactive (ses boutons doivent rester cliquables).
    expect(screen.getByRole('button', { name: /Suivant/ }).closest('.pointer-events-auto'))
      .not.toBeNull()
  })

  // Défaut visuel prouvé (PR #518, correctif) : la 1re étape de CHAQUE tour
  // n'a pas de `selecteur` (pas de cible à spotlighter) ; la bulle doit alors
  // être centrée à l'écran. `animate-pop-in` (tokens.css) définit lui-même un
  // `transform` (keyframes `pop-in`, finissent sur `transform: none`, fill-mode
  // `both`) — s'il est posé sur le MÊME nœud qu'un `transform` de centrage
  // inline, l'animation l'écrase et la bulle atterrit décalée en bas-à-droite
  // du centre. On verrouille donc la SÉPARATION : le centrage doit vivre sur
  // un conteneur dédié, jamais sur l'élément qui porte `animate-pop-in`.
  it('centre la bulle sans cible sans que l’animation pop-in n’écrase le centrage', async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    renderTour(RECENT_USER)
    await screen.findByText('Créer un devis')
    const bulle = screen.getByRole('button', { name: /Suivant/ }).closest('.animate-pop-in')
    expect(bulle).not.toBeNull()
    // L'élément animé lui-même ne doit porter AUCUN transform de centrage —
    // sinon `animate-pop-in` l'écraserait en fin d'animation.
    expect(bulle.style.transform).not.toContain('translate')
    // Le centrage doit vivre sur un conteneur ancêtre dédié, inerte et non
    // animé (séparé de l'élément `animate-pop-in`).
    const centreur = bulle.parentElement
    expect(centreur.className).toContain('fixed')
    expect(centreur.style.transform).toContain('translate(-50%, -50%)')
    expect(centreur.className).toContain('pointer-events-none')
  })

  it('un clic hors de la bulle ferme la visite (et un clic dedans ne la ferme pas)', async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    api.post.mockResolvedValueOnce({ data: [{ ...TOURS[0], vu: true }] })
    renderTour(RECENT_USER)
    await screen.findByText('Créer un devis')
    // Dedans : ne ferme pas.
    fireEvent.pointerDown(screen.getByRole('button', { name: /Suivant/ }))
    expect(api.post).not.toHaveBeenCalled()
    // Dehors : ferme et marque vu, comme le faisait le clic sur le voile.
    fireEvent.pointerDown(document.body)
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/onboarding/tours/devis/vu/'))
    expect(screen.queryByText('Créer un devis')).not.toBeInTheDocument()
  })

  // Rouge e2e MB6 (PR #518, `mobile-safari`) : au format iPhone, la bulle
  // centrée recouvrait PHYSIQUEMENT le bouton « Créer le devis » du générateur
  // (`div.mt-3…` de la bulle peint au-dessus de la barre d'actions collante).
  // Le calque était bien inerte, mais une bulle posée au milieu de l'écran EST
  // un obstacle : au téléphone, TOUTES les actions primaires du produit vivent
  // dans le tiers bas (FAB « + Nouveau lead » VX42, `.gen-actions-sticky`
  // MB3/VX138, barre d'onglets MB1) — une aide non sollicitée doit donc vivre à
  // l'opposé, ancrée sous l'en-tête. On verrouille cet ancrage.
  it("au téléphone, la bulle sans cible s'ancre en haut et libère la zone d'action", async () => {
    const restaurer = simulerMobile()
    try {
      api.get.mockResolvedValueOnce({ data: TOURS })
      renderTour(RECENT_USER)
      await screen.findByText('Créer un devis')
      const bulle = screen.getByRole('button', { name: /Suivant/ }).closest('.animate-pop-in')
      const dock = bulle.parentElement
      // Ancrée en HAUT (offset mesuré sous l'en-tête), jamais centrée à l'écran.
      expect(dock.style.top).toMatch(/^\d+px$/)
      expect(dock.style.transform).not.toContain('translate')
      // …et JAMAIS ancrée au bas : le tiers bas reste entièrement au pouce.
      expect(dock.style.bottom).toBe('')
      // Contrat E4 inchangé : dock inerte, bulle cliquable.
      expect(dock.className).toContain('pointer-events-none')
      expect(bulle.className).toContain('pointer-events-auto')
    } finally {
      restaurer()
    }
  })

  // Même incident, seconde cause (trouvée en instruisant le rouge MB6) : rien
  // ne réinitialisait la visite en quittant son écran. `open`/`step`/`activeKey`
  // restaient ceux de l'écran PRÉCÉDENT — l'écran suivant héritait donc d'une
  // bulle ouverte à la mauvaise étape, et sa fermeture marquait « vu » le tour
  // du mauvais écran (celui de l'écran d'avant, jamais celui affiché).
  it("repart de zéro sur chaque écran (bonne étape, bon tour marqué vu)", async () => {
    api.get.mockResolvedValueOnce({ data: [LEADS_TOUR, ...TOURS] })
    api.post.mockResolvedValue({ data: [] })
    function Aller() {
      const navigate = useNavigate()
      return (
        <button type="button" onClick={() => navigate('/ventes/devis/nouveau')}>
          aller au générateur
        </button>
      )
    }
    renderTour(RECENT_USER, '/crm/leads', <Aller />)
    await screen.findByText('Suivre vos prospects')
    // On avance dans le tour « leads » avant de changer d'écran.
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    await screen.findByText('Faites glisser une carte')

    fireEvent.click(screen.getByRole('button', { name: 'aller au générateur' }))
    // Le tour du générateur démarre à SA première étape (jamais à l'index hérité).
    expect(await screen.findByText('Créer un devis')).toBeInTheDocument()
    // …et sa fermeture marque « devis », jamais « leads ».
    fireEvent.keyDown(window, { key: 'Escape' })
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/onboarding/tours/devis/vu/'))
  })

  // NTDMO27 — toggle société « Visites guidées actives » (Paramètres → Démo &
  // Onboarding). `company_tours_actifs: false` doit empêcher tout tour de
  // s'ouvrir automatiquement, même pour un utilisateur récent sur un écran
  // cible jamais vu.
  it('ne s’affiche jamais si la société a désactivé les visites guidées (tours_actifs=false)', async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    renderTour({ ...RECENT_USER, company_tours_actifs: false })
    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(screen.queryByText('Créer un devis')).not.toBeInTheDocument()
  })

  it('« Suivant » avance puis « Terminer » ferme et marque vu', async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    api.post.mockResolvedValueOnce({ data: [{ ...TOURS[0], vu: true }] })
    renderTour(RECENT_USER)
    await screen.findByText('Créer un devis')
    fireEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    expect(await screen.findByText('Ajoutez vos produits')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Terminer/ }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/onboarding/tours/devis/vu/'))
  })
})
