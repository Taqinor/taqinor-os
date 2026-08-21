// CJ1 — « Sur une journée » devient RÉEL.
//
// Le graphe journalier de /proposition dessinait une cloche synthétique et
// libellait son sommet en « kWh » alors que c'est une PUISSANCE. Le backend sert
// désormais un bloc additif `courbes_journalieres` (forme PVGIS par saison,
// kWh/jour et kW de pointe du devis, kWh/jour réel de consommation). Ces tests
// prouvent les six invariants de la reprise :
//   (1) la saison de départ est celle de la DATE, avec les MÊMES bornes que le
//       serveur (hiver DJF / été JJA / mi-saison le reste) — dates injectées,
//       jamais l'horloge de la machine de test ;
//   (2) la silhouette de consommation somme EXACTEMENT au kWh/jour servi —
//       c'est ce qui rend « ajusté à votre facture » vrai ;
//   (3) AUCUN libellé de pic ne porte jamais « kWh », dans les 3 langues, sur le
//       chemin servi comme sur le repli ;
//   (4) l'occupation par défaut vient du drapeau serveur ;
//   (5) la fenêtre de Ramadan est CALCULÉE (plage grégorienne + coucher NOAA),
//       plus jamais codée en dur ;
//   (6) les options de batterie servies commandent le calque, et un bloc absent
//       laisse le rendu STRICTEMENT identique à celui d'avant.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  DEFAULT_LAT,
  DEFAULT_LON,
  FAJR_BEFORE_SUNRISE_MIN,
  OCCUPANCY_IDS,
  OCCUPANCY_LABELS,
  OCCUPANCY_SHAPES,
  RAMADAN_RANGES,
  RAMADAN_TZ_OFFSET_HOURS,
  SEASON_IDS,
  formatHourLabel,
  occupancyFromFlag,
  parseDailyCurves,
  ramadanRangeFor,
  ramadanWindow,
  seasonForDate,
  servedSeasons,
  sunTimes,
} from '../src/lib/dayProfiles';
import { consumptionKwhShape, renderYearCurve } from '../src/lib/proposalCurve';
import {
  initialProductionState,
  productionLayers,
  setBatteryLayer,
  setOccupancy,
  setSeason,
  type ProductionAvailability,
} from '../src/lib/propositionPage';

const PAGE = readFileSync(
  fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
  'utf-8',
);

// ── Charge utile de référence : la FORME est une cloche normalisée à somme 1
// (exactement la convention serveur `production[saison].forme`), les NIVEAUX
// sont des nombres arbitraires mais cohérents entre eux.
const RAW_BELL = Array.from({ length: 24 }, (_, h) =>
  h >= 6 && h <= 19 ? Math.sin((Math.PI * (h - 6)) / 14) ** 2 : 0,
);
const BELL_SUM = RAW_BELL.reduce((a, b) => a + b, 0);
const FORME = RAW_BELL.map((v) => v / BELL_SUM);
const PROD_KWH_JOUR = 48.2;
const PIC_KW = Math.round(PROD_KWH_JOUR * Math.max(...FORME) * 100) / 100;
const CONS_KWH_JOUR = 22.5;

const PAYLOAD = {
  note_horaire:
    "Heures en heure civile marocaine (UTC+1). Pendant le Ramadan, le Maroc repasse à UTC+0 : la courbe se décale alors d'une heure plus tôt.",
  unites: { forme: 'part du total du jour (somme = 1)', kwh_jour: 'kWh/jour', pic_kw: 'kW', batterie_kwh: 'kWh' },
  occupation: 'presence_jour',
  occupation_source: 'defaut_residentiel_fondateur',
  production: {
    ete: { forme: FORME, kwh_jour: PROD_KWH_JOUR, pic_kw: PIC_KW, source: 'pvgis_live' },
    hiver: { forme: FORME, kwh_jour: 24.1, pic_kw: 3.1, source: 'ville_reference' },
  },
  consommation: { ete: { kwh_jour: CONS_KWH_JOUR }, hiver: { kwh_jour: 14.2 } },
  options: ['sans', 'avec'],
  batterie_kwh: 10,
};

