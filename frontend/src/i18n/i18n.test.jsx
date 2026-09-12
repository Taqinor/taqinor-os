import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen, act, cleanup } from '@testing-library/react'
import { I18nProvider, useI18n, useT, DEFAULT_LOCALE, STORAGE_KEY } from './index'

/* N93 — cadre i18n léger : lookup, interpolation, repli sur clé manquante, et
   bascule RTL (dir=rtl sur <html>) au passage en arabe. */

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.removeAttribute('dir')
  document.documentElement.removeAttribute('lang')
  // NTI18N7 — le <link> de police arabe est injecté dans <head> (hors de
  // l'arbre React démonté par `cleanup()`) : sans ce retrait explicite, un
  // test antérieur qui passe par 'ar' laisserait le <link> visible aux tests
  // suivants dans ce même fichier (jsdom ne réinitialise pas <head> entre
  // les `it()` d'un même fichier).
  document.getElementById('nti18n7-arabic-font')?.remove()
})
afterEach(() => cleanup())

// Petit harnais : expose t/setLocale/dir/locale du contexte pour les assertions.
function Probe() {
  const { t, locale, setLocale, dir } = useI18n()
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="dir">{dir}</span>
      <span data-testid="save">{t('common.save')}</span>
      <span data-testid="interp">{t('__interp__', { name: 'Reda' })}</span>
      <span data-testid="missing">{t('this.key.does.not.exist')}</span>
      <button data-testid="to-ar" onClick={() => setLocale('ar')}>ar</button>
      <button data-testid="to-en" onClick={() => setLocale('en')}>en</button>
    </div>
  )
}

const renderProbe = () =>
  render(<I18nProvider><Probe /></I18nProvider>)

describe('N93 i18n — t()', () => {
  it('defaults to French and looks up a known key', () => {
    renderProbe()
    expect(screen.getByTestId('locale').textContent).toBe(DEFAULT_LOCALE)
    expect(screen.getByTestId('locale').textContent).toBe('fr')
    expect(screen.getByTestId('save').textContent).toBe('Enregistrer')
  })

  it('translates a known key when locale switches to English', () => {
    renderProbe()
    act(() => { screen.getByTestId('to-en').click() })
    expect(screen.getByTestId('save').textContent).toBe('Save')
  })

  it('interpolates {var} tokens', () => {
    // `__interp__` is not in a catalog → t() falls back to the key string, which
    // contains no token, so we verify interpolation on a returned template via a
    // direct hook probe instead.
    function Interp() {
      const t = useT()
      // The key itself is returned as fallback; interpolation runs on it.
      return <span data-testid="x">{t('Hi {name}!', { name: 'Reda' })}</span>
    }
    render(<I18nProvider><Interp /></I18nProvider>)
    expect(screen.getByTestId('x').textContent).toBe('Hi Reda!')
  })

  it('falls back to the key when a translation is missing', () => {
    renderProbe()
    expect(screen.getByTestId('missing').textContent).toBe('this.key.does.not.exist')
  })

  it('persists the chosen locale to localStorage', () => {
    renderProbe()
    act(() => { screen.getByTestId('to-en').click() })
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('en')
  })
})

describe('N93 i18n — RTL', () => {
  it('sets dir=rtl on <html> and dir=rtl in context when switching to Arabic', () => {
    renderProbe()
    // Default LTR.
    expect(document.documentElement.dir).toBe('ltr')
    expect(screen.getByTestId('dir').textContent).toBe('ltr')

    act(() => { screen.getByTestId('to-ar').click() })

    expect(screen.getByTestId('locale').textContent).toBe('ar')
    expect(screen.getByTestId('dir').textContent).toBe('rtl')
    expect(document.documentElement.dir).toBe('rtl')
    expect(document.documentElement.lang).toBe('ar')
  })

  it('returns to ltr when switching back to a non-Arabic locale', () => {
    renderProbe()
    act(() => { screen.getByTestId('to-ar').click() })
    expect(document.documentElement.dir).toBe('rtl')
    act(() => { screen.getByTestId('to-en').click() })
    expect(document.documentElement.dir).toBe('ltr')
  })
})

// NTI18N7 — police arabe auto-hébergée, chargée PARESSEUSEMENT : seulement au
// passage en 'ar', jamais au chargement FR/EN par défaut.
describe('NTI18N7 i18n — police arabe paresseuse', () => {
  const fontLinkId = 'nti18n7-arabic-font'

  it('ne charge PAS la police arabe par défaut (FR)', () => {
    renderProbe()
    expect(document.getElementById(fontLinkId)).toBeNull()
  })

  it('ne charge PAS la police arabe en passant en anglais', () => {
    renderProbe()
    act(() => { screen.getByTestId('to-en').click() })
    expect(document.getElementById(fontLinkId)).toBeNull()
  })

  it('charge la police arabe (auto-hébergée) au passage en arabe', () => {
    renderProbe()
    act(() => { screen.getByTestId('to-ar').click() })
    const link = document.getElementById(fontLinkId)
    expect(link).not.toBeNull()
    expect(link.getAttribute('href')).toBe('/fonts/arabic.css')
  })
})
