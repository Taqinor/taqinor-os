// WJ17 — Bascule de langue FR/عربي RTL-native sur les deux pages du parcours
// (capture « Mon toit » + proposition [token]). Discipline : le toggle
// préserve tout markup imbriqué (dual-node show/hide, jamais `.textContent =`
// qui aplatirait des balises), applique dir/lang au niveau DOCUMENT, et l'AR
// se lit comme un design RTL de première classe (line-height, mirroring),
// pas un habillage de dernière minute. Lecture SOURCE en texte, sans build
// (même convention que perceivedPerfWJ34.test.ts / quoteCtaWJ36.test.ts) :
// ces micro-interactions DOM ne sont pas facilement montables sous vitest —
// on prouve donc les invariants de câblage.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const MON_TOIT = read('../src/pages/devis/mon-toit.astro');
const PROPOSITION = read('../src/pages/proposition/[token].astro');
const GLOBAL_CSS = read('../src/styles/global.css');

describe('WJ17 — proposition/[token].astro : le switcher FR/عربي est câblé (pas juste des boutons morts)', () => {
  it('les boutons #prop-lang-fr / #prop-lang-ar existent avec la classe prop-lang-switch', () => {
    expect(PROPOSITION).toContain('prop-lang-switch');
    expect(PROPOSITION).toContain('id="prop-lang-fr"');
    expect(PROPOSITION).toContain('id="prop-lang-ar"');
  });

  it('un script implémente applyLang + prepareI18n (le toggle n’est plus une coquille vide)', () => {
    expect(PROPOSITION).toContain('function prepareI18n');
    expect(PROPOSITION).toContain('function applyLang');
    expect(PROPOSITION).toContain("getElementById('prop-lang-fr')?.addEventListener('click', () => applyLang('fr'))");
    expect(PROPOSITION).toContain("getElementById('prop-lang-ar')?.addEventListener('click', () => applyLang('ar'))");
  });

  it('le toggle utilise le mécanisme DUAL-NODE (jamais el.textContent = qui aplatirait un <strong> imbriqué)', () => {
    const fn = PROPOSITION.slice(PROPOSITION.indexOf('function prepareI18n'), PROPOSITION.indexOf('function applyLang'));
    expect(fn).toContain('frSpan.innerHTML = el.innerHTML');
    expect(fn).toContain('arSpan.textContent = arText');
    expect(fn).toContain('el.append(frSpan, arSpan)');
    const applyFn = PROPOSITION.slice(PROPOSITION.indexOf('function applyLang'), PROPOSITION.indexOf('prepareI18n();'));
    expect(applyFn).toContain('fr.hidden = isAr');
    expect(applyFn).toContain('ar.hidden = !isAr');
    // La bascule ne doit PAS réécrire le innerHTML/textContent d'un élément
    // data-i18n à chaque clic (ce serait le bug WJ33 corrigé) — seul le
    // hidden des paires change.
    expect(applyFn).not.toContain('el.textContent =');
  });

  it('applyLang pilote dir/lang au niveau DOCUMENT + aria-pressed sur les deux boutons', () => {
    const applyFn = PROPOSITION.slice(PROPOSITION.indexOf('function applyLang'), PROPOSITION.indexOf('prepareI18n();'));
    expect(applyFn).toContain("document.documentElement.lang = isAr ? 'ar' : 'fr'");
    expect(applyFn).toContain("document.documentElement.dir = isAr ? 'rtl' : 'ltr'");
    expect(applyFn).toContain("frBtn?.setAttribute('aria-pressed'");
    expect(applyFn).toContain("arBtn?.setAttribute('aria-pressed'");
  });

  it('les libellés « busy » (Signature…, génération PDF…) restent FR/AR-corrects via un registre partagé plutôt que de casser le dual-node', () => {
    expect(PROPOSITION).toContain('__propRegisterBusyLabel');
    expect(PROPOSITION).toContain('__propCurrentLang');
    expect(PROPOSITION).toContain('SUBMIT_LABEL_BUSY');
    expect(PROPOSITION).toContain('PDF_LABEL_LOADING');
  });

  it('au moins 100 éléments portent data-i18n (couverture large, pas juste les 36 du commit partiel)', () => {
    const count = (PROPOSITION.match(/data-i18n/g) || []).length;
    expect(count).toBeGreaterThanOrEqual(100);
  });

  it('les anciens spans AR toujours-visibles (dir="rtl" côte-à-côte) ont été convertis en toggle (plus de span[dir=rtl] à côté d’un span FR non tagué)', () => {
    // Le pattern bolt-on corrigé : walkthrough/étapes/hypothèses/FAQ affichaient
    // avant un <span dir="rtl" lang="ar"> visible en permanence à côté du FR.
    // Après WJ17, ces blocs passent par data-i18n (dual-node caché/affiché).
    expect(PROPOSITION).not.toContain('<span dir="rtl" lang="ar" class="shrink-0 text-xs text-lune-faint">{s.titleAr}');
    expect(PROPOSITION).not.toContain('<span dir="rtl" lang="ar" class="shrink-0 text-xs text-lune-faint">{m.labelAr}');
    expect(PROPOSITION).not.toContain('<span dir="rtl" lang="ar" class="shrink-0 text-xs">{a.labelAr}');
    // Les questionAr/answerAr existent toujours — mais uniquement comme valeur
    // data-ar= du toggle, jamais comme span visible en permanence.
    expect(PROPOSITION).not.toContain('lang="ar" class="shrink-0 text-xs font-normal text-lune-faint">{item.questionAr}');
    expect(PROPOSITION).not.toContain('text-right text-xs text-lune-faint" style="line-height: 1.8">{item.answerAr}');
    expect(PROPOSITION).toContain('data-ar={item.questionAr}');
    expect(PROPOSITION).toContain('data-ar={item.answerAr}');
  });

  it('les valeurs numériques/références/dates restent dir="ltr" (jamais mirées en RTL)', () => {
    expect(PROPOSITION).toContain('dir="ltr"');
    // Chaîne de prix (Sous-total/Total HT/TVA/Total TTC) : chaque <dd> figure numérique est LTR.
    const priceChain = PROPOSITION.slice(PROPOSITION.indexOf('Chaîne de prix explicite'), PROPOSITION.indexOf('Chaîne de prix explicite') + 1800);
    expect((priceChain.match(/dir="ltr"/g) || []).length).toBeGreaterThanOrEqual(5);
  });
});

