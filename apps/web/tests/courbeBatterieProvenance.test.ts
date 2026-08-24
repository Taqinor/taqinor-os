// ORDRE FONDATEUR (24/08/2026) — trois demandes sur la section « VOTRE
// PRODUCTION » de /proposition, vue « Sur une journée » :
//
//  1. PROVENANCE DU CHIFFRE « 30,2 kWh/jour (été) ». Le repère d'axe affichait
//     « pic ≈ 4 kW / 30,2 kWh/jour (été) » SANS dire de quelle courbe il
//     parlait : posé sur un graphe à deux courbes, le client l'a lu comme SA
//     consommation et l'a jugé incohérent avec sa facture. Les deux chiffres
//     ont toujours été ceux de la PRODUCTION (`courbes_journalieres.
//     production[saison].kwh_jour` / `.pic_kw`, moteur serveur) — ils le DISENT
//     désormais, et le kWh/jour RÉEL de consommation servi pour la même saison
//     a sa propre ligne. Ces tests pincent la provenance : le nombre affiché en
//     « production estimée » est celui de la production SERVIE, jamais celui de
//     la consommation.
//  2. LA COUCHE BATTERIE SUR CE GRAPHE-LÀ (et non un second dessin qui remplace
//     celui que le client regarde).
//  3. Payback par palier + message de charge incomplète, servis par le moteur.
//
// Les tests « Source pin » pincent le câblage RÉEL de [...token].astro (code,
// commentaires retirés — un commentaire ne doit jamais faire passer un test).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { renderYearCurve } from '../src/lib/proposalCurve';
import { storageSweepInfo } from '../src/lib/proposition';
import { initialProductionState, productionLayers } from '../src/lib/propositionPage';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
const PAGE = read('../src/pages/proposition/[...token].astro').replace(/\r\n/g, '\n');
const CODE = PAGE
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');

// Charge utile SERVIE de référence (mêmes conventions que le backend :
// `forme` somme à 1, `pic_kw` = kwh_jour × max(forme)).
const RAW_BELL = Array.from({ length: 24 }, (_, h) =>
  h >= 6 && h <= 19 ? Math.sin((Math.PI * (h - 6)) / 14) ** 2 : 0,
);
const SUM = RAW_BELL.reduce((a, b) => a + b, 0);
const FORME = RAW_BELL.map((v) => v / SUM);
const PROD_KWH_JOUR = 30.2;
const PIC_KW = Math.round(PROD_KWH_JOUR * Math.max(...FORME) * 100) / 100;
const CONS_KWH_JOUR = 21.7;

const served = (extra: Record<string, unknown> = {}) => ({
  production: { forme: FORME, kwhJour: PROD_KWH_JOUR, picKw: PIC_KW },
  consumptionKwhJour: CONS_KWH_JOUR,
  season: 'ete' as const,
  ...extra,
});

