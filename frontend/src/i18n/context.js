import { createContext, useContext } from 'react'
import fr from './catalogs/fr.json'
import en from './catalogs/en.json'
import ar from './catalogs/ar.json'

// N93 — cœur (non-composant) du cadre i18n léger : contexte, catalogues,
// helpers et hooks. Séparé de `I18nProvider.jsx` pour que ce dernier n'exporte
// QUE le composant (règle react-refresh/only-export-components).

export const LOCALES = ['fr', 'en', 'ar']
export const DEFAULT_LOCALE = 'fr'
export const STORAGE_KEY = 'taqinor.locale'

export const CATALOGS = { fr, en, ar }

export function dirForLocale(locale) {
  return locale === 'ar' ? 'rtl' : 'ltr'
}

// Interpolation `{var}` : remplace chaque occurrence par vars[var] (ou laisse
// le token si la variable est absente, pour rester débogable).
export function interpolate(str, vars) {
  if (!vars || typeof str !== 'string') return str
  return str.replace(/\{(\w+)\}/g, (m, name) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : m)
}

export function readInitialLocale() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored && LOCALES.includes(stored)) return stored
  } catch { /* localStorage indisponible (SSR / navigation privée) */ }
  return DEFAULT_LOCALE
}

// Applique lang + dir sur <html> — appelé au montage ET à chaque changement.
export function applyDocumentAttrs(locale) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.lang = locale
  root.dir = dirForLocale(locale)
}

export const I18nContext = createContext(null)

// Hook complet : { t, locale, setLocale, dir }.
export function useI18n() {
  const ctx = useContext(I18nContext)
  if (!ctx) {
    // Repli hors provider (ex. test isolé, ou composant rendu sans provider) :
    // t() renvoie le FR, locale=fr, dir=ltr, setLocale no-op.
    return {
      locale: DEFAULT_LOCALE,
      setLocale: () => {},
      dir: 'ltr',
      t: (key, vars) => interpolate(
        CATALOGS[DEFAULT_LOCALE][key] ?? key, vars),
    }
  }
  return ctx
}

// Hook ergonomique : ne renvoie que la fonction `t`.
export function useT() {
  return useI18n().t
}
