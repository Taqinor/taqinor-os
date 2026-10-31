import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { documentContrat } from '../../test/fixtures/contractSamples'
import { polyfillResizeObserver } from '../../test/selectNatif'

// AANA45 / D-AANA-036-BRANCHER — les écrans « Achats → paiement » (KpiP2pCard)
// et « Envois programmés » (EnvoisProgrammesPage) sont testés ici, dans le
// fichier de test existant du module reporting. Leurs charges utiles viennent
// des contrats PACT10 `kpi_p2p.json`, `rapports_programmes.json` et
// `envois_rapports.json`, assertés par les tests backend de chaque endpoint.
vi.mock('../../api/reportingApi', () => ({
  default: {
    kpiP2p: vi.fn(),
    listSavedReports: vi.fn(),
    createSavedReport: vi.fn(),
    updateSavedReport: vi.fn(),
    deleteSavedReport: vi.fn(),
    listEnvoisRapports: vi.fn(),
  },
}))

import reportingApi from '../../api/reportingApi'
import KpiP2pCard from './KpiP2pCard'
import EnvoisProgrammesPage from './EnvoisProgrammesPage'
import {
  CANAUX, SCHEDULES, STATUTS, TARGET_KINDS,
} from './envoisProgrammesChoix'

beforeAll(polyfillResizeObserver)


/* WIR17(a) — « Cohortes » (`CohortsPage.jsx`, FG98) avait déjà sa route
   (`/reporting/cohortes`, gatée responsable/admin) mais aucune entrée de menu
   ANALYSE : on vérifie ici — comme `adsengine.test.jsx`/`compta.test.jsx` le
   font pour leur propre module — que route et nav existent et pointent vers
   le même rôle. Le reste des routes `reporting` (ex. archive client/chantier)
   reste sans entrée de nav dédiée (ouvertes par clic depuis leur écran
   d'origine) : ce test ne vérifie donc pas de parité totale route↔nav,
   seulement l'ajout WIR17(a). (WIR283 a depuis branché `/reporting/dashboards`,
   couvert par `module.config.wir283.test.jsx`.) */
describe('reporting — module.config (WIR17 Cohortes)', () => {
  it('déclare /reporting/cohortes en route ET en entrée du menu ANALYSE, gatées responsable/admin', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('reporting')

    const route = config.routes.find((r) => r.path === '/reporting/cohortes')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['responsable', 'admin'])

    const navItem = config.nav.items.find((i) => i.to === '/reporting/cohortes')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe('Cohortes')
    expect(navItem.roles).toEqual(['responsable', 'admin'])
    expect(navItem.icon).toBeTruthy()
  })
})

/* AANA45 / D-AANA-036-BRANCHER — « Envois programmés » : route ET entrée de
   menu ANALYSE, gatées responsable/admin comme l'endpoint (IsResponsableOrAdmin). */
describe('reporting — module.config (AANA45 Envois programmés)', () => {
  it('déclare /reporting/envois-programmes en route ET en entrée du menu ANALYSE', async () => {
    const { default: config } = await import('./module.config.jsx')

    const route = config.routes.find((r) => r.path === '/reporting/envois-programmes')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['responsable', 'admin'])

    const navItem = config.nav.items.find((i) => i.to === '/reporting/envois-programmes')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe('Envois programmés')
    expect(navItem.k).toBe('nav.envois_programmes')
    expect(navItem.roles).toEqual(['responsable', 'admin'])
    expect(navItem.icon).toBeTruthy()
  })
})

/* ODY23 — « Reporting/Rapports/Journal → app Rapports ». Le Journal
   d'activité gagne une entrée dans le menu ANALYSE ; sa ROUTE reste déclarée
   dans features/parametres/module.config.jsx (inchangée) — on vérifie donc
   ici seulement l'entrée de nav, pas de parité route/nav dans CE fichier. */
describe('reporting — module.config (ODY23 Journal)', () => {
  it('déclare /journal en entrée du menu ANALYSE, gatée normal/responsable/admin + permission dédiée', async () => {
    const { default: config } = await import('./module.config.jsx')

    const navItem = config.nav.items.find((i) => i.to === '/journal')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe("Journal d'activité")
    expect(navItem.roles).toEqual(['normal', 'responsable', 'admin'])
    expect(navItem.perm).toBe('journal_activite_voir')
    expect(navItem.icon).toBeTruthy()

    // La route /journal n'est PAS redéclarée ici (elle vit dans parametres).
    expect(config.routes.find((r) => r.path === '/journal')).toBeFalsy()
  })
})

const CONTRAT_P2P = documentContrat('reporting', 'kpi_p2p').exemple

