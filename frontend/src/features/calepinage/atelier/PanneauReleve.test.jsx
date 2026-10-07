import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

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
const corrigerReleve = vi.fn()
const supprimerReleve = vi.fn()
const photos = vi.fn()
const layout = vi.fn()
const appliquerCoteReleve = vi.fn()
const enregistrerSectionLayout = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: (...a) => layout(...a),
      appliquerCoteReleve: (...a) => appliquerCoteReleve(...a),
      enregistrerSectionLayout: (...a) => enregistrerSectionLayout(...a),
      releve: (...a) => releve(...a),
      enregistrerReleve: (...a) => enregistrerReleve(...a),
      corrigerReleve: (...a) => corrigerReleve(...a),
      supprimerReleve: (...a) => supprimerReleve(...a),
      photos: (...a) => photos(...a),
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

/* ============================================================================
   ACAL205 — relire et préremplir le relevé courant ; « Enregistrer » CORRIGE
   ce relevé (PATCH), « Nouveau relevé » crée une ligne (POST). Les réponses
   viennent du contrat committé `calepinage_releve.json` (jamais tapées à la
   main).
   ========================================================================== */

describe('ACAL205 — le relevé courant est relu, corrigé, ou doublé', () => {
  const lectureContrat = () => {
    const reponse = reponseContrat('calepinage', 'calepinage_releve')
    // GET : l'historique et le courant (le POST porte en plus `releve`).
    return { data: { releves: reponse.data.releves, releve_courant_id: reponse.data.releve_courant_id } }
  }

  beforeEach(() => {
    releve.mockResolvedValue(lectureContrat())
    photos.mockResolvedValue(reponseContrat('calepinage', 'calepinage_photos'))
  })

  it('préremplit le relevé courant au montage', async () => {
    rendre()
    const courant = lectureContrat().data.releves[0]

    expect(await screen.findByDisplayValue(courant.releve_le)).toBeInTheDocument()
    expect(releve).toHaveBeenCalledWith(1)
    expect(screen.getByTestId('cal-releve-chaine-0-nom').querySelector('input').value)
      .toBe(courant.chaines[0].nom)
    expect(screen.getByDisplayValue(courant.notes)).toBeInTheDocument()
    expect(screen.getByTestId('cal-releve-historique')).toBeInTheDocument()
  })

  it('Enregistrer corrige le même relevé (PATCH)', async () => {
    corrigerReleve.mockResolvedValue({ data: { releve: lectureContrat().data.releves[0], releve_courant_id: 1 } })
    rendre()
    const courant = lectureContrat().data.releves[0]
    await screen.findByDisplayValue(courant.releve_le)

    fireEvent.click(screen.getByTestId('cal-releve-envoyer'))

    await waitFor(() => expect(corrigerReleve).toHaveBeenCalledTimes(1))
    expect(corrigerReleve.mock.calls[0][0]).toBe(1)
    expect(corrigerReleve.mock.calls[0][1]).toBe(lectureContrat().data.releve_courant_id)
    expect(enregistrerReleve).not.toHaveBeenCalled()
    expect(await screen.findByTestId('cal-releve-message')).toHaveTextContent('corrigé')
  })

  it('Nouveau relevé crée une ligne', async () => {
    enregistrerReleve.mockResolvedValue(reponseContrat('calepinage', 'calepinage_releve'))
    rendre()
    await screen.findByDisplayValue(lectureContrat().data.releves[0].releve_le)

    fireEvent.click(screen.getByTestId('cal-releve-nouveau'))

    await waitFor(() => expect(enregistrerReleve).toHaveBeenCalledTimes(1))
    expect(corrigerReleve).not.toHaveBeenCalled()
  })

  it('les photos du calepinage sont cochables et partent en photo_ids', async () => {
    corrigerReleve.mockResolvedValue({ data: { releve: lectureContrat().data.releves[0], releve_courant_id: 1 } })
    rendre()
    await screen.findByDisplayValue(lectureContrat().data.releves[0].releve_le)
    const premiere = reponseContrat('calepinage', 'calepinage_photos').data.photos[0]
    const case1 = await screen.findByTestId(`cal-releve-photo-${premiere.id}`)
    const etait = case1.checked

    fireEvent.click(case1)
    fireEvent.click(screen.getByTestId('cal-releve-envoyer'))

    await waitFor(() => expect(corrigerReleve).toHaveBeenCalled())
    const ids = corrigerReleve.mock.calls[0][2].photo_ids
    expect(ids.includes(premiere.id)).toBe(!etait)
  })

  it('Supprimer retire le relevé courant', async () => {
    const confirmation = vi.spyOn(window, 'confirm').mockReturnValue(true)
    supprimerReleve.mockResolvedValue({})
    rendre()
    await screen.findByDisplayValue(lectureContrat().data.releves[0].releve_le)
    releve.mockResolvedValue({ data: { releves: [], releve_courant_id: null } })

    fireEvent.click(screen.getByTestId('cal-releve-supprimer'))

    await waitFor(() => expect(supprimerReleve).toHaveBeenCalledWith(1, lectureContrat().data.releve_courant_id))
    expect(await screen.findByTestId('cal-releve-message')).toHaveTextContent('supprimé')
    confirmation.mockRestore()
  })

  it('sans relevé courant, le bouton crée (POST) et il n’y a ni Nouveau ni Supprimer', async () => {
    releve.mockResolvedValue({ data: { releves: [], releve_courant_id: null } })
    rendre()
    await waitFor(() => expect(releve).toHaveBeenCalled())

    expect(screen.queryByTestId('cal-releve-nouveau')).toBeNull()
    expect(screen.queryByTestId('cal-releve-supprimer')).toBeNull()
  })
})

