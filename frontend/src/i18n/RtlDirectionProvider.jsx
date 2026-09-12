import { DirectionProvider } from '@radix-ui/react-direction'
import { useI18n } from './context'

// NTI18N2 — propage `dir` (ltr/rtl, cadre i18n N93) aux primitives Radix
// (Tabs, DropdownMenu, Select…) utilisées dans `ui/`. SANS ce provider, ces
// primitives assument LTR pour leur logique INTERNE (navigation clavier
// ArrowLeft/ArrowRight, orientation des sous-menus) même quand `<html
// dir="rtl">` est déjà posé par `I18nProvider` — un bug d'interaction
// invisible à l'audit visuel mais bloquant au clavier en arabe.
//
// `@radix-ui/react-direction` n'est pas une nouvelle dépendance : c'est déjà
// une dépendance TRANSITIVE résolue dans `package-lock.json` (plusieurs
// `@radix-ui/react-*` déjà utilisés dans `ui/` la déclarent) — aucun ajout,
// aucun `npm install`.
//
// Monté DANS `I18nProvider` (a besoin de `useI18n()`), autour du reste de
// l'arbre applicatif — voir `main.jsx`.
export default function RtlDirectionProvider({ children }) {
  const { dir } = useI18n()
  return <DirectionProvider dir={dir}>{children}</DirectionProvider>
}
