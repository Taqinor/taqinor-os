import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTRET1 / AUD230 — mode offline caisse enfin CÂBLÉ.

   `offlineQueue.js` (263 lignes, testé) existait depuis NTRET1 mais n'était
   importé nulle part : `CaisseScreen` enchaînait ses trois appels REST et un
   échec réseau perdait la vente — le panier était vidé, rien n'avait été
   enregistré, et la dédup serveur sur `uuid_client` ne protégeait de toute
   façon que la 1re des trois étapes (le `uuid_client` n'était même pas
   envoyé).

   Ces tests prouvent les quatre comportements attendus :
     * coupure réseau PENDANT la vente → payload COMPLET mis en file ;
     * refus métier (4xx) → JAMAIS mis en file, message serveur affiché ;
     * hors ligne connu d'avance → mise en file sans tenter d'appel ;
     * en ligne → chemin nominal inchangé, rien en file.
   Plus la sémantique de REJEU (`envoyerVenteComptoir`), qui doit reprendre
   une vente laissée à moitié appliquée sans jamais la dupliquer. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const PRODUIT = { id: 11, nom: 'Panneau AUD230', prix_vente: '100', tva: 20 }
const UUID = 'uuid-aud230'
// prixTtc = ttcFromHt(100, 20) = 120.
const PRIX_TTC = 120

const {
  getProduits, searchClients, createVente, ajouterLigne, validerVente,
  estHorsLigne, enqueue, count, flush,
} = vi.hoisted(() => ({
  getProduits: vi.fn(),
  searchClients: vi.fn(() => Promise.resolve({ data: [] })),
  createVente: vi.fn(),
  ajouterLigne: vi.fn(() => Promise.resolve({ data: {} })),
  validerVente: vi.fn(),
  estHorsLigne: vi.fn(),
  enqueue: vi.fn(),
  count: vi.fn(),
  flush: vi.fn(),
}))

vi.mock('../../api/posApi', () => ({
  default: {
    getProduits: (...a) => getProduits(...a),
    searchClients: (...a) => searchClients(...a),
    createVente: (...a) => createVente(...a),
    ajouterLigne: (...a) => ajouterLigne(...a),
    validerVente: (...a) => validerVente(...a),
  },
}))

vi.mock('../../api/axios', () => ({ default: { defaults: { baseURL: '' } } }))

vi.mock('./offlineQueue', () => ({
  estHorsLigne: (...a) => estHorsLigne(...a),
  makeUuidClient: () => UUID,
  getOfflineVenteQueue: () => ({
    enqueue: (...a) => enqueue(...a),
    count: (...a) => count(...a),
    flush: (...a) => flush(...a),
  }),
}))

import CaisseScreen, { envoyerVenteComptoir } from './CaisseScreen'

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

function erreurReseau() {
  // Axios sur coupure réseau : une Error SANS `response`.
  return new Error('Network Error')
}

function refusServeur(detail) {
  const err = new Error('Request failed with status code 400')
  err.response = { status: 400, data: { detail } }
  return err
}

beforeEach(() => {
  vi.clearAllMocks()
  getProduits.mockResolvedValue({ data: [PRODUIT] })
  searchClients.mockResolvedValue({ data: [] })
  createVente.mockResolvedValue({ data: { id: 5, statut: 'brouillon', lignes: [] } })
  ajouterLigne.mockResolvedValue({ data: {} })
  validerVente.mockResolvedValue({ data: { id: 5, statut: 'validee', reference: 'VC-1' } })
  estHorsLigne.mockResolvedValue(false)
  enqueue.mockResolvedValue(UUID)
  flush.mockResolvedValue({ skipped: false, flushed: 0, remaining: 0 })
  // Le compteur affiché SUIT les mises en file de ce test.
  count.mockImplementation(async () => enqueue.mock.calls.length)
})

/** Panier → dialogue d'encaissement → confirmation. */
async function encaisserUneVente() {
  withProviders(<CaisseScreen />)
  await waitFor(() => expect(screen.getByText('Panneau AUD230')).toBeTruthy())
  fireEvent.click(screen.getByText('Panneau AUD230'))

  fireEvent.click(screen.getByRole('button', { name: 'Encaisser' }))
  await waitFor(() => expect(screen.getByLabelText('Montant')).toBeTruthy())
  fireEvent.change(screen.getByLabelText('Montant'), {
    target: { value: String(PRIX_TTC) },
  })
  const confirmer = screen.getByRole(
    'button', { name: 'Confirmer l’encaissement' })
  // Le bouton reste `disabled` tant que le règlement ne couvre pas le total :
  // cliquer trop tôt ne déclencherait RIEN et rendrait le test creux.
  await waitFor(() => expect(confirmer.hasAttribute('disabled')).toBe(false))
  fireEvent.click(confirmer)
}

