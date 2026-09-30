import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import api from '../../api/axios'
import crmApi from '../../api/crmApi'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
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

// La préférence « détail du contrôle déplié » du navigateur ne doit pas fuir d'un test à l'autre.
afterEach(() => { cleanup(); vi.clearAllMocks(); window.localStorage.clear() })

function makeStore({ clients = [], leads = [], role = 'admin' } = {}) {
  return configureStore({
    reducer: {
      crm: (state = { clients, leads, loading: false, error: null }) => state,
      // MRY33 — `PlacementAnciensLeadsCard` (rendue pour de vrai ici, comme
      // `KpiRelancesPanel`) se gate au rôle via
      // `useIsAdminOrResponsable` (`useHasPermission.js`, lit `state.auth.role`
      // directement) : sans cette tranche minimale, ce smoke test plantait au
      // montage (`Cannot read properties of undefined`). `admin` par défaut — la
      // carte reste inerte tant qu'on ne clique pas « Aperçu » (aucun appel
      // réseau dans ces trois tests). COCKPIT-CONTRÔLE : le rôle est
      // paramétrable — la carte de placement et l'aide du contrôle en dépendent,
      // l'ORDRE de la page, jamais.
      auth: (state = { role }) => state,
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

// COCKPIT-CONTRÔLE passe 2 (fondateur, 30/09/2026) — UNE seule page, le MÊME ordre
// pour tous les rôles (aucune branche par rôle) : en-tête, « Contrôle du suivi »
// (repliable), insights, chaîne commerciale, la file du jour, puis la grille ;
// l'ancienne vue « Adhérence » et les tuiles perso CKP4 ont quitté la page.
// Charges utiles = les exemples COMMITTÉS du contrat (PACT10).
describe('COCKPIT-CONTRÔLE passe 2 — un seul ordre de page pour tous les rôles', () => {
  beforeEach(() => {
    vi.spyOn(crmApi, 'getControleSuivi').mockResolvedValue(reponseContrat('crm', 'controle_suivi'))
    vi.spyOn(crmApi, 'getRelanceEtapesDues').mockResolvedValue(reponseContrat('crm', 'relance_etape_v2'))
    vi.spyOn(crmApi, 'getChaineCommerciale').mockResolvedValue(reponseContrat('crm', 'chaine_commerciale'))
    // Espion SANS remplacement sur le client HTTP : on relève les routes que le
    // cockpit demande vraiment (les autres widgets, eux, gardent leur appel réel).
    vi.spyOn(api, 'get')
  })
  afterEach(() => { vi.restoreAllMocks() })

  /** Vrai si `a` précède `b` dans l'ordre du document. */
  const precede = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

  async function monterEtAttendre(role) {
    mount({ role })
    // Les deux blocs ont chargé leurs données (ils ne sont plus des squelettes).
    await screen.findByTestId('controle-verdict')
    await screen.findAllByTestId('relance-etape-row')
    await screen.findByTestId('chaine-commerciale-panel')
    return {
      controle: screen.getByTestId('cockpit-controle-suivi'),
      file: screen.getByTestId('cockpit-file'),
      insights: screen.getByTestId('crm-insights-stub'),
      chaine: screen.getByTestId('chaine-commerciale-panel'),
      dormants: screen.getByTestId('dormant-accounts-stub'),
    }
  }

  // Les blocs de la page, par leur hook DOM, dans l'ordre où on les rencontre.
  const BLOCS = [
    'crm-cockpit-stats', 'cockpit-controle-suivi', 'crm-insights-stub', 'chaine-commerciale-panel',
    'cockpit-file', 'kpi-relances-panel', 'placement-anciens-leads-card', 'dormant-accounts-stub',
    'portfolio-widget-stub',
  ]
  const ordreDuDocument = () => [...document.querySelectorAll('[data-testid]')]
    .map((el) => el.getAttribute('data-testid'))
    .filter((id) => BLOCS.includes(id))

  it.each(['admin', 'responsable', 'normal'])(
    '%s : le MÊME ordre — en-tête, contrôle, insights, chaîne, file, puis la grille',
    async (role) => {
      await monterEtAttendre(role)
      expect(ordreDuDocument()).toEqual([
        'crm-cockpit-stats', 'cockpit-controle-suivi', 'crm-insights-stub', 'chaine-commerciale-panel',
        'cockpit-file', 'kpi-relances-panel',
        // La carte de placement se gate elle-même aux rôles responsable / admin
        // (MRY33) : c'est la SEULE différence entre les rôles.
        ...(role === 'normal' ? [] : ['placement-anciens-leads-card']),
        'dormant-accounts-stub', 'portfolio-widget-stub',
      ])
    },
  )

  it('le contrôle est là pour tous les rôles — jamais caché —, replié par défaut : le bandeau, pas la frise', async () => {
    for (const role of ['admin', 'responsable', 'normal']) {
      const { unmount } = mount({ role })
      await screen.findByTestId('controle-verdict')
      expect(within(screen.getByTestId('cockpit-controle-suivi')).getByTestId('controle-suivi-panel'))
        .toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Voir le détail' })).toHaveAttribute('aria-expanded', 'false')
      expect(screen.queryByTestId('controle-frise')).not.toBeInTheDocument()
      unmount()
    }
  })

  it('la file s\'appelle « À faire aujourd\'hui » pour tous les rôles ; « Ma journée » a quitté la page', async () => {
    for (const role of ['admin', 'responsable', 'normal']) {
      const { unmount } = mount({ role })
      await screen.findAllByTestId('relance-etape-row')
      expect(within(screen.getByTestId('cockpit-file')).getByRole('heading', { name: 'À faire aujourd\'hui' }))
        .toBeInTheDocument()
      expect(screen.queryByText(/Ma journée/)).not.toBeInTheDocument()
      unmount()
    }
  })

  it.each(['admin', 'normal'])('%s : le contrôle est sous l\'en-tête et AU-DESSUS du reste de la page', async (role) => {
    const {
      controle, file, insights, chaine, dormants,
    } = await monterEtAttendre(role)
    const entete = screen.getByRole('heading', { name: 'CRM' })
    expect(precede(entete, controle)).toBe(true)
    ;[insights, chaine, file, dormants].forEach((reste) => expect(precede(controle, reste)).toBe(true))
    // La file du jour vient APRÈS la chaîne commerciale et AVANT la grille.
    expect(precede(chaine, file)).toBe(true)
    expect(precede(file, dormants)).toBe(true)
  })

  it('pleine largeur : ni le contrôle ni la file ne sont dans la grille à deux colonnes', async () => {
    const { controle, file } = await monterEtAttendre('admin')
    expect(controle.closest('.md\\:grid-cols-2')).toBeNull()
    expect(file.closest('.md\\:grid-cols-2')).toBeNull()
    // Le reste de la page (comptes dormants…) reste, lui, dans la grille du bas.
    expect(screen.getByTestId('dormant-accounts-stub').closest('.md\\:grid-cols-2')).not.toBeNull()
  })

  it('l\'ancienne vue « Adhérence » et les tuiles perso CKP4 ont quitté la page (les deux rôles)', async () => {
    for (const role of ['admin', 'normal']) {
      const { unmount } = mount({ role })
      // Un rôle après l'autre, par construction.
      await screen.findByTestId('controle-verdict')
      expect(screen.queryByTestId('adherence-relances-panel')).not.toBeInTheDocument()
      expect(screen.queryByTestId('mes-stats-relance-tuiles')).not.toBeInTheDocument()
      unmount()
    }
    // Le code mort a suivi : plus aucune méthode cliente pour ces deux routes
    // serveur (`kpi-adherence/`, `mes-stats/` — les routes restent côté serveur)…
    expect(crmApi.getKpiAdherence).toBeUndefined()
    expect(crmApi.getMesStatsRelance).toBeUndefined()
    // … et le cockpit n'en demande aucune (l'espion a bien vu passer d'autres routes).
    const routes = api.get.mock.calls.map(([url]) => String(url))
    expect(routes.length).toBeGreaterThan(0)
    expect(routes.filter((url) => /kpi-adherence|mes-stats/.test(url))).toEqual([])
  })

  it('le contrôle et la file lisent chacun leur route, une fois', async () => {
    await monterEtAttendre('admin')
    expect(crmApi.getControleSuivi).toHaveBeenCalledTimes(1)
    expect(crmApi.getControleSuivi).toHaveBeenCalledWith({ jours: 14 })
    expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith({ scope: 'all' })
  })
})
