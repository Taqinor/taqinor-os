import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CAL37 — l'emplacement des panneaux de l'atelier en mode calepinage.

   Ce que ce fichier prouve :
   1. le panneau affiche la CIBLE servie par le serveur, et « non renseignée »
      quand elle vaut `null` — jamais une puissance inventée ;
   2. une conception en LECTURE SEULE ne propose aucune écriture ;
   3. ACAL42 — le bandeau de lecture seule affiche le motif du SERVEUR
      (`raison_lecture_seule`) ; « Déverrouiller » n'existe plus, le seul geste
      est « Réviser (v2) » de `BoutonDevis`.

   SOLMVP15 — les deux essais du bouton « Reprendre le contour de l'affaire »
   (CAL242, sens CAL240) sont partis avec lui : son endpoint n'existe plus,
   l'app d'appels d'offres sortant du produit.
   ========================================================================== */

/* CALX27 — le droit est PILOTÉ par le test : `AtelierPanneaux` lit désormais
   `calepinage_gerer` (le code EXACT de la garde serveur). Sans ce double, le
   hook irait chercher le store redux, qu'aucun de ces rendus ne monte. */
const mocks = vi.hoisted(() => ({ hasPermission: vi.fn(() => false) }))
vi.mock('../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => mocks.hasPermission(code),
}))

vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      get: vi.fn(),
      genererDevis: vi.fn(),
      syncDevis: vi.fn(),
    },
    // CAL70 — PanneauAllees (monté ici, emplacement CAL37) lit les réglages
    // société et interroge le moteur ; sans double par défaut, la promesse
    // non résolue laisse `.get`/`.calculer` undefined et casse CE fichier.
    parametres: { get: vi.fn().mockResolvedValue({ data: { degagements: {} } }) },
    moteur: { calculer: vi.fn() },
  },
}))
vi.mock('../../api/crmApi', () => ({
  default: { getRoofFootprint: vi.fn(), lancerRechercheEmprise: vi.fn(), getRechercheEmprise: vi.fn() },
}))
vi.mock('../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))

import calepinageApi from '../../api/calepinageApi'
import crmApi from '../../api/crmApi'
import { fireEvent } from '@testing-library/react'
import AtelierPanneaux from './AtelierPanneaux'
import { conceptionAuto, contourLngLat } from './atelier/conceptionAuto'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CTX_VIDE = exempleContrat('calepinage', 'calepinage_design_context',
  'exemple_vide')
const DETAIL = exempleContrat('calepinage', 'calepinage_detail')

const rendre = (props = {}) => render(
  <MemoryRouter>
    <AtelierPanneaux calepinageId={CTX.calepinage.id} contexte={CTX} {...props} />
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  calepinageApi.calepinages.get.mockResolvedValue({ data: DETAIL })
  // Par défaut : SANS le droit de gérer — l'affordance d'écriture est l'exception.
  mocks.hasPermission.mockReturnValue(false)
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AtelierPanneaux (CAL37)', () => {
  it('affiche la cible SERVIE et le lien contextuel vers le comparatif', async () => {
    rendre()

    expect(screen.getByTestId('cal-cible-panneaux'))
      .toHaveTextContent(String(CTX.cible.panneaux))
    expect(screen.getByTestId('cal-lien-variantes'))
      .toHaveAttribute('href', `/calepinage/${CTX.calepinage.id}?onglet=variantes`)
  })

  it('cible nulle : « non renseignée », et l’écran le DIT', async () => {
    rendre({ contexte: CTX_VIDE, calepinageId: CTX_VIDE.calepinage.id })

    expect(screen.getByTestId('cal-cible-panneaux'))
      .toHaveTextContent('non renseignée')
    expect(screen.getByRole('status'))
      .toHaveTextContent('Aucune cible de puissance connue')
  })

  it('ACAL942 — empreinte changée : le détail est relu (fiche « Oui » sans F5)', async () => {
    const { rerender } = rendre()
    await waitFor(() => expect(calepinageApi.calepinages.get).toHaveBeenCalledTimes(1))

    const apres = {
      ...CTX, geometrie: { ...CTX.geometrie, empreinte_document: 'f'.repeat(64) },
    }
    rerender(
      <MemoryRouter>
        <AtelierPanneaux calepinageId={CTX.calepinage.id} contexte={apres} />
      </MemoryRouter>,
    )

    await waitFor(() => expect(calepinageApi.calepinages.get).toHaveBeenCalledTimes(2))
  })

  it('lecture seule : aucune écriture proposée', async () => {
    rendre({ lectureSeule: true })

    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-bouton-devis')).toBeNull()
    // Le panneau LUI-MÊME reste : consulter une conception figée est le but.
    expect(screen.getByTestId('cal-lien-variantes')).toBeTruthy()
  })
})

