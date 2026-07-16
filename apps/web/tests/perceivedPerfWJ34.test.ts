// WJ34 — Performance perçue & délice sur les deux pages du parcours : squelettes
// réservés (map + calcul d'estimation), poster blur-up du héros de la
// proposition, affordance « génération du PDF… », safe-area-inset-bottom sur
// les éléments collants. Lecture SOURCE en texte (même convention que
// quoteCtaWJ36.test.ts) : ces éléments sont des micro-interactions DOM qu'on
// ne peut pas facilement monter sous vitest — on prouve donc les invariants de
// câblage et de sûreté (zéro CLS, reduced-motion respecté).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const MON_TOIT = read('../src/pages/devis/mon-toit.astro');
const PROPOSITION = read('../src/pages/proposition/[token].astro');

describe('WJ34 — mon-toit.astro : squelettes de performance perçue', () => {
  it('la carte porte un squelette shimmer retiré à onReady / au repli sans carte', () => {
    expect(MON_TOIT).toContain('mt-skeleton-shimmer');
    expect(MON_TOIT).toContain('id="rp9-map"');
    expect(MON_TOIT).toContain('function clearMapSkeleton()');
    expect(MON_TOIT).toContain('onReady: clearMapSkeleton');
  });

  it('le repli carte (showFallback) retire aussi le squelette — jamais de shimmer figé', () => {
    const fallbackFn = MON_TOIT.slice(MON_TOIT.indexOf('function showFallback'));
    expect(fallbackFn.slice(0, 120)).toContain('clearMapSkeleton()');
  });

  it("l'estimation affiche un squelette/anticipation AVANT le calcul (performance perçue), zéro CLS (même gabarit text-3xl)", () => {
    // Le câblage du squelette + anticipation branded reste EN PLACE (l'affordance
    // « un calcul se produit » demeure). Le calcul (computeEstimate) est toujours
    // déclenché dans le rAF, exactement comme avant.
    expect(MON_TOIT).toContain('function showEstimateSkeleton()');
    expect(MON_TOIT).toContain('mt-est-skeleton');
    expect(MON_TOIT).toContain('showEstimateSkeleton();');
    // WJ46 a élargi le rAF (récupère le retour de computeEstimate pour déclencher
    // l'offre WhatsApp au rendu de l'estimation) — le squelette reste peint avant le calcul.
    expect(MON_TOIT).toContain('requestAnimationFrame(() => {');
    expect(MON_TOIT).toContain('computeEstimate();');
  });

  it("WJ125 — le squelette/anticipation précède désormais la CARTE TEASER gatée (le document chiffré ne se rend plus dans le parcours public — seul le RENDU change, le CALCUL reste)", () => {
    // Adaptation délibérée au nouveau rendu gaté (RÈGLE FONDATEUR anti-concurrent) :
    // computeEstimate calcule toujours (estimateShown part au CRM) mais, en public,
    // il révèle une carte teaser verrouillée au lieu du document chiffré. Le
    // squelette ci-dessus reste l'affordance « calcul en cours » qui la précède.
    expect(MON_TOIT).toContain('const PUBLIC_ESTIMATE_GATED: boolean = true;');
    expect(MON_TOIT).toContain('function showEstimateTeaser(');
    expect(MON_TOIT).toContain('if (PUBLIC_ESTIMATE_GATED) showEstimateTeaser(mode);');
    // le document détaillé est masqué en permanence dans le parcours public.
    expect(MON_TOIT).toContain('<div id="mt-doc" class="mt-doc mt-4" hidden>');
  });

  it('le shimmer est gated prefers-reduced-motion (statique sinon)', () => {
    const shimmerBlock = MON_TOIT.slice(MON_TOIT.indexOf('.mt-skeleton-shimmer'), MON_TOIT.indexOf('.mt-skeleton-shimmer') + 700);
    expect(shimmerBlock).toContain('prefers-reduced-motion: no-preference');
  });

  it('la modale de récupération d’abandon respecte env(safe-area-inset-bottom)', () => {
    expect(MON_TOIT).toContain('id="mt-exit"');
    const exitBlock = MON_TOIT.slice(MON_TOIT.indexOf('id="mt-exit"') - 200, MON_TOIT.indexOf('id="mt-exit"') + 300);
    expect(exitBlock).toContain('env(safe-area-inset-bottom)');
  });
});

