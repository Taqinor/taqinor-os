import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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

function renderTour(user, path = '/ventes/devis/nouveau') {
  const store = configureStore({ reducer: { auth: (s = { user }) => s } })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[path]}>
        <ProductTour />
      </MemoryRouter>
    </Provider>,
  )
}

// productTours.js met en cache la promesse `/onboarding/tours/` au niveau du
// module (un seul appel réseau par session, NTDMO14) — voulu en production,
// mais ce cache doit être invalidé entre chaque test sinon les tests suivants
// réutilisent silencieusement la réponse mockée du premier test.
beforeEach(() => { vi.clearAllMocks(); invalidateToursCache() })
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
