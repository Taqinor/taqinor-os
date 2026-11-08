// AMON93 — annulation d'un certificat carbone depuis le registre (motif
// obligatoire), puis ligne barrée « annulé le … par … ».
// Nouveau fichier car : la section n'avait aucun test (dit par la tâche AMON93).
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

const emis = {
  id: 4, installation_id: 87, client_id: null, periode_debut: '2025-06-01',
  periode_fin: '2025-06-30', tco2_evitees: '0.405', reference: 'CERT-CO2-202611-0001',
  created_at: '2026-11-01T09:30:00Z', statut: 'emis', motif_annulation: '',
  annule_le: null, annule_par_nom: null,
}

vi.mock('../../../api/monitoringApi', () => ({
  default: {
    getCertificatsCarbone: vi.fn(() => Promise.resolve({ data: { count: 1, next: null, results: [emis] } })),
    annulerCertificatCarbone: vi.fn(() => Promise.resolve({ data: {} })),
    emettreCertificatCarbone: vi.fn(),
    getCertificatCarbonePdf: vi.fn(() => Promise.resolve({ data: new Blob(['%PDF']) })),
  },
}))

import monitoringApi from '../../../api/monitoringApi'
import CertificatsCarboneSection from './CertificatsCarboneSection'

describe('CertificatsCarboneSection (AMON93 — annulation)', () => {
  it('AMON94 — télécharge le PDF du certificat', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:certificat')
    URL.revokeObjectURL = vi.fn()
    render(<MemoryRouter><ThemeProvider><CertificatsCarboneSection systems={[]} loadingSystems={false} /></ThemeProvider></MemoryRouter>)

    await userEvent.click(await screen.findByRole('button', { name: 'PDF' }))
    await waitFor(() => expect(monitoringApi.getCertificatCarbonePdf).toHaveBeenCalledWith(4))
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('AMON96 — nomme le site par sa référence (repli « Système #id » sans référence)', async () => {
    monitoringApi.getCertificatsCarbone.mockResolvedValueOnce({
      data: { count: 2, next: null, results: [
        { ...emis, installation_reference: 'CHT-202611-0087' },
        { ...emis, id: 5, installation_id: 88, reference: 'CERT-CO2-202611-0002', installation_reference: null },
      ] },
    })
    render(<MemoryRouter><ThemeProvider><CertificatsCarboneSection systems={[]} loadingSystems={false} /></ThemeProvider></MemoryRouter>)
    expect(await screen.findByText(/CHT-202611-0087/)).toBeInTheDocument()
    expect(screen.queryByText(/Système #87/)).not.toBeInTheDocument()
    expect(screen.getByText(/Système #88/)).toBeInTheDocument()
  })

  it('annule un certificat avec motif puis l’affiche barré', async () => {
    monitoringApi.getCertificatsCarbone
      .mockResolvedValueOnce({ data: { count: 1, next: null, results: [emis] } })
      .mockResolvedValueOnce({
        data: {
          count: 1, next: null,
          results: [{
            ...emis, statut: 'annule', motif_annulation: 'Relevé corrigé',
            annule_le: '2026-11-08T09:30:00Z', annule_par_nom: 'Responsable SAV',
          }],
        },
      })
    render(<MemoryRouter><ThemeProvider><CertificatsCarboneSection systems={[]} loadingSystems={false} /></ThemeProvider></MemoryRouter>)

    await userEvent.click(await screen.findByRole('button', { name: 'Annuler' }))
    const confirmer = screen.getByRole('button', { name: 'Confirmer l’annulation' })
    expect(confirmer).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Motif de l’annulation'), 'Relevé corrigé')
    await userEvent.click(confirmer)

    await waitFor(() => expect(monitoringApi.annulerCertificatCarbone).toHaveBeenCalledWith(4, 'Relevé corrigé'))
    expect(await screen.findByText(/annulé le .* par Responsable SAV/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Annuler' })).not.toBeInTheDocument()
  })
})
