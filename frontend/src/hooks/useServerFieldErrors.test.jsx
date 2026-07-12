import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useServerFieldErrors } from './useServerFieldErrors'

/* VX171 — vérité serveur → champ. DRF renvoie 3 formes de réponse d'erreur :
   `{ detail: '…' }` (générique, sans champ), `{ champ: ['msg'] }` (le cas
   courant), et un array nu / `{ champ: 'msg' }` (serializer qui renvoie une
   chaîne). `setFromResponse` doit TOUJOURS produire `errors{champ: string}`,
   jamais un objet brut re-rendu tel quel (l'ancien bug : `errors.nom` valant
   `['Nom requis']`, un array, pas une chaîne). `clearField` doit effacer
   l'entrée AVANT le prochain submit, dès la frappe. */
describe('useServerFieldErrors (VX171)', () => {
  it('forme {champ:[msg]} — le cas DRF courant', () => {
    const { result } = renderHook(() => useServerFieldErrors())
    act(() => {
      result.current.setFromResponse({ nom: ['Ce champ est obligatoire.'] })
    })
    expect(result.current.errors).toEqual({ nom: 'Ce champ est obligatoire.' })
  })

  it('forme {champ: msg} — chaîne nue', () => {
    const { result } = renderHook(() => useServerFieldErrors())
    act(() => {
      result.current.setFromResponse({ email: 'Adresse invalide.' })
    })
    expect(result.current.errors).toEqual({ email: 'Adresse invalide.' })
  })

  it('forme {detail: msg} — pas de champ précis, replié sur `submit`', () => {
    const { result } = renderHook(() => useServerFieldErrors())
    act(() => {
      result.current.setFromResponse({ detail: 'Action non autorisée.' })
    })
    expect(result.current.errors).toEqual({ submit: 'Action non autorisée.' })
  })

  it('forme array nue (non_field_errors implicite) — replié sur `submit`', () => {
    const { result } = renderHook(() => useServerFieldErrors())
    act(() => {
      result.current.setFromResponse(['Erreur globale du serializer.'])
    })
    expect(result.current.errors).toEqual({ submit: 'Erreur globale du serializer.' })
  })

  it('{ non_field_errors: [...] } — jamais un faux champ `non_field_errors`', () => {
    const { result } = renderHook(() => useServerFieldErrors())
    act(() => {
      result.current.setFromResponse({ non_field_errors: ['Combinaison déjà utilisée.'] })
    })
    expect(result.current.errors).toEqual({ submit: 'Combinaison déjà utilisée.' })
  })

  it('plusieurs champs en erreur en même temps', () => {
    const { result } = renderHook(() => useServerFieldErrors())
    act(() => {
      result.current.setFromResponse({ nom: ['Requis.'], email: ['Invalide.'] })
    })
    expect(result.current.errors).toEqual({ nom: 'Requis.', email: 'Invalide.' })
  })

  it('réponse vide / non exploitable → message générique, jamais un champ vide', () => {
    const { result } = renderHook(() => useServerFieldErrors())
    act(() => {
      result.current.setFromResponse({})
    })
    expect(result.current.errors).toEqual({ submit: 'Une erreur est survenue.' })
  })

  it('chaîne nue (err.message d\'un rejectWithValue réseau)', () => {
    const { result } = renderHook(() => useServerFieldErrors())
    act(() => {
      result.current.setFromResponse('Network Error')
    })
    expect(result.current.errors).toEqual({ submit: 'Network Error' })
  })

  it('clearField efface UNIQUEMENT le champ visé, avant le prochain submit', () => {
    const { result } = renderHook(() => useServerFieldErrors())
    act(() => {
      result.current.setFromResponse({ nom: ['Requis.'], email: ['Invalide.'] })
    })
    act(() => { result.current.clearField('nom') })
    expect(result.current.errors).toEqual({ email: 'Invalide.' })
  })

  it('clearField sur un champ déjà propre ne casse rien (no-op)', () => {
    const { result } = renderHook(() => useServerFieldErrors())
    act(() => { result.current.clearField('inconnu') })
    expect(result.current.errors).toEqual({})
  })

  it('clearAll vide tout', () => {
    const { result } = renderHook(() => useServerFieldErrors())
    act(() => {
      result.current.setFromResponse({ nom: ['Requis.'] })
    })
    act(() => { result.current.clearAll() })
    expect(result.current.errors).toEqual({})
  })
})