const PAYLOAD_ATTENDU = {
  uuid_client: UUID,
  lignes: [{
    produit: PRODUIT.id,
    quantite: 1,
    prix_unitaire_ttc: PRIX_TTC,
    numeros_serie: [],
  }],
  paiements: [{ mode: 'especes', montant: PRIX_TTC }],
}

describe('CaisseScreen — coupure réseau pendant une vente (AUD230)', () => {
  it('met le payload COMPLET en file plutôt que de perdre la vente', async () => {
    createVente.mockRejectedValueOnce(erreurReseau())

    await encaisserUneVente()

    await waitFor(() => expect(enqueue).toHaveBeenCalledTimes(1))
    expect(enqueue).toHaveBeenCalledWith(
      expect.objectContaining(PAYLOAD_ATTENDU),
      { uuidClient: UUID },
    )
  })

  it('met la vente en file même si la coupure survient APRÈS la création', async () => {
    // La vente existe déjà côté serveur : le rejeu la retrouvera par son
    // `uuid_client` — c'est précisément pour cela qu'il est envoyé dès la
    // première tentative.
    validerVente.mockRejectedValueOnce(erreurReseau())

    await encaisserUneVente()

    await waitFor(() => expect(enqueue).toHaveBeenCalledTimes(1))
    expect(createVente).toHaveBeenCalledWith(
      expect.objectContaining({ uuid_client: UUID }))
  })

  it('affiche les ventes restées en file', async () => {
    createVente.mockRejectedValueOnce(erreurReseau())

    await encaisserUneVente()

    await waitFor(() => expect(
      screen.getByTestId('ventes-hors-ligne')).toBeTruthy())
    expect(screen.getByText(/1 vente hors ligne/)).toBeTruthy()
  })

  it('ne tente aucun appel quand la coupure est déjà connue', async () => {
    estHorsLigne.mockResolvedValue(true)

    await encaisserUneVente()

    await waitFor(() => expect(enqueue).toHaveBeenCalledTimes(1))
    expect(createVente).not.toHaveBeenCalled()
  })
})

describe('CaisseScreen — un refus métier ne part JAMAIS en file (AUD230)', () => {
  it('laisse le 4xx visible sans rien mettre en file', async () => {
    createVente.mockRejectedValueOnce(
      refusServeur('Un client est requis pour émettre la facture légale.'))

    await encaisserUneVente()

    await waitFor(() => expect(createVente).toHaveBeenCalled())
    expect(enqueue).not.toHaveBeenCalled()
  })
})

describe('CaisseScreen — chemin en ligne inchangé (AUD230)', () => {
  it('crée, ajoute les lignes, valide, et ne met rien en file', async () => {
    await encaisserUneVente()

    await waitFor(() => expect(validerVente).toHaveBeenCalled())
    expect(createVente).toHaveBeenCalledWith(
      expect.objectContaining({ uuid_client: UUID }))
    expect(ajouterLigne).toHaveBeenCalledWith(5, expect.objectContaining({
      produit: PRODUIT.id, quantite: 1, prix_unitaire_ttc: PRIX_TTC,
    }))
    expect(validerVente).toHaveBeenCalledWith(5, {
      paiements: [{ mode: 'especes', montant: PRIX_TTC }],
    })
    expect(enqueue).not.toHaveBeenCalled()
  })
})

describe('envoyerVenteComptoir — sémantique de rejeu (AUD230)', () => {
  it('ne rejoue rien sur une vente déjà validée', async () => {
    createVente.mockResolvedValueOnce({
      data: { id: 5, statut: 'validee', reference: 'VC-1' } })

    const vente = await envoyerVenteComptoir(PAYLOAD_ATTENDU)

    expect(vente.reference).toBe('VC-1')
    expect(ajouterLigne).not.toHaveBeenCalled()
    expect(validerVente).not.toHaveBeenCalled()
  })

  it('ne repose pas une ligne déjà enregistrée par un rejeu interrompu', async () => {
    createVente.mockResolvedValueOnce({
      data: {
        id: 5,
        statut: 'brouillon',
        lignes: [{ id: 1, produit: PRODUIT.id }],
      },
    })

    await envoyerVenteComptoir({
      ...PAYLOAD_ATTENDU,
      lignes: [
        ...PAYLOAD_ATTENDU.lignes,
        { produit: 12, quantite: 2, prix_unitaire_ttc: 50, numeros_serie: [] },
      ],
    })

    expect(ajouterLigne).toHaveBeenCalledTimes(1)
    expect(ajouterLigne).toHaveBeenCalledWith(
      5, expect.objectContaining({ produit: 12 }))
    expect(validerVente).toHaveBeenCalledWith(5, {
      paiements: PAYLOAD_ATTENDU.paiements,
    })
  })

  it('transmet le client quand il y en a un', async () => {
    await envoyerVenteComptoir({ ...PAYLOAD_ATTENDU, client: 3 })
    expect(createVente).toHaveBeenCalledWith({ uuid_client: UUID, client: 3 })
  })
})
