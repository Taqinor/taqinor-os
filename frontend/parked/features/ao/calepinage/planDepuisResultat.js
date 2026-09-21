/* ============================================================================
   Adaptateur de RENDU : résultat de `/ao/calepinage/calculer/` → charge utile
   de `PlanLayer`. Recâblage du 03/08/2026.
   ----------------------------------------------------------------------------
   POURQUOI CE FICHIER EXISTE — dit franchement.
   `PlanLayer` a été écrit contre une charge utile de DESSIN (`cadre`, `allees`,
   `rives`, `degagements`, `obstacles`, `zones`, `legende`, traits de faîtage)
   que le serveur ne publie sous AUCUNE route. Ce que le serveur publie
   réellement, c'est la géométrie POSÉE par le moteur :

     resultat.plans[] = { surface, modules, ecart_a_l_optimum,
                          rangees: [{surface, x0, y0, kit, modules,
                                     emprise_m, troncons}],
                          tables:  [{x0, x1, y0, y1, kit}] }

   (source : `apps/ao/calepinage_io.plan_vers_json` / `resultat_vers_json`,
   sérialisé par `ResultatCalepinageSerializer`.)

   Ce module fait UNE chose et rien d'autre : traduire des COINS de rectangle
   (`x0,x1,y0,y1`) en rectangles SVG (`x, y, largeur_m, hauteur_m`) et calculer
   la FENÊTRE d'affichage qui les contient. Ce ne sont pas des grandeurs
   métier : le serveur ne publie ni l'un ni l'autre, il n'y a donc rien à
   « recalculer ». Aucun compte, aucun kWc, aucune marge n'est dérivé ici — ils
   viennent du résultat, tels quels (cf. la garde de code d'AOF94).

   AUCUN AXE N'EST RENVERSÉ. On pose les coordonnées du moteur telles quelles,
   comme `PlanLayer` s'y engage : « dessiné = compté ».

   CE QUI RESTE VIDE, ET POURQUOI (à ne pas remplir par déduction) :
     • `allees` / `rives` / `degagements` / `obstacles` / `zones` — le résultat
       ne porte AUCUNE de ces couches. Les déduire (bandes entre rangées,
       emprises d'obstacles rejouées côté client…) fabriquerait un dessin que
       le serveur n'a pas produit : la planche PDF et l'écran divergeraient.
     • `faitage` — la table posée ne porte pas son trait de faîtage.
     • `cote` — aucun texte coté n'est publié ; le front ne formate aucun
       nombre (règle : les textes viennent de `core.formats_fr`, côté serveur).
   Chacune de ces couches apparaîtra d'elle-même le jour où une route la
   publie ; d'ici là, son absence se VOIT au lieu d'être simulée.
   ========================================================================== */

/**
 * @param {object|null} resultat  Corps de `/ao/calepinage/calculer/`.
 * @returns {object|null} Charge utile `PlanLayer`, ou `null` si rien n'est posé.
 */
export default function planDepuisResultat(resultat) {
  const feuilles = Array.isArray(resultat?.plans) ? resultat.plans : []
  const groupes = []
  const abscisses = []
  const ordonnees = []

  for (const feuille of feuilles) {
    const poses = Array.isArray(feuille?.tables) ? feuille.tables : []
    const dessins = []
    for (let rang = 0; rang < poses.length; rang += 1) {
      const pose = poses[rang]
      const gauche = Math.min(pose.x0, pose.x1)
      const droite = Math.max(pose.x0, pose.x1)
      const haut = Math.min(pose.y0, pose.y1)
      const bas = Math.max(pose.y0, pose.y1)
      if (![gauche, droite, haut, bas].every(Number.isFinite)) continue
      abscisses.push(gauche, droite)
      ordonnees.push(haut, bas)
      dessins.push({
        id: `${feuille.surface}#${rang}`,
        kit: pose.kit,
        x: gauche,
        y: haut,
        largeur_m: droite - gauche,
        hauteur_m: bas - haut,
      })
    }
    // UN groupe par SURFACE (le découpage que le serveur donne), jamais un
    // regroupement par rangée reconstitué ici : `PlanLayer` interdit
    // explicitement un regroupement recalculé côté front.
    if (dessins.length > 0) {
      groupes.push({ id: feuille.surface, tables: dessins })
    }
  }

  if (abscisses.length === 0) return null

  const xMin = Math.min(...abscisses)
  const yMin = Math.min(...ordonnees)
  return {
    cadre: {
      x_min: xMin,
      y_min: yMin,
      largeur_m: Math.max(...abscisses) - xMin,
      hauteur_m: Math.max(...ordonnees) - yMin,
    },
    rangees: groupes,
  }
}
