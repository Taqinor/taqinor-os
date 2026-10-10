import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* AFAC18 — gestes « Réaffecter » et « Annuler (erreur de saisie) » à côté de
   « Rejeter » ; état `annule_saisie` distinct de « Rejeté ». Réponses simulées
   LUES dans paiement_reaffecter.json / paiement_annuler_saisie.json. */

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: http }))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getPaiements: vi.fn(),
    importReleveDryRun: vi.fn(),
    importReleveCommit: vi.fn(),
    rejeterPaiement: vi.fn(),
  },
}))
vi.mock('../../hooks/useHasPermission', () => ({
  useHasPermission: () => true,
  useHasRole: () => true,
  useIsAdmin: () => true,
  useIsAdminOrResponsable: () => true,
}))
import ventesApi from '../../api/ventesApi'
import PaiementsPage from './PaiementsPage'

const ICI = dirname(fileURLToPath(import.meta.url))
const contrat = (nom) => JSON.parse(readFileSync(join(
  ICI, '..', '..', '..', '..', 'backend', 'django_core', 'apps', 'facturation',
  'contract_samples', nom), 'utf8'))
const REAFFECTER = contrat('paiement_reaffecter.json')
const ANNULER = contrat('paiement_annuler_saisie.json')

const MAUVAISE = {
  id: 412, facture: 118, facture_reference: 'FAC-2026-10-0007',
  client: 5, client_nom: 'ACME SARL', montant: '5000.00',
  date_paiement: '2026-10-02', mode: 'virement', mode_display: 'Virement',
  statut: 'encaisse',
}
const ANNULE = {
  id: 413, facture: 119, facture_reference: 'FAC-2026-10-0008',
  client: 5, client_nom: 'ACME SARL', montant: '777.00',
  date_paiement: '2026-10-03', mode: 'cheque', mode_display: 'Chèque',
  statut: 'annule_saisie', motif_annulation: ANNULER.exemple.motif_annulation,
}
const CIBLE = { id: 121, reference: 'FAC-2026-10-0009', client: 5, statut: 'emise', encaissable: true }
const AUTRE = { id: 130, reference: 'FAC-AUTRE-CLIENT', client: 9, statut: 'emise', encaissable: true }

beforeEach(() => {
  ventesApi.getPaiements.mockResolvedValue({ data: [MAUVAISE, ANNULE] })
  http.get.mockResolvedValue({ data: [CIBLE, AUTRE, { id: 118, reference: 'FAC-2026-10-0007', client: 5, statut: 'emise' }] })
  http.post.mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderPage = () => render(
  <MemoryRouter initialEntries={['/ventes/paiements']}><PaiementsPage /></MemoryRouter>,
)

describe('PaiementsPage — AFAC18 correction d’un paiement mal saisi', () => {
  it('badge « Annulé (saisie) » distinct de « Rejeté », hors du total', async () => {
    renderPage()
    expect(await screen.findByText('FAC-2026-10-0008')).toBeInTheDocument()
    const badge = screen.getByText('Annulé (saisie)')
    expect(badge).toHaveAttribute('title', ANNULER.exemple.motif_annulation)
    expect(screen.queryByText('Rejeté')).toBeNull()
    expect(screen.getByText('Total encaissé (1)')).toBeInTheDocument()
  })

  it('Réaffecter : envoie facture_cible au contrat, factures du même client seulement', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('FAC-2026-10-0007')
    await user.click(screen.getByRole('button', { name: /Réaffecter/ }))
    const select = await screen.findByLabelText('Facture cible')
    await waitFor(() => expect(screen.getByRole('option', { name: 'FAC-2026-10-0009' })).toBeInTheDocument())
    expect(screen.queryByRole('option', { name: 'FAC-AUTRE-CLIENT' })).toBeNull()
    fireEvent.change(select, { target: { value: String(REAFFECTER.requete.facture_cible) } })
    await user.click(screen.getByRole('button', { name: 'Réaffecter' }))
    await waitFor(() => expect(http.post).toHaveBeenCalledWith(
      '/ventes/paiements/412/reaffecter/', REAFFECTER.requete))
    await waitFor(() => expect(ventesApi.getPaiements).toHaveBeenCalledTimes(2))
  })

  it('Réaffecter : un refus 400 s’affiche sous le champ facture', async () => {
    http.post.mockRejectedValueOnce({ response: { data: REAFFECTER.exemple_refus_autre_client } })
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('FAC-2026-10-0007')
    await user.click(screen.getByRole('button', { name: /Réaffecter/ }))
    const select = await screen.findByLabelText('Facture cible')
    await waitFor(() => screen.getByRole('option', { name: 'FAC-2026-10-0009' }))
    fireEvent.change(select, { target: { value: '121' } })
    await user.click(screen.getByRole('button', { name: 'Réaffecter' }))
    expect(await screen.findByTestId('reaffecter-erreur'))
      .toHaveTextContent(REAFFECTER.exemple_refus_autre_client.detail)
  })

  it('Annuler (erreur de saisie) : motif obligatoire puis envoi au contrat', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('FAC-2026-10-0007')
    await user.click(screen.getByRole('button', { name: /Annuler \(erreur de saisie\)/ }))
    const confirmer = screen.getByRole('button', { name: 'Annuler la saisie' })
    expect(confirmer).toBeDisabled()
    await user.type(screen.getByLabelText(/Motif/), ANNULER.requete.motif)
    await user.click(confirmer)
    await waitFor(() => expect(http.post).toHaveBeenCalledWith(
      '/ventes/paiements/412/annuler-saisie/', ANNULER.requete))
  })

  it('Annuler la saisie : le refus serveur s’affiche sous le motif', async () => {
    http.post.mockRejectedValueOnce({ response: { data: ANNULER.exemple_refus } })
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('FAC-2026-10-0007')
    await user.click(screen.getByRole('button', { name: /Annuler \(erreur de saisie\)/ }))
    await user.type(screen.getByLabelText(/Motif/), 'x')
    await user.click(screen.getByRole('button', { name: 'Annuler la saisie' }))
    expect(await screen.findByTestId('annulation-saisie-erreur'))
      .toHaveTextContent(ANNULER.exemple_refus.detail)
  })

  it('un paiement déjà annulé (saisie) n’offre plus de geste', async () => {
    ventesApi.getPaiements.mockResolvedValue({ data: [ANNULE] })
    renderPage()
    await screen.findByText('FAC-2026-10-0008')
    expect(screen.queryByRole('button', { name: /Réaffecter/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Rejeter/ })).toBeNull()
  })
})
