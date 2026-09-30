import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* MRY31 — écran « Suivi des relances ». Charge utile venant de l'exemple
   COMMITTÉ (`apps/crm/contract_samples/relance_etapes_suivi.json`, PACT10),
   jamais un objet retapé à la main : c'est cette deuxième source de vérité
   qui avait laissé passer l'écran AO mort du 03/08/2026 (test vert, écran
   mort). Si le serveur change de forme, l'exemple change et ce test casse
   tout seul. */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const DONNEES = exempleContrat('crm', 'relance_etapes_suivi')
const ETAPES = DONNEES.results

// Même patron que `IdentityRail.test.jsx`/`ViewsManagerPopover.test.jsx` :
// on mocke le hook de rôle plutôt que de monter un vrai Provider redux pour
// `useHasRole`. Mock réassignable par test (`.mockReturnValue`).
const isAdminOrResponsableMock = vi.fn(() => false)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))

// Même patron que `UsersManagement.test.jsx` : `useSelector` mocké
// directement plutôt qu'un vrai Provider redux (l'écran ne lit que
// `auth.user.id`).
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { id: 42 } } }),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesSuivi: vi.fn(),
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: {} })),
    marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: {} })),
    reporterRelanceEtape: vi.fn(() => Promise.resolve({ data: {} })),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
  },
}))

// SUIVI-REFUS — seul `toastError` est remplacé (pour prouver qu'un refus NOMMÉ
// n'ajoute pas de toast générique) ; les autres exports du helper restent réels.
vi.mock('../../lib/toast', async (importOriginal) => ({
  ...(await importOriginal()),
  toastError: vi.fn(),
}))

import crmApi from '../../api/crmApi'
import { toastError } from '../../lib/toast'
import RelancesSuiviPage from './RelancesSuiviPage'

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(false)
  crmApi.getRelanceEtapesSuivi.mockResolvedValue(reponseContrat('crm', 'relance_etapes_suivi'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesSuiviPage />
    </MemoryRouter>,
  )
}

// Bornes Casablanca — recalculées ICI indépendamment de l'écran (jamais un
// import de son détail interne) pour que le test reste une vraie preuve, pas
// une tautologie — même esprit que `CadenceFrise.mry15.test.jsx` (F3).
// Un `TabsTrigger` Radix s'active sur mousedown (bouton 0) — jamais sur un
// simple `click` synthétique (piège DOM RTL, même famille que le pointerdown
// des menus Radix) : les deux événements, dans cet ordre.
function activerOnglet(name) {
  const tab = screen.getByRole('tab', { name })
  fireEvent.mouseDown(tab, { button: 0 })
  fireEvent.click(tab)
}

function casaISO(d) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca' }).format(d)
}
function decalerJours(yyyyMmDd, delta) {
  const [y, m, d] = yyyyMmDd.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d + delta)).toISOString().slice(0, 10)
}

