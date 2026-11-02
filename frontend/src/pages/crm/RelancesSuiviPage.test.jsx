import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '../../test/relancesSuiviHarness'
import { isAdminOrResponsableMock } from '../../test/relancesSuiviMocks'
import { screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* MRY31 — écran « Suivi des relances ». Charge utile venant de l'exemple
   COMMITTÉ (`apps/crm/contract_samples/relance_etapes_suivi.json`, PACT10),
   jamais un objet retapé à la main : c'est cette deuxième source de vérité
   qui avait laissé passer l'écran AO mort du 03/08/2026 (test vert, écran
   mort). Si le serveur change de forme, l'exemple change et ce test casse
   tout seul. */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const DONNEES = exempleContrat('crm', 'relance_etapes_suivi')
const ETAPES = DONNEES.results

vi.mock('../../api/crmApi', async () => (await import('../../test/relancesSuiviMocks')).crmApiSuivi({
  marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: {} })),
  marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: {} })),
  reporterRelanceEtape: vi.fn(() => Promise.resolve({ data: {} })),
}))

// SUIVI-REFUS — seul `toastError` est remplacé (pour prouver qu'un refus NOMMÉ
// n'ajoute pas de toast générique) ; les autres exports du helper restent réels.
vi.mock('../../lib/toast', async (importOriginal) => ({
  ...(await importOriginal()),
  toastError: vi.fn(),
}))

import crmApi from '../../api/crmApi'
import { toastError } from '../../lib/toast'
import { render, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import RelancesSuiviPage from './RelancesSuiviPage'
import { fusionnerLignes } from '../../features/crm/relances/fusionSuivi'
import RelancesEquipePanel from './RelancesEquipePanel'

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(false)
  crmApi.getRelanceEtapesSuivi.mockResolvedValue(reponseContrat('crm', 'relance_etapes_suivi'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

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

  // SUIVI-RELOAD (02/11/2026) — ces deux succès relisaient toute la PÉRIODE
  // (~1,5 Mo) ; ils relisent désormais le seul LEAD concerné, et la touche
  // elle-même vient de la réponse du geste.
  it('succès « Reporter » : le panneau se referme, seules les touches du LEAD sont relues — jamais la période', async () => {
    crmApi.reporterRelanceEtape.mockResolvedValue({
      data: { ...touche(), due_date: demain(), due_at: `${demain()}T09:00:00Z` },
    })
    await monterEtOuvrir(/Reporter/)
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: demain() } })
    confirmer()
    await waitFor(() => expect(crmApi.reporterRelanceEtape).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith(
      { lead: touche().lead }, { suppressErrorToast: true }))
    await waitFor(() => expect(screen.queryByLabelText('Reporter au')).not.toBeInTheDocument())
    expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId('erreur-outcome')).not.toBeInTheDocument()
    expect(toastError).not.toHaveBeenCalled()
  })

  it('succès « Sauter » : la touche sautée vient de sa réponse (badge « Sautées : 1 »), le lead est relu, la période non', async () => {
    const sautee = { ...touche(), statut: 'sautee', statut_libelle: 'Sautée' }
    crmApi.marquerRelanceEtapeSautee.mockResolvedValue({ data: sautee })
    // Le serveur, relu sur le LEAD, confirme la même touche sautée.
    crmApi.getRelanceEtapesDues.mockResolvedValue({ data: { count: 1, results: [sautee] } })
    await monterEtOuvrir(/Sauter/)
    confirmer()
    await waitFor(() => expect(crmApi.marquerRelanceEtapeSautee).toHaveBeenCalledWith(780, ''))
    await waitFor(() => expect(screen.getByText(/Sautées\s*:\s*1/)).toBeInTheDocument())
    // Le DELTA des compteurs serveur suit la touche : « À faire » retombe à 0.
    expect(screen.getByText(/À faire\s*:\s*0/)).toBeInTheDocument()
    expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith(
      { lead: touche().lead }, { suppressErrorToast: true })
    expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledTimes(1)
    expect(toastError).not.toHaveBeenCalled()
  })
})

