import { forwardRef } from 'react'
import { Input } from './Input'

/* G22 — Variantes numériques de Input. RÈGLE FONDATRICE : saisie sans perte —
   `step="any"` + aucun reformatage automatique de la valeur tapée (cf. la règle
   du générateur : ne jamais « snap »/rejeter un nombre saisi). L'unité n'est
   qu'un ornement visuel ; la valeur reste brute.

   NTI18N6 — `dir="ltr"` EXPLICITE sur le champ natif : sans lui, un `<input>`
   HÉRITE de la direction ambiante (`<html dir="rtl">` en arabe) et le
   navigateur applique l'algorithme bidi au CONTENU du champ — un montant
   comme « 1 234,50 MAD » peut alors se réordonner de façon imprévisible
   (ponctuation/espaces/unité) même si chaque run de chiffres reste lisible
   individuellement. Les chiffres restent LTR même en contexte RTL (convention
   universelle, cf. NTI18N1) : `dir="ltr"` fige la lecture de GAUCHE à DROITE
   du champ entier, tandis que `text-right`/`className` restent la
   responsabilité de l'ALIGNEMENT visuel du conteneur (indépendant de la
   direction interne du texte). Placé AVANT `{...props}` : un appelant qui
   passerait explicitement `dir` reste prioritaire (cas hypothétique, jamais
   utilisé aujourd'hui). */

export const NumberInput = forwardRef(function NumberInput({ ...props }, ref) {
  return <Input ref={ref} type="text" inputMode="decimal" dir="ltr" {...props} />
})

export const CurrencyInput = forwardRef(function CurrencyInput({ className, ...props }, ref) {
  return (
    <Input
      ref={ref}
      type="text"
      inputMode="decimal"
      trailing="MAD"
      dir="ltr"
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
      dir="ltr"
      className={`tabular-nums text-right ${className ?? ''}`}
      {...props}
    />
  )
})

export const PhoneInput = forwardRef(function PhoneInput({ ...props }, ref) {
  return <Input ref={ref} type="tel" inputMode="tel" autoComplete="tel" {...props} />
})

export default NumberInput
