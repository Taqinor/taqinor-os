// ATST5 — la page /proposition RENDUE depuis les exemples figés du contrat, et
// chaque montant `formatMAD` affiché relu à sa valeur attendue.
//
// Avant : un seul test rendait un composant (`ChainePrix.astro`) ; les autres
// lisaient le source. Afficher la dépense actuelle à la place de l'économie
// nette an 1 (`SectionAgricole.astro`), ou faire ignorer l'option recommandée à
// la barre TTC collante, laissait les 337 tests apps/web verts.
//
// Ici la VRAIE page `[...token].astro` est rendue par `experimental_AstroContainer`
// (jeton plausible, `fetch` remplacé : il sert l'exemple du contrat). Chaque
// montant entier « 114 000 MAD » du HTML est lu avec l'ancre `data-*` qui le
// précède (son libellé voisin) et comparé à la valeur SERVIE écrite en dur
// ci-dessous — jamais recalculée par `src/lib`. Les sites `formatMAD(...)` du
// source qu'aucun exemple ne rend sont dans `NON_RENDUS`, liste qui ne fait que
// rétrécir : un site neuf doit être classé, un site disparu doit en sortir.
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('cloudflare:workers', () => ({ env: {} }));

import Page from '../src/pages/proposition/[...token].astro';

const ici = (chemin: string) => fileURLToPath(new URL(chemin, import.meta.url));
const contrat = JSON.parse(readFileSync(ici('../src/contract_samples/proposal_data.json'), 'utf-8'));
const JETON = 'Zx8kq2Lm9Pq4Rt6Vw1Yb3Nc5Df7Gh0Jk';

async function rendre(cle: string): Promise<string> {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(contrat[cle]), {
    status: 200, headers: { 'content-type': 'application/json' },
  })));
  const container = await AstroContainer.create({ astroConfig: { site: 'https://taqinor.ma' } } as never);
  return container.renderToString(Page, {
    params: { token: JETON },
    request: new Request(`https://taqinor.ma/proposition/${JETON}`),
  });
}

afterEach(() => vi.unstubAllGlobals());

const ANCRE = /data-(?!i18n\b|fr\b|en\b|ar\b)([a-z][a-z0-9-]*)(?:="([^"]*)")?/g;

/** « ancre:montant » de chaque montant entier `formatMAD` du HTML rendu (les
 *  montants au centime — `formatMADCentimes`, chaîne de prix — sont exclus). */
function montantsRendus(html: string): string[] {
  const s = html.replace(/<script\b[\s\S]*?<\/script>/gi, '')
    .replace(/<style\b[\s\S]*?<\/style>/gi, '').replace(/ data-astro-cid-\w+/g, '');
  const out: string[] = [];
  for (const t of s.matchAll(/>([^<>]+)</g)) {
    for (const m of t[1].matchAll(/(?<![\d,])(\d{1,3}(?:[   ]\d{3})*) MAD/g)) {
      const fin = t.index! + 1;
      const a = [...s.slice(Math.max(0, fin - 4000), fin).matchAll(ANCRE)].at(-1);
      out.push(`${a ? a[1] + (a[2] ? `=${a[2]}` : '') : '?'}:${m[1].replace(/[  ]/g, ' ')}`);
    }
  }
  return out;
}

const MOIS_SANS = ['820', '780', '900', '950', '1 020', '1 100', '1 180', '1 150', '1 000', '900', '830', '800'];
const MOIS_AVEC = ['1 100', '1 050', '1 200', '1 250', '1 320', '1 400', '1 480', '1 450', '1 300', '1 200', '1 120', '1 080'];

