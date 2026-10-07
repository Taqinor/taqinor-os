import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

/** Retire les commentaires `//` d'un JSONC (aucune chaîne du fichier n'en contient). */
function lireJsonc(chemin: string): Record<string, unknown> {
  const brut = readFileSync(new URL(chemin, import.meta.url), 'utf-8');
  const sansCommentaires = brut
    .split('\n')
    .map((ligne) => ligne.replace(/^\s*\/\/.*$/, ''))
    .join('\n');
  return JSON.parse(sansCommentaires);
}

describe('YBW10 — configuration Worker propre à YanBow', () => {
  const cfg = lireJsonc('../wrangler.jsonc');

  it('porte un nom unique, jamais celui du site TAQINOR', () => {
    expect(cfg.name).toBe('yanbow-web');
  });

  it('garde les variables du tableau de bord entre déploiements', () => {
    expect(cfg.keep_vars).toBe(true);
  });

  it("ne déclare ni KV, ni cron, ni variable en clair", () => {
    expect(cfg).not.toHaveProperty('kv_namespaces');
    expect(cfg).not.toHaveProperty('triggers');
    expect(cfg).not.toHaveProperty('vars');
  });

  it('le package a son propre nom et Node >= 22.12', () => {
    const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf-8'));
    expect(pkg.name).toBe('yanbow-web');
    expect(pkg.engines.node).toBe('>=22.12.0');
    for (const s of ['dev', 'check', 'build', 'test', 'test:e2e', 'lighthouse']) {
      expect(pkg.scripts).toHaveProperty(s);
    }
  });
});
