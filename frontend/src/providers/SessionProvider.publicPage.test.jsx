import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* Bug corrigé — la modale « Session expirée » s'ouvrait sur une page PUBLIQUE.
   ----------------------------------------------------------------------------
   L'intercepteur d'`api/axios.js` traitait TOUT enchaînement « 401 puis refresh
   en échec » comme une session expirée, sans jamais vérifier qu'une session
   existait au départ. Sur une vitrine publique (ex. `/ui`, sans backend), les
   providers globaux montés dans `main.jsx` émettent des appels authentifiés dès
   le montage → 401 → la modale s'ouvrait par-dessus toute la page et son
   overlay Radix (`data-state="open"`) bloquait TOUS les clics.

   Ces tests prouvent les deux moitiés : un 401 SANS session n'ouvre PAS la
   modale, et un 401 AVEC session l'ouvre TOUJOURS (la vraie protection est
   intacte). Le scénario est joué de bout en bout : vraie instance axios, vrai
   SessionProvider, vrai store. */

// Le refresh silencieux ÉCHOUE — c'est exactement le chemin « 401 non
// rejouable » qui menait à `emitSessionExpired()`.
vi.mock('../api/refreshCoordinator', () => ({
  refreshSession: vi.fn(() => Promise.reject(new Error('refresh KO'))),
  default: vi.fn(() => Promise.reject(new Error('refresh KO'))),
}))

const { default: api } = await import('../api/axios')
const { brancherSourceDeSession } = await import('./session-bridge')
const { SessionProvider } = await import('./SessionProvider')
const { default: authReducer, setCredentials } = await import(
  '../features/auth/store/authSlice')

const TITRE_MODALE = 'Session expirée'

const adapter401 = async (config) => {
  const error = new Error('Request failed with status code 401')
  error.config = config
  error.response = { status: 401, data: {}, headers: {}, config }
  throw error
}

let adapterInitial
let store

const monterAvecStore = () => {
  brancherSourceDeSession(() => store.getState().auth.isAuthenticated)
  return render(
    <Provider store={store}>
      <SessionProvider>
        <p>contenu public</p>
      </SessionProvider>
    </Provider>,
  )
}

// Un 401 attendu : on avale le rejet pour ne pas polluer le run.
const declencher401 = async () => {
  await expect(api.get('/auth/me/')).rejects.toBeTruthy()
}

beforeEach(() => {
  adapterInitial = api.defaults.adapter
  api.defaults.adapter = adapter401
  store = configureStore({ reducer: { auth: authReducer } })
})

afterEach(() => {
  api.defaults.adapter = adapterInitial
  // Débranche la source de session (repli « aucune session »).
  brancherSourceDeSession(null)
  vi.clearAllMocks()
})

describe('Modale « Session expirée » — seulement s\'il y avait une session', () => {
  it("n'ouvre PAS la modale sur un 401 sans session (page publique)", async () => {
    monterAvecStore()
    expect(store.getState().auth.isAuthenticated).toBe(false)

    await declencher401()
    // Laisse le temps à un éventuel événement + rendu de se produire.
    await waitFor(() => expect(screen.getByText('contenu public')).toBeTruthy())

    expect(screen.queryByText(TITRE_MODALE)).toBeNull()
    // Aucun overlay/dialog ne recouvre la page : les clics passent.
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('ouvre TOUJOURS la modale sur un 401 avec session (protection intacte)', async () => {
    store.dispatch(setCredentials({ user: { username: 'reda' } }))
    monterAvecStore()
    expect(store.getState().auth.isAuthenticated).toBe(true)

    await declencher401()

    expect(await screen.findByText(TITRE_MODALE)).toBeTruthy()
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('rouvre la modale quand la session a été perdue puis retrouvée', async () => {
    // La source est LUE à l'instant de la décision (jamais figée au montage) :
    // un login survenu après le montage doit être vu par la couche API.
    monterAvecStore()

    await declencher401()
    // `waitFor` laisse React vidanger un éventuel rendu de modale avant qu'on
    // affirme son absence (sans ça l'assertion passerait même sans le correctif).
    await waitFor(() => expect(screen.getByText('contenu public')).toBeTruthy())
    expect(screen.queryByText(TITRE_MODALE)).toBeNull()

    store.dispatch(setCredentials({ user: { username: 'reda' } }))
    await declencher401()

    expect(await screen.findByText(TITRE_MODALE)).toBeTruthy()
  })
})
