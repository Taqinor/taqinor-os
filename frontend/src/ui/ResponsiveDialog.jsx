import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './Dialog'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from './Sheet'

/* M158 — ResponsiveDialog : un adaptateur unique qui rend le `Dialog` centré
   (modale de bureau) à partir de 768 px, et le `Sheet` en bas (tiroir bas) sous
   768 px — construit ENTIÈREMENT sur les primitifs existants, sans nouvelle
   dépendance. La surface de props est identique aux deux variantes :
   `open`, `onOpenChange`, `title`, `description`, `footer`, `children`. */

// Sous 768 px = mobile → tiroir bas ; à partir de 768 px = bureau → modale
// centrée. (`max-width: 767px` donne bien la coupure stricte <768 / ≥768.)
const MOBILE_QUERY = '(max-width: 767px)'

// Hook media-query interne minimal : suit le point de rupture en direct.
// `matchMedia` peut manquer (SSR / vieux jsdom) — on retombe alors sur bureau.
export function useIsMobile(query = MOBILE_QUERY) {
  const [mobile, setMobile] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia(query).matches
  })
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined
    const mq = window.matchMedia(query)
    const onChange = (e) => setMobile(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [query])
  return mobile
}

export function ResponsiveDialog({
  open,
  onOpenChange,
  title,
  description,
  footer,
  children,
  className,
  showClose = true,
  ...props
}) {
  const isMobile = useIsMobile()

  // Bloc d'en-tête + corps + pied partagé : identique quelle que soit la variante,
  // seules les enveloppes (Header/Title/Description) diffèrent par primitif.
  const body = (Header, Title, Description, Footer) => (
    <>
      {(title || description) && (
        <Header>
          {title && <Title>{title}</Title>}
          {description && <Description>{description}</Description>}
        </Header>
      )}
      {children}
      {footer && (Footer ? <Footer>{footer}</Footer> : <div>{footer}</div>)}
    </>
  )

  if (isMobile) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange} {...props}>
        <SheetContent side="bottom" showClose={showClose} className={className}>
          {body(SheetHeader, SheetTitle, SheetDescription, null)}
        </SheetContent>
      </Sheet>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} {...props}>
      <DialogContent showClose={showClose} className={className}>
        {body(DialogHeader, DialogTitle, DialogDescription, DialogFooter)}
      </DialogContent>
    </Dialog>
  )
}

export default ResponsiveDialog
