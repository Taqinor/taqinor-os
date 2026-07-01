import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  I18nContext, CATALOGS, LOCALES, DEFAULT_LOCALE,
  STORAGE_KEY, dirForLocale, interpolate,
  readInitialLocale, applyDocumentAttrs,
} from './context'

// N93 — cadre d'internationalisation léger (0 dépendance npm). Ce fichier
// n'exporte QUE le composant provider (règle react-refresh) ; les hooks,
// helpers et constantes vivent dans `./context.js`.
//
// - FR est la locale PAR DÉFAUT et le repli de dernier recours (rule founder).
// - EN est conceptuellement la langue des clés, mais les clés sont des
//   identifiants stables (ex. `nav.stock`) — chaque locale fournit sa valeur.
// - AR déclenche la mise en page RTL (`dir=rtl` sur <html>).

export function I18nProvider({ children }) {
  const [locale, setLocaleState] = useState(readInitialLocale)

  // Applique lang/dir au montage initial (et si la locale change).
  useEffect(() => {
    applyDocumentAttrs(locale)
  }, [locale])

  const setLocale = useCallback((next) => {
    const value = LOCALES.includes(next) ? next : DEFAULT_LOCALE
    setLocaleState(value)
    try { window.localStorage.setItem(STORAGE_KEY, value) } catch { /* noop */ }
    // Applique immédiatement (avant même le re-render) pour éviter tout flash.
    applyDocumentAttrs(value)
  }, [])

  // t(key, vars?) : valeur de la locale courante, sinon repli FR, sinon la clé.
  const t = useCallback((key, vars) => {
    const active = CATALOGS[locale] || CATALOGS[DEFAULT_LOCALE]
    let value = active[key]
    if (value == null) value = CATALOGS[DEFAULT_LOCALE][key]
    if (value == null) value = key
    return interpolate(value, vars)
  }, [locale])

  const value = useMemo(() => ({
    locale,
    setLocale,
    t,
    dir: dirForLocale(locale),
  }), [locale, setLocale, t])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
