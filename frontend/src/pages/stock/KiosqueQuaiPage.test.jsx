import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK219 — kiosque de quai public (/quai/checkin). Réponses = contrat
   committé `wms_quais.json` (ASTK162) ; seul axios est mocké (le client
   public est une instance `axios.create`, sans cookie).
   ========================================================================== */

const client = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({ default: { create: vi.fn(() => client) } }))

import KiosqueQuaiPage from './KiosqueQuaiPage'

const R = documentContrat('stock', 'wms_quais').routes
const CHECKIN = R.public_quai_checkin

const monter = (url = '/quai/checkin?societe=taqinor') => render(
  <MemoryRouter initialEntries={[url]}><KiosqueQuaiPage /></MemoryRouter>)

function saisir(code) {
  fireEvent.change(screen.getByLabelText("Code d'arrivée"), { target: { value: code } })
  fireEvent.click(screen.getByRole('button', { name: /Je suis arrivé/i }))
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('ASTK219 — KiosqueQuaiPage', () => {
  it('code valide affiche le quai', async () => {
    client.post.mockResolvedValue({ data: CHECKIN.exemple })
    monter()
    saisir(CHECKIN.exemple_corps.code)
    expect(await screen.findByText(/Arrivée enregistrée — quai Quai R1/)).toBeInTheDocument()
    expect(client.post).toHaveBeenCalledWith(
      '/api/django/public/stock/quai-checkin/', CHECKIN.exemple_corps)
  })

  it('code inconnu affiche le message serveur', async () => {
    client.post.mockRejectedValue({ response: { status: 404, data: CHECKIN.exemple_erreur_404 } })
    monter()
    saisir('ZZZZZZZZ')
    expect(await screen.findByRole('alert')).toHaveTextContent(CHECKIN.exemple_erreur_404.detail)
  })

  it('429 affiché', async () => {
    client.post.mockRejectedValue({
      response: { status: 429, data: { detail: 'Request was throttled. Expected available in 12 seconds.' } },
    })
    monter()
    saisir('K7M2PQ9X')
    expect(await screen.findByRole('alert')).toHaveTextContent(/Trop de tentatives/)
    expect(screen.getByRole('alert')).toHaveTextContent(/12 secondes/)
  })

  it("un second envoi du même code reste idempotent (même confirmation)", async () => {
    client.post.mockResolvedValue({ data: CHECKIN.exemple })
    monter()
    saisir('K7M2PQ9X')
    await screen.findByText(/Arrivée enregistrée/)
    saisir('K7M2PQ9X')
    await waitFor(() => expect(client.post).toHaveBeenCalledTimes(2))
    expect(screen.getAllByText(/Arrivée enregistrée — quai Quai R1/)).toHaveLength(1)
  })

  it("n'affiche aucune donnée de société ni de prix", async () => {
    client.post.mockResolvedValue({ data: CHECKIN.exemple })
    monter()
    saisir('K7M2PQ9X')
    await screen.findByText(/Arrivée enregistrée/)
    expect(document.body.textContent).not.toMatch(/prix|marge|MAD|DH/i)
  })

  it('demande la société quand le lien ne la porte pas', async () => {
    client.post.mockResolvedValue({ data: CHECKIN.exemple })
    monter('/quai/checkin')
    fireEvent.change(screen.getByLabelText('Société'), { target: { value: 'taqinor' } })
    saisir('K7M2PQ9X')
    await waitFor(() => expect(client.post).toHaveBeenCalledWith(
      '/api/django/public/stock/quai-checkin/', { societe: 'taqinor', code: 'K7M2PQ9X' }))
  })
})
