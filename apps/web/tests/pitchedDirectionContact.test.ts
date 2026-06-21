// Garde-fous des 3 chantiers pro-11 (lane B) :
//  1. correction FINE du sens de la pente (curseur #rp9-facing-range 0–359°) ;
//  2. aire de toiture corrigée du cos de la pente dans le prefill ;
//  3. diagnostic « une page » OPT-IN sur pro-11 (singleStep) — le défaut (wizard
//     3 étapes) reste byte-identique et le pipe de lead live est intact.
// Tests « chaîne de caractères » (source) ; le câblage runtime est couvert par
// tests/estimatorRuntimePro10Pro11.test.ts.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { billRangeIdForAmount, roofTypeIdForBuilder } from '../src/scripts/roofPro11/prefill';
import { BILL_RANGES } from '../src/lib/billRange';
import { ROOF_TYPES } from '../src/lib/lead';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('Task 1 — curseur de correction fine du sens de la pente', () => {
  const page = read('../src/pages/preview/toiture-3d-pro-11.astro');
  const tool = read('../src/scripts/roof-tool-pro11.ts');

  it('la page ajoute un curseur 0–359° step="any" + une lecture aria-live, en GARDANT les 5 boutons', () => {
    expect(page).toMatch(/id="rp9-facing-range"[^>]*type="range"/s);
    expect(page).toMatch(/id="rp9-facing-range"[^>]*min="0"/s);
    expect(page).toMatch(/id="rp9-facing-range"[^>]*max="359"/s);
    expect(page).toMatch(/id="rp9-facing-range"[^>]*step="any"/s);
    expect(page).toContain('id="rp9-facing-value"');
    expect(page).toMatch(/id="rp9-facing-value"[^>]*aria-live="polite"/s);
    // libellé FR demandé + les 5 boutons cardinaux toujours présents
    expect(page).toContain('Sens de la pente');
    for (const az of ['180', '135', '225', '90', '270']) {
      expect(page).toContain(`data-facing="${az}"`);
    }
    // le texte d'aide invite à corriger le sens de la pente
    expect(page).toMatch(/corriger.*sens de la pente|sens de la pente.*corriger/is);
  });

  it('le script câble le curseur : normalisation 0–359, sync chips/lecture, recompute pente', () => {
    expect(tool).toContain("rp9-facing-range");
    expect(tool).toContain("rp9-facing-value");
    expect(tool).toContain('const facingName');
    // normalisation modulo 360 (jamais de rejet d'un nombre tapé)
    expect(tool).toMatch(/facingAzimuthDeg = \(\(v % 360\) \+ 360\) % 360/);
    // sur input pente fermée → re-résolution
    expect(tool).toContain('pitchedRecompute()');
    // sync au clic cardinal ET au restore de zone
    expect(tool).toContain('syncFacingSlider');
  });
});

describe('Task 2 — aire corrigée du cos de la pente (prefill)', () => {
  const prefill = read('../src/scripts/roofPro11/prefill.ts');

  it('le prefill divise la projetée par cos(pente) en pente, avec garde-fou cos<=0', () => {
    expect(prefill).toContain('Math.cos(ctx.pitchDeg * DEG2RAD)');
    expect(prefill).toMatch(/ctx\.roofType === 'pitched'/);
    // garde-fou : cos fini et > 0, sinon repli sur la projetée
    expect(prefill).toMatch(/Number\.isFinite\(cosPitch\) && cosPitch > 0/);
    expect(prefill).toContain('projected / cosPitch');
    // le toit plat n'est PAS corrigé (la branche est gardée par 'pitched')
  });
});

