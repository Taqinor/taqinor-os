import { useEffect, useState } from 'react'
import { RACCOURCIS, estSaisieEnCours, raccourciDe } from './RaccourcisAtelier.helpers'

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

  useEffect(() => {
    const surTouche = (evenement) => {
      // LA GARDE : une frappe dans un champ appartient au champ.
      if (estSaisieEnCours(evenement.target)) return

      if (evenement.key === TOUCHE_AIDE) {
        evenement.preventDefault()
        setAideOuverte((ouverte) => !ouverte)
        return
      }
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

  return (
    <div data-testid="cal-raccourcis">
      <button
        type="button"
        onClick={() => setAideOuverte((ouverte) => !ouverte)}
        data-testid="cal-raccourcis-bouton"
        aria-expanded={aideOuverte}
        className="text-sm font-semibold text-brass-300 underline"
      >
        Raccourcis clavier (?)
      </button>

      {aideOuverte && (
        <div
          role="dialog"
          aria-label="Aide-mémoire des raccourcis clavier"
          data-testid="cal-raccourcis-aide"
          className="mt-3 rounded border border-white/15 bg-black/40 p-4"
        >
          <p className="tech-label text-lune-faint">
            Raccourcis de l’atelier — inactifs pendant la saisie d’un champ
          </p>
          <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
            {RACCOURCIS.map((raccourci) => (
              <div key={raccourci.action} className="flex items-baseline gap-2"
                data-testid={`cal-raccourci-${raccourci.action}`}>
                <dt>
                  <kbd className="rounded bg-white/10 px-1.5 text-xs text-white">
                    {raccourci.affichage}
                  </kbd>
                </dt>
                <dd className="text-sm text-lune-soft">{raccourci.libelle}</dd>
              </div>
            ))}
            <div className="flex items-baseline gap-2" data-testid="cal-raccourci-aide">
              <dt>
                <kbd className="rounded bg-white/10 px-1.5 text-xs text-white">?</kbd>
              </dt>
              <dd className="text-sm text-lune-soft">Afficher ou masquer cette aide</dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  )
}