/** Valeurs SERVIES par le contrat (chemin en commentaire), écrites en dur. */
const ATTENDUS: Record<string, string[]> = {
  exemple: [
    'hero-ttc-value:114 000', // quote.totaux_avec.ttc — option recommandée (avec)
    'figure-option=avec:233 000', // gain_net_25_ans.avec_batterie
    'figure=facture_mensuelle_avant:1 450', 'figure-option=avec:550', // facture_sans_solaire ; annual_after / 12
    'figure-option=avec:17 400', 'figure-option=avec:6 600', // annual_before, annual_after
    ...MOIS_SANS.flatMap((v, i) => [`detail-eco-mois=${i}:${v}`, `detail-eco-mois-avec=${i}:${MOIS_AVEC[i]}`]),
    'detail-eco-total:11 430', 'detail-eco-total-avec-bloc:14 950', // economies_mensuelles.total_sans / total_avec
    'occ-eco:14 950', 'occ-eco:11 430',
    'track-section=options:78 000', 'figure-option=sans:114 000', // cartes d'options : totaux_sans / totaux_avec
    'batt-tier-panel:114 000',
    'gamme-carte=courante:114 000', 'gamme-carte=soeur:138 000', 'gamme-ecart:24 000', // gammes.soeur.total_ttc / ecart_ttc
    'gamme-choisir:98 000', // variants[0].total_ttc
    'sign-recap-ttc:114 000', 'sign-acompte-valeur:34 200', // acompte.montants.avec_batterie
    'option-label:78 000', 'option-label:114 000',
    'sticky-ttc:114 000', // barre collante = option recommandée, jamais totaux_sans (78 000)
  ],
  exemple_agricole: [
    'agri-ligne=depense-actuelle:32 871', // synthese_agricole.economies.depense_actuelle.annuelle_mad
    'agri-ligne=charges-solaires:600', // charges_solaires.total_mad_an
    'agri-ligne=economie-nette-an1:32 271', // economie.flux[1].flux_mad
    'agri-ligne=remplacement:18 000', // remplacements[0].montant_ttc_mad
    'ligne-id=90311:950', // options_kit[0].total_ttc
  ],
  exemple_commercial: [ // synthese_ci.argent.economie_annee1.total_mad / total_mad_ttc
    'hero-eco-value:98 933', 'figure=economie_annuelle:98 933', 'figure=economie_annuelle:118 717',
    'track-section=options:98 933',
  ],
  exemple_industriel: [],
  exemple_ci_deux_options: [
    'hero-eco-value:53 123', 'figure=economie_annuelle:53 123', 'figure=economie_annuelle:63 746',
    'ci-option-badge=principale:53 123',
    'ci-valeur-batterie=chiffree:95 767', // synthese_ci.option_batterie.valeur_chiffree.economie_annuelle_mad
    'ci-ligne=total_ttc:473 100', // option_totals.avec_batterie.ttc
    'ci-ligne=valeur:95 767',
  ],
};

/** Sites `formatMAD(` du source rendus par au moins un exemple ci-dessus. */
const COUVERTS = new Set([
  ...['storagePalierAtInitialN.coutTtc', 'montant', 'avec ? (s.economieAvecMad as number', 's.economieSansMad',
    'heroTtc', 'ecoHero', 'headline.gainNet', 'synthese.mensuelAvant', 'synthese.mensuelApres',
    'synthese.annuelAvant', 'synthese.annuelApres', 'ecoMensuelles.sans[i]', 'ecoMensuelles.avec[i]',
    'ecoMensuelles.totalSans', 'ecoMensuelles.totalAvec', 'optionTtc(data!, opt', 'eco',
    'battTierInitialClient.prix', 'gammes.courante.total_ttc', 'gammes.soeur.total_ttc', 'v.total_ttc',
    'optionTtc(data!, optionInitiale', 'stickyTtc ?? 0'].map((e) => `[...token].astro::${e}`),
  ...['argent.economies.depenseActuelleMadAn', 'argent.economies.chargesSolairesMadAn',
    'argent.economies.economieNetteAn1', 'r.montantTtc', 'o.totalTtc'].map((e) => `SectionAgricole.astro::${e}`),
  ...['ciEco', 'ciArgent.economieAnnee1.ttc'].map((e) => `SectionAutoconso.astro::${e}`),
]);

