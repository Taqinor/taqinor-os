import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { toast } from '../../../ui'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { formatMAD } from '../../../lib/format'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

/* WIR280/WIR279 (XACC14) — Emprunts & crédits-bails contractés par la
   société : le modèle, le tableau d'amortissement et le posting au grand
   livre existaient côté services/ViewSet SANS AUCUN écran.

   Les charges utiles de `generer-tableau/` et `poster/` reprennent EXACTEMENT
   les contrats committés (`apps/compta/contract_samples/
   emprunt_tableau_amortissement.json` et `echeance_emprunt_poster.json`,
   WIR279) via `exempleContrat`/`reponseContrat` (PACT10/13, patron maison) —
   JAMAIS un objet recopié à la main : si le serveur change de forme,
   l'exemple committé change et ce test casse tout seul.

   `ListShell`/`DataTable` rend DEUX fois la même ligne (repli desktop table +
   cartes mobile, toutes deux dans le DOM sous jsdom) : les requêtes sur la
   liste des emprunts sont scopées à `[data-dt-table]` (patron déjà en usage
   dans `RapprochementsComptePage.test.jsx`). Le tableau d'amortissement dans
   la boîte de dialogue passe par `ComptaTable` (primitif distinct, pas de
   double rendu) : ses requêtes restent globales. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  empruntsList: vi.fn(),
  empruntsCreate: vi.fn(),
  genererTableau: vi.fn(),
  echeancesList: vi.fn(),
  poster: vi.fn(),
  comptes: vi.fn(),
  tresorerie: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    emprunts: { list: mocks.empruntsList, create: mocks.empruntsCreate, genererTableau: mocks.genererTableau },
    echeancesEmprunt: { list: mocks.echeancesList, poster: mocks.poster },
    comptes: { list: mocks.comptes },
    tresorerie: { list: mocks.tresorerie },
  },
}))

import EmpruntsPage from './EmpruntsPage.jsx'

// Contrats committés WIR279 — lus depuis le fichier réel, jamais recopiés.
const TABLEAU_GENERE = exempleContrat('compta', 'emprunt_tableau_amortissement')
const PREMIERE_ECHEANCE = TABLEAU_GENERE.echeances[0]

// `formatMAD` insère un espace fine insécable (Intl fr-FR) entre les groupes
// de milliers ; le normaliseur de texte par défaut de testing-library ne
// l'applique qu'au texte du DOM, pas à la chaîne de requête — comparer sans
// AUCUN espace des deux côtés rend le matcher robuste au type d'espace.
function matchMontant(valeurDecimale) {
  const cible = formatMAD(valeurDecimale).replace(/\s/g, '')
  return (contenu) => (contenu || '').replace(/\s/g, '') === cible
}

const EMPRUNT = {
  id: 12, reference: 'EMPR-2026-01', banque: 'BMCE Bank', type_financement: 'emprunt',
  type_financement_display: 'Emprunt bancaire', capital: '100000.00', taux_annuel: '4.500',
  duree_mois: 3, date_debut: '2026-02-01', compte_capital: 5, compte_interets: 8,
  compte_tresorerie: 3, encours_restant_du: '100000.00', nb_echeances: 0,
  nb_echeances_postees: 0, date_creation: '2026-01-15T09:00:00Z',
}

function mount({ permissions = [] } = {}) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><EmpruntsPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

// Le repli desktop de `ListShell`/`DataTable` (unique porteur du gestionnaire
// de clic de ligne) — jamais les cartes mobile, dupliquées dans le DOM.
async function tableDesktop(container) {
  await waitFor(() => expect(container.querySelector('[data-dt-table]')).toBeTruthy())
  return within(container.querySelector('[data-dt-table]'))
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.empruntsList.mockResolvedValue({ data: [EMPRUNT] })
  mocks.comptes.mockResolvedValue({
    data: [
      { id: 5, numero: '1481', intitule: 'Emprunts auprès des établissements de crédit' },
      { id: 8, numero: '6311', intitule: 'Intérêts des emprunts et dettes' },
    ],
  })
  mocks.tresorerie.mockResolvedValue({ data: [{ id: 3, libelle: 'BMCE compte courant' }] })
  mocks.empruntsCreate.mockResolvedValue({ data: { id: 13 } })
  mocks.echeancesList.mockResolvedValue({ data: [] })
  mocks.genererTableau.mockResolvedValue({ data: TABLEAU_GENERE })
  mocks.poster.mockResolvedValue(reponseContrat('compta', 'echeance_emprunt_poster'))
})

describe('EmpruntsPage — liste et création (WIR280)', () => {
  it('affiche la liste des emprunts', async () => {
    const { container } = mount()
    const table = await tableDesktop(container)
    expect(await table.findByText('EMPR-2026-01')).toBeInTheDocument()
    expect(table.getByText('Emprunt bancaire')).toBeInTheDocument()
  })

  it('crée un emprunt depuis le formulaire', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    const table = await tableDesktop(container)
    await table.findByText('EMPR-2026-01')

    await user.click(screen.getByRole('button', { name: /Nouvel emprunt/ }))
    await user.type(await screen.findByLabelText('Banque / bailleur'), 'Attijariwafa')
    // Champs `required` (Label pose un « * » aria-hidden dans le textContent
    // du <label> — getByLabelText matche le textContent brut, pas le nom
    // accessible) : requête en préfixe plutôt qu'une égalité exacte.
    await user.type(screen.getByLabelText(/^Capital emprunté \(MAD\)/), '50000')
    await user.type(screen.getByLabelText(/^Durée \(mois\)/), '12')
    await user.type(screen.getByLabelText(/^Date de départ/), '2026-03-01')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(mocks.empruntsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ banque: 'Attijariwafa', capital: '50000', duree_mois: '12' }),
    ))
  })
})

describe('EmpruntsPage — tableau d\'amortissement (WIR280/WIR279)', () => {
  it('génère le tableau d\'amortissement et affiche les échéances du contrat', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    const table = await tableDesktop(container)
    await user.click(await table.findByText('EMPR-2026-01'))

    await user.click(await screen.findByRole('button', { name: /Générer le tableau/ }))

    await waitFor(() => expect(mocks.genererTableau).toHaveBeenCalledWith(TABLEAU_GENERE.emprunt))
    // Montants EXACTEMENT ceux du contrat committé (capital_restant_du de la
    // 1ère échéance, mensualité) — jamais recalculés, comparés au rendu RÉEL
    // de `formatMAD` (pas une approximation en dur).
    expect(await screen.findByText(matchMontant(PREMIERE_ECHEANCE.capital_restant_du)))
      .toBeInTheDocument()
    expect((await screen.findAllByText(matchMontant(PREMIERE_ECHEANCE.mensualite)))
      .length).toBeGreaterThan(0)
  })

  it('comptabilise une échéance avec la permission compta_saisir', async () => {
    const user = userEvent.setup()
    mocks.echeancesList.mockResolvedValue({ data: TABLEAU_GENERE.echeances })
    const { container } = mount({ permissions: ['compta_saisir'] })
    const table = await tableDesktop(container)
    await user.click(await table.findByText('EMPR-2026-01'))

    const boutons = await screen.findAllByRole('button', { name: /Comptabiliser l'échéance/ })
    await user.click(boutons[0])

    await waitFor(() => expect(mocks.poster).toHaveBeenCalledWith(PREMIERE_ECHEANCE.id))
  })

  it('masque « Comptabiliser » sans la permission compta_saisir', async () => {
    const user = userEvent.setup()
    mocks.echeancesList.mockResolvedValue({ data: TABLEAU_GENERE.echeances })
    const { container } = mount({ permissions: [] })
    const table = await tableDesktop(container)
    await user.click(await table.findByText('EMPR-2026-01'))

    // Principal de la 1ère échéance, comparé au rendu RÉEL de `formatMAD`.
    expect(await screen.findByText(matchMontant(PREMIERE_ECHEANCE.principal)))
      .toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Comptabiliser l'échéance/ })).not.toBeInTheDocument()
  })

  it('affiche le refus serveur (déjà postée) en toast', async () => {
    const user = userEvent.setup()
    mocks.echeancesList.mockResolvedValue({ data: TABLEAU_GENERE.echeances })
    mocks.poster.mockRejectedValueOnce({
      response: { data: { detail: "L'échéance 1 est déjà postée au grand livre : elle ne peut pas être postée une seconde fois." } },
    })
    const erreur = vi.spyOn(toast, 'error')
    const { container } = mount({ permissions: ['compta_saisir'] })
    const table = await tableDesktop(container)
    await user.click(await table.findByText('EMPR-2026-01'))

    const boutons = await screen.findAllByRole('button', { name: /Comptabiliser l'échéance/ })
    await user.click(boutons[0])

    await waitFor(() => expect(erreur).toHaveBeenCalledWith(
      "L'échéance 1 est déjà postée au grand livre : elle ne peut pas être postée une seconde fois.",
    ))
  })
})
