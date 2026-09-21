/* SOL5 — le hook de gating par module actif, et le déplacement de routes
   `/parametres/<x>` sous leur module propriétaire (nav ET route déclarées
   ensemble, motif PACT150). SOLMVP40 (21/09/2026) a sorti `mrp` du périmètre
   MVP solaire (frontend/parked/README.md) : ce test utilisait son extraction
   `/parametres/mrp` comme exemple. `entites` (NTADM4/30,
   features/entites/module.config.jsx) est un module GARDÉ qui suit EXACTEMENT
   le même patron : la route `/parametres/entites` est déclarée par le module
   propriétaire, jamais par `parametres` (fondation). */
import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

import { useModuleActif } from './useModuleActif'
import entitesConfig from '../features/entites/module.config.jsx'
import parametresConfig from '../features/parametres/module.config.jsx'

function wrapper(modulesDesactives) {
  const store = configureStore({
    reducer: { auth: (s = { modulesDesactives }) => s },
  })
  return function Wrapper({ children }) {
    return <Provider store={store}>{children}</Provider>
  }
}

describe('useModuleActif (SOL5)', () => {
  it('actif par défaut (aucun module désactivé)', () => {
    const { result } = renderHook(() => useModuleActif('entites'), {
      wrapper: wrapper([]),
    })
    expect(result.current).toBe(true)
  })

  it('actif quand la liste est absente (compat totale)', () => {
    const { result } = renderHook(() => useModuleActif('entites'), {
      wrapper: wrapper(undefined),
    })
    expect(result.current).toBe(true)
  })

  it('inactif quand la société a désactivé ce module', () => {
    const { result } = renderHook(() => useModuleActif('entites'), {
      wrapper: wrapper(['entites']),
    })
    expect(result.current).toBe(false)
  })

  it("n'affecte pas les autres modules", () => {
    const { result } = renderHook(() => useModuleActif('ventes'), {
      wrapper: wrapper(['entites']),
    })
    expect(result.current).toBe(true)
  })

  it('surface globale (clé absente) : toujours active', () => {
    const { result } = renderHook(() => useModuleActif(null), {
      wrapper: wrapper(['entites']),
    })
    expect(result.current).toBe(true)
  })
})

describe('SOL5 — /parametres/entites appartient au module entites', () => {
  const chemins = (config) => (config.routes ?? []).map((r) => r.path)
  const liens = (config) => (config.nav?.items ?? []).map((i) => i.to)

  it('la route est déclarée par le module entites (donc gatée par moduleLoader)', () => {
    expect(chemins(entitesConfig)).toContain('/parametres/entites')
    expect(entitesConfig.key).toBe('entites')
  })

  it("la route n'est plus déclarée par le module parametres (fondation)", () => {
    expect(chemins(parametresConfig)).not.toContain('/parametres/entites')
    expect(liens(parametresConfig)).not.toContain('/parametres/entites')
  })

  it("l'entrée de nav a suivi la route (écran resté atteignable)", () => {
    expect(liens(entitesConfig)).toContain('/parametres/entites')
  })

  it('le chemin public est INCHANGÉ (aucun lien cassé)', () => {
    const route = entitesConfig.routes.find((r) => r.path === '/parametres/entites')
    expect(route.roles).toEqual(['admin'])
  })
})
