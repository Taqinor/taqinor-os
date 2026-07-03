import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   QS1 — bouton « PDF (interne) » du bon de commande fournisseur.
   Avant : tout échec (403 permission, HTML d'erreur, réseau) était avalé en
   « PDF indisponible. » et rien ne s'ouvrait. Après : le PDF s'ouvre dans un
   nouvel onglet (repli téléchargement si popup bloquée) et la VRAIE erreur
   serveur est affichée (lue depuis le Blob d'erreur DRF).

   QS2 — « + Nouveau produit » dans le BCF (réservé Directeur/Commercial
   responsable), QS4 — boutons Envoyer WhatsApp / email (grisés sans contact).
   Le BcfDetail consulte désormais le hook de rôle → Provider Redux requis.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    bcfPdf: vi.fn(),
    createProduit: vi.fn(),
    whatsappBcf: vi.fn(),
    envoyerEmailBcf: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import { BcfDetail } from './BonsCommandeFournisseur.jsx'
import { messageErreurBlob } from '../../utils/pdfBlob'

function makeStore({ role_nom = 'Magasinier', permissions = [] } = {}) {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom, permissions,
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function makeWrapper(authState) {
  return function wrapper({ children }) {
    return (
      <Provider store={makeStore(authState)}>
        <MemoryRouter>
          <ThemeProvider>{children}</ThemeProvider>
        </MemoryRouter>
      </Provider>
    )
  }
}

const bcf = {
  id: 42,
  reference: 'BCF-2026-07-0042',
  statut: 'recu',
  fournisseur: 1,
  lignes: [],
}

function renderDetail(props = {}, authState) {
  return render(
    <BcfDetail bcf={bcf} fournisseurs={[]} produits={[]}
               onClose={() => {}} onSaved={() => {}} {...props} />,
    { wrapper: makeWrapper(authState) },
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  // jsdom n'implémente pas createObjectURL ; matchMedia requis par la densité.
  URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  URL.revokeObjectURL = vi.fn()
  window.open = vi.fn(() => ({}))
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
})

describe('QS1 — PDF (interne) : ouverture', () => {
  it('ouvre le PDF dans un nouvel onglet quand le serveur renvoie un PDF', async () => {
    stockApi.bcfPdf.mockResolvedValue({
      data: new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
    })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    await waitFor(() => {
      expect(window.open).toHaveBeenCalledWith('blob:mock-url', '_blank', 'noopener')
    })
    expect(stockApi.bcfPdf).toHaveBeenCalledWith(42)
    // Pas de message d'erreur.
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('retombe sur un téléchargement direct si la popup est bloquée', async () => {
    stockApi.bcfPdf.mockResolvedValue({
      data: new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
    })
    window.open = vi.fn(() => null) // popup bloquée
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    await waitFor(() => { expect(clickSpy).toHaveBeenCalled() })
    clickSpy.mockRestore()
  })

  it('refuse honnêtement une réponse qui n\'est pas un PDF (HTML d\'erreur)', async () => {
    stockApi.bcfPdf.mockResolvedValue({
      data: new Blob(['<html>boom</html>'], { type: 'text/html' }),
    })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(/n['’]a pas renvoyé de PDF/)
    expect(window.open).not.toHaveBeenCalled()
  })
})

describe('QS1 — PDF (interne) : la vraie erreur est affichée', () => {
  it('affiche le détail DRF lu depuis le Blob d\'erreur (plus de « PDF indisponible »)', async () => {
    stockApi.bcfPdf.mockRejectedValue({
      response: {
        status: 403,
        data: new Blob(
          [JSON.stringify({ detail: 'Réservé aux responsables et administrateurs.' })],
          { type: 'application/json' },
        ),
      },
    })
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Réservé aux responsables et administrateurs.')
    expect(alert.textContent).not.toContain('PDF indisponible')
  })

  it('affiche un message réseau explicite quand le serveur est injoignable', async () => {
    stockApi.bcfPdf.mockRejectedValue(new Error('Network Error'))
    renderDetail()
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(/injoignable/)
  })
})

describe('QS1 — messageErreurBlob (unitaire)', () => {
  it('parse un Blob JSON DRF', async () => {
    const err = {
      response: {
        status: 400,
        data: new Blob([JSON.stringify({ detail: 'Erreur métier.' })],
          { type: 'application/json' }),
      },
    }
    expect(await messageErreurBlob(err)).toBe('Erreur métier.')
  })

  it('403 sans corps lisible → message permission explicite', async () => {
    const err = {
      response: { status: 403, data: new Blob(['not json'], { type: 'text/plain' }) },
    }
    expect(await messageErreurBlob(err)).toMatch(/Accès refusé/)
  })

  it('accepte aussi une donnée déjà décodée (objet)', async () => {
    const err = { response: { status: 500, data: { detail: 'Erreur interne.' } } }
    expect(await messageErreurBlob(err)).toBe('Erreur interne.')
  })
})

// ── QS2 — « + Nouveau produit » dans le BCF (réservé Directeur/Commercial resp.) ─
const newBcf = { fournisseur: '', lignes: [{ produit: '', quantite: 1, prix_achat_unitaire: '' }] }

describe('QS2 — création produit inline dans le BCF', () => {
  it('rôle non autorisé (Magasinier) : bouton « Nouveau produit » absent', () => {
    renderDetail({ bcf: newBcf, produits: [] }, { role_nom: 'Magasinier', permissions: [] })
    expect(screen.queryByLabelText('Nouveau produit')).toBeNull()
  })

  it('rôle autorisé (Directeur) : bouton présent, crée + dépose sur la ligne avec prix d\'achat', async () => {
    stockApi.createProduit.mockResolvedValue({
      data: { id: 55, nom: 'Module test', prix_vente: 5000, prix_achat: 3200, is_archived: false },
    })
    renderDetail({ bcf: newBcf, produits: [] }, { role_nom: 'Directeur', permissions: ['stock_creer'] })
    fireEvent.click(screen.getByLabelText('Nouveau produit'))
    fireEvent.change(screen.getByLabelText(/Nom du produit/), { target: { value: 'Module test' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer et sélectionner/ }))
    await waitFor(() => expect(stockApi.createProduit).toHaveBeenCalled())
    // La ligne pointe désormais sur le nouveau produit (nom affiché dans le picker).
    await waitFor(() => expect(screen.getByText('Module test')).toBeInTheDocument())
    // Prix d'achat U. (interne) pré-rempli depuis prix_achat renvoyé par le serveur.
    await waitFor(() => expect(screen.getByDisplayValue('3200')).toBeInTheDocument())
  })

  it('rôle autorisé (Commercial responsable) : bouton présent', () => {
    renderDetail({ bcf: newBcf, produits: [] },
      { role_nom: 'Commercial responsable', permissions: ['stock_creer'] })
    expect(screen.getByLabelText('Nouveau produit')).toBeInTheDocument()
  })
})

// ── QS4 — Envoyer WhatsApp / email (grisés sans contact, reflètent ENVOYE) ──
const fournisseursAvecContact = [
  { id: 1, nom: 'Fourni Plus', telephone: '+212600000001', email: 'contact@fourni.ma' },
]
const fournisseursSansContact = [{ id: 1, nom: 'Fourni Muet', telephone: '', email: '' }]

describe('QS4 — envois fournisseur WhatsApp / email', () => {
  it('fournisseur avec téléphone + email : les deux boutons sont actifs', () => {
    renderDetail({ fournisseurs: fournisseursAvecContact })
    expect(screen.getByRole('button', { name: /Envoyer par WhatsApp/ })).toBeEnabled()
    expect(screen.getByRole('button', { name: /Envoyer par email/ })).toBeEnabled()
  })

  it('fournisseur sans contact : les deux boutons sont grisés avec un tooltip', () => {
    renderDetail({ fournisseurs: fournisseursSansContact })
    const wa = screen.getByRole('button', { name: /Envoyer par WhatsApp/ })
    const mail = screen.getByRole('button', { name: /Envoyer par email/ })
    expect(wa).toBeDisabled()
    expect(mail).toBeDisabled()
    expect(wa).toHaveAttribute('title', expect.stringMatching(/pas de numéro/))
    expect(mail).toHaveAttribute('title', expect.stringMatching(/pas d['’]adresse email/))
  })

  it('WhatsApp : appelle QS3, ouvre le lien wa.me et reflète l\'état ENVOYE', async () => {
    stockApi.whatsappBcf.mockResolvedValue({
      data: { wa_url: 'https://wa.me/212600000001?text=x', statut: 'envoye' },
    })
    const onSaved = vi.fn()
    renderDetail({ fournisseurs: fournisseursAvecContact, onSaved })
    fireEvent.click(screen.getByRole('button', { name: /Envoyer par WhatsApp/ }))
    await waitFor(() => expect(stockApi.whatsappBcf).toHaveBeenCalledWith(42))
    expect(window.open).toHaveBeenCalledWith('https://wa.me/212600000001?text=x', '_blank', 'noopener')
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })

  it('email : appelle QS3 et affiche la confirmation', async () => {
    stockApi.envoyerEmailBcf.mockResolvedValue({
      data: { detail: 'Email envoyé à contact@fourni.ma.', statut: 'envoye' },
    })
    const onSaved = vi.fn()
    renderDetail({ fournisseurs: fournisseursAvecContact, onSaved })
    fireEvent.click(screen.getByRole('button', { name: /Envoyer par email/ }))
    await waitFor(() => expect(stockApi.envoyerEmailBcf).toHaveBeenCalledWith(42))
    expect(await screen.findByText(/Email envoyé à contact@fourni\.ma/)).toBeInTheDocument()
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
  })
})
