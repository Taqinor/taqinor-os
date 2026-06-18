import { forwardRef } from 'react'
import { Input } from './Input'

/* G22 — Variantes numériques de Input. RÈGLE FONDATRICE : saisie sans perte —
   `step="any"` + aucun reformatage automatique de la valeur tapée (cf. la règle
   du générateur : ne jamais « snap »/rejeter un nombre saisi). L'unité n'est
   qu'un ornement visuel ; la valeur reste brute. */

export const NumberInput = forwardRef(function NumberInput({ ...props }, ref) {
  return <Input ref={ref} type="text" inputMode="decimal" {...props} />
})

export const CurrencyInput = forwardRef(function CurrencyInput({ className, ...props }, ref) {
  return (
    <Input
      ref={ref}
      type="text"
      inputMode="decimal"
      trailing="MAD"
      className={`tabular-nums text-right ${className ?? ''}`}
      {...props}
    />
  )
})

export const PercentInput = forwardRef(function PercentInput({ className, ...props }, ref) {
  return (
    <Input
      ref={ref}
      type="text"
      inputMode="decimal"
      trailing="%"
      className={`tabular-nums text-right ${className ?? ''}`}
      {...props}
    />
  )
})

export const PhoneInput = forwardRef(function PhoneInput({ ...props }, ref) {
  return <Input ref={ref} type="tel" inputMode="tel" autoComplete="tel" {...props} />
})

export default NumberInput