/* SUIVI-FILTRE + SUIVI-ÉQUIPE (fondateur, 29/10/2026) — cases à cocher par
   statut (filtrage d'ÉCRAN sur les lignes servies, compteurs serveur intacts,
   choix dans l'URL) et la vue d'équipe réservée aux rôles responsable/admin. */
describe('RelancesSuiviPage — filtre par statut et vue d\'équipe (29/10/2026)', () => {
  function SondeUrl() {
    const { search } = useLocation()
    return <output data-testid="sonde-url">{search}</output>
  }
  function monterAvecUrl(url = '/crm/relances') {
    return render(
      <MemoryRouter initialEntries={[url]}>
        <RelancesSuiviPage />
        <SondeUrl />
      </MemoryRouter>,
    )
  }
  const lignesVisibles = () => screen.queryAllByTestId('relance-etape-row')
  const caseStatut = (name) => screen.getByRole('checkbox', { name })

  it('cocher « Faites » ne garde que les touches faites et écrit ?statut=fait ; les compteurs restent ceux du serveur', async () => {
    monterAvecUrl()
    activerOnglet('7 derniers jours')
    await waitFor(() => expect(lignesVisibles()).toHaveLength(2))
    fireEvent.click(caseStatut('Faites'))
    await waitFor(() => expect(lignesVisibles()).toHaveLength(1))
    expect(screen.getByText(new RegExp(`^Fait · \\d{2}:\\d{2} · ${ETAPES[0].traite_par_nom}$`))).toBeInTheDocument()
    expect(screen.getByTestId('sonde-url').textContent).toBe('?statut=fait')
    // `resume` vient TEL QUEL du serveur, quel que soit le filtre d'écran…
    expect(screen.getByText(/À faire\s*:\s*1/)).toBeInTheDocument()
    expect(screen.getByText(/Faites\s*:\s*1/)).toBeInTheDocument()
    // …et le serveur n'est PAS re-sollicité (montage + onglet = 2 appels).
    expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledTimes(2)

    // Deux cases = l'UNION des lignes, l'URL dans l'ordre des compteurs.
    fireEvent.click(caseStatut('À faire'))
    await waitFor(() => expect(lignesVisibles()).toHaveLength(2))
    expect(screen.getByTestId('sonde-url').textContent).toBe('?statut=a_faire&statut=fait')

    // « Tout afficher » efface le filtre et disparaît.
    fireEvent.click(screen.getByRole('button', { name: 'Tout afficher' }))
    await waitFor(() => expect(screen.getByTestId('sonde-url').textContent).toBe(''))
    expect(lignesVisibles()).toHaveLength(2)
    expect(screen.queryByRole('button', { name: 'Tout afficher' })).not.toBeInTheDocument()
  })

  it('?statut=en_retard dans l\'URL s\'applique au chargement : seule la touche ouverte déjà échue reste', async () => {
    // L'exemple committé est daté d'un autre jour : sa touche « à faire » est
    // donc échue (en retard) ; sa touche « fait » ne l'est pas.
    monterAvecUrl('/crm/relances?statut=en_retard')
    activerOnglet('7 derniers jours')
    await waitFor(() => expect(lignesVisibles()).toHaveLength(1))
    expect(screen.queryByText(/^Fait · /)).not.toBeInTheDocument()
    expect(caseStatut('En retard')).toHaveAttribute('aria-checked', 'true')
    expect(caseStatut('Faites')).toHaveAttribute('aria-checked', 'false')
  })

  it('la vue d\'équipe est absente au rôle normal, présente aux responsables et lue sur le contrat controle_suivi', async () => {
    isAdminOrResponsableMock.mockReturnValue(false)
    mount()
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalled())
    expect(screen.queryByTestId('relances-equipe-panel')).not.toBeInTheDocument()
    expect(crmApi.getControleSuivi).not.toHaveBeenCalled()
    cleanup()

    isAdminOrResponsableMock.mockReturnValue(true)
    mount()
    await waitFor(() => expect(screen.getByTestId('relances-equipe-panel')).toBeInTheDocument())
    // Par défaut « Toute l'équipe » : 14 jours, aucun `owner` (comme la file).
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenCalledWith({ jours: 14 }))
    // Société vide (`exemple_vide`) : le bloc le dit, sans inventer un chiffre.
    await waitFor(() => expect(screen.getByTestId('equipe-vide')).toBeInTheDocument())
  })
})

