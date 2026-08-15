// PV80 — Refonte de /proposition/<token> : logique PURE du graphique fusionné
// « Votre production » (vue année ↔ journée, onglets de profil, CALQUE batterie)
// et extraction du token depuis la route catch-all (slug décoratif optionnel).
//
// L'invariant central de la refonte est vérifié ici : le bloc production ne
// montre JAMAIS deux dessins à la fois (c'est exactement ce que la page faisait
// avant — trois graphes empilés du même sujet).
import { describe, expect, it } from 'vitest';
import {
  type ProductionAvailability,
  availableViews,
  hasProductionBlock,
  initialProductionState,
  setProductionView,
  setCurveVariant,
  setBatteryLayer,
  productionLayers,
  proposalPathSegments,
  tokenFromSegments,
  decorativeSlug,
  classifyEquipment,
  groupEquipment,
  equipmentLineCount,
  equipmentDelta,
} from '../src/lib/propositionPage';

/** Devis résidentiel complet : les deux vues, les 3 profils, le calque batterie. */
const FULL: ProductionAvailability = {
  monthly: true,
  daily: true,
  variants: ['normal', 'ete', 'ramadan'],
  battery: true,
};

describe('PV80 — graphique fusionné : vues disponibles', () => {
  it('propose année puis journée quand les deux sont rendues', () => {
    // Fondateur 2026-08-15 : la journée d'abord (défaut), l'année ensuite.
    expect(availableViews(FULL)).toEqual(['journee', 'annee']);
    expect(hasProductionBlock(FULL)).toBe(true);
  });

  it('ne propose que la vue rendue quand une seule série existe', () => {
    expect(availableViews({ monthly: true, daily: false, variants: [], battery: false })).toEqual(['annee']);
    expect(availableViews({ monthly: false, daily: true, variants: ['normal'], battery: false })).toEqual(['journee']);
  });

  it('omet tout le bloc quand le backend ne fournit aucune série', () => {
    expect(hasProductionBlock({ monthly: false, daily: false, variants: [], battery: false })).toBe(false);
    expect(hasProductionBlock(null)).toBe(false);
    expect(hasProductionBlock(undefined)).toBe(false);
  });

  it('ignore un calque batterie annoncé sans courbe journalière (impossible à superposer)', () => {
    const layers = productionLayers(
      { view: 'journee', variant: 'normal', battery: true },
      { monthly: true, daily: false, variants: [], battery: true },
    );
    expect(layers.battery).toBe(false);
    expect(layers.showBatteryToggle).toBe(false);
    // Repli sur la seule vue réellement rendue.
    expect(layers.monthly).toBe(true);
  });
});

describe('PV80 — graphique fusionné : état initial', () => {
  it('démarre sur l’année, profil standard, batterie décochée', () => {
    expect(initialProductionState(FULL)).toEqual({ view: 'journee', variant: 'normal', battery: false });
  });

  it('démarre sur la journée quand les barres mensuelles manquent', () => {
    const s = initialProductionState({ monthly: false, daily: true, variants: ['normal'], battery: true });
    expect(s.view).toBe('journee');
    expect(s.battery).toBe(false);
  });
});

describe('PV80 — graphique fusionné : un seul dessin visible à la fois', () => {
  const onlyOne = (l: { monthly: boolean; daily: boolean; battery: boolean }) =>
    [l.monthly, l.daily, l.battery].filter(Boolean).length;

  it('vue année : barres seules', () => {
    const l = productionLayers({ view: 'annee', variant: 'normal', battery: false }, FULL);
    expect(l.monthly).toBe(true);
    expect(onlyOne(l)).toBe(1);
    expect(l.showVariantTabs).toBe(false);
    expect(l.showBatteryToggle).toBe(false);
  });

  it('vue journée : courbe seule, onglets de profil et case batterie offerts', () => {
    const l = productionLayers({ view: 'journee', variant: 'normal', battery: false }, FULL);
    expect(l.daily).toBe(true);
    expect(onlyOne(l)).toBe(1);
    expect(l.showVariantTabs).toBe(true);
    expect(l.showBatteryToggle).toBe(true);
    expect(l.showViewTabs).toBe(true);
  });

  it('calque batterie : REMPLACE la courbe nue, jamais un second graphique', () => {
    const l = productionLayers({ view: 'journee', variant: 'normal', battery: true }, FULL);
    expect(l.battery).toBe(true);
    expect(l.daily).toBe(false);
    expect(l.monthly).toBe(false);
    expect(onlyOne(l)).toBe(1);
  });

  it('le calque batterie reste invisible tant qu’on est sur la vue année', () => {
    const l = productionLayers({ view: 'annee', variant: 'normal', battery: true }, FULL);
    expect(l.battery).toBe(false);
    expect(l.monthly).toBe(true);
    expect(onlyOne(l)).toBe(1);
  });

  it('masque le sélecteur de vue quand une seule vue existe', () => {
    const l = productionLayers(
      { view: 'journee', variant: 'normal', battery: false },
      { monthly: false, daily: true, variants: ['normal'], battery: false },
    );
    expect(l.showViewTabs).toBe(false);
    expect(l.showVariantTabs).toBe(false);
  });
});

