// ATOT34 — la chaîne de prix de /proposition, lue sur le HTML RENDU.
//
// `ChainePrix.astro` est rendu par `experimental_AstroContainer` (Astro 7) avec
// les totaux du contrat (ATOT26) et ceux de DEV-202609-0005 (V2 : Sous-total
// 61 512,58, arrondi 35,31, Total HT 61 477,27, sans remise). On lit les
// `data-figure` du HTML produit et on vérifie les deux égalités au centime :
//   Sous-total − Remise − Arrondi = Total HT   et   Total HT + TVA = Total TTC.
// Une ligne d'arrondi retirée du composant rend le premier test ROUGE
// (test-du-test).
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { describe, expect, it } from 'vitest';
import ChainePrix from '../src/components/proposition/ChainePrix.astro';
import { formatMADCentimes } from '../src/lib/proposition';

type Totaux = {
  ht_brut: number;
  remise: number;
  arrondi: number;
  ht_net: number;
  tva: number;
  ttc: number;
};

const contrat = JSON.parse(
  readFileSync(fileURLToPath(new URL('../src/contract_samples/proposal_data.json', import.meta.url)), 'utf-8'),
);

// DEV-202609-0005 (sonde V2) : Total HT 61 477,27 + TVA 20 % = TTC 73 772,72.
const DEV_0005: Totaux = {
  ht_brut: 61512.58, remise: 0, arrondi: 35.31, ht_net: 61477.27, tva: 12295.45, ttc: 73772.72,
};

async function rendre(totaux: Totaux, option = 'sans'): Promise<string> {
  const container = await AstroContainer.create();
  return container.renderToString(ChainePrix, { props: { totaux, option } });
}

/** « 61 512,58 MAD » / « −35,31 MAD » → nombre (centimes exacts). */
function montant(texte: string): number {
  const m = texte.replace(/[\s  ]/g, '').match(/([-−–]?)(\d+)(?:,(\d+))?MAD/);
  if (!m) throw new Error(`montant illisible : ${texte}`);
  const v = Number(`${m[2]}.${m[3] ?? '0'}`);
  return m[1] ? -v : v;
}

/** Les `data-figure` du HTML rendu → { cle: nombre }. */
function figures(html: string): Record<string, number> {
  const out: Record<string, number> = {};
  const re = /<dd[^>]*data-figure="([a-z_]+)"[^>]*>([^<]*)<\/dd>/g;
  for (const m of html.matchAll(re)) out[m[1]] = montant(m[2]);
  return out;
}

const centimes = (n: number) => Math.round(n * 100);

function verifierChaine(f: Record<string, number>) {
  const remise = f.remise ?? 0;
  const arrondi = f.arrondi ?? 0;
  expect(centimes(Math.abs(remise))).toBe(centimes(remise < 0 ? -remise : remise));
  // Remise et arrondi sont affichés « −x » : on compare en valeur absolue.
  expect(centimes(f.sous_total_ht - Math.abs(remise) - Math.abs(arrondi))).toBe(centimes(f.total_ht));
  expect(centimes(f.total_ht + f.tva)).toBe(centimes(f.total_ttc));
}

describe('ATOT34 — chaîne de prix rendue (ChainePrix.astro)', () => {
  it('DEV-202609-0005 : ligne « Arrondi commercial −35,31 » entre la remise et le Total HT', async () => {
    const html = await rendre(DEV_0005);
    expect(html).toContain('Arrondi commercial');
    const f = figures(html);
    expect(Math.abs(f.arrondi)).toBeCloseTo(35.31, 2);
    // ordre : Sous-total, (Remise), Arrondi, Total HT, TVA, TTC
    const ordre = [...html.matchAll(/data-figure="([a-z_]+)"/g)].map((m) => m[1]);
    expect(ordre).toEqual(['sous_total_ht', 'arrondi', 'total_ht', 'tva', 'total_ttc']);
    verifierChaine(f);
  });

  it('les montants s’affichent au centime (plus d’arrondi au dirham étage par étage)', async () => {
    const f = figures(await rendre(DEV_0005));
    expect(f.sous_total_ht).toBe(61512.58);
    expect(f.total_ht).toBe(61477.27);
    expect(formatMADCentimes(61512.58)).toBe('61 512,58 MAD');
  });

  it('les deux options du contrat (remise 1 450 + arrondi 50 ; arrondi 75) s’additionnent', async () => {
    const quote = contrat.exemple.quote;
    for (const [cle, option] of [['totaux_sans', 'sans'], ['totaux_avec', 'avec']] as const) {
      const t = quote[cle];
      const html = await rendre(
        { ht_brut: t.ht_brut, remise: t.remise, arrondi: t.arrondi, ht_net: t.ht_net, tva: t.tva, ttc: t.ttc },
        option,
      );
      expect(html).toContain(`data-figure-option="${option}"`);
      verifierChaine(figures(html));
    }
  });

  it('remise et arrondi nuls : ni l’une ni l’autre de ces lignes n’est rendue', async () => {
    const html = await rendre({ ht_brut: 1000, remise: 0, arrondi: 0, ht_net: 1000, tva: 200, ttc: 1200 });
    const f = figures(html);
    expect(Object.keys(f)).toEqual(['sous_total_ht', 'total_ht', 'tva', 'total_ttc']);
    verifierChaine(f);
  });

  it('aucune clé de coût interne dans le HTML rendu ni dans la charge utile du contrat', async () => {
    const html = await rendre(DEV_0005);
    expect(html).not.toMatch(/prix_achat|marge|revendeur/i);
    expect(JSON.stringify(contrat.exemple)).not.toMatch(/prix_achat|"marge"|revendeur/i);
  });

  it('la page n’imprime plus la chaîne en ligne : seul ChainePrix la rend', () => {
    const page = readFileSync(
      fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)), 'utf-8');
    expect(page).toContain('<ChainePrix');
    expect(page).not.toContain('data-figure="sous_total_ht"');
  });
});
