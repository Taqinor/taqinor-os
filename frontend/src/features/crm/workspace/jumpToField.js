/* ROUND 5 — LE saut canonique vers une section / un champ du centre.
   ---------------------------------------------------------------------------
   Il en existait DEUX, et ils ne faisaient pas la même chose :
     • `SectionsPane.jumpTo` dépliait la section cible avant de scroller ;
     • `DevisTab.jumpToMissingField` NE dépliait PAS — un champ dans une
       section repliée n'est même pas dans le DOM, alors `getElementById`
       renvoyait null et on retombait sur un scroll jusqu'à l'en-tête. Cliquer
       « facture hiver » amenait donc parfois AU champ, parfois seulement à un
       titre replié : le même geste, deux résultats. Le commentaire de l'époque
       l'assumait comme une limite de périmètre ; elle disparaît ici.

   UN seul chemin, et il DÉPLIE TOUJOURS avant de scroller. Le dépli passe par
   le bouton d'en-tête de la section — l'affordance publique, celle que
   l'utilisatrice actionnerait elle-même : aucun état n'a besoin d'être
   remonté, et le choix est persisté exactement comme un dépli manuel (c'est
   bien un choix d'utilisateur : elle a cliqué pour aller là).

   Module DOM pur (aucun React) : testable et réutilisable des deux côtés. */

/**
 * jumpToField — déplie, amène en vue, puis focalise.
 *
 * @param {{section?: string, field?: string, root?: Element|Document}} cible
 *   `section` = `data-nav-id` du registre SectionsPane ; `field` = id DOM
 *   `lf-*` du champ (optionnel : sans lui on s'arrête à l'en-tête de section).
 * @returns {boolean} faux si la cible est introuvable (rien n'a été fait).
 */
export function jumpToField({ section, field, root } = {}) {
  const scope = root || (typeof document !== 'undefined' ? document : null)
  if (!scope) return false
  const ancre = section ? scope.querySelector(`[data-nav-id="${section}"]`) : null
  if (!ancre && !field) return false

  // (1) DÉPLIER — toujours, et avant tout le reste.
  const entete = ancre?.querySelector('.lw-section-head')
  if (entete && entete.getAttribute('aria-expanded') === 'false') entete.click()

  // (2) Au frame suivant : le corps de la section vient d'être monté, le champ
  // n'existait pas encore quand on a cliqué.
  const aller = () => {
    const el = field && typeof document !== 'undefined' ? document.getElementById(field) : null
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.focus()
      return
    }
    ancre?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  if (typeof requestAnimationFrame === 'function') requestAnimationFrame(aller)
  else aller()
  return true
}

export default jumpToField
