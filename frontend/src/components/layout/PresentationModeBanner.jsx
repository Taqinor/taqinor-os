// NTDMO10 — bandeau discret « Mode présentation actif ».
// Visible UNIQUEMENT quand la société courante a le mode présentation actif
// (`company_mode_presentation_actif`, servi par /auth/me). Rend null sinon →
// aucune société non concernée n'est affectée.
import { useSelector } from 'react-redux'
import { Eye } from 'lucide-react'

export default function PresentationModeBanner() {
  const active = useSelector(
    (s) => s.auth.user?.company_mode_presentation_actif)
  if (!active) return null
  return (
    <div
      role="status"
      data-testid="presentation-mode-banner"
      className="flex items-center justify-center gap-2 border-b border-amber-300/60 bg-amber-50 px-4 py-1.5 text-[12.5px] font-medium text-amber-800 dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-200"
    >
      <Eye className="size-3.5" aria-hidden="true" />
      Mode présentation actif — les coordonnées des clients sont masquées.
    </div>
  )
}
