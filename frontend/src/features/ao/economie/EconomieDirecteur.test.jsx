import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { formatMAD } from '../../../lib/format'

/* PACT75 — Économie DIRECTEUR de l'AO : coût de revient et cibles de marge.
   Preuves : (1) `aoRentabiliteApi` (export SÉPARÉ) est le SEUL client
   importé — jamais `aoApi` pour une donnée de marge ; (2) aucun agrégat n'est
   recalculé, tout vient du serializer ; (3) le verrou désactive les
   écritures ; (4) une cible exige un motif (versionnée, auteur tracé côté
   serveur). */

const mocks = vi.hoisted(() => ({
  parAffaire: vi.fn(),
  creer: vi.fn(),
  verrouiller: vi.fn(),
  deverrouiller: vi.fn(),
  lignesList: vi.fn(),
  lignesCreate: vi.fn(),
  lignesRemove: vi.fn(),
  ciblesList: vi.fn(),
  ciblesCreate: vi.fn(),
  affairesList: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '42' }) }
})

vi.mock('../../../api/aoApi', () => ({
  default: { affaires: { list: mocks.affairesList } },
  aoRentabiliteApi: {
    parAffaire: mocks.parAffaire,
    creer: mocks.creer,
    verrouiller: mocks.verrouiller,
    deverrouiller: mocks.deverrouiller,
    lignesCoutRevient: { list: mocks.lignesList, create: mocks.lignesCreate, remove: mocks.lignesRemove },
    ciblesFinancieres: { list: mocks.ciblesList, create: mocks.ciblesCreate },
    produireClasseur: vi.fn(),
    statutClasseur: vi.fn(),
    download: vi.fn(),
  },
}))

import EconomieDirecteur from './EconomieDirecteur'

const ECONOMIE = {
  id: 5, appel_offre: 42, appel_offre_reference: 'AO-2026-005', verrouillee: false,
  taux_tva_vente: '20.00', cout_revient_ht: '3200000.00', cout_regime_reduit_ht: '2100000.00',
  cout_regime_standard_ht: '1100000.00', tva_deductible: '320000.00', benefice_net_cible_ht: '400000.00',
  total_ht: '3600000.00', tva_collectee: '720000.00', total_ttc: '4320000.00',
  tva_nette_a_reverser: '400000.00', marge_pct: '11.11', controle_tresorerie: '0.00',
  ecart_tresorerie: '0.00', sous_seuil_psychologique: true,
}

const renderEcran = () => render(<MemoryRouter><EconomieDirecteur /></MemoryRouter>)

// `formatMAD` sépare les milliers par une ESPACE FINE INSÉCABLE (U+202F) —
// Testing Library normalise les espaces du DOM mais pas la chaîne de requête
// littérale : on neutralise la classe d'espace des deux côtés (même patron
// que `bordereau/BordereauPage.test.jsx`).
const mad = (valeur) => formatMAD(valeur).replace(/\s+/g, ' ')

beforeEach(() => {
  vi.clearAllMocks()
  mocks.parAffaire.mockResolvedValue({ data: [ECONOMIE] })
  mocks.lignesList.mockResolvedValue({ data: [] })
  mocks.ciblesList.mockResolvedValue({ data: [] })
  mocks.affairesList.mockResolvedValue({ data: [] })
  mocks.lignesCreate.mockResolvedValue({ data: {} })
  mocks.ciblesCreate.mockResolvedValue({ data: {} })
  mocks.verrouiller.mockResolvedValue({ data: { verrouillee: true } })
  mocks.deverrouiller.mockResolvedValue({ data: { verrouillee: false } })
})

describe('EconomieDirecteur (PACT75)', () => {
  it('résout l’économie via aoRentabiliteApi.parAffaire(id) — l’id de la route EST celui de l’affaire', async () => {
    renderEcran()
    await waitFor(() => expect(mocks.parAffaire).toHaveBeenCalledWith('42'))
    expect((await screen.findAllByText(mad(4320000))).length).toBeGreaterThan(0)
  })

  it('AUCUN agrégat n’est recalculé : le total HT/TTC/marge vient TEL QUEL du serializer', async () => {
    renderEcran()
    expect((await screen.findAllByText(mad(3600000))).length).toBeGreaterThan(0)
    expect(screen.getAllByText('11.11 %').length).toBeGreaterThan(0)
  })

  it('aucune économie pour cette affaire : propose de la créer, jamais une donnée inventée', async () => {
    mocks.parAffaire.mockResolvedValue({ data: [] })
    renderEcran()
    const bouton = (await screen.findAllByRole('button', { name: 'Créer l’économie' }))[0]
    await userEvent.click(bouton)
    await waitFor(() => expect(mocks.creer).toHaveBeenCalledWith('42'))
  })

  it('ajouter un poste de coût appelle un POST réel sur lignes-cout-revient, scopé à l’économie', async () => {
    renderEcran()
    await screen.findByRole('heading', { name: 'Coût de revient — postes' })
    await userEvent.type(screen.getByLabelText('Désignation'), 'Modules 625 Wc')
    await userEvent.type(screen.getByLabelText('Coût unitaire HT (MAD)'), '950')
    await userEvent.click(screen.getAllByRole('button', { name: 'Ajouter le poste' })[0])
    await waitFor(() => expect(mocks.lignesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ economie: 5, designation: 'Modules 625 Wc', prix_unitaire_ht: '950' }),
    ))
  })

  it('une cible exige un motif — la version est TRACÉE côté serveur (auteur, jamais saisi ici)', async () => {
    renderEcran()
    await screen.findByRole('heading', { name: 'Cibles financières — historique versionné' })
    const bouton = screen.getAllByRole('button', { name: 'Verser une nouvelle version' })[0]
    expect(bouton).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Bénéfice net visé HT (MAD)'), '450000')
    await userEvent.type(screen.getByLabelText('Motif de la version (obligatoire)'), 'Ajustement après relecture du CPS')
    await userEvent.click(bouton)
    await waitFor(() => expect(mocks.ciblesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ economie: 5, benefice_net_cible_ht: '450000', motif: 'Ajustement après relecture du CPS' }),
    ))
    expect(mocks.ciblesCreate.mock.calls[0][0]).not.toHaveProperty('auteur')
  })

  it('une économie verrouillée désactive l’ajout de poste ET de cible (refusé de toute façon côté serveur)', async () => {
    mocks.parAffaire.mockResolvedValue({ data: [{ ...ECONOMIE, verrouillee: true }] })
    renderEcran()
    await screen.findAllByText('Verrouillée')
    expect(screen.getAllByRole('button', { name: 'Ajouter le poste' })[0]).toBeDisabled()
    expect(screen.getAllByRole('button', { name: 'Verser une nouvelle version' })[0]).toBeDisabled()
  })

  it('bascule le verrou via les actions serveur dédiées (jamais un PATCH nu sur verrouillee)', async () => {
    renderEcran()
    const bouton = (await screen.findAllByRole('button', { name: 'Verrouiller' }))[0]
    await userEvent.click(bouton)
    await waitFor(() => expect(mocks.verrouiller).toHaveBeenCalledWith(5))
  })
})
