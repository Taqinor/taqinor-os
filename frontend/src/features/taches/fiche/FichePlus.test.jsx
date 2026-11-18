import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { ZoneAnnonces } from '../coquille/CoquilleTaches'
import { reinitialiserGestes } from '../lib/gestes'
import Fiche from './Fiche'

const api = vi.hoisted(() => ({
  lireTache: vi.fn(), modifierTache: vi.fn(), poserRappel: vi.fn(), modifierReglages: vi.fn(), annulerGeste: vi.fn(),
  supprimerTache: vi.fn(), restaurerTache: vi.fn(), trancherTache: vi.fn(), attendreTache: vi.fn(), creerTache: vi.fn(),
  modifierRecurrence: vi.fn(), sauterTache: vi.fn(), retirerRappel: vi.fn(), rechercher: vi.fn(), recevoirTache: vi.fn(),
}))
vi.mock('../../../api/tachesApi', async (importOriginal) => ({ ...(await importOriginal()), ...api }))

/* TCH85 — Fiche → Plus : rappel (+ la question du titre qui écrit `PATCH reglages/`), répéter, durée,
   en attente de…, jalon, lié à, confidentielle, sous-tâches, abandonner, supprimer (dialogue nommant).
   Réponses = échantillons du contrat. */

const tache = exempleContrat('taches', 'tache')
const ecrite = exempleContrat('taches', 'tache_ecrite')
const AUJOURDHUI = '2026-11-17'
const erreurHttp = (data, status) => Object.assign(new Error('http'), { response: { status, data } })

const monter = (props = {}) => {
  const onFermer = vi.fn()
  render(<div className="tch"><Fiche id={20} aujourdhui={AUJOURDHUI} onFermer={onFermer} {...props} /><ZoneAnnonces /></div>)
  return { onFermer }
}
const ouvrirPlus = async (user) => {
  await screen.findByRole('textbox', { name: 'Titre' })
  await user.click(screen.getByRole('button', { name: 'Plus' }))
}

beforeEach(() => {
  api.lireTache.mockResolvedValue({ data: tache })
  api.modifierTache.mockResolvedValue({ data: ecrite })
  api.poserRappel.mockResolvedValue({ data: ecrite })
  api.modifierReglages.mockResolvedValue({ data: {} })
  api.annulerGeste.mockResolvedValue({ data: {} })
  api.supprimerTache.mockResolvedValue({ data: {} })
  api.restaurerTache.mockResolvedValue({ data: {} })
  api.trancherTache.mockResolvedValue({ data: { geste_id: 5 } })
  api.attendreTache.mockResolvedValue({ data: {} })
  api.creerTache.mockResolvedValue({ data: {} })
  api.modifierRecurrence.mockResolvedValue({ data: {} })
  api.sauterTache.mockResolvedValue({ data: {} })
})
afterEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
})

