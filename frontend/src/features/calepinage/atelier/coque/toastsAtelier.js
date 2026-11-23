import { useEffect } from 'react'

/** ACAL2001 — Un message ne cache jamais le bouton d'action. Le Toaster de l'ERP (ui/Toaster.jsx) pose ses messages
    en bas à droite : dans l'atelier, c'est exactement la place du bouton d'étape du panneau (et, sur tablette, de la
    rangée du tiroir). Tant que l'atelier est monté, `<body>` porte ce repère ; la feuille 50 range alors les messages
    à gauche du panneau (au bureau) ou au-dessus du tiroir (tablette). Le reste de l'ERP ne voit rien : le repère est
    retiré au démontage. */
export const REPERE_TOASTS_ATELIER = 'data-cal-atelier'

export function useToastsHorsDuBouton() {
  useEffect(() => {
    if (typeof document === 'undefined') return undefined
    document.body.setAttribute(REPERE_TOASTS_ATELIER, '1')
    return () => document.body.removeAttribute(REPERE_TOASTS_ATELIER)
  }, [])
}
