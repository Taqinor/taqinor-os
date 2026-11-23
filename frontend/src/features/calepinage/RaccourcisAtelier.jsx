import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { dialogueParDessus } from '../../providers/focusedRecordShortcuts'
import {
  RACCOURCIS, REQUETE_SANS_CLAVIER, SECTIONS_AIDE, ecranSansClavier, estSaisieEnCours, raccourciDe,
} from './RaccourcisAtelier.helpers'

/* ============================================================================
   CAL101 — LES RACCOURCIS DE L'ATELIER, ET LEUR AIDE-MÉMOIRE.
   ----------------------------------------------------------------------------
   Constat : seuls Ctrl+Z / Ctrl+Y existent aujourd'hui, et uniquement dans le
   panneau de disposition (`pages/ventes/ToitureDesign.jsx`). Un atelier de
   pose se pilote au clavier — c'est ce qui fait la vitesse.

   LA RÈGLE QUI COMPTE : AUCUN RACCOURCI NE CAPTURE UNE FRAPPE PENDANT LA
   SAISIE D'UN CHAMP. Un « T » tapé dans « Titre du calepinage » doit écrire un
   T, jamais basculer l'outil tracé. `estSaisieEnCours` garde la porte, et le
   test l'exerce champ par champ (input, textarea, select, contenteditable).

   L'AIDE-MÉMOIRE EST LA MÊME TABLE que les gestionnaires : impossible qu'un
   raccourci existe sans être documenté, ou qu'un raccourci documenté ne fasse
   rien — les deux sont dérivés de `RACCOURCIS`, et le test le vérifie.

   ENTIÈREMENT EN FRANÇAIS (libellés et aide), règle du dépôt.
   ========================================================================== */

/** La touche qui ouvre l'aide — le « ? » usuel des outils de conception. */
export const TOUCHE_AIDE = '?'

export default function RaccourcisAtelier({ actions = {} }) {
  const [aideOuverte, setAideOuverte] = useState(false)
  const racine = useRef(null)
  // ACAL1027 — sur un appareil sans clavier le bouton n'ouvre rien d'utile : il n'est pas rendu (la touche « ? »
  // reste écoutée) ; le choix suit le mode (tablette posée sur un clavier) par l'événement `change` de la requête.
  const [sansClavier, setSansClavier] = useState(() => ecranSansClavier())
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined
    const requete = window.matchMedia(REQUETE_SANS_CLAVIER)
    const suivre = () => setSansClavier(ecranSansClavier())
    requete.addEventListener?.('change', suivre)
    return () => requete.removeEventListener?.('change', suivre)
  }, [])

  useEffect(() => {
    const surTouche = (evenement) => {
      // LA GARDE : une frappe dans un champ appartient au champ.
      if (estSaisieEnCours(evenement.target)) return
      // AERR114 — une boîte ouverte par-dessus l'atelier garde ses frappes.
      if (dialogueParDessus(racine.current)) return

      if (evenement.key === 'Escape') {
        setAideOuverte(false)
        return
      }
      const raccourci = raccourciDe(evenement)
      if (!raccourci) return
      const gestionnaire = actions[raccourci.action]
      // Un raccourci sans gestionnaire ne « mange » PAS la frappe : l'atelier
      // qui n'offre pas cet outil laisse le navigateur faire son travail.
      if (typeof gestionnaire !== 'function') return
      evenement.preventDefault()
      gestionnaire(evenement)
    }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [actions])

  // ACAL414 (acceptation ACAL490) — « ? » dans l'atelier ouvre CETTE aide, jamais celle de
  // l'ERP : écoutée en CAPTURE sur `window`, avant l'écouteur global (`ShortcutsProvider`),
  // qui ne reçoit plus la touche.
  useEffect(() => {
    const surAide = (evenement) => {
      if (evenement.key !== TOUCHE_AIDE || evenement.ctrlKey || evenement.metaKey || evenement.altKey) return
      if (estSaisieEnCours(evenement.target) || dialogueParDessus(racine.current)) return
      evenement.preventDefault()
      evenement.stopPropagation()
      setAideOuverte((ouverte) => !ouverte)
    }
    window.addEventListener('keydown', surAide, true)
    return () => window.removeEventListener('keydown', surAide, true)
  }, [])

  return (
    <div data-testid="cal-raccourcis" ref={racine}>
      {sansClavier ? null : (
        <button
          type="button"
          onClick={() => setAideOuverte((ouverte) => !ouverte)}
          data-testid="cal-raccourcis-bouton"
          aria-expanded={aideOuverte}
          className="text-sm font-semibold text-primary-text underline"
        >
          Raccourcis clavier (?)
        </button>
      )}

      {/* ACAL1435 — l'aide est une fenêtre fixe montée sur <body> : le tiroir « Avancé » qui porte ce composant est
          masqué (`hidden`) en Guidé, et une aide qui y vit mesure 0 × 0 px. */}
      {aideOuverte && createPortal(
        <div className="fixed inset-0 z-[var(--z-overlay)] flex items-center justify-center overflow-auto bg-background/70 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setAideOuverte(false) }}>
        <div
          role="dialog"
          aria-label="Aide-mémoire des raccourcis clavier"
          data-testid="cal-raccourcis-aide"
          className="max-h-full w-full max-w-2xl overflow-auto rounded border border-border bg-card p-4 shadow-lg"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Raccourcis de l’atelier — inactifs pendant la saisie d’un champ
          </p>
          <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
            {RACCOURCIS.map((raccourci) => (
              <div key={raccourci.action} className="flex items-baseline gap-2"
                data-testid={`cal-raccourci-${raccourci.action}`}>
                <dt>
                  <kbd className="rounded bg-muted px-1.5 text-xs text-foreground">
                    {raccourci.affichage}
                  </kbd>
                </dt>
                <dd className="text-sm text-foreground">{raccourci.libelle}</dd>
              </div>
            ))}
            <div className="flex items-baseline gap-2" data-testid="cal-raccourci-aide">
              <dt>
                <kbd className="rounded bg-muted px-1.5 text-xs text-foreground">?</kbd>
              </dt>
              <dd className="text-sm text-foreground">Afficher ou masquer cette aide</dd>
            </div>
          </dl>
          {SECTIONS_AIDE.map((section) => (
            <div key={section.cle} className="mt-3" data-testid={`cal-raccourcis-section-${section.cle}`}>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{section.titre}</p>
              <dl className="mt-1 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
                {section.lignes.map((l) => (
                  <div key={`${l.ecriture}-${l.libelle}`} className="flex items-baseline gap-2">
                    <dt><kbd className="rounded bg-muted px-1.5 text-xs text-foreground">{l.ecriture}</kbd></dt>
                    <dd className="text-sm text-foreground">{l.libelle}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
