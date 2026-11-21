// CAL106 — re-snap en masse, sorti À L'IDENTIQUE de `layoutEditor.ts` (ACAL510 : un fichier de
// 2 000 lignes ou plus ne grossit pas). `layoutEditor.ts` le ré-exporte pour ses importeurs.

/* ════════════════════════════════════════════════════════════════════════════
   CAL106 — TENIR LA CHARGE DES GRANDS CHAMPS : LE RE-SNAP EN MASSE.
   ----------------------------------------------------------------------------
   Constat mesuré : le coût qui explose sur un grand champ n'est pas le rendu,
   c'est le RE-SNAP EN MASSE. `nearestEmptyCell` balaie TOUTES les cellules de
   la lattice pour UN centre ; les trois chemins de masse (retour depuis le
   placement libre, `reenterCustomLayout` après un re-pavage, `hydrateLayout` au
   rechargement d'un dossier) l'appellent une fois PAR panneau. C'est du
   N × M : 2 000 panneaux sur une lattice de 2 000 cellules = 4 000 000 de
   distances par geste, sur le fil d'exécution de l'interface. Dimensionné pour
   la villa (quelques dizaines), jamais mesuré sur un champ.

   `resnapEnMasse` fait le MÊME travail avec un index par cases : les cellules
   vides sont rangées dans une grille de cases, et la recherche part de la case
   du centre puis s'élargit en anneaux jusqu'à ce que l'anneau suivant ne puisse
   plus contenir mieux. Le coût redevient proportionnel au voisinage, pas à la
   lattice entière.

   ÉQUIVALENCE STRICTE, PAS « À PEU PRÈS PAREIL » — c'est la condition posée par
   la tâche (« aucun chiffre de calepinage ne change ») :
     * même critère : la cellule VIDE la plus proche au carré de la distance ;
     * même départage : à distance ÉGALE, la cellule qui vient en PREMIER dans
       l'ordre de la lattice — exactement ce que produit le balayage linéaire,
       qui n'améliore que sur un `<` strict ;
     * même effet de bord : chaque centre occupe sa cellule AVANT que le centre
       suivant ne cherche la sienne (l'ordre des centres compte, et il est
       préservé).
   Le test jumeau confronte les deux implémentations sur des cas aléatoires et
   exige des ensembles d'index IDENTIQUES.
   ══════════════════════════════════════════════════════════════════════════ */

/** Un centre à re-snapper (repère ENU, mètres). */
export interface CentreASnapper {
  cx: number;
  cy: number;
}

/**
 * CAL106 — RÉFÉRENCE : le balayage linéaire historique, extrait tel quel pour
 * que le test puisse confronter la version rapide à la sémantique d'origine.
 * Ce n'est pas du code mort : c'est l'étalon de l'équivalence.
 */
export function resnapNaif(
  cells: readonly { index: number; cx: number; cy: number }[],
  centres: readonly CentreASnapper[],
): number[] {
  const occupees = new Set<number>();
  const retenus: number[] = [];
  for (const p of centres) {
    let best = -1;
    let bestD = Infinity;
    for (const c of cells) {
      if (occupees.has(c.index)) continue;
      const dx = c.cx - p.cx;
      const dy = c.cy - p.cy;
      const d = dx * dx + dy * dy;
      if (d < bestD) {
        bestD = d;
        best = c.index;
      }
    }
    if (best >= 0) {
      occupees.add(best);
      retenus.push(best);
    }
  }
  return retenus;
}

/** Taille de case de l'index (m). Une case ≈ une travée : assez grande pour que
 *  le voisinage utile tienne en un ou deux anneaux, assez petite pour élaguer. */
const CASE_RESNAP_M = 4;

/**
 * CAL106 — re-snap en masse INDEXÉ. Rend les index de cellules occupées, dans
 * l'ordre des centres — strictement les mêmes que `resnapNaif`.
 */
