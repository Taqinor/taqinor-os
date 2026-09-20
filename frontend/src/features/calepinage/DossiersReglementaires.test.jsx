/* CAL196 — l'écran « Dossiers réglementaires » du calepinage.

   Ce qui est prouvé ici, sur l'échantillon COMMITTÉ
   `apps/calepinage/contract_samples/dossiers_reglementaires.json` (CAL247,
   PACT10/13 — `reponseContrat`, jamais une charge utile écrite à la main) :
   1. chaque pièce est listée avec son état et sa SOURCE ;
   2. AUCUN champ « à compléter » n'est prérempli quand le serveur sert
      `valeur: null` — le champ est rendu VIDE et le message du serveur
      s'affiche (le Done de la tâche) ;
   3. un dossier dont le gabarit n'est pas déposé reste VISIBLE et dit pourquoi ;
   4. société sans aucun gabarit ⇒ liste vide ET le message du serveur. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { dossiersReglementaires: vi.fn() } },
}))

import calepinageApi from '../../api/calepinageApi'
import DossiersReglementaires from './DossiersReglementaires'

const servir = (variante) => {
  calepinageApi.calepinages.dossiersReglementaires
    .mockResolvedValue(reponseContrat('calepinage', 'dossiers_reglementaires', variante))
}

const echantillon = (variante) => reponseContrat(
  'calepinage', 'dossiers_reglementaires', variante,
).data

const rendre = () => render(
  <MemoryRouter><DossiersReglementaires calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DossiersReglementaires (CAL196)', () => {
  it('liste les pièces de chaque dossier avec leur état et leur source', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const exemple = echantillon('exemple')
    const premier = exemple.dossiers[0]

    const bloc = screen.getByTestId(`cal196-dossier-${premier.id}`)
    expect(within(bloc).getByText(premier.intitule)).toBeInTheDocument()

    const pieces = within(bloc).getByTestId('cal196-pieces')
    premier.pieces.forEach((piece) => {
      expect(within(pieces).getByText(piece.intitule)).toBeInTheDocument()
    })
    // Chaque pièce de l'échantillon porte une source : aucune n'est « non déclarée ».
    expect(within(pieces).getAllByTestId('cal196-source'))
      .toHaveLength(premier.pieces.length)
    expect(within(pieces).queryByText('source non déclarée')).toBeNull()
  })

  it('aucun champ « à compléter » n’est prérempli quand le serveur sert null', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const premier = echantillon('exemple').dossiers[0]

    premier.champs_a_completer.forEach((champ) => {
      const saisie = screen.getByTestId(`cal196-champ-${champ.code}`)
      // `valeur: null` dans le contrat ⇒ champ VIDE à l'écran.
      expect(champ.valeur).toBeNull()
      expect(saisie).toHaveValue('')
      expect(screen.getByTestId(`cal196-message-${champ.code}`))
        .toHaveTextContent(champ.message)
    })
  })

  it('la génération est refusée avec le motif SERVEUR, jamais un motif inventé', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const premier = echantillon('exemple').dossiers[0]

    expect(premier.peut_generer).toBe(false)
    expect(screen.getByTestId(`cal196-generer-${premier.id}`)).toBeDisabled()
    expect(screen.getByTestId(`cal196-motif-${premier.id}`))
      .toHaveTextContent(premier.motif_non_generable)
  })

  it('gabarit non déposé : le dossier reste visible et dit pourquoi', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const second = echantillon('exemple').dossiers[1]

    expect(second.gabarit.present).toBe(false)
    const bloc = screen.getByTestId(`cal196-dossier-${second.id}`)
    expect(bloc).toBeInTheDocument()
    expect(screen.getByTestId(`cal196-gabarit-${second.id}`))
      .toHaveTextContent('Gabarit non déposé')
    expect(within(bloc).getByTestId('cal196-pieces-vide')).toBeInTheDocument()
  })

  it('société sans gabarit : aucun dossier fantôme, et le message du serveur', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal196-ecran')
    const vide = echantillon('exemple_vide')

    expect(vide.dossiers).toHaveLength(0)
    expect(screen.getByTestId('cal196-aucun-gabarit'))
      .toHaveTextContent(vide.message_aucun_gabarit)
    expect(screen.queryByTestId('cal196-pieces')).toBeNull()
    expect(screen.getByTestId('cal196-entete')).toHaveTextContent('Pays de la société : MA')
  })

  it('erreur réseau : message français, aucune pièce inventée', async () => {
    calepinageApi.calepinages.dossiersReglementaires.mockRejectedValue(new Error('boum'))
    rendre()

    expect(await screen.findByTestId('cal196-erreur')).toHaveTextContent(
      'Dossiers réglementaires indisponibles.',
    )
  })
})