describe('Task 3 — diagnostic « une page » opt-in (singleStep)', () => {
  const form = read('../src/components/DiagnosticFormEnriched.astro');
  const page = read('../src/pages/preview/toiture-3d-pro-11.astro');

  it('le DÉFAUT (sans singleStep) garde le wizard 3 étapes intact', () => {
    // marqueurs du wizard 3 étapes toujours présents dans le composant
    expect(form).toContain('data-step="1"');
    expect(form).toContain('data-step="2"');
    expect(form).toContain('data-step="3"');
    expect(form).toContain('id="diag-progress"');
    expect(form).toContain('id="diag-next"');
    expect(form).toContain('id="diag-back"');
    expect(form).toContain('Étape 1 sur 3');
    expect(form).toContain('renderStep');
    // l'attribut n'apparaît QUE conditionnellement (undefined si non singleStep → omis)
    expect(form).toContain("data-single-step={singleStep ? 'true' : undefined}");
    // le défaut de la prop est false
    expect(form).toContain('singleStep = false');
  });

  it('singleStep produit data-single-step="true" et une branche « tout sur une page »', () => {
    expect(form).toContain('singleStep');
    expect(form).toContain("form?.dataset.singleStep === 'true'");
    expect(form).toContain('renderSingleStep');
    // masque progression + nav, force le submit visible
    expect(form).toMatch(/progressEl\.classList\.add\('hidden'\)/);
    expect(form).toMatch(/nextBtn\.classList\.add\('hidden'\)/);
    expect(form).toMatch(/backBtn\.classList\.add\('hidden'\)/);
    expect(form).toMatch(/submitBtn\.classList\.remove\('hidden'\)/);
    // le wizard n'est PAS armé en single-step
    expect(form).toContain('if (!singleStep)');
  });

  it('le payload + endpoint restent EXACTEMENT ceux du formulaire live preview', () => {
    // un seul POST, toujours vers /api/preview-lead, jamais un fetch /api/simulate
    expect(form).toContain("fetch('/api/preview-lead'");
    expect(form).not.toContain("fetch('/api/simulate'");
    // les champs du payload sont inchangés
    for (const k of ['fullName', 'phone', 'whatsappOptIn', 'city', 'roofType', 'billRange', 'consent']) {
      expect(form).toContain(`fd.get('${k}')`);
    }
    // les selects obligatoires restent dans le DOM (pré-remplis, jamais retirés)
    expect(form).toContain('name="billRange"');
    expect(form).toContain('name="roofType"');
    expect(form).toContain('name="city"');
  });

  it('pro-11 passe singleStep et place le formulaire dans le flux une page', () => {
    expect(page).toContain('DiagnosticFormEnriched');
    expect(page).toContain('singleStep={true}');
    // le CTA continue de défiler vers #simulateur (id du formulaire)
    expect(page).toContain('id="rp9-cta"');
  });
});

describe('garde de sécurité — pro-11 ne poste AUCUN lead lui-même', () => {
  it('le script de la page pro-11 importe son outil paresseusement et ne POSTe rien', () => {
    const page = read('../src/pages/preview/toiture-3d-pro-11.astro');
    // le script INLINE de la page (hors composant) ne contient aucun POST de lead
    const inline = page.slice(page.indexOf('<script>'));
    expect(inline).not.toContain("fetch('/api/preview-lead'");
    expect(inline).not.toContain("fetch('/api/simulate'");
    expect(inline).toContain("import('../../scripts/roof-tool-pro11.ts')");
  });

  it('le formulaire LIVE (non-preview) reste sur /api/simulate, jamais /api/preview-lead', () => {
    const live = read('../src/components/DiagnosticForm.astro');
    expect(live).toContain("fetch('/api/simulate'");
    expect(live).not.toContain('preview-lead');
    expect(live).not.toContain('singleStep');
  });
});

describe('helpers purs — mapping facture/toit pour le prefill une page', () => {
  it('billRangeIdForAmount range un montant MAD dans le bon bucket BILL_RANGES', () => {
    expect(billRangeIdForAmount(500)).toBe('lt800');
    expect(billRangeIdForAmount(799)).toBe('lt800');
    expect(billRangeIdForAmount(800)).toBe('800-1000');
    expect(billRangeIdForAmount(999)).toBe('800-1000');
    expect(billRangeIdForAmount(1000)).toBe('1000-1500');
    expect(billRangeIdForAmount(1500)).toBe('1500-3000');
    expect(billRangeIdForAmount(3000)).toBe('3000-5000');
    expect(billRangeIdForAmount(5000)).toBe('5000-10000');
    expect(billRangeIdForAmount(10000)).toBe('gt10000');
    expect(billRangeIdForAmount(50000)).toBe('gt10000');
    // non fini / <= 0 → '' (le visiteur complète)
    expect(billRangeIdForAmount(0)).toBe('');
    expect(billRangeIdForAmount(-5)).toBe('');
    expect(billRangeIdForAmount(Number.NaN)).toBe('');
    // tout id renvoyé existe bien dans BILL_RANGES
    for (const v of [500, 900, 1200, 2000, 4000, 7000, 20000]) {
      const id = billRangeIdForAmount(v);
      expect(BILL_RANGES.some((r) => r.id === id)).toBe(true);
    }
  });

  it('roofTypeIdForBuilder mappe flat→toit_plat, pitched→villa (ids existants)', () => {
    expect(roofTypeIdForBuilder('flat')).toBe('toit_plat');
    expect(roofTypeIdForBuilder('pitched')).toBe('villa');
    expect(ROOF_TYPES.some((r) => r.id === roofTypeIdForBuilder('flat'))).toBe(true);
    expect(ROOF_TYPES.some((r) => r.id === roofTypeIdForBuilder('pitched'))).toBe(true);
  });
});
