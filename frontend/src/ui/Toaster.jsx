import { Toaster as SonnerToaster, toast } from 'sonner'
import { useTheme } from '../design/theme-context'

/* G29 — Notifications toast (succès/erreur/chargement/undo) via sonner, mappées
   sur les tokens de marque et le thème courant. `toast` réexporté pour appel
   direct : toast.success('…'), toast.error('…', { action: { label, onClick } }). */
export function Toaster(props) {
  const { resolvedTheme } = useTheme()
  return (
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
  )
}

export { toast }
export default Toaster
