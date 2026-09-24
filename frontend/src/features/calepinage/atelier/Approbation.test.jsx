/* CALX349 — l'onglet « Approbation » de l'atelier.

   Tout ce qui est affirmé ici l'est sur l'échantillon COMMITTÉ
   `apps/calepinage/contract_samples/calepinage_approbation.json` (PACT10,
   `reponseContrat`) — jamais une charge utile écrite à la main : le test
   backend jumeau affirme le MÊME fichier.

   Ce qui est prouvé :
   1. sans le code `calepinage_approuver`, les boutons Approuver/Refuser sont
      ABSENTS et la raison est affichée ;
   2. avec le code, une décision POST rappelle l'état à jour (contrat) sans
      qu'aucune valeur ne soit inventée côté écran ;
   3. un refus 400 NOMME son champ : le bandeau liste les champs fautifs et le
      message SERVEUR est rendu SOUS le champ (`motif`) ;
   4. une suggestion automatique en attente (clé `buildings[0].hauteurM`) est
      rendue sous SON chemin, jamais fondue dans un message générique. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

const mocks = vi.hoisted(() => ({ hasPermission: vi.fn(() => false) }))
vi.mock('../../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => mocks.hasPermission(code),
}))

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { approbation: vi.fn(), decisionApprobation: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import Approbation from './Approbation'

const echantillon = (variante) => reponseContrat('calepinage', 'calepinage_approbation', variante).data

const servir = (variante) => {
  calepinageApi.calepinages.approbation.mockResolvedValue(
    reponseContrat('calepinage', 'calepinage_approbation', variante),
  )
}

const rendre = () => render(
  <MemoryRouter><Approbation calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks(); mocks.hasPermission.mockReturnValue(false) })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Approbation (CALX349) — lecture', () => {
  it('affiche « aucune décision » sur l’exemple vide', async () => {
    servir('exemple_vide')
    rendre()
    await screen.findByTestId('calx349-panneau')
    expect(screen.getByTestId('calx349-aucune-decision')).toBeInTheDocument()
    expect(screen.queryByTestId('calx349-exigee')).toBeNull()
  })

  it('affiche la décision, le décideur et la date SERVIS, sans invention', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('calx349-panneau')

    const exemple = echantillon('exemple')
    expect(screen.getByTestId('calx349-decision'))
      .toHaveTextContent(exemple.decide_par.nom_complet)
    expect(screen.getByTestId('calx349-motif-decision')).toHaveTextContent(exemple.motif)
    expect(screen.getByTestId('calx349-exigee')).toBeInTheDocument()
  })

  it('affiche un refus tel que servi', async () => {
    servir('exemple_refuse')
    rendre()
    await screen.findByTestId('calx349-panneau')
    const refuse = echantillon('exemple_refuse')
    expect(screen.getByTestId('calx349-decision')).toHaveTextContent('Refusée')
    expect(screen.getByTestId('calx349-motif-decision')).toHaveTextContent(refuse.motif)
  })
})

describe('Approbation (CALX349) — sans le code d’approbation', () => {
  it('n’affiche AUCUN bouton et nomme la raison', async () => {
    mocks.hasPermission.mockReturnValue(false)
    servir('exemple_vide')
    rendre()
    await screen.findByTestId('calx349-panneau')

    expect(screen.queryByTestId('calx349-approuver')).toBeNull()
    expect(screen.queryByTestId('calx349-refuser')).toBeNull()
    expect(screen.getByTestId('calx349-sans-droit')).toHaveTextContent('calepinage_approuver')
  })
})

describe('Approbation (CALX349) — décider, avec le code', () => {
  beforeEach(() => { mocks.hasPermission.mockReturnValue(true) })

  it('approuve puis affiche l’état RENVOYÉ par le POST, sans second GET', async () => {
    servir('exemple_vide')
    calepinageApi.calepinages.decisionApprobation
      .mockResolvedValue(reponseContrat('calepinage', 'calepinage_approbation', 'exemple'))
    rendre()
    await screen.findByTestId('calx349-decider')

    fireEvent.click(screen.getByTestId('calx349-approuver'))

    await waitFor(() => expect(calepinageApi.calepinages.decisionApprobation)
      .toHaveBeenCalledWith(1, { decision: 'approuve', motif: '' }))
    await screen.findByTestId('calx349-decision')
    expect(screen.getByTestId('calx349-decision')).toHaveTextContent('Approuvée')
  })

  it('un refus SANS motif est rendu SOUS le champ « motif », bandeau nommé', async () => {
    servir('exemple_vide')
    calepinageApi.calepinages.decisionApprobation.mockRejectedValue({
      response: { data: { motif: 'Un refus d’approbation exige un motif : dites ce qui est à reprendre.' } },
    })
    rendre()
    await screen.findByTestId('calx349-decider')

    fireEvent.click(screen.getByTestId('calx349-refuser'))

    await screen.findByTestId('calx349-erreur-motif')
    expect(screen.getByTestId('calx349-erreur-motif'))
      .toHaveTextContent('exige un motif')
    expect(screen.getByTestId('calx349-bandeau')).toHaveTextContent('motif')
  })

  it('une décision inconnue est rendue SOUS le champ « decision »', async () => {
    servir('exemple_vide')
    calepinageApi.calepinages.decisionApprobation.mockRejectedValue({
      response: { data: { decision: 'Décision inconnue : « valide ». Décisions admises : approuve, refuse.' } },
    })
    rendre()
    await screen.findByTestId('calx349-decider')

    fireEvent.click(screen.getByTestId('calx349-approuver'))

    await screen.findByTestId('calx349-erreur-decision')
    expect(screen.getByTestId('calx349-bandeau')).toHaveTextContent('decision')
  })

  it('une suggestion automatique en attente est nommée SOUS son chemin de document', async () => {
    servir('exemple_vide')
    const refus = echantillon('exemple')
    void refus
    calepinageApi.calepinages.decisionApprobation.mockRejectedValue({
      response: {
        data: {
          'buildings[0].hauteurM':
            'Hauteur proposée par OpenStreetMap, jamais acceptée : acceptez-la ou saisissez-la avant d’approuver.',
        },
      },
    })
    rendre()
    await screen.findByTestId('calx349-decider')

    fireEvent.click(screen.getByTestId('calx349-approuver'))

    const ligne = await screen.findByTestId('calx349-suggestion-buildings[0].hauteurM')
    expect(ligne).toHaveTextContent('OpenStreetMap')
    expect(screen.getByTestId('calx349-bandeau')).toHaveTextContent('buildings[0].hauteurM')
  })

  it('envoie le motif saisi avec la décision', async () => {
    servir('exemple_vide')
    calepinageApi.calepinages.decisionApprobation
      .mockResolvedValue(reponseContrat('calepinage', 'calepinage_approbation', 'exemple_refuse'))
    rendre()
    await screen.findByTestId('calx349-decider')

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Obstacle non relevé.' } })
    fireEvent.click(screen.getByTestId('calx349-refuser'))

    await waitFor(() => expect(calepinageApi.calepinages.decisionApprobation)
      .toHaveBeenCalledWith(1, { decision: 'refuse', motif: 'Obstacle non relevé.' }))
  })
})
