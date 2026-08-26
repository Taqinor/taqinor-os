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
    // WIR223 — le composant se réhydrate au montage : par défaut, aucune
    // version existante (comportement historique des tests ci-dessous).
    list: vi.fn(() => Promise.resolve({ data: [] })),
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

/* WIR223 — l'état ne vivait QUE dans le state local posé par le clic sur
   « Générer » : après un rechargement de la fiche, une e-facture pourtant
   DÉJÀ générée redevenait invisible, et la seule porte de sortie était de
   re-cliquer « Générer » — ce qui ajoute une version de plus à l'historique
   à chaque fois. */
describe('EinvoiceActions (WIR223 — réhydratation au montage)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('liste les versions de la facture au montage', async () => {
    einvoiceApi.list.mockResolvedValueOnce({ data: [] })
    render(<EinvoiceActions factureId={5} />)
    await waitFor(() => expect(einvoiceApi.list)
      .toHaveBeenCalledWith({ facture_id: 5 }))
  })

  it('liste VIDE : seul « Générer » est proposé (comportement inchangé)', async () => {
    einvoiceApi.list.mockResolvedValueOnce({ data: [] })
    render(<EinvoiceActions factureId={5} />)
    await waitFor(() => expect(einvoiceApi.list).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: /Générer e-facture/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Télécharger XML/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Contrôler/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Transmettre/ })).toBeNull()
  })

  it('liste PLEINE : les trois actions sont là SANS recliquer « Générer »', async () => {
    einvoiceApi.list.mockResolvedValueOnce({
      data: {
        results: [
          { id: 41, version: 2, mode: 'dry_run' },
          { id: 40, version: 1, mode: 'dry_run' },
        ],
      },
    })
    render(<EinvoiceActions factureId={5} />)
    expect(await screen.findByRole('button', { name: /Télécharger XML/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Contrôler/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Transmettre/ })).toBeInTheDocument()
    expect(einvoiceApi.generer).not.toHaveBeenCalled()
  })

  it('retient la version la PLUS RÉCENTE, quel que soit l’ordre reçu', async () => {
    einvoiceApi.list.mockResolvedValueOnce({
      data: [
        { id: 40, version: 1, mode: 'dry_run' },
        { id: 42, version: 3, mode: 'dry_run' },
        { id: 41, version: 2, mode: 'dry_run' },
      ],
    })
    render(<EinvoiceActions factureId={5} />)
    fireEvent.click(await screen.findByRole('button', { name: /Télécharger XML/ }))
    await waitFor(() => expect(einvoiceApi.telecharger).toHaveBeenCalledWith(42))
    expect(screen.getByText(/version 3/)).toBeInTheDocument()
  })

  it('un échec de lecture (403, réseau) reste SILENCIEUX', async () => {
    einvoiceApi.list.mockRejectedValueOnce({ response: { status: 403 } })
    render(<EinvoiceActions factureId={5} />)
    await waitFor(() => expect(einvoiceApi.list).toHaveBeenCalled())
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByRole('button', { name: /Générer e-facture/ })).toBeInTheDocument()
  })

  it('une génération fraîche n’est jamais piétinée par la réhydratation', async () => {
    let resoudreListe
    einvoiceApi.list.mockReturnValueOnce(new Promise((r) => { resoudreListe = r }))
    einvoiceApi.generer.mockResolvedValueOnce({ status: 201, data: { id: 99, version: 7 } })
    render(<EinvoiceActions factureId={5} />)
    fireEvent.click(screen.getByRole('button', { name: /Générer e-facture/ }))
    await waitFor(() => expect(einvoiceApi.generer).toHaveBeenCalled())
    // La liste répond APRÈS, avec une version plus ancienne : elle ne doit pas
    // remplacer celle que l'utilisateur vient de générer.
    resoudreListe({ data: [{ id: 40, version: 1, mode: 'dry_run' }] })
    await waitFor(() => expect(screen.getByText(/version 7/)).toBeInTheDocument())
  })
})
