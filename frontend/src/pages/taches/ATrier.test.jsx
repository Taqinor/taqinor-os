import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'
import ATrier from './ATrier'

const api = vi.hoisted(() => ({
  listerToutesLesTaches: vi.fn(), lireAujourdhui: vi.fn(), traiterLot: vi.fn(), convertirActivites: vi.fn(),
  listerTousLesProjets: vi.fn(), creerProjet: vi.fn(), annulerGeste: vi.fn(), saisieRapide: vi.fn(), listerSuggestions: vi.fn(),
}))
vi.mock('../../api/tachesApi', async (importOriginal) => ({ ...(await importOriginal()), ...api }))
// R2-024 — la pastille d'À trier : ses deux gestes (corriger tout de suite, relire du serveur) sont observés, pas lus d'un faux serveur
const ordre = vi.hoisted(() => [])
const badge = vi.hoisted(() => ({ chargerBadgeTaches: vi.fn(), ajusterBadgeATrier: vi.fn() }))
vi.mock('../../features/taches/useBadgeTaches', async (importOriginal) => ({ ...(await importOriginal()), ...badge }))

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

function Position() {
  return <output data-testid="position">{useLocation().search}</output>
}
const monter = () => render(
  <MemoryRouter initialEntries={['/taches/a-trier']}><ATrier aujourdhui={AUJOURD} /><Position /></MemoryRouter>,
)
const RESERVE = [
  { ...ligne(51, 'Comparer deux devis'), projet: { id: 9, nom: 'Salon Solaire Expo', couleur: 'indigo', priorite: 3 } },
  ligne(52, 'Changer de banque'),
].map((t) => ({ ...t, quelque_jour: true }))
const lignes = () => within(screen.getAllByRole('list')[0]).getAllByRole('listitem')
const appelsBoite = () => api.listerToutesLesTaches.mock.calls.filter(([f]) => f.vue === 'boite').length

