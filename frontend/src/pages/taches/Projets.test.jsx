import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { ReactReduxContext } from 'react-redux'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'

vi.mock('../../api/tachesApi', async (original) => ({
  ...(await original()),
  listerProjets: vi.fn(),
  creerProjet: vi.fn(),
  modifierProjet: vi.fn(),
  reordonnerProjet: vi.fn(),
  supprimerProjet: vi.fn(),
  restaurerProjet: vi.fn(),
  trierProjetsParPriorite: vi.fn(),
}))

const api = await import('../../api/tachesApi')
const { default: Projets } = await import('./Projets')

/* TCH88 — l'écran rend `projets_liste.json` : puce de priorité touchable, avancement, « à surveiller »,
   constat, En pause replié, Nouveau projet → Planifier le projet. Chaque geste met la liste à jour
   sur place (jamais de relecture) et un échec remet la ligne comme avant. */

const projets = () => structuredClone(exempleContrat('taches', 'projets_liste'))
const vide = { data: { count: 0, next: null, previous: null, results: [] } }

function Lieu() {
  const l = useLocation()
  return <div data-testid="lieu">{`${l.pathname}${l.search}`}</div>
}

const monter = () => render(
  <MemoryRouter initialEntries={['/taches/projets']}>
    <Routes>
      <Route path="/taches/projets" element={<Projets />} />
      <Route path="*" element={<Lieu />} />
    </Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  reinitialiserGestes()
  api.listerProjets.mockImplementation(async (params) => (params?.statut === 'en_pause' ? vide : reponseContrat('taches', 'projets_liste')))
})
afterEach(() => { vi.clearAllMocks(); reinitialiserGestes() })

describe('TCH88 — Projets : rendu du contrat', () => {
  it('la ligne porte nom, avancement, échéance, « à surveiller » et la puce de priorité', async () => {
    monter()
    const ligne = (await screen.findByRole('button', { name: 'Ventes' })).closest('.ligne')
    expect(ligne).toHaveAttribute('data-p', 'vert')
    expect(within(ligne).getByText('12 sur 20')).toBeInTheDocument()
    expect(ligne.querySelector('.meta')).toHaveTextContent('échéance')
    expect(within(ligne).getByText('à surveiller')).toBeInTheDocument()
    expect(within(ligne).getByRole('button', { name: 'Priorité haute, changer' })).toHaveTextContent('Haute')
    expect(within(ligne).getByRole('img', { name: '12 sur 20' })).toBeInTheDocument()
    expect(within(ligne).queryByText('À planifier')).toBeNull()
  })

  it('passe visuelle n° 39 — puce de priorité : trois barres croissantes allumées depuis la gauche (« Moyenne » : 2 sur 3)', async () => {
    const liste = projets()
    liste.results[0].priorite = 2
    api.listerProjets.mockImplementation(async (params) => (params?.statut === 'en_pause' ? vide : { data: liste }))
    monter()
    const ligne = (await screen.findByRole('button', { name: 'Ventes' })).closest('.ligne')
    const puce = within(ligne).getByRole('button', { name: 'Priorité moyenne, changer' })
    expect([...puce.querySelectorAll('.barres i')].map((i) => i.className)).toEqual(['', '', 'eteinte'])
  })

  it('passe visuelle n° 40 — une seule forme de date de projet : jour, quantième ET mois', async () => {
    const { echeanceProjet, jourProjet } = await import('../../features/taches/projets/LigneProjet')
    const auj = '2026-11-24'
    expect(echeanceProjet('2026-12-04', auj)).toEqual({ texte: 'échéance ven. 4 déc.', ton: 'fort' })
    expect(echeanceProjet('2026-11-27', auj).texte).toBe('échéance ven. 27 nov.')
    expect(echeanceProjet('2027-01-15', auj).texte).toBe('échéance ven. 15 janv.')
    expect(echeanceProjet('2027-12-03', auj).texte).toBe('échéance ven. 3 déc. 2027')
    expect(echeanceProjet('2026-11-24', auj)).toEqual({ texte: "échéance aujourd'hui", ton: 'alerte' })
    expect(echeanceProjet('2026-11-20', auj)).toEqual({ texte: 'échéance dépassée le 20/11', ton: 'alerte' })
    expect(jourProjet('2026-11-25', auj)).toBe('demain')
    expect(jourProjet('2026-12-03', auj)).toBe('jeu. 3 déc.')
  })

  it('le constat est calculé du serveur : « 7 projets actifs, 3 ont avancé ces 7 jours »', async () => {
    monter()
    expect(await screen.findByText('7 projets actifs, 3 ont avancé ces 7 jours')).toBeInTheDocument()
  })

  it('« À planifier » et « Projet de la semaine » s\'affichent quand le serveur les pose', async () => {
    const liste = projets()
    liste.results[0].a_planifier = true
    liste.results[0].focus_semaine = true
    api.listerProjets.mockImplementation(async (params) => (params?.statut === 'en_pause' ? vide : { data: liste }))
    monter()
    expect(await screen.findByText('À planifier')).toBeInTheDocument()
    expect(screen.getByText('Projet de la semaine')).toBeInTheDocument()
  })

  it('aucun projet : « Aucun projet » et « Coller mes listes » ouvre la saisie', async () => {
    api.listerProjets.mockResolvedValue(vide)
    const ouvrir = vi.fn()
    window.addEventListener('taqinor:taches:saisir', ouvrir)
    monter()
    expect(await screen.findByText('Aucun projet')).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Coller mes listes' }))
    window.removeEventListener('taqinor:taches:saisir', ouvrir)
    expect(ouvrir).toHaveBeenCalled()
  })

  it('l\'échec du premier chargement est dit, sans liste inventée', async () => {
    api.listerProjets.mockRejectedValue(new Error('Network Error'))
    monter()
    expect(await screen.findByRole('alert')).toHaveTextContent('Connexion perdue')
  })
})

