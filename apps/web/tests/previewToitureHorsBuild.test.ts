// ACAL332 — /preview/toiture* (générations 1 à 3 et pro-11) hors du build de
// production, gardées en galerie interne `astro dev` (D-ACAL-19 : aucune page
// ni aucun script supprimé des sources).
import { afterEach, describe, expect, it } from 'vitest';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import {
  LIENS_PREVIEW,
  dossierClient,
  liensPreview,
  retirerPreviewToiture,
} from '../scripts/retirer-preview-toiture.mjs';

const temporaires: string[] = [];

/** Un dossier de build factice : client/preview/{toiture*, diagnostic, index}. */
function buildFactice(): string {
  const racine = mkdtempSync(join(tmpdir(), 'acal332-'));
  temporaires.push(racine);
  const preview = join(racine, 'client', 'preview');
  for (const page of ['toiture', 'toiture-3d', 'toiture-3d-pro', 'toiture-3d-pro-11', 'diagnostic']) {
    mkdirSync(join(preview, page), { recursive: true });
    writeFileSync(join(preview, page, 'index.html'), `<html>${page}</html>`);
  }
  writeFileSync(join(preview, 'index.html'), '<html>index</html>');
  writeFileSync(join(racine, 'client', 'index.html'), '<html>accueil</html>');
  return racine;
}

afterEach(() => {
  while (temporaires.length) rmSync(temporaires.pop() as string, { recursive: true, force: true });
});

describe('retirerPreviewToiture', () => {
  it('supprime preview/toiture* d\'un dossier de build factice, conserve preview/diagnostic, est idempotent', async () => {
    const racine = buildFactice();
    const client = join(racine, 'client');

    const retirees = await retirerPreviewToiture(client);

    expect(retirees).toEqual(['toiture', 'toiture-3d', 'toiture-3d-pro', 'toiture-3d-pro-11']);
    for (const page of retirees) expect(existsSync(join(client, 'preview', page))).toBe(false);
    expect(existsSync(join(client, 'preview', 'diagnostic', 'index.html'))).toBe(true);
    expect(existsSync(join(client, 'preview', 'index.html'))).toBe(true);
    expect(existsSync(join(client, 'index.html'))).toBe(true);

    // Idempotent : un second passage ne retire rien et ne lève pas.
    expect(await retirerPreviewToiture(client)).toEqual([]);
  });

  it('accepte la racine dist/ comme le dossier client (le hook ne présume pas la forme de `dir`)', () => {
    const racine = buildFactice();
    expect(dossierClient(pathToFileURL(racine + '/'))).toBe(join(racine, 'client'));
    expect(dossierClient(join(racine, 'client'))).toBe(join(racine, 'client'));
  });

  it('sans dossier preview : rien à retirer', async () => {
    const racine = mkdtempSync(join(tmpdir(), 'acal332-vide-'));
    temporaires.push(racine);
    expect(await retirerPreviewToiture(racine)).toEqual([]);
  });
});

describe("l'index de preview n'expose les liens toiture qu'en dev", () => {
  it('rendu build : aucun lien toiture, diagnostic présent', () => {
    const hrefs = liensPreview(false).map((l) => l.href);
    expect(hrefs).toEqual(['/preview/diagnostic']);
  });

  it('rendu dev : les quatre générations, pro-11 mis en avant', () => {
    const liens = liensPreview(true);
    expect(liens.map((l) => l.href)).toEqual(LIENS_PREVIEW.map((l) => l.href));
    expect(liens.filter((l) => l.href.startsWith('/preview/toiture'))).toHaveLength(4);
    expect(liens.find((l) => l.featured)?.href).toBe('/preview/toiture-3d-pro-11');
  });

  it("la page rend la liste filtrée par import.meta.env.DEV (aucun lien écrit en dur)", () => {
    const page = readFileSync(
      fileURLToPath(new URL('../src/pages/preview/index.astro', import.meta.url)),
      'utf-8',
    );
    expect(page).toContain('liensPreview(import.meta.env.DEV)');
    expect(page).not.toContain('href="/preview/toiture');
  });
});

describe('le hook réel d\'astro.config.mjs', () => {
  it('la liste d\'intégrations porte le hook build:done qui retire preview/toiture*', async () => {
    const { default: config } = await import('../astro.config.mjs');
    const integration = (config.integrations ?? [])
      .flat()
      .find((i: { name?: string }) => i && i.name === 'taqinor:retirer-preview-toiture');
    expect(integration, 'hook ACAL332 absent de astro.config.mjs').toBeTruthy();
    const hook = integration.hooks['astro:build:done'];
    expect(typeof hook).toBe('function');

    const racine = buildFactice();
    await hook({ dir: pathToFileURL(join(racine, 'client') + '/') });
    expect(existsSync(join(racine, 'client', 'preview', 'toiture-3d-pro-11'))).toBe(false);
    expect(existsSync(join(racine, 'client', 'preview', 'diagnostic'))).toBe(true);
  });

  it('les sources des pages et du canonique roof-tool-pro11 restent en place', () => {
    for (const rel of [
      '../src/pages/preview/toiture.astro',
      '../src/pages/preview/toiture-3d.astro',
      '../src/pages/preview/toiture-3d-pro.astro',
      '../src/pages/preview/toiture-3d-pro-11.astro',
      '../src/scripts/roof-tool-pro11.ts',
    ]) {
      expect(existsSync(fileURLToPath(new URL(rel, import.meta.url))), rel).toBe(true);
    }
  });
});
