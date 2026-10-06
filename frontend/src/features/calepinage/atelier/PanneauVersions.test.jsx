import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* ============================================================================
   CALX36 — HISTORIQUE DES VERSIONS ET RESTAURATION.
   ----------------------------------------------------------------------------
   Trois invariants du « Done » : la ligne courante (première de la liste,
   `selectors.versions` trie `-created_at`) est marquée et NON restaurable ;
   après restauration la liste s'allonge d'une entrée ; aucune version n'est
   jamais supprimée depuis l'interface (aucun bouton de suppression n'existe).
   ========================================================================== */

const versionsMock = vi.fn()
const restaurerVersion = vi.fn()
/* ACAL23 — doublure à la FRONTIÈRE RÉSEAU : `versions` et `restaurerVersion`
   sont pilotés par le test ; tout autre appel (l'atelier monté autour, dans le
   test d'intégration) rend une promesse résolue — même proxy permissif que
   `Rail.test.jsx`. */
vi.mock('../../../api/calepinageApi', () => {
  const reponse = () => Promise.resolve({ data: {} })
  const surcharges = {
    versions: (...a) => versionsMock(...a),
    restaurerVersion: (...a) => restaurerVersion(...a),
  }
  const doublure = () => new Proxy(function appel() { return reponse() }, {
    get: (_cible, prop) => {
      if (typeof prop === 'symbol' || prop === 'then') return undefined
      return surcharges[prop] ?? doublure()
    },
    apply: () => reponse(),
  })
  return { default: doublure() }
})
vi.mock('../../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))
vi.mock('../../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

const { default: PanneauVersions } = await import('./PanneauVersions')
const { default: AtelierPanneaux } = await import('../AtelierPanneaux')

const V_COURANTE = {
  id: 3, libelle: 'Version 3', layout_hash: 'abc', cree_le: '2026-09-21T09:00:00Z',
  cree_par: { id: 1, nom_complet: 'Reda' }, a_un_resultat: true,
}
const V_ANCIENNE = {
  id: 2, libelle: 'Version 2', layout_hash: 'def', cree_le: '2026-09-20T09:00:00Z',
  cree_par: { id: 1, nom_complet: 'Reda' }, a_un_resultat: false,
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

const rendre = (props = {}) => render(
  <MemoryRouter><PanneauVersions calepinageId={5} {...props} /></MemoryRouter>,
)

describe('CALX36 — la version courante', () => {
  it('est la PREMIÈRE de la liste, marquée, et SANS bouton restaurer', async () => {
    versionsMock.mockResolvedValue({ data: [V_COURANTE, V_ANCIENNE] })
    rendre()

    expect(await screen.findByTestId('cal-versions-courante-3')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-versions-restaurer-3')).not.toBeInTheDocument()
    // L'ancienne, elle, propose bien de restaurer.
    expect(screen.getByTestId('cal-versions-restaurer-2')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-versions-courante-2')).not.toBeInTheDocument()
  })

  it('aucun bouton de suppression n’existe nulle part', async () => {
    versionsMock.mockResolvedValue({ data: [V_COURANTE, V_ANCIENNE] })
    rendre()
    await screen.findByTestId('cal-versions-ligne-3')
    expect(screen.queryByText(/[Ss]upprimer/)).not.toBeInTheDocument()
  })
})

describe('CALX36 — restaurer une version', () => {
  it('exige une confirmation en DEUX temps avant l’appel réseau', async () => {
    versionsMock.mockResolvedValue({ data: [V_COURANTE, V_ANCIENNE] })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-versions-restaurer-2'))

    expect(await screen.findByTestId('cal-versions-confirmer-2')).toBeInTheDocument()
    expect(restaurerVersion).not.toHaveBeenCalled()

    fireEvent.click(screen.getByTestId('cal-versions-annuler-2'))
    expect(screen.queryByTestId('cal-versions-confirmer-2')).not.toBeInTheDocument()
    expect(restaurerVersion).not.toHaveBeenCalled()
  })

  it('après restauration, la liste s’allonge d’une entrée (rechargée depuis le serveur)', async () => {
    const V_NEUVE = {
      id: 4, libelle: 'Version 4', layout_hash: 'def', cree_le: '2026-09-21T10:00:00Z',
      cree_par: { id: 1, nom_complet: 'Reda' }, a_un_resultat: false,
    }
    // Les DEUX réponses sont posées AVANT toute interaction : la seconde
    // (après restauration) ne dépend d'aucun minutage de microtâches.
    restaurerVersion.mockResolvedValue({ data: { restauree: 2, version: 4 } })
    versionsMock
      .mockResolvedValueOnce({ data: [V_COURANTE, V_ANCIENNE] })
      .mockResolvedValueOnce({ data: [V_NEUVE, V_COURANTE, V_ANCIENNE] })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-versions-restaurer-2'))
    fireEvent.click(await screen.findByTestId('cal-versions-confirmer-2'))

    await waitFor(() => expect(restaurerVersion).toHaveBeenCalledWith(5, 2))
    await waitFor(() => expect(versionsMock).toHaveBeenCalledTimes(2))
    expect(await screen.findByTestId('cal-versions-courante-4')).toBeInTheDocument()
    expect(screen.getByTestId('cal-versions-ligne-3')).toBeInTheDocument()
    expect(screen.getByTestId('cal-versions-ligne-2')).toBeInTheDocument()
  })
})

describe('CALX36 — historique vide', () => {
  it('affiche un état vide explicite', async () => {
    versionsMock.mockResolvedValue({ data: [] })
    rendre()
    expect(await screen.findByText('Aucune version pour l’instant')).toBeInTheDocument()
  })
})

/* ACAL23 — APRÈS une restauration, la scène 3D relit le document restauré :
   le Rail relaie `onRecharger` (l'unique rechargement de l'atelier, qui relit
   design-context et `GET layout/`) jusqu'au panneau. Sans ce relais, « Enregistrer
   le calepinage » republiait la copie d'avant et annulait la restauration. */
describe('ACAL23 — restauration et rechargement de la scène', () => {
  const rendreAtelier = (onRecharger) => render(
    <MemoryRouter initialEntries={['/calepinage/5?onglet=versions']}>
      <Routes>
        <Route
          path="/calepinage/:id"
          element={(
            <AtelierPanneaux
              calepinageId={5}
              contexte={{ cible: null, calepinage: null }}
              onRecharger={onRecharger}
            />
          )}
        />
      </Routes>
    </MemoryRouter>,
  )

  it('restauration confirmée → GET layout/ relu et scène ré-hydratée (onRecharger relayé par le Rail)', async () => {
    versionsMock.mockResolvedValue({ data: [V_COURANTE, V_ANCIENNE] })
    restaurerVersion.mockResolvedValue({ data: { restauree: 2, version: 4 } })
    const onRecharger = vi.fn()
    rendreAtelier(onRecharger)

    fireEvent.click(await screen.findByTestId('cal-versions-restaurer-2'))
    expect(onRecharger).not.toHaveBeenCalled()
    fireEvent.click(await screen.findByTestId('cal-versions-confirmer-2'))

    await waitFor(() => expect(restaurerVersion).toHaveBeenCalledWith(5, 2))
    await waitFor(() => expect(onRecharger).toHaveBeenCalledTimes(1))
  })

  it('409 verrou → message du serveur affiché, et aucun rechargement', async () => {
    versionsMock.mockResolvedValue({ data: [V_COURANTE, V_ANCIENNE] })
    restaurerVersion.mockRejectedValue({
      response: {
        status: 409,
        data: { roof_layout: ['Ce calepinage est verrouillé : son devis lié a été envoyé.'] },
      },
    })
    const onRecharger = vi.fn()
    rendreAtelier(onRecharger)

    fireEvent.click(await screen.findByTestId('cal-versions-restaurer-2'))
    fireEvent.click(await screen.findByTestId('cal-versions-confirmer-2'))

    expect(await screen.findByTestId('cal-versions-erreur'))
      .toHaveTextContent('Ce calepinage est verrouillé : son devis lié a été envoyé.')
    expect(onRecharger).not.toHaveBeenCalled()
  })

  it('refus {detail} → le détail du serveur, jamais le texte générique', async () => {
    versionsMock.mockResolvedValue({ data: [V_COURANTE, V_ANCIENNE] })
    restaurerVersion.mockRejectedValue({
      response: { status: 409, data: { detail: 'Version détachée de ce calepinage.' } },
    })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-versions-restaurer-2'))
    fireEvent.click(await screen.findByTestId('cal-versions-confirmer-2'))
    expect(await screen.findByTestId('cal-versions-erreur'))
      .toHaveTextContent('Version détachée de ce calepinage.')
  })
})
