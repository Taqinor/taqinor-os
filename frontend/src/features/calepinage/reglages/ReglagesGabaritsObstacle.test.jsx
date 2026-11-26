import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, within } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { espions } from '../../../test/fixtures/calepinageApiMock'

/* ============================================================================
   ACAL494 / ACAL495 — « GABARITS D'OBSTACLE » (et de ZONE) de Réglages › Calepinage.
   Le serveur REMPLACE `zones_types` en entier : le PUT porte TOUTE la section
   servie (échantillon `parametres_calepinage.json`), seule l'entrée touchée change.
   ========================================================================== */

const SERVI = exempleContrat('calepinage', 'parametres_calepinage').zones_types

vi.mock('../../../api/calepinageApi', async () => (await import('../../../test/fixtures/calepinageApiMock')).apiParametres())
vi.mock('../../../hooks/useHasPermission', async () => (await import('../../../test/fixtures/calepinageApiMock')).permissionMock())

const { default: ReglagesGabaritsObstacle } = await import('./ReglagesGabaritsObstacle')

const champ = (cle) => screen.getByTestId(`acal494-champ-${cle}`).querySelector('input')
const remplir = (valeurs) => {
  for (const [cle, valeur] of Object.entries(valeurs)) fireEvent.change(champ(cle), { target: { value: valeur } })
}
const SOUCHE = { libelle: 'Souche type', longueur_m: '0,9', largeur_m: '0,6', hauteur_m: '1,1', retrait_m: '0,8', source: 'Consigne de pose interne' }

beforeEach(() => {
  vi.clearAllMocks()
  espions.hasPermission.mockReturnValue(true)
  espions.getParametres.mockResolvedValue({ data: { zones_types: SERVI } })
  espions.putParametres.mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup() })

describe('ReglagesGabaritsObstacle (ACAL494)', () => {
  it('création : le PUT renvoie la section COMPLÈTE + la nouvelle entrée (rien de perdu)', async () => {
    render(<ReglagesGabaritsObstacle zonesTypes={SERVI} />)

    fireEvent.click(screen.getByTestId('acal494-nouveau'))
    remplir(SOUCHE)
    fireEvent.click(screen.getByTestId('acal494-enregistrer'))

    await waitFor(() => expect(espions.putParametres).toHaveBeenCalledTimes(1))
    expect(espions.putParametres.mock.calls[0][0]).toEqual({
      zones_types: {
        ...SERVI,
        souche_type_2: {
          libelle: 'Souche type', nature: 'INTERDITE', forme: 'rectangle', longueur_m: 0.9,
          largeur_m: 0.6, hauteur_m: 1.1, retrait_m: 0.8, source: 'Consigne de pose interne',
        },
      },
    })
    expect(espions.putParametres.mock.calls[0][0].zones_types.coupe_feu).toEqual(SERVI.coupe_feu)
  })

  it('suppression : le reste de la section repart intact', async () => {
    render(<ReglagesGabaritsObstacle zonesTypes={SERVI} />)

    fireEvent.click(screen.getByTestId('acal494-supprimer-souche_type'))

    await waitFor(() => expect(espions.putParametres).toHaveBeenCalledTimes(1))
    expect(espions.putParametres.mock.calls[0][0]).toEqual({ zones_types: { coupe_feu: SERVI.coupe_feu } })
  })

  it('refus 400 : le motif se pose sous « Source » avec aria-invalid', async () => {
    espions.putParametres.mockRejectedValueOnce({
      response: { data: { 'zones_types.souche_type_2.source': ['Le gabarit « souche_type_2 » ne peut pas être enregistré sans SOURCE.'] } },
    })
    render(<ReglagesGabaritsObstacle zonesTypes={SERVI} />)

    fireEvent.click(screen.getByTestId('acal494-nouveau'))
    remplir({ ...SOUCHE, source: '' })
    fireEvent.click(screen.getByTestId('acal494-enregistrer'))

    const ligne = await screen.findByTestId('acal494-champ-source')
    expect(within(ligne).getByTestId('acal494-erreur-source')).toHaveTextContent('sans SOURCE')
    expect(champ('source')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByTestId('acal494-bandeau')).toHaveTextContent('source')
    // ACAL1434 — la requête coupe le toast de l'intercepteur : le refus n'est
    // dit qu'une fois, sous le champ. Mutant : retirer l'option ⇒ échec.
    expect(espions.putParametres.mock.calls[0][1]).toEqual({ suppressErrorToast: true })
  })

  it('cercle : demande son rayon, aucune longueur ni largeur envoyée', async () => {
    render(<ReglagesGabaritsObstacle zonesTypes={SERVI} />)

    fireEvent.click(screen.getByTestId('acal494-nouveau'))
    fireEvent.change(screen.getByTestId('acal494-champ-forme'), { target: { value: 'cercle' } })
    expect(screen.queryByTestId('acal494-champ-longueur_m')).toBeNull()
    remplir({ libelle: 'Citerne', rayon_m: '0,5', source: 'Relevé interne' })
    fireEvent.click(screen.getByTestId('acal494-enregistrer'))

    await waitFor(() => expect(espions.putParametres).toHaveBeenCalledTimes(1))
    const entree = espions.putParametres.mock.calls[0][0].zones_types.citerne
    expect(entree).toEqual({ libelle: 'Citerne', nature: 'INTERDITE', forme: 'cercle', rayon_m: 0.5, source: 'Relevé interne' })
  })

  it('sans le droit de gérer : aucun bouton', () => {
    espions.hasPermission.mockReturnValue(false)
    render(<ReglagesGabaritsObstacle zonesTypes={SERVI} />)

    expect(screen.queryByTestId('acal494-nouveau')).toBeNull()
    expect(screen.queryByTestId('acal494-supprimer-souche_type')).toBeNull()
  })
})