/** Sites qu'AUCUN exemple du contrat ne rend (liste qui ne fait que rétrécir). */
const NON_RENDUS = new Set([
  ...['avecTtc', 'sansTtc', 'x.prixTtc', 'x.economieAnnuelleMad', 'headline.monthly', 'headline.cumulative',
    'valeur', 'p.cumuleMad', 'battTierInitialClient.eco', 'va.prixTtc', 'va.prixParKwcTtc',
    'va.economieAnnuelleMad', 'va.economiesCumulees25AnsMad', 'tier.prix', 'tier.eco']
    .map((e) => `[...token].astro::${e}`),
  'SectionAutoconso.astro::ciInjection.valeurMadAn',
  ...['ciRent.vanMad', 'j.cumul', 'ciRent.jalonsTtc.find((x'].map((e) => `SectionRentabiliteIndustrielle.astro::${e}`),
]);

/** `fichier::expression` de chaque `formatMAD(` des `.astro` de la proposition. */
function sitesFormatMAD(): Set<string> {
  const racines = ['../src/pages/proposition/', '../src/components/proposition/'];
  const sites = new Set<string>();
  for (const racine of racines) {
    for (const rel of readdirSync(ici(racine), { recursive: true }) as string[]) {
      if (!rel.endsWith('.astro')) continue;
      const nom = rel.split(/[\\/]/).at(-1);
      const source = readFileSync(ici(racine + rel.replace(/\\/g, '/')), 'utf-8');
      for (const m of source.matchAll(/(?<![\w.])formatMAD\(([^)]*)/g)) sites.add(`${nom}::${m[1]}`);
    }
  }
  return sites;
}

describe('ATST5 — montants formatMAD de /proposition, page RENDUE', () => {
  for (const cle of Object.keys(ATTENDUS)) {
    it(`${cle} : chaque montant rendu vaut la valeur servie, à son libellé`, async () => {
      expect(montantsRendus(await rendre(cle))).toEqual(ATTENDUS[cle]);
    }, 60_000);
  }

  it('agricole : économie nette an 1 = 32 271 MAD, dépense actuelle = 32 871 MAD (jamais l’une pour l’autre)', async () => {
    const eco = contrat.exemple_agricole.synthese_agricole.economies;
    expect([eco.economie.flux[1].flux_mad, eco.depense_actuelle.annuelle_mad]).toEqual([32271.45, 32871.45]);
    const rendus = montantsRendus(await rendre('exemple_agricole'));
    expect(rendus).toContain('agri-ligne=economie-nette-an1:32 271');
    expect(rendus).toContain('agri-ligne=depense-actuelle:32 871');
  }, 60_000);

  it('barre TTC et héros d’`exemple` = option recommandée (114 000), pas totaux_sans (78 000)', async () => {
    expect([contrat.exemple.quote.totaux_avec.ttc, contrat.exemple.quote.totaux_sans.ttc]).toEqual([114000, 78000]);
    const rendus = montantsRendus(await rendre('exemple'));
    expect(rendus.filter((r) => /^(sticky-ttc|hero-ttc-value):/.test(r)))
      .toEqual(['hero-ttc-value:114 000', 'sticky-ttc:114 000']);
  }, 60_000);

  it('chaque site formatMAD du source est rendu par un exemple ou listé dans NON_RENDUS', () => {
    const sites = sitesFormatMAD();
    expect([...sites].filter((s) => !COUVERTS.has(s) && !NON_RENDUS.has(s))).toEqual([]);
    expect([...NON_RENDUS].filter((s) => !sites.has(s))).toEqual([]); // liste qui ne fait que rétrécir
    expect([...COUVERTS].filter((s) => !sites.has(s) || NON_RENDUS.has(s))).toEqual([]);
  });
});