describe('TCH88 — Projets : gestes sur place', () => {
  it('la puce de priorité change la priorité, sans relire la liste', async () => {
    const mis = { ...projets().results[0], priorite: 1, lock_version: 5 }
    api.modifierProjet.mockResolvedValue({ data: mis })
    monter()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Priorité haute, changer' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Basse' }))
    expect(api.modifierProjet).toHaveBeenCalledWith(3, { priorite: 1, lock_version: 4 })
    expect(await screen.findByRole('button', { name: 'Priorité basse, changer' })).toBeInTheDocument()
    expect(api.listerProjets).toHaveBeenCalledTimes(2) // le chargement initial seulement (actif + en pause)
  })

  it('un échec remet la priorité d\'avant et le dit', async () => {
    api.modifierProjet.mockRejectedValue(new Error('Network Error'))
    monter()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Priorité haute, changer' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Moyenne' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Connexion perdue')
    expect(screen.getByRole('button', { name: 'Priorité haute, changer' })).toBeInTheDocument()
  })

  it('Mettre en pause range le projet sous « En pause (1) » avec Annuler', async () => {
    const enPause = { ...projets().results[0], statut: 'en_pause', lock_version: 5 }
    api.modifierProjet.mockResolvedValueOnce({ data: enPause })
    monter()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Actions pour « Ventes »' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Mettre en pause' }))
    expect(api.modifierProjet).toHaveBeenCalledWith(3, { statut: 'en_pause', lock_version: 4 })
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Ventes' })).toBeNull())
    expect(screen.getByRole('button', { name: /En pause \(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('« Ventes » en pause')

    api.modifierProjet.mockResolvedValueOnce({ data: { ...enPause, statut: 'actif', lock_version: 6 } })
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(await screen.findByRole('button', { name: 'Ventes' })).toBeInTheDocument()
    expect(api.modifierProjet).toHaveBeenLastCalledWith(3, { statut: 'actif', lock_version: 5 })
  })

  it('Trier par priorité (⋯) appelle le tri une fois', async () => {
    api.trierProjetsParPriorite.mockResolvedValue({ data: {} })
    monter()
    const user = userEvent.setup()
    await screen.findByRole('button', { name: 'Ventes' })
    await user.click(screen.getByRole('button', { name: "Plus d'actions" }))
    await user.click(await screen.findByRole('menuitem', { name: 'Trier par priorité' }))
    expect(api.trierProjetsParPriorite).toHaveBeenCalledTimes(1)
  })
})

