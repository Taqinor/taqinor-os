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
import {
  useHasPermission,
  useHasRole,
  useIsAdmin,
  useIsAdminOrResponsable,
  useCanCreateProduit,
  useCanValiderVente,
  PRODUIT_CREATE_ROLES,
  VENTES_VALIDER_PERMISSION,
} from './useHasPermission'

function renderWithAuth({ role = 'normal', role_nom = null, permissions = [] } = {}) {
  const store = configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 },
        role,
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

// VX199 — test d'ALIGNEMENT front↔back : la garde des actions ventes sensibles
// (accepter/refuser un devis, émettre une facture) est le code ERP fin
// `ventes_valider` côté backend (HasPermissionOrLegacy). Le front DOIT cacher
// l'affordance avec exactement ce code. Ce test échoue si la constante front
// diverge du code backend attendu.
describe('useCanValiderVente (VX199)', () => {
  it('la constante front est exactement le code backend ventes_valider', () => {
    expect(VENTES_VALIDER_PERMISSION).toBe('ventes_valider')
  })

  it('un rôle « lecture + une écriture » (sans ventes_valider) ne peut PAS valider', () => {
    // Exactement le compte que la garde grossière laissait passer par erreur :
    // il détient une écriture (crm_creer, ventes_creer) mais pas ventes_valider.
    const commercial = renderWithAuth({
      role_nom: 'Commercial',
      permissions: ['crm_voir', 'crm_creer', 'ventes_voir', 'ventes_creer'],
    })
    expect(renderHook(() => useCanValiderVente(), { wrapper: commercial }).result.current).toBe(false)
  })

  it('un rôle porteur de ventes_valider peut valider', () => {
    const valideur = renderWithAuth({
      role_nom: 'Valideur',
      permissions: ['ventes_voir', 'ventes_valider'],
    })
    expect(renderHook(() => useCanValiderVente(), { wrapper: valideur }).result.current).toBe(true)
  })
})

// ARC47 — le gating par palier machine (state.auth.role) passe désormais par
// useHasRole ; on vérifie la parité stricte avec l'ancien `role === X`.
describe('useHasRole (ARC47)', () => {
  it('autorise quand le palier courant est dans la liste blanche', () => {
    const wrapper = renderWithAuth({ role: 'admin' })
    expect(renderHook(() => useHasRole(['admin']), { wrapper }).result.current).toBe(true)
  })

  it('refuse quand le palier courant est hors liste', () => {
    const wrapper = renderWithAuth({ role: 'normal' })
    expect(renderHook(() => useHasRole(['admin']), { wrapper }).result.current).toBe(false)
  })

  it('gère une liste multi-palier (responsable OU admin)', () => {
    const resp = renderWithAuth({ role: 'responsable' })
    expect(renderHook(() => useHasRole(['responsable', 'admin']), { wrapper: resp }).result.current).toBe(true)
    const norm = renderWithAuth({ role: 'normal' })
    expect(renderHook(() => useHasRole(['responsable', 'admin']), { wrapper: norm }).result.current).toBe(false)
  })

  it('useIsAdmin / useIsAdminOrResponsable reflètent les paliers', () => {
    const admin = renderWithAuth({ role: 'admin' })
    expect(renderHook(() => useIsAdmin(), { wrapper: admin }).result.current).toBe(true)
    expect(renderHook(() => useIsAdminOrResponsable(), { wrapper: admin }).result.current).toBe(true)

    const resp = renderWithAuth({ role: 'responsable' })
    expect(renderHook(() => useIsAdmin(), { wrapper: resp }).result.current).toBe(false)
    expect(renderHook(() => useIsAdminOrResponsable(), { wrapper: resp }).result.current).toBe(true)

    const norm = renderWithAuth({ role: 'normal' })
    expect(renderHook(() => useIsAdmin(), { wrapper: norm }).result.current).toBe(false)
    expect(renderHook(() => useIsAdminOrResponsable(), { wrapper: norm }).result.current).toBe(false)
  })
})
