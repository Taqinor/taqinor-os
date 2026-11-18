import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'
import ATrier from './ATrier'

const api = vi.hoisted(() => ({
  listerToutesLesTaches: vi.fn(), lireAujourdhui: vi.fn(), traiterLot: vi.fn(), convertirActivites: vi.fn(),
  listerTousLesProjets: vi.fn(), creerProjet: vi.fn(), annulerGeste: vi.fn(), saisieRapide: vi.fn(), listerSuggestions: vi.fn(),
}))
vi.mock('../../api/tachesApi', async (importOriginal) => ({ ...(await importOriginal()), ...api }))

/* TCH86 — À trier : bandeau à convertir, Aujourd'hui · Demain · Projet… · ⋯, Trier une par une,
   En réserve, Tout ranger. Réponses = `lot.json`, `convertir_activite.json` (et le reste du contrat). */

const modele = exempleContrat('taches', 'tache')
const lot = exempleContrat('taches', 'lot')
const conversion = exempleContrat('taches', 'convertir_activite')
const aujourdhui = exempleContrat('taches', 'aujourdhui')
const projet = exempleContrat('taches', 'projets_liste').results[0]
const AUJOURD = '2026-11-17'

const ligne = (id, titre) => ({ ...modele, id, titre, projet: null, jour_prevu: null, heure_debut: null, essentielle: false })
const TACHES = [ligne(41, 'Appeler Karim'), ligne(42, 'Timbres'), ligne(43, 'Ranger le bureau')]
const erreurHttp = (data, status) => Object.assign(new Error('http'), { response: { status, data } })

const monter = () => render(
  <MemoryRouter initialEntries={['/taches/a-trier']}><ATrier aujourdhui={AUJOURD} /></MemoryRouter>,
)
const lignes = () => within(screen.getByRole('list')).getAllByRole('listitem')

beforeEach(() => {
  api.listerToutesLesTaches.mockResolvedValue(TACHES)
  api.lireAujourdhui.mockResolvedValue({ data: aujourdhui })
  api.traiterLot.mockImplementation((corps) => Promise.resolve({ data: { appliquees: corps.ids, refusees: [], geste_id: lot.geste_id } }))
  api.convertirActivites.mockResolvedValue({ data: conversion })
  api.listerTousLesProjets.mockResolvedValue([projet])
  api.annulerGeste.mockResolvedValue({ data: {} })
  api.listerSuggestions.mockResolvedValue({ data: { results: [] } }) // TCH167 : « Suggéré par l'ERP » (testé dans atrier/Suggestions.test.jsx)
})
afterEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
})

