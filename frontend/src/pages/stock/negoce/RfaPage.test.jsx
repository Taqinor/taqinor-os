import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK222 — écran « Remises arrière (RFA) ». Réponses = contrat committé
   `negoce_consignation_rfa.json` (ASTK164) ; seul axios est mocké.
   ========================================================================== */

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '../../../api/axios'
import RfaPage from './RfaPage'

const R = documentContrat('stock', 'negoce_consignation_rfa').routes
const ACCORDS = R.accords_rfa_fournisseur.exemple
const CALCUL = R.accord_rfa_calcul.exemple
const AVOIR = R.accord_rfa_generer_avoir.exemple

let etat
function brancher() {
  etat = ACCORDS
  api.get.mockImplementation((url) => {
    if (url === '/stock/accords-rfa-fournisseur/') return Promise.resolve({ data: etat })
    if (url === '/stock/accords-rfa-fournisseur/3/calcul/') return Promise.resolve({ data: CALCUL })
    if (url === '/stock/fournisseurs/') return Promise.resolve({ data: { results: [{ id: 5, nom: 'Import Solar SARL' }] } })
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
}

const monter = () => render(<MemoryRouter><RfaPage /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks(); brancher() })
afterEach(() => { cleanup() })

describe('ASTK222 — RfaPage', () => {
  it('affiche le calcul', async () => {
    monter()
    fireEvent.click(await screen.findByRole('button', { name: /Voir le calcul/i }))
    expect(await screen.findByText(/Seuil atteint/i)).toBeInTheDocument()
    expect(screen.getByText(/Progression : 100 %/)).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/stock/accords-rfa-fournisseur/3/calcul/')
  })

  it("générer l'avoir une seule fois", async () => {
    let resoudre
    api.post.mockImplementation(() => new Promise((res) => {
      resoudre = () => {
        etat = { ...ACCORDS, results: [{ ...ACCORDS.results[0], avoir_deja_genere: true }] }
        res({ data: AVOIR })
      }
    }))
    monter()
    const bouton = await screen.findByRole('button', { name: /Générer l'avoir/i })
    fireEvent.click(bouton)
    // désactivé PENDANT l'envoi : un second clic n'appelle rien
    await waitFor(() => expect(bouton).toBeDisabled())
    fireEvent.click(bouton)
    expect(api.post).toHaveBeenCalledTimes(1)
    resoudre()
    expect(await screen.findByText(/AVF-2026-10-0001/)).toBeInTheDocument()
    // désactivé APRÈS génération
    expect(screen.getByRole('button', { name: /Avoir déjà généré/i })).toBeDisabled()
    expect(api.post).toHaveBeenCalledWith('/stock/accords-rfa-fournisseur/3/generer-avoir/')
  })

  it('un accord dont l\'avoir existe déjà ne propose pas de générer', async () => {
    etat = { ...ACCORDS, results: [{ ...ACCORDS.results[0], avoir_deja_genere: true }] }
    monter()
    expect(await screen.findByRole('button', { name: /Avoir déjà généré/i })).toBeDisabled()
    expect(screen.queryByRole('button', { name: /^Générer l'avoir/i })).toBeNull()
  })

  it('ERR-ASTK222 — la référence de l avoir survit au rechargement (servie par l accord relu)', async () => {
    etat = { ...ACCORDS, results: [{
      ...ACCORDS.results[0], avoir_deja_genere: true, avoir_genere: 21, avoir_id: 21, avoir_reference: 'AVF-2026-10-0001',
    }] }
    monter()
    expect(await screen.findByText(/Avoir AVF-2026-10-0001 généré/)).toBeInTheDocument()
  })

  it('un second POST refusé par le serveur affiche son message', async () => {
    api.post.mockRejectedValue({
      response: { status: 400, data: R.accord_rfa_generer_avoir.exemple_erreur_400 },
    })
    monter()
    fireEvent.click(await screen.findByRole('button', { name: /Générer l'avoir/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(R.accord_rfa_generer_avoir.exemple_erreur_400.detail)
  })

  it('crée un accord avec le corps attendu', async () => {
    api.post.mockResolvedValue({ data: R.accords_rfa_fournisseur.exemple_element })
    monter()
    fireEvent.change(await screen.findByLabelText('Fournisseur'), { target: { value: '5' } })
    fireEvent.change(screen.getByLabelText('Début de période'), { target: { value: '2026-01-01' } })
    fireEvent.change(screen.getByLabelText('Fin de période'), { target: { value: '2026-12-31' } })
    fireEvent.change(screen.getByLabelText("Seuil de CA d'achat"), { target: { value: '100000' } })
    fireEvent.change(screen.getByLabelText('Taux (%)'), { target: { value: '2.5' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer l'accord/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/accords-rfa-fournisseur/', {
      fournisseur: 5, periode_debut: '2026-01-01', periode_fin: '2026-12-31',
      seuil_ca_achat: '100000', taux_pct: '2.5',
    }))
  })

  it('une erreur de validation à la création est affichée telle quelle', async () => {
    api.post.mockRejectedValue({ response: { status: 400, data: R.accords_rfa_fournisseur.exemple_erreur_400 } })
    monter()
    fireEvent.change(await screen.findByLabelText('Fournisseur'), { target: { value: '5' } })
    fireEvent.change(screen.getByLabelText('Début de période'), { target: { value: '2026-01-01' } })
    fireEvent.change(screen.getByLabelText('Fin de période'), { target: { value: '2026-12-31' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer l'accord/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Renseignez soit un taux (%), soit un montant fixe.')
  })
})
