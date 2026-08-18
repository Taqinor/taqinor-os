// PV80 — Refonte de /proposition/<token> : logique PURE du graphique fusionné
// « Votre production » (vue année ↔ journée, onglets de profil, CALQUE batterie)
// et extraction du token depuis la route catch-all (slug décoratif optionnel).
//
// L'invariant central de la refonte est vérifié ici : le bloc production ne
// montre JAMAIS deux dessins à la fois (c'est exactement ce que la page faisait
// avant — trois graphes empilés du même sujet).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  parseConceptionElectrique,
  conceptionPourLigne,
  chaineLabel,
  protectionLabel,
  cableLabel,
  type ProposalResponse,
} from '../src/lib/proposition';
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

  // PACT-battery (2026-08-15) — fondateur : « quand on active le bouton avec
  // batterie on peut encore voir l'effet le ramadan et l'été ». Le calque
  // batterie REMPLACE la courbe nue (un seul dessin), mais les onglets de
  // profil doivent rester visibles et actifs, et changer d'onglet doit
  // continuer à changer la variante retenue par productionLayers — c'est ce
  // que le script client relit pour recalculer le simulateur batterie.
  it('les onglets Standard/Été/Ramadan restent actifs ET changent la silhouette quand la batterie est cochée', () => {
    let s = setBatteryLayer(initialProductionState(FULL), true, FULL);
    expect(s.battery).toBe(true);
    let l = productionLayers(s, FULL);
    // Un seul dessin : la batterie remplace la courbe, jamais un second graphe.
    expect(l.battery).toBe(true);
    expect(l.daily).toBe(false);
    expect(l.monthly).toBe(false);
    // Les onglets restent proposés ET utilisables pendant que la batterie est active.
    expect(l.showVariantTabs).toBe(true);
    expect(l.variant).toBe('normal');

    s = setCurveVariant(s, 'ete', FULL);
    l = productionLayers(s, FULL);
    expect(l.battery).toBe(true);
    expect(l.variant).toBe('ete');
    expect([l.monthly, l.daily, l.battery].filter(Boolean)).toHaveLength(1);

    s = setCurveVariant(s, 'ramadan', FULL);
    l = productionLayers(s, FULL);
    expect(l.battery).toBe(true);
    expect(l.variant).toBe('ramadan');
    expect([l.monthly, l.daily, l.battery].filter(Boolean)).toHaveLength(1);
  });

  it('changer de variante ne touche jamais à l’état de la case batterie', () => {
    const s0 = setBatteryLayer(initialProductionState(FULL), true, FULL);
    const s1 = setCurveVariant(s0, 'ete', FULL);
    expect(s1.battery).toBe(true);
    expect(s1.view).toBe('journee');
  });
});

