// WJ129 — Visionneuse plein écran du schéma électrique (SLD) : la géométrie
// PURE du pan/zoom/pinch (aucun DOM, aucune bibliothèque) qui remplace le
// SVG écrasé (302×213 px illisible en mobile) par une carte-teaser + une
// visionneuse plein écran. Voir [token].astro (section `#sld`) pour le
// branchement Pointer Events/wheel sur ces fonctions.
import { describe, expect, it } from 'vitest';
import {
  SLD_MAX_SCALE,
  SLD_MIN_SCALE,
  centeredTranslate,
  clamp,
  clampPanAxis,
  clampTranslate,
  doubleTapScale,
  fitScale,
  isDoubleTap,
  parseViewBoxSize,
  pinchScale,
  pointDistance,
  pointMidpoint,
  zoomAtPoint,
} from '../src/lib/sldViewer';

describe('WJ129 — clamp', () => {
  it('borne à l’intérieur des limites', () => {
    expect(clamp(3, 0.5, 5)).toBe(3);
  });
  it('borne en dessous → min', () => {
    expect(clamp(0.1, 0.5, 5)).toBe(0.5);
  });
  it('borne au-dessus → max', () => {
    expect(clamp(9, 0.5, 5)).toBe(5);
  });
  it('NaN → repli sur min (jamais NaN en sortie)', () => {
    expect(clamp(Number.NaN, 0.5, 5)).toBe(0.5);
  });
});

describe('WJ129 — fitScale (fit-to-width/height du schéma dans le viewport)', () => {
  it('contenu plus large que haut, viewport carré → limité par la largeur', () => {
    // viewBox 1122×794 (mentionné par l’audit) dans un viewport 400×400.
    const s = fitScale({ width: 400, height: 400 }, { width: 1122, height: 794 });
    expect(s).toBeCloseTo(400 / 1122, 6);
  });

  it('viewport large et bas (desktop) → limité par la hauteur', () => {
    const s = fitScale({ width: 2000, height: 300 }, { width: 1122, height: 794 });
    expect(s).toBeCloseTo(300 / 794, 6);
  });

  it('viewport ou contenu invalide (0/négatif) → repli 1, jamais NaN/Infinity', () => {
    expect(fitScale({ width: 0, height: 400 }, { width: 1122, height: 794 })).toBe(1);
    expect(fitScale({ width: 400, height: 400 }, { width: -1, height: 794 })).toBe(1);
    expect(fitScale({ width: 400, height: 400 }, { width: 1122, height: 0 })).toBe(1);
  });
});

describe('WJ129 — centeredTranslate', () => {
  it('centre un contenu plus petit que le viewport', () => {
    const t = centeredTranslate({ width: 400, height: 300 }, { width: 100, height: 100 }, 1);
    expect(t).toEqual({ x: 150, y: 100 });
  });

  it('applique l’échelle avant de centrer', () => {
    const t = centeredTranslate({ width: 400, height: 300 }, { width: 1122, height: 794 }, 400 / 1122);
    // largeur mise à l’échelle == largeur viewport → tx = 0
    expect(t.x).toBeCloseTo(0, 6);
    expect(t.y).toBeGreaterThan(0); // hauteur mise à l’échelle < 300 → marge verticale
  });
});

