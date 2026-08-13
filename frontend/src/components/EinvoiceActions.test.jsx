import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../api/einvoiceApi', () => ({
  default: {
    generer: vi.fn(),
    telecharger: vi.fn(() => Promise.resolve({ data: new Blob(['<xml/>']) })),
    // PACT54 — `controler` était wrappé mais jamais appelé ; `transmettre`
    // n'avait aucun wrapper. Les deux sont désormais exposés par ce composant.
    controler: vi.fn(),
    transmettre: vi.fn(),
  },
}))
vi.mock('../utils/downloadBlob', () => ({ downloadBlob: vi.fn() }))

import einvoiceApi from '../api/einvoiceApi'
import { downloadBlob } from '../utils/downloadBlob'
import EinvoiceActions from './EinvoiceActions'

describe('EinvoiceActions (WIR106)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('génère une e-facture dry-run et propose le téléchargement du XML', async () => {
    einvoiceApi.generer.mockResolvedValueOnce({ status: 201, data: { id: 12, version: 1 } })
    render(<EinvoiceActions factureId={5} />)
    fireEvent.click(screen.getByRole('button', { name: /Générer e-facture/ }))
    await waitFor(() => expect(einvoiceApi.generer).toHaveBeenCalledWith(5, 'dry_run'))
    const dl = await screen.findByRole('button', { name: /Télécharger XML/ })
    fireEvent.click(dl)
    await waitFor(() => expect(einvoiceApi.telecharger).toHaveBeenCalledWith(12))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled())
  })

  it('affiche « désactivée » quand le serveur renvoie 204 (EINVOICE_ENABLED off)', async () => {
    einvoiceApi.generer.mockResolvedValueOnce({ status: 204, data: null })
    render(<EinvoiceActions factureId={5} />)
    fireEvent.click(screen.getByRole('button', { name: /Générer e-facture/ }))
    expect(await screen.findByText(/E-facturation désactivée/)).toBeInTheDocument()
  })

  /* PACT54 — contrôle avant envoi + transmission : les deux moitiés vont
     ensemble (un contrôle sans envoi ne sert à rien, un envoi sans contrôle
     est dangereux). La transmission reste inerte sans credential DGI. */
  it('« Contrôler » liste les anomalies bloquantes', async () => {
    einvoiceApi.generer.mockResolvedValueOnce({ status: 201, data: { id: 12, version: 1 } })
    einvoiceApi.controler.mockResolvedValueOnce({
      data: { anomalies: ['ICE du client manquant.'], conforme: false },
    })
    render(<EinvoiceActions factureId={5} />)
    fireEvent.click(screen.getByRole('button', { name: /Générer e-facture/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Contrôler/ }))

    await waitFor(() => expect(einvoiceApi.controler).toHaveBeenCalledWith(12))
    expect(await screen.findByText('ICE du client manquant.')).toBeInTheDocument()
  })

  it('« Contrôler » confirme la conformité quand aucune anomalie', async () => {
    einvoiceApi.generer.mockResolvedValueOnce({ status: 201, data: { id: 12, version: 1 } })
    einvoiceApi.controler.mockResolvedValueOnce({ data: { anomalies: [], conforme: true } })
    render(<EinvoiceActions factureId={5} />)
    fireEvent.click(screen.getByRole('button', { name: /Générer e-facture/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Contrôler/ }))

    expect(await screen.findByText(/aucune anomalie bloquante/)).toBeInTheDocument()
  })

  it('« Transmettre » enregistre l\'intention et montre son statut', async () => {
    einvoiceApi.generer.mockResolvedValueOnce({ status: 201, data: { id: 12, version: 1 } })
    einvoiceApi.transmettre.mockResolvedValueOnce({
      data: { id: 3, einvoice: 12, statut: 'en_attente', tentatives: 0 },
    })
    render(<EinvoiceActions factureId={5} />)
    fireEvent.click(screen.getByRole('button', { name: /Générer e-facture/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Transmettre/ }))

    await waitFor(() => expect(einvoiceApi.transmettre).toHaveBeenCalledWith(12))
    expect(await screen.findByText(/Transmission enregistrée/)).toBeInTheDocument()
    expect(screen.getByText('en_attente')).toBeInTheDocument()
  })
})
