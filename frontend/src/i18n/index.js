// N93 — barrel du cadre i18n léger. Import unique côté app :
//   import { I18nProvider, useT, useI18n } from '@/i18n'
export { I18nProvider } from './I18nProvider'
export {
  useI18n,
  useT,
  dirForLocale,
  resolveValue,
  CATALOGS,
  LOCALES,
  DEFAULT_LOCALE,
  STORAGE_KEY,
} from './context'