describe('R2-060 — Projets : « Mettre en haut » atteignable au doigt', () => {
  it('l\'appui long (500 ms, doigt immobile) sur une ligne ouvre le menu ⋯ ; Mettre en haut y est', async () => {
    api.reordonnerProjet.mockResolvedValue({ data: {} })
    const liste = projets()
    liste.results = [liste.results[0], { ...liste.results[0], id: 8, nom: 'Site web' }]
    api.listerProjets.mockImplementation(async (params) => (params?.statut === 'en_pause' ? vide : { data: liste }))
    monter()
    const titre = await screen.findByRole('button', { name: 'Site web' })
    const ligne = titre.closest('.ligne')
    vi.useFakeTimers()
    fireEvent.pointerDown(ligne, { pointerType: 'touch', clientX: 20, clientY: 20 })
    act(() => { vi.advanceTimersByTime(520) })
    vi.useRealTimers()
    const menu = await screen.findByRole('menu')
    expect(within(menu).getByRole('menuitem', { name: 'Mettre en haut' })).toBeInTheDocument()
    // l'appui long ne doit pas ouvrir le projet au relâchement
    fireEvent.pointerUp(ligne, { pointerType: 'touch' })
    fireEvent.click(titre)
    expect(screen.queryByTestId('lieu')).toBeNull()
    await userEvent.setup().click(within(menu).getByRole('menuitem', { name: 'Mettre en haut' }))
    expect(api.reordonnerProjet).toHaveBeenCalledWith(8, { avant_id: 3 })
  })

  it('un appui court ou un doigt qui bouge n\'ouvre pas le menu', async () => {
    monter()
    const ligne = (await screen.findByRole('button', { name: 'Ventes' })).closest('.ligne')
    vi.useFakeTimers()
    fireEvent.pointerDown(ligne, { pointerType: 'touch', clientX: 20, clientY: 20 })
    fireEvent.pointerMove(ligne, { pointerType: 'touch', clientX: 20, clientY: 60 })
    act(() => { vi.advanceTimersByTime(700) })
    vi.useRealTimers()
    expect(screen.queryByRole('menu')).toBeNull()
  })
})

describe('R2-071 — Projets : priorité « Aucune » écrite', () => {
  it('un projet sans priorité porte la pastille « Aucune » (jamais « — »), et le menu offre Aucune', async () => {
    const liste = projets()
    liste.results[0].priorite = 0
    api.listerProjets.mockImplementation(async (params) => (params?.statut === 'en_pause' ? vide : { data: liste }))
    monter()
    const ligne = (await screen.findByRole('button', { name: 'Ventes' })).closest('.ligne')
    const puce = within(ligne).getByRole('button', { name: 'Priorité aucune, changer' })
    expect(puce).toHaveTextContent('Aucune')
    expect(puce).not.toHaveTextContent('—')
    await userEvent.setup().click(puce)
    expect(await screen.findByRole('menuitem', { name: 'Aucune' })).toBeInTheDocument()
  })
})

