import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { useDeviseTenant } from './useDeviseTenant'
import { formatMontant } from '../lib/format'

// NTI18N9 — le dashboard affiche ses totaux dans la devise de la société.
const wrap = (profile) => ({ children }) => (
  <Provider store={configureStore({ reducer: { parametres: () => ({ profile }) } })}>{children}</Provider>
)

describe('useDeviseTenant (NTI18N9)', () => {
  it('société XOF -> totaux en XOF', () => {
    const { result } = renderHook(() => useDeviseTenant(), { wrapper: wrap({ devise_tenant: 'XOF' }) })
    expect(result.current).toBe('XOF')
    expect(formatMontant(1500, { decimals: 0, devise: result.current })).toMatch(/XOF$/)
  })

  it('profil non chargé ou champ absent -> MAD', () => {
    const a = renderHook(() => useDeviseTenant(), { wrapper: wrap(null) })
    const b = renderHook(() => useDeviseTenant(), { wrapper: wrap({}) })
    expect(a.result.current).toBe('MAD')
    expect(b.result.current).toBe('MAD')
  })
})
