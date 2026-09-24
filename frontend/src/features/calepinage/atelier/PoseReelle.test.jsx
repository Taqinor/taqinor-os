/* CALX367 — l'onglet « Pose réelle » de l'atelier.

   Tout ce qui est affirmé ici l'est sur l'échantillon COMMITTÉ
   `apps/calepinage/contract_samples/calepinage_asbuilt_ecarts.json` (CALX337,
   `reponseContrat`) — jamais une charge utile écrite à la main : le test
   backend jumeau (`tests/test_calx366_pose_reelle.py`) rejoue le MÊME
   fichier, les deux moitiés ne peuvent donc pas diverger.

   Ce qui est prouvé :
   1. la grille rend un pan par ligne : prévu, posé saisissable, écart du
      SERVEUR, écarts de position ;
   2. un pan SANS saisie affiche un écart VIDE et la mention — jamais `0` ;
   3. « Enregistrer » envoie la saisie du pan ; la réponse remplace la grille ;
   4. un refus 400 s'affiche SOUS le champ du pan fautif et le bandeau NOMME le
      pan et le champ (`pan`, puis `modules_poses`, les deux refus du contrat) ;
   5. « Créer une version depuis les écarts » appelle la porte et affiche la
      version gelée ; un refus `creer_version` s'affiche sous le bouton. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      poseReelle: vi.fn(),
      enregistrerPoseReelle: vi.fn(),
      creerVersionPoseReelle: vi.fn(),
    },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import PoseReelle from './PoseReelle'

const NOM = 'calepinage_asbuilt_ecarts'
const echantillon = (variante) => exempleContrat('calepinage', NOM, variante)

const servir = (variante) => {
  calepinageApi.calepinages.poseReelle
    .mockResolvedValue(reponseContrat('calepinage', NOM, variante))
}

const rendre = () => render(
  <MemoryRouter><PoseReelle calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PoseReelle (CALX367) — la grille des pans', () => {
  it('rend un pan par ligne avec son prévu, son posé et l’écart du serveur', async () => {
    servir('exemple')
    rendre()
    const grille = await screen.findByTestId('cal-pose-grille')

    const exemple = echantillon('exemple')
    const lignes = within(grille).getAllByRole('row').slice(1)
    expect(lignes).toHaveLength(exemple.lignes.length)
    const panB = within(grille).getByTestId('cal-pose-ligne-PAN-B')
    expect(within(panB).getByTestId('cal-pose-prevu-PAN-B')).toHaveTextContent('4')
    expect(within(panB).getByTestId('cal-pose-modules-PAN-B')).toHaveValue(3)
    expect(within(panB).getByTestId('cal-pose-ecart-PAN-B')).toHaveTextContent('-1')
    expect(within(panB).getByTestId('cal-pose-position-PAN-B'))
      .toHaveValue(exemple.lignes[1].ecarts_position)
    expect(screen.getByTestId('cal-pose-source')).toHaveTextContent('total posé 11')
  })

  it('un pan SANS saisie affiche un écart VIDE et la mention — jamais 0', async () => {
    servir('exemple')
    rendre()
    const grille = await screen.findByTestId('cal-pose-grille')
    const panC = within(grille).getByTestId('cal-pose-ligne-PAN-C')
    expect(within(panC).getByTestId('cal-pose-ecart-PAN-C').textContent).toBe('')
    expect(within(panC).getByTestId('cal-pose-modules-PAN-C')).toHaveValue(null)
    expect(within(panC).getByTestId('cal-pose-mention-PAN-C'))
      .toHaveTextContent(echantillon('exemple').lignes[2].mention)
  })

  it('aucun pan relevé : le total posé n’est pas un zéro', async () => {
    servir('exemple_vide')
    rendre()
    expect(await screen.findByTestId('cal-pose-source')).toHaveTextContent('aucun pan relevé')
    for (const ligne of echantillon('exemple_vide').lignes) {
      expect(screen.getByTestId(`cal-pose-ecart-${ligne.pan}`).textContent).toBe('')
    }
  })

  it('une réponse sans pan dit ce qui manque', async () => {
    calepinageApi.calepinages.poseReelle.mockResolvedValue({ data: {} })
    rendre()
    expect(await screen.findByTestId('cal-pose-vide')).toHaveTextContent('Aucun pan prévu')
  })
})

describe('PoseReelle (CALX367) — saisir un pan', () => {
  it('« Enregistrer » envoie la saisie du pan, la réponse remplace la grille', async () => {
    servir('exemple_vide')
    calepinageApi.calepinages.enregistrerPoseReelle
      .mockResolvedValue(reponseContrat('calepinage', NOM, 'exemple'))
    rendre()
    const grille = await screen.findByTestId('cal-pose-grille')
    const corps = echantillon('corps_saisie')

    fireEvent.change(within(grille).getByTestId('cal-pose-modules-PAN-B'),
      { target: { value: String(corps.modules_poses) } })
    fireEvent.change(within(grille).getByTestId('cal-pose-position-PAN-B'),
      { target: { value: corps.ecarts_position } })
    fireEvent.change(screen.getByTestId('cal-pose-champ-releve_le').querySelector('input'),
      { target: { value: corps.releve_le } })
    fireEvent.click(within(grille).getByTestId('cal-pose-enregistrer-PAN-B'))

    expect(await screen.findByTestId('cal-pose-message')).toHaveTextContent('PAN-B')
    expect(calepinageApi.calepinages.enregistrerPoseReelle).toHaveBeenCalledWith(1, {
      pan: 'PAN-B',
      modules_poses: String(corps.modules_poses),
      ecarts_position: corps.ecarts_position,
      releve_le: corps.releve_le,
    })
    expect(screen.getByTestId('cal-pose-ecart-PAN-B')).toHaveTextContent('-1')
  })

  it('refus `modules_poses` : SOUS le champ du pan fautif, le bandeau nomme pan et champ', async () => {
    servir('exemple')
    const refus = echantillon('refus_modules_poses')
    calepinageApi.calepinages.enregistrerPoseReelle
      .mockRejectedValue({ response: { status: 400, data: refus } })
    rendre()
    const grille = await screen.findByTestId('cal-pose-grille')
    fireEvent.click(within(grille).getByTestId('cal-pose-enregistrer-PAN-A'))

    const erreur = await screen.findByTestId('cal-pose-erreur-modules-PAN-A')
    expect(erreur).toHaveTextContent(refus.modules_poses)
    expect(within(within(grille).getByTestId('cal-pose-ligne-PAN-A'))
      .getByTestId('cal-pose-erreur-modules-PAN-A')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-pose-erreur-modules-PAN-B')).toBeNull()
    const bandeau = screen.getByTestId('cal-pose-bandeau')
    expect(bandeau).toHaveTextContent('PAN-A')
    expect(bandeau).toHaveTextContent('modules_poses')
    expect(bandeau.textContent).not.toMatch(/non enregistré/i)
  })

  it('refus `pan` : sous la cellule du pan fautif', async () => {
    servir('exemple')
    const refus = echantillon('refus_pan_inconnu')
    calepinageApi.calepinages.enregistrerPoseReelle
      .mockRejectedValue({ response: { status: 400, data: refus } })
    rendre()
    const grille = await screen.findByTestId('cal-pose-grille')
    fireEvent.click(within(grille).getByTestId('cal-pose-enregistrer-PAN-C'))

    expect(await screen.findByTestId('cal-pose-erreur-pan-PAN-C')).toHaveTextContent(refus.pan)
    expect(screen.getByTestId('cal-pose-bandeau')).toHaveTextContent('pan')
  })
})

describe('PoseReelle (CALX367) — créer une version depuis les écarts', () => {
  it('appelle la porte et affiche la version gelée', async () => {
    servir('exemple')
    calepinageApi.calepinages.creerVersionPoseReelle
      .mockResolvedValue(reponseContrat('calepinage', NOM, 'exemple_version_creee'))
    rendre()
    fireEvent.click(await screen.findByTestId('cal-pose-creer-version'))

    const version = echantillon('exemple_version_creee').version_creee
    expect(await screen.findByTestId('cal-pose-version')).toHaveTextContent(`n° ${version}`)
    expect(screen.getByTestId('cal-pose-message')).toHaveTextContent(`Version n° ${version}`)
    expect(calepinageApi.calepinages.creerVersionPoseReelle).toHaveBeenCalledWith(1)
  })

  it('un refus `creer_version` s’affiche sous le bouton, le bandeau le nomme', async () => {
    servir('exemple_vide')
    const message = 'Aucun pan n’a été relevé sur le chantier : il n’y a aucun écart à figer en version.'
    calepinageApi.calepinages.creerVersionPoseReelle
      .mockRejectedValue({ response: { status: 400, data: { creer_version: message } } })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-pose-creer-version'))

    expect(await screen.findByTestId('cal-pose-erreur-creer_version')).toHaveTextContent(message)
    expect(screen.getByTestId('cal-pose-bandeau')).toHaveTextContent('creer_version')
  })
})
