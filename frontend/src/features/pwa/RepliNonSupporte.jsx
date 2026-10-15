import { CameraOff } from 'lucide-react'

/* Carte de repli PARTAGÉE quand la caméra / le scan n'est pas pris en charge :
   icône, message et actions de repli (`children`). */
export function RepliNonSupporte({ className, children }) {
  return (
    <div
      role="alert"
      className={`flex flex-col items-center gap-2 rounded-xl border border-border bg-muted/40 p-4 text-center text-sm text-muted-foreground ${className}`}
    >
      <CameraOff className="size-6" aria-hidden="true" />
      {children}
    </div>
  )
}