describe('WJ34 — [token].astro : poster blur-up, PDF affordance, safe-area', () => {
  it('le héros porte un poster LQIP (dégradé) sous la photo, JAMAIS masqué (LCP protégé)', () => {
    expect(PROPOSITION).toContain('hero-lqip');
    expect(PROPOSITION).toContain('hero-photo');
    expect(PROPOSITION).toContain("onload=\"this.classList.add('is-loaded')\"");
    // La photo garde loading="eager" — jamais transformée en lazy par erreur.
    const heroBlock = PROPOSITION.slice(PROPOSITION.indexOf('hero-lqip'), PROPOSITION.indexOf('hero-lqip') + 900);
    expect(heroBlock).toContain('loading="eager"');
  });

  it('le fondu du poster est gated reduced-motion (opaque par défaut, transition seulement sous no-preference)', () => {
    const cssBlock = PROPOSITION.slice(PROPOSITION.lastIndexOf('.hero-lqip'));
    expect(cssBlock).toContain('.hero-photo {');
    expect(cssBlock).toContain('opacity: 1;');
    expect(cssBlock).toContain('prefers-reduced-motion: no-preference');
  });

  it('le lien PDF affiche « Génération du PDF… » au clic puis revient à l’état par défaut (WJ17/WJ43 : FR/EN/AR-aware)', () => {
    expect(PROPOSITION).toContain('id="pdf-download"');
    expect(PROPOSITION).toContain("PDF_LABEL_LOADING = { fr: 'Génération du PDF…', en: 'Generating the PDF…', ar: 'جارٍ إنشاء PDF…' }");
    expect(PROPOSITION).toContain("PDF_LABEL_DEFAULT = { fr: 'Télécharger le devis (PDF)', en: 'Download the quote (PDF)', ar: 'تحميل العرض (PDF)' }");
    expect(PROPOSITION).toContain("pdfLink.addEventListener('click'");
    expect(PROPOSITION).toContain("document.addEventListener('visibilitychange'");
  });

  it('le lien PDF garde target=_blank (jamais bloqué par preventDefault dans le code, hors commentaires)', () => {
    const linkBlock = PROPOSITION.slice(PROPOSITION.indexOf('id="pdf-download"') - 100, PROPOSITION.indexOf('id="pdf-download"') + 300);
    expect(linkBlock).toContain('target="_blank"');
    const scriptStart = PROPOSITION.indexOf('WJ34 — affordance');
    // WJ53/WJ56/WJ80 folded more logic into this SAME <script> tag AFTER the
    // PDF affordance (to keep the page at exactly 3 <script> blocks — see the
    // scriptTagCount test below) ; WJ56's Web Share handler legitimately calls
    // preventDefault() on a DIFFERENT element (#prop-share-whatsapp), so the
    // slice must stop at the PDF affordance's own closing brace
    // (`if (pdfLink && pdfLabel) { … }`), not at the end of the whole script tag.
    const pdfIfStart = PROPOSITION.indexOf('if (pdfLink && pdfLabel)', scriptStart);
    const closeMatch = /\r?\n {2}\}\r?\n/.exec(PROPOSITION.slice(pdfIfStart));
    const scriptEnd = closeMatch ? pdfIfStart + closeMatch.index : PROPOSITION.indexOf('</script>', scriptStart);
    const codeLines = PROPOSITION.slice(scriptStart, scriptEnd)
      .split('\n')
      .filter((line) => !line.trim().startsWith('//'));
    expect(codeLines.join('\n')).not.toContain('preventDefault');
  });

  it('le CTA collant « Signer en ligne » respecte env(safe-area-inset-bottom)', () => {
    const stickyBlock = PROPOSITION.slice(PROPOSITION.indexOf('id="sticky-cta"'), PROPOSITION.indexOf('id="sticky-cta"') + 400);
    expect(stickyBlock).toContain('env(safe-area-inset-bottom)');
  });

  it('l’affordance PDF vit DANS le script WJ29 (pas un 5ᵉ <script> isolé) — un 4ᵉ <script> sans import ES sur cette route perdait son chunk client (manifeste SSR le référençait, le fichier n’était jamais écrit) ; regroupé pour rester bâti', () => {
    const scriptTagCount = (PROPOSITION.match(/^<script>$/gm) ?? []).length;
    expect(scriptTagCount).toBe(3);
    const wj29Start = PROPOSITION.indexOf('WJ29 — «');
    const wj29End = PROPOSITION.indexOf('</script>', wj29Start);
    const wj29Block = PROPOSITION.slice(wj29Start, wj29End);
    expect(wj29Block).toContain('WJ34 — affordance');
    expect(wj29Block).toContain('pdf-download');
  });
});
