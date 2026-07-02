import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   QS1 — bouton « PDF (interne) » du bon de commande fournisseur.
   Avant : tout échec (403 permission, HTML d'erreur, réseau) était avalé en
   « PDF indisponible. » et rien ne s'ouvrait. Après : le PDF s'ouvre dans un
   nouvel onglet (repli téléchargement si popup bloquée) et la VRAIE erreur
   serveur est affichée (lue depuis le Blob d'erreur DRF).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: { bcfPdf: vi.fn() },
}))

import stockApi from '../../api/stockApi'
import { BcfDetail } from './BonsCommandeFournisseur.jsx'
import { messageErreurBlob } from '../../utils/pdfBlob'

function wrapper({ children }) {
  return (
    <MemoryRouter>
      <ThemeProvider>{children}</ThemeProvider>
    </MemoryRouter>
  )
}

const bcf = {
  id: 42,
  reference: 'BCF-2026-07-0042',
  statut: 'recu',
  fournisseur: 1,
  lignes: [],
}

function renderDetail() {
  return render(
    <BcfDetail bcf={bcf} fournisseurs={[]} produits={[]}
               onClose={() => {}} onSaved={() => {}} />,
    { wrapper },
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
