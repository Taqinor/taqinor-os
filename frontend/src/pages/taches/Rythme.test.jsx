import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'
import {
  annulerGeste, lireAujourdhui, lireRythme, modifierReglages, poserMode, poserPreference, repondreProposition,
} from '../../api/tachesApi'
import Rythme from './Rythme'

vi.mock('../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  lireRythme: vi.fn(),
  lireAujourdhui: vi.fn(),
  poserMode: vi.fn(),
  poserPreference: vi.fn(),
  repondreProposition: vi.fn(),
  modifierReglages: vi.fn(),
  annulerGeste: vi.fn(),
}))

/* TCH107 — Mon rythme rend `rythme.json` : aujourd'hui, objectif et source, proposition
   (« Monter à 6 » · « Pas maintenant »), constats, modes, Mes jours ; chaque geste adopte le RYTHME
   rendu par le serveur ; une erreur s'affiche sous le champ fautif. Le jour est injecté. */

// le jour courant n'est JAMAIS dans la série servie (jours déjà évalués seulement) : un jour APRÈS celui de l'échantillon
const AUJOURDHUI = '2026-11-17'
const journee = () => structuredClone(exempleContrat('taches', 'aujourdhui'))
const rythme = () => structuredClone(exempleContrat('taches', 'rythme'))
const reponse = (donnees) => Promise.resolve({ data: donnees })
const erreur400 = (corps) => Object.assign(new Error('400'), { response: { status: 400, data: corps } })

function monter() {
  return render(<MemoryRouter><Rythme aujourdhui={AUJOURDHUI} /></MemoryRouter>)
}

beforeEach(() => {
  lireRythme.mockImplementation(() => reponse(rythme()))
  lireAujourdhui.mockImplementation(() => reponse(journee()))
})
afterEach(() => { vi.clearAllMocks(); reinitialiserGestes() })

