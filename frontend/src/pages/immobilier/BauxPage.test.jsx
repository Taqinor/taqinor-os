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
    // WIR263 — historique d'escalade des relances de loyer.
    relancesLoyer: { list: vi.fn() },
  },
}))

import immobilierApi from '../../api/immobilierApi'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import BauxPage from './BauxPage'

/* WIR263 — la charge utile des relances n'est PAS tapée à la main : elle vient
   de l'exemple COMMITTÉ `apps/immobilier/contract_samples/
   relances_loyer_par_echeance.json`, le même fichier que le test backend
   `apps/immobilier/tests/test_wir263_historique_relances.py` compare à la
   réponse RÉELLE du serveur (PACT10/PACT13). */
const PAGE_RELANCES = exempleContrat(
  'immobilier', 'relances_loyer_par_echeance', 'exemple_page')
const RELANCE_N1 = exempleContrat(
  'immobilier', 'relances_loyer_par_echeance', 'exemple_niveau_1')

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
  immobilierApi.relancesLoyer.list.mockResolvedValue(
    { data: { count: 0, next: null, previous: null, results: [] } })
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

/* ==========================================================================
   WIR263 — L'escalade 1 -> 2 -> 3 (le 3 a une portée juridique) devient
   visible : historique par échéance + niveau atteint signalé AVANT tout
   nouveau clic. Aucune charge utile n'est tapée à la main (contrat committé).
   ========================================================================== */
describe('BauxPage — WIR263 historique des relances de loyer', () => {
  beforeEach(() => { vi.clearAllMocks(); mockDefaults() })

  // L'échéance de l'exemple committé (id 30), déjà relancée.
  const ECHEANCE_RELANCEE = {
    id: PAGE_RELANCES.results[0].echeance_loyer,
    periode_debut: '2026-08-01', montant_total: '3200.00',
    statut: 'relancee', statut_display: 'Relancée',
  }

  it('2 relances → 2 lignes (niveau/date/canal) et la mention « Niveau 2/3 »', async () => {
    immobilierApi.echeancesLoyer.list.mockResolvedValue({ data: [ECHEANCE_RELANCEE] })
    immobilierApi.relancesLoyer.list.mockResolvedValue({ data: PAGE_RELANCES })
    render(<BauxPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Détails' }))

    // Le filtre serveur par échéance est bien utilisé.
    await waitFor(() => expect(immobilierApi.relancesLoyer.list)
      .toHaveBeenCalledWith({ echeance_loyer: ECHEANCE_RELANCEE.id }))

    const historique = await screen.findByTestId(
      `historique-relances-${ECHEANCE_RELANCEE.id}`)
    const lignes = within(historique).getAllByTestId('ligne-relance')
    expect(lignes).toHaveLength(2)
    // Niveau, date et canal de CHAQUE relance, dans l'ordre du serveur.
    expect(lignes[0]).toHaveTextContent(`Niveau ${PAGE_RELANCES.results[0].niveau}`)
    expect(lignes[0]).toHaveTextContent(PAGE_RELANCES.results[0].date_envoi)
    expect(lignes[0]).toHaveTextContent(PAGE_RELANCES.results[0].canal_display)
    expect(lignes[1]).toHaveTextContent(`Niveau ${RELANCE_N1.niveau}`)
    expect(lignes[1]).toHaveTextContent(RELANCE_N1.canal_display)
    // Le niveau ATTEINT est signalé (avant tout nouveau clic sur « Relancer »).
    expect(screen.getByTestId(`niveau-relance-${ECHEANCE_RELANCEE.id}`))
      .toHaveTextContent('Niveau 2/3')
    // Pas encore le dernier niveau : aucune mention de portée juridique.
    expect(screen.queryByTestId(`niveau-max-relance-${ECHEANCE_RELANCEE.id}`)).toBeNull()
  })

  it('niveau 3 atteint : la portée juridique est signalée', async () => {
    immobilierApi.echeancesLoyer.list.mockResolvedValue({ data: [ECHEANCE_RELANCEE] })
    immobilierApi.relancesLoyer.list.mockResolvedValue({ data: {
      ...PAGE_RELANCES,
      count: 3,
      results: [
        { ...PAGE_RELANCES.results[0], id: 403, niveau: 3 },
        ...PAGE_RELANCES.results,
      ],
    } })
    render(<BauxPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Détails' }))
    expect(await screen.findByTestId(`niveau-relance-${ECHEANCE_RELANCEE.id}`))
      .toHaveTextContent('Niveau 3/3')
    expect(screen.getByTestId(`niveau-max-relance-${ECHEANCE_RELANCEE.id}`))
      .toHaveTextContent('portée juridique')
  })

  it('relancer relit l\'historique aussitôt (le niveau se voit avant un nouveau clic)', async () => {
    immobilierApi.echeancesLoyer.list.mockResolvedValue({ data: [
      { ...ECHEANCE_RELANCEE, statut: 'emise', statut_display: 'Émise' },
    ] })
    immobilierApi.echeancesLoyer.relancer.mockResolvedValue({ data: RELANCE_N1 })
    immobilierApi.relancesLoyer.list.mockResolvedValue({ data: {
      count: 1, next: null, previous: null, results: [RELANCE_N1],
    } })
    render(<BauxPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Détails' }))
    // Échéance seulement « émise » : aucun historique n'est chargé au départ.
    expect(immobilierApi.relancesLoyer.list).not.toHaveBeenCalled()

    const table = screen.getByTestId('table-echeances')
    await userEvent.click(within(table).getByRole('button', { name: 'Relancer' }))
    await waitFor(() => expect(immobilierApi.relancesLoyer.list)
      .toHaveBeenCalledWith({ echeance_loyer: ECHEANCE_RELANCEE.id }))
    expect(await screen.findByTestId(`niveau-relance-${ECHEANCE_RELANCEE.id}`))
      .toHaveTextContent('Niveau 1/3')
  })

  it('échéance jamais relancée : rien n\'est affirmé tant qu\'on n\'a pas lu', async () => {
    immobilierApi.echeancesLoyer.list.mockResolvedValue({ data: [
      { ...ECHEANCE_RELANCEE, statut: 'emise', statut_display: 'Émise' },
    ] })
    render(<BauxPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Détails' }))
    const bouton = await screen.findByTestId(`voir-relances-${ECHEANCE_RELANCEE.id}`)
    expect(immobilierApi.relancesLoyer.list).not.toHaveBeenCalled()
    await userEvent.click(bouton)
    await waitFor(() => expect(immobilierApi.relancesLoyer.list)
      .toHaveBeenCalledWith({ echeance_loyer: ECHEANCE_RELANCEE.id }))
    expect(await screen.findByTestId(`aucune-relance-${ECHEANCE_RELANCEE.id}`))
      .toBeInTheDocument()
  })
})
