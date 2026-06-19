// W67 — gardes SOURCE des 3 pages de segment portées en EN + AR
// (résidentiel, professionnel, marocains-du-monde). Pour chacun des 6 nouveaux
// fichiers : il importe le Layout partagé, n'est jamais noindex, ne contient
// aucun « témoignage » (zéro faux avis), localise ses liens internes via
// localizeNavHref (jamais de lien mort), et porte une phrase traduite
// distinctive (anglais sous en/, arabe sous ar/) — preuve que le français a
// bien été traduit et non recopié.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

// Chaque cas : fichier source + une phrase traduite distinctive à y trouver.
const EN_PAGES = [
  { file: '../src/pages/en/résidentiel.astro', phrase: 'A villa, its bill, its roof: three data points, one sizing' },
  { file: '../src/pages/en/professionnel.astro', phrase: 'Your electricity cost line — you can steer it instead of enduring it' },
  { file: '../src/pages/en/marocains-du-monde.astro', phrase: 'Are you a Moroccan living abroad?' },
] as const;

const AR_PAGES = [
  { file: '../src/pages/ar/résidentiel.astro', phrase: 'فيلا، فاتورتها، سطحها: ثلاث معطيات، تحديد مقاس واحد' },
  { file: '../src/pages/ar/professionnel.astro', phrase: 'بند الكهرباء عندك، يمكنك قيادته بدل أن تخضع له' },
  { file: '../src/pages/ar/marocains-du-monde.astro', phrase: 'هل أنت مغربي·ة بالخارج؟' },
] as const;

const ALL = [...EN_PAGES, ...AR_PAGES];

describe('W67 — segments résidentiel/professionnel/marocains-du-monde en EN + AR', () => {
  it.each(ALL.map((p) => p.file))('%s importe le Layout partagé', (file) => {
    const src = read(file);
    expect(src).toContain("import Layout from '../../layouts/Layout.astro'");
  });

  it.each(ALL.map((p) => p.file))('%s est INDEXABLE (aucun noindex)', (file) => {
    expect(read(file).toLowerCase()).not.toContain('noindex');
  });

  it.each(ALL.map((p) => p.file))('%s ne contient AUCUN « témoignage » (zéro faux avis)', (file) => {
    expect(read(file).toLowerCase()).not.toContain('témoignage');
  });

  it.each(ALL.map((p) => p.file))('%s localise ses liens via localizeNavHref (jamais de lien mort)', (file) => {
    const src = read(file);
    expect(src).toContain('localizeNavHref');
    expect(src).toContain('getLocaleFromPath');
  });

  it.each(EN_PAGES.map((p) => [p.file, p.phrase] as const))(
    '%s porte une phrase ANGLAISE distinctive (FR traduit, pas recopié)',
    (file, phrase) => {
      expect(read(file)).toContain(phrase);
    },
  );

  it.each(AR_PAGES.map((p) => [p.file, p.phrase] as const))(
    '%s porte une phrase ARABE distinctive (FR traduit, pas recopié)',
    (file, phrase) => {
      expect(read(file)).toContain(phrase);
    },
  );
});
