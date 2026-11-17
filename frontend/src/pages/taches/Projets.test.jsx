import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
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