export function resnapEnMasse(
  cells: readonly { index: number; cx: number; cy: number }[],
  centres: readonly CentreASnapper[],
): number[] {
  if (!cells.length || !centres.length) return [];

  // Rang de chaque cellule dans l'ORDRE DE LA LATTICE : c'est lui qui départage
  // à distance égale, comme le fait le balayage linéaire.
  const rang = new Map<number, number>();
  for (let i = 0; i < cells.length; i++) rang.set(cells[i].index, i);

  /* Clé de case NUMÉRIQUE : une `Map<number, …>` évite de fabriquer une chaîne
     à chaque sondage d'anneau — mesurable sur un grand champ. */
  const DECALAGE = 1_000_000;
  const cle = (ix: number, iy: number) => (ix + DECALAGE) * 4_000_000 + (iy + DECALAGE);
  const cases = new Map<number, number[]>(); // case → positions dans `cells`
  const cleDe = new Float64Array(cells.length);
  for (let i = 0; i < cells.length; i++) {
    const k = cle(Math.floor(cells[i].cx / CASE_RESNAP_M), Math.floor(cells[i].cy / CASE_RESNAP_M));
    cleDe[i] = k;
    const seau = cases.get(k);
    if (seau) seau.push(i);
    else cases.set(k, [i]);
  }

  // Portée maximale utile : les cases EXTRÊMES de la lattice. Elle est calculée
  // PAR CENTRE, parce qu'un centre peut tomber très loin de la lattice (un
  // dossier rechargé dans un autre repère) : une portée mesurée sur la seule
  // emprise de la lattice s'arrêterait avant de l'avoir atteinte, et rendrait
  // « aucune cellule » là où le balayage linéaire en trouvait une.
  let ixMin = Infinity; let ixMax = -Infinity; let iyMin = Infinity; let iyMax = -Infinity;
  for (const c of cells) {
    const ix = Math.floor(c.cx / CASE_RESNAP_M);
    const iy = Math.floor(c.cy / CASE_RESNAP_M);
    if (ix < ixMin) ixMin = ix;
    if (ix > ixMax) ixMax = ix;
    if (iy < iyMin) iyMin = iy;
    if (iy > iyMax) iyMax = iy;
  }

  const retenus: number[] = [];

  for (const p of centres) {
    const cx0 = Math.floor(p.cx / CASE_RESNAP_M);
    const cy0 = Math.floor(p.cy / CASE_RESNAP_M);
    let best = -1;
    let bestRang = Infinity;
    let bestD = Infinity;
    // Assez d'anneaux pour couvrir TOUTE la lattice depuis CE centre.
    const anneauMax = Math.max(
      Math.abs(cx0 - ixMin), Math.abs(cx0 - ixMax),
      Math.abs(cy0 - iyMin), Math.abs(cy0 - iyMax),
    ) + 1;

    const examiner = (ix: number, iy: number) => {
      const seau = cases.get(cle(ix, iy));
      if (!seau) return;
      // Un seau ne contient QUE des cellules encore libres (voir le retrait
      // plus bas) : plus aucun test d'occupation n'est nécessaire ici.
      for (let j = 0; j < seau.length; j++) {
        const pos = seau[j];
        const c = cells[pos];
        const dx = c.cx - p.cx;
        const dy = c.cy - p.cy;
        const d = dx * dx + dy * dy;
        // `<` strict pour la distance ; à ÉGALITÉ, le rang le plus petit gagne
        // — le même départage que le balayage linéaire d'origine.
        if (d < bestD || (d === bestD && pos < bestRang)) {
          bestD = d;
          best = c.index;
          bestRang = pos;
        }
      }
    };

    for (let r = 0; r <= anneauMax; r++) {
      if (r === 0) examiner(cx0, cy0);
      else {
        for (let ix = cx0 - r; ix <= cx0 + r; ix++) {
          examiner(ix, cy0 - r);
          examiner(ix, cy0 + r);
        }
        for (let iy = cy0 - r + 1; iy <= cy0 + r - 1; iy++) {
          examiner(cx0 - r, iy);
          examiner(cx0 + r, iy);
        }
      }
      // Distance minimale garantie de l'anneau SUIVANT : si le meilleur trouvé
      // est déjà plus proche, aucun anneau plus loin ne peut faire mieux.
      if (best >= 0) {
        const plancher = r * CASE_RESNAP_M;
        if (bestD <= plancher * plancher) break;
      }
    }

    if (best >= 0) {
      /* La cellule prise SORT de son seau : les centres suivants ne la
         reverront jamais. Sans ce retrait, les derniers centres re-balaient
         les cellules déjà occupées et le coût remonte au N² qu'on supprime —
         mesuré sur 2 000 centres / 2 000 cellules (le pire cas : la lattice
         finit saturée) : 154 ms AVEC re-balayage — donc PLUS LENT que les
         ~120 ms du balayage linéaire, l'index était devenu un ralentisseur —
         contre 20-48 ms une fois les cellules prises retirées de l'index. */
      const seau = cases.get(cleDe[bestRang]);
      if (seau) {
        const j = seau.indexOf(bestRang);
        if (j >= 0) {
          seau[j] = seau[seau.length - 1];
          seau.pop();
          if (!seau.length) cases.delete(cleDe[bestRang]);
        }
      }
      retenus.push(best);
    }
  }
  return retenus;
}