/** Extrait le repère d'échelle du SVG (attribut tap-to-reveal + les 2 textes). */
function scaleLabels(svg: string): { attr: string; peakText: string; avgText: string } {
  const group = svg.match(/<g data-curve-scale[\s\S]*?<\/g>/)?.[0] ?? '';
  const attr = group.match(/data-peak="([^"]*)"/)?.[1] ?? '';
  const texts = [...group.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map((m) => m[1]);
  return { attr, peakText: texts[0] ?? '', avgText: texts[1] ?? '' };
}

// ════════════════════════════════════════════════════════════════════════════
describe('CJ1 — saison par DATE, mêmes bornes que le serveur (MOIS_PAR_SAISON)', () => {
  it('DJF → hiver, JJA → été, tout le reste → mi-saison', () => {
    // Dates INJECTÉES : aucun test ne dépend de l'horloge de la machine.
    expect(seasonForDate(new Date('2026-12-15T12:00:00Z'))).toBe('hiver');
    expect(seasonForDate(new Date('2026-01-15T12:00:00Z'))).toBe('hiver');
    expect(seasonForDate(new Date('2026-02-28T12:00:00Z'))).toBe('hiver');
    expect(seasonForDate(new Date('2026-06-01T12:00:00Z'))).toBe('ete');
    expect(seasonForDate(new Date('2026-07-21T12:00:00Z'))).toBe('ete');
    expect(seasonForDate(new Date('2026-08-31T12:00:00Z'))).toBe('ete');
    for (const iso of ['2026-03-10', '2026-04-10', '2026-05-10', '2026-09-10', '2026-10-10', '2026-11-10']) {
      expect(seasonForDate(new Date(`${iso}T12:00:00Z`))).toBe('mi_saison');
    }
  });

  it('les 12 mois sont couverts, une seule saison chacun', () => {
    const seen = new Set<string>();
    for (let m = 1; m <= 12; m++) {
      const s = seasonForDate(new Date(Date.UTC(2026, m - 1, 15)));
      expect(SEASON_IDS).toContain(s);
      seen.add(`${m}:${s}`);
    }
    expect(seen.size).toBe(12);
  });

  it('date invalide → mi-saison (repli neutre, jamais un throw)', () => {
    expect(seasonForDate(new Date('pas-une-date'))).toBe('mi_saison');
  });

  it('la saison de départ de l’état vient de la disponibilité SÉRIALISÉE, pas de l’horloge', () => {
    const avail: ProductionAvailability = {
      monthly: false,
      daily: true,
      variants: ['normal'],
      battery: false,
      seasons: ['hiver', 'ete'],
      defaultSeason: 'hiver',
    };
    expect(initialProductionState(avail).season).toBe('hiver');
    // Une saison NON servie est refusée : on ne bascule jamais sur du vide.
    const s = initialProductionState(avail);
    expect(setSeason(s, 'mi_saison', avail)).toEqual(s);
    expect(setSeason(s, 'ete', avail).season).toBe('ete');
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('CJ1 — la silhouette est MISE À L’ÉCHELLE du kWh/jour réel', () => {
  it('l’intégrale journalière vaut EXACTEMENT le kwh_jour servi', () => {
    for (const occupancy of OCCUPANCY_IDS) {
      for (const variant of ['normal', 'ete', 'ramadan'] as const) {
        const hours = consumptionKwhShape(CONS_KWH_JOUR, { mode: 'residentiel', variant, occupancy });
        expect(hours).toHaveLength(24);
        expect(hours.reduce((a, b) => a + b, 0)).toBeCloseTo(CONS_KWH_JOUR, 9);
      }
    }
  });

  it('le mode non résidentiel est mis à l’échelle de la même façon', () => {
    for (const mode of ['industriel', 'commercial', 'agricole'] as const) {
      const hours = consumptionKwhShape(31.7, { mode });
      expect(hours.reduce((a, b) => a + b, 0)).toBeCloseTo(31.7, 9);
    }
  });

  it('kWh/jour absent ou ≤ 0 → 24 zéros (aucun niveau inventé)', () => {
    expect(consumptionKwhShape(0)).toEqual(new Array(24).fill(0));
    expect(consumptionKwhShape(-4)).toEqual(new Array(24).fill(0));
    expect(consumptionKwhShape(Number.NaN)).toEqual(new Array(24).fill(0));
  });

  it('avec production ET consommation servies, les deux courbes partagent un axe RÉEL', () => {
    const curves = parseDailyCurves(PAYLOAD)!;
    const out = renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel' }, {
      production: curves.production.ete ?? null,
      consumptionKwhJour: curves.consommation.ete?.kwhJour ?? null,
      season: 'ete',
    });
    expect(out.hasServedShape).toBe(true);
    expect(out.hasRealConsScale).toBe(true);
    expect(out.hasRealScale).toBe(true);
  });

  it('production servie SANS niveau de consommation → aucune échelle réelle inventée pour la conso', () => {
    const curves = parseDailyCurves({ ...PAYLOAD, consommation: {} })!;
    const out = renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel' }, {
      production: curves.production.ete ?? null,
      consumptionKwhJour: null,
      season: 'ete',
    });
    expect(out.hasServedShape).toBe(true);
    expect(out.hasRealConsScale).toBe(false);
  });

  it('consommation servie SANS forme de production → pas d’axe réel du tout (un vrai chiffre sur un axe illustratif serait pire)', () => {
    const out = renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel' }, {
      production: null,
      consumptionKwhJour: CONS_KWH_JOUR,
      season: 'ete',
    });
    expect(out.hasServedShape).toBe(false);
    expect(out.hasRealConsScale).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('CJ1 — un PIC est une PUISSANCE : jamais « kWh » sur ce libellé', () => {
  const served = () => {
    const curves = parseDailyCurves(PAYLOAD)!;
    return {
      production: curves.production.ete ?? null,
      consumptionKwhJour: curves.consommation.ete?.kwhJour ?? null,
      season: 'ete' as const,
    };
  };

  it('chemin SERVI — les 3 langues portent kW et jamais kWh sur le pic', () => {
    for (const lang of ['fr', 'en', 'ar'] as const) {
      const { attr, peakText } = scaleLabels(
        renderYearCurve(9000, undefined, lang, { mode: 'residentiel' }, served()).svg,
      );
      expect(peakText).toContain('kW');
      expect(peakText).not.toContain('kWh');
      expect(attr).toContain('kW');
      expect(attr).not.toContain('kWh');
    }
  });

  it('chemin de REPLI (aucun bloc servi) — même règle, l’ancien « pic ≈ … kWh » est mort', () => {
    for (const lang of ['fr', 'en', 'ar'] as const) {
      const { attr, peakText } = scaleLabels(renderYearCurve(11000, undefined, lang).svg);
      expect(peakText).toContain('kW');
      expect(peakText).not.toContain('kWh');
      expect(attr).not.toContain('kWh');
    }
  });

  it('le pic affiché est EXACTEMENT le pic_kw servi (jamais recalculé sur la page)', () => {
    const { peakText } = scaleLabels(
      renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel' }, served()).svg,
    );
    const expected = (Math.round(PIC_KW * 10) / 10).toString().replace('.', ',');
    expect(peakText).toContain(expected);
    expect(peakText).toContain('kW');
  });

  it('la seconde ligne dit l’énergie du JOUR de la saison affichée (kWh, avec l’incise)', () => {
    const { avgText } = scaleLabels(
      renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel' }, served()).svg,
    );
    expect(avgText).toContain('kWh/jour');
    expect(avgText).toContain('(été)');
    expect(avgText).toContain('48,2');
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('CJ1 — occupation : trois silhouettes, défaut donné par le serveur', () => {
  it('le drapeau servi devient l’occupation de départ', () => {
    expect(parseDailyCurves(PAYLOAD)!.occupation).toBe('presence_jour');
    expect(parseDailyCurves({ ...PAYLOAD, occupation: 'absence_jour' })!.occupation).toBe('absence_jour');
  });

  // L4 (extension fondateur, 21/08/2026) — crm.Lead.occupation_jour='partiel'
  // fait désormais du serveur la SOURCE de la 3e silhouette (avant : un choix
  // VISITEUR uniquement) ; le contrat servi (source `lead_occupation_jour:*`)
  // suit exactement le même chemin que les deux drapeaux historiques.
  it('« presence_partielle » servie par le serveur (occupation_jour du lead) est lue comme les deux autres', () => {
    const curves = parseDailyCurves({
      ...PAYLOAD, occupation: 'presence_partielle',
      occupation_source: 'lead_occupation_jour:partiel',
    })!;
    expect(curves.occupation).toBe('presence_partielle');
    expect(curves.occupationSource).toBe('lead_occupation_jour:partiel');
  });

  it('drapeau absent/inconnu → « présence partielle », le milieu honnête des trois', () => {
    expect(parseDailyCurves({ ...PAYLOAD, occupation: undefined })!.occupation).toBeNull();
    expect(occupancyFromFlag(null)).toBe('presence_partielle');
    expect(occupancyFromFlag('n’importe quoi')).toBe('presence_partielle');
    expect(occupancyFromFlag('presence_jour')).toBe('presence_jour');
    expect(occupancyFromFlag('absence_jour')).toBe('absence_jour');
  });

  it('l’état de départ retient l’occupation servie, et refuse une valeur non proposée', () => {
    const avail: ProductionAvailability = {
      monthly: false,
      daily: true,
      variants: ['normal'],
      battery: false,
      occupancies: OCCUPANCY_IDS,
      defaultOccupancy: 'absence_jour',
    };
    const s = initialProductionState(avail);
    expect(s.occupancy).toBe('absence_jour');
    expect(setOccupancy(s, 'presence_jour', avail).occupancy).toBe('presence_jour');
    const solo: ProductionAvailability = { ...avail, occupancies: ['presence_jour'] };
    const s2 = initialProductionState(solo);
    expect(setOccupancy(s2, 'absence_jour', solo)).toEqual(s2);
  });

  it('les puces n’apparaissent qu’en vue journée ET s’il y a un choix réel', () => {
    const avail: ProductionAvailability = {
      monthly: true,
      daily: true,
      variants: ['normal'],
      battery: false,
      occupancies: OCCUPANCY_IDS,
      defaultOccupancy: 'presence_jour',
      seasons: ['hiver', 'ete'],
      defaultSeason: 'ete',
    };
    const jour = productionLayers({ ...initialProductionState(avail), view: 'journee' }, avail);
    expect(jour.showOccupancyTabs).toBe(true);
    expect(jour.showSeasonTabs).toBe(true);
    const annee = productionLayers({ ...initialProductionState(avail), view: 'annee' }, avail);
    expect(annee.showOccupancyTabs).toBe(false);
    expect(annee.showSeasonTabs).toBe(false);
    const solo: ProductionAvailability = { ...avail, occupancies: ['presence_jour'], seasons: ['ete'] };
    const l = productionLayers({ ...initialProductionState(solo), view: 'journee' }, solo);
    expect(l.showOccupancyTabs).toBe(false);
    expect(l.showSeasonTabs).toBe(false);
  });

  it('changer d’occupation change RÉELLEMENT le tracé de consommation', () => {
    const consPath = (svg: string) => svg.match(/class="curve-cons-line" d="([^"]+)"/)?.[1];
    const a = renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel', occupancy: 'presence_jour' });
    const b = renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel', occupancy: 'absence_jour' });
    const c = renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel', occupancy: 'presence_partielle' });
    expect(consPath(a.svg)).not.toBe(consPath(b.svg));
    expect(consPath(b.svg)).not.toBe(consPath(c.svg));
    expect(consPath(a.svg)).not.toBe(consPath(c.svg));
  });

  it('les trois silhouettes portent 24 poids strictement positifs (aucune heure trouée)', () => {
    for (const id of OCCUPANCY_IDS) {
      const shape = OCCUPANCY_SHAPES[id];
      expect(shape, id).toHaveLength(24);
      for (const w of shape) expect(w).toBeGreaterThan(0);
    }
  });

  it('la page rend bien les TROIS puces d’occupation + les puces de saison', () => {
    expect(PAGE).toContain('data-curve-occupancy-btn');
    expect(PAGE).toContain('data-prod-occupancy-control');
    expect(PAGE).toContain('data-curve-season-btn');
    expect(PAGE).toContain('data-prod-season-control');
    // Les libellés viennent de la SOURCE UNIQUE (dayProfiles), jamais recopiés.
    expect(PAGE).toContain('OCCUPANCY_LABELS[occ].fr');
    expect(PAGE).toContain('SEASON_LABELS[season].fr');
    // Les trois silhouettes sont bien proposées (OCCUPANCY_IDS en résidentiel).
    expect(PAGE).toContain("curveMode === 'residentiel' ? OCCUPANCY_IDS : []");
    expect(OCCUPANCY_IDS).toHaveLength(3);
    for (const id of OCCUPANCY_IDS) {
      expect(OCCUPANCY_LABELS[id].fr).toBeTruthy();
      expect(OCCUPANCY_LABELS[id].en).toBeTruthy();
      expect(OCCUPANCY_LABELS[id].ar).toBeTruthy();
    }
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('CJ1 — Ramadan : la fenêtre est CALCULÉE, plus jamais codée en dur', () => {
  it('la table couvre 2025 → 2033 et reste triée, bornes cohérentes', () => {
    expect(RAMADAN_RANGES.length).toBeGreaterThanOrEqual(10);
    let previousEnd = '';
    for (const r of RAMADAN_RANGES) {
      expect(r.start < r.end).toBe(true);
      expect(previousEnd < r.start).toBe(true);
      previousEnd = r.end;
    }
    // Ramadan 1447 — la plage 2026 épinglée (estimation aladhan.com, ±1 jour :
    // le Maroc confirme le 1er jour par observation lunaire).
    const r2026 = RAMADAN_RANGES.find((r) => r.hijri === 1447)!;
    expect(r2026.start).toBe('2026-02-18');
    expect(r2026.end).toBe('2026-03-19');
  });

  it('une date DANS le Ramadan retient sa propre plage ; une date hors Ramadan vise le SUIVANT', () => {
    const inside = ramadanRangeFor(new Date('2026-03-06T12:00:00Z'))!;
    expect(inside.inRamadan).toBe(true);
    expect(inside.range.hijri).toBe(1447);
    const outside = ramadanRangeFor(new Date('2026-08-21T12:00:00Z'))!;
    expect(outside.inRamadan).toBe(false);
    expect(outside.range.hijri).toBe(1448);
    // Au-delà de la table, on n'affirme rien.
    expect(ramadanRangeFor(new Date('2040-01-01T12:00:00Z'))).toBeNull();
    expect(ramadanWindow(new Date('2040-01-01T12:00:00Z'))).toBeNull();
  });

  // SANITY DE LA FORMULE NOAA. Casablanca (33,57 N / 7,59 O) est à UTC+1 le
  // reste de l'année mais repasse à UTC+0 PENDANT LE RAMADAN (note horaire du
  // backend `courbes_journalieres.NOTE_HORAIRE` ; « Time in Morocco »,
  // en.wikipedia.org) : l'iftar que le client connaît est donc une heure UTC+0.
  // Le coucher réel début mars y est d'environ 18h30-18h40 — on tolère ±15 min,
  // largement au-delà de l'erreur de l'algorithme (< 2 min).
  it('iftar Casablanca mi-Ramadan 2026 ≈ 18h39 à ±15 min (coucher NOAA, heure de Ramadan UTC+0)', () => {
    const win = ramadanWindow(new Date('2026-03-06T12:00:00Z'), DEFAULT_LAT, DEFAULT_LON)!;
    expect(win.inRamadan).toBe(true);
    expect(win.hijri).toBe(1447);
    expect(Math.abs(win.iftarHour - (18 + 39 / 60))).toBeLessThan(0.25);
    expect(RAMADAN_TZ_OFFSET_HOURS).toBe(0);
  });

  it('l’imsak est le lever MOINS 80 min (approximation du fajr, assumée et testée)', () => {
    const day = new Date('2026-03-06T12:00:00Z');
    const sun = sunTimes(day, DEFAULT_LAT, DEFAULT_LON, RAMADAN_TZ_OFFSET_HOURS)!;
    const win = ramadanWindow(day, DEFAULT_LAT, DEFAULT_LON)!;
    expect(win.imsakHour).toBeCloseTo((sun.sunriseMin - FAJR_BEFORE_SUNRISE_MIN) / 60, 9);
    expect(win.iftarHour).toBeCloseTo(sun.sunsetMin / 60, 9);
    // Le lever encadre bien le coucher (aucune inversion de signe de longitude).
    expect(sun.sunriseMin).toBeLessThan(sun.sunsetMin);
  });

  it('le coucher se DÉPLACE avec la date et avec la longitude (ce n’est pas une constante)', () => {
    const casaMars = sunTimes(new Date('2026-03-06T12:00:00Z'), DEFAULT_LAT, DEFAULT_LON, 0)!;
    const casaJuin = sunTimes(new Date('2026-06-21T12:00:00Z'), DEFAULT_LAT, DEFAULT_LON, 0)!;
    expect(casaJuin.sunsetMin).toBeGreaterThan(casaMars.sunsetMin + 45);
    // Oujda (1,9 O) est à ~5,7° à l'est de Casablanca : le soleil s'y couche
    // ~23 min PLUS TÔT en temps universel (4 min par degré).
    const oujdaMars = sunTimes(new Date('2026-03-06T12:00:00Z'), 34.68, -1.9, 0)!;
    expect(oujdaMars.sunsetMin).toBeLessThan(casaMars.sunsetMin);
    expect(casaMars.sunsetMin - oujdaMars.sunsetMin).toBeGreaterThan(15);
  });

  it('la puce annonce l’heure calculée (format 24 h, séparateur par langue)', () => {
    const win = ramadanWindow(new Date('2026-03-06T12:00:00Z'), DEFAULT_LAT, DEFAULT_LON)!;
    expect(formatHourLabel(win.iftarHour, 'fr')).toMatch(/^\d{1,2}h\d{2}$/);
    expect(formatHourLabel(win.iftarHour, 'en')).toMatch(/^\d{1,2}:\d{2}$/);
    expect(formatHourLabel(18.65, 'fr')).toBe('18h39');
    // …et la page l'affiche vraiment sur la puce Ramadan.
    expect(PAGE).toContain('iftar ≈ ${ramadanIftarFr}');
    expect(PAGE).toContain('ramadanWindow(');
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('CJ1 — les options servies commandent le calque batterie', () => {
  const base: ProductionAvailability = { monthly: true, daily: true, variants: ['normal'], battery: true };

  it("['sans','avec'] → la case à cocher historique, décochée au départ", () => {
    const avail: ProductionAvailability = { ...base, batteryOptions: ['sans', 'avec'] };
    const s = initialProductionState(avail);
    expect(s.battery).toBe(false);
    const l = productionLayers({ ...s, view: 'journee' }, avail);
    expect(l.showBatteryToggle).toBe(true);
    expect(l.batteryLocked).toBe(false);
  });

  it("['avec'] → le calque est OFFERT et ÉTIQUETÉ, sans case à décocher", () => {
    const avail: ProductionAvailability = { ...base, batteryOptions: ['avec'] };
    const s = initialProductionState(avail);
    expect(s.battery).toBe(true);
    const l = productionLayers(s, avail);
    expect(l.battery).toBe(true);
    expect(l.batteryLocked).toBe(true);
    // Décocher n'a aucun sens : il n'existe pas d'option sans stockage.
    expect(setBatteryLayer(s, false, avail).battery).toBe(true);
  });

  it("['sans'] → AUCUN calque batterie, aucune commande", () => {
    const avail: ProductionAvailability = { ...base, batteryOptions: ['sans'] };
    const s = initialProductionState(avail);
    expect(s.battery).toBe(false);
    const l = productionLayers({ ...s, view: 'journee', battery: true }, avail);
    expect(l.battery).toBe(false);
    expect(l.showBatteryToggle).toBe(false);
    expect(l.batteryLocked).toBe(false);
    // Le calque nu reprend la place : un seul dessin, toujours.
    expect(l.daily).toBe(true);
  });

  it('clé `options` absente → comportement historique STRICTEMENT inchangé', () => {
    const s = initialProductionState(base);
    expect(s.battery).toBe(false);
    const l = productionLayers({ ...s, view: 'journee' }, base);
    expect(l.showBatteryToggle).toBe(true);
    expect(l.batteryLocked).toBe(false);
    expect(setBatteryLayer(s, true, base).battery).toBe(true);
    expect(setBatteryLayer(setBatteryLayer(s, true, base), false, base).battery).toBe(false);
  });

  it('la page fait suivre les options jusqu’au simulateur (pas seulement à la case)', () => {
    expect(PAGE).toContain('batteryOptionsServed');
    expect(PAGE).toContain("batteryOptionsServed.includes('avec')");
    expect(PAGE).toContain('prodLayers.batteryLocked');
  });

  it('la capacité du simulateur retombe sur le kWh SERVI, plus sur la valeur catalogue', () => {
    expect(PAGE).toContain('servedBatteryTotalKwh');
    expect(PAGE).toContain('offerBattery.capacityKwhPerUnit ?? servedUnitCapacityKwh ?? DEFAULT_UNIT_CAPACITY_KWH');
    expect(parseDailyCurves(PAYLOAD)!.batterieKwh).toBe(10);
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('CJ1 — lecture DÉFENSIVE du bloc backend (chaque morceau peut manquer)', () => {
  it('clé absente / type inattendu → null, jamais un throw', () => {
    expect(parseDailyCurves(undefined)).toBeNull();
    expect(parseDailyCurves(null)).toBeNull();
    expect(parseDailyCurves('bloc')).toBeNull();
    expect(parseDailyCurves(42)).toBeNull();
    expect(parseDailyCurves([1, 2, 3])).toBeNull();
  });

  it('bloc minimal (aucune saison servie) → objet vide, aucune puce', () => {
    const curves = parseDailyCurves({ note_horaire: 'x', occupation: 'absence_jour' })!;
    expect(curves.production).toEqual({});
    expect(curves.consommation).toEqual({});
    expect(curves.options).toEqual([]);
    expect(curves.batterieKwh).toBeNull();
    expect(servedSeasons(curves)).toEqual([]);
    expect(servedSeasons(null)).toEqual([]);
  });

  it('une saison ILLISIBLE est écartée sans emporter les autres', () => {
    const curves = parseDailyCurves({
      ...PAYLOAD,
      production: {
        ete: PAYLOAD.production.ete,
        hiver: { forme: [1, 2, 3], kwh_jour: 10, pic_kw: 2 }, // forme trop courte
        mi_saison: { forme: FORME, kwh_jour: 0, pic_kw: 2 }, // niveau nul
      },
    })!;
    expect(Object.keys(curves.production)).toEqual(['ete']);
  });

  it('une forme entièrement nulle est écartée (une ligne plate n’est pas une production)', () => {
    const curves = parseDailyCurves({
      ...PAYLOAD,
      production: { ete: { forme: new Array(24).fill(0), kwh_jour: 10, pic_kw: 2 } },
    })!;
    expect(curves.production.ete).toBeUndefined();
  });

  it('les options inconnues sont ignorées, l’ordre est canonique', () => {
    expect(parseDailyCurves({ ...PAYLOAD, options: ['avec', 'sans', 'peut-être'] })!.options)
      .toEqual(['sans', 'avec']);
    expect(parseDailyCurves({ ...PAYLOAD, options: 'avec' })!.options).toEqual([]);
  });

  it('servedSeasons ne liste que les saisons RÉELLEMENT servies, dans l’ordre canonique', () => {
    expect(servedSeasons(parseDailyCurves(PAYLOAD))).toEqual(['hiver', 'ete']);
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('CJ1 — bloc ABSENT : le rendu reste celui d’avant, au caractère près', () => {
  it('passer `null`, rien, ou un bloc vide produit STRICTEMENT le même SVG', () => {
    const options = { mode: 'residentiel' as const, variant: 'normal' as const };
    const sansArg = renderYearCurve(10000, undefined, 'fr', options);
    const avecNull = renderYearCurve(10000, undefined, 'fr', options, null);
    const avecVide = renderYearCurve(10000, undefined, 'fr', options, {
      production: null,
      consumptionKwhJour: null,
      season: null,
    });
    expect(avecNull.svg).toBe(sansArg.svg);
    expect(avecVide.svg).toBe(sansArg.svg);
    expect(avecVide.hasRealScale).toBe(sansArg.hasRealScale);
  });

  it('sans production annuelle NI bloc servi → « année type », aucun chiffre fabriqué', () => {
    const out = renderYearCurve(null, undefined, 'fr', {}, null);
    expect(out.hasRealScale).toBe(false);
    expect(out.hasServedShape).toBe(false);
    expect(out.svg).toContain('année type');
    expect(out.svg).not.toMatch(/\d[\d ,.]*kWh/);
    expect(out.svg).not.toMatch(/\d[\d ,.]*kW\b/);
  });

  it('la disponibilité sans les nouvelles clés se comporte comme avant', () => {
    const avail: ProductionAvailability = {
      monthly: true, daily: true, variants: ['normal', 'ete', 'ramadan'], battery: true,
    };
    const l = productionLayers({ ...initialProductionState(avail), view: 'journee' }, avail);
    expect(l.showSeasonTabs).toBe(false);
    expect(l.showOccupancyTabs).toBe(false);
    expect(l.showVariantTabs).toBe(true);
    expect(l.showBatteryToggle).toBe(true);
    expect([l.monthly, l.daily, l.battery].filter(Boolean)).toHaveLength(1);
  });
});
