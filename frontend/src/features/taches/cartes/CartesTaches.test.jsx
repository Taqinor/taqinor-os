import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const api = (await import('../../../api/axios')).default
const { default: CartesTaches } = await import('./CartesTaches')

/* NOUVEAU FICHIER DE TEST : premier test de ce domaine dans le nouveau module
   (`features/taches/cartes/`). Chaque carte est rendue DIRECTEMENT par `CartesTaches` (sans
   `CarteResultat`) avec l'ÉCHANTILLON COMMITTÉ de la route qui la sert (`exempleContrat`) ; les
   gestes d'écriture sont vérifiés sur l'appel envoyé au serveur et sur ce que l'écran en dit. */

const contrat = (nom) => structuredClone(exempleContrat('taches', nom))
const monter = (cle, donnees) => render(
  <MemoryRouter><CartesTaches carte={{ type: 'resultat', carte: cle, donnees }} /></MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  api.post.mockResolvedValue({ data: { geste_id: 5 } })
  api.patch.mockResolvedValue({ data: { geste_id: 6 } })
  api.delete.mockResolvedValue({ data: {} })
})

describe('TCH117 — cartes Tâches du Copilote (1/2)', () => {
  it('plan_propose : « Garder ces 2 » poste le mode express puis dit « 2 gardées » avec Annuler', async () => {
    const donnees = contrat('journee_proposition')
    monter('plan_propose', donnees)
    const carte = screen.getByRole('group', { name: "Proposé pour aujourd'hui" })
    expect(within(carte).getByText('2 · objectif 5')).toBeInTheDocument()
    expect(within(carte).getByText('Déclaration TVA')).toBeInTheDocument()
    expect(within(carte).getByText('échéance jeu. 19')).toBeInTheDocument()
    await userEvent.click(within(carte).getByRole('button', { name: 'Garder ces 2' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    const [url, corps] = api.post.mock.calls[0]
    expect(url).toBe('/taches/journee/planifier/')
    expect(corps).toMatchObject({
      jour: '2026-11-17', mode: 'express', lignes: [{ type: 'tache', id: 21 }, { type: 'tache', id: 30 }],
    })
    expect(await within(carte).findByText(/2 gardées/)).toBeInTheDocument()
    await userEvent.click(within(carte).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.post).toHaveBeenLastCalledWith('/taches/gestes/5/annuler/', {}))
  })

  it('plan_propose : une erreur du serveur s’affiche sous le geste, la liste reste', async () => {
    api.post.mockRejectedValueOnce({ response: { status: 400, data: { error: 'x', essentielles: ['3 au plus.'] } } })
    monter('plan_propose', contrat('journee_proposition'))
    await userEvent.click(screen.getByRole('button', { name: 'Garder ces 2' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Déclaration TVA')).toBeInTheDocument()
  })

  it('ma_journee : lignes de la journée, cocher termine la tâche, report groupé au prochain jour travaillé', async () => {
    const donnees = contrat('aujourdhui')
    monter('ma_journee', donnees)
    const carte = screen.getByRole('group', { name: 'Ma journée' })
    expect(within(carte).getByText('Devis Settat')).toBeInTheDocument()
    expect(within(carte).getByText('1 sur 5')).toBeInTheDocument()
    await userEvent.click(within(carte).getByRole('checkbox', { name: /Devis Settat/ }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/taches/taches/20/terminer/', expect.objectContaining({ lock_version: 4 }),
    ))
    const nb = [...donnees.essentiel, ...donnees.journee].filter((it) => it.type === 'tache').length
    await userEvent.click(within(carte).getByRole('button', { name: `Tout au prochain jour travaillé (${nb})` }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/taches/taches/lot/',
      expect.objectContaining({ action: 'planifier', valeurs: { jour_prevu: donnees.prochain_jour_ouvre } }),
      expect.anything(),
    ))
    expect(within(carte).getAllByRole('link', { name: 'Ouvrir' })[0]).toHaveAttribute('href', '/taches/aujourdhui?tache=20')
  })

  it('liste_taches : projets et tâches, chaque « Ouvrir » mène à sa fiche', () => {
    monter('liste_taches', contrat('recherche'))
    const carte = screen.getByRole('group', { name: 'Tes tâches' })
    const liens = within(carte).getAllByRole('link', { name: 'Ouvrir' })
    expect(liens.map((l) => l.getAttribute('href'))).toEqual(['/taches/projets/3', '/taches/aujourdhui?tache=20'])
  })

  it('tache (écho) : « Renommer » écrit le nouveau titre avec le lock_version ; « Laisser » n’écrit rien', async () => {
    monter('tache', contrat('tache_changement'))
    const carte = screen.getByRole('group', { name: 'Devis Settat' })
    expect(within(carte).getByText('Devis Settat → Devis Settat — relance')).toBeInTheDocument()
    await userEvent.click(within(carte).getByRole('button', { name: 'Renommer' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith(
      '/taches/taches/20/', { titre: 'Devis Settat — relance', lock_version: 4 },
    ))
    expect(await within(carte).findByText(/Renommée/)).toBeInTheDocument()
  })

  it('tache (écho) : « Laisser » ne touche pas au serveur', async () => {
    monter('tache', contrat('tache_changement'))
    await userEvent.click(screen.getByRole('button', { name: 'Laisser' }))
    expect(api.patch).not.toHaveBeenCalled()
    expect(screen.getByText('Laissée comme elle est.')).toBeInTheDocument()
  })

  it('tache (écriture) : la tâche écrite et « Modifiée · Annuler » défait le geste', async () => {
    monter('tache', contrat('tache_ecrite'))
    const carte = screen.getByRole('group', { name: 'Devis Settat' })
    expect(within(carte).getByText('Prévue après l\'échéance.')).toBeInTheDocument()
    await userEvent.click(within(carte).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/gestes/77/annuler/', {}))
    expect(await within(carte).findByText('Annulé')).toBeInTheDocument()
  })

  it('une clé inconnue ne rend rien', () => {
    const { container } = monter('inconnue', {})
    expect(container).toHaveTextContent('')
  })
})

describe('TCH165 — cartes Tâches du Copilote (2/2)', () => {
  it('priorites : raisons, sous-titre, repli après les N premières, Garder ces 2', async () => {
    monter('priorites', contrat('priorites'))
    const carte = screen.getByRole('group', { name: 'Tes priorités' })
    expect(within(carte).getByText('2 pour atteindre ton objectif de 5')).toBeInTheDocument()
    expect(within(carte).getByText('échéance jeu. 19')).toBeInTheDocument()
    expect(within(carte).queryByText('Site web')).not.toBeInTheDocument()
    await userEvent.click(within(carte).getByRole('button', { name: 'Voir les 1 suivantes' }))
    expect(within(carte).getByText('Site web')).toBeInTheDocument()
    expect(within(carte).getByText('reportée 3 fois')).toBeInTheDocument()
    await userEvent.click(within(carte).getByRole('button', { name: 'Garder ces 2' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/taches/journee/planifier/',
      expect.objectContaining({ lignes: [{ type: 'tache', id: 21 }, { type: 'tache', id: 30 }] }),
      expect.anything(),
    ))
  })

  it('priorites : Essentiel, Aujourd’hui et Plus tard dans la semaine ont chacun leur route', async () => {
    monter('priorites', contrat('priorites'))
    const ligne = screen.getByText('Déclaration TVA').closest('.ligne')
    await userEvent.click(within(ligne).getByRole('button', { name: 'Essentiel' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/journee/essentiel/', { tache_id: 21, essentielle: true }))
    expect(await within(ligne).findByText(/Essentielle/)).toBeInTheDocument()
    await userEvent.click(within(ligne).getByRole('button', { name: /Plus tard dans la semaine/ }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/taches/taches/21/planifier/', expect.objectContaining({ jour_prevu: '2026-11-19', lock_version: 2 }),
    ))
  })

  it('priorites : liste vide', () => {
    const donnees = { ...contrat('priorites'), lignes: [], garder_n: 0 }
    monter('priorites', donnees)
    expect(screen.getByText('Rien à prioriser : tout est gardé ou fait.')).toBeInTheDocument()
  })

  it('priorites : objectif atteint et mode libre ont leur phrase', () => {
    const atteint = { ...contrat('priorites'), garder_n: 0 }
    const { unmount } = monter('priorites', atteint)
    expect(screen.getByText('Objectif atteint : le reste peut attendre.')).toBeInTheDocument()
    unmount()
    const libre = contrat('priorites')
    libre.objectif.mode = 'libre'
    monter('priorites', libre)
    expect(screen.getByText("Dans l'ordre où l'ERP les prendrait")).toBeInTheDocument()
  })

  it('point : les constats calculés par le serveur, rien d’autre', () => {
    monter('point', contrat('point'))
    const carte = screen.getByRole('group', { name: 'Où tu en es' })
    expect(within(carte).getByText('1 sur 5')).toBeInTheDocument()
    expect(within(carte).getByText('Essentiel restant : Devis Settat')).toBeInTheDocument()
    expect(within(carte).getByText('Prochaine : Timbres')).toBeInTheDocument()
    expect(within(carte).getByText('Encore 3 gardées')).toBeInTheDocument()
    expect(within(carte).getByText('Temps libre : 3 h')).toBeInTheDocument()
    expect(within(carte).getByRole('link', { name: "Ouvrir Aujourd'hui" })).toHaveAttribute('href', '/taches/aujourdhui')
  })

  it('capture_apercu : « Retirer » ôte la ligne, « Tout ajouter » crée les lignes restantes', async () => {
    monter('capture_apercu', contrat('saisie_apercu'))
    const carte = screen.getByRole('group', { name: 'Ta liste rangée' })
    expect(within(carte).getByText('Nouveau projet : SiteWeb')).toBeInTheDocument()
    await userEvent.click(within(carte).getByRole('button', { name: 'Tout ajouter (1)' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    const [url, corps] = api.post.mock.calls[0]
    expect(url).toBe('/taches/saisie-rapide/')
    expect(corps.apercu).toBe(false)
    expect(corps.lignes[0]).toMatchObject({ titre: 'Appeler Karim', jour_prevu: '2026-11-18' })
    expect(await within(carte).findByText(/1 ajoutée/)).toBeInTheDocument()
  })

  it('capture_apercu : retirer la dernière ligne vide la carte', async () => {
    monter('capture_apercu', contrat('saisie_apercu'))
    await userEvent.click(screen.getByRole('button', { name: 'Retirer' }))
    expect(screen.getByText('Rien à ajouter.')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('rythme : la proposition et ses boutons répondent par la route des propositions', async () => {
    monter('rythme', contrat('rythme'))
    const carte = screen.getByRole('group', { name: 'Ton rythme' })
    expect(within(carte).getByText('objectif 5')).toBeInTheDocument()
    await userEvent.click(within(carte).getByRole('button', { name: 'Monter à 6' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/taches/rythme/propositions/41/repondre/', { reponse: 'oui' },
    ))
  })

  it('rythme : « Retirer » une préférence appelle sa route', async () => {
    monter('rythme', contrat('rythme'))
    await userEvent.click(screen.getByRole('button', { name: 'Retirer' }))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/taches/preferences/heure_limite/'))
  })

  it('rythme : la réponse d’une proposition (rythme imbriqué) se rend aussi', () => {
    monter('rythme', contrat('proposition_repondue'))
    expect(screen.getByRole('group', { name: 'Ton rythme' })).toBeInTheDocument()
  })

  it('plan_projet : les étapes et leurs tâches, « Retirer » ôte une tâche localement', async () => {
    monter('plan_projet', contrat('planification_apercu'))
    const carte = screen.getByRole('group', { name: 'Le projet en étapes' })
    expect(within(carte).getByText('Visite')).toBeInTheDocument()
    await userEvent.click(within(carte).getAllByRole('button', { name: 'Retirer' })[0])
    expect(within(carte).queryByText('Visite')).not.toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('projet : avancement, prochaine action, Ouvrir', () => {
    monter('projet', contrat('projet_vue'))
    const carte = screen.getByRole('group', { name: 'Ventes' })
    expect(within(carte).getByText('12 sur 20')).toBeInTheDocument()
    expect(within(carte).getByText('Rien de fait depuis 10 jours travaillés.')).toBeInTheDocument()
    expect(within(carte).getByRole('link', { name: 'Ouvrir' })).toHaveAttribute('href', '/taches/projets/3')
  })

  it('revue_semaine : le bilan de la semaine et « Ouvrir la revue »', () => {
    monter('revue_semaine', contrat('revue_projets'))
    const carte = screen.getByRole('group', { name: 'Revue de la semaine' })
    expect(within(carte).getByText(/Du lun. 16 au ven. 20/)).toBeInTheDocument()
    expect(within(carte).getByRole('link', { name: 'Ouvrir la revue' })).toHaveAttribute('href', '/taches/revue')
  })
})