describe('TCH107 — Mon rythme', () => {
  it('sans la progression du jour (lecture en échec), la ligne « aujourd\'hui » manque et tout le reste s\'affiche', async () => {
    lireAujourdhui.mockRejectedValue(new Error('Network Error'))
    monter()
    expect(await screen.findByText('Objectif du jour : 5 (accepté)')).toBeInTheDocument()
    expect(screen.queryByText("sur 5 aujourd'hui")).toBeNull()
  })

  it('rend aujourd\'hui, l\'objectif et sa source, la proposition, les constats et le repère', async () => {
    monter()
    // la ligne du jour vient de la progression d'Aujourd'hui (aujourdhui.json : 1 faite, essentiel 0/1), pas de la série
    const ligne = await screen.findByText("sur 5 aujourd'hui")
    expect(ligne.parentElement).toHaveTextContent("1 sur 5 aujourd'hui")
    expect(screen.getByText('essentiel 0/1')).toBeInTheDocument()
    expect(screen.getByText('Objectif du jour : 5 (accepté)')).toBeInTheDocument()
    expect(screen.getByText('Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Monter à 6' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pas maintenant' })).toBeInTheDocument()
    expect(screen.getByText('Vendredi : 3,1 tâches en moyenne, 5,2 les autres jours.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'En faire un jour court (un de moins) ?' })).toBeInTheDocument()
    expect(screen.getByText('Repère : 6 de tes journées sur 10 sont à 5,5 tâches ou moins (sur 9 jours).')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Tâches faites, jour par jour travaillé : 5\./ })).toBeInTheDocument()
    expect(screen.getByText('5 faites ou plus 7 jours sur 10')).toBeInTheDocument()
  })

  it('passe visuelle n° 44 — pas de section « Objectif du jour » en plus : Moins · Plus · Choisir sous la ligne de l\'objectif', async () => {
    monter()
    const ligne = (await screen.findByText('Objectif du jour : 5 (accepté)')).closest('p')
    expect(screen.queryByRole('heading', { name: 'Objectif du jour' })).toBeNull()
    const groupe = screen.getByRole('group', { name: "Changer d'objectif" })
    expect(within(groupe).getAllByRole('button').map((b) => b.textContent)).toEqual(['Moins', 'Plus', 'Choisir un nombre (1 à 12)'])
    expect(ligne.nextElementSibling).toBe(groupe)
  })

  it('les trois modes : « En faire plus » est coché, et choisir « Garder ce rythme » envoie le mode', async () => {
    const tenir = { ...rythme(), mode: 'tenir', objectif: { nb: 5, source: 'calcule', mode: 'tenir', zone: [4, 6] }, geste_id: 92 }
    poserMode.mockResolvedValue({ data: tenir })
    monter()
    const groupe = await screen.findByRole('radiogroup', { name: 'Mode du rythme' })
    expect(within(groupe).getAllByRole('radio')).toHaveLength(3)
    expect(within(groupe).getByRole('radio', { name: /En faire plus/ })).toBeChecked()
    await userEvent.click(within(groupe).getByRole('radio', { name: /Garder ce rythme/ }))
    expect(poserMode).toHaveBeenCalledWith({ mode: 'tenir' })
    expect(await screen.findByText('Ton rythme : environ 5 tâches (4 à 6)')).toBeInTheDocument()
    expect(within(await screen.findByRole('group', { name: 'Geste effectué' })).getByText(/Garder ce rythme : environ 5 tâches par jour \(4 à 6\)/)).toBeInTheDocument()
  })

  it('« Monter à 6 » répond oui, adopte le RYTHME rendu et propose Annuler', async () => {
    repondreProposition.mockResolvedValue({ data: exempleContrat('taches', 'proposition_repondue') })
    annulerGeste.mockResolvedValue({ data: {} })
    monter()
    await userEvent.click(await screen.findByRole('button', { name: 'Monter à 6' }))
    expect(repondreProposition).toHaveBeenCalledWith(41, { reponse: 'oui' })
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    expect(within(toast).getByText("Objectif du jour : 5, dès aujourd'hui.")).toBeInTheDocument()
    await userEvent.click(within(toast).getByRole('button', { name: 'Annuler' }))
    expect(annulerGeste).toHaveBeenCalledWith(91)
    await waitFor(() => expect(lireRythme).toHaveBeenCalledTimes(2))
  })

  it('« Pas maintenant » répond sans toast ; une proposition expirée le dit sous la carte', async () => {
    repondreProposition.mockRejectedValueOnce(Object.assign(new Error('409'), {
      response: { status: 409, data: { detail: 'x', code: 'proposition_expiree' } },
    }))
    monter()
    await userEvent.click(await screen.findByRole('button', { name: 'Pas maintenant' }))
    expect(repondreProposition).toHaveBeenCalledWith(41, { reponse: 'pas_maintenant' })
    expect(await screen.findByRole('alert')).toHaveTextContent('Cette proposition a expiré.')
    expect(screen.queryByRole('group', { name: 'Geste effectué' })).toBeNull()
  })

  it('un constat se répond par sa question', async () => {
    repondreProposition.mockResolvedValue({ data: exempleContrat('taches', 'proposition_repondue') })
    monter()
    await userEvent.click(await screen.findByRole('button', { name: 'En faire un jour court (un de moins) ?' }))
    expect(repondreProposition).toHaveBeenCalledWith(44, { reponse: 'oui' })
  })

  it('Plus envoie le sens ; « Choisir un nombre » refuse 13 sous le champ sans appeler le serveur', async () => {
    poserMode.mockResolvedValue({ data: { ...rythme(), objectif: { nb: 6, source: 'dit', mode: 'pousser', zone: null } } })
    monter()
    await userEvent.click(await screen.findByRole('button', { name: 'Plus' }))
    expect(poserMode).toHaveBeenCalledWith({ mode: 'pousser', sens: 'plus' })
    expect((await screen.findAllByText("Objectif du jour : 6 (un de plus), dès aujourd'hui.")).length).toBeGreaterThan(0)
    await userEvent.click(screen.getByRole('button', { name: 'Choisir un nombre (1 à 12)' }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Objectif du jour' }), '13')
    await userEvent.click(screen.getByRole('button', { name: 'OK' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Entre 1 et 12.')
    expect(poserMode).toHaveBeenCalledTimes(1)
  })

  it('Mes jours : un jour travaillé décoché envoie le masque ; le dernier jour est gardé', async () => {
    poserPreference.mockResolvedValue({ data: rythme() })
    monter()
    await userEvent.click(await screen.findByRole('button', { name: /Mes jours/ }))
    const travailles = screen.getByRole('group', { name: 'Jours travaillés' })
    await userEvent.click(within(travailles).getByRole('button', { name: 'dimanche' }))
    expect(poserPreference).toHaveBeenCalledWith({ cle: 'jours_travailles', valeur: '1111110' })
  })

  it('Mes jours : l\'erreur du serveur s\'affiche sous le temps disponible, la saisie reste', async () => {
    poserPreference.mockRejectedValue(erreur400({ valeur: ['Entre 30 et 720 minutes.'] }))
    monter()
    await userEvent.click(await screen.findByRole('button', { name: /Mes jours/ }))
    const champ = screen.getByRole('textbox', { name: 'Temps disponible par jour' })
    await userEvent.type(champ, '100')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Entre 30 et 720 minutes.')).toBeInTheDocument()
    expect(champ).toHaveValue('100')
  })

  it('Mes jours : un congé dont la fin précède le début est refusé sans appel', async () => {
    monter()
    await userEvent.click(await screen.findByRole('button', { name: /Mes jours/ }))
    const [du, au] = [...document.querySelectorAll('input[type="date"]')]
    await userEvent.type(du, '2026-12-10')
    await userEvent.type(au, '2026-12-01')
    await userEvent.click(screen.getByRole('button', { name: 'Ajouter' }))
    expect(await screen.findByText('La date de fin précède la date de début.')).toBeInTheDocument()
    expect(poserPreference).not.toHaveBeenCalled()
  })

  it('Comprendre mon rythme : éteindre envoie le réglage et annonce la phrase', async () => {
    modifierReglages.mockResolvedValue({ data: {} })
    monter()
    await userEvent.click(await screen.findByRole('button', { name: /Comprendre mon rythme/ }))
    await userEvent.click(screen.getByRole('switch', { name: 'Comprendre mon rythme' }))
    expect(modifierReglages).toHaveBeenCalledWith({ comprendre_mon_rythme: false })
    expect(await screen.findByText("C'est éteint : plus rien n'est calculé ni gardé sur ton rythme.")).toBeInTheDocument()
  })

  it('« Parler de mon rythme » ouvre le Copilote avec la question', async () => {
    const ouvert = vi.fn()
    window.addEventListener('taqinor:assistant:ouvrir', ouvert)
    monter()
    await userEvent.click(await screen.findByRole('button', { name: 'Parler de mon rythme' }))
    window.removeEventListener('taqinor:assistant:ouvrir', ouvert)
    expect(ouvert).toHaveBeenCalledTimes(1)
    expect(ouvert.mock.calls[0][0].detail.question).toBe('Parler de mon rythme')
  })

  it('avant 10 jours : la phrase d\'attente remplace le graphique', async () => {
    const neuf = { ...rythme(), objectif: { nb: 5, source: 'defaut', mode: 'pousser', zone: null }, proposition: null, constats: [] }
    lireRythme.mockImplementation(() => reponse(neuf))
    monter()
    expect(await screen.findByText("1 jour sur 10 : il m'en faut 10 pour comprendre ton rythme.")).toBeInTheDocument()
    expect(screen.getByText('Objectif du jour : 5 (valeur par défaut, pas encore calculée sur toi)')).toBeInTheDocument()
    expect(screen.getByText("Rien de remarqué pour l'instant.")).toBeInTheDocument()
    expect(screen.queryByRole('img')).toBeNull()
  })

  it('un échec de lecture dit « Pas à jour » et Réessayer relit', async () => {
    lireRythme.mockRejectedValueOnce(new Error('Network Error'))
    monter()
    expect(await screen.findByText('Pas à jour')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByText('Objectif du jour : 5 (accepté)')).toBeInTheDocument()
    expect(screen.queryByText('Pas à jour')).toBeNull()
  })
})