describe('R2-070 — Projets : jamais « Aucun projet » sans réponse ; hors ligne, la dernière liste lue', () => {
  const connecte = (id) => ({ getState: () => ({ auth: { user: { id, active_company_id: 7 } } }) })
  const monterConnecte = (id = 42) => render(
    <ReactReduxContext.Provider value={{ store: connecte(id) }}>
      <MemoryRouter initialEntries={['/taches/projets']}>
        <Routes><Route path="/taches/projets" element={<Projets />} /><Route path="*" element={<Lieu />} /></Routes>
      </MemoryRouter>
    </ReactReduxContext.Provider>,
  )
  beforeEach(() => { window.localStorage.clear() })
  afterEach(() => { window.localStorage.clear() })

  it('lecture échouée et rien de gardé : l\'erreur est dite, jamais un faux « Aucun projet »', async () => {
    api.listerProjets.mockRejectedValue(new Error('Network Error'))
    monterConnecte()
    expect(await screen.findByRole('alert')).toHaveTextContent('Connexion perdue')
    expect(screen.queryByText('Aucun projet')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Coller mes listes' })).toBeNull()
  })

  it('relu sans réseau : la dernière liste lue du compte s\'affiche, avec son constat', async () => {
    const premier = monterConnecte()
    await screen.findByRole('button', { name: 'Ventes' })
    premier.unmount()
    api.listerProjets.mockRejectedValue(new Error('Network Error'))
    monterConnecte()
    expect(await screen.findByRole('button', { name: 'Ventes' })).toBeInTheDocument()
    expect(screen.getByText('7 projets actifs, 3 ont avancé ces 7 jours')).toBeInTheDocument()
    expect(screen.queryByText('Aucun projet')).toBeNull()
  })

  it('hors ligne, la dernière liste lue est montrée SANS la phrase rouge « Connexion perdue » (la ligne « Hors ligne » de la coquille suffit)', async () => {
    const premier = monterConnecte()
    await screen.findByRole('button', { name: 'Ventes' })
    premier.unmount()
    api.listerProjets.mockRejectedValue(new Error('Network Error'))
    const enLigne = vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    try {
      monterConnecte()
      expect(await screen.findByRole('button', { name: 'Ventes' })).toBeInTheDocument()
      expect(document.querySelector('.entete-date[role="status"]')).toHaveTextContent('Hors ligne')
      expect(screen.queryByRole('alert')).toBeNull()
      expect(screen.queryByText('Aucun projet')).toBeNull()
    } finally {
      enLigne.mockRestore()
    }
  })

  it('la liste gardée par un AUTRE compte n\'est jamais montrée ; la déconnexion vide le cache', async () => {
    const premier = monterConnecte(42)
    await screen.findByRole('button', { name: 'Ventes' })
    premier.unmount()
    api.listerProjets.mockRejectedValue(new Error('Network Error'))
    const autre = monterConnecte(43)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ventes' })).toBeNull()
    autre.unmount()
    const { viderCacheProjets } = await import('../../features/taches/horsligne/cacheProjets')
    expect(viderCacheProjets()).toBeGreaterThan(0)
    // plus aucune entrée de CACHE DES PROJETS (d'autres clés du module, ex. « messages sans délai », ne sont pas à vider)
    expect(Object.keys(window.localStorage).filter((c) => c.startsWith('taches:projets:'))).toEqual([])
  })

  it('R2-085 — la page Projets ne porte plus la date du jour en sous-titre', async () => {
    monter()
    await screen.findByRole('button', { name: 'Ventes' })
    expect(document.querySelector('.entete-date')).toBeNull()
  })
})

describe('TCH92 — Projets : Supprimer depuis la ligne', () => {
  it('⋯ → Supprimer ouvre le dialogue ; confirmer retire la ligne avec Annuler', async () => {
    api.supprimerProjet.mockResolvedValue({ data: {} })
    monter()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Actions pour « Ventes »' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Supprimer' }))
    const dialogue = await screen.findByRole('dialog', { name: 'Supprimer le projet' })
    await user.click(within(dialogue).getByRole('button', { name: 'Supprimer' }))
    expect(api.supprimerProjet).toHaveBeenCalledWith(3)
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Ventes' })).toBeNull())
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent(/^« Ventes » et ses \d+ tâches? supprimés/) // textes.md §2.15
  })
})

