import { createAsyncThunk } from '@reduxjs/toolkit'

// VX163 — Infrastructure thunk partagée pour les thunks CHAUDS (montés/
// démontés souvent, potentiellement dispatchés plusieurs fois en concurrence) :
// 79 `createAsyncThunk` identiques dans ce repo, ZÉRO `{signal}` câblé jusqu'à
// axios — un démontage laisse la requête vivre et son `.fulfilled` réduire un
// écran qui n'existe plus ; et ZÉRO dé-duplication — deux montages simultanés
// du même écran déclenchent deux GET identiques. Le « RTK Query sans RTK
// Query » : 0 nouvelle dépendance, ~15 lignes utiles.

/** Vrai pour une annulation volontaire (AbortController/axios), jamais une
 *  vraie erreur métier — ne doit jamais être toastée ni traitée comme un échec. */
export function isCancelledError(err) {
  return err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED' || err?.name === 'AbortError'
}

/**
 * `createCancellableThunk(type, apiCall)` — enrobe `createAsyncThunk` :
 *  - une annulation (démontage → `thunk.abort()`) est REPROPAGÉE comme une
 *    vraie `AbortError` (axios lève une `CanceledError`, nom que RTK ne
 *    reconnaît pas) pour que `action.meta.aborted === true` — un
 *    `rejectWithValue` ici casserait ce contrat (RTK ne marque `aborted` que
 *    sur une erreur PROPAGÉE, jamais sur un rejet applicatif) ;
 *  - toute AUTRE erreur suit le chemin `rejectWithValue` habituel.
 *  Le toast est déjà supprimé pour les annulations par l'intercepteur axios
 *  (`api/axios.js` : `axios.isCancel?.(error)`), indépendamment de ceci.
 */
export function createCancellableThunk(type, apiCall) {
  return createAsyncThunk(type, async (arg, thunkAPI) => {
    try {
      return await apiCall(arg, thunkAPI)
    } catch (err) {
      if (isCancelledError(err)) {
        const abortErr = new Error(err.message || 'Aborted')
        abortErr.name = 'AbortError'
        throw abortErr
      }
      return thunkAPI.rejectWithValue(err.response?.data ?? err.message)
    }
  })
}

// Dé-duplication en vol : `Map<clé, Promise>` process-wide. Deux appels
// concurrents avec la MÊME clé partagent la MÊME promesse — le second
// n'émet JAMAIS sa propre requête réseau, les deux appelants reçoivent le
// MÊME résultat (même payload). Nettoyée en `finally`, succès comme échec —
// l'appel SUIVANT (une fois celui-ci résolu) relance un fetch frais.
const inFlight = new Map()

export function dedupeInFlight(key, run) {
  const existing = inFlight.get(key)
  if (existing) return existing
  const p = Promise.resolve().then(run).finally(() => inFlight.delete(key))
  inFlight.set(key, p)
  return p
}
