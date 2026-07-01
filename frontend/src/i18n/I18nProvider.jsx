import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  I18nContext, LOCALES, DEFAULT_LOCALE,
  STORAGE_KEY, dirForLocale, interpolate,
  readInitialLocale, applyDocumentAttrs, resolveValue,
} from './context'
import { fetchTranslationOverrides } from './overridesApi'

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
  // N94 — surcharges de traduction de la société : { locale: { key: value } }.
  // Vide par défaut → t() se comporte EXACTEMENT comme le catalogue statique
  // (aucune régression du cadre N93). Chargées après authentification.
  const [overrides, setOverridesState] = useState({})

  // Applique lang/dir au montage initial (et si la locale change).
  useEffect(() => {
    applyDocumentAttrs(locale)
  }, [locale])

  // N94 — charge les surcharges de la société une fois (au montage, quand
  // l'utilisateur est authentifié). Tout échec (401 hors session, réseau,
  // aucune donnée) est AVALÉ : `overrides` reste vide et l'interface retombe
  // sur les catalogues statiques — donc jamais de régression.
  useEffect(() => {
    let alive = true
    fetchTranslationOverrides()
      .then((data) => { if (alive && data) setOverridesState(data) })
      .catch(() => { /* repli silencieux sur le catalogue statique */ })
    return () => { alive = false }
  }, [])

  // Permet de rafraîchir les surcharges après une édition (effet immédiat sans
  // rechargement) ; remplace l'état par un objet vide ⇒ retour au statique.
  const setOverrides = useCallback((next) => {
    setOverridesState(next && typeof next === 'object' ? next : {})
  }, [])

  const setLocale = useCallback((next) => {
    const value = LOCALES.includes(next) ? next : DEFAULT_LOCALE
    setLocaleState(value)
    try { window.localStorage.setItem(STORAGE_KEY, value) } catch { /* noop */ }
    // Applique immédiatement (avant même le re-render) pour éviter tout flash.
    applyDocumentAttrs(value)
  }, [])

  // t(key, vars?) : surcharge(locale) → statique(locale) → statique(FR) → clé.
  // Quand `overrides` est vide, resolveValue est byte-identique au comportement
  // statique N93 (garde-fou anti-régression).
  const t = useCallback((key, vars) =>
    interpolate(resolveValue(key, locale, overrides), vars),
  [locale, overrides])

  const value = useMemo(() => ({
    locale,
    setLocale,
    setOverrides,
    overrides,
    t,
    dir: dirForLocale(locale),
  }), [locale, setLocale, setOverrides, overrides, t])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
