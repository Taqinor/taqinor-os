// W343 — « Partager avec un proche » : composeur de parrainage post-signature.
// DISTINCT de whatsappShareLink (WJ56, tests propositionShareWJ56.test.ts) qui
// partage LA MÊME proposition avec un co-décideur du même foyer AVANT signature.
// W343 partage /parrainage (W338) — un lien tagué vers un NOUVEAU projet pour
// un proche différent — une fois le devis SIGNÉ.
import { describe, expect, it } from 'vitest';
import { referralTaggedLink, whatsappReferralLink } from '../src/lib/proposition';

describe('W343 — referralTaggedLink (même convention que /parrainage.astro)', () => {
  it('construit /parrainage?utm_source=parrainage&utm_campaign=<référence>', () => {
    const url = referralTaggedLink('https://taqinor.ma', 'DEV-2026-042');
    expect(url).toBe('https://taqinor.ma/parrainage?utm_source=parrainage&utm_campaign=DEV-2026-042');
  });

  it('encode la référence (caractères spéciaux)', () => {
    const url = referralTaggedLink('https://taqinor.ma', 'DEV/2026 042');
    expect(url).toContain('utm_campaign=DEV%2F2026%20042');
  });

  it('sans référence → utm_source seul, jamais une chaîne "undefined"', () => {
    const url = referralTaggedLink('https://taqinor.ma', '');
    expect(url).toBe('https://taqinor.ma/parrainage?utm_source=parrainage');
    expect(url).not.toContain('undefined');
  });

  it('retire un slash de fin sur l’origine', () => {
    const url = referralTaggedLink('https://taqinor.ma/', 'DEV-042');
    expect(url).toBe('https://taqinor.ma/parrainage?utm_source=parrainage&utm_campaign=DEV-042');
  });

  it('repli sur https://taqinor.ma quand l’origine est vide', () => {
    const url = referralTaggedLink('', 'DEV-042');
    expect(url.startsWith('https://taqinor.ma/parrainage')).toBe(true);
  });
});

describe('W343 — whatsappReferralLink (compositeur générique, jamais un numéro cible)', () => {
  it('ne cible aucun numéro (wa.me/ générique, comme whatsappShareLink)', () => {
    const url = whatsappReferralLink('https://taqinor.ma', 'DEV-2026-042');
    expect(url.startsWith('https://wa.me/?text=')).toBe(true);
  });

  it('le message contient le lien de parrainage TAGUÉ (pas le lien de la proposition)', () => {
    const url = whatsappReferralLink('https://taqinor.ma', 'DEV-2026-042');
    const decoded = decodeURIComponent(url);
    expect(decoded).toContain('taqinor.ma/parrainage?utm_source=parrainage&utm_campaign=DEV-2026-042');
    expect(decoded).not.toContain('/proposition/');
  });
});