describe('WJ129 — pointDistance / pointMidpoint (géométrie du pincement)', () => {
  it('distance euclidienne standard', () => {
    expect(pointDistance({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5);
  });
  it('point médian', () => {
    expect(pointMidpoint({ x: 0, y: 0 }, { x: 10, y: 20 })).toEqual({ x: 5, y: 10 });
  });
});

describe('WJ129 — pinchScale (calcul d’échelle du pincement à deux doigts)', () => {
  it('doigts qui s’écartent → zoom avant proportionnel', () => {
    expect(pinchScale(1, 100, 200)).toBe(2);
  });
  it('doigts qui se rapprochent → zoom arrière proportionnel', () => {
    expect(pinchScale(2, 200, 100)).toBe(1);
  });
  it('borné à SLD_MAX_SCALE même sur un écart énorme', () => {
    expect(pinchScale(1, 10, 10000)).toBe(SLD_MAX_SCALE);
  });
  it('borné à SLD_MIN_SCALE même sur un pincement extrême', () => {
    expect(pinchScale(1, 1000, 1)).toBe(SLD_MIN_SCALE);
  });
  it('distance de départ ou courante nulle/négative → échelle de départ inchangée (bornée), jamais Infinity/NaN', () => {
    expect(pinchScale(1.2, 0, 100)).toBeCloseTo(1.2, 6);
    expect(pinchScale(1.2, 100, 0)).toBeCloseTo(1.2, 6);
    expect(pinchScale(1.2, -5, 100)).toBeCloseTo(1.2, 6);
  });
});

describe('WJ129 — zoomAtPoint (zoom au curseur/pincement/double-tap, point ancré)', () => {
  it('zoom ×2 centré sur l’origine du contenu (ancre == origine actuelle du contenu)', () => {
    // Contenu affiché à scale=1, translate=(0,0) → l’ancre (0,0) est déjà le
    // coin haut-gauche du contenu : il doit rester à (0,0) après le zoom.
    const t = zoomAtPoint({ x: 0, y: 0 }, 1, 2, { x: 0, y: 0 });
    expect(t).toEqual({ x: 0, y: 0 });
  });

  it('le point du contenu sous l’ancre reste visuellement immobile après le zoom', () => {
    const translate = { x: -50, y: -30 };
    const scale = 1;
    const anchor = { x: 120, y: 80 };
    const newScale = 3;
    const t = zoomAtPoint(translate, scale, newScale, anchor);
    // Reconstruit le point du contenu sous l’ancre AVANT et APRÈS : doit être identique.
    const contentBefore = { x: (anchor.x - translate.x) / scale, y: (anchor.y - translate.y) / scale };
    const contentAfter = { x: (anchor.x - t.x) / newScale, y: (anchor.y - t.y) / newScale };
    expect(contentAfter.x).toBeCloseTo(contentBefore.x, 6);
    expect(contentAfter.y).toBeCloseTo(contentBefore.y, 6);
  });

  it('échelle de départ invalide (0) → translation inchangée (jamais une division par zéro)', () => {
    const t = zoomAtPoint({ x: 10, y: 20 }, 0, 2, { x: 5, y: 5 });
    expect(t).toEqual({ x: 10, y: 20 });
  });
});

describe('WJ129 — doubleTapScale (bascule double-tap : fit → ×2 → fit)', () => {
  it('proche du fit → zoom ×2 (borné)', () => {
    expect(doubleTapScale(1, 1)).toBe(2);
  });
  it('déjà zoomé (loin du fit) → retour au fit', () => {
    expect(doubleTapScale(3, 1)).toBe(1);
  });
  it('le zoom ×2 reste borné à SLD_MAX_SCALE quand le fit est déjà élevé', () => {
    expect(doubleTapScale(4, 4)).toBe(SLD_MAX_SCALE);
  });
  it('epsilon absorbe une imprécision flottante autour du fit', () => {
    expect(doubleTapScale(1.0001, 1)).toBe(2);
  });
});

describe('WJ129 — clampPanAxis (bornes de pan par axe)', () => {
  it('contenu plus petit que le viewport → centré, aucune marge de pan', () => {
    expect(clampPanAxis(999, 400, 100)).toBe(150);
    expect(clampPanAxis(-999, 400, 100)).toBe(150);
  });
  it('contenu plus grand → translation bornée entre (viewport-contenu) et 0', () => {
    expect(clampPanAxis(0, 400, 1000)).toBe(0);
    expect(clampPanAxis(-1000, 400, 1000)).toBe(-600);
    expect(clampPanAxis(200, 400, 1000)).toBe(0); // ne peut pas laisser le bord proche flotter
    expect(clampPanAxis(-9999, 400, 1000)).toBe(-600); // ne peut pas laisser le bord loin flotter
  });
});

describe('WJ129 — clampTranslate (les deux axes ensemble)', () => {
  it('borne x et y indépendamment selon la taille mise à l’échelle', () => {
    const t = clampTranslate(
      { x: 500, y: -500 },
      { width: 400, height: 300 },
      { width: 1122, height: 794 },
      1, // scale=1 → contenu 1122×794, plus grand que le viewport sur les deux axes
    );
    expect(t.x).toBe(0); // 500 borné à max=0
    expect(t.y).toBe(300 - 794); // -500 borné à min=(viewport-contenu)
  });
});

describe('WJ129 — TapRecord/isDoubleTap (détection double-tap/double-clic)', () => {
  it('premier tap de la session (prev=null) → jamais un double-tap', () => {
    expect(isDoubleTap(null, { x: 10, y: 10, time: 0 })).toBe(false);
  });
  it('proche en temps ET en espace → double-tap', () => {
    expect(isDoubleTap({ x: 10, y: 10, time: 0 }, { x: 15, y: 12, time: 250 })).toBe(true);
  });
  it('trop lent (> 300 ms par défaut) → pas un double-tap', () => {
    expect(isDoubleTap({ x: 10, y: 10, time: 0 }, { x: 10, y: 10, time: 400 })).toBe(false);
  });
  it('trop loin (> 40 px par défaut) → pas un double-tap (deux taps distincts)', () => {
    expect(isDoubleTap({ x: 10, y: 10, time: 0 }, { x: 100, y: 100, time: 100 })).toBe(false);
  });
  it('horodatage à rebours (dt négatif) → jamais un double-tap', () => {
    expect(isDoubleTap({ x: 10, y: 10, time: 500 }, { x: 10, y: 10, time: 100 })).toBe(false);
  });
  it('seuils personnalisés respectés', () => {
    expect(isDoubleTap({ x: 0, y: 0, time: 0 }, { x: 60, y: 0, time: 50 }, 300, 100)).toBe(true);
  });
});

describe('WJ129 — parseViewBoxSize (lecture défensive du viewBox SVG backend)', () => {
  it('viewBox standard espaces → {width, height}', () => {
    expect(parseViewBoxSize('0 0 1122 794')).toEqual({ width: 1122, height: 794 });
  });
  it('séparateurs virgule acceptés', () => {
    expect(parseViewBoxSize('0,0,1122,794')).toEqual({ width: 1122, height: 794 });
  });
  it('minX/minY non nuls sans incidence sur la taille lue', () => {
    expect(parseViewBoxSize('-50 -20 800 600')).toEqual({ width: 800, height: 600 });
  });
  it('absent/null/undefined → null (jamais une taille inventée)', () => {
    expect(parseViewBoxSize(null)).toBeNull();
    expect(parseViewBoxSize(undefined)).toBeNull();
    expect(parseViewBoxSize('')).toBeNull();
  });
  it('malformé (nombre de segments incorrect, valeurs non numériques) → null', () => {
    expect(parseViewBoxSize('0 0 1122')).toBeNull();
    expect(parseViewBoxSize('a b c d')).toBeNull();
  });
  it('largeur/hauteur non positive → null', () => {
    expect(parseViewBoxSize('0 0 0 794')).toBeNull();
    expect(parseViewBoxSize('0 0 1122 -10')).toBeNull();
  });
});