describe('PV80 — graphique fusionné : transitions', () => {
  it('bascule de vue et retour', () => {
    const s0 = initialProductionState(FULL);
    const s1 = setProductionView(s0, 'journee', FULL);
    expect(s1.view).toBe('journee');
    expect(setProductionView(s1, 'annee', FULL).view).toBe('annee');
  });

  it('ignore une vue non rendue', () => {
    const avail = { monthly: false, daily: true, variants: ['normal' as const], battery: false };
    const s = initialProductionState(avail);
    expect(setProductionView(s, 'annee', avail)).toEqual(s);
  });

  it('les onglets Standard/Été/Ramadan changent la silhouette rendue', () => {
    let s = setProductionView(initialProductionState(FULL), 'journee', FULL);
    s = setCurveVariant(s, 'ete', FULL);
    expect(productionLayers(s, FULL).variant).toBe('ete');
    s = setCurveVariant(s, 'ramadan', FULL);
    expect(productionLayers(s, FULL).variant).toBe('ramadan');
  });

  it('ignore une variante non pré-rendue (industriel/agricole : profil unique)', () => {
    const avail = { monthly: true, daily: true, variants: ['normal' as const], battery: false };
    const s = setProductionView(initialProductionState(avail), 'journee', avail);
    expect(setCurveVariant(s, 'ete', avail)).toEqual(s);
    expect(productionLayers(s, avail).showVariantTabs).toBe(false);
  });

  it('cocher « Avec batterie » depuis l’année amène sur la vue journée', () => {
    const s = setBatteryLayer(initialProductionState(FULL), true, FULL);
    expect(s.view).toBe('journee');
    expect(s.battery).toBe(true);
    expect(productionLayers(s, FULL).battery).toBe(true);
  });

  it('décocher rend la courbe nue', () => {
    let s = setBatteryLayer(initialProductionState(FULL), true, FULL);
    s = setBatteryLayer(s, false, FULL);
    expect(s.battery).toBe(false);
    expect(productionLayers(s, FULL).daily).toBe(true);
  });

  it('la coche est mémorisée quand on repasse par l’année', () => {
    let s = setBatteryLayer(initialProductionState(FULL), true, FULL);
    s = setProductionView(s, 'annee', FULL);
    expect(s.battery).toBe(true);
    expect(productionLayers(s, FULL).battery).toBe(false);
    s = setProductionView(s, 'journee', FULL);
    expect(productionLayers(s, FULL).battery).toBe(true);
  });

  it('sans calque batterie rendu, la coche reste toujours fausse', () => {
    const avail = { monthly: true, daily: true, variants: ['normal' as const], battery: false };
    const s = setBatteryLayer(initialProductionState(avail), true, avail);
    expect(s.battery).toBe(false);
  });

  it('une variante devenue indisponible retombe sur la première rendue', () => {
    const avail = { monthly: true, daily: true, variants: ['normal' as const], battery: false };
    expect(productionLayers({ view: 'journee', variant: 'ramadan', battery: false }, avail).variant).toBe('normal');
  });
});