describe('TCH86 — écran À trier', () => {
  it('liste les tâches de la boîte et le bandeau « à-faire personnels dans Activités »', async () => {
    monter()
    expect(await screen.findByText('Appeler Karim')).toBeInTheDocument()
    expect(api.listerToutesLesTaches).toHaveBeenCalledWith({ vue: 'boite' })
    expect(lignes()).toHaveLength(3)
    const bandeau = screen.getByRole('region', { name: 'Activités personnelles' })
    expect(bandeau).toHaveTextContent('7 à-faire personnels dans Activités')
    expect(within(bandeau).getByRole('button', { name: 'Tout convertir' })).toBeInTheDocument()
    expect(within(bandeau).getByRole('button', { name: 'Voir' })).toBeInTheDocument()
  })

  it('passe visuelle n° 22 — une ligne = case ronde, titre, mentions servies, gestes en liens (pas en pilules)', async () => {
    const user = userEvent.setup()
    api.listerToutesLesTaches.mockResolvedValue([{ ...TACHES[0], source: 'suggestion' }, TACHES[1]])
    monter()
    await screen.findByText('Timbres')
    const [premiere, seconde] = lignes()
    expect(premiere).toHaveClass('ligne', 'tri')
    expect(within(premiere).getByText("Suggéré par l'ERP")).toBeInTheDocument()
    expect(within(premiere).getByText(modele.lien.libelle)).toBeInTheDocument()
    expect(within(premiere).getByText('échéance jeu. 19')).toBeInTheDocument()
    expect(within(seconde).queryByText("Suggéré par l'ERP")).toBeNull()
    for (const nom of ['Aujourd\'hui', 'Demain', 'Projet…']) {
      const geste = within(premiere).getByRole('button', { name: nom })
      expect(geste).toHaveClass('geste')
      expect(geste).not.toHaveClass('puce')
    }
    await user.click(within(seconde).getByRole('checkbox', { name: 'Marquer « Timbres » comme faite' }))
    expect(api.traiterLot).toHaveBeenLastCalledWith({ ids: [42], action: 'terminer', valeurs: {} })
    expect(screen.queryByText('Timbres')).toBeNull()
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Faite')
  })

  it('Aujourd\'hui : la ligne part tout de suite, le lot est écrit, « Annuler » la ramène à sa place', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Timbres')
    await user.click(within(lignes()[1]).getByRole('button', { name: 'Aujourd\'hui' }))
    expect(screen.queryByText('Timbres')).toBeNull()
    expect(api.traiterLot).toHaveBeenCalledWith({ ids: [42], action: 'planifier', valeurs: { jour_prevu: AUJOURD } })
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    expect(toast).toHaveTextContent('Mise à aujourd\'hui')
    await user.click(within(toast).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.annulerGeste).toHaveBeenCalledWith(lot.geste_id))
    await waitFor(() => expect(lignes().map((l) => l.textContent.slice(0, 7))).toEqual(['Appeler', 'Timbres', 'Ranger ']))
  })

  it('Demain, En réserve, Supprimer : un seul chemin, `taches/lot/`', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Appeler Karim')
    await user.click(within(lignes()[0]).getByRole('button', { name: 'Demain' }))
    expect(api.traiterLot).toHaveBeenLastCalledWith({ ids: [41], action: 'planifier', valeurs: { jour_prevu: '2026-11-18' } })
    await user.click(within(lignes()[0]).getByRole('button', { name: /Autres gestes pour/ }))
    await user.click(await screen.findByRole('menuitem', { name: 'En réserve' }))
    expect(api.traiterLot).toHaveBeenLastCalledWith({ ids: [42], action: 'planifier', valeurs: { quelque_jour: true } })
    await user.click(within(lignes()[0]).getByRole('button', { name: /Autres gestes pour/ }))
    await user.click(await screen.findByRole('menuitem', { name: 'Supprimer' }))
    expect(api.traiterLot).toHaveBeenLastCalledWith({ ids: [43], action: 'supprimer', valeurs: {} })
  })

  it('une ligne refusée par le serveur reste dans la liste, avec sa phrase', async () => {
    const user = userEvent.setup()
    api.traiterLot.mockResolvedValue({ data: lot })
    monter()
    await screen.findByText('Timbres')
    await user.click(within(lignes()[1]).getByRole('button', { name: 'Demain' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Cette tâche a changé : elle est restée dans la liste.')
    expect(screen.getByText('Timbres')).toBeInTheDocument()
    expect(lignes()).toHaveLength(3)
  })

  it('sans réseau, la ligne revient et la liste ne se vide pas', async () => {
    const user = userEvent.setup()
    api.traiterLot.mockRejectedValue(Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' }))
    monter()
    await screen.findByText('Appeler Karim')
    await user.click(within(lignes()[0]).getByRole('button', { name: 'Aujourd\'hui' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Possible une fois connecté') // Raccord F2 : la phrase de textes.md §2.1
    expect(lignes()).toHaveLength(3)
  })

  it('Projet… : le sélecteur déplace la tâche dans le projet choisi', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Appeler Karim')
    await user.click(within(lignes()[0]).getByRole('button', { name: 'Projet…' }))
    await user.click(await screen.findByRole('option', { name: 'Ventes' }))
    await waitFor(() => expect(api.traiterLot).toHaveBeenCalledWith({ ids: [41], action: 'deplacer', valeurs: { projet_id: projet.id } }))
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Déplacée dans « Ventes »')
  })

  it('Choisir un jour : le sélecteur « Quand » pose le jour choisi', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Appeler Karim')
    await user.click(within(lignes()[0]).getByRole('button', { name: /Autres gestes pour/ }))
    await user.click(await screen.findByRole('menuitem', { name: 'Choisir un jour' }))
    await user.click(await screen.findByRole('radio', { name: /Demain/ }))
    await waitFor(() => expect(api.traiterLot).toHaveBeenCalledWith({ ids: [41], action: 'planifier', valeurs: { jour_prevu: '2026-11-18' } }))
  })

  it('Tout convertir : une conversion, le refus est dit, le compteur baisse', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(await screen.findByRole('button', { name: 'Tout convertir' }))
    expect(api.convertirActivites).toHaveBeenCalledWith({ toutes: true })
    expect(await screen.findByText('Assigné à un collègue : reste dans Activités.')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Activités personnelles' })).toHaveTextContent('6 à-faire personnels')
    expect(api.listerToutesLesTaches).toHaveBeenCalledTimes(2)
  })

  it('« En réserve » lit la vue quelque_jour ; vide : « Rien en réserve »', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Appeler Karim')
    api.listerToutesLesTaches.mockResolvedValue([])
    await user.click(screen.getByRole('radio', { name: 'En réserve' }))
    expect(await screen.findByText('Rien en réserve')).toBeInTheDocument()
    expect(api.listerToutesLesTaches).toHaveBeenLastCalledWith({ vue: 'quelque_jour' })
  })

  it('boîte vide : « Rien à trier » et « Voir mes projets »', async () => {
    api.listerToutesLesTaches.mockResolvedValue([])
    monter()
    expect(await screen.findByText('Rien à trier')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Voir mes projets' })).toBeInTheDocument()
  })

  it('une lecture en échec le dit, sans fausse boîte vide', async () => {
    api.listerToutesLesTaches.mockRejectedValue(erreurHttp({ detail: 'Erreur du serveur.' }, 500))
    monter()
    await screen.findByRole('alert')
    expect(screen.queryByText('Rien à trier')).toBeNull()
  })

  it('Trier une par une : une carte à la fois, les mêmes gestes, puis « Tout est trié »', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Appeler Karim')
    await user.click(screen.getByRole('button', { name: 'Plus d\'actions' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Trier une par une' }))
    const carte = await screen.findByRole('group', { name: 'Trier : Appeler Karim' })
    await user.click(within(carte).getByRole('button', { name: 'Demain' }))
    expect(api.traiterLot).toHaveBeenLastCalledWith({ ids: [41], action: 'planifier', valeurs: { jour_prevu: '2026-11-18' } })
    const suivante = await screen.findByRole('group', { name: 'Trier : Timbres' })
    await user.click(within(suivante).getByRole('button', { name: 'Suivant' }))
    expect(api.traiterLot).toHaveBeenCalledTimes(1)
    const derniere = await screen.findByRole('group', { name: 'Trier : Ranger le bureau' })
    await user.click(within(derniere).getByRole('button', { name: 'En réserve' }))
    expect(await screen.findByText('Tout est trié')).toBeInTheDocument()
  })

  it('Ranger avec le Copilote (≥ 5 lignes) puis « Tout ranger » : un lot, rangées / non rangées dites', async () => {
    const user = userEvent.setup()
    const cinq = [41, 42, 43, 44, 45].map((id) => ligne(id, `Tâche ${id}`))
    api.listerToutesLesTaches.mockResolvedValue(cinq)
    api.saisieRapide.mockResolvedValue({ data: { lignes: [
      { tache_id: 41, champs: {}, projet_suggere: { id: 3, nom: 'Ventes' } },
      { tache_id: 42, champs: {}, projet_suggere: null },
    ] } })
    api.traiterLot.mockResolvedValue({ data: { appliquees: [41], refusees: [], geste_id: 80 } })
    monter()
    await screen.findByText('Tâche 41')
    await user.click(screen.getByRole('button', { name: 'Plus d\'actions' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Ranger avec le Copilote' }))
    expect(api.saisieRapide).toHaveBeenCalledWith({ ids: [41, 42, 43, 44, 45], apercu: true }, { cle: null })
    expect(await screen.findByText('Projet suggéré : Ventes')).toBeInTheDocument()
    expect(screen.getAllByText('Non rangée')).toHaveLength(4)
    await user.click(screen.getByRole('button', { name: 'Tout ranger' }))
    await waitFor(() => expect(api.traiterLot).toHaveBeenCalledWith({ ids: [41], action: 'deplacer', valeurs: { par_tache: { 41: { projet_id: 3 } } } }))
    expect(screen.queryByText('Tâche 41')).toBeNull()
    expect(screen.getByText('Tâche 42')).toBeInTheDocument()
  })

  it('« Ranger avec le Copilote » n\'est proposé qu\'à partir de 5 lignes', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Appeler Karim')
    await user.click(screen.getByRole('button', { name: 'Plus d\'actions' }))
    expect(await screen.findByRole('menuitem', { name: 'Trier une par une' })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'Ranger avec le Copilote' })).toBeNull()
  })
})