describe('PV80 — chapitre « Votre installation » : équipement structuré', () => {
  const ITEMS = [
    { designation: 'Panneau solaire 550 W', quantite: 12, marque: 'Longi' },
    { designation: 'Onduleur hybride 6 kW', quantite: 1, marque: 'Deye' },
    { designation: 'Batterie lithium LFP 5 kWh', quantite: 2, marque: 'Dyness' },
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

// ════════════════════════════════════════════════════════════════════════════
// (fondateur 2026-08-18) « DANS VOTRE INSTALLATION » — le DÉTAIL ÉLECTRIQUE du
// devis, exposé au lien client SANS PRIX.
//
// Le backend (`public_views._conception_electrique_publique`) n'envoie que trois
// listes, sur liste blanche STRICTE : chaînes, protections nominatives, câbles.
// Tout le reste de l'étude (nomenclature d'achat, paramètres de calcul, ratios,
// tensions de chaîne, chute de tension) reste côté vendeur.
//
// Ici on verrouille la moitié WEB : lecture défensive, règle dure « valeur
// absente = OMISE », et aiguillage vers la BONNE ligne d'équipement.
// ════════════════════════════════════════════════════════════════════════════

/** Un bloc backend réaliste (mêmes clés que la whitelist serveur). */
const CONCEPTION = {
  chaines: [
    { pan: 1, mppt: 1, nb_modules: 16 },
    { pan: 2, mppt: 2, nb_modules: 14 },
  ],
  protections: [
    { repere: 'Q1', designation: 'Disjoncteur DC chaîne 1', calibre: '16 A', quantite: 2 },
    { repere: 'F1', designation: 'Parafoudre DC type 2', calibre: '1000 V', quantite: 1 },
    { repere: 'Q10', designation: 'Disjoncteur AC général', calibre: '32 A', quantite: 1 },
  ],
  cables: [
    { liaison: 'Chaîne 1 → coffret DC', longueur_m: 18.5, section_mm2: 6 },
    { liaison: 'Onduleur → tableau AC', longueur_m: 12, section_mm2: 10 },
  ],
};

const AVEC = { conception_electrique: CONCEPTION } as unknown as ProposalResponse;

describe('détail électrique — lecture défensive du bloc backend', () => {
  it('un bloc complet est lu tel quel', () => {
    const c = parseConceptionElectrique(AVEC)!;
    expect(c.chaines).toHaveLength(2);
    expect(c.protections).toHaveLength(3);
    expect(c.cables).toHaveLength(2);
    expect(c.chaines[0]).toEqual({ pan: 1, mppt: 1, nb_modules: 16 });
  });

  it('absent, null ou vide → null (aucun dépliant, la page ne bouge pas d’un pixel)', () => {
    expect(parseConceptionElectrique({} as unknown as ProposalResponse)).toBeNull();
    expect(parseConceptionElectrique(
      { conception_electrique: null } as unknown as ProposalResponse,
    )).toBeNull();
    expect(parseConceptionElectrique(
      { conception_electrique: { chaines: [], protections: [], cables: [] } } as unknown as ProposalResponse,
    )).toBeNull();
  });

  it('type inattendu → null, jamais un throw', () => {
    for (const brut of [42, 'oui', true, []]) {
      expect(parseConceptionElectrique(
        { conception_electrique: brut } as unknown as ProposalResponse,
      )).toBeNull();
    }
  });

  it('RÈGLE DURE — une valeur absente est OMISE, jamais remplacée par 0', () => {
    const c = parseConceptionElectrique({
      conception_electrique: {
        chaines: [{ nb_modules: 12 }],
        protections: [{ designation: 'Sectionneur DC' }],
        cables: [{ liaison: 'Chaîne 2 → coffret DC', section_mm2: 4 }],
      },
    } as unknown as ProposalResponse)!;
    expect(c.chaines[0]).toEqual({ nb_modules: 12 });
    expect('mppt' in c.chaines[0]).toBe(false);
    expect(c.protections[0]).toEqual({ designation: 'Sectionneur DC' });
    expect('quantite' in c.protections[0]).toBe(false);
    expect('longueur_m' in c.cables[0]).toBe(false);
  });

  it('une entrée sans rien de dicible est écartée (pas de ligne fantôme)', () => {
    const c = parseConceptionElectrique({
      conception_electrique: {
        chaines: [{ mppt: 1 }, { nb_modules: 8 }],
        protections: [{ repere: 'Q9' }, { designation: 'Coffret AC' }],
        cables: [{ liaison: 'Sans mesure' }, { section_mm2: 6 }],
      },
    } as unknown as ProposalResponse)!;
    expect(c.chaines).toHaveLength(1);
    expect(c.protections).toHaveLength(1);
    expect(c.cables).toHaveLength(1);
  });
});

describe('détail électrique — chaque ligne d’équipement reçoit SA part', () => {
  const c = parseConceptionElectrique(AVEC);

  it('protection DC → ses organes du côté continu, et eux seuls', () => {
    const bloc = conceptionPourLigne(c, 'protection-dc')!;
    expect(bloc.protections.map((o) => o.repere)).toEqual(['Q1', 'F1']);
    expect(bloc.cables).toHaveLength(0);
    expect(bloc.chaines).toHaveLength(0);
  });

  it('protection AC → ses organes du côté alternatif, et eux seuls', () => {
    const bloc = conceptionPourLigne(c, 'protection-ac')!;
    expect(bloc.protections.map((o) => o.repere)).toEqual(['Q10']);
  });

  it('câblage → les sections et longueurs de liaison', () => {
    const bloc = conceptionPourLigne(c, 'cablage')!;
    expect(bloc.cables).toHaveLength(2);
    expect(bloc.protections).toHaveLength(0);
  });

  it('panneaux et onduleur → le chaînage (modules par MPPT)', () => {
    for (const slug of ['canadian-solar-710', 'jinko-710', 'onduleur-deye-hybride', 'onduleur-huawei-reseau']) {
      expect(conceptionPourLigne(c, slug)!.chaines, slug).toHaveLength(2);
    }
  });

  it('les familles sans détail électrique n’ouvrent AUCUN dépliant', () => {
    for (const slug of [
      'batterie-dyness', 'structure-fixation', 'accessoires-pose',
      'smart-meter-huawei', 'wifi-dongle-huawei', 'poste-mt-raccordement',
    ]) {
      expect(conceptionPourLigne(c, slug), slug).toBeNull();
    }
    expect(conceptionPourLigne(c, null)).toBeNull();
    expect(conceptionPourLigne(null, 'protection-dc')).toBeNull();
  });

  it('famille concernée mais étude muette pour elle → null (jamais un volet vide)', () => {
    const sansCable = parseConceptionElectrique({
      conception_electrique: { chaines: [], protections: CONCEPTION.protections, cables: [] },
    } as unknown as ProposalResponse);
    expect(conceptionPourLigne(sansCable, 'cablage')).toBeNull();
    expect(conceptionPourLigne(sansCable, 'protection-ac')).not.toBeNull();
  });
});

describe('détail électrique — libellés affichés', () => {
  it('la chaîne est le SEUL libellé traduit (un calibre ne se traduit pas)', () => {
    expect(chaineLabel({ nb_modules: 16, mppt: 1, pan: 2 }, 'fr')).toBe('16 modules · MPPT 1 · pan 2');
    expect(chaineLabel({ nb_modules: 16, mppt: 1, pan: 2 }, 'en')).toBe('16 modules · MPPT 1 · roof section 2');
    expect(chaineLabel({ nb_modules: 16, mppt: 1, pan: 2 }, 'ar')).toContain('MPPT 1');
  });

  it('un morceau absent disparaît du libellé (jamais « MPPT — »)', () => {
    expect(chaineLabel({ nb_modules: 12 }, 'fr')).toBe('12 modules');
    expect(protectionLabel({ designation: 'Coffret AC' })).toBe('Coffret AC');
    expect(cableLabel({ section_mm2: 6 })).toBe('6 mm²');
    expect(cableLabel({})).toBe('');
  });

  it('l’organe porte son repère, sa désignation et son calibre — jamais sa quantité', () => {
    const o = { repere: 'Q1', designation: 'Disjoncteur DC chaîne 1', calibre: '16 A', quantite: 2 };
    expect(protectionLabel(o)).toBe('Q1 · Disjoncteur DC chaîne 1 · 16 A');
  });

  it('la liaison porte ce qu’elle relie, sa section et sa longueur (virgule décimale)', () => {
    expect(cableLabel({ liaison: 'Chaîne 1 → coffret DC', section_mm2: 6, longueur_m: 18.5 }))
      .toBe('Chaîne 1 → coffret DC · 6 mm² · 18,5 m');
  });
});

describe('détail électrique — rendu dans le tableau d’équipement', () => {
  const PAGE = readFileSync(
    fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
    'utf-8',
  );

  it('la page lit le bloc backend par la fonction pure, une seule fois', () => {
    expect(PAGE).toContain('parseConceptionElectrique(data!)');
    expect(PAGE).toContain('conceptionPourLigne(conception, ficheSlug)');
  });

  it('le dépliant est STRICTEMENT conditionnel (pas de détail → rien du tout)', () => {
    expect(PAGE).toContain('{it.detail ? (');
    expect(PAGE).toContain('<details class="conception-fold');
  });

  it('le dépliant vit DANS le tableau d’équipement, jamais ailleurs', () => {
    const debut = PAGE.indexOf('id="equipement"');
    const fin = PAGE.indexOf('id="mode-agricole"');
    const idx = PAGE.indexOf('conception-fold');
    expect(debut).toBeGreaterThan(0);
    expect(idx).toBeGreaterThan(debut);
    expect(idx).toBeLessThan(fin);
  });

  it('le libellé du dépliant porte ses trois langues', () => {
    expect(PAGE).toContain('data-fr="Dans votre installation" data-en="In your installation" data-ar="في تركيبكم"');
  });

  it('la quantité d’un organe n’est rendue que si elle existe', () => {
    expect(PAGE).toContain('{o.quantite !== undefined ? (');
  });

  it('AUCUN prix ne s’invite dans le dépliant', () => {
    const debut = PAGE.indexOf('<details class="conception-fold');
    const fin = PAGE.indexOf('</details>', debut);
    const bloc = PAGE.slice(debut, fin);
    expect(debut).toBeGreaterThan(0);
    for (const interdit of ['formatMAD', 'prix_unit', 'prix_achat', 'remise', 'MAD', 'ttc']) {
      expect(bloc, `« ${interdit} » dans le dépliant`).not.toContain(interdit);
    }
  });
});

// ── GAMMES (fondateur 2026-08-18) — bloc de choix de gamme sur la page.
// Garde de SOURCE : le bloc n'existe QUE sous la condition `gammes` (mode
// d'envoi « les_deux »), il porte les deux cartes + le badge « Recommandé » +
// l'écart en MAD, et chaque carte ouvre le lien de SA gamme (un PDF = une
// gamme). En mode « seule », le backend n'envoie pas la clé → rien ne rend.
describe('GAMMES — choix de gamme sur la page proposition', () => {
  const PAGE = readFileSync(
    fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
    'utf-8',
  );

  it('la page lit le bloc par les fonctions PURES, une seule fois', () => {
    expect(PAGE).toContain('proposalGammes(data!)');
    expect(PAGE).toContain('gammeEcartLabel(gammes.soeur.ecart_ttc)');
    expect(PAGE).toContain('gammeComparatif(gammes)');
  });

  it('le bloc est STRICTEMENT conditionnel (mode « seule » → rien du tout)', () => {
    expect(PAGE).toContain('{gammes && (');
    expect(PAGE).toContain('<section id="gammes"');
  });

  it('deux cartes de gamme, badge « Recommandé » et écart en MAD absolus', () => {
    const debut = PAGE.indexOf('<section id="gammes"');
    const fin = PAGE.indexOf('</section>', PAGE.indexOf('data-gamme-comparatif'));
    const bloc = PAGE.slice(debut, fin);
    expect(debut).toBeGreaterThan(0);
    expect(bloc).toContain('data-gamme-carte="courante"');
    expect(bloc).toContain('data-gamme-carte="soeur"');
    expect(bloc).toContain('data-fr="Recommandé" data-en="Recommended" data-ar="موصى به"');
    expect(bloc).toContain('data-gamme-ecart');
    expect(bloc).toContain('gammes.courante.nom');
    expect(bloc).toContain('gammes.soeur.nom');
  });

  it('la carte de la sœur ouvre le lien de SA gamme (un PDF = une gamme)', () => {
    expect(PAGE).toContain('href={gammes.soeur.proposition_path}');
    expect(PAGE).toContain('data-gamme-choisir');
  });

  it('une valeur absente du comparatif est OMISE (jamais un 0 inventé)', () => {
    expect(PAGE).toContain("{typeof r.quantite === 'number' ? formatNumber(r.quantite, 2) : '—'}");
    expect(PAGE).toContain(
      "{typeof r.quantite_soeur === 'number' ? formatNumber(r.quantite_soeur, 2) : '—'}");
  });

  it('un total de gamme absent n’affiche aucun prix', () => {
    expect(PAGE).toContain("{typeof gammes.courante.total_ttc === 'number' && (");
    expect(PAGE).toContain("{typeof gammes.soeur.total_ttc === 'number' && (");
  });

  it('la gamme signée est NOMMÉE dans le bloc signature, avant le stylo', () => {
    const idxGamme = PAGE.indexOf('data-gamme-signature');
    const idxSigner = PAGE.indexOf('id="signer"');
    // L'axe « avec / sans batterie » (choix d'option) vit APRÈS : les deux
    // choix sont distincts et ne se mélangent jamais.
    const idxChoixOption = PAGE.indexOf('data-fr="Votre choix"');
    expect(idxGamme).toBeGreaterThan(idxSigner);
    expect(idxGamme).toBeLessThan(idxChoixOption);
    expect(PAGE).toContain('data-fr="Vous signez la gamme"');
    expect(PAGE).toContain('data-gamme-basculer');
  });

  it('le bloc porte ses trois langues (FR/EN/AR)', () => {
    expect(PAGE).toContain(
      'data-fr="Vos deux gammes" data-en="Your two ranges" data-ar="نطاقاكم"');
    expect(PAGE).toContain(
      'data-fr="Ce qui change entre les deux" data-en="What differs between the two"');
  });

  it('la bande « Autres tailles » reste distincte du bloc gammes', () => {
    const idxGammes = PAGE.indexOf('<section id="gammes"');
    const idxTailles = PAGE.indexOf('data-fr="Autres tailles proposées"');
    expect(idxGammes).toBeGreaterThan(0);
    expect(idxTailles).toBeGreaterThan(idxGammes);
  });
});
