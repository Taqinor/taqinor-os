import { useEffect, useState } from 'react'
import { Toaster as SonnerToaster, toast } from 'sonner'
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react'
import { useTheme } from '../design/theme-context'
import { subscribeAssertiveAnnouncer } from '../lib/toast'

/* G29 — Notifications toast (succès/erreur/chargement/undo) via sonner, mappées
   sur les tokens de marque et le thème courant. `toast` réexporté pour appel
   direct : toast.success('…'), toast.error('…', { action: { label, onClick } }).
   VX130 — le toast devient un objet de marque : `richColors` (couleurs
   génériques sonner, divergentes du thème en sombre) retiré au profit de
   `toastOptions.classNames` par TYPE consommant les mêmes tokens que Badge
   (`bg-success/12 border-success/40 text-success`…, parité clair/sombre
   automatique) ; icônes lucide (`icons`) au lieu des glyphes internes de
   sonner — `AlertTriangle` est le MÊME glyphe que EmptyState/ErrorBoundary
   posent déjà sur un état d'erreur, `CheckCircle2`/`Info` cohérents avec le
   reste de l'app. La durée d'animation suit `--motion-base` (règle
   `[data-sonner-toast]` d'index.css) au lieu d'être indépendante du système
   de mouvement du reste de l'UI. */
/* VX196 — sonner ne rend qu'UNE région `aria-live="polite"` pour tous les
   toasts (succès comme erreur) : une erreur bloquante n'interrompt jamais le
   lecteur d'écran. `toastError` (lib/toast.js) publie le message d'erreur via
   `subscribeAssertiveAnnouncer` ; on le relaie ici dans une région dédiée
   `role="alert"`/`aria-live="assertive"`, visuellement masquée — le toast
   sonner reste inchangé à l'écran, seule l'annonce devient prioritaire. */
function AssertiveAnnouncer() {
  const [message, setMessage] = useState('')
  useEffect(() => subscribeAssertiveAnnouncer(setMessage), [])
  return (
    <div role="alert" aria-live="assertive" aria-atomic="true" className="sr-only">
      {message}
    </div>
  )
}

export function Toaster(props) {
  const { resolvedTheme } = useTheme()
  return (
    <>
      <AssertiveAnnouncer />
      <SonnerToaster
        theme={resolvedTheme}
        position="bottom-right"
        closeButton
        icons={{
          success: <CheckCircle2 className="size-4" aria-hidden="true" />,
          error: <AlertTriangle className="size-4" aria-hidden="true" />,
          warning: <AlertTriangle className="size-4" aria-hidden="true" />,
          info: <Info className="size-4" aria-hidden="true" />,
        }}
        toastOptions={{
          classNames: {
            toast:
              'rounded-lg border border-border bg-card text-card-foreground shadow-ui-lg font-brand',
            description: 'text-muted-foreground',
            actionButton: 'bg-primary text-primary-foreground',
            cancelButton: 'bg-muted text-muted-foreground',
            // VX130 — un registre par type, dérivé des mêmes tokens sémantiques
            // que Badge (bg-X/12 border-X/40 text-X) : parité clair/sombre
            // automatique, sans plus dépendre de la palette figée `richColors`.
            success: 'border-success/40 bg-success/12 text-success',
            error: 'border-destructive/40 bg-destructive/12 text-destructive',
            warning: 'border-warning/40 bg-warning/12 text-warning',
            info: 'border-info/40 bg-info/12 text-info',
          },
        }}
        {...props}
      />
    </>
  )
}

export { toast }
export default Toaster
