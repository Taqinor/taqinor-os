import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CALX25 — LE RELEVÉ TERRAIN SUR UN PANNEAU, AUCUN CALCUL CÔTÉ ÉCRAN.
   ----------------------------------------------------------------------------
   CE QUE CE TEST TIENT :
     * les chaînes de cotes se saisissent (nom, total mesuré, tolérance,
       cotes), ainsi que l'azimut boussole et sa précision ;
     * une chaîne à qui il manque PLUS D'UNE cote est refusée AVANT tout envoi
       réseau, l'erreur posée SOUS la chaîne fautive — jamais un « non
       enregistré » générique (règle fondateur du 08/09/2026) ;
     * un envoi valide affiche la géométrie RÉSOLUE telle que le solveur la
       rend (jamais recalculée côté écran) ;
     * une chaîne en échec affiche le POINT DE RUPTURE nommé par le solveur
       (son `motif`), pas un message inventé ;
     * la cote manquante est nommée.
   ========================================================================== */

const RESULTAT = {
  releve: {
    id: 9,
    releve_le: '2026-09-18',
    notes: '',
    chaines: [],
    geometrie: {
      chaines: [
        {
          nom: 'Pignon nord',
          ok: true,
          motif: 'cote b DÉDUITE par fermeture (7.200 m) — à confirmer à l’exécution',
          somme: 12.4,
          total_mesure: 12.4,
          residu_m: 0.0,
          residu_pct: 0.0,
          tolerance_m: 0.3,
          positions: [0.0, 5.2, 12.4],
          cotes: [
            { nom: 'a', valeur: 5.2, statut: 'MESUREE', a_confirmer: false },
            { nom: 'b', valeur: 7.2, statut: 'A_CONFIRMER', a_confirmer: true },
          ],
        },
        {
          nom: 'Égout sud',
          ok: false,
          motif: 'fermeture NON tenue : résidu +0.500 m (+5.56 %) pour une tolérance de 0.050 m',
          somme: 9.55,
          total_mesure: 9.0,
          residu_m: 0.5,
          residu_pct: 5.56,
          tolerance_m: 0.05,
          positions: [],
          cotes: [
            { nom: 'c', valeur: 4.5, statut: 'MESUREE', a_confirmer: false },
            { nom: 'd', valeur: 5.05, statut: 'MESUREE', a_confirmer: false },
          ],
        },
      ],
      cotes_a_confirmer: ['Pignon nord / b'],
      toutes_fermees: false,
    },
    azimut: null,
    cotes_a_confirmer: ['Pignon nord / b'],
    photos: [],
    releve_par: 'tech.releve',
    created_at: '2026-09-18T09:12:00+01:00',
  },
  releves: [],
}

const releve = vi.fn()
const enregistrerReleve = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      releve: (...a) => releve(...a),
      enregistrerReleve: (...a) => enregistrerReleve(...a),
    },
  },
}))

const { default: PanneauReleve } = await import('./PanneauReleve')

