import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR148 — Écran de gestion des Baux : signature/révision/dépôt/échéancier/
   quittancement/impayés, tout entier consommé depuis immobilierApi (déjà
   backend-only et testé). */

vi.mock('../../api/immobilierApi', () => ({
  default: {
    locaux: { list: vi.fn() },
    locataires: { list: vi.fn() },
    baux: {
      list: vi.fn(), get: vi.fn(), create: vi.fn(),
      reviser: vi.fn(), encaisserDepot: vi.fn(), restituerDepot: vi.fn(),
      genererEcheancier: vi.fn(),
    },
    echeancesLoyer: {
      list: vi.fn(), impayees: vi.fn(), emettreQuittance: vi.fn(),
      relancer: vi.fn(), quittancePdfUrl: vi.fn((id) => `/api/django/immobilier/echeances-loyer/${id}/quittance-pdf/`),
    },
    // WIR263 — historique des relances (escalade 1 → 3, portée juridique).
    relancesLoyer: { list: vi.fn(), parEcheance: vi.fn() },
  },
}))

import immobilierApi from '../../api/immobilierApi'
// PACT10/PACT13 — la charge utile vient de l'exemple COMMITTÉ, jamais d'un
// mock écrit à la main (deuxième source de vérité = la cause racine du
// plantage du 03/08/2026).
import { exempleContrat } from '../../test/fixtures/contractSamples'
import BauxPage from './BauxPage'

const LOCAUX = [{ id: 1, reference: 'RDC-01' }]
const LOCATAIRES = [{ id: 5, nom: 'Bennani' }]
const BAUX = [
  {
    id: 10, local_reference: 'RDC-01', locataire_nom: 'Bennani',
    type_bail_display: 'Habitation (loi 67-12)', loyer_mensuel_ht: '3000.00',
    statut_display: 'Actif', statut: 'actif',
    depot_garantie_recu: false, depot_garantie_restitue: false,
    revisions: [],
  },
]

function mockDefaults() {
  immobilierApi.locaux.list.mockResolvedValue({ data: LOCAUX })
  immobilierApi.locataires.list.mockResolvedValue({ data: LOCATAIRES })
  immobilierApi.baux.list.mockResolvedValue({ data: BAUX })
  immobilierApi.echeancesLoyer.impayees.mockResolvedValue({ data: [] })
  immobilierApi.echeancesLoyer.list.mockResolvedValue({ data: [] })
  immobilierApi.relancesLoyer.parEcheance.mockResolvedValue({ data: [] })
}