describe('PV80 — chapitre « Votre installation » : équipement structuré', () => {
  const ITEMS = [
    { designation: 'Panneau solaire 550 W', quantite: 12, marque: 'Longi' },
    { designation: 'Onduleur hybride 6 kW', quantite: 1, marque: 'Deye' },
    { designation: 'Batterie lithium LFP 5 kWh', quantite: 2, marque: 'Deyness' },
    { designation: 'Coffret de protection DC', quantite: 1 },
    { designation: 'Structure aluminium toiture', quantite: 1 },
    { designation: 'Câble solaire 6 mm²', quantite: 60 },
    { designation: 'Frais de dossier ONEE', quantite: 1 },
  ];

  it('classe chaque poste dans sa famille', () => {
    expect(classifyEquipment('Panneau solaire 550 W')).toBe('production');
    expect(classifyEquipment('Onduleur hybride 6 kW')).toBe('production');
    expect(classifyEquipment('Batterie lithium LFP 5 kWh')).toBe('stockage');
    expect(classifyEquipment('Coffret de protection DC')).toBe('protection');
    expect(classifyEquipment('Structure aluminium toiture')).toBe('structure');
    expect(classifyEquipment('Frais de dossier ONEE')).toBe('autres');
  });

  it('le poste le plus SPÉCIFIQUE gagne (un câble batterie reste du stockage)', () => {
    expect(classifyEquipment('Câble batterie 25 mm²')).toBe('stockage');
    expect(classifyEquipment('Coffret DC onduleur')).toBe('protection');
  });

  it('regroupe dans l’ordre canonique, groupes vides omis', () => {
    const groups = groupEquipment(ITEMS);
    expect(groups.map((g) => g.id)).toEqual(['production', 'stockage', 'protection', 'structure', 'autres']);
    expect(groups[0].lines.map((l) => l.quantite)).toEqual([12, 1]);
    expect(groups[1].lines[0].designation).toContain('Batterie');
    expect(equipmentLineCount(ITEMS)).toBe(7);
  });

  it('ne perd JAMAIS une ligne du devis (libellé inconnu → « autres »)', () => {
    const exotic = [{ designation: 'Prestation XYZ non catalogée', quantite: 1 }];
    const groups = groupEquipment(exotic);
    expect(groups).toHaveLength(1);
    expect(groups[0].id).toBe('autres');
    expect(equipmentLineCount(exotic)).toBe(1);
  });

  it('ignore les lignes vides ou à quantité nulle/invalide', () => {
    expect(equipmentLineCount([
      { designation: '  ', quantite: 3 },
      { designation: 'Panneau', quantite: 0 },
      { designation: 'Panneau', quantite: Number.NaN },
    ])).toBe(0);
    expect(groupEquipment(null)).toEqual([]);
    expect(groupEquipment(undefined)).toEqual([]);
  });

  it('le delta dit ce que la seconde option AJOUTE (jamais un second tableau)', () => {
    const sans = [
      { designation: 'Panneau solaire 550 W', quantite: 12 },
      { designation: 'Onduleur hybride 6 kW', quantite: 1 },
    ];
    const avec = [
      { designation: 'Panneau solaire 550 W', quantite: 12 },
      { designation: 'Onduleur hybride 6 kW', quantite: 1 },
      { designation: 'Batterie lithium LFP 5 kWh', quantite: 2 },
    ];
    expect(equipmentDelta(sans, avec)).toEqual([
      { designation: 'Batterie lithium LFP 5 kWh', quantite: 2 },
    ]);
    expect(equipmentDelta(avec, sans)).toEqual([]);
  });

  it('un delta de QUANTITÉ ne compte que la différence', () => {
    const d = equipmentDelta(
      [{ designation: 'Panneau', quantite: 10 }],
      [{ designation: 'panneau', quantite: 14 }],
    );
    expect(d).toEqual([{ designation: 'panneau', quantite: 4 }]);
  });
});

describe('PV80 — token depuis la route catch-all (le token est le DERNIER segment)', () => {
  it('cas 1 — /proposition/<token>', () => {
    expect(tokenFromSegments('a1b2c3')).toBe('a1b2c3');
    expect(decorativeSlug('a1b2c3')).toBe('');
  });

  it('cas 2 — /proposition/<slug>/<token> : le slug est purement décoratif', () => {
    expect(tokenFromSegments('ahmed-benali/a1b2c3')).toBe('a1b2c3');
    expect(decorativeSlug('ahmed-benali/a1b2c3')).toBe('ahmed-benali');
    // Astro peut fournir les segments déjà découpés.
    expect(tokenFromSegments(['ahmed-benali', 'a1b2c3'])).toBe('a1b2c3');
  });

  it('cas 3 — chemin vide / absent → aucun token (la page 404)', () => {
    expect(tokenFromSegments('')).toBe('');
    expect(tokenFromSegments('   ')).toBe('');
    expect(tokenFromSegments(undefined)).toBe('');
    expect(tokenFromSegments(null)).toBe('');
    expect(tokenFromSegments('/')).toBe('');
  });

  it('tolère les slashs superflus sans jamais changer le token', () => {
    expect(tokenFromSegments('/villa-anfa//a1b2c3/')).toBe('a1b2c3');
    expect(proposalPathSegments('/villa-anfa//a1b2c3/')).toEqual(['villa-anfa', 'a1b2c3']);
    expect(decorativeSlug('societe/agence-nord/a1b2c3')).toBe('societe/agence-nord');
  });
});
