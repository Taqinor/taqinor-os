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