describe('BauxPage (WIR148)', () => {
  beforeEach(() => { vi.clearAllMocks(); mockDefaults() })

  it('affiche la liste des baux', async () => {
    render(<BauxPage />)
    const row = await screen.findByTestId('ligne-bail-10')
    expect(within(row).getByText('RDC-01')).toBeInTheDocument()
    expect(within(row).getByText('Bennani')).toBeInTheDocument()
    expect(within(row).getByText('Actif')).toBeInTheDocument()
  })

  it('signe un nouveau bail', async () => {
    immobilierApi.baux.create.mockResolvedValue({ data: { id: 11 } })
    render(<BauxPage />)
    await screen.findByTestId('ligne-bail-10')

    await userEvent.selectOptions(screen.getByLabelText('Local'), '1')
    await userEvent.selectOptions(screen.getByLabelText('Locataire'), '5')
    // input[type=date] : fireEvent.change (userEvent.type est peu fiable sur
    // les champs date segmentés, même patron que Composer.test.jsx WIR155).
    fireEvent.change(screen.getByLabelText('Date de début'), { target: { value: '2026-08-01' } })
    await userEvent.type(screen.getByLabelText('Loyer mensuel HT'), '3500')

    await userEvent.click(screen.getByRole('button', { name: 'Signer le bail' }))
    await waitFor(() => expect(immobilierApi.baux.create).toHaveBeenCalledWith(
      expect.objectContaining({ local: '1', locataire: '5', loyer_mensuel_ht: '3500' })))
  })

  it('ouvre le détail d’un bail et révise le loyer', async () => {
    immobilierApi.baux.reviser.mockResolvedValue({ data: {} })
    immobilierApi.baux.get.mockResolvedValue({
      data: { ...BAUX[0], loyer_mensuel_ht: '3200.00' },
    })
    render(<BauxPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Détails' }))
    await screen.findByTestId('detail-bail')

    await userEvent.type(screen.getByLabelText('Nouveau loyer'), '3200')
    fireEvent.change(screen.getByLabelText("Date d'effet de la révision"), { target: { value: '2026-09-01' } })
    await userEvent.click(screen.getByRole('button', { name: 'Réviser' }))

    await waitFor(() => expect(immobilierApi.baux.reviser).toHaveBeenCalledWith(
      10, expect.objectContaining({ nouveau_loyer: '3200', date_effet: '2026-09-01' })))
  })

  it('encaisse le dépôt de garantie', async () => {
    immobilierApi.baux.encaisserDepot.mockResolvedValue({ data: {} })
    immobilierApi.baux.get.mockResolvedValue({
      data: { ...BAUX[0], depot_garantie_recu: true, date_reception_depot: '2026-08-01' },
    })
    render(<BauxPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Détails' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Encaisser le dépôt' }))
    await waitFor(() => expect(immobilierApi.baux.encaisserDepot).toHaveBeenCalledWith(10, {}))
  })

  it('génère l’échéancier puis émet une quittance', async () => {
    immobilierApi.baux.genererEcheancier.mockResolvedValue({ data: [] })
    immobilierApi.echeancesLoyer.list.mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({
        data: [{ id: 20, periode_debut: '2026-08-01', montant_total: '3200.00', statut: 'a_emettre', statut_display: 'À émettre' }],
      })
    immobilierApi.echeancesLoyer.emettreQuittance.mockResolvedValue({ data: {} })
    render(<BauxPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Détails' }))
    await userEvent.click(await screen.findByRole('button', { name: "Générer l'échéancier" }))
    expect(await screen.findByText('À émettre')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Émettre quittance' }))
    await waitFor(() => expect(immobilierApi.echeancesLoyer.emettreQuittance).toHaveBeenCalledWith(20))
  })

  it('liste les impayés et relance', async () => {
    immobilierApi.echeancesLoyer.impayees.mockResolvedValue({
      data: [{ echeance_id: 30, local: 'RDC-01', locataire: 'Bennani', montant_total: '3200.00', jours_retard: 15 }],
    })
    immobilierApi.echeancesLoyer.relancer.mockResolvedValue({ data: {} })
    render(<BauxPage />)
    const row = await screen.findByText('15')
    expect(row).toBeInTheDocument()
    const impayeesTable = screen.getByTestId('table-impayees')
    await userEvent.click(within(impayeesTable).getByRole('button', { name: 'Relancer' }))
    await waitFor(() => expect(immobilierApi.echeancesLoyer.relancer).toHaveBeenCalledWith(30, {}))
  })
})

/* ── WIR263 / NTPRO8 — escalade des relances de loyer (portée juridique) ────
   Le payload N'EST PAS écrit à la main : il vient de l'exemple COMMITTÉ
   `apps/immobilier/contract_samples/relance_loyer.json`, le même fichier que
   le test backend affirme (PACT10/PACT13). Si le serveur change de forme,
   l'exemple change et ce test casse tout seul. */
describe('BauxPage — historique des relances de loyer (WIR263)', () => {
  beforeEach(() => { vi.clearAllMocks(); mockDefaults() })

  const ECHEANCE = {
    id: 12, periode_debut: '2026-07-01', montant_total: '3200.00',
    statut: 'relancee', statut_display: 'Relancée',
  }

  function armerEcheanceAvecRelances(relances) {
    immobilierApi.echeancesLoyer.list.mockResolvedValue({ data: [ECHEANCE] })
    immobilierApi.relancesLoyer.parEcheance.mockResolvedValue({ data: relances })
  }

  it('2 relances → 2 lignes + mention « niveau 2/3 »', async () => {
    const niveau1 = exempleContrat('immobilier', 'relance_loyer', 'exemple_niveau_1')
    const niveau2 = exempleContrat('immobilier', 'relance_loyer')
    armerEcheanceAvecRelances([niveau2, niveau1])

    render(<BauxPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Détails' }))

    await waitFor(() => expect(immobilierApi.relancesLoyer.parEcheance)
      .toHaveBeenCalledWith(12))
    const cellule = await screen.findByTestId('relances-12')
    expect(within(cellule).getAllByRole('listitem')).toHaveLength(2)
    expect(within(cellule).getByText('Niveau 2/3')).toBeInTheDocument()
    // Le niveau maximal n'est PAS atteint : aucun avertissement.
    expect(within(cellule).queryByRole('status')).toBeNull()
  })

  it('signale le niveau maximal atteint avant tout nouveau clic', async () => {
    const niveau3 = {
      ...exempleContrat('immobilier', 'relance_loyer'), id: 32, niveau: 3,
    }
    armerEcheanceAvecRelances([niveau3])

    render(<BauxPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Détails' }))

    const cellule = await screen.findByTestId('relances-12')
    expect(within(cellule).getByText('Niveau 3/3')).toBeInTheDocument()
    expect(within(cellule).getByRole('status')).toBeInTheDocument()
  })

  it('sans relance, la cellule le dit au lieu de rester vide', async () => {
    armerEcheanceAvecRelances([])
    render(<BauxPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Détails' }))
    const cellule = await screen.findByTestId('relances-12')
    expect(within(cellule).getByText('Aucune relance')).toBeInTheDocument()
  })
})
