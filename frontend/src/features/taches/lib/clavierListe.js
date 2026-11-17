import { useEffect, useRef } from 'react'

/* ============================================================================
   TCH46 — Clavier des listes de tâches (spec-7 §5). Une touche ne vaut QUE sur une ligne
   focalisée ; elle ne fait JAMAIS disparaître une ligne (règle maison du 02/10 : Supprimer et
   Abandonner passent par un menu ou un dialogue nommant la tâche — aucune touche seule).

   | j · k                | ligne suivante / précédente (Proposé compris), focus sur son titre |
   | Espace               | Fait (défait) — `terminer`                                        |
   | e · d · m · x · h · *| `renommer` · `quand` · `deplacer` · `selectionner` · `heure` · `essentiel` |
   | Alt+↑ · Alt+↓        | `monter` · `descendre` (réordonner)                               |
   | Maj+↓                | `allonger` (bloc d'agenda, +15 min)                               |
   | Ctrl/⌘ Z             | `annuler` (hors d'un champ)                                       |

   MUET : sous un dialogue modal ; dans un champ de saisie ; et (N1) pendant le délai de
   séquence qui suit `g` ou `c` (les touches `g j` et `c t` appartiennent aux raccourcis
   globaux de l'ERP). Les lignes sont les éléments `[data-ligne]` (LigneTache) ; l'élément
   focalisé d'une ligne est son bouton de titre `.ligne-corps-bouton`.
   ========================================================================== */

/** Délai (ms) pendant lequel la touche suivant `g` ou `c` appartient à la séquence globale. */
export const SEQUENCE_MS = 1000

const SIMPLES = { ' ': 'terminer', e: 'renommer', d: 'quand', m: 'deplacer', x: 'selectionner', h: 'heure', '*': 'essentiel' }
const SEQUENCES = new Set(['g', 'c'])

/** Vrai si l'événement vient d'un champ de saisie (la frappe y est du texte, jamais un raccourci). */
export function dansUnChamp(cible) {
  if (!cible || typeof cible.closest !== 'function') return false
  if (cible.isContentEditable) return true
  return Boolean(cible.closest('input, textarea, select, [contenteditable=""], [contenteditable="true"], [role="textbox"], [role="combobox"]'))
}

/** Vrai tant qu'un dialogue modal est ouvert : le clavier de la liste se tait. */
export function sousDialogue(doc = document) {
  return Boolean(doc.querySelector('[role="dialog"][aria-modal="true"], [role="alertdialog"]'))
}

/**
 * L'action qu'une frappe déclenche, ou `null` (pur : aucune lecture du DOM hors `evenement`).
 * `j` et `k` rendent `'suivante'` / `'precedente'`.
 */
export function actionDeTouche(evenement) {
  const { key, ctrlKey, metaKey, altKey, shiftKey } = evenement
  const minuscule = typeof key === 'string' ? key.toLowerCase() : ''
  if ((ctrlKey || metaKey) && !altKey && minuscule === 'z' && !shiftKey) return 'annuler'
  if (ctrlKey || metaKey) return null
  if (altKey && key === 'ArrowUp') return 'monter'
  if (altKey && key === 'ArrowDown') return 'descendre'
  if (altKey) return null
  if (shiftKey && key === 'ArrowDown') return 'allonger'
  if (key === 'j') return 'suivante'
  if (key === 'k') return 'precedente'
  if (shiftKey && key !== '*') return null
  return SIMPLES[key] ?? null
}

const lignesDe = (racine) => [...racine.querySelectorAll('[data-ligne]')].filter((el) => !el.closest('[hidden], [inert]'))
const focalisable = (ligne) => ligne.querySelector('.ligne-corps-bouton') ?? ligne.querySelector('button')

/** Focalise la ligne suivante (`1`) ou précédente (`-1`) ; la première si aucune n'est focalisée. */
export function parcourir(racine, sens) {
  const lignes = lignesDe(racine)
  if (lignes.length === 0) return null
  const courante = document.activeElement?.closest?.('[data-ligne]')
  const i = courante ? lignes.indexOf(courante) : -1
  const cible = i < 0 ? lignes[sens > 0 ? 0 : lignes.length - 1] : lignes[Math.min(Math.max(i + sens, 0), lignes.length - 1)]
  focalisable(cible)?.focus()
  return cible
}

/**
 * Branche le clavier sur une liste et RENVOIE la ref du conteneur des lignes (`<div ref={racine}>`).
 * `surAction(action, { ligne, cle })` reçoit les autres actions (`cle` = `data-ligne` : « tache:20 »,
 * « activite:101 »). Se détache au démontage.
 */
export function useClavierListe(surAction, { actif = true } = {}) {
  const racine = useRef(null)
  const derniere = useRef({ touche: '', instant: 0 })
  const espaceGere = useRef(false)
  const rappel = useRef(surAction)
  useEffect(() => { rappel.current = surAction })

  useEffect(() => {
    if (!actif) return undefined
    const surTouche = (e) => {
      const maintenant = Date.now()
      const avant = derniere.current
      derniere.current = { touche: e.key, instant: maintenant }
      if (e.defaultPrevented || e.repeat) return
      if (SEQUENCES.has(avant.touche) && maintenant - avant.instant < SEQUENCE_MS) return
      if (dansUnChamp(e.target) || sousDialogue()) return
      const zone = racine.current
      if (!zone) return
      const action = actionDeTouche(e)
      if (!action) return
      if (action === 'suivante' || action === 'precedente') {
        e.preventDefault()
        parcourir(zone, action === 'suivante' ? 1 : -1)
        return
      }
      const ligne = e.target?.closest?.('[data-ligne]') ?? null
      if (action === 'annuler') { e.preventDefault(); rappel.current?.('annuler', { ligne: null, cle: null }); return }
      if (!ligne || !zone.contains(ligne)) return
      e.preventDefault()
      if (e.key === ' ') espaceGere.current = true
      rappel.current?.(action, { ligne, cle: ligne.dataset.ligne })
    }
    // Espace active un bouton au RELÂCHEMENT : on l'avale aussi, sinon la case se coche deux fois
    const surRelache = (e) => {
      if (e.key === ' ' && espaceGere.current) { espaceGere.current = false; e.preventDefault() }
    }
    document.addEventListener('keydown', surTouche)
    document.addEventListener('keyup', surRelache)
    return () => {
      document.removeEventListener('keydown', surTouche)
      document.removeEventListener('keyup', surRelache)
    }
  }, [actif])
  return racine
}
