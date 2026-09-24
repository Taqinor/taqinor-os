import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* ============================================================================
   CALX397 — SAVOIR QUELS ONGLETS SONT RÉELLEMENT OUVERTS.
   ----------------------------------------------------------------------------
   Au montage d'un onglet, le rail emprunte le chemin EXISTANT
   `GET /uxviews/saved-views/?ecran=calepinage:<cle>` (seul chemin d'écriture
   de `uxviews.EcranRecent`, NTUX39) — aucun modèle, aucun endpoint neuf.

   Ce fichier prouve :
     * UN appel par ouverture d'onglet, avec la CLÉ du registre (jamais un
       libellé traduit, jamais une donnée du calepinage) ;
     * ZÉRO appel à la ré-ouverture du même onglet dans la même session ;
     * aucun appel sans onglet ouvert ;
     * l'onglet s'affiche à l'identique quand l'appel échoue, sans le toast
       d'erreur global (`suppressErrorToast`).

   L'instance axios est doublée : seuls les appels vers `saved-views` sont
   comptés (un panneau peut en émettre d'autres, ils ne concernent pas ce
   test). L'API du module est le même proxy permissif que `Rail.test.jsx`.
   ========================================================================== */

const mocks = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('../../../api/axios', () => {
  const reponse = () => Promise.resolve({ data: {} })
  const doublure = () => new Proxy(function appel() { return reponse() }, {
    get: (_cible, prop) => (typeof prop === 'symbol' || prop === 'then'
      ? undefined
      : doublure()),
    apply: () => reponse(),
  })
  const racine = new Proxy(function appel() { return reponse() }, {
    get: (_cible, prop) => {
      if (prop === 'get') return (...a) => mocks.get(...a)
      return typeof prop === 'symbol' || prop === 'then' ? undefined : doublure()
    },
    apply: () => reponse(),
  })
  return { default: racine }
})

vi.mock('../../../api/calepinageApi', () => {
  const reponse = () => Promise.resolve({ data: {} })
  const doublure = () => new Proxy(function appel() { return reponse() }, {
    // `then` DOIT rester absent : un proxy « thenable » serait attendu comme
    // une promesse par `await` et bloquerait le test.
    get: (_cible, prop) => (typeof prop === 'symbol' || prop === 'then'
      ? undefined
      : doublure()),
    apply: () => reponse(),
  })
  return { default: doublure() }
})
vi.mock('../../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))

import Rail from './Rail'
import { ONGLETS, PARAM_ONGLET, ongletParCle } from './onglets'

const URL_VUES = '/uxviews/saved-views/'

const rendreRail = (recherche = '') => render(
  <MemoryRouter initialEntries={[`/calepinage/7${recherche}`]}>
    <Routes>
      <Route path="/calepinage/:id" element={<Rail />} />
    </Routes>
  </MemoryRouter>,
)

/** Les écrans signalés, dans l'ordre des appels vers `saved-views`. */
const ecransSignales = () => mocks.get.mock.calls
  .filter(([url]) => url === URL_VUES)
  .map(([, config]) => config?.params?.ecran)

/* Deux onglets du registre, lus par leur clé (jamais par leur rang) : si
   l'un disparaît, le test le DIT au lieu de viser un autre panneau. */
const onglet = (cle) => {
  const trouve = ongletParCle(cle)
  expect(trouve, `l’onglet « ${cle} » a disparu du registre`).toBeTruthy()
  return trouve
}

beforeEach(() => {
  mocks.get.mockReset()
  mocks.get.mockResolvedValue({ data: [] })
  window.sessionStorage.clear()
})
afterEach(() => { cleanup() })

describe('CALX397 — la mesure d’usage des onglets', () => {
  it('sans onglet ouvert, aucun appel', async () => {
    rendreRail()
    await Promise.resolve()
    expect(ecransSignales()).toEqual([])
  })

  it('un onglet ouvert au chargement est signalé UNE fois, par sa clé', async () => {
    const versions = onglet('versions')
    rendreRail(`?${PARAM_ONGLET}=${versions.cle}`)
    await waitFor(() => expect(ecransSignales()).toEqual([`calepinage:${versions.cle}`]))
    const [, config] = mocks.get.mock.calls.find(([url]) => url === URL_VUES)
    expect(config.suppressErrorToast).toBe(true)
    // Seule la CLÉ part : ni le libellé traduit, ni l'identifiant du calepinage.
    expect(Object.keys(config.params)).toEqual(['ecran'])
    expect(config.params.ecran).not.toContain(versions.libelle)
    expect(config.params.ecran).not.toContain('7')
  })

  it('UN appel par ouverture, ZÉRO à la ré-ouverture dans la même session', async () => {
    const utilisateur = userEvent.setup()
    const versions = onglet('versions')
    const activite = onglet('activite')
    rendreRail()

    await utilisateur.click(screen.getByTestId(`cal-onglet-${versions.cle}`))
    await waitFor(() => expect(ecransSignales()).toEqual([`calepinage:${versions.cle}`]))

    await utilisateur.click(screen.getByTestId(`cal-onglet-${activite.cle}`))
    await waitFor(() => expect(ecransSignales()).toEqual([
      `calepinage:${versions.cle}`, `calepinage:${activite.cle}`,
    ]))

    await utilisateur.click(screen.getByTestId(`cal-onglet-${versions.cle}`))
    await waitFor(() => expect(screen.getByTestId(`cal-onglet-${versions.cle}`))
      .toHaveAttribute('aria-selected', 'true'))
    expect(ecransSignales()).toHaveLength(2)
  })

  it('la même session survit au démontage du rail', async () => {
    const versions = onglet('versions')
    rendreRail(`?${PARAM_ONGLET}=${versions.cle}`)
    await waitFor(() => expect(ecransSignales()).toHaveLength(1))
    cleanup()
    rendreRail(`?${PARAM_ONGLET}=${versions.cle}`)
    await screen.findByTestId('cal-onglet-panneau')
    expect(ecransSignales()).toHaveLength(1)
  })

  it('un échec de l’appel ne change rien à l’affichage de l’onglet', async () => {
    mocks.get.mockImplementation((url) => (url === URL_VUES
      ? Promise.reject(new Error('réseau coupé'))
      : Promise.resolve({ data: [] })))
    const versions = onglet('versions')
    rendreRail(`?${PARAM_ONGLET}=${versions.cle}`)
    await waitFor(() => expect(ecransSignales()).toHaveLength(1))
    const panneau = await screen.findByTestId('cal-onglet-panneau')
    expect(panneau).toBeInTheDocument()
    expect(screen.queryByTestId('cal-onglet-erreur')).toBeNull()
    expect(screen.getByTestId(`cal-onglet-${versions.cle}`))
      .toHaveAttribute('aria-selected', 'true')
  })

  it('chaque clé du registre tient dans un écran `uxviews` (80 caractères)', () => {
    for (const entree of ONGLETS) {
      expect(`calepinage:${entree.cle}`.length, entree.cle).toBeLessThanOrEqual(80)
    }
  })
})
