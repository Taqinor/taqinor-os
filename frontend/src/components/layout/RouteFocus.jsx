import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { titleFor } from './routes.meta'
import { useT } from '../../i18n'

/* VX197 — navigation SPA accessible (WCAG 2.4.1 « Bypass Blocks » / 2.4.3
   « Focus Order »). Avant ce composant : `<main>` (Layout.jsx) n'avait ni
   `id` ni `tabIndex`, la barre de progression de route n'avait pas
   `aria-live`, et RIEN n'annonçait ni ne déplaçait le focus après un
   changement de route — un lecteur d'écran restait planté sur le header/
   sidebar après chaque clic de menu, et aucun raccourci clavier ne permettait
   de sauter la navigation. Trois choses, dans l'ordre du DOM :
   1) Skip-link « Aller au contenu » — premier élément focalisable de la page,
      visible seulement au focus clavier (`sr-only focus:not-sr-only`).
   2) Région `aria-live="polite"` dédiée qui annonce le nom d'écran à CHAQUE
      navigation — consomme `titleFor()` de routes.meta.js, la MÊME source
      que VX82 (`useDocumentTitle`, monté par chaque page) affiche dans
      l'onglet. RouteFocus ne recrée PAS la gestion du titre d'onglet, il
      l'ANNONCE.
   3) À chaque changement de route, le focus clavier est déplacé sur
      `<main id="contenu" tabIndex={-1}>` (posé dans Layout.jsx) — Tab part
      du contenu, pas du header, après une navigation SPA. */
export default function RouteFocus() {
  const location = useLocation()
  const t = useT()
  const announceRef = useRef(null)
  // Ignore le tout premier montage : le focus initial de la page (chargement
  // direct d'une URL) appartient au navigateur, pas à une navigation SPA —
  // ne PAS voler le focus au premier rendu.
  const firstRender = useRef(true)

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    const main = document.getElementById('contenu')
    main?.focus()
    if (announceRef.current) {
      announceRef.current.textContent = titleFor(location.pathname, t)
    }
  }, [location.pathname, t])

  return (
    <>
      <a
        href="#contenu"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[var(--z-modal)] focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground focus:shadow-ui-lg"
      >
        Aller au contenu
      </a>
      <div ref={announceRef} aria-live="polite" role="status" className="sr-only" />
    </>
  )
}
