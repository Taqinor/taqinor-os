/* eslint-disable react-refresh/only-export-components --
   `RACCOURCIS` (la table) et `estSaisieEnCours` (le garde-fou) sont des
   données/fonctions PURES : le test jumeau les PARCOURT pour exiger que chaque
   raccourci soit à la fois listé dans l'aide-mémoire ET réellement déclenché.
   Même dérogation que `module.config.jsx` du même module. */
import { useEffect, useState } from 'react'

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

/**
 * CAL101 — la table UNIQUE des raccourcis.
 * `action` est la clé du gestionnaire attendu dans la prop `actions` ;
 * `touche` est comparée à `event.key` SANS casse ; `ctrl` exige la touche
 * Contrôle (ou Commande) ; `libelle` est ce que l'aide affiche.
 */
export const RACCOURCIS = [
  { action: 'outilTrace', touche: 't', libelle: 'Outil tracé de toit', affichage: 'T' },
  { action: 'outilObstacle', touche: 'o', libelle: 'Outil obstacle', affichage: 'O' },
  { action: 'outilZone', touche: 'z', libelle: 'Outil zone', affichage: 'Z' },
  { action: 'outilMesure', touche: 'm', libelle: 'Outil mesure', affichage: 'M' },
  { action: 'aimantation', touche: 'a', libelle: 'Activer ou couper l’aimantation', affichage: 'A' },
  { action: 'supprimer', touche: 'delete', libelle: 'Supprimer la sélection', affichage: 'Suppr' },
  { action: 'dupliquer', touche: 'd', ctrl: true, libelle: 'Dupliquer la sélection', affichage: 'Ctrl + D' },
  { action: 'pleinEcran', touche: 'f', libelle: 'Plein écran', affichage: 'F' },
]

/** La touche qui ouvre l'aide — le « ? » usuel des outils de conception. */
export const TOUCHE_AIDE = '?'

/**
 * CAL101 — vrai quand la frappe appartient à un champ de saisie. Un raccourci
 * qui volerait cette frappe rendrait les formulaires inutilisables : c'est la
 * garde la plus importante de ce fichier.
 */
export function estSaisieEnCours(cible) {
  if (!cible) return false
  const balise = (cible.tagName || '').toLowerCase()
  if (balise === 'input' || balise === 'textarea' || balise === 'select') return true
  if (cible.isContentEditable) return true
  // `contenteditable` posé en attribut (jsdom ne calcule pas toujours
  // `isContentEditable`) : on lit l'attribut lui-même.
  const attribut = typeof cible.getAttribute === 'function'
    ? cible.getAttribute('contenteditable') : null
  return attribut === '' || attribut === 'true'
}

/** Le raccourci que cette frappe désigne, ou `null`. */
export function raccourciDe(evenement) {
  const touche = String(evenement.key || '').toLowerCase()
  const avecCtrl = Boolean(evenement.ctrlKey || evenement.metaKey)
  return RACCOURCIS.find((r) => r.touche === touche
    && Boolean(r.ctrl) === avecCtrl) ?? null
}

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
