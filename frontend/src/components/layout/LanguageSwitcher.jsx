import { Globe } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator,
} from '../../ui'
import { useI18n, LOCALES } from '../../i18n'

// N93 — sélecteur compact de langue d'interface (FR / EN / العربية) monté dans
// le Header. FR reste le défaut ; le choix est persisté par I18nProvider et
// bascule la mise en page RTL pour l'arabe.
const LABEL_KEY = { fr: 'lang.fr', en: 'lang.en', ar: 'lang.ar' }
const SHORT = { fr: 'FR', en: 'EN', ar: 'ع' }

export default function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="nb-btn header-lang-btn"
          aria-label={t('lang.switcher')}
          title={t('lang.switcher')}
          data-testid="lang-switcher"
        >
          <Globe size={18} aria-hidden="true" />
          <span className="header-lang-code" aria-hidden="true">{SHORT[locale]}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>{t('lang.switcher')}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {LOCALES.map((code) => (
          <DropdownMenuItem
            key={code}
            data-testid={`lang-option-${code}`}
            aria-current={code === locale ? 'true' : undefined}
            onSelect={() => setLocale(code)}
          >
            {t(LABEL_KEY[code])}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