/* SUIVI-ÉQUIPE — le composant « Vue d'équipe » lui-même
   (`RelancesEquipePanel.jsx`), testé ICI, dans le module de test de l'écran qui
   le porte (AMET84 : aucun fichier de test neuf). Charge utile = l'exemple
   COMMITTÉ du contrat `controle_suivi` (PACT10), jamais un objet retapé à la
   main : si le serveur change de forme, l'exemple change et ces tests cassent
   tout seuls. Le mock `getControleSuivi` est partagé avec les suites de
   l'écran : chaque test le règle, et le rend à la société vide après lui. */
describe('RelancesEquipePanel (SUIVI-ÉQUIPE)', () => {
  const DONNEES_EQUIPE = exempleContrat('crm', 'controle_suivi')
  const PAR_COMMERCIAL = DONNEES_EQUIPE.par_commercial
  // Le sélecteur de période est un `Segmented` (role=radiogroup) : clic sur l'option.
  const choisirPeriode = (name) => fireEvent.click(screen.getByRole('radio', { name }))
  const ligne = (id) => screen.getByTestId(`equipe-ligne-${id}`)

  beforeEach(() => {
    crmApi.getControleSuivi.mockResolvedValue(reponseContrat('crm', 'controle_suivi'))
  })
  afterEach(() => {
    crmApi.getControleSuivi.mockResolvedValue(reponseContrat('crm', 'controle_suivi', 'exemple_vide'))
  })

  it('appelle le contrôle sur 14 jours par défaut sans owner, puis avec la période choisie et le responsable reçu', async () => {
    const { rerender } = render(<RelancesEquipePanel owner="" />)
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenCalledWith({ jours: 14 }))
    choisirPeriode('7 jours')
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenCalledWith({ jours: 7 }))
    rerender(<RelancesEquipePanel owner="7" />)
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenCalledWith({ jours: 7, owner: '7' }))
  })

  it('les quatre tuiles et les barres rendent les chiffres SERVIS, tels quels, dans l\'ordre servi', async () => {
    render(<RelancesEquipePanel owner="" />)
    await waitFor(() => expect(screen.getByTestId('equipe-tuiles')).toBeInTheDocument())
    expect(screen.getByTestId('equipe-tuile-retard'))
      .toHaveTextContent(String(DONNEES_EQUIPE.exceptions.en_retard.total))
    expect(screen.getByTestId('equipe-tuile-a-temps')).toHaveTextContent(/85[,.]7/)
    expect(screen.getByTestId('equipe-tuile-a-temps')).toHaveTextContent(/78[,.]0/)
    expect(screen.getByTestId('equipe-tuile-reportees'))
      .toHaveTextContent(String(DONNEES_EQUIPE.verdict.reportees))
    expect(screen.getByTestId('equipe-tuile-attente'))
      .toHaveTextContent(String(DONNEES_EQUIPE.exceptions.taches_en_attente.total))

    // Une barre par ligne servie, dans l'ordre servi (le serveur trie).
    const lignes = screen.getAllByTestId(/^equipe-ligne-/)
    expect(lignes).toHaveLength(PAR_COMMERCIAL.length)
    expect(lignes.map((l) => within(l).getByRole('button').textContent))
      .toEqual(PAR_COMMERCIAL.map((c) => c.nom))

    // Segments depuis la base : le retard d'abord ; un compteur à 0 n'a pas de segment.
    const premiere = PAR_COMMERCIAL[0]
    const segments = [...lignes[0].querySelectorAll('[data-serie]')].map((s) => s.dataset.serie)
    expect(segments).toEqual(['ouvert', 'en_retard', 'a_temps', 'sautees'].filter((k) => premiere[k]))
    expect(lignes[0]).toHaveTextContent(`${premiere.en_retard_actuel} en retard`)
    expect(lignes[0]).toHaveTextContent(`${premiere.aujourdhui} aujourd'hui`)

    // La légende dit le MOT ; la frise a son tableau équivalent (ChartFrame).
    expect(screen.getByTestId('equipe-legende-commercial')).toHaveTextContent('Toujours en retard')
    expect(screen.getByTestId('equipe-legende-jours')).toHaveTextContent('Ouvertes, pas encore en retard')
    expect(screen.getByText(`Touches dues jour par jour sur ${DONNEES_EQUIPE.periode_jours} jours`))
      .toBeInTheDocument()
  })

  it('cliquer un commercial borne la file à lui ; re-cliquer revient à toute l\'équipe', async () => {
    const onChoisirOwner = vi.fn()
    const premiere = PAR_COMMERCIAL[0]
    const { rerender } = render(<RelancesEquipePanel owner="" onChoisirOwner={onChoisirOwner} />)
    await waitFor(() => expect(ligne(premiere.id)).toBeInTheDocument())
    expect(within(ligne(premiere.id)).getByRole('button')).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(within(ligne(premiere.id)).getByRole('button'))
    expect(onChoisirOwner).toHaveBeenCalledWith(premiere.id)

    rerender(<RelancesEquipePanel owner={String(premiere.id)} onChoisirOwner={onChoisirOwner} />)
    await waitFor(() => expect(within(ligne(premiere.id)).getByRole('button'))
      .toHaveAttribute('aria-pressed', 'true'))
    fireEvent.click(within(ligne(premiere.id)).getByRole('button'))
    expect(onChoisirOwner).toHaveBeenLastCalledWith('')
  })

  it('société vide (`exemple_vide`) : le bloc le dit, aucun chiffre inventé', async () => {
    crmApi.getControleSuivi.mockResolvedValue(reponseContrat('crm', 'controle_suivi', 'exemple_vide'))
    render(<RelancesEquipePanel owner="" />)
    await waitFor(() => expect(screen.getByTestId('equipe-vide')).toBeInTheDocument())
    expect(screen.queryByTestId('equipe-tuiles')).not.toBeInTheDocument()
  })

  it('refus serveur : un message, jamais des barres vides qui mentent', async () => {
    crmApi.getControleSuivi.mockRejectedValue(new Error('500'))
    render(<RelancesEquipePanel owner="" />)
    await waitFor(() => expect(screen.getByText(/Vue d.équipe indisponible/)).toBeInTheDocument())
    expect(screen.queryByTestId('equipe-tuiles')).not.toBeInTheDocument()
  })
})

