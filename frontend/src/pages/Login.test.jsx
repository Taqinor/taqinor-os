import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// Login ne fait pas de requête réseau au montage (seulement au submit) —
// on neutralise quand même le module axios pour ne dépendre d'aucun réseau.
vi.mock('../api/axios', () => ({ default: { post: vi.fn() } }))

import Login from './Login'

function makeStore() {
  return configureStore({ reducer: { auth: (s = {}) => s } })
}

function renderLogin() {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    </Provider>,
  )
}

/* SCA24 — Login est pré-auth : marque produit neutre par env (VITE_PRODUCT_NAME),
   plus AUCUNE chaîne "Taqinor"/"TAQINOR" en dur (première chose qu'un tenant #2
   verrait). Les sélecteurs e2e (login.spec.js/mobile.spec.js) ciblent le
   placeholder, input[type=password] et le libellé du bouton — préservés ici. */
describe('Login (SCA24 — marque produit neutre)', () => {
  afterEach(() => {
    cleanup()
  })

  it('affiche le repli neutre "ERP" quand VITE_PRODUCT_NAME est vide/absent', () => {
    renderLogin()
    // import.meta.env.VITE_PRODUCT_NAME n'est pas défini en test → repli 'ERP'.
    expect(screen.getByText('ERP')).toBeInTheDocument()
  })

  it('zéro occurrence de "Taqinor"/"TAQINOR" dans le DOM rendu', () => {
    const { container } = renderLogin()
    expect(container.textContent).not.toMatch(/taqinor/i)
    // Aucune image de logo Taqinor non plus (asset supprimé de l'écran pré-auth).
    const imgs = Array.from(container.querySelectorAll('img'))
    expect(imgs.find((img) => /taqinor/i.test(img.src) || /taqinor/i.test(img.alt))).toBeUndefined()
  })

  it('préserve les sélecteurs e2e du formulaire (placeholder, password, bouton)', () => {
    renderLogin()
    expect(screen.getByPlaceholderText('Entrez votre identifiant')).toBeInTheDocument()
    expect(document.querySelector('input[type="password"]')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Se connecter →' })).toBeInTheDocument()
  })

  it('UI en français préservée (libellés du formulaire)', () => {
    renderLogin()
    expect(screen.getByText("Nom d'utilisateur")).toBeInTheDocument()
    expect(screen.getByText('Mot de passe')).toBeInTheDocument()
    expect(screen.getByText('Connectez-vous à votre espace de gestion')).toBeInTheDocument()
  })

  // VX150 — le wordmark (repli neutre « ERP ») utilise la police de marque
  // (var(--font-display)), pas une police héritée/hors-système type Arial Black.
  it('le wordmark utilise la police de marque (var(--font-display))', () => {
    renderLogin()
    const wordmark = screen.getByText('ERP')
    expect(wordmark.style.fontFamily).toContain('--font-display')
  })
})
