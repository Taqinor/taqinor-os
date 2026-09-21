import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT78 — Paramètres avancés du module Projet (3 ressources sans écran).

   Charges utiles alignées sur les sérialiseurs serveur réels :
   `PeriodeVerrouilleeTempsSerializer` (id/mois/verrouille_par/
   verrouille_par_nom/date_creation), `PortailProjetTokenSerializer`
   (id/projet/projet_code/token/actif/date_creation) et
   `RecurrenceTacheSerializer` (id/projet/projet_code/libelle/phase/
   charge_estimee/assigne/regle/regle_display/intervalle/prochaine_echeance/
   date_fin/nb_occurrences/nb_generees/actif/date_creation). */

vi.mock('../../api/gestionProjetApi', () => ({
  default: {
    getProjets: vi.fn(),
    getPeriodesVerrouillees: vi.fn(),
    getPortailTokens: vi.fn(),
    getRecurrencesTache: vi.fn(),
    createPeriodeVerrouillee: vi.fn(),
    deletePeriodeVerrouillee: vi.fn(),
    createPortailToken: vi.fn(),
    updatePortailToken: vi.fn(),
    createRecurrenceTache: vi.fn(),
    deleteRecurrenceTache: vi.fn(),
  },
}))

import gestionProjetApi from '../../api/gestionProjetApi'
import ParametresAvances from './ParametresAvances'

const PROJETS = [
  { id: 1, code: 'PRJ-001', nom: 'Centrale Bouskoura', statut: 'en_cours' },
  { id: 2, code: 'PRJ-002', nom: 'Pompage Tadla', statut: 'planifie' },
]

const PERIODES = [
  {
    id: 6, mois: '2026-06-01', verrouille_par: 3, verrouille_par_nom: 'reda',
    date_creation: '2026-07-01T09:00:00Z',
  },
]

const TOKENS = [
  {
    id: 9, projet: 1, projet_code: 'PRJ-001', token: 'tok-abc123',
    actif: true, date_creation: '2026-07-10T09:00:00Z',
  },
]

const RECURRENCES = [
  {
    id: 4, projet: 1, projet_code: 'PRJ-001', libelle: 'Réunion de chantier',
    phase: null, charge_estimee: null, assigne: null, regle: 'hebdomadaire',
    regle_display: 'Hebdomadaire', intervalle: 1,
    prochaine_echeance: '2026-08-20', date_fin: null, nb_occurrences: null,
    nb_generees: 3, actif: true, date_creation: '2026-07-01T09:00:00Z',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  gestionProjetApi.getProjets.mockResolvedValue({ data: PROJETS })
  gestionProjetApi.getPeriodesVerrouillees.mockResolvedValue({ data: PERIODES })
  gestionProjetApi.getPortailTokens.mockResolvedValue({ data: TOKENS })
  gestionProjetApi.getRecurrencesTache.mockResolvedValue({ data: RECURRENCES })
  gestionProjetApi.createPeriodeVerrouillee.mockResolvedValue({ data: { id: 7 } })
  gestionProjetApi.deletePeriodeVerrouillee.mockResolvedValue({ data: {} })
  gestionProjetApi.createPortailToken.mockResolvedValue({ data: { id: 10 } })
  gestionProjetApi.updatePortailToken.mockResolvedValue({ data: {} })
  gestionProjetApi.createRecurrenceTache.mockResolvedValue({ data: { id: 5 } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ParametresAvances (PACT78)', () => {
  it('verrouille un mois de feuilles de temps (1er jour du mois, comme le serveur l’attend)', async () => {
    const user = userEvent.setup()
    render(<ParametresAvances />)
    await screen.findByTestId('projet-parametres-verrous')

    fireEvent.change(screen.getByLabelText('Mois à verrouiller'), {
      target: { value: '2026-07' },
    })
    await user.click(screen.getByRole('button', { name: 'Verrouiller le mois' }))

    await waitFor(() => expect(gestionProjetApi.createPeriodeVerrouillee)
      .toHaveBeenCalledWith({ mois: '2026-07-01' }))
    // Le verrou existant reste déverrouillable.
    const verrou = screen.getByTestId('periode-verrouillee-6')
    await user.click(within(verrou).getByRole('button', { name: 'Déverrouiller' }))
    await waitFor(() => expect(gestionProjetApi.deletePeriodeVerrouillee)
      .toHaveBeenCalledWith(6))
  })

  it('génère puis révoque le lien public de portail d’un projet', async () => {
    const user = userEvent.setup()
    render(<ParametresAvances />)
    await screen.findByTestId('projet-parametres-portail')

    // Le lien affiché est bâti sur le jeton SERVEUR (jamais fabriqué ici).
    const ligne = screen.getByTestId('portail-token-9')
    expect(within(ligne).getByText(/\/gestion-projet\/portail\/tok-abc123\//))
      .toBeInTheDocument()
    expect(within(ligne).getByText('Actif')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Projet'), '2')
    await user.click(screen.getByRole('button', { name: 'Générer le lien' }))
    await waitFor(() => expect(gestionProjetApi.createPortailToken)
      .toHaveBeenCalledWith({ projet: '2' }))

    const ligneApres = screen.getByTestId('portail-token-9')
    await user.click(within(ligneApres).getByRole('button', { name: 'Révoquer' }))
    await waitFor(() => expect(gestionProjetApi.updatePortailToken)
      .toHaveBeenCalledWith(9, { actif: false }))
  })

  it('crée un gabarit de tâche récurrente sans jamais générer de tâche', async () => {
    const user = userEvent.setup()
    render(<ParametresAvances />)
    await screen.findByTestId('projet-parametres-recurrences')

    // Le gabarit existant affiche le compteur SERVEUR des occurrences générées.
    expect(within(screen.getByTestId('recurrence-tache-4')).getByText('3'))
      .toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Projet du gabarit'), '1')
    await user.type(screen.getByLabelText('Libellé de la tâche'), 'Point sécurité')
    await user.selectOptions(screen.getByLabelText('Règle'), 'mensuelle')
    fireEvent.change(screen.getByLabelText('Prochaine échéance'), {
      target: { value: '2026-09-01' },
    })
    await user.click(screen.getByRole('button', { name: 'Créer le gabarit' }))

    await waitFor(() => expect(gestionProjetApi.createRecurrenceTache)
      .toHaveBeenCalledWith({
        projet: '1',
        libelle: 'Point sécurité',
        regle: 'mensuelle',
        intervalle: 1,
        prochaine_echeance: '2026-09-01',
      }))
    expect(screen.getByText(/La génération reste une commande serveur/))
      .toBeInTheDocument()
  })
})
