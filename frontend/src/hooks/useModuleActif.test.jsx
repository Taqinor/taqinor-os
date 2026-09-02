/* SOL5 — le hook de gating par module actif, et le déplacement des trois
   arêtes mrp vivantes (carte Dashboard, écran de réglages, bouton devis). */
import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

import { useModuleActif } from './useModuleActif'
import mrpConfig from '../features/mrp/module.config.jsx'
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
    const { result } = renderHook(() => useModuleActif('mrp'), {
      wrapper: wrapper([]),
    })
    expect(result.current).toBe(true)
  })

  it('actif quand la liste est absente (compat totale)', () => {
    const { result } = renderHook(() => useModuleActif('mrp'), {
      wrapper: wrapper(undefined),
    })
    expect(result.current).toBe(true)
  })

  it('inactif quand la société a désactivé ce module', () => {
    const { result } = renderHook(() => useModuleActif('mrp'), {
      wrapper: wrapper(['mrp']),
    })
    expect(result.current).toBe(false)
  })

  it("n'affecte pas les autres modules", () => {
    const { result } = renderHook(() => useModuleActif('ventes'), {
      wrapper: wrapper(['mrp']),
    })
    expect(result.current).toBe(true)
  })

  it('surface globale (clé absente) : toujours active', () => {
    const { result } = renderHook(() => useModuleActif(null), {
      wrapper: wrapper(['mrp']),
    })
    expect(result.current).toBe(true)
  })
})

describe('SOL5 — /parametres/mrp appartient au module mrp', () => {
  const chemins = (config) => (config.routes ?? []).map((r) => r.path)
  const liens = (config) => (config.nav?.items ?? []).map((i) => i.to)

  it('la route est déclarée par le module mrp (donc gatée par moduleLoader)', () => {
    expect(chemins(mrpConfig)).toContain('/parametres/mrp')
    expect(mrpConfig.key).toBe('mrp')
  })

  it("la route n'est plus déclarée par le module parametres (fondation)", () => {
    expect(chemins(parametresConfig)).not.toContain('/parametres/mrp')
    expect(liens(parametresConfig)).not.toContain('/parametres/mrp')
  })

  it("l'entrée de nav a suivi la route (écran resté atteignable)", () => {
    expect(liens(mrpConfig)).toContain('/parametres/mrp')
  })

  it('le chemin public est INCHANGÉ (aucun lien cassé)', () => {
    const route = mrpConfig.routes.find((r) => r.path === '/parametres/mrp')
    expect(route.roles).toEqual(['admin'])
  })
})