describe('TCH88 — Projets : Nouveau projet et navigation', () => {
  it('« Créer » ouvre aussitôt Planifier le projet (réponse `projet_ecrit` : { projet, … })', async () => {
    const ecrit = exempleContrat('taches', 'projet_ecrit')
    api.creerProjet.mockResolvedValue({ data: { ...ecrit, projet: { ...ecrit.projet, id: 9, nom: 'Salon', statut: 'actif' } } })
    monter()
    const user = userEvent.setup()
    await screen.findByRole('button', { name: 'Ventes' })
    await user.click(screen.getAllByRole('button', { name: 'Nouveau projet' })[0])
    const feuille = await screen.findByRole('dialog', { name: 'Nouveau projet' })
    await user.type(within(feuille).getByLabelText('Nom du projet'), 'Salon')
    await user.click(within(feuille).getByRole('button', { name: 'Créer' }))
    expect(api.creerProjet).toHaveBeenCalledWith({ nom: 'Salon' })
    expect(await screen.findByTestId('lieu')).toHaveTextContent('/taches/projets/9?planifier=1')
  })

  it('un nom déjà pris s\'affiche sous le champ', async () => {
    api.creerProjet.mockRejectedValue({ response: { status: 400, data: { nom: ['Un projet « Ventes » existe déjà.'] } } })
    monter()
    const user = userEvent.setup()
    await screen.findByRole('button', { name: 'Ventes' })
    await user.click(screen.getAllByRole('button', { name: 'Nouveau projet' })[0])
    const feuille = await screen.findByRole('dialog', { name: 'Nouveau projet' })
    await user.type(within(feuille).getByLabelText('Nom du projet'), 'Ventes')
    await user.click(within(feuille).getByRole('button', { name: 'Créer' }))
    const champ = within(feuille).getByLabelText('Nom du projet')
    expect(await within(feuille).findByRole('alert')).toHaveTextContent('Un projet « Ventes » existe déjà.')
    expect(champ).toHaveAttribute('aria-invalid', 'true')
  })

  it('ouvrir une ligne mène à /taches/projets/:id', async () => {
    monter()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Ventes' }))
    expect(await screen.findByTestId('lieu')).toHaveTextContent('/taches/projets/3')
  })
})

describe('Raccord F2 — Projets : « Nouveau projet » de la palette', () => {
  it('`?nouveau=1` ouvre la feuille « Nouveau projet » ; la fermer retire le paramètre', async () => {
    render(
      <MemoryRouter initialEntries={['/taches/projets?nouveau=1']}>
        <Routes>
          <Route path="/taches/projets" element={<><Projets /><Lieu /></>} />
        </Routes>
      </MemoryRouter>,
    )
    const feuille = await screen.findByRole('dialog', { name: 'Nouveau projet' })
    expect(within(feuille).getByLabelText('Nom du projet')).toBeInTheDocument()
    await userEvent.setup().click(within(feuille).getByRole('button', { name: 'Fermer' }))
    await waitFor(() => expect(screen.getByTestId('lieu')).toHaveTextContent(/^\/taches\/projets$/))
  })
})

describe('Raccord F2 — Projets : chargement', () => {
  it('rien pendant 1 s, puis le squelette « Chargement » ; il part dès que la liste arrive', async () => {
    vi.useFakeTimers()
    const attentes = []
    const finir = (r) => attentes.forEach((ok) => ok(r))
    api.listerProjets.mockImplementation(() => new Promise((ok) => { attentes.push(ok) }))
    monter()
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    expect(screen.getByRole('status', { name: 'Chargement' })).toBeInTheDocument()
    await act(async () => { finir(reponseContrat('taches', 'projets_liste')); await vi.advanceTimersByTimeAsync(0) })
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
    vi.useRealTimers()
  })
})

describe('R2-067 — Projets au bureau (≥ 1024 px) : /taches/projets ouvre le premier projet', () => {
  const ancienne = window.matchMedia
  const media = (bureau) => vi.fn().mockImplementation((requete) => ({
    matches: bureau, media: requete, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  }))
  afterEach(() => { window.matchMedia = ancienne })

  it('le premier projet actif s\'ouvre à droite (l\'adresse devient /taches/projets/<id>) ; la palette garde sa requête', async () => {
    window.matchMedia = media(true)
    render(
      <MemoryRouter initialEntries={['/taches/projets?nouveau=1']}>
        <Routes>
          <Route path="/taches/projets" element={<Projets />} />
          <Route path="/taches/projets/:id" element={<Lieu />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByTestId('lieu')).toHaveTextContent('/taches/projets/3?nouveau=1')
  })

  it('aucun projet : l\'état vide reste (rien à ouvrir)', async () => {
    window.matchMedia = media(true)
    api.listerProjets.mockResolvedValue(vide)
    monter()
    expect(await screen.findByText('Aucun projet')).toBeInTheDocument()
    expect(screen.queryByTestId('lieu')).toBeNull()
  })

  it('< 1024 px : la liste reste la liste (puis le projet)', async () => {
    window.matchMedia = media(false)
    monter()
    expect(await screen.findByRole('button', { name: 'Ventes' })).toBeInTheDocument()
    expect(screen.queryByTestId('lieu')).toBeNull()
  })
})