/** Les <text> du repère d'échelle, dans l'ordre. */
function scaleTexts(svg: string): string[] {
  const group = svg.match(/<g data-curve-scale[\s\S]*?<\/g>/)?.[0] ?? '';
  return [...group.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map((m) => m[1]);
}

// ════════════════════════════════════════════════════════════════════════════
describe('1. Provenance — le repère NOMME la courbe dont il parle', () => {
  it('le kWh/jour du repère est la PRODUCTION servie, explicitement libellée', () => {
    const texts = scaleTexts(renderYearCurve(11000, undefined, 'fr', {}, served()).svg);
    expect(texts[0]).toContain('pic de production ≈');
    expect(texts[1]).toContain('production estimée :');
    // Le nombre est celui de la PRODUCTION servie (30,2), pas de la conso (21,7).
    expect(texts[1]).toContain('30,2 kWh/jour');
    expect(texts[1]).not.toContain('21,7');
    expect(texts[1]).toContain('(été)');
  });

  it('la CONSOMMATION servie a sa propre ligne, avec son propre chiffre', () => {
    const texts = scaleTexts(renderYearCurve(11000, undefined, 'fr', {}, served()).svg);
    expect(texts[2]).toContain('votre consommation :');
    expect(texts[2]).toContain('21,7 kWh/jour');
  });

  it('sans kWh/jour de consommation servi, AUCUNE ligne de consommation (omission)', () => {
    const out = renderYearCurve(
      11000, undefined, 'fr', {}, served({ consumptionKwhJour: null }),
    );
    expect(out.hasRealConsScale).toBe(false);
    expect(scaleTexts(out.svg)).toHaveLength(2);
    expect(out.svg).not.toContain('votre consommation');
  });

  it('les trois langues nomment la production (jamais un chiffre anonyme)', () => {
    for (const [lang, prod] of [['fr', 'production estimée :'], ['en', 'estimated production:'],
      ['ar', 'الإنتاج المقدّر:']] as const) {
      const texts = scaleTexts(renderYearCurve(11000, undefined, lang, {}, served()).svg);
      expect(texts[1]).toContain(prod);
    }
  });

  it('le repli annuel (aucune saison servie) nomme lui aussi la production', () => {
    const texts = scaleTexts(renderYearCurve(11000).svg);
    expect(texts[0]).toContain('pic de production ≈');
    expect(texts[1]).toContain('production estimée :');
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('2. La couche batterie vit SUR ce graphe', () => {
  const BATT = Array.from({ length: 24 }, (_, h) => (h >= 18 && h <= 22 ? 1.4 : 0));

  it('série horaire servie ⇒ aire batterie dessinée sur la même courbe', () => {
    const out = renderYearCurve(
      11000, undefined, 'fr', {}, served({ batterieHoraireKwh: BATT }),
    );
    expect(out.hasBatteryLayer).toBe(true);
    expect(out.svg).toContain('data-curve-battery');
    // Le graphe reste CELUI-LÀ : les deux courbes d'origine sont toujours là.
    expect(out.svg).toContain('curve-solar-line');
    expect(out.svg).toContain('curve-cons-line');
  });

  it('série absente / malformée / toute nulle ⇒ aucune couche, SVG inchangé', () => {
    const nu = renderYearCurve(11000, undefined, 'fr', {}, served()).svg;
    for (const serie of [null, [], Array(24).fill(0), Array(12).fill(1), Array(24).fill(Number.NaN)]) {
      const out = renderYearCurve(
        11000, undefined, 'fr', {}, served({ batterieHoraireKwh: serie }),
      );
      expect(out.hasBatteryLayer).toBe(false);
      expect(out.svg).toBe(nu);
    }
  });

  it('jamais de couche batterie sur un axe illustratif (aucune donnée servie)', () => {
    const out = renderYearCurve(11000, undefined, 'fr', {}, { batterieHoraireKwh: BATT });
    expect(out.hasBatteryLayer).toBe(false);
    expect(out.svg).not.toContain('data-curve-battery');
  });

  it('le calque batterie ne fait plus DISPARAÎTRE la courbe journalière', () => {
    const avail = {
      monthly: true, daily: true, variants: ['normal' as const], battery: true,
    };
    const l = productionLayers(
      { ...initialProductionState(avail), view: 'journee' as const, battery: true }, avail,
    );
    expect(l.battery).toBe(true);
    expect(l.daily).toBe(true);
  });

  // Source pins — le câblage réel de la page.
  it('la page transmet la série du simulateur à la courbe (un seul moteur)', () => {
    expect(CODE).toContain('__propBatteryHourly');
    expect(CODE).toContain('batterieHoraireKwh,');
    expect(CODE).toContain('batterieHoraireKwh: batteryInitial.hourly.battery,');
    // La courbe est redemandée par le simulateur à chaque recalcul.
    expect(CODE).toContain('__propRerenderCurves');
  });

  it('la légende « Couvert par la batterie » suit le calque', () => {
    expect(CODE).toContain('data-prod-battery-legend');
    expect(CODE).toContain('data-fr="Couvert par la batterie"');
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('3a. Payback par palier — passe directe du moteur', () => {
  it('storageSweepInfo lit `payback_annees` / `economie_mad` tels quels', () => {
    const r = storageSweepInfo({
      balayage_stockage: {
        paliers: [
          {
            nb_packs: 1, capacite_kwh: 5, cout_ttc: 42000,
            remplissage_moyen_pct: 98.2, payback_annees: 7.4, economie_mad: 5680,
          },
        ],
      },
    });
    expect(r!.paliers[0].paybackAnnees).toBe(7.4);
    expect(r!.paliers[0].economieMad).toBe(5680);
  });

  it('payback absent / non fini ⇒ null (omis, jamais approché)', () => {
    for (const payback of [undefined, null, Number.NaN, 'x' as unknown as number]) {
      const r = storageSweepInfo({
        balayage_stockage: {
          paliers: [{ nb_packs: 2, capacite_kwh: 10, payback_annees: payback }],
        },
      });
      expect(r!.paliers[0].paybackAnnees).toBeNull();
    }
  });

  it('la page N’A AUCUNE arithmétique de payback : elle lit le palier servi', () => {
    expect(CODE).toContain('payback: p.paybackAnnees,');
    expect(CODE).toContain('const payback = palierAt(n)?.payback ?? null;');
    expect(CODE).toContain('row.hidden = payback == null;');
    // Les deux chiffres montrés (« X ans → Y ans ») sont DEUX valeurs servies.
    expect(CODE).toContain('const refPayback = palierAt(cfg.initialN)?.payback ?? null;');
    expect(CODE).toContain('`${fmtNum(refPayback, 1)} ${unit} → ${now}`');
    // Aucun coût divisé par une économie côté client.
    expect(CODE).not.toContain('ttc / eco');
    expect(CODE).not.toContain('coutTtc /');
  });

  it('l’unité « ans » suit la langue, jamais le nombre', () => {
    expect(CODE).toContain("const YEARS_UNIT: Record<BsLang, string> = { fr: 'ans', en: 'years', ar: 'سنوات' };");
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('3b. Charge incomplète d’un palier ACCEPTÉ', () => {
  it('le message n’apparaît que sous 100 % de remplissage moyen', () => {
    expect(CODE).toContain('const pct = palierAt(n)?.remplissagePct ?? null;');
    expect(CODE).toContain('const show = pct != null && pct < 100;');
    expect(CODE).toContain('id="battery-sim-fill"');
  });

  it('le pourcentage inséré est celui du palier (aucun calcul côté JS)', () => {
    expect(CODE).toContain("const numEl = el.querySelector<HTMLElement>('[data-fill-pct-num]');");
    expect(CODE).toContain('if (numEl) numEl.textContent = fmtPct(pct);');
    expect(CODE).toContain('remplissagePct: p.remplissageMoyenPct,');
  });

  it('le message de SUR-STOCKAGE (palier refusé) reste distinct et intact', () => {
    expect(CODE).toContain('id="battery-sim-overstorage"');
    expect(CODE).toContain('const hit = !!refuse && refuse.n === n;');
  });

  it('les trois langues sont servies par data-i18n', () => {
    expect(PAGE).toContain('data-fr="La batterie supplémentaire ne se remplira pas à 100 %"');
    expect(PAGE).toContain('data-en="The extra battery will not be filled to 100%"');
    expect(PAGE).toContain('data-ar="لن تمتلئ البطارية الإضافية بنسبة 100٪"');
  });
});
