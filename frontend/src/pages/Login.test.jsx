import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// On neutralise le module axios pour ne dépendre d'aucun réseau. Le stub doit
// se COMPORTER comme axios (renvoyer une promesse) : Login monte désormais
// `portailApi.themePublic()` (NTPRT19, marque white-label résolue par domaine),
// un vrai client bâti sur ce module — un `vi.fn()` nu renverrait `undefined` et
// ferait planter le `.then()` de l'effet au montage.
vi.mock('../api/axios', () => ({
  default: {
    post: vi.fn(() => Promise.resolve({ data: {} })),
    get: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
// WIR134 — bannière légale résolue par identityApi (pré-auth) : stub par défaut
// sans bannière (surchargé dans le test dédié).
const { bannerGet, bannerAck } = vi.hoisted(() => ({
  bannerGet: vi.fn(() => Promise.resolve({ data: { login_banner_text: '' } })),
  bannerAck: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../api/identityApi', () => ({
  default: { loginBanner: { get: bannerGet, acknowledge: bannerAck } },
}))
// NTPRT19 — la marque white-label est resolue par le DOMAINE appelant. Par
// defaut : aucun theme (domaine generique). Le test dedie la surcharge.
const { themePublic } = vi.hoisted(() => ({
  themePublic: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../api/portailApi', () => ({ default: { themePublic } }))

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

/* SCA24 + ODY33 — Login est pré-auth, donc la marque affichée dépend du seul
   DOMAINE appelant (NTPRT19) :
     • domaine d'une société cliente (TenantTheme) → SA marque, et zéro
       occurrence de « Taqinor » — c'est l'invariant que SCA24 protège, et il
       est intégralement conservé ;
     • domaine générique → notre portail à nous, donc notre marque. Le repli
       « E » bleu + étiquette « ERP » d'avant n'appartenait à personne ; le
       fondateur (2026-08-02) l'a remplacé par le mot-symbole Taqinor.
   Les sélecteurs e2e (login.spec.js/mobile.spec.js) ciblent le placeholder,
   input[type=password] et le libellé du bouton — préservés ici. */
describe('Login (SCA24/ODY33 — marque résolue par le domaine)', () => {
  afterEach(() => {
    cleanup()
    themePublic.mockClear()
  })

  it('domaine générique : le repli porte le mot-symbole ET le nom Taqinor', async () => {
    renderLogin()
    // VITE_PRODUCT_NAME n'est pas défini en test → repli de marque produit.
    expect(await screen.findByText('Taqinor')).toBeInTheDocument()
    // Le mot-symbole VX154 (SVG tokenisé), pas un carré à initiale.
    expect(document.querySelector('svg.taqinor-mark')).toBeInTheDocument()
  })

  it('domaine générique : le bouton est en BRASS, jamais le bleu générique', async () => {
    renderLogin()
    const bouton = await screen.findByRole('button', { name: 'Se connecter →' })
    expect(bouton.style.background).toContain('--login-brass')
    expect(bouton.style.background).not.toContain('--login-azur')
  })

  it('SCA24 — domaine d’un tenant : SA marque, et zéro « Taqinor » dans le DOM', async () => {
    themePublic.mockResolvedValueOnce({
      data: { nom_affichage: 'Solaris SARL', couleur_primaire: '#118844' },
    })
    const { container } = renderLogin()
    expect(await screen.findByText('Solaris SARL')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/taqinor/i)
    expect(container.querySelector('svg.taqinor-mark')).toBeNull()
    // Et son bouton reste EXACTEMENT celui d'avant (azur), pas notre brass.
    const bouton = screen.getByRole('button', { name: 'Se connecter →' })
    expect(bouton.style.background).toContain('--login-azur')
  })

  it('SCA24 — logo de tenant : aucune image de marque Taqinor', async () => {
    themePublic.mockResolvedValueOnce({
      data: { nom_affichage: 'Solaris SARL', logo_url: 'https://exemple.ma/logo.png' },
    })
    const { container } = renderLogin()
    await screen.findByAltText('Solaris SARL')
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

  // VX150 — le wordmark utilise la police de marque (var(--font-display)), pas
  // une police héritée/hors-système type Arial Black.
  it('le wordmark utilise la police de marque (var(--font-display))', async () => {
    renderLogin()
    const wordmark = await screen.findByText('Taqinor')
    expect(wordmark.style.fontFamily).toContain('--font-display')
  })
})

describe('Login — WIR134/NTSEC28 bannière légale de connexion', () => {
  afterEach(() => { cleanup(); bannerGet.mockClear() })

  it('affiche la bannière résolue par username (au blur)', async () => {
    bannerGet.mockResolvedValueOnce({
      data: { login_banner_text: 'Accès réservé au personnel autorisé.' },
    })
    renderLogin()
    const input = screen.getByPlaceholderText('Entrez votre identifiant')
    fireEvent.change(input, { target: { value: 'reda' } })
    fireEvent.blur(input)
    await waitFor(() => expect(bannerGet).toHaveBeenCalledWith('reda'))
    expect(await screen.findByTestId('login-banner'))
      .toHaveTextContent('Accès réservé au personnel autorisé.')
  })

  it('n’affiche aucun bandeau quand aucune bannière n’est configurée', async () => {
    renderLogin()
    const input = screen.getByPlaceholderText('Entrez votre identifiant')
    fireEvent.change(input, { target: { value: 'sami' } })
    fireEvent.blur(input)
    await waitFor(() => expect(bannerGet).toHaveBeenCalled())
    expect(screen.queryByTestId('login-banner')).not.toBeInTheDocument()
  })
})