/* ============================================================================
   ACAL42 — LE BANDEAU FIGÉ : MOTIF SERVEUR, « RÉVISER (V2) », AUCUN DÉVERROUILLER.
   ========================================================================== */
describe('ACAL42 — bandeau de lecture seule', () => {
  it('bandeau figé : motif serveur et Réviser (v2), aucun Déverrouiller', async () => {
    mocks.hasPermission.mockReturnValue(true)
    const contexte = {
      ...CTX, modifiable: false,
      raison_lecture_seule: 'Devis accepté : révisez-le',
      revision_possible: true,
    }
    rendre({ contexte, lectureSeule: true })

    expect(screen.getByTestId('cal-bandeau-lecture-seule-raison'))
      .toHaveTextContent('Devis accepté : révisez-le')
    expect(screen.queryByTestId('cal-deverrouiller')).toBeNull()
    expect(screen.queryByText(/Déverrouiller/)).toBeNull()
    expect(await screen.findByTestId('cal-devis-reviser-lecture-seule'))
      .toHaveTextContent('Réviser (v2)')
  })

  it('conception ouverte : aucun bandeau', async () => {
    rendre()
    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-bandeau-lecture-seule')).toBeNull()
  })
})

/* =====================================================================  })
})

   ACAL415 — les outils et onglets de l'atelier dans la palette ⌘K.
   ========================================================================== */
describe('ACAL415 — commandes ⌘K de l’atelier', () => {
  const ecouter = () => {
    const recus = []
    const onEvt = (e) => recus.push(e.detail.actions)
    window.addEventListener('taqinor:lead-workspace-actions', onEvt)
    return { recus, fin: () => window.removeEventListener('taqinor:lead-workspace-actions', onEvt) }
  }

  it('l’atelier poste ses commandes puis les retire au démontage', async () => {
    const { recus, fin } = ecouter()
    const outilObstacle = vi.fn()
    const { unmount } = rendre({ builderApi: { raccourcis: { outilObstacle } } })

    const actions = recus.at(-1)
    expect(actions.some((a) => a.label === 'Ouvrir Horizon lointain')).toBe(true)
    const obstacle = actions.find((a) => a.label === 'Ajouter un obstacle')
    obstacle.run()
    expect(outilObstacle).toHaveBeenCalledTimes(1)

    unmount()
    expect(recus.at(-1)).toEqual([])
    fin()
  })

  it('lecture seule : aucun outil d’édition proposé, les onglets restent', async () => {
    const { recus, fin } = ecouter()
    rendre({ lectureSeule: true, builderApi: { raccourcis: { outilObstacle: vi.fn(), outilMesure: vi.fn() } } })

    const labels = recus.at(-1).map((a) => a.label)
    expect(labels).not.toContain('Ajouter un obstacle')
    expect(labels).toContain('Mesurer une distance')
    expect(labels).toContain('Ouvrir Horizon lointain')
    fin()
  })
})

