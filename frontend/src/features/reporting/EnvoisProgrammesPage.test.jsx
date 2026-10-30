import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { documentContrat } from '../../test/fixtures/contractSamples'
import { polyfillResizeObserver } from '../../test/selectNatif'

/* AANA45 / D-AANA-036-BRANCHER — écran « Envois programmés ».
   Les charges utiles viennent des contrats partagés `rapports_programmes.json`
   et `envois_rapports.json` (PACT10), asserté côté serveur par `tests_saved_reports.py` et
   `tests_ntdata40_envois.py` : aucun mock écrit à la main. */

vi.mock('../../api/reportingApi', () => ({
  default: {
    listSavedReports: vi.fn(),
    createSavedReport: vi.fn(),
    updateSavedReport: vi.fn(),
    deleteSavedReport: vi.fn(),
    listEnvoisRapports: vi.fn(),
  },
}))

import reportingApi from '../../api/reportingApi'
import EnvoisProgrammesPage from './EnvoisProgrammesPage'
import {
  CANAUX, SCHEDULES, STATUTS, TARGET_KINDS,
} from './envoisProgrammesChoix'

const CONTRAT_RAPPORTS = documentContrat('reporting', 'rapports_programmes')
const CONTRAT_ENVOIS = documentContrat('reporting', 'envois_rapports')
const RAPPORT = CONTRAT_RAPPORTS.exemple
const ENVOI = CONTRAT_ENVOIS.exemple

const page = (results) => ({ data: { count: results.length, next: null, previous: null, results } })