describe('WJ17 — mon-toit.astro : le toggle WJ33 reste la référence + couvre les blocs de cette run', () => {
  it('le mécanisme dual-node (prepareI18n/applyLang) est présent et documenté comme référence WJ33', () => {
    expect(MON_TOIT).toContain('function prepareI18n()');
    expect(MON_TOIT).toContain('function applyLang(lang:');
    expect(MON_TOIT).toContain('APLATISSAIT');
  });

  it('le step de capture 3D (WJ2) est AR-labellé et participe au toggle', () => {
    expect(MON_TOIT).toContain('data-fr="Voir les panneaux sur votre toit" data-ar="مشاهدة الألواح على سطحك"');
  });

  it('les questions optionnelles WJ31 sont AR-labellées', () => {
    expect(MON_TOIT).toContain('data-fr="Affiner mon estimation (facultatif, 1 minute)" data-ar="تحسين تقديري (اختياري، دقيقة واحدة)"');
    expect(MON_TOIT).toContain('data-fr="Ombrage sur le toit" data-ar="التظليل على السطح"');
  });

  it('applyLang pilote dir/lang document + une hauteur de ligne AR plus généreuse', () => {
    const applyFn = MON_TOIT.slice(MON_TOIT.indexOf('function applyLang'), MON_TOIT.indexOf('prepareI18n();'));
    expect(applyFn).toContain("document.documentElement.dir = isAr ? 'rtl' : 'ltr'");
    expect(applyFn).toContain("root.style.lineHeight = isAr ? '1.75' : ''");
  });
});

describe('WJ17 — RTL CSS designed-in (global.css), pas seulement du JS inline', () => {
  it('une règle [dir="rtl"] fixe une line-height AR généreuse (1.6–1.8×)', () => {
    const block = GLOBAL_CSS.slice(GLOBAL_CSS.indexOf('WJ17'));
    expect(block).toContain('[dir="rtl"] {');
    expect(block).toContain('line-height: 1.7;');
  });

  it('les chiffres/dates dir="ltr" imbriqués dans un conteneur RTL restent isolés (unicode-bidi)', () => {
    const block = GLOBAL_CSS.slice(GLOBAL_CSS.indexOf('WJ17'));
    expect(block).toContain('[dir="rtl"] [dir="ltr"]');
    expect(block).toContain('unicode-bidi: isolate');
  });

  it('les glyphes flèche/chevron inline se retournent en RTL', () => {
    const block = GLOBAL_CSS.slice(GLOBAL_CSS.indexOf('WJ17'));
    expect(block).toContain('scaleX(-1)');
  });

  it('le switcher de langue flottant reste ancré au bord logique (flip left/right en RTL)', () => {
    const block = GLOBAL_CSS.slice(GLOBAL_CSS.indexOf('WJ17'));
    expect(block).toContain('[dir="rtl"] .prop-lang-switch');
  });
});
