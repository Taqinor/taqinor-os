import { useEffect, useRef } from 'react'
import { useSelector } from 'react-redux'
import { useI18n, LOCALES } from './context'
import { patchLangueInterface } from './langueInterfaceApi'

// NTI18N3 — synchronise la locale d'interface avec `CustomUser.langue_interface`
// (serveur), SANS coupler `I18nProvider` (cadre i18n 0-dépendance, N93) à Redux
// — plusieurs tests montent `I18nProvider` SEUL, sans `<Provider>` Redux
// (ex. `TraductionsSection.test.jsx`), donc un `useSelector` À L'INTÉRIEUR
// d'`I18nProvider` casserait ces rendus. Ce composant séparé (ne rend rien) se
// monte À CÔTÉ, dans l'arbre authentifié uniquement (voir `main.jsx`).
//
// Deux sens :
//  1) à la connexion / au (re)chargement du profil, ADOPTE la langue serveur
//     si elle diffère de la locale courante — UNE fois par valeur reçue (un
//     changement local ultérieur n'est jamais écrasé par une réponse
//     /auth/me/ en vol qui portait encore l'ancienne valeur) ;
//  2) un changement de LOCALE (sélecteur de langue) pendant que l'utilisateur
//     est connecté est persisté côté serveur (best-effort, silencieux).
export default function ServerLocaleSync() {
  const isAuthenticated = useSelector((s) => s.auth?.isAuthenticated)
  const serverLocale = useSelector((s) => s.auth?.user?.langue_interface)
  const { locale, setLocale } = useI18n()
  // Dernière valeur SERVEUR connue — distingue « on vient de la recevoir »
  // (ne pas la renvoyer aussitôt) de « l'utilisateur vient de changer
  // localement » (à persister).
  const lastServerValue = useRef(null)

  useEffect(() => {
    if (!serverLocale || !LOCALES.includes(serverLocale)) return
    if (lastServerValue.current === serverLocale) return
    const premiereReception = lastServerValue.current === null
    lastServerValue.current = serverLocale
    if (premiereReception && serverLocale !== locale) {
      setLocale(serverLocale)
    }
    // `locale`/`setLocale` volontairement absents des deps : ce useEffect ne
    // doit réagir qu'à un CHANGEMENT DE VALEUR SERVEUR, jamais à un
    // changement local de `locale` (couvert par l'effet ci-dessous).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverLocale])

  useEffect(() => {
    if (!isAuthenticated) return
    if (lastServerValue.current === null) return // profil pas encore chargé
    if (locale === lastServerValue.current) return
    lastServerValue.current = locale
    patchLangueInterface(locale)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale, isAuthenticated])

  return null
}
