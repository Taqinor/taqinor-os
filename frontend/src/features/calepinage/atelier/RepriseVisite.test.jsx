/* CALX365 — l'onglet « Reprise de la visite » de l'atelier.

   Tout ce qui est affirmé ici l'est sur l'échantillon COMMITTÉ
   `apps/calepinage/contract_samples/calepinage_releve_visite.json` (CALX336,
   `reponseContrat`) — jamais une charge utile écrite à la main : le test
   backend jumeau (`tests/test_calx364_reprise_visite.py`) rejoue le MÊME
   fichier, les deux moitiés ne peuvent donc pas diverger.

   Ce qui est prouvé :
   1. une visite validée non reprise : chaque mesure TELLE QUE SAISIE (unité
      déclarée, jamais convertie), chaque photo retenue, bouton actif ;
   2. une visite déjà reprise : bouton DÉSACTIVÉ avec sa raison, bandeau qui
      dit la date et l'auteur de la reprise ;
   3. aucune visite validée : état vide qui affiche `motif_absence` TEL QUEL,
      aucun bouton ;
   4. `validee_le: null` est accepté — l'écran le dit, aucune autre date ;
   5. « Reprendre » appelle la porte et affiche la réponse du serveur ;
   6. un refus 400 s'affiche SOUS le bouton et le bandeau NOMME le champ. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { releveVisite: vi.fn(), reprendreVisite: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import RepriseVisite from './RepriseVisite'

const NOM = 'calepinage_releve_visite'
const echantillon = (variante) => exempleContrat('calepinage', NOM, variante)

const servir = (variante) => {
  calepinageApi.calepinages.releveVisite
    .mockResolvedValue(reponseContrat('calepinage', NOM, variante))
}

const rendre = () => render(
  <MemoryRouter><RepriseVisite calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RepriseVisite (CALX365) — visite validée, pas encore reprise', () => {
  it('liste chaque mesure telle que saisie, avec son unité déclarée', async () => {
    servir('exemple_avant_reprise')
    rendre()
    const liste = await screen.findByTestId('cal-reprise-mesures')

    const exemple = echantillon('exemple_avant_reprise')
    expect(within(liste).getAllByRole('listitem')).toHaveLength(exemple.mesures.length)
    expect(screen.getByTestId('cal-reprise-mesure-longueur_m'))
      .toHaveTextContent('Longueur de la zone utile (m) : 12.5 m')
    // Une orientation reste le CHOIX saisi — jamais un azimut deviné.
    expect(screen.getByTestId('cal-reprise-mesure-orientation'))
      .toHaveTextContent('Orientation du pan : sud')
    expect(screen.getByTestId('cal-reprise-mesure-toit_plat'))
      .toHaveTextContent('Toit plat : non')
  })

  it('liste chaque photo retenue, par sa pièce jointe', async () => {
    servir('exemple_avant_reprise')
    rendre()
    const liste = await screen.findByTestId('cal-reprise-photos')
    const exemple = echantillon('exemple_avant_reprise')
    expect(within(liste).getAllByRole('listitem')).toHaveLength(exemple.photos.length)
    expect(screen.getByTestId('cal-reprise-photo-43')).toHaveTextContent('Obstacles et ombrages')
  })

  it('le bouton « Reprendre » est actif, sans raison affichée', async () => {
    servir('exemple_avant_reprise')
    rendre()
    const bouton = await screen.findByTestId('cal-reprise-bouton')
    expect(bouton).toBeEnabled()
    expect(bouton).toHaveTextContent('Reprendre dans ce calepinage')
    expect(screen.queryByTestId('cal-reprise-raison')).toBeNull()
    expect(screen.queryByTestId('cal-reprise-bandeau')).toBeNull()
  })
})

describe('RepriseVisite (CALX365) — visite déjà reprise', () => {
  it('désactive le bouton AVEC sa raison, et dit la date et l’auteur de la reprise', async () => {
    servir('exemple')
    rendre()
    const bouton = await screen.findByTestId('cal-reprise-bouton')
    expect(bouton).toBeDisabled()
    expect(screen.getByTestId('cal-reprise-raison')).toHaveTextContent('déjà reprise')

    const releve = echantillon('exemple').releve
    const bandeau = screen.getByTestId('cal-reprise-bandeau')
    expect(bandeau).toHaveTextContent('Visite reprise le 19/09/2026')
    expect(bandeau).toHaveTextContent(`par ${releve.releve_par}`)
    expect(bandeau).toHaveTextContent(`${releve.photos.length} photo(s)`)
  })
})

describe('RepriseVisite (CALX365) — aucune visite validée', () => {
  it('affiche le motif du serveur TEL QUEL, sans bouton', async () => {
    servir('exemple_vide')
    rendre()
    const vide = await screen.findByTestId('cal-reprise-vide')
    expect(vide.textContent).toBe(echantillon('exemple_vide').motif_absence)
    expect(screen.queryByTestId('cal-reprise-bouton')).toBeNull()
    expect(screen.queryByTestId('cal-reprise-mesures')).toBeNull()
  })

  it('une réponse sans motif garde un état vide qui NOMME le manque', async () => {
    calepinageApi.calepinages.releveVisite.mockResolvedValue({ data: {} })
    rendre()
    expect(await screen.findByTestId('cal-reprise-vide'))
      .toHaveTextContent('Aucune visite technique validée')
  })
})

describe('RepriseVisite (CALX365) — `validee_le` absent', () => {
  it('accepte `validee_le: null` et le DIT, sans aucune autre date', async () => {
    const exemple = { ...echantillon('exemple_avant_reprise'), validee_le: null }
    calepinageApi.calepinages.releveVisite.mockResolvedValue({ data: exemple })
    rendre()
    const entete = await screen.findByTestId('cal-reprise-visite-entete')
    expect(entete).toHaveTextContent(`Visite technique n° ${exemple.visite_id}`)
    expect(entete).toHaveTextContent('n’enregistre pas encore l’heure de sa validation')
    expect(entete.textContent).not.toMatch(/\d{2}\/\d{2}\/\d{4}/)
  })
})

describe('RepriseVisite (CALX365) — reprendre', () => {
  it('« Reprendre » appelle la porte et affiche le bandeau de la reprise', async () => {
    servir('exemple_avant_reprise')
    calepinageApi.calepinages.reprendreVisite
      .mockResolvedValue(reponseContrat('calepinage', NOM, 'exemple'))
    rendre()
    fireEvent.click(await screen.findByTestId('cal-reprise-bouton'))

    expect(await screen.findByTestId('cal-reprise-bandeau')).toHaveTextContent('Visite reprise le')
    expect(calepinageApi.calepinages.reprendreVisite).toHaveBeenCalledWith(1)
    expect(screen.getByTestId('cal-reprise-bouton')).toBeDisabled()
  })

  it('un refus 400 s’affiche SOUS le bouton, et le bandeau NOMME le champ', async () => {
    servir('exemple_avant_reprise')
    const motif = echantillon('exemple_vide').motif_absence
    calepinageApi.calepinages.reprendreVisite
      .mockRejectedValue({ response: { status: 400, data: { visite_id: motif } } })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-reprise-bouton'))

    expect(await screen.findByTestId('cal-reprise-erreur-visite_id')).toHaveTextContent(motif)
    const bandeau = screen.getByTestId('cal-reprise-refus-bandeau')
    expect(bandeau).toHaveTextContent('visite_id')
    expect(bandeau.textContent).not.toMatch(/non enregistré/i)
  })
})