describe('ReglagesGabaritsObstacle — zones réglementaires (ACAL495)', () => {
  const zChamp = (cle) => screen.getByTestId(`acal495-champ-${cle}`).querySelector('input')
  const remplirZone = (valeurs) => {
    for (const [cle, valeur] of Object.entries(valeurs)) fireEvent.change(zChamp(cle), { target: { value: valeur } })
  }

  it('bande coupe-feu : le PUT garde la section complète et ajoute la bande, côté nord', async () => {
    render(<ReglagesGabaritsObstacle zonesTypes={SERVI} />)

    fireEvent.click(screen.getByTestId('acal495-nouveau'))
    remplirZone({ libelle: 'Bande nord', largeur_m: '1,2', source: 'Arrêté n° 2026-14, art. 7' })
    fireEvent.change(screen.getByTestId('acal495-champ-cote'), { target: { value: 'nord' } })
    fireEvent.click(screen.getByTestId('acal495-enregistrer'))

    await waitFor(() => expect(espions.putParametres).toHaveBeenCalledTimes(1))
    const corps = espions.putParametres.mock.calls[0][0].zones_types
    expect(corps).toEqual({
      ...SERVI,
      bande_nord: { libelle: 'Bande nord', nature: 'INTERDITE', genre: 'bande', largeur_m: 1.2, cote: 'nord', source: 'Arrêté n° 2026-14, art. 7' },
    })
    expect(corps.coupe_feu).toEqual(SERVI.coupe_feu)
  })

  it('côté laissé vide : aucune clé « cote » envoyée (le serveur décide)', async () => {
    render(<ReglagesGabaritsObstacle zonesTypes={SERVI} />)

    fireEvent.click(screen.getByTestId('acal495-nouveau'))
    remplirZone({ libelle: 'Servitude', largeur_m: '2', source: 'Plan local' })
    fireEvent.click(screen.getByTestId('acal495-enregistrer'))

    await waitFor(() => expect(espions.putParametres).toHaveBeenCalledTimes(1))
    expect('cote' in espions.putParametres.mock.calls[0][0].zones_types.servitude).toBe(false)
  })

  it('sans source : le refus se pose sous « Source »', async () => {
    espions.putParametres.mockRejectedValueOnce({
      response: { data: { 'zones_types.bande_nord.source': ['Le gabarit « bande_nord » ne peut pas être enregistré sans SOURCE.'] } },
    })
    render(<ReglagesGabaritsObstacle zonesTypes={SERVI} />)

    fireEvent.click(screen.getByTestId('acal495-nouveau'))
    remplirZone({ libelle: 'Bande nord', largeur_m: '1,2' })
    fireEvent.click(screen.getByTestId('acal495-enregistrer'))

    const ligne = await screen.findByTestId('acal495-champ-source')
    expect(within(ligne).getByTestId('acal495-erreur-source')).toHaveTextContent('sans SOURCE')
    expect(zChamp('source')).toHaveAttribute('aria-invalid', 'true')
  })

  it('polygone : lecture seule (contour tracé dans l’atelier), supprimable', async () => {
    const poly = { libelle: 'Contour', nature: 'INTERDITE', genre: 'polygone', sommets: [[0, 0], [1, 0], [0, 1]], source: 'Plan' }
    render(<ReglagesGabaritsObstacle zonesTypes={{ ...SERVI, contour: poly }} />)

    expect(screen.getByTestId('acal495-ligne-contour')).toHaveTextContent('contour tracé dans l’atelier')
    expect(screen.queryByTestId('acal495-modifier-contour')).toBeNull()
    fireEvent.click(screen.getByTestId('acal495-supprimer-contour'))
    await waitFor(() => expect(espions.putParametres).toHaveBeenCalledTimes(1))
    expect(espions.putParametres.mock.calls[0][0]).toEqual({ zones_types: SERVI })
  })
})
