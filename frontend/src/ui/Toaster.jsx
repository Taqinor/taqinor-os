import { useEffect, useState } from 'react'
import { Toaster as SonnerToaster, toast } from 'sonner'
import { useTheme } from '../design/theme-context'
import { subscribeAssertiveAnnouncer } from '../lib/toast'

/* G29 — Notifications toast (succès/erreur/chargement/undo) via sonner, mappées
   sur les tokens de marque et le thème courant. `toast` réexporté pour appel
   direct : toast.success('…'), toast.error('…', { action: { label, onClick } }). */
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
        richColors
        closeButton
        toastOptions={{
          classNames: {
            toast:
              'rounded-lg border border-border bg-card text-card-foreground shadow-ui-lg font-brand',
            description: 'text-muted-foreground',
            actionButton: 'bg-primary text-primary-foreground',
            cancelButton: 'bg-muted text-muted-foreground',
          },
        }}
        {...props}
      />
    </>
  )
}

export { toast }
export default Toaster
