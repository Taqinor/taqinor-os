// Garde-fou W59 — raffinement du CTA collant (StickyCta.astro), lecture SOURCE
// en texte (convention de content.test.ts / homepage-craft-w51-w58.test.ts),
// sans navigateur ni build. On affirme :
//   FROZEN  — le lien WhatsApp, le lien du CTA principal vers le parcours devis
//             (WJ36 : quoteJourneyHref → /devis/mon-toit) et la logique
//             d'affichage pastHero/formVisible restent intacts ;
//   W59     — la pilule desktop est plus compacte + marge de sécurité au bord,
//             et un repli au défilement (translate-y) est posé par-dessus.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const cta = readFileSync(
  fileURLToPath(new URL('../src/components/StickyCta.astro', import.meta.url)),
  'utf-8',
);

describe('StickyCta — invariants gelés (les liens et la logique d’affichage)', () => {
  it('garde le lien WhatsApp (whatsappLink + href={wa})', () => {
    expect(cta).toContain('whatsappLink');
    expect(cta).toContain('const wa = whatsappLink(');
    expect(cta).toContain('href={wa}');
  });

  it('WJ36 — le CTA principal pointe le parcours devis (quoteJourneyHref)', () => {
    // Libellé principal verbatim (t('cta.primary') = « Obtenir mon étude
    // gratuite » en FR) et lien vers /devis/mon-toit via le point de bascule
    // unique quoteJourneyHref (WJ38 localisera EN/AR dans i18n/pages.ts).
    expect(cta).toContain("t('cta.primary')");
    expect(cta).toContain('id="sticky-diag"');
    expect(cta).toContain('quoteJourneyHref(locale)');
    // Plus AUCUNE bascule du href vers l'ancre #simulateur.
    expect(cta).not.toContain("href = '#simulateur'");
  });

  it('garde la logique d’affichage pastHero / formVisible', () => {
    expect(cta).toContain('let pastHero');
    expect(cta).toContain('let formVisible');
    expect(cta).toContain("bar?.classList.toggle('hidden', !pastHero || formVisible)");
    // L’observateur du formulaire pilote toujours formVisible.
    expect(cta).toContain('IntersectionObserver');
    expect(cta).toContain('formVisible = entries[0].isIntersecting');
  });
});

describe('W59 — pilule desktop compacte + marge de sécurité', () => {
  it('s’écarte du bord du viewport (offset agrandi)', () => {
    expect(cta).toContain('sm:bottom-6');
    expect(cta).toContain('sm:right-6');
  });

  it('adopte une forme pilule compacte sur desktop', () => {
    expect(cta).toContain('sm:rounded-full');
    // Padding réduit et texte plus petit côté desktop.
    expect(cta).toContain('sm:text-[13px]');
    expect(cta).toMatch(/sm:px-1\.5/);
  });
});

describe('W59 — repli au défilement (anti-recouvrement), posé par-dessus', () => {
  it('suit la direction du défilement (collapsed + lastY)', () => {
    expect(cta).toContain('let collapsed');
    expect(cta).toContain('let lastY');
  });

  it('glisse la pilule hors-champ par transform (zéro reflow)', () => {
    expect(cta).toContain("bar?.classList.toggle('translate-y-[150%]', collapsed)");
    expect(cta).toContain('transition-transform');
  });

  it('respecte prefers-reduced-motion', () => {
    expect(cta).toContain('motion-reduce:transition-none');
  });

  it('le repli reste SUBORDONNÉ à pastHero/formVisible (le `hidden` garde la priorité)', () => {
    // La bascule `hidden` apparaît avant la bascule de transform dans update().
    const hiddenIdx = cta.indexOf("classList.toggle('hidden'");
    const transformIdx = cta.indexOf("classList.toggle('translate-y-[150%]'");
    expect(hiddenIdx).toBeGreaterThan(-1);
    expect(transformIdx).toBeGreaterThan(hiddenIdx);
  });
});