describe('TCH85 — fiche → Plus', () => {
  it('F4 revue #17 — l\'ordre des lignes est celui de la référence (textes.md, « Plus »)', async () => {
    const user = userEvent.setup()
    api.lireTache.mockResolvedValue({ data: { ...tache, lien: { etat: 'ok', libelle: 'Devis D-2026-0042', url: '/ventes/devis/42' } } })
    monter()
    await ouvrirPlus(user)
    const plus = document.querySelector('.fiche-plus')
    const texte = plus.textContent
    const place = (mot) => texte.indexOf(mot)
    // Rappel · Répéter · Étiquettes · Durée · En attente de… · Jalon · Lié à · Confidentielle · Sous-tâches
    const ordre = ['Rappel', 'Répéter', 'Étiquettes', 'Durée', 'En attente de', 'Jalon', 'Lié à', 'Confidentielle']
    const places = ordre.map(place)
    expect(places.every((i) => i >= 0)).toBe(true)
    expect([...places].sort((x, y) => x - y)).toEqual(places)
  })

  it('rappel : posé sur l\'échéance ; la question du titre (1er rappel) écrit PATCH reglages/', async () => {
    const user = userEvent.setup()
    api.poserRappel.mockResolvedValue({ data: { ...ecrite, question_titres: true, rappel: { jour: '2026-11-19', heure: '09:00' } } })
    monter()
    await ouvrirPlus(user)
    await user.click(screen.getByRole('button', { name: 'Poser le rappel' }))
    await waitFor(() => expect(api.poserRappel).toHaveBeenCalledWith(20, { ancre: 'echeance', decalage_jours: 0, heure: '09:00' }))
    const question = await screen.findByRole('group', { name: "Question sur l'écran verrouillé" })
    expect(question).toHaveTextContent('Montrer le titre sur l\'écran verrouillé ?')
    expect(question).toHaveTextContent('Sans réponse, l\'écran verrouillé n\'affiche que des nombres.')
    await user.click(within(question).getByRole('button', { name: 'Oui' }))
    await waitFor(() => expect(api.modifierReglages).toHaveBeenCalledWith({ titres_notifications: true }))
    expect(screen.queryByRole('group', { name: "Question sur l'écran verrouillé" })).toBeNull()
  })

  it('« Non » à la question écrit aussi le réglage', async () => {
    const user = userEvent.setup()
    api.poserRappel.mockResolvedValue({ data: { ...ecrite, question_titres: true } })
    monter()
    await ouvrirPlus(user)
    await user.click(screen.getByRole('radio', { name: 'La veille' }))
    await user.click(screen.getByRole('button', { name: 'Poser le rappel' }))
    await waitFor(() => expect(api.poserRappel).toHaveBeenCalledWith(20, { ancre: 'echeance', decalage_jours: -1, heure: '09:00' }))
    await user.click(await screen.findByRole('button', { name: 'Non' }))
    await waitFor(() => expect(api.modifierReglages).toHaveBeenCalledWith({ titres_notifications: false }))
  })

  it('rouvrir le volet montre les mêmes valeurs (durée, jalon, confidentielle, lien, sous-tâches)', async () => {
    const user = userEvent.setup()
    monter()
    await ouvrirPlus(user)
    const verifier = () => {
      expect(screen.getByRole('spinbutton')).toHaveValue(60)
      expect(screen.getByRole('switch', { name: 'Jalon' })).toHaveAttribute('aria-checked', 'false')
      expect(screen.getByRole('switch', { name: 'Confidentielle' })).toHaveAttribute('aria-checked', 'false')
      expect(screen.getByRole('link', { name: 'Lié à : DEV-2026-11-0042' })).toHaveAttribute('href', '/ventes/devis?devis=512')
      expect(screen.getByText('Relire les quantités')).toBeInTheDocument()
    }
    verifier()
    await user.click(screen.getByRole('button', { name: 'Plus' }))
    expect(screen.queryByRole('switch', { name: 'Jalon' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Plus' }))
    verifier()
  })

  it('durée : enregistrée avec le lock_version ; l\'erreur « Entre 5 et 960 minutes. » est sous le champ', async () => {
    const user = userEvent.setup()
    monter()
    await ouvrirPlus(user)
    const champ = screen.getByRole('spinbutton')
    await user.clear(champ)
    await user.type(champ, '90')
    await user.tab()
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledWith(20, { estimation_minutes: 90, lock_version: 4 }))

    api.modifierTache.mockRejectedValueOnce(erreurHttp({ estimation_minutes: ['Entre 5 et 960 minutes.'] }, 400))
    await user.clear(champ)
    await user.type(champ, '2')
    await user.tab()
    expect(await screen.findByText('Entre 5 et 960 minutes.')).toBeInTheDocument()
    expect(champ).toHaveValue(2)
  })

  it('jalon et confidentielle s\'écrivent chacun par PATCH', async () => {
    const user = userEvent.setup()
    monter()
    await ouvrirPlus(user)
    await user.click(screen.getByRole('switch', { name: 'Jalon' }))
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledWith(20, { jalon: true, lock_version: 4 }))
    await user.click(screen.getByRole('switch', { name: 'Confidentielle' }))
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledWith(20, { confidentiel: true, lock_version: 4 }))
  })

  it('répéter : « chaque mardi » (jour de la tâche) crée la règle', async () => {
    const user = userEvent.setup()
    monter()
    await ouvrirPlus(user)
    await user.click(screen.getByRole('radio', { name: 'chaque mardi' }))
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledTimes(1))
    expect(api.modifierTache).toHaveBeenCalledWith(20, expect.objectContaining({
      lock_version: 4,
      recurrence: expect.objectContaining({ frequence: 'hebdo', jours_semaine: '0100000', mode: 'calendrier', date_debut: '2026-11-17' }),
    }))
  })

  it('répéter, règle existante : libellé du serveur, Sauter cette fois · Arrêter de répéter', async () => {
    const user = userEvent.setup()
    api.lireTache.mockResolvedValue({ data: {
      ...tache,
      recurrente: true,
      recurrence: { id: 9, frequence: 'hebdo', intervalle: 1, jours_semaine: '0100000', jour_du_mois: null, rang_dans_mois: null, mode: 'calendrier', date_debut: '2026-11-17', date_fin: null, actif: true, libelle: 'chaque mardi' },
    } })
    monter()
    await ouvrirPlus(user)
    expect(screen.getByText('chaque mardi', { selector: 'p' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Arrêter de répéter' }))
    await waitFor(() => expect(api.modifierRecurrence).toHaveBeenCalledWith(9, { actif: false }))
    await user.click(screen.getByRole('button', { name: 'Sauter cette fois' }))
    await waitFor(() => expect(api.sauterTache).toHaveBeenCalledWith(20))
  })

  it('en attente de quelqu\'un : « De qui ou de quoi ? » est écrit à la sortie du champ', async () => {
    const user = userEvent.setup()
    monter()
    await ouvrirPlus(user)
    await user.type(screen.getByRole('textbox', { name: 'De qui ou de quoi ?' }), 'Lydec')
    await user.tab()
    await waitFor(() => expect(api.attendreTache).toHaveBeenCalledWith(20, { en_attente_de: 'Lydec' }))
  })

  it('en attente d\'une autre tâche : cherche, choisit, écrit bloquee_par_id', async () => {
    const user = userEvent.setup()
    api.rechercher.mockResolvedValue({ data: { projets: [], taches: [{ ...tache, id: 43, titre: 'Obtenir le plan' }, { ...tache, id: 20 }] } })
    monter()
    await ouvrirPlus(user)
    await user.click(screen.getByRole('radio', { name: 'Une autre tâche' }))
    await user.type(screen.getByRole('searchbox', { name: 'Chercher une tâche' }), 'plan')
    await user.click(await screen.findByRole('button', { name: 'Obtenir le plan' }))
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledWith(20, { bloquee_par_id: 43, lock_version: 4 }))
    expect(screen.queryByRole('button', { name: 'Devis Settat' })).toBeNull()
  })

  it('sous-tâches : « Découper » crée l\'enfant et relit la tâche', async () => {
    const user = userEvent.setup()
    monter()
    await ouvrirPlus(user)
    await user.type(screen.getByRole('textbox', { name: 'Découper' }), 'Faire le devis{Enter}')
    await waitFor(() => expect(api.creerTache).toHaveBeenCalledWith(expect.objectContaining({ titre: 'Faire le devis', parent_id: 20 })))
    await waitFor(() => expect(api.lireTache).toHaveBeenCalledTimes(2))
  })

  it('Abandonner : « Abandonnée · Annuler » et la fiche se ferme', async () => {
    const user = userEvent.setup()
    const { onFermer } = monter()
    await ouvrirPlus(user)
    await user.click(screen.getByRole('button', { name: 'Abandonner' }))
    await waitFor(() => expect(api.trancherTache).toHaveBeenCalledWith(20, { choix: 'abandonner' }))
    expect(onFermer).toHaveBeenCalled()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Abandonnée')
  })

  it('Supprimer : le dialogue NOMME la tâche et ses sous-tâches ; rien n\'est supprimé avant la confirmation', async () => {
    const user = userEvent.setup()
    const { onFermer } = monter()
    await ouvrirPlus(user)
    await user.click(screen.getByRole('button', { name: 'Supprimer' }))
    const dialogue = screen.getByRole('alertdialog', { name: 'Supprimer « Devis Settat »' })
    expect(dialogue).toHaveTextContent('1 sous-tâche sera supprimée aussi.')
    expect(api.supprimerTache).not.toHaveBeenCalled()
    await user.click(within(dialogue).getByRole('button', { name: 'Annuler' }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Supprimer' }))
    await user.click(screen.getByRole('button', { name: 'Supprimer « Devis Settat »' }))
    await waitFor(() => expect(api.supprimerTache).toHaveBeenCalledWith(20))
    expect(onFermer).toHaveBeenCalled()
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    await user.click(within(toast).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.restaurerTache).toHaveBeenCalledWith(20))
  })

  it('Supprimer puis Annuler : le geste rendu par le serveur est défait (A7), jamais `restaurer/`', async () => {
    const user = userEvent.setup()
    api.supprimerTache.mockResolvedValue({ data: { geste_id: 77 } })
    api.annulerGeste.mockResolvedValue({ data: { restaurees: [{ objet: 'tache', id: 20 }], conflits: [], deja: false } })
    monter()
    await ouvrirPlus(user)
    await user.click(screen.getByRole('button', { name: 'Supprimer' }))
    await user.click(screen.getByRole('button', { name: 'Supprimer « Devis Settat »' }))
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    await user.click(within(toast).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.annulerGeste).toHaveBeenCalledWith(77))
    expect(api.restaurerTache).not.toHaveBeenCalled()
  })
})
