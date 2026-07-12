import { forwardRef } from 'react'
import * as AccordionPrimitive from '@radix-ui/react-accordion'
import { ChevronDown } from 'lucide-react'
import { cn } from '../lib/cn'

/* G29 — Accordéon (sections repliables). */
export const Accordion = AccordionPrimitive.Root

export const AccordionItem = forwardRef(function AccordionItem({ className, ...props }, ref) {
  return (
    <AccordionPrimitive.Item ref={ref} className={cn('border-b border-border', className)} {...props} />
  )
})

export const AccordionTrigger = forwardRef(function AccordionTrigger({ className, children, ...props }, ref) {
  return (
    <AccordionPrimitive.Header className="flex">
      <AccordionPrimitive.Trigger
        ref={ref}
        className={cn(
          'flex flex-1 items-center justify-between gap-2 py-3 text-left text-sm font-medium',
          'transition-colors hover:text-foreground',
          'focus-ring',
          '[&[data-state=open]>svg]:rotate-180',
          className,
        )}
        {...props}
      >
        {children}
        <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform duration-200" aria-hidden="true" />
      </AccordionPrimitive.Trigger>
    </AccordionPrimitive.Header>
  )
})

export const AccordionContent = forwardRef(function AccordionContent({ className, children, ...props }, ref) {
  return (
    <AccordionPrimitive.Content
      ref={ref}
      className="overflow-hidden text-sm text-muted-foreground"
      {...props}
    >
      <div className={cn('pb-3 pt-0', className)}>{children}</div>
    </AccordionPrimitive.Content>
  )
})

export default Accordion
