import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK218 — écran « Quais & rendez-vous ». Réponses = contrat committé
   `wms_quais.json` (ASTK162), jamais retapées ; seul axios est mocké.
   ========================================================================== */

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '../../../api/axios'
import QuaisPage from './QuaisPage'

const R = documentContrat('stock', 'wms_quais').routes
// Les clés fournisseur / bon_commande (ASTK192) sont celles du contrat.
const RDV_AVEC_FOURNISSEUR = {
  ...R.rendez_vous_transporteur.exemple,
  results: [R.rendez_vous_transporteur.exemple_nouveau_astk192],
}

function brancher() {
  api.get.mockImplementation((url) => {
    if (url === '/stock/quais/') return Promise.resolve({ data: R.quais.exemple })
    if (url === '/stock/quais/planning/') return Promise.resolve({ data: R.quais_planning.exemple })
    if (url === '/stock/rendez-vous-transporteur/') return Promise.resolve({ data: RDV_AVEC_FOURNISSEUR })
    if (url === '/stock/unites-logistiques/') return Promise.resolve({ data: { results: [{ id: 5, sscc: '000000000000000017', statut: 'scellee' }] } })
    if (url.includes('export-asn')) return Promise.resolve({ data: R.unite_export_asn.exemple })
    if (url === '/stock/emplacements/') return Promise.resolve({ data: { results: [{ id: 3, nom: 'Dépôt principal' }] } })
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
}

const monter = () => render(<MemoryRouter><QuaisPage /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks(); brancher() })
afterEach(() => { cleanup() })

describe('ASTK218 — QuaisPage', () => {
  it('le planning affiche fournisseur et BCF', async () => {
    monter()
    const planning = await screen.findByRole('region', { name: /Planning/i })
    expect(await within(planning).findByText(/Import Solar SARL/)).toBeInTheDocument()
    expect(within(planning).getByText(/BCF-2026-0047/)).toBeInTheDocument()
    expect(within(planning).getByText(/Quai R1/)).toBeInTheDocument()
  })

  it('un chevauchement affiche le 400 serveur', async () => {
    api.post.mockRejectedValue({
      response: { status: 400, data: R.rendez_vous_transporteur.exemple_erreur_400_chevauchement },
    })
    monter()
    await screen.findByRole('region', { name: /Planning/i })
    fireEvent.change(await screen.findByLabelText('Quai du rendez-vous'), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Début'), { target: { value: '2026-10-12T09:30' } })
    fireEvent.change(screen.getByLabelText('Fin'), { target: { value: '2026-10-12T10:30' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer le rendez-vous/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      R.rendez_vous_transporteur.exemple_erreur_400_chevauchement.detail)
    expect(api.post.mock.calls[0][0]).toBe('/stock/rendez-vous-transporteur/')
    expect(api.post.mock.calls[0][1]).toMatchObject({ quai: 2 })
  })

  it('importer un ASN', async () => {
    api.post.mockResolvedValue({ data: R.unites_import_asn.exemple })
    monter()
    const fichier = new File([JSON.stringify(R.unite_export_asn.exemple)], 'asn.json', { type: 'application/json' })
    fireEvent.change(await screen.findByLabelText('Fichier ASN'), { target: { files: [fichier] } })
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/stock/unites-logistiques/import-asn/', R.unite_export_asn.exemple))
    expect(await screen.findByText(/ASN valide/i)).toBeInTheDocument()
    expect(screen.getByText(/MIC-001/)).toBeInTheDocument()
  })

  it('un ASN invalide affiche ses erreurs', async () => {
    api.post.mockResolvedValue({ data: R.unites_import_asn.exemple_invalide })
    monter()
    const fichier = new File(['{}'], 'asn.json', { type: 'application/json' })
    fireEvent.change(await screen.findByLabelText('Fichier ASN'), { target: { files: [fichier] } })
    expect(await screen.findByText(/clé de contrôle GS1 invalide/i)).toBeInTheDocument()
  })

  it('annule un rendez-vous (statut annule) puis relit le planning', async () => {
    api.patch.mockResolvedValue({ data: {} })
    monter()
    fireEvent.click(await screen.findByRole('button', { name: /Annuler le rendez-vous 17/i }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith(
      '/stock/rendez-vous-transporteur/17/', { statut: 'annule' }))
  })

  it("crée un quai avec le corps attendu", async () => {
    api.post.mockResolvedValue({ data: R.quais.exemple_element })
    monter()
    fireEvent.change(await screen.findByLabelText('Nom du quai'), { target: { value: 'Quai R2' } })
    fireEvent.change(screen.getByLabelText('Type de quai'), { target: { value: 'mixte' } })
    fireEvent.change(screen.getByLabelText("Emplacement du quai"), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter le quai/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/quais/', {
      nom: 'Quai R2', type_quai: 'mixte', emplacement: 3, actif: true,
    }))
  })

  it("exporte l'ASN d'une unité", async () => {
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:x')
    globalThis.URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    monter()
    fireEvent.change(await screen.findByLabelText('Unité à exporter'), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: /Exporter l'ASN/i }))
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/stock/unites-logistiques/5/export-asn/'))
  })
})
