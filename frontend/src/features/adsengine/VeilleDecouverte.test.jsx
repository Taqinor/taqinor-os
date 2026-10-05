import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* VEIL30 — Onglet « Découverte ». Les charges utiles viennent des contrats
   committés (veille_decouverte.json, veille_couverture.json) : jamais un mock
   inventé (PACT13). */

const DECOUVERTE = documentContrat('adsengine', 'veille_decouverte').exemple
const COUVERTURE = documentContrat('adsengine', 'veille_couverture').exemple

const mocks = vi.hoisted(() => ({
  decouvertes: vi.fn(), decouverte: vi.fn(), lancer: vi.fn(),
  annuler: vi.fn(), reprendre: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: { veille: mocks },
}))

import VeilleDecouverte from './VeilleDecouverte'

const PAYS_UE_GB = [
  ...COUVERTURE.couverture,
  { pays: 'BE', statut: 'couvert', motif_fr: 'UE', source_url: '', lu_le: '' },
]

const rendre = () => render(<VeilleDecouverte couverture={PAYS_UE_GB} onSelection={() => {}} />)

const remplir = ({ mot = 'robe été', appels = '200', pages = '10' } = {}) => {
  fireEvent.change(screen.getByTestId('ae-veille-decouverte-mot-0'), { target: { value: mot } })
  fireEvent.click(screen.getByTestId('ae-veille-decouverte-pays-0-FR'))
  fireEvent.change(screen.getByTestId('ae-veille-decouverte-plafond-appels'), { target: { value: appels } })
  fireEvent.change(screen.getByTestId('ae-veille-decouverte-plafond-pages'), { target: { value: pages } })
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.decouvertes.mockResolvedValue({ data: { count: 0, results: [] } })
  mocks.lancer.mockResolvedValue({ data: DECOUVERTE })
  mocks.decouverte.mockResolvedValue({ data: DECOUVERTE })
})

describe('VeilleDecouverte', () => {
  it('mot-clé de 101 caractères : erreur sous le champ, aucun appel', async () => {
    rendre()
    remplir({ mot: 'x'.repeat(101) })
    fireEvent.click(screen.getByTestId('ae-veille-decouverte-lancer'))
    expect(await screen.findByTestId('ae-veille-decouverte-erreur-mot-0')).toBeTruthy()
    expect(mocks.lancer).not.toHaveBeenCalled()
  })

  it('plafonds obligatoires : aucun défaut inventé, aucun appel', async () => {
    rendre()
    remplir({ appels: '', pages: '' })
    fireEvent.click(screen.getByTestId('ae-veille-decouverte-lancer'))
    expect(await screen.findByTestId('ae-veille-decouverte-erreur-plafonds')).toBeTruthy()
    expect(mocks.lancer).not.toHaveBeenCalled()
  })

  it('pays : UE et Royaume-Uni (à confirmer) proposés, hors couverture absents', async () => {
    rendre()
    await waitFor(() => expect(mocks.decouvertes).toHaveBeenCalled())
    expect(screen.getByTestId('ae-veille-decouverte-pays-0-GB').parentElement.textContent)
      .toContain('à confirmer')
    expect(screen.queryByTestId('ae-veille-decouverte-pays-0-MA')).toBeNull()
    expect(screen.queryByTestId('ae-veille-decouverte-pays-0-US')).toBeNull()
  })

  it('lance avec les plafonds saisis et affiche l’état servi (pause sans contournement)', async () => {
    rendre()
    remplir()
    fireEvent.click(screen.getByTestId('ae-veille-decouverte-lancer'))
    await waitFor(() => expect(mocks.lancer).toHaveBeenCalled())
    expect(mocks.lancer.mock.calls[0][0]).toEqual({
      mots_cles: [{ texte: 'robe été', pays: ['FR'] }],
      search_type: 'KEYWORD_UNORDERED',
      ad_active_status: 'ACTIVE',
      plafond_appels: 200,
      plafond_pages_par_requete: 10,
    })
    const statut = await screen.findByTestId('ae-veille-decouverte-statut')
    expect(statut.textContent).toContain('quota atteint, reprise à')
    expect(screen.queryByTestId('ae-veille-decouverte-reprendre')).toBeNull()
    expect(screen.getAllByTestId(/ae-veille-decouverte-requete-/))
      .toHaveLength(DECOUVERTE.requetes.length)
  })

  it('enregistrer → rouvrir → enregistrer : même objet serveur affiché', async () => {
    rendre()
    remplir()
    fireEvent.click(screen.getByTestId('ae-veille-decouverte-lancer'))
    const apresLancement = (await screen.findByTestId('ae-veille-decouverte-etat')).textContent
    cleanup()
    mocks.decouvertes.mockResolvedValue({ data: { count: 1, results: [DECOUVERTE] } })
    rendre()
    const rouvert = (await screen.findByTestId('ae-veille-decouverte-etat')).textContent
    expect(rouvert).toBe(apresLancement)
    fireEvent.click(screen.getByTestId('ae-veille-decouverte-actualiser'))
    await waitFor(() => expect(mocks.decouverte).toHaveBeenCalledWith(DECOUVERTE.id))
    expect(screen.getByTestId('ae-veille-decouverte-etat').textContent).toBe(apresLancement)
  })

  it('refus serveur : message sous le bouton', async () => {
    mocks.lancer.mockRejectedValue({ response: { data: { detail: "Cette société n'est pas autorisée." } } })
    rendre()
    remplir()
    fireEvent.click(screen.getByTestId('ae-veille-decouverte-lancer'))
    expect((await screen.findByTestId('ae-veille-decouverte-erreur-serveur')).textContent)
      .toContain('pas autorisée')
  })
})