describe('RelancesSuiviPage (MRY31)', () => {
  it('groupe les touches par jour, affiche le résumé serveur et une touche « Fait » avec son auteur', async () => {
    mount()
    // Onglet « 7 derniers jours » : AUCUN filtrage côté écran (contrairement
    // à l'onglet par défaut « Aujourd'hui + retard », qui compare au jour
    // réel d'exécution) — la seule façon de tester le regroupement/les
    // badges sans dépendre de la date du jour où la CI tourne.
    activerOnglet('7 derniers jours')
    await waitFor(() => expect(screen.getAllByTestId('relance-etape-row')).toHaveLength(2))

    // `resume` vient TEL QUEL du serveur (jamais recompté écran) : 1/0/1/0.
    expect(screen.getByText(/À faire\s*:\s*1/)).toBeInTheDocument()
    expect(screen.getByText(/En retard\s*:\s*0/)).toBeInTheDocument()
    expect(screen.getByText(/Faites\s*:\s*1/)).toBeInTheDocument()
    expect(screen.getByText(/Sautées\s*:\s*0/)).toBeInTheDocument()

    // Les deux étapes du contrat partagent le même `due_date` : UN seul
    // groupe de jour attendu, calculé indépendamment de l'écran.
    const d = new Date(`${ETAPES[0].due_date}T00:00:00`)
    const semaine = new Intl.DateTimeFormat('fr-FR', { weekday: 'long' }).format(d)
    const jour = new Intl.DateTimeFormat('fr-FR', { day: 'numeric' }).format(d)
    const mois = new Intl.DateTimeFormat('fr-FR', { month: 'long' }).format(d)
    expect(screen.getByText(new RegExp(`${semaine} ${jour} ${mois}`, 'i'))).toBeInTheDocument()

    // La touche « fait » (id 412 du contrat) affiche l'auteur du marquage.
    // Le badge complet (« Fait · HH:MM · auteur ») : le seul nom de l'auteur
    // apparaît AUSSI dans la puce responsable de chaque ligne.
    expect(screen.getByText(new RegExp(`^Fait · \\d{2}:\\d{2} · ${ETAPES[0].traite_par_nom}$`))).toBeInTheDocument()
  })

  it('« Demain » appelle l\'API avec les bornes de demain (Africa/Casablanca)', async () => {
    mount()
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalled())
    const today = casaISO(new Date())
    const demain = decalerJours(today, 1)
    // Une touche du protocole datée de DEMAIN, à faire (l'exemple committé
    // date d'un autre jour : il serait filtré hors de l'onglet).
    crmApi.getRelanceEtapesSuivi.mockResolvedValue({
      data: {
        results: [{ ...ETAPES[0], id: 778, due_date: demain, statut: 'a_faire', overdue: false }],
        resume: { a_faire: 1, en_retard: 0, fait: 0, sautee: 0, annulee: 0 },
      },
    })
    activerOnglet('Demain')
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledWith(
      expect.objectContaining({ date_debut: demain, date_fin: demain }),
    ))
    // CAD44 puis SUIVI-BLOCAGE (30/09/2026) — les lignes « Demain » ne se
    // lisent plus seulement : même règle que le cockpit (CADX). Sur une touche
    // du protocole à venir : Appeler / WhatsApp / Reporter ouverts, « Fait »
    // caché jusqu'à l'échéance (ou jusqu'au geste réellement fait).
    await waitFor(() => expect(screen.queryAllByRole('button', { name: /Appeler/ }).length).toBeGreaterThan(0))
    expect(screen.queryAllByRole('button', { name: /Reporter/ }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /^Fait$/ })).not.toBeInTheDocument()
    expect(screen.getAllByTestId('touche-en-avance').length).toBeGreaterThan(0)
  })

  it('le filtre Responsable est masqué au rôle normal', async () => {
    isAdminOrResponsableMock.mockReturnValue(false)
    mount()
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalled())
    expect(screen.queryByLabelText('Responsable')).not.toBeInTheDocument()
  })

  it('le filtre Responsable est visible aux rôles responsable/admin, par défaut « Toute l\'équipe » (CAD112)', async () => {
    isAdminOrResponsableMock.mockReturnValue(true)
    mount()
    await waitFor(() => expect(screen.getByLabelText('Responsable')).toBeInTheDocument())
    // CAD112 — aligné sur le Cockpit (`RelancesDuJourWidget.jsx`), qui n'a
    // aucun filtre propriétaire : à « Moi », un admin ouvrant le Suivi ne
    // voyait que SES touches quand le même admin, sur l'onglet HOMONYME
    // « Aujourd'hui + retard » du cockpit, voyait toute l'équipe.
    expect(screen.getByText("Toute l'équipe")).toBeInTheDocument()
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledWith(
      expect.not.objectContaining({ owner: expect.anything() }),
    ))
  })
})

describe('RelancesSuiviPage — CAD112 (deux onglets homonymes « Aujourd\'hui + retard »)', () => {
  // `casaISO`/`decalerJours` : déjà déclarées plus haut dans ce fichier
  // (helpers de test « Demain », mêmes calculs que ceux internes de l'écran).

  it('la fenêtre de « Aujourd\'hui + retard » couvre 62 jours en arrière (une touche J-35 y entre, comme dans le Cockpit sans borne basse)', async () => {
    mount()
    const today = casaISO(new Date())
    const borneBasse = decalerJours(today, -62)
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledWith(
      expect.objectContaining({ date_debut: borneBasse, date_fin: today }),
    ))
  })

  it('une touche en retard de 35 jours (J-35), renvoyée par le serveur, s\'affiche sur cet onglet', async () => {
    const j35 = decalerJours(casaISO(new Date()), -35)
    crmApi.getRelanceEtapesSuivi.mockResolvedValue({
      data: {
        results: [{ ...ETAPES[0], id: 777, due_date: j35, statut: 'a_faire' }],
        resume: { a_faire: 1, en_retard: 1, fait: 0, sautee: 0, annulee: 0 },
      },
    })
    mount()
    expect(await screen.findAllByTestId('relance-etape-row')).toHaveLength(1)
  })
})