const rendre = () => render(
  <MemoryRouter><PanneauReleve calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('CALX25 — la saisie des chaînes de cotes et de l’azimut', () => {
  it('monte une chaîne avec deux cotes par défaut, et l’azimut avec sa précision', () => {
    rendre()
    expect(screen.getByTestId('cal-releve-chaine-0')).toBeInTheDocument()
    expect(screen.getByTestId('cal-releve-chaine-0-cote-0')).toBeInTheDocument()
    expect(screen.getByTestId('cal-releve-chaine-0-cote-1')).toBeInTheDocument()
    expect(screen.getByTestId('cal-releve-champ-azimut_boussole_deg')).toBeInTheDocument()
    expect(screen.getByTestId('cal-releve-champ-precision_azimut_deg')).toBeInTheDocument()
  })

  it('ajoute une cote et une chaîne à la demande', () => {
    rendre()
    fireEvent.click(screen.getByTestId('cal-releve-chaine-0-ajouter-cote'))
    expect(screen.getByTestId('cal-releve-chaine-0-cote-2')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('cal-releve-ajouter-chaine'))
    expect(screen.getByTestId('cal-releve-chaine-1')).toBeInTheDocument()
  })
})

describe('CALX25 — une chaîne inconsistante est refusée AVANT tout envoi', () => {
  it('deux cotes manquantes dans une même chaîne : erreur SOUS la chaîne, aucun appel réseau', () => {
    rendre()
    // Les deux cotes par défaut restent VIDES : deux inconnues, une seule
    // équation — le noyau ne peut en déduire qu'une.
    fireEvent.click(screen.getByTestId('cal-releve-envoyer'))

    const erreur = screen.getByTestId('cal-releve-erreur-chaine-0')
    expect(erreur).toHaveTextContent('manquantes')
    expect(erreur.textContent).not.toMatch(/non enregistré/i)
    expect(screen.getByTestId('cal-releve-bandeau')).toBeInTheDocument()
    expect(enregistrerReleve).not.toHaveBeenCalled()
  })

  it('un azimut saisi sans sa précision est refusé, la précision pointée', () => {
    rendre()
    fireEvent.change(
      screen.getByTestId('cal-releve-champ-azimut_boussole_deg').querySelector('input'),
      { target: { value: '187' } },
    )
    // Les deux cotes de la chaîne par défaut sont comblées pour isoler le
    // refus sur l'azimut seul.
    fireEvent.change(
      screen.getByTestId('cal-releve-chaine-0-cote-0-valeur').querySelector('input'),
      { target: { value: '5.2' } },
    )
    fireEvent.change(
      screen.getByTestId('cal-releve-chaine-0-cote-1-valeur').querySelector('input'),
      { target: { value: '7.2' } },
    )
    fireEvent.click(screen.getByTestId('cal-releve-envoyer'))

    expect(screen.getByTestId('cal-releve-erreur-precision_azimut_deg'))
      .toHaveTextContent('précision')
    expect(enregistrerReleve).not.toHaveBeenCalled()
  })
})

describe('CALX25 — la géométrie résolue OU le point de rupture nommé', () => {
  const remplirChaineValide = () => {
    fireEvent.change(
      screen.getByTestId('cal-releve-chaine-0-cote-0-valeur').querySelector('input'),
      { target: { value: '5.2' } },
    )
    fireEvent.change(
      screen.getByTestId('cal-releve-chaine-0-cote-1-valeur').querySelector('input'),
      { target: { value: '7.2' } },
    )
  }

  it('une chaîne FERMÉE affiche ses positions, une chaîne EN ÉCHEC son motif', async () => {
    enregistrerReleve.mockResolvedValue({ data: RESULTAT })
    rendre()
    remplirChaineValide()
    fireEvent.click(screen.getByTestId('cal-releve-envoyer'))

    expect(await screen.findByTestId('cal-releve-resultat-chaine-0-fermee'))
      .toHaveTextContent('12.400')
    const rupture = screen.getByTestId('cal-releve-resultat-chaine-1-rupture')
    expect(rupture).toHaveTextContent(RESULTAT.releve.geometrie.chaines[1].motif)
  })

  it('la cote DÉDUITE est nommée « à confirmer »', async () => {
    enregistrerReleve.mockResolvedValue({ data: RESULTAT })
    rendre()
    remplirChaineValide()
    fireEvent.click(screen.getByTestId('cal-releve-envoyer'))

    expect(await screen.findByTestId('cal-releve-resultat-chaine-0-a-confirmer-b'))
      .toHaveTextContent('à confirmer')
  })

  it('le refus 400 du serveur (champ nommé) atterrit sous la bonne chaîne', async () => {
    enregistrerReleve.mockRejectedValue({
      response: { data: { 'chaines[0]': 'chaîne « Pignon nord » : une seule cote manquante peut être déduite par fermeture.' } },
    })
    rendre()
    remplirChaineValide()
    fireEvent.click(screen.getByTestId('cal-releve-envoyer'))

    expect(await screen.findByTestId('cal-releve-erreur-chaine-0'))
      .toHaveTextContent('une seule cote manquante')
  })
})
