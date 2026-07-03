// WJ81 — La page proposition (la plus commercialement critique du site) ne
// doit JAMAIS rester blanche : (a) le fetch SSR de la proposition est borné
// par un AbortController avec un message honnête + un « Réessayer » distinct
// d'une vraie panne quand la connexion est simplement lente ; (b) la
// signature ne reste JAMAIS bloquée sur un « Signature… » désactivé pour
// l'éternité — un AbortController de 15 s rend la main avec un message
// « connexion lente » + repli WhatsApp. Lecture SOURCE en texte (même
// convention que perceivedPerfWJ34.test.ts) : ce sont des comportements
// réseau/DOM qu'on ne peut pas monter facilement sous vitest.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const PROPOSITION = read('../src/pages/proposition/[token].astro');

describe('WJ81 — SSR fetch : timeout + repli honnête (jamais un blanc)', () => {
  it('le fetch de la proposition est borné par un AbortController', () => {
    const ssrSection = PROPOSITION.slice(
      PROPOSITION.indexOf('Lecture serveur de la proposition'),
      PROPOSITION.indexOf('Préparation des données'),
    );
    expect(ssrSection).toContain('new AbortController()');
    expect(ssrSection).toContain('setTimeout(() => controller.abort()');
    expect(ssrSection).toContain('signal: controller.signal');
    expect(ssrSection).toContain('clearTimeout(timer)');
  });

  it('un timeout obtient un message DISTINCT (connexion lente) d’une vraie panne réseau', () => {
    const ssrSection = PROPOSITION.slice(
      PROPOSITION.indexOf('Lecture serveur de la proposition'),
      PROPOSITION.indexOf('Préparation des données'),
    );
    expect(ssrSection).toContain("err.name === 'AbortError'");
    expect(ssrSection).toMatch(/La connexion est lente/);
    expect(ssrSection).toContain('isTimeout');
  });

  it('l’état d’erreur timeout propose « Réessayer » (recharge la même URL) + un repli WhatsApp', () => {
    const errorSection = PROPOSITION.slice(
      PROPOSITION.indexOf('État « lien expiré'),
      PROPOSITION.indexOf('WJ84'),
    );
    expect(errorSection).toContain('isTimeout');
    expect(errorSection).toContain('Astro.url.href');
    expect(errorSection).toContain('Réessayer');
    expect(errorSection).toContain('waLinkFallback');
  });

  it('waLinkFallback fonctionne même sans référence (whatsappLink dégrade proprement)', () => {
    expect(PROPOSITION).toContain("const waLinkFallback = whatsappLink(reference || '')");
  });
});

describe('WJ81 — signature : jamais un « Signature… » bloqué pour l’éternité', () => {
  it('la requête de signature est bornée par un AbortController à 15 s', () => {
    const signScript = PROPOSITION.slice(
      PROPOSITION.indexOf("form?.addEventListener('submit'"),
      PROPOSITION.indexOf('</script>', PROPOSITION.indexOf("form?.addEventListener('submit'")),
    );
    expect(signScript).toContain('SIGN_SUBMIT_TIMEOUT_MS = 15000');
    expect(signScript).toContain('new AbortController()');
    expect(signScript).toContain('signal: submitController.signal');
    expect(signScript).toContain('window.clearTimeout(submitTimer)');
  });

  it('un timeout de signature affiche « connexion lente » + oriente vers WhatsApp, jamais un blocage silencieux', () => {
    const signScript = PROPOSITION.slice(
      PROPOSITION.indexOf("form?.addEventListener('submit'"),
      PROPOSITION.indexOf('</script>', PROPOSITION.indexOf("form?.addEventListener('submit'")),
    );
    expect(signScript).toContain("timedOut = err instanceof Error && err.name === 'AbortError'");
    expect(signScript).toMatch(/La connexion est lente/);
    expect(signScript).toMatch(/WhatsApp/);
  });

  it('le bouton de signature est TOUJOURS réactivé dans le `finally` (jamais désactivé pour toujours)', () => {
    const signScript = PROPOSITION.slice(
      PROPOSITION.indexOf("form?.addEventListener('submit'"),
      PROPOSITION.indexOf('</script>', PROPOSITION.indexOf("form?.addEventListener('submit'")),
    );
    const finallyBlock = signScript.slice(signScript.lastIndexOf('} finally {'));
    expect(finallyBlock).toContain('submitBtn.disabled = false');
    expect(finallyBlock).toContain('spinner.hidden = true');
  });
});
