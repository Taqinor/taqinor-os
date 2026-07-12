import { describe, it, expect, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import useDocumentTitle from './useDocumentTitle'

/* VX82 — Chrome navigateur vivant : titre d'onglet par page. Zéro dépendance
   (`document.title` direct), restauré au démontage pour ne pas laisser un
   titre de page fermée collé sur la suivante. */

describe('useDocumentTitle (VX82)', () => {
  const originalTitle = document.title
  afterEach(() => { document.title = originalTitle })

  it('pose le nom de page comme titre (SCA29 — sans marque en dur)', () => {
    document.title = 'Ancien titre'
    renderHook(() => useDocumentTitle('Devis'))
    expect(document.title).toBe('Devis')
  })

  it('bascule le titre quand la valeur change', () => {
    const { rerender } = renderHook(
      ({ title }) => useDocumentTitle(title),
      { initialProps: { title: 'Devis' } },
    )
    expect(document.title).toBe('Devis')
    rerender({ title: 'Factures' })
    expect(document.title).toBe('Factures')
  })

  it('restaure le titre précédent au démontage', () => {
    document.title = 'Ancien titre'
    const { unmount } = renderHook(() => useDocumentTitle('Devis'))
    expect(document.title).toBe('Devis')
    unmount()
    expect(document.title).toBe('Ancien titre')
  })

  it('ne touche pas au titre courant quand la valeur est vide/nulle', () => {
    document.title = 'Titre inchangé'
    renderHook(() => useDocumentTitle(''))
    expect(document.title).toBe('Titre inchangé')
    renderHook(() => useDocumentTitle(null))
    expect(document.title).toBe('Titre inchangé')
  })
})
