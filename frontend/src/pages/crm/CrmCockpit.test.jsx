import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import crmApi from '../../api/crmApi'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import CrmCockpit from './CrmCockpit'

/* ODY15 — rendu smoke du cockpit CRM (ModuleHero + actions rapides + KPI).
   Aucun appel réseau réel : `fetchClients`/`fetchLeads` sont mockés en no-op
   (même patron que ClientList.test.jsx) et `CrmInsightsPanel` (VX219/WR9, son
   propre appel réseau) est mocké en stub — ce test vérifie SEULEMENT que le
   cockpit assemble correctement ModuleHero + actions + KPI + le panneau
   d'insights, pas le comportement interne du panneau (déjà couvert
   ailleurs). */

vi.mock('../../features/crm/store/crmSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchClients: () => ({ type: 'crm/fetchClients/noop' }),
    fetchLeads: () => ({ type: 'crm/fetchLeads/noop' }),
  }
})

vi.mock('./leads/CrmInsightsPanel', () => ({
  default: () => <div data-testid="crm-insights-stub" />,
}))

// NTCRM15 — le widget comptes dormants a son propre appel réseau (couvert
// par son propre test) ; ce smoke test ne vérifie que l'assemblage cockpit.
vi.mock('./DormantAccountsWidget', () => ({
  default: () => <div data-testid="dormant-accounts-stub" />,
}))

// NTCRM29 — même patron : le widget portefeuille a son propre appel réseau
// (couvert par son propre test), stubé ici pour ce smoke test d'assemblage.
vi.mock('./dashboard/PortfolioWidget', () => ({
  default: () => <div data-testid="portfolio-widget-stub" />,
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore({ clients = [], leads = [] } = {}) {
  return configureStore({
    reducer: {
      crm: (state = { clients, leads, loading: false, error: null }) => state,
      // MRY33 — `PlacementAnciensLeadsCard` (rendue pour de vrai ici, comme
      // `KpiRelancesPanel`) se gate au rôle via
      // `useIsAdminOrResponsable` (`useHasPermission.js`, lit `state.auth.role`
      // directement) : sans cette tranche minimale, ce smoke test plantait au
      // montage (`Cannot read properties of undefined`). `admin` — la carte
      // reste inerte tant qu'on ne clique pas « Aperçu » (aucun appel réseau
      // dans ces trois tests).
      auth: (state = { role: 'admin' }) => state,
    },
  })
}

function mount(opts) {
  const store = makeStore(opts)
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/crm/cockpit']}>
        <ThemeProvider>
          <CrmCockpit />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('CrmCockpit — rendu smoke (ODY15)', () => {
  it('affiche le titre CRM (ModuleHero) et les actions rapides', () => {
    mount()
    expect(screen.getByRole('heading', { name: 'CRM' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Nouveau lead/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Nouveau client/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Carte/ })).toBeInTheDocument()
  })

  it('affiche les compteurs KPI dérivés des clients/leads chargés', () => {
    mount({
      clients: [{ id: 1 }, { id: 2 }],
      leads: [
        { id: 1, is_archived: false, perdu: false },
        { id: 2, is_archived: true, perdu: false },
      ],
    })
    const stats = screen.getByTestId('crm-cockpit-stats')
    expect(stats).toHaveTextContent('Clients')
    expect(stats).toHaveTextContent('2')
    expect(stats).toHaveTextContent('Leads actifs')
    expect(stats).toHaveTextContent('1')
  })

  it('rend le panneau d’insights CRM existant (VX219/WR9), aucune deuxième implémentation', () => {
    mount()
    expect(screen.getByTestId('crm-insights-stub')).toBeInTheDocument()
  })
})

// PARAM-CADENCE (décision fondateur 25/09/2026) — le panneau « Où en est la
// chaîne » (E6), au-dessus de la file du jour. Charge utile = l'exemple
// COMMITTÉ du contrat `chaine_commerciale` (PACT10), jamais un objet retapé.
// Seul `crmApi.getChaineCommerciale` est espionné (`vi.spyOn`, jamais un
// `vi.mock` du module entier) : les autres widgets du cockpit
// (RelancesDuJourWidget, KpiRelancesPanel…) gardent leur comportement réel
// déjà toléré par les tests smoke ci-dessus (appel réseau qui échoue vite en
// environnement de test, géré par chacun).
describe('PARAM-CADENCE — panneau « Où en est la chaîne » (E6)', () => {
  afterEach(() => { vi.restoreAllMocks() })

  it('affiche les trois tuiles depuis le contrat committé, avec liens et « et N autres »', async () => {
    const donnees = exempleContrat('crm', 'chaine_commerciale')
    vi.spyOn(crmApi, 'getChaineCommerciale').mockResolvedValue({ data: donnees })
    mount()
    const panneau = await screen.findByTestId('chaine-commerciale-panel')
    expect(panneau).toHaveTextContent('Où en est la chaîne')
    expect(screen.getByTestId('chaine-total-joints_sans_devis')).toHaveTextContent('3')
    expect(screen.getByTestId('chaine-total-visites_a_venir')).toHaveTextContent('1')
    expect(screen.getByTestId('chaine-total-devis_a_preparer')).toHaveTextContent('2')
    // Chaque dossier servi est un LIEN vers sa fiche (/crm/leads?lead=<id>).
    const lien = screen.getByRole('link', { name: 'Fatima Alaoui' })
    expect(lien).toHaveAttribute('href', '/crm/leads?lead=1489')
    // « et N autres » : total (3) > le seul dossier servi → N = 2 ; la
    // limite (5) affichée vient du contrat, jamais devinée côté écran.
    const tuileJoints = screen.getByTestId('chaine-tuile-joints_sans_devis')
    expect(tuileJoints).toHaveTextContent('et 2 autres')
    expect(tuileJoints).toHaveTextContent('5')
    // total (2) > 1 dossier servi → N = 1, singulier (« autre », pas « autres »).
    expect(screen.getByTestId('chaine-tuile-devis_a_preparer')).toHaveTextContent('et 1 autre')
    // total === le nombre de dossiers servis (1) → pas de « et N autres ».
    expect(screen.getByTestId('chaine-tuile-visites_a_venir'))
      .not.toHaveTextContent(/et \d+ autres?/)
  })

  it('état vide (`exemple_vide`) : une ligne neutre par tuile', async () => {
    const vide = exempleContrat('crm', 'chaine_commerciale', 'exemple_vide')
    vi.spyOn(crmApi, 'getChaineCommerciale').mockResolvedValue({ data: vide })
    mount()
    await screen.findByTestId('chaine-commerciale-panel')
    expect(screen.getAllByText('Aucun dossier.')).toHaveLength(3)
  })

  it('erreur réseau : le panneau se tait — jamais un cockpit cassé', async () => {
    vi.spyOn(crmApi, 'getChaineCommerciale').mockRejectedValue(new Error('network'))
    mount()
    expect(screen.getByRole('heading', { name: 'CRM' })).toBeInTheDocument()
    await waitFor(() => expect(crmApi.getChaineCommerciale).toHaveBeenCalled())
    expect(screen.queryByTestId('chaine-commerciale-panel')).not.toBeInTheDocument()
    expect(screen.queryByText('Où en est la chaîne')).not.toBeInTheDocument()
  })
})
