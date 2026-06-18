// L54 — Fournisseur de confirmations destructives, monté à la racine. Expose
// `useConfirm()` qui renvoie une fonction `confirm(options) => Promise<boolean>`.
// Bâti sur la primitive AlertDialog de `@/ui` (pas de fermeture au clic
// extérieur, choix explicite Annuler / Confirmer). Défauts en français.
import { useCallback, useMemo, useRef, useState } from 'react'
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogFooter,
  AlertDialogTitle, AlertDialogDescription, AlertDialogCancel, AlertDialogAction,
} from '../ui/AlertDialog'
import { ConfirmContext } from './confirm-context'

const DEFAULTS = {
  title: 'Confirmer l’action',
  description: '',
  confirmLabel: 'Confirmer',
  cancelLabel: 'Annuler',
  destructive: true,
}

export function ConfirmProvider({ children }) {
  const [open, setOpen] = useState(false)
  const [opts, setOpts] = useState(DEFAULTS)
  // Conserve le resolver de la promesse en cours entre deux rendus.
  const resolverRef = useRef(null)

  const settle = useCallback((value) => {
    const resolve = resolverRef.current
    resolverRef.current = null
    setOpen(false)
    if (resolve) resolve(value)
  }, [])

  const confirm = useCallback((options = {}) => {
    // Si une confirmation est déjà ouverte, on la résout en « false » avant de
    // démarrer la nouvelle (évite une promesse orpheline).
    if (resolverRef.current) settle(false)
    setOpts({ ...DEFAULTS, ...options })
    setOpen(true)
    return new Promise((resolve) => { resolverRef.current = resolve })
  }, [settle])

  // Fermeture par Échap / overlay (Radix) → considéré comme « Annuler ».
  const onOpenChange = useCallback((next) => {
    if (!next) settle(false)
    else setOpen(true)
  }, [settle])

  const value = useMemo(() => confirm, [confirm])

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      <AlertDialog open={open} onOpenChange={onOpenChange}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{opts.title}</AlertDialogTitle>
            {opts.description && (
              <AlertDialogDescription>{opts.description}</AlertDialogDescription>
            )}
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => settle(false)}>
              {opts.cancelLabel}
            </AlertDialogCancel>
            <AlertDialogAction
              variant={opts.destructive ? 'destructive' : 'default'}
              onClick={() => settle(true)}
            >
              {opts.confirmLabel}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ConfirmContext.Provider>
  )
}

export default ConfirmProvider