/* ============================================================================
   ACAL207 (D-ACAL-28) — « Appliquer la cote au pan » : le dessinateur choisit le pan, le
   côté et une cote MESURÉE ; l'écran envoie {zone_id, cote_index, longueur_m} et le
   SERVEUR recale (aucune homothétie ici). Relevé du contrat `calepinage_releve.json`.
   ========================================================================== */
describe('ACAL207 — appliquer une cote du relevé à un côté du pan', () => {
  const PAN = { id: 'z1', label: 'Pan sud', vertices: [
    [-7.58986, 33.57306], [-7.58973, 33.57306], [-7.58973, 33.57313], [-7.58986, 33.57313],
  ] }

  beforeEach(() => {
    const reponse = reponseContrat('calepinage', 'calepinage_releve')
    releve.mockResolvedValue({ data: { releves: reponse.data.releves,
      releve_courant_id: reponse.data.releve_courant_id } })
    photos.mockResolvedValue({ data: { photos: [] } })
    layout.mockResolvedValue({ data: { roof_layout: { zones: [PAN] } } })
    appliquerCoteReleve.mockResolvedValue({ data: { roof_layout: { zones: [PAN] }, version: 6 } })
  })

  it('choisir le côté puis appliquer la cote envoie zone_id, cote_index et la mesure', async () => {
    const courant = reponseContrat('calepinage', 'calepinage_releve').data.releves[0]
    rendre()
    const panneau = await screen.findByTestId('cal-releve-appliquer-cote')
    expect(layout).toHaveBeenCalledWith(1)
    expect(panneau).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('cal-releve-cote-pan'), { target: { value: 'z1' } })
    // Quatre côtés, chacun avec sa longueur actuelle (lue par la projection partagée).
    const cotes = screen.getByTestId('cal-releve-cote-cote').querySelectorAll('option')
    expect(cotes).toHaveLength(5)
    expect(cotes[1].textContent).toMatch(/^Côté 0 → 1 \(\d+\.\d{2} m\)$/)
    fireEvent.change(screen.getByTestId('cal-releve-cote-cote'), { target: { value: '0' } })
    // La cote déduite « b » (à confirmer) n'est pas proposable.
    const options = [...screen.getByTestId('cal-releve-cote-mesure').querySelectorAll('option')]
    const deduite = options.find((o) => o.textContent.includes('/ b'))
    expect(deduite.disabled).toBe(true)
    const totalSud = options.find((o) => o.textContent.startsWith('Égout sud — total'))
    expect(totalSud.textContent).toContain('± 0.05 m')
    fireEvent.change(screen.getByTestId('cal-releve-cote-mesure'), { target: { value: totalSud.value } })

    fireEvent.click(screen.getByTestId('cal-releve-cote-appliquer'))

    await waitFor(() => expect(appliquerCoteReleve).toHaveBeenCalledWith(
      1, courant.id, { zone_id: 'z1', cote_index: 0, longueur_m: 9 }))
    expect(await screen.findByTestId('cal-releve-cote-retour'))
      .toHaveTextContent('Cote appliquée au côté 0 — nouvelle version (précision ± 0.05 m).')
  })

  it('un refus nommé du serveur s’affiche tel quel', async () => {
    appliquerCoteReleve.mockRejectedValue({ response: { status: 400, data: {
      zone_id: 'Le pan « z1 » est croisé : corrigez son contour avant d’appliquer une cote.' } } })
    rendre()
    await screen.findByTestId('cal-releve-appliquer-cote')
    fireEvent.change(screen.getByTestId('cal-releve-cote-pan'), { target: { value: 'z1' } })
    fireEvent.change(screen.getByTestId('cal-releve-cote-cote'), { target: { value: '1' } })
    const options = [...screen.getByTestId('cal-releve-cote-mesure').querySelectorAll('option')]
    fireEvent.change(screen.getByTestId('cal-releve-cote-mesure'),
      { target: { value: options.find((o) => o.textContent.startsWith('Pignon nord / a')).value } })
    fireEvent.click(screen.getByTestId('cal-releve-cote-appliquer'))

    expect(await screen.findByTestId('cal-releve-cote-retour'))
      .toHaveTextContent('Le pan « z1 » est croisé')
  })
})

/* ============================================================================
   ACAL206 (D-ACAL-28) — « Appliquer l'azimut au pan » : relevé du contrat
   `calepinage_releve.json` (azimut + précision), écriture par la primitive de section.
   ========================================================================== */
