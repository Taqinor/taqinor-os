import { describe, it, expect, afterEach } from 'vitest'
import { ensureArabicFontLoaded } from './arabicFont'

/* NTI18N7 — la police arabe est chargée PARESSEUSEMENT (un <link> injecté
   dans <head>, jamais au chargement FR/EN par défaut — voir I18nProvider.
   Ce test couvre le mécanisme d'injection lui-même : href/rel corrects,
   idempotence (un second appel ne duplique pas le <link>). */

afterEach(() => {
  document.getElementById('nti18n7-arabic-font')?.remove()
})

describe('NTI18N7 ensureArabicFontLoaded', () => {
  it('injecte un <link rel="stylesheet"> vers /fonts/arabic.css', () => {
    ensureArabicFontLoaded()
    const link = document.getElementById('nti18n7-arabic-font')
    expect(link).not.toBeNull()
    expect(link.tagName).toBe('LINK')
    expect(link.rel).toBe('stylesheet')
    expect(link.getAttribute('href')).toBe('/fonts/arabic.css')
  })

  it('est idempotent (un second appel ne duplique pas le <link>)', () => {
    ensureArabicFontLoaded()
    ensureArabicFontLoaded()
    const links = document.querySelectorAll('#nti18n7-arabic-font')
    expect(links.length).toBe(1)
  })
})
