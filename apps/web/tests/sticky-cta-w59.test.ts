// Garde-fou W59 — raffinement du CTA collant (StickyCta.astro), lecture SOURCE
// en texte (convention de content.test.ts / homepage-craft-w51-w58.test.ts),
// sans navigateur ni build. On affirme :
//   FROZEN  — le lien WhatsApp, le lien Diagnostic #simulateur et la logique
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

  it('garde le lien Diagnostic gratuit vers #simulateur', () => {
    // W67 — libellé et lien localisés (FR inchangé : t('cta.stickyDiag') =
    // « Diagnostic gratuit », lien vers /contact#simulateur en FR).
    expect(cta).toContain("t('cta.stickyDiag')");
    expect(cta).toContain('id="sticky-diag"');
    expect(cta).toContain("localizeNavHref('/contact', locale) + '#simulateur'");
    // Le script bascule vers l’ancre locale quand le formulaire est sur la page.
    expect(cta).toContain("href = '#simulateur'");
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