describe('ACAL206 — appliquer l’azimut du relevé à un pan', () => {
  const PAN_A = { id: 'zA', label: 'Pan A', pitchDeg: 22, facingAzimuthDeg: 90 }
  const PAN_B = { id: 'zB', label: 'Pan B', pitchDeg: 15, facingAzimuthDeg: 270 }

  beforeEach(() => {
    const reponse = reponseContrat('calepinage', 'calepinage_releve')
    releve.mockResolvedValue({ data: { releves: reponse.data.releves,
      releve_courant_id: reponse.data.releve_courant_id } })
    photos.mockResolvedValue({ data: { photos: [] } })
    layout.mockResolvedValue({ data: { roof_layout: { zones: [PAN_A, PAN_B] },
      empreinte_document: 'jeton-1' } })
    enregistrerSectionLayout.mockResolvedValue({ data: {
      roof_layout: { zones: [PAN_A, PAN_B] }, empreinte_document: 'jeton-2' } })
  })

  it('applique l’azimut au pan choisi et seulement à lui', async () => {
    const courant = reponseContrat('calepinage', 'calepinage_releve').data.releves[0]
    expect(courant.azimut.precision_deg).not.toBeNull()
    rendre()
    await screen.findByTestId('cal-releve-appliquer-azimut')
    expect(screen.getByTestId('cal-releve-azimut-mesure'))
      .toHaveTextContent(`${courant.azimut.deg}° ± ${courant.azimut.precision_deg}°`)
    // Jamais d'application automatique.
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()

    fireEvent.change(screen.getByTestId('cal-releve-azimut-pan'), { target: { value: 'zB' } })
    fireEvent.click(screen.getByTestId('cal-releve-azimut-appliquer'))

    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalledTimes(1))
    expect(enregistrerSectionLayout).toHaveBeenCalledWith(1, {
      cle: 'zones',
      zone_id: 'zB',
      champs: {
        facingAzimuthDeg: courant.azimut.deg,
        facingAzimuthSource: 'releve',
        facingAzimuthPrecisionDeg: courant.azimut.precision_deg,
      },
      base_empreinte: 'jeton-1',
    })
    expect(await screen.findByTestId('cal-releve-azimut-retour')).toHaveTextContent('Pan B')
  })

  it('atelier vivant : son jeton fait foi et la section rendue lui revient', async () => {
    // Lot 2 critique #24 / #31.
    const documentVivant = { empreinte: 'jeton-vivant', appliquerSection: vi.fn() }
    render(<MemoryRouter>
      <PanneauReleve calepinageId={1} documentVivant={documentVivant} />
    </MemoryRouter>)
    await screen.findByTestId('cal-releve-appliquer-azimut')
    fireEvent.change(screen.getByTestId('cal-releve-azimut-pan'), { target: { value: 'zA' } })
    fireEvent.click(screen.getByTestId('cal-releve-azimut-appliquer'))
    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalledTimes(1))
    expect(enregistrerSectionLayout.mock.calls[0][1].base_empreinte).toBe('jeton-vivant')
    await waitFor(() => expect(documentVivant.appliquerSection)
      .toHaveBeenCalledWith('zones', [PAN_A, PAN_B], 'jeton-2'))
  })

  it('lecture seule : le geste est désactivé et la raison dite', async () => {
    // Lot 2 critique #24.
    render(<MemoryRouter><PanneauReleve calepinageId={1} lectureSeule /></MemoryRouter>)
    await screen.findByTestId('cal-releve-appliquer-azimut')
    fireEvent.change(screen.getByTestId('cal-releve-azimut-pan'), { target: { value: 'zA' } })
    expect(screen.getByTestId('cal-releve-azimut-appliquer')).toBeDisabled()
    expect(screen.getByTestId('cal-releve-azimut-lecture-seule')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('cal-releve-azimut-appliquer'))
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()
  })

  it('sans précision déclarée, le bouton est absent', async () => {
    const reponse = reponseContrat('calepinage', 'calepinage_releve')
    const sansPrecision = { ...reponse.data.releves[0],
      azimut: { ...reponse.data.releves[0].azimut, precision_deg: null } }
    releve.mockResolvedValue({ data: { releves: [sansPrecision],
      releve_courant_id: sansPrecision.id } })
    rendre()
    await screen.findByTestId(`cal-releve-historique-${sansPrecision.id}`)
    await waitFor(() => expect(layout).toHaveBeenCalled())
    expect(screen.queryByTestId('cal-releve-appliquer-azimut')).toBeNull()
    expect(screen.queryByTestId('cal-releve-azimut-appliquer')).toBeNull()
  })

  it('un jeton périmé (409) est dit, sans rien écrire de plus', async () => {
    enregistrerSectionLayout.mockRejectedValue({ response: { status: 409, data: {
      code: 'document_modifie' } } })
    rendre()
    await screen.findByTestId('cal-releve-appliquer-azimut')
    fireEvent.change(screen.getByTestId('cal-releve-azimut-pan'), { target: { value: 'zA' } })
    fireEvent.click(screen.getByTestId('cal-releve-azimut-appliquer'))
    expect(await screen.findByTestId('cal-releve-azimut-retour'))
      .toHaveTextContent('a changé ailleurs')
  })
})
