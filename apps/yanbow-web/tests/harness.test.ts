import { describe, expect, it, vi } from 'vitest';
import { pagesRendues, urlDeFichier } from './builtHtml';
import { FetchNonSimule } from './setup';

describe('YBW14 — stub réseau global', () => {
  it('un fetch non simulé échoue (cas prouvé)', () => {
    expect(() => fetch('https://exemple.test/x')).toThrow(FetchNonSimule);
    expect(() => fetch(new Request('https://exemple.test/y'))).toThrow(/exemple\.test\/y/);
  });

  it('un fetch simulé explicitement fonctionne, puis le stub revient', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('ok')));
    expect(await (await fetch('https://exemple.test/')).text()).toBe('ok');
    vi.unstubAllGlobals();
    expect(() => fetch('https://exemple.test/')).toThrow(FetchNonSimule);
  });
});

describe('YBW14 — aides « HTML rendu »', () => {
  it('urlDeFichier', () => {
    expect(urlDeFichier('index.html')).toBe('/');
    expect(urlDeFichier('en/index.html')).toBe('/en/');
    expect(urlDeFichier('solarbow/index.html')).toBe('/solarbow/');
  });

  it('au moins une page est construite', () => {
    expect(pagesRendues().length).toBeGreaterThan(0);
  });

  it('chaque page rendue porte le <html lang> de sa langue', () => {
    for (const p of pagesRendues()) {
      expect(p.document.documentElement.getAttribute('lang'), p.url).toBe(p.langueUrl);
    }
  });
});