/* ============================================================================
   SUIVI-RELOAD (02/11/2026) — incident de production. La commerciale ouvrait
   WhatsApp depuis une touche, revenait cocher « Fait », et recevait un
   « problème de connexion » puis un écran SANS aucune suite : elle se
   déconnectait et se reconnectait pour retrouver sa file. Cause relevée dans
   les journaux du serveur : chaque geste — l'ouverture de WhatsApp comprise —
   relisait la PÉRIODE entière (jusqu'à 62 jours, ~1,5 Mo), la relecture
   dépassait le délai d'attente du navigateur pendant que les ouvriers du
   serveur redémarraient, et l'écran remplaçait TOUTE la liste par
   « Indisponible pour le moment. ». Les deux règles qui en sortent sont
   prouvées ici.
   ========================================================================== */
describe('RelancesSuiviPage — SUIVI-RELOAD (geste ciblé, liste jamais vidée)', () => {
  const AUJOURDHUI = () => casaISO(new Date())
  // Une touche WhatsApp À FAIRE d'aujourd'hui : le geste de Meryem.
  const touche = () => ({
    ...ETAPES.find((e) => e.canal === 'whatsapp'),
    id: 782, due_date: AUJOURDHUI(), overdue: false, statut: 'a_faire',
    traite_le: null, traite_par_nom: null, message_ouvert_le: null,
  })
  const MESSAGE = exempleContrat('crm', 'relance_etape_message')

  beforeEach(() => {
    crmApi.getRelanceEtapesSuivi.mockResolvedValue({
      data: {
        results: [touche()],
        resume: { a_faire: 1, en_retard: 0, fait: 0, sautee: 0, annulee: 0 },
      },
    })
    crmApi.getRelanceEtapeMessage.mockResolvedValue({ data: MESSAGE })
    vi.spyOn(window, 'open').mockReturnValue(null)
  })

  it('ouvrir WhatsApp ne relit AUCUNE liste : la touche à jour vient de la réponse du POST', async () => {
    const ouverte = { ...touche(), message_ouvert_le: new Date().toISOString() }
    crmApi.whatsappRelanceEtape.mockResolvedValue({ data: { ...MESSAGE, etape: ouverte } })
    mount()
    expect(await screen.findAllByTestId('relance-etape-row')).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: /WhatsApp/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Ouvrir WhatsApp' }))
    await waitFor(() => expect(crmApi.whatsappRelanceEtape).toHaveBeenCalledWith(782))
    expect(window.open).toHaveBeenCalledWith(MESSAGE.wa_url, '_blank', 'noopener')

    // La touche a été FUSIONNÉE depuis la réponse : le panneau « Fait » dit
    // désormais que le message a été ouvert (RLC3) au lieu de demander la
    // confirmation « message non ouvert ».
    fireEvent.click(await screen.findByRole('button', { name: /Fait/ }))
    expect(await screen.findByTestId('rappel-message-ouvert'))
      .toHaveTextContent(/Message ouvert à \d{2}:\d{2} depuis l/)
    expect(screen.queryByTestId('confirmer-sans-ouverture')).not.toBeInTheDocument()

    // Le geste le plus fréquent de la journée ne coûte AUCUNE lecture de
    // liste : ni la période (le montage seulement), ni même le lead.
    expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledTimes(1)
    expect(crmApi.getRelanceEtapesDues).not.toHaveBeenCalled()
  })

  it('un rafraîchissement en échec GARDE les touches affichées, le dit, et « Réessayer » relit la période', async () => {
    crmApi.whatsappRelanceEtape.mockResolvedValue({ data: { ...MESSAGE } })
    crmApi.getRelanceEtapesDues.mockRejectedValue(new Error('Network Error'))
    mount()
    expect(await screen.findAllByTestId('relance-etape-row')).toHaveLength(1)

    // Réponse sans `etape` : on retombe sur la relecture du LEAD… qui échoue.
    fireEvent.click(screen.getByRole('button', { name: /WhatsApp/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Ouvrir WhatsApp' }))
    await waitFor(() => expect(crmApi.getRelanceEtapesDues).toHaveBeenCalled())

    // L'écran ne se vide PAS (c'était le « plus aucune suite » de l'incident)
    // et ne ment pas : il dit que la liste n'est pas rafraîchie.
    expect(await screen.findByTestId('suivi-pas-a-jour'))
      .toHaveTextContent(/Liste non rafraîchie/)
    expect(screen.getAllByTestId('relance-etape-row')).toHaveLength(1)
    expect(screen.queryByText('Indisponible pour le moment.')).not.toBeInTheDocument()

    // « Réessayer » relit la période EN PLACE ; au succès, l'avis disparaît.
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(crmApi.getRelanceEtapesSuivi).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByTestId('suivi-pas-a-jour')).not.toBeInTheDocument())
    expect(screen.getAllByTestId('relance-etape-row')).toHaveLength(1)
  })

  it('un chargement de NOUVELLE fenêtre en échec reste une erreur : « Indisponible pour le moment. »', async () => {
    // Les lignes de l'ancienne fenêtre ne répondent pas à la question posée
    // par le nouvel onglet : là, et là seulement, l'écran dit qu'il n'a rien.
    crmApi.getRelanceEtapesSuivi.mockRejectedValue(new Error('Network Error'))
    mount()
    expect(await screen.findByText('Indisponible pour le moment.')).toBeInTheDocument()
    expect(screen.queryByTestId('suivi-pas-a-jour')).not.toBeInTheDocument()
  })
})

/* AMET84 — ces tests de `features/crm/relances/fusionSuivi.js` vivent dans le
   module de test de l’écran qui la consomme (la garde `check_test_placement`
   refuse un fichier de test NEUF hors tâche cochée).
   La fusion du « Suivi des relances », en FONCTION PURE : c'est elle qui tient
   la promesse « les compteurs restent ceux du serveur » sans relire la
   période. Testée sans écran (aucun rendu à dérouler pour une règle de
   calcul). */
describe('fusionnerLignes (SUIVI-RELOAD)', () => {
  const BORNES = { date_debut: '2026-09-01', date_fin: '2026-09-30' }
  const TODAY = '2026-09-15'
  const ligne = (p) => ({ due_at: null, ordre: 1, statut: 'a_faire', ...p })
  const donnees = (results, resume) => ({ count: results.length, results, resume })

  it('une touche faite quitte « à faire » (et « en retard ») et entre dans « faites »', () => {
    const avant = donnees(
      [ligne({ id: 1, lead: 7, due_date: '2026-09-10' })],
      { a_faire: 4, en_retard: 2, fait: 1, sautee: 0, annulee: 0 },
    )
    const apres = fusionnerLignes(
      avant, new Set([1]),
      [ligne({ id: 1, lead: 7, due_date: '2026-09-10', statut: 'fait' })],
      BORNES, TODAY,
    )
    // La ligne était ouverte et échue (10/09 < 15/09) : les deux seaux baissent.
    expect(apres.resume).toEqual({ a_faire: 3, en_retard: 1, fait: 2, sautee: 0, annulee: 0 })
    expect(apres.results.map((e) => e.statut)).toEqual(['fait'])
    // Jamais de doublon d'id, et le compte suit la liste.
    expect(apres.count).toBe(1)
  })

  it('une touche reportée HORS de la fenêtre servie quitte la liste ET les compteurs', () => {
    const avant = donnees(
      [ligne({ id: 1, lead: 7, due_date: '2026-09-10' })],
      { a_faire: 1, en_retard: 1, fait: 0, sautee: 0, annulee: 0 },
    )
    const apres = fusionnerLignes(
      avant, new Set([1]),
      [ligne({ id: 1, lead: 7, due_date: '2026-10-20' })],
      BORNES, TODAY,
    )
    expect(apres.results).toEqual([])
    expect(apres.resume).toEqual({ a_faire: 0, en_retard: 0, fait: 0, sautee: 0, annulee: 0 })
  })

  it('une touche qui NAÎT se range à sa place (jour, puis heure NULLS LAST, puis ordre)', () => {
    const avant = donnees(
      [
        ligne({ id: 1, lead: 7, due_date: '2026-09-10', due_at: '2026-09-10T08:00:00Z' }),
        ligne({ id: 2, lead: 9, due_date: '2026-09-12' }),
      ],
      { a_faire: 2, en_retard: 2, fait: 0, sautee: 0, annulee: 0 },
    )
    const apres = fusionnerLignes(
      avant, new Set([1]),
      [
        ligne({ id: 1, lead: 7, due_date: '2026-09-10', due_at: '2026-09-10T08:00:00Z', statut: 'fait' }),
        ligne({ id: 3, lead: 7, due_date: '2026-09-10', due_at: '2026-09-10T07:00:00Z' }),
      ],
      BORNES, TODAY,
    )
    // 3 (07:00) avant 1 (08:00), tous deux avant la journée du 12.
    expect(apres.results.map((e) => e.id)).toEqual([3, 1, 2])
    expect(apres.resume).toEqual({ a_faire: 2, en_retard: 2, fait: 1, sautee: 0, annulee: 0 })
  })

  it('un compteur ne descend jamais sous zéro, et une liste absente est rendue telle quelle', () => {
    const avant = donnees(
      [ligne({ id: 1, lead: 7, due_date: '2026-09-10' })],
      { a_faire: 0, en_retard: 0, fait: 0, sautee: 0, annulee: 0 },
    )
    const apres = fusionnerLignes(avant, new Set([1]), [], BORNES, TODAY)
    expect(apres.resume.a_faire).toBe(0)
    expect(fusionnerLignes(null, new Set([1]), [], BORNES, TODAY)).toBeNull()
  })
})
