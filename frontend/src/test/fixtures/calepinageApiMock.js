/* ACAL345 — LA doublure de `api/calepinageApi` des tests d'écrans calepinage,
   au lieu d'un `vi.mock` recopié dans chaque fichier (terrain, ombrière,
   horizon, réglages). Usage, dans le fichier de test :

     import { espions } from '../../../test/fixtures/calepinageApiMock'
     vi.mock('../../../api/calepinageApi', async () =>
       (await import('../../../test/fixtures/calepinageApiMock')).apiDocument({ moteur: true }))

   Les espions vivent dans CE module : vitest isole le registre de modules par
   fichier de test, ils ne fuient donc jamais d'un fichier à l'autre, et
   `vi.clearAllMocks()` les remet à zéro comme n'importe quel `vi.fn()`. */
import { expect, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { exempleContrat } from './contractSamples'

export const espions = {
  layout: vi.fn(),
  get: vi.fn(),
  enregistrerLayoutCalepinage: vi.fn(),
  enregistrerSectionLayout: vi.fn(),
  horizon: vi.fn(),
  pose: vi.fn(),
  getParametres: vi.fn(),
  putParametres: vi.fn(),
  recalculer: vi.fn(),
  hasPermission: vi.fn(),
}

/* Un relais plutôt que l'espion lui-même : la doublure reste valable si un
   test remplace l'implémentation de l'espion. */
const relais = (nom) => (...a) => espions[nom](...a)

/** Lecture/écriture du document (`calepinages.*`), + `moteur.pose` / `horizon` sur demande. */
export function apiDocument({ moteur = false, horizon = false } = {}) {
  const calepinages = {
    layout: relais('layout'),
    // ACAL251 — le détail (`contexte_geographique`) : repli de latitude des onglets.
    get: relais('get'),
    enregistrerLayoutCalepinage: relais('enregistrerLayoutCalepinage'),
    enregistrerSectionLayout: relais('enregistrerSectionLayout'),
  }
  if (horizon) calepinages.horizon = relais('horizon')
  const api = { calepinages }
  if (moteur) api.moteur = { pose: relais('pose') }
  return { default: api }
}

/**
 * ENF19 — la réponse de `calepinages.layout` pour un SITE REPÉRÉ (épingle GPS
 * posée), pan actif `z1` : les suites « course du soleil » en montaient chacune
 * la leur, à l'identique. `extra` ajoute les clés propres au test (`scene`,
 * `horizonProfile`, `environment`, `buildings`…).
 */
export function reponseLayoutSite(zones, extra = {}) {
  return {
    data: { roof_layout: { pin: { lat: 33.6, lng: -7.6 }, activeAreaId: 'z1', zones, ...extra } },
  }
}

/**
 * ENF19 — `calepinages.*` relayés vers des espions PROPRES au fichier de test
 * (`{ nom: vi.fn() }`) : pour les suites qui pilotent leurs propres appels
 * (photos de site, calage). `extra` ajoute les autres familles de la doublure
 * (`parametres`, `moteur`…). Les espions sont lus à l'appel : la fabrique reste
 * valable même si le fichier les déclare après le `vi.mock` hissé.
 */
export function apiCalepinages(espionsLocaux, extra = {}) {
  const calepinages = {}
  for (const [nom, espion] of Object.entries(espionsLocaux)) {
    calepinages[nom] = (...a) => espion(...a)
  }
  return { default: { calepinages, ...extra } }
}

/** Les réglages société (`parametres.*`), + `recalculerSimulations` sur demande. */
export function apiParametres({ recalculer = false } = {}) {
  const parametres = { get: relais('getParametres'), update: relais('putParametres') }
  if (recalculer) parametres.recalculerSimulations = relais('recalculer')
  return { default: { parametres } }
}

/** La doublure de `hooks/useHasPermission`, pilotée par `espions.hasPermission`. */
export function permissionMock() {
  return { useHasPermission: (code) => espions.hasPermission(code) }
}

/* ── La réponse du moteur de pose : l'exemple COMMITTÉ du contrat `pose.json`
   (PACT10/13 : un mock écrit à la main est une deuxième source de vérité). */
export const REPONSE_POSE = exempleContrat('calepinage', 'pose')
/** Le pas inter-rangées, MESURÉ sur les rangées de l'exemple — jamais retapé. */
export const PAS_REPONSE_POSE = REPONSE_POSE.plans[0].rangees[1].y0 - REPONSE_POSE.plans[0].rangees[0].y0
/** L'emprise totale des tables de l'exemple, par la même formule que `empriseTablesM2`. */
export const EMPRISE_REPONSE_POSE = REPONSE_POSE.plans[0].tables.reduce(
  (acc, t) => acc + Math.abs(t.x1 - t.x0) * Math.abs(t.y1 - t.y0), 0,
)

/* ── Assertions communes aux deux écrans de surface de pose ──────────────── */

/** L'écriture est UNE section `poseSurfaces` (jamais le document entier). */
export function verifierSectionEcrite({ id, kind }) {
  const [idEcrit, corps] = espions.enregistrerSectionLayout.mock.calls[0]
  expect(idEcrit).toBe(id)
  expect(Object.keys(corps).sort()).toEqual(['base_empreinte', 'cle', 'valeur'])
  expect(corps.cle).toBe('poseSurfaces')
  expect(corps.base_empreinte).toBe('E0')
  expect(corps.valeur).toHaveLength(1)
  expect(corps.valeur[0].kind).toBe(kind)
  expect(espions.enregistrerLayoutCalepinage).not.toHaveBeenCalled() // aucun document entier
}

/** Lecture en échec → Enregistrer désactivé, message affiché, aucun POST. */
export async function verifierLectureEnEchec({ monter, prefixe }) {
  espions.layout.mockRejectedValue(new Error('500'))
  monter()
  expect(await screen.findByRole('alert'))
    .toHaveTextContent('Conception illisible : rien n’est enregistré')
  const bouton = screen.getByTestId(`${prefixe}-enregistrer`)
  expect(bouton).toBeDisabled()
  fireEvent.click(bouton)
  expect(espions.enregistrerSectionLayout).not.toHaveBeenCalled()
  expect(espions.enregistrerLayoutCalepinage).not.toHaveBeenCalled()
}

/** Calculer puis enregistrer ; la section écrite est poussée dans l'atelier vivant. */
export async function verifierSectionPousseeDansAtelier({ documentVivant, prefixe, kind }) {
  fireEvent.click(screen.getByTestId(`${prefixe}-calculer`))
  await waitFor(() => expect(espions.pose).toHaveBeenCalled())
  fireEvent.click(screen.getByTestId(`${prefixe}-enregistrer`))
  await waitFor(() => expect(documentVivant.appliquerSection).toHaveBeenCalledTimes(1))
  expect(espions.enregistrerSectionLayout.mock.calls[0][1].base_empreinte).toBe('EATELIER')
  const [cle, valeur, empreinte] = documentVivant.appliquerSection.mock.calls[0]
  expect(cle).toBe('poseSurfaces')
  expect(valeur[0].kind).toBe(kind)
  expect(empreinte).toBe('E1')
}
