// QG5 — Tests du hook rôle/permission partagé. On vérifie que la règle
// combinée (code de permission ERP + role_nom en liste blanche) matche
// exactement la garde backend HasPermissionAndRole('stock_creer', 'Directeur',
// 'Commercial responsable') utilisée par QG4, dans les deux sens : autorisé
// et refusé.

import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import React from 'react'

import authReducer from '../features/auth/store/authSlice'
import { useHasPermission, useCanCreateProduit, PRODUIT_CREATE_ROLES } from './useHasPermission'

function renderWithAuth({ role_nom = null, permissions = [] } = {}) {
  const store = configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 },
        role: 'normal',
        role_nom,
        permissions,
        isAuthenticated: true,
        loading: false,
      },
    },
  })
  const wrapper = ({ children }) => <Provider store={store}>{children}</Provider>
  return wrapper
}

describe('useHasPermission (QG5)', () => {
  it('autorise quand le code de permission ET le role_nom sont présents', () => {
    const wrapper = renderWithAuth({ role_nom: 'Directeur', permissions: ['stock_creer'] })
    const { result } = renderHook(
      () => useHasPermission('stock_creer', ['Directeur', 'Commercial responsable']),
      { wrapper }
    )
    expect(result.current).toBe(true)
  })

  it('refuse si le role_nom n’est pas dans la liste blanche', () => {
    const wrapper = renderWithAuth({ role_nom: 'Magasinier', permissions: ['stock_creer'] })
    const { result } = renderHook(
      () => useHasPermission('stock_creer', ['Directeur', 'Commercial responsable']),
      { wrapper }
    )
    expect(result.current).toBe(false)
  })

  it('refuse si le rôle est bon mais la permission ERP absente', () => {
    const wrapper = renderWithAuth({ role_nom: 'Directeur', permissions: [] })
    const { result } = renderHook(
      () => useHasPermission('stock_creer', ['Directeur', 'Commercial responsable']),
      { wrapper }
    )
    expect(result.current).toBe(false)
  })

  it('sans contrainte de rôle, seule la permission compte', () => {
    const wrapper = renderWithAuth({ role_nom: 'Peu importe', permissions: ['stock_voir'] })
    const { result } = renderHook(() => useHasPermission('stock_voir'), { wrapper })
    expect(result.current).toBe(true)
  })

  it('useCanCreateProduit reflète exactement la garde QG4 (Directeur + Commercial responsable)', () => {
    const directeur = renderWithAuth({ role_nom: 'Directeur', permissions: ['stock_creer'] })
    expect(renderHook(() => useCanCreateProduit(), { wrapper: directeur }).result.current).toBe(true)

    const commercial = renderWithAuth({ role_nom: 'Commercial responsable', permissions: ['stock_creer'] })
    expect(renderHook(() => useCanCreateProduit(), { wrapper: commercial }).result.current).toBe(true)

    const magasinier = renderWithAuth({ role_nom: 'Magasinier', permissions: ['stock_creer'] })
    expect(renderHook(() => useCanCreateProduit(), { wrapper: magasinier }).result.current).toBe(false)

    expect(PRODUIT_CREATE_ROLES).toEqual(['Directeur', 'Commercial responsable'])
  })
})