beforeEach(() => {
  ordre.length = 0
  badge.ajusterBadgeATrier.mockImplementation((delta) => { ordre.push(`ajuster:${delta}`) })
  badge.chargerBadgeTaches.mockImplementation((options) => { ordre.push(`relire:${options?.force ? 'force' : 'cache'}`); return Promise.resolve() })
  api.listerToutesLesTaches.mockImplementation(({ vue }) => Promise.resolve(vue === 'quelque_jour' ? RESERVE : TACHES))
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

  it('passe visuelle n° 24 — bandeau : la phrase seule sur sa ligne, « Tout convertir · Voir » en liens dessous', async () => {
    api.lireAujourdhui.mockResolvedValue({ data: { ...aujourdhui, a_trier: { ...aujourdhui.a_trier, a_convertir: 1 } } })
    monter()
    const bandeau = await screen.findByRole('region', { name: 'Activités personnelles' })
    const phrase = within(bandeau).getByText('1 à-faire personnel dans Activités')
    expect(phrase).toHaveClass('bandeau-titre')
    for (const nom of ['Tout convertir', 'Voir']) {
      const geste = within(bandeau).getByRole('button', { name: nom })
      expect(geste).toHaveClass('geste')
      expect(phrase.contains(geste)).toBe(false)
    }
  })

  it('passe visuelle n° 22 — une ligne = case ronde, titre, mentions servies, gestes en liens (pas en pilules)', async () => {
    const user = userEvent.setup()
    api.listerToutesLesTaches.mockImplementation(({ vue }) => Promise.resolve(
      vue === 'quelque_jour' ? [] : [{ ...TACHES[0], source: 'suggestion' }, TACHES[1]],
    ))
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

  it('passe visuelle n° 21 — sous-titre « {n} sans jour ni projet », suit la boîte', async () => {
    const user = userEvent.setup()
    monter()
    expect(await screen.findByText('3 sans jour ni projet')).toBeInTheDocument()
    await user.click(within(lignes()[0]).getByRole('button', { name: 'Demain' }))
    expect(await screen.findByText('2 sans jour ni projet')).toBeInTheDocument()
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

  it('Couture r2 — Projet… › Créer « … » refusé : le message est dit par l\'écran, sans toast global en double', async () => {
    api.creerProjet.mockRejectedValue(Object.assign(new Error('http'), { response: { status: 400, data: { nom: ['Ce nom est trop long.'] } } }))
    const user = userEvent.setup()
    monter()
    await screen.findByText('Appeler Karim')
    await user.click(within(lignes()[0]).getByRole('button', { name: 'Projet…' }))
    await user.type(await screen.findByRole('combobox', { name: 'Chercher un projet' }), 'Chantier')
    await user.click(await screen.findByRole('option', { name: 'Créer « Chantier »' }))
    await waitFor(() => expect(api.creerProjet).toHaveBeenCalledWith({ nom: 'Chantier' }, { erreurSousLeChamp: true }))
    expect(api.traiterLot).not.toHaveBeenCalled()
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
    expect(appelsBoite()).toBe(2)
  })

  it('passe visuelle n° 23 — « En réserve {n} » est replié EN BAS (vue quelque_jour), jamais un commutateur en tête', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Appeler Karim')
    expect(screen.queryByRole('radiogroup', { name: 'Liste' })).toBeNull()
    expect(api.listerToutesLesTaches).toHaveBeenCalledWith({ vue: 'quelque_jour' })
    const replie = await screen.findByRole('button', { name: /^En réserve\s*2/ })
    expect(replie).toHaveAttribute('aria-expanded', 'false')
    // replié : sous la liste de la boîte, ses lignes cachées
    expect(screen.getByRole('region', { name: 'À trier' }).compareDocumentPosition(replie) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.queryByText('Comparer deux devis')).toBeNull()
    await user.click(replie)
    const reserve = screen.getByRole('region', { name: 'En réserve' })
    expect(within(reserve).getAllByRole('listitem')).toHaveLength(2)
    expect(within(within(reserve).getAllByRole('listitem')[0]).getByText('Salon Solaire Expo').closest('[data-p]')).toHaveAttribute('data-p', 'indigo')
    // une ligne de la boîte mise en réserve la rejoint aussitôt
    await user.click(within(lignes()[0]).getByRole('button', { name: /Autres gestes pour/ }))
    await user.click(await screen.findByRole('menuitem', { name: 'En réserve' }))
    expect(within(reserve).getAllByRole('listitem')).toHaveLength(3)
    expect(screen.getByRole('button', { name: /^En réserve\s*3/ })).toBeInTheDocument()
  })

  it('« En réserve » vide une fois déplié : « Rien en réserve »', async () => {
    const user = userEvent.setup()
    api.listerToutesLesTaches.mockImplementation(({ vue }) => Promise.resolve(vue === 'quelque_jour' ? RESERVE.slice(0, 1) : TACHES))
    monter()
    await user.click(await screen.findByRole('button', { name: /^En réserve\s*1/ }))
    const reserve = screen.getByRole('region', { name: 'En réserve' })
    await user.click(within(reserve).getByRole('button', { name: 'Demain' }))
    expect(await screen.findByText('Rien en réserve')).toBeInTheDocument()
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

describe('R2-024 — la pastille rouge d\'À trier suit les gestes tout de suite', () => {
  it('un geste corrige la pastille AVANT le serveur (−1) puis la relit du serveur (relecture forcée)', async () => {
    const user = userEvent.setup()
    api.traiterLot.mockImplementation((corps) => { ordre.push('lot'); return Promise.resolve({ data: { appliquees: corps.ids, refusees: [], geste_id: lot.geste_id } }) })
    monter()
    await screen.findByText('Appeler Karim')
    await user.click(within(lignes()[0]).getByRole('button', { name: 'Demain' }))
    await waitFor(() => expect(ordre).toEqual(['ajuster:-1', 'lot', 'relire:force']))
  })

  it('une ligne refusée ou un échec réseau : la pastille revient (+1) puis se relit', async () => {
    const user = userEvent.setup()
    api.traiterLot.mockImplementation(() => { ordre.push('lot'); return Promise.reject(Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' })) })
    monter()
    await screen.findByText('Appeler Karim')
    await user.click(within(lignes()[0]).getByRole('button', { name: 'Aujourd\'hui' }))
    await waitFor(() => expect(ordre).toEqual(['ajuster:-1', 'lot', 'ajuster:1', 'relire:force']))
  })

  it('Annuler remet la ligne : la pastille se relit encore', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Timbres')
    await user.click(within(lignes()[1]).getByRole('button', { name: 'Demain' }))
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    ordre.length = 0
    await user.click(within(toast).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(ordre).toEqual(['ajuster:1', 'relire:force']))
  })

  it('une ligne de la réserve n\'est pas dans la pastille : aucun ajustement, mais une relecture', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(await screen.findByRole('button', { name: /^En réserve\s*2/ }))
    const reserve = screen.getByRole('region', { name: 'En réserve' })
    await user.click(within(within(reserve).getAllByRole('listitem')[0]).getByRole('button', { name: 'Demain' }))
    await waitFor(() => expect(ordre).toContain('relire:force'))
    expect(ordre).not.toContain('ajuster:-1')
  })

  it('Tout ranger (un lot de n cartes) : −n tout de suite', async () => {
    const user = userEvent.setup()
    const cinq = [41, 42, 43, 44, 45].map((id) => ligne(id, `Tâche ${id}`))
    api.listerToutesLesTaches.mockResolvedValue(cinq)
    api.saisieRapide.mockResolvedValue({ data: { lignes: [
      { tache_id: 41, champs: {}, projet_suggere: { id: 3, nom: 'Ventes' } },
      { tache_id: 42, champs: {}, projet_suggere: { id: 3, nom: 'Ventes' } },
    ] } })
    api.traiterLot.mockResolvedValue({ data: { appliquees: [41, 42], refusees: [], geste_id: 80 } })
    monter()
    await screen.findByText('Tâche 41')
    await user.click(screen.getByRole('button', { name: 'Plus d\'actions' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Ranger avec le Copilote' }))
    expect(await screen.findAllByText('Projet suggéré : Ventes')).toHaveLength(2)
    ordre.length = 0
    await user.click(screen.getByRole('button', { name: 'Tout ranger' }))
    await waitFor(() => expect(ordre).toEqual(['ajuster:-2', 'relire:force']))
  })
})

describe('R2-036 — j / k parcourent les cartes d\'À trier, Entrée ouvre la fiche', () => {
  it('j j Entrée : la 2e carte s\'ouvre (sa fiche), sans rien cocher ni faire disparaître', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Appeler Karim')
    await user.keyboard('jj')
    expect(within(lignes()[1]).getByRole('button', { name: 'Timbres' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByTestId('position')).toHaveTextContent('?tache=42')
    expect(api.traiterLot).not.toHaveBeenCalled()
    expect(lignes()).toHaveLength(3)
  })

  it('couture r2 — `e` ouvre la fiche curseur dans le titre, `h` sur l\'heure (comme l\'aide le dit)', async () => {
    const user = userEvent.setup()
    const premier = monter()
    await screen.findByText('Appeler Karim')
    await user.keyboard('jj')
    await user.keyboard('e')
    expect(screen.getByTestId('position')).toHaveTextContent('?tache=42&focus=titre')
    premier.unmount()
    monter()
    await screen.findByText('Appeler Karim')
    await act(async () => { within(lignes()[0]).getByRole('button', { name: 'Appeler Karim' }).focus() })
    await user.keyboard('h')
    expect(screen.getByTestId('position')).toHaveTextContent('?tache=41&focus=heure')
  })

  it('k remonte, jamais au-delà de la première ; Espace ne fait disparaître aucune carte', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Appeler Karim')
    await user.keyboard('jjjjk')
    expect(within(lignes()[1]).getByRole('button', { name: 'Timbres' })).toHaveFocus()
    await user.keyboard('kkk')
    expect(within(lignes()[0]).getByRole('button', { name: 'Appeler Karim' })).toHaveFocus()
    await user.keyboard(' ')
    expect(api.traiterLot).not.toHaveBeenCalled()
    expect(lignes()).toHaveLength(3)
  })

  it('d choisit un jour pour la carte focalisée ; la frappe dans un champ n\'est jamais un raccourci', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByText('Appeler Karim')
    await user.keyboard('j')
    await user.keyboard('d')
    expect(await screen.findByRole('radio', { name: /Demain/ })).toBeInTheDocument()
  })
})

