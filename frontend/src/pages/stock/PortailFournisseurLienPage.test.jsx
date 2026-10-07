import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK228 — portail fournisseur PAR LIEN (/fournisseur/lien/:token).
   Réponses = contrats committés `fournisseur_portail_jetons.json` (ASTK167)
   et `wms_quais.json` (ASTK162) ; seul axios est mocké (client public).
   ========================================================================== */

const client = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({ default: { create: vi.fn(() => client) } }))

import PortailFournisseurLienPage from './PortailFournisseurLienPage'

const PF = documentContrat('stock', 'fournisseur_portail_jetons').routes
const Q = documentContrat('stock', 'wms_quais').routes
const PORTAIL = PF.public_portail_fournisseur.exemple
const CONFIRMER = PF.public_portail_confirmer_bcf
const CRENEAUX = Q.public_creneaux_disponibles
const RESERVER = Q.public_reserver_creneau
const URL_PORTAIL = '/api/django/public/stock/portail-fournisseur/tok123/'

function brancher(portail = PORTAIL) {
  client.get.mockImplementation((url) => {
    if (url === URL_PORTAIL) return Promise.resolve({ data: portail })
    if (url.endsWith('/creneaux-disponibles/')) return Promise.resolve({ data: CRENEAUX.exemple })
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
}

const monter = () => render(
  <MemoryRouter initialEntries={['/fournisseur/lien/tok123']}>
    <Routes><Route path="/fournisseur/lien/:token" element={<PortailFournisseurLienPage />} /></Routes>
  </MemoryRouter>)

beforeEach(() => { vi.clearAllMocks(); brancher() })
afterEach(() => { cleanup() })

describe('ASTK228 — PortailFournisseurLienPage', () => {
  it('affiche les documents du fournisseur', async () => {
    monter()
    expect(await screen.findByText('Import Solar SARL')).toBeInTheDocument()
    expect(screen.getAllByText(/BCF-2026-0047/).length).toBeGreaterThan(0)
    expect(screen.getByText(/REC-2026-0009/)).toBeInTheDocument()
    expect(screen.getByText(/FF-2026-0014/)).toBeInTheDocument()
  })

  it("confirmer affiche l'erreur de date sous le champ", async () => {
    client.post.mockRejectedValue({
      response: { status: 400, data: CONFIRMER.nouveau_astk181.exemple_date },
    })
    monter()
    fireEvent.change(await screen.findByLabelText('Date de livraison confirmée'), { target: { value: '18/10' } })
    fireEvent.click(screen.getByRole('button', { name: /Confirmer la commande/i }))
    const msg = CONFIRMER.nouveau_astk181.exemple_date.date_confirmee_fournisseur[0]
    const erreur = await screen.findByText(msg)
    expect(erreur).toBeInTheDocument()
    // « sous le champ » : le message est relié au champ par aria-describedby.
    const champ = screen.getByLabelText('Date de livraison confirmée')
    expect(champ.getAttribute('aria-describedby')).toBe(erreur.id)
    expect(client.post).toHaveBeenCalledWith(
      `${URL_PORTAIL}bcf/47/confirmer/`,
      { date_confirmee_fournisseur: '18/10', numero_confirmation_fournisseur: '' })
  })

  it('confirmer réussi relit le portail', async () => {
    client.post.mockResolvedValue({ data: CONFIRMER.exemple })
    monter()
    fireEvent.change(await screen.findByLabelText('Date de livraison confirmée'),
      { target: { value: CONFIRMER.exemple_corps.date_confirmee_fournisseur } })
    fireEvent.change(screen.getByLabelText('N° de confirmation'),
      { target: { value: CONFIRMER.exemple_corps.numero_confirmation_fournisseur } })
    const lecturesAvant = client.get.mock.calls.filter(([u]) => u === URL_PORTAIL).length
    fireEvent.click(screen.getByRole('button', { name: /Confirmer la commande/i }))
    await waitFor(() => expect(client.post).toHaveBeenCalledWith(
      `${URL_PORTAIL}bcf/47/confirmer/`, CONFIRMER.exemple_corps))
    await waitFor(() => expect(
      client.get.mock.calls.filter(([u]) => u === URL_PORTAIL).length).toBeGreaterThan(lecturesAvant))
  })

  it("un 409 (déjà reçu) est affiché tel quel", async () => {
    client.post.mockRejectedValue({ response: { status: 409, data: CONFIRMER.nouveau_astk180.exemple } })
    monter()
    fireEvent.change(await screen.findByLabelText('Date de livraison confirmée'), { target: { value: '2026-10-18' } })
    fireEvent.click(screen.getByRole('button', { name: /Confirmer la commande/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(CONFIRMER.nouveau_astk180.exemple.detail)
  })

  it("un BCF reçu n'offre pas de confirmation", async () => {
    const recu = {
      ...PORTAIL,
      bons_commande: [{ ...PORTAIL.bons_commande[0], statut: 'recu', statut_display: 'Reçu' }],
    }
    brancher(recu)
    monter()
    expect(await screen.findByText('Reçu')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Confirmer la commande/i })).toBeNull()
    expect(screen.queryByLabelText('Date de livraison confirmée')).toBeNull()
  })

  it('seuls les créneaux proposés sont sélectionnables', async () => {
    monter()
    await screen.findByText('Import Solar SARL')
    const choix = await screen.findAllByRole('radio')
    expect(choix).toHaveLength(CRENEAUX.exemple.creneaux.length)
    // jamais de champ heure libre
    expect(document.querySelector('input[type="datetime-local"], input[type="time"]')).toBeNull()
  })

  it('réserve le créneau choisi et montre le code du chauffeur', async () => {
    client.post.mockResolvedValue({ data: RESERVER.exemple })
    monter()
    fireEvent.click((await screen.findAllByRole('radio'))[0])
    fireEvent.change(screen.getByLabelText('Chauffeur'), { target: { value: 'M. Alami' } })
    fireEvent.click(screen.getByRole('button', { name: /Réserver ce créneau/i }))
    const creneau = CRENEAUX.exemple.creneaux[0]
    await waitFor(() => expect(client.post).toHaveBeenCalledWith(
      `${URL_PORTAIL}reserver-creneau/`,
      { quai: creneau.quai, debut: creneau.debut, bon_commande: 47, chauffeur_nom: 'M. Alami', immatriculation: '' }))
    expect(await screen.findByText(RESERVER.exemple.code_checkin)).toBeInTheDocument()
  })

  it('jeton révoqué : message serveur', async () => {
    client.get.mockRejectedValue({ response: { status: 404, data: PF.public_portail_fournisseur.exemple_erreur_404 } })
    monter()
    expect(await screen.findByRole('alert')).toHaveTextContent(PF.public_portail_fournisseur.exemple_erreur_404.detail)
  })

  it('une réservation refusée (créneau pris) affiche le 400 serveur', async () => {
    client.post.mockRejectedValue({ response: { status: 400, data: RESERVER.exemple_erreur_400 } })
    monter()
    fireEvent.click((await screen.findAllByRole('radio'))[0])
    fireEvent.click(screen.getByRole('button', { name: /Réserver ce créneau/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(RESERVER.exemple_erreur_400.detail)
  })
})
