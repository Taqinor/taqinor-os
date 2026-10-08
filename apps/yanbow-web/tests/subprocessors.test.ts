/**
 * YBW26 — registre des sous-traitants : la CSP du Worker ne contient AUCUN
 * hôte absent du registre (vérifié sur la CSP construite ET sur la
 * configuration réellement copiée dans le build).
 */
import { existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { describe, expect, it } from 'vitest';
import { buildCsp } from '../worker/headers.mjs';
import { hotesHorsRegistre, KV_REPRISE_DUREE_JOURS, sourcesCsp, SOUS_TRAITANTS, type SousTraitant } from '../src/lib/subprocessors';

describe('YBW26 — registre réel', () => {
  it('Cloudflare, serveur ERP (Allemagne), WhatsApp au clic ; KV absent tant qu’il n’existe pas', () => {
    expect(SOUS_TRAITANTS.map((s) => s.id)).toEqual(['cloudflare', 'serveur-erp', 'whatsapp']);
    expect(KV_REPRISE_DUREE_JOURS).toBeNull();
    expect(SOUS_TRAITANTS.find((s) => s.id === 'serveur-erp')?.pays).toEqual(['DE']);
    expect(SOUS_TRAITANTS.find((s) => s.id === 'whatsapp')?.quand?.fr).toMatch(/clic/);
  });

  it('chaque entrée a un rôle FR et EN et un moment de déclenchement', () => {
    for (const s of SOUS_TRAITANTS) {
      expect(s.role.trim()).not.toBe('');
      expect(s.roleEn?.trim()).toBeTruthy();
      expect(s.quand?.fr && s.quand?.en).toBeTruthy();
    }
  });

  it('aucune entrée ne nomme l’entreprise d’installation', () => {
    expect(JSON.stringify(SOUS_TRAITANTS)).not.toMatch(/taqinor/i);
  });
});

describe('YBW26 — CSP = registre', () => {
  it('la CSP construite depuis le registre n’a aucun hôte hors registre', () => {
    expect(hotesHorsRegistre(buildCsp(sourcesCsp()))).toEqual([]);
  });

  it('cas négatif : un hôte ajouté à la CSP sans entrée au registre est détecté', () => {
    const csp = buildCsp({ 'img-src': ['https://pixel.exemple.test'] });
    expect(hotesHorsRegistre(csp)).toEqual(['https://pixel.exemple.test']);
  });

  it('un hôte déclaré au registre est accepté', () => {
    const registre: SousTraitant[] = [...SOUS_TRAITANTS, { id: 'x', nom: 'X', role: 'test', csp: { 'img-src': ['https://img.exemple.test'] } }];
    expect(hotesHorsRegistre(buildCsp(sourcesCsp(registre)), registre)).toEqual([]);
  });

  it('build : la configuration copiée dans le Worker reprend exactement le registre', async () => {
    const chemin = fileURLToPath(new URL('../dist/server/site-config.mjs', import.meta.url));
    if (!existsSync(chemin)) throw new Error('dist/server/site-config.mjs absent — lancer `npm run build` avant `npm test`');
    const cfg = (await import(/* @vite-ignore */ pathToFileURL(chemin).href)) as { CSP_SOURCES: Record<string, string[]> };
    expect(cfg.CSP_SOURCES).toEqual(sourcesCsp());
    expect(hotesHorsRegistre(buildCsp(cfg.CSP_SOURCES))).toEqual([]);
  });
});
