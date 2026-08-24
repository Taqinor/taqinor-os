import { createContext, useContext } from 'react'
import {
  LOCALES, DEFAULT_LOCALE, STORAGE_KEY,
  dirForLocale, interpolate, readInitialLocale, applyDocumentAttrs,
  resolveValueWithCatalogs,
} from './resolve.js'
import { CATALOGS } from './i18nCatalogs.js'

// N93 — cœur (non-composant) du cadre i18n léger : contexte React + hooks.
// La logique pure (résolution de clé, constantes) vit dans `resolve.js`
// (zéro dépendance React/JSON, testable en `node:test`) ; les catalogues
// statiques vivent dans `i18nCatalogs.js`. Ce fichier lie les deux pour les
// consommateurs existants (`I18nProvider.jsx`, `index.js`) — API inchangée.
// Séparé de `I18nProvider.jsx` pour que ce dernier n'exporte QUE le
// composant (règle react-refresh/only-export-components).

export { LOCALES, DEFAULT_LOCALE, STORAGE_KEY, dirForLocale, interpolate, readInitialLocale, applyDocumentAttrs, CATALOGS }

// resolveValue(key, locale, overrides, fallback) — même algorithme que
// `resolveValueWithCatalogs`, lié aux vrais catalogues statiques.
export function resolveValue(key, locale, overrides, fallback) {
  return resolveValueWithCatalogs(key, locale, overrides, fallback, CATALOGS)
}

export const I18nContext = createContext(null)

// Hook complet : { t, locale, setLocale, dir, setOverrides }.
export function useI18n() {
  const ctx = useContext(I18nContext)
  if (!ctx) {
    // Repli hors provider (ex. test isolé, ou composant rendu sans provider) :
    // t() renvoie le FR, locale=fr, dir=ltr, setLocale/setOverrides no-op.
    return {
      locale: DEFAULT_LOCALE,
      setLocale: () => {},
      setOverrides: () => {},
      dir: 'ltr',
      t: (key, vars, fallback) => interpolate(
        resolveValue(key, DEFAULT_LOCALE, null, fallback), vars),
    }
  }
  return ctx
}

// Hook ergonomique : ne renvoie que la fonction `t`.
export function useT() {
  return useI18n().t
}
