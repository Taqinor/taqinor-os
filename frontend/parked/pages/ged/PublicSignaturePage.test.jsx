import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import gedApi from '../../api/gedApi'
import PublicSignaturePage from './PublicSignaturePage.jsx'

/* XGED1/XGED2 — cérémonie de signature publique : consultation → consentement
   → signature/refus. Toutes les données gedApi sont mockées ; on vérifie le
   déroulé heureux (signer), le garde-fou du consentement, le refus, et l'état
   « lien invalide » (jamais de faux succès). */

vi.mock('../../api/gedApi', () => ({
  default: {
    getSignaturePublique: vi.fn(),
    signerPublique: vi.fn(),
    refuserPublique: vi.fn(),
    getSignatairePublique: vi.fn(),
    signerSignataire: vi.fn(),
    refuserSignataire: vi.fn(),
    envoyerCodeSignataire: vi.fn(),
    validerCodeSignataire: vi.fn(),
    getVersions: vi.fn(() => Promise.resolve({ data: [] })),
    apercuVersionUrl: (id) => `/api/django/ged/versions/${id}/apercu/`,
  },
}))

function renderAt(path, element) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/ged/signature/:token" element={element} />
          <Route path="/ged/signataire/:token" element={element} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('XGED1 PublicSignaturePage (mono-signataire)', () => {
  it('consulte, consent puis signe le document', async () => {
    gedApi.getSignaturePublique.mockResolvedValue({
      data: {
        document_nom: 'NDA.pdf', document_id: 7,
        signataire_nom: 'Amine', statut: 'en_attente', champs: [],
      },
    })
    gedApi.signerPublique.mockResolvedValue({ data: { statut: 'signe' } })

    renderAt('/ged/signature/tok-123', <PublicSignaturePage mode="signature" />)

    await waitFor(() => expect(screen.getByText('NDA.pdf')).toBeInTheDocument())

    // Le bouton Signer est désactivé tant qu'on n'a pas consenti.
    const signer = screen.getByRole('button', { name: /Signer le document/i })
    expect(signer).toBeDisabled()

    await userEvent.click(screen.getByRole('checkbox'))
    expect(signer).toBeEnabled()
    await userEvent.click(signer)

    await waitFor(() =>
      expect(gedApi.signerPublique).toHaveBeenCalledWith(
        'tok-123', expect.objectContaining({ consentement: true })))
    await waitFor(() =>
      expect(screen.getByText(/votre signature a bien été enregistrée/i))
        .toBeInTheDocument())
  })

  it('refuse avec un motif', async () => {
    gedApi.getSignaturePublique.mockResolvedValue({
      data: { document_nom: 'Contrat.pdf', document_id: 3, statut: 'en_attente', champs: [] },
    })
    gedApi.refuserPublique.mockResolvedValue({ data: { statut: 'refuse' } })

    renderAt('/ged/signature/tok-9', <PublicSignaturePage mode="signature" />)
    await waitFor(() => expect(screen.getByText('Contrat.pdf')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /^Refuser$/i }))
    await userEvent.type(screen.getByLabelText(/Motif du refus/i), 'Montant erroné')
    await userEvent.click(screen.getByRole('button', { name: /Confirmer le refus/i }))

    await waitFor(() =>
      expect(gedApi.refuserPublique).toHaveBeenCalledWith(
        'tok-9', { motif: 'Montant erroné' }))
    await waitFor(() =>
      expect(screen.getByText(/refusé de signer/i)).toBeInTheDocument())
  })

  it('affiche un message honnête sur un lien invalide (404)', async () => {
    gedApi.getSignaturePublique.mockRejectedValue({ response: { status: 404 } })
    renderAt('/ged/signature/bad', <PublicSignaturePage mode="signature" />)
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/introuvable|expiré/i))
  })
})

describe('XGED2 PublicSignaturePage (signataire d’un circuit)', () => {
  it('consulte via le jeton du destinataire', async () => {
    gedApi.getSignatairePublique.mockResolvedValue({
      data: {
        document_nom: 'Circuit.pdf', document_id: 12, nom: 'Sofia',
        role: 'approbateur', statut: 'notifie', demande_statut: 'en_cours',
        otp_requis: false, champs: [],
      },
    })
    renderAt('/ged/signataire/sig-1', <PublicSignaturePage mode="signataire" />)
    await waitFor(() => expect(screen.getByText('Circuit.pdf')).toBeInTheDocument())
    expect(gedApi.getSignatairePublique).toHaveBeenCalledWith('sig-1')
    // Le bouton de signature est présent (OTP non requis).
    expect(screen.getByRole('button', { name: /Signer le document/i })).toBeInTheDocument()
  })
})
