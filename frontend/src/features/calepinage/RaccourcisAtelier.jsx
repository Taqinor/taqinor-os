import { useEffect, useRef, useState } from 'react'
import { dialogueParDessus } from '../../providers/focusedRecordShortcuts'
import { RACCOURCIS, SECTIONS_AIDE, estSaisieEnCours, raccourciDe } from './RaccourcisAtelier.helpers'

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
      <button
        type="button"
        onClick={() => setAideOuverte((ouverte) => !ouverte)}
        data-testid="cal-raccourcis-bouton"
        aria-expanded={aideOuverte}
        className="text-sm font-semibold text-primary-text underline"
      >
        Raccourcis clavier (?)
      </button>

      {aideOuverte && (
        <div
          role="dialog"
          aria-label="Aide-mémoire des raccourcis clavier"
          data-testid="cal-raccourcis-aide"
          className="mt-3 rounded border border-border bg-black/40 p-4"
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
      )}
    </div>
  )
}
