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
  { file: '../src/pages/en/résidentiel.astro', phrase: 'Your bill already knows the size of your installation' },
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

// CPRW8 (27/10/2026) — /professionnel (FR) : promesses retirées, CTA du héros avec le mode, tuile sans chiffre.
describe('CPRW8 — professionnel.astro : plus de promesse invérifiable', () => {
  const SRC = read('../src/pages/professionnel.astro');
  it('hangar agro-industriel : fait vérifiable (aucune surface au sol utilisée)', () => {
    expect(SRC).not.toContain('la toiture existante finance la structure');
    expect(SRC).not.toContain('ne coûte rien de plus à exploiter');
    expect(SRC).toContain('Aucune surface au sol utilisée');
  });
  it('collectivités : plus de continuité de service, aucune promesse de couverture totale', () => {
    expect(SRC).not.toMatch(/continuité/i);
    expect(SRC).not.toContain('ne tolère pas la coupure');
    expect(SRC).toContain('qui prennent le relais le soir et la nuit');
    expect(SRC).not.toContain('la batterie couvre');
  });
  it('tous les CTA vers le tunnel portent ?mode=', () => {
    const liens = SRC.match(/href="\/devis\/mon-toit[^"]*"/g) ?? [];
    expect(liens.length).toBeGreaterThanOrEqual(3);
    for (const l of liens) expect(l).toMatch(/\?mode=(industriel|commercial)/);
  });
  it('héros : plus de tuile « 5 MW — Seuil d\'autorisation », un fait du parcours à la place', () => {
    expect(SRC).not.toContain('data-tally>5 MW');
    expect(SRC).not.toContain("Seuil d'autorisation");
    expect(SRC).toContain('Étude heure par heure');
  });
});

// CPRW12 (27/10/2026) — variantes EN/AR de /professionnel alignées sur le FR (CPRW8).
describe('CPRW12 — professionnel EN/AR : mêmes retraits que le FR', () => {
  for (const [lang, file] of [['en', '../src/pages/en/professionnel.astro'], ['ar', '../src/pages/ar/professionnel.astro']] as const) {
    const SRC = read(file);
    it(`${lang} : plus de continuité de service, de toiture qui finance ni de tuile « 5 MW » en héros`, () => {
      expect(SRC).not.toMatch(/continuity|استمرارية|tolerates no outage|لا يتحمّل الانقطاع/);
      expect(SRC).not.toMatch(/funds the structure|يموّل الهيكل|costs nothing extra|لا يكلّف شيئاً إضافياً/);
      expect(SRC).not.toMatch(/data-tally>5 MW/);
    });
    it(`${lang} : CTA du héros avec ?mode=industriel et tuile « étude heure par heure »`, () => {
      const liens = SRC.match(/\/devis\/mon-toit'\)\}[^"]*"/g) ?? [];
      expect(liens.length).toBeGreaterThanOrEqual(3);
      for (const l of liens) expect(l).toMatch(/\?mode=(industriel|commercial)/);
      expect(SRC).toContain(lang === 'en' ? 'Hour-by-hour study' : 'دراسة ساعة بساعة');
      expect(SRC).toContain(lang === 'en' ? 'From your consumption' : 'انطلاقاً من استهلاككم');
    });
  }
});

// ── CPRW20 — /professionnel : segments Collectivités sans promesse 10 ans, CTA par mode, titres h3 ──
describe('CPRW20 — /professionnel : sources des 3 pages', () => {
  const PAGES20 = ['../src/pages/professionnel.astro', '../src/pages/en/professionnel.astro', '../src/pages/ar/professionnel.astro'];
  for (const rel of PAGES20) {
    const src = read(rel);
    it(`${rel} — la ligne Collectivités ne promet aucune durée de 10 ans`, () => {
      const bloc = src.slice(src.indexOf("n: '04'"), src.indexOf('];', src.indexOf("n: '04'")));
      const proof = /proof: '([^']*)'/.exec(bloc)![1]!;
      expect(proof).not.toMatch(/10\s*(ans|years)/);
      expect(proof).not.toContain('10 سنوات');
      expect(proof).not.toMatch(/\d/);
    });
    it(`${rel} — chaque segment pointe son CTA vers son mode ; titres en h3 ; plus de commentaire périmé`, () => {
      expect(src).toMatch(/n: '01', mode: 'industriel'/);
      expect(src).toMatch(/n: '02', mode: 'industriel'/);
      expect(src).toMatch(/n: '03', mode: 'commercial'/);
      expect(src).toMatch(/n: '04', mode: 'commercial'/);
      expect(src).toContain('data-segment-cta');
      expect(src).toContain('<h3 class="display mt-2 text-xl text-white">{s.title}</h3>');
      expect(src).not.toContain('<h2 class="display mt-2 text-xl text-white">{s.title}</h2>');
      const tete = src.slice(0, src.indexOf('---', 4));
      for (const vieux of ['17,04', '3,72', 'ref. 468', '3–5']) expect(tete).not.toContain(vieux);
    });
  }
});