beforeAll(polyfillResizeObserver)
beforeEach(() => {
  Object.values(reportingApi).forEach((fn) => fn.mockReset())
  reportingApi.listSavedReports.mockResolvedValue(page([RAPPORT]))
  reportingApi.listEnvoisRapports.mockResolvedValue(page([ENVOI]))
  reportingApi.createSavedReport.mockResolvedValue({ data: RAPPORT })
  reportingApi.updateSavedReport.mockResolvedValue({ data: RAPPORT })
  reportingApi.deleteSavedReport.mockResolvedValue({})
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

const erreur400 = (data) => ({ response: { status: 400, data, headers: {} } })

describe('EnvoisProgrammesPage (AANA45)', () => {
  it('liste les rapports programmés et l’historique servis par le contrat', async () => {
    render(<EnvoisProgrammesPage />)

    const ligne = await screen.findByTestId(`envoi-programme-${RAPPORT.id}`)
    expect(within(ligne).getByText('Ventes du lundi')).toBeInTheDocument()
    expect(within(ligne).getByText('Hebdomadaire · à 8 h')).toBeInTheDocument()
    expect(within(ligne).getByText('direction@exemple.ma')).toBeInTheDocument()

    const envoi = screen.getByTestId(`envoi-${ENVOI.id}`)
    expect(within(envoi).getByText('Échec')).toBeInTheDocument()
    // Le motif d'un échec est lisible dans l'historique.
    expect(within(envoi).getByText('Backend email injoignable.')).toBeInTheDocument()
    expect(reportingApi.listEnvoisRapports).toHaveBeenCalledWith({ page_size: 50 })
  })

  it('égale ses choix à la section « choix » du contrat', () => {
    expect(TARGET_KINDS).toEqual(CONTRAT_RAPPORTS.choix.target_kind)
    expect(SCHEDULES).toEqual(CONTRAT_RAPPORTS.choix.schedule)
    expect(CANAUX).toEqual(CONTRAT_RAPPORTS.choix.canal)
    expect(STATUTS).toEqual(CONTRAT_ENVOIS.choix.statut)
  })

  it('états vides : aucun rapport programmé, aucun envoi', async () => {
    reportingApi.listSavedReports.mockResolvedValue(page([]))
    reportingApi.listEnvoisRapports.mockResolvedValue(page([]))
    render(<EnvoisProgrammesPage />)

    expect(await screen.findByText('Aucun envoi programmé')).toBeInTheDocument()
    expect(screen.getByTestId('envois-vide')).toBeInTheDocument()
  })

  it('état d’erreur de chargement avec Réessayer', async () => {
    reportingApi.listSavedReports.mockRejectedValueOnce(new Error('boom'))
    render(<EnvoisProgrammesPage />)

    expect(await screen.findByText('Chargement impossible')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByTestId(`envoi-programme-${RAPPORT.id}`)).toBeInTheDocument()
  })

  it('filtre « Échecs seulement » : relit l’historique avec statut=echec', async () => {
    render(<EnvoisProgrammesPage />)
    await screen.findByTestId(`envoi-${ENVOI.id}`)

    await userEvent.click(screen.getByLabelText('Échecs seulement'))
    await waitFor(() => expect(reportingApi.listEnvoisRapports)
      .toHaveBeenLastCalledWith({ page_size: 50, statut: 'echec' }))
  })

  it('dit quand l’historique est plus long que la page affichée', async () => {
    reportingApi.listEnvoisRapports.mockResolvedValue({
      data: { count: 130, next: 'http://x/?page=2', previous: null, results: [ENVOI] },
    })
    render(<EnvoisProgrammesPage />)

    expect(await screen.findByTestId('envois-suite')).toHaveTextContent('sur 130')
  })

  it('crée un envoi par POST des champs du formulaire, puis recharge', async () => {
    render(<EnvoisProgrammesPage />)
    await screen.findByTestId(`envoi-programme-${RAPPORT.id}`)

    await userEvent.click(screen.getByRole('button', { name: /Nouvel envoi/ }))
    await userEvent.type(screen.getByLabelText(/Nom du rapport/), 'Stock du matin')
    await userEvent.selectOptions(screen.getByLabelText('Rapport à envoyer'), 'stock')
    await userEvent.selectOptions(screen.getByLabelText('Cadence'), 'monthly')
    await userEvent.type(screen.getByLabelText(/Heure d'envoi/), '7')
    await userEvent.clear(screen.getByLabelText(/Jour du mois/))
    await userEvent.type(screen.getByLabelText(/Jour du mois/), '15')
    await userEvent.type(screen.getByLabelText(/Destinataires \(emails\)/), 'a@b.ma')
    await userEvent.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(reportingApi.createSavedReport).toHaveBeenCalledTimes(1))
    expect(reportingApi.createSavedReport).toHaveBeenCalledWith({
      name: 'Stock du matin',
      target_kind: 'stock',
      cible_id: null,
      schedule: 'monthly',
      heure_envoi: 7,
      jour_du_mois: 15,
      canal: 'email',
      recipients: 'a@b.ma',
      destinataires_whatsapp: '',
    })
    await waitFor(() => expect(reportingApi.listSavedReports).toHaveBeenCalledTimes(2))
    expect(screen.queryByTestId('envoi-form-carte')).not.toBeInTheDocument()
  })

  it('affiche l’erreur de validation SOUS le champ fautif et garde le formulaire', async () => {
    reportingApi.createSavedReport.mockRejectedValue(erreur400({
      name: ['Ce champ ne peut être vide.'],
      heure_envoi: ['Assurez-vous que cette valeur est inférieure ou égale à 23.'],
    }))
    render(<EnvoisProgrammesPage />)
    await screen.findByTestId(`envoi-programme-${RAPPORT.id}`)

    await userEvent.click(screen.getByRole('button', { name: /Nouvel envoi/ }))
    await userEvent.type(screen.getByLabelText(/Heure d'envoi/), '99')
    await userEvent.click(screen.getByRole('button', { name: 'Créer' }))

    const champNom = screen.getByLabelText(/Nom du rapport/)
    await waitFor(() => expect(champNom).toHaveAttribute('aria-invalid', 'true'))
    // Chaque message est rendu dans le bloc du champ qu'il concerne.
    expect(champNom.closest('div')).toHaveTextContent('Ce champ ne peut être vide.')
    const champHeure = screen.getByLabelText(/Heure d'envoi/)
    expect(champHeure).toHaveAttribute('aria-invalid', 'true')
    expect(champHeure.closest('div')).toHaveTextContent('inférieure ou égale à 23')
    expect(screen.getByTestId('envoi-form-carte')).toBeInTheDocument()
  })

  it('cible d’un tableau de bord : identifiant envoyé en entier, 404 rendu au champ cible_id', async () => {
    reportingApi.createSavedReport.mockRejectedValue({
      response: {
        status: 404,
        data: { cible_id: ["Cette cible n'existe pas dans votre société."] },
        headers: {},
      },
    })
    render(<EnvoisProgrammesPage />)
    await screen.findByTestId(`envoi-programme-${RAPPORT.id}`)

    await userEvent.click(screen.getByRole('button', { name: /Nouvel envoi/ }))
    await userEvent.type(screen.getByLabelText(/Nom du rapport/), 'Tableau')
    await userEvent.selectOptions(screen.getByLabelText('Rapport à envoyer'), 'dashboard')
    await userEvent.type(screen.getByLabelText('Identifiant du tableau de bord'), '987654')
    await userEvent.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(reportingApi.createSavedReport).toHaveBeenCalled())
    expect(reportingApi.createSavedReport.mock.calls[0][0]).toMatchObject({
      target_kind: 'dashboard', cible_id: 987654,
    })
    expect(await screen.findByText("Cette cible n'existe pas dans votre société.")).toBeInTheDocument()
  })

  it('canal WhatsApp : saisit les numéros, pas les emails', async () => {
    render(<EnvoisProgrammesPage />)
    await screen.findByTestId(`envoi-programme-${RAPPORT.id}`)

    await userEvent.click(screen.getByRole('button', { name: /Nouvel envoi/ }))
    await userEvent.type(screen.getByLabelText(/Nom du rapport/), 'WA')
    await userEvent.selectOptions(screen.getByLabelText('Canal'), 'whatsapp')
    expect(screen.queryByLabelText(/Destinataires \(emails\)/)).not.toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Numéros WhatsApp'), '+212600000000')
    await userEvent.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(reportingApi.createSavedReport).toHaveBeenCalled())
    expect(reportingApi.createSavedReport.mock.calls[0][0]).toMatchObject({
      canal: 'whatsapp', destinataires_whatsapp: '+212600000000',
    })
  })

  it('modifie un envoi existant par PATCH (jamais un second POST)', async () => {
    render(<EnvoisProgrammesPage />)
    await screen.findByTestId(`envoi-programme-${RAPPORT.id}`)

    await userEvent.click(screen.getByRole('button', { name: 'Modifier Ventes du lundi' }))
    const nom = screen.getByLabelText(/Nom du rapport/)
    expect(nom).toHaveValue('Ventes du lundi')
    expect(screen.getByLabelText(/Heure d'envoi/)).toHaveValue('8')
    await userEvent.selectOptions(screen.getByLabelText('Cadence'), 'daily')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(reportingApi.updateSavedReport).toHaveBeenCalledTimes(1))
    const [id, payload] = reportingApi.updateSavedReport.mock.calls[0]
    expect(id).toBe(RAPPORT.id)
    expect(payload).toMatchObject({
      name: 'Ventes du lundi', schedule: 'daily', heure_envoi: 8,
      recipients: 'direction@exemple.ma', cible_id: null,
    })
    expect(reportingApi.createSavedReport).not.toHaveBeenCalled()
  })

  it('ne supprime rien si la confirmation est refusée', async () => {
    const confirmation = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<EnvoisProgrammesPage />)
    await screen.findByTestId(`envoi-programme-${RAPPORT.id}`)

    await userEvent.click(screen.getByRole('button', { name: 'Supprimer Ventes du lundi' }))
    await waitFor(() => expect(confirmation).toHaveBeenCalledTimes(1))
    expect(reportingApi.deleteSavedReport).not.toHaveBeenCalled()
  })

  it('supprime après confirmation (DELETE existant) puis recharge', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<EnvoisProgrammesPage />)
    await screen.findByTestId(`envoi-programme-${RAPPORT.id}`)

    await userEvent.click(screen.getByRole('button', { name: 'Supprimer Ventes du lundi' }))
    await waitFor(() => expect(reportingApi.deleteSavedReport).toHaveBeenCalledWith(RAPPORT.id))
    await waitFor(() => expect(reportingApi.listSavedReports).toHaveBeenCalledTimes(2))
  })
})