/* ACAL421 — « Conception automatique » : {lat, lng} servis → [lng, lat] attendus par le builder. */
describe('ACAL421 — conception automatique', () => {
  it('le chemin OSM fermé (dernier nœud = premier) donne un contour sans sommet répété (rejeu runner 44905036243)', () => {
    const p = [{ lat: 33.5, lng: -7.6 }, { lat: 33.5, lng: -7.59 }, { lat: 33.51, lng: -7.59 }, { lat: 33.51, lng: -7.59 }, { lat: 33.5, lng: -7.6 }]
    expect(contourLngLat(p)).toEqual([[-7.6, 33.5], [-7.59, 33.5], [-7.59, 33.51]])
  })
  const POLYGONE = [{ lat: 33.5, lng: -7.6 }, { lat: 33.5, lng: -7.59 }, { lat: 33.51, lng: -7.59 }]
  const builder = (zones = []) => ({
    serializeLayout: vi.fn(() => ({ zones })),
    ajouterPanDepuisContour: vi.fn(() => ({ ok: true, id: 'area-2' })),
  })

  it('emprise convertie en [lng, lat], pan vide remplacé, refus nommé sans emprise', async () => {
    mocks.hasPermission.mockReturnValue(true)
    const builderApi = builder()
    // Décision fondateur 21/11 : tâche de fond — « en cours » affiché pendant la recherche.
    let finir
    crmApi.lancerRechercheEmprise.mockReturnValueOnce(new Promise((r) => { finir = r }))
    rendre({ builderApi })
    fireEvent.click(await screen.findByTestId('cal-conception-auto'))
    expect(await screen.findByTestId('cal-conception-auto-message')).toHaveTextContent('Recherche du bâtiment en cours…')
    expect(screen.getByTestId('cal-conception-auto')).toBeDisabled()
    const pret = exempleContrat('crm', 'lead_emprise_recherche')
    finir({ data: { ...pret, polygon: POLYGONE } })
    await waitFor(() => expect(builderApi.ajouterPanDepuisContour).toHaveBeenCalledTimes(1))
    expect(crmApi.lancerRechercheEmprise).toHaveBeenCalledWith(CTX.calepinage.lead)
    expect(builderApi.ajouterPanDepuisContour.mock.calls[0][0])
      .toEqual([[-7.6, 33.5], [-7.59, 33.5], [-7.59, 33.51]])

    crmApi.lancerRechercheEmprise.mockResolvedValueOnce(reponseContrat('crm', 'lead_emprise_recherche', 'exemple_refus'))
    fireEvent.click(await screen.findByTestId('cal-conception-auto'))
    expect(await screen.findByTestId('cal-conception-auto-message'))
      .toHaveTextContent("OpenStreetMap n'a pas répondu")
    expect(builderApi.ajouterPanDepuisContour).toHaveBeenCalledTimes(1)
  })

  it('suit le statut de la tâche de fond jusqu’au contour, borné à 90 s, sans vraie pause', async () => {
    const enCours = exempleContrat('crm', 'lead_emprise_recherche', 'exemple_vide')
    const pret = exempleContrat('crm', 'lead_emprise_recherche')
    const attendre = vi.fn(() => Promise.resolve())
    crmApi.lancerRechercheEmprise.mockResolvedValueOnce({ data: enCours })
    crmApi.getRechercheEmprise.mockResolvedValueOnce({ data: enCours }).mockResolvedValueOnce({ data: pret })
    const builderApi = builder()
    const r = await conceptionAuto(7, builderApi, { attendre })
    expect(r).toEqual({ ok: true, message: 'Contour posé : le toit est rempli.' })
    expect(crmApi.getRechercheEmprise).toHaveBeenCalledWith(enCours.job_id)
    expect(attendre).toHaveBeenCalledTimes(2)

    crmApi.lancerRechercheEmprise.mockResolvedValueOnce({ data: enCours })
    crmApi.getRechercheEmprise.mockResolvedValue({ data: enCours })
    const borne = await conceptionAuto(7, builder(), { attendre })
    expect(borne.ok).toBe(false)
    expect(borne.message).toMatch(/trop de temps/)
    expect(attendre).toHaveBeenCalledTimes(2 + 45)
  })

  it('bouton absent : pan déjà tracé, lecture seule', async () => {
    rendre({ builderApi: builder([{ vertices: POLYGONE.map((p) => [p.lng, p.lat]) }]) })
    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-conception-auto')).toBeNull()
    cleanup()
    rendre({ builderApi: builder(), lectureSeule: true })
    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-conception-auto')).toBeNull()
  })
})