describe('KpiP2pCard (AANA45)', () => {
  beforeEach(() => { reportingApi.kpiP2p.mockReset() })
  afterEach(cleanup)

  it('affiche exactement les valeurs servies par le contrat', async () => {
    reportingApi.kpiP2p.mockResolvedValue({ data: CONTRAT_P2P })
    render(<KpiP2pCard />)

    expect(screen.getByTestId('kpi-p2p-chargement')).toBeInTheDocument()
    expect(await screen.findByText('Achats → paiement')).toBeInTheDocument()
    expect(await screen.findByText(/Délai demande → bon de commande/)).toBeInTheDocument()
    expect(screen.getByText(/3[,.]5\s*j/)).toBeInTheDocument()
    expect(screen.getByText(/70[,.]0/)).toBeInTheDocument()
    expect(screen.getByText(/75[,.]0\s*%/)).toBeInTheDocument()
    expect(screen.getByText('Période du 2026-10-01 au 2026-10-31')).toBeInTheDocument()

    const budget = CONTRAT_P2P.budgets_departement[0]
    const bloc = screen.getByTestId(`kpi-p2p-budget-${budget.budget_id}`)
    expect(within(bloc).getByText('Budget achats · octobre 2026')).toBeInTheDocument()
    expect(within(bloc).getByText(/42[,.]0\s*%\s*consommé/)).toBeInTheDocument()
    expect(within(bloc).getByText(/100\s?000\s*DH/)).toBeInTheDocument()
    expect(within(bloc).getByText(/58\s?000\s*DH/)).toBeInTheDocument()
    expect(reportingApi.kpiP2p).toHaveBeenCalledTimes(1)
  })

  it('omet une valeur null au lieu d’inventer un zéro', async () => {
    reportingApi.kpiP2p.mockResolvedValue({
      data: {
        ...CONTRAT_P2P,
        delai_demande_bcf_jours: null,
        conformite_fournisseur_moyenne: null,
        budgets_departement: [],
      },
    })
    render(<KpiP2pCard />)

    expect(await screen.findByText(/Demandes d’achat commandées/)).toBeInTheDocument()
    expect(screen.queryByText(/Délai demande/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Conformité fournisseurs/)).not.toBeInTheDocument()
    expect(screen.queryByTestId(/kpi-p2p-budget-/)).not.toBeInTheDocument()
  })

  it('dit l’état vide quand le serveur ne sert aucune valeur', async () => {
    reportingApi.kpiP2p.mockResolvedValue({
      data: {
        debut: null,
        fin: null,
        delai_demande_bcf_jours: null,
        budgets_departement: [],
        conformite_fournisseur_moyenne: null,
        taux_conversion_pct: null,
      },
    })
    render(<KpiP2pCard />)

    expect(await screen.findByTestId('kpi-p2p-vide')).toBeInTheDocument()
    expect(screen.queryByText(/Période du/)).not.toBeInTheDocument()
  })

  it('montre l’erreur et recharge au clic sur Réessayer', async () => {
    reportingApi.kpiP2p.mockRejectedValueOnce(new Error('boom'))
    reportingApi.kpiP2p.mockResolvedValueOnce({ data: CONTRAT_P2P })
    render(<KpiP2pCard />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Impossible de charger les indicateurs achats.')
    await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(reportingApi.kpiP2p).toHaveBeenCalledTimes(2))
    expect(await screen.findByText(/Délai demande → bon de commande/)).toBeInTheDocument()
  })
})

const CONTRAT_RAPPORTS = documentContrat('reporting', 'rapports_programmes')
const CONTRAT_ENVOIS = documentContrat('reporting', 'envois_rapports')
const RAPPORT = CONTRAT_RAPPORTS.exemple
const ENVOI = CONTRAT_ENVOIS.exemple

const page = (results) => ({ data: { count: results.length, next: null, previous: null, results } })

const preparerMocks = () => {
  Object.values(reportingApi).forEach((fn) => fn.mockReset())
  reportingApi.listSavedReports.mockResolvedValue(page([RAPPORT]))
  reportingApi.listEnvoisRapports.mockResolvedValue(page([ENVOI]))
  reportingApi.createSavedReport.mockResolvedValue({ data: RAPPORT })
  reportingApi.updateSavedReport.mockResolvedValue({ data: RAPPORT })
  reportingApi.deleteSavedReport.mockResolvedValue({})
}

const erreur400 = (data) => ({ response: { status: 400, data, headers: {} } })

describe('EnvoisProgrammesPage (AANA45)', () => {
  beforeEach(preparerMocks)
  afterEach(() => { cleanup(); vi.restoreAllMocks() })

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