/* SUIVI-REFUS (30/09/2026) — l'écran de suivi avalait, comme le cockpit et la
   frise, le refus serveur de « Sauter » et « Reporter » (double clic → 400
   `erreurs.etape`, SUIVI E8) : panneau refermé comme réussi + toast générique.
   Comme « Fait » : panneau ouvert, message exact sous le geste, liste NON
   relue sur un refus, aucun toast générique. */
describe('RelancesSuiviPage — SUIVI-REFUS (Sauter / Reporter refusés)', () => {
  const DEJA_TRAITEE = 'Cette étape est déjà traitée — rechargez la liste.'
  const refus400 = (erreurs) => ({ response: { status: 400, data: { erreurs } } })

  // Une touche À FAIRE d'aujourd'hui : actionnable (ni lecture seule, ni à venir).
  const AUJOURDHUI = () => casaISO(new Date())
  const touche = () => ({
    ...ETAPES.find((e) => e.statut === 'a_faire'),
    id: 780, due_date: AUJOURDHUI(), overdue: false, statut: 'a_faire',
  })
  beforeEach(() => {
    crmApi.getRelanceEtapesSuivi.mockResolvedValue({
      data: {
        results: [touche()],
        resume: { a_faire: 1, en_retard: 0, fait: 0, sautee: 0, annulee: 0 },
      },
    })
  })

  async function monterEtOuvrir(geste) {
    mount()
    expect(await screen.findAllByTestId('relance-etape-row')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: geste }))
  }
  const confirmer = () => fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
  const demain = () => decalerJours(AUJOURDHUI(), 1)

  it('« Reporter » refusé (400 erreurs.etape) : panneau ouvert, message exact, liste non relue, aucun toast générique', async () => {
    crmApi.reporterRelanceEtape.mockRejectedValueOnce(refus400({ etape: DEJA_TRAITEE }))
    await monterEtOuvrir(/Reporter/)
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: demain() } })
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    expect(crmApi.reporterRelanceEtape).toHaveBeenCalledWith(
      780, { rappel_le: demain(), rappel_heure: '09:00' })
    expect(screen.getByLabelText('Reporter au')).toHaveValue(demain())
    expect(toastError).not.toHaveBeenCalled()
    expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Confirmer' })).not.toBeDisabled())
  })

  it('« Sauter » refusé (400 erreurs.etape) : panneau ouvert, message exact, liste non relue, aucun toast générique', async () => {
    crmApi.marquerRelanceEtapeSautee.mockRejectedValueOnce(refus400({ etape: DEJA_TRAITEE }))
    await monterEtOuvrir(/Sauter/)
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    expect(screen.getByTestId('suite-sauter')).toBeInTheDocument()
    expect(toastError).not.toHaveBeenCalled()
    expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledTimes(1)
  })

  it('« Reporter » : un échec RÉSEAU garde son toast (F2) ET la phrase claire sous le geste', async () => {
    crmApi.reporterRelanceEtape.mockRejectedValueOnce(new Error('Network Error'))
    await monterEtOuvrir(/Reporter/)
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: demain() } })
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent('Pas de connexion au serveur')
    expect(toastError).toHaveBeenCalledWith('Action impossible pour le moment.')
  })

  it('succès « Reporter » inchangé : la liste est relue EN PLACE et le panneau se referme', async () => {
    await monterEtOuvrir(/Reporter/)
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: demain() } })
    confirmer()
    await waitFor(() => expect(crmApi.reporterRelanceEtape).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByLabelText('Reporter au')).not.toBeInTheDocument())
    expect(screen.queryByTestId('erreur-outcome')).not.toBeInTheDocument()
    expect(toastError).not.toHaveBeenCalled()
  })

  it('succès « Sauter » inchangé : la liste est relue EN PLACE', async () => {
    await monterEtOuvrir(/Sauter/)
    confirmer()
    await waitFor(() => expect(crmApi.marquerRelanceEtapeSautee).toHaveBeenCalledWith(780, ''))
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledTimes(2))
    expect(toastError).not.toHaveBeenCalled()
  })
})
