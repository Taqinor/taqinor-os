/**
 * CALX129 — LE PLEIN ÉCRAN RÉVERSIBLE, PARTAGÉ. ZÉRO React, ZÉRO DOM global.
 * ----------------------------------------------------------------------------
 * Constat de la tâche : le plein écran n'existe que pour l'onglet de vue plan
 * (`Vue2DPlan.jsx`, CAL104 — API Fullscreen + repli CSS) ; la vue 3D
 * d'édition n'en a pas. Ce module extrait la MÊME mécanique — déjà en
 * service dans `Vue2DPlan.jsx`, non touché ici (hors périmètre de cette
 * lane) — pour que `ToitureDesign.jsx` bascule le conteneur de la scène 3D
 * sans dupliquer sa propre copie de la danse Fullscreen/repli.
 *
 * Ce fichier ne connaît ni `document` ni `window` en dur : `element` et `doc`
 * sont reçus en paramètre, ce qui le rend exécutable sous `node --test`
 * (aucun jsdom) et réutilisable par n'importe quel écran de l'atelier.
 *
 * RÉVERSIBLE, SANS RIEN DÉMONTER : ce module ne touche jamais au contenu de
 * `element` (aucun montage/démontage, aucun accès au builder) — il ne fait
 * que demander/quitter le plein écran natif sur l'élément qu'on lui donne, et
 * dire si le CSS doit prendre le relais. L'appelant (le composant) garde donc
 * le MÊME objet d'API de builder avant/après la bascule, par construction :
 * aucune ligne de ce module ne peut le recréer.
 */

/**
 * Demande ou quitte le plein écran sur `element`, selon `enPleinEcranActuel`.
 * Renvoie le nouvel état `{ enPleinEcran, repliCss }` :
 *   - `repliCss` vaut `true` quand l'API Fullscreen est absente du navigateur
 *     ou refuse la demande — le CSS prend alors seul le relais, avec la MÊME
 *     réversibilité (aucun état perdu, aucun geste en moins) ;
 *   - `element` absent ⇒ l'état ne bouge pas (rien à basculer).
 */
export async function basculerPleinEcran(element, doc, enPleinEcranActuel) {
  if (!element) return { enPleinEcran: enPleinEcranActuel, repliCss: false }

  if (enPleinEcranActuel) {
    try {
      if (doc?.fullscreenElement && typeof doc.exitFullscreen === 'function') {
        await doc.exitFullscreen()
      }
    } catch {
      /* Sortie refusée par le navigateur : le repli CSS de l'appelant suffit
         à rendre la main — jamais un état bloqué en plein écran. */
    }
    return { enPleinEcran: false, repliCss: false }
  }

  try {
    if (typeof element.requestFullscreen === 'function') {
      await element.requestFullscreen()
      return { enPleinEcran: true, repliCss: false }
    }
  } catch {
    /* Refusé (permission, contexte non interactif…) : repli CSS ci-dessous. */
  }
  return { enPleinEcran: true, repliCss: true }
}

/**
 * `true` quand `doc` rapporte EFFECTIVEMENT `element` comme son élément plein
 * écran — jamais deviné depuis un état local. Sert à suivre une sortie par
 * Échap (l'appelant écoute `fullscreenchange` et rappelle cette fonction :
 * MÊME repli que `Vue2DPlan.jsx`, on ne suppose jamais que le bouton est la
 * seule sortie).
 */
export function estEnPleinEcranSur(doc, element) {
  return !!(doc && element && doc.fullscreenElement === element)
}
