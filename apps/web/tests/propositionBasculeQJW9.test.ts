// @vitest-environment jsdom
//
// QJW9 — LA BASCULE : l'îlot de `pages/proposition/[...token].astro` n'a plus
// de câblage, il ORCHESTRE les tables (QJW7) via le moteur (QJW8).
//
// CE QUE CE FICHIER VÉRIFIE, EN DEUX TEMPS.
//
//  (1) LA SOURCE — que les quatre fonctions câblées à la main ont bien
//      DISPARU (`appliquerChampHero`, `peindreCumulAnnuel`, les corps de
//      `restaurerDetail`/`appliquerDetail`/`marquerChargement`), et avec elles
//      les ~50 constantes de nœuds : c'est l'idiome de la maison pour un îlot
//      `<script>` Astro, que vitest ne peut pas monter tel quel.
//
//  (2) LE COMPORTEMENT — un aller-retour Recommandé → Éco → Max → Recommandé
//      joué sur la VRAIE structure de nœuds, avec les VRAIES tables, le VRAI
//      moteur et le détail de l'ÉCHANTILLON DE CONTRAT. C'est la substance de
//      la « vérification en navigateur » exigée par la tâche : que les sept
//      champs de tête et les six chapitres profonds suivent la carte cliquée,
//      et que le retour sur Recommandé rende la page IDENTIQUE À L'OCTET.
//
// CE QUE CE FICHIER NE REMPLACE PAS. Un vrai clic dans un vrai navigateur sur
// une vraie proposition : la page exige un backend Django joignable (elle
// `fetch` `proposalEndpoint(API_BASE, token)` et n'a AUCUN chemin de fixture
// local — vérifié). Ce test reproduit la mécanique de swap, pas le rendu
// serveur ni la mise en page.
import { beforeEach, describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import echantillon from '../src/contract_samples/taille_detail.json';
import {
  HERO,
  PROFONDS,
  liaisonsHero,
  type ContexteHero,
} from '../src/lib/proposition/liaisons';
import {
  appliquer,
  capturerOriginaux,
  marquerChargement,
  restaurer,
} from '../src/lib/proposition/swap';
import { tailleDetail, type TailleDetail } from '../src/lib/tailleDetail';

const SOURCE = readFileSync(join(process.cwd(), 'src/pages/proposition/[...token].astro'), 'utf-8');

/**
 * L'ÎLOT SEUL — à partir de `setupTaillesOffres`. Les assertions d'absence
 * doivent porter sur la région de swap, pas sur la page entière : le
 * frontmatter Astro a ses propres helpers de rendu serveur qui portent
 * légitimement des noms voisins (`const ecoBloc = (profil, variante) => …`,
 * un constructeur de blocs SSR qui n'a rien à voir avec le nœud du même nom).
 */
const ILOT = SOURCE.slice(SOURCE.indexOf('function setupTaillesOffres'));

const ECH = echantillon as unknown as { exemple: unknown; exemple_avec_batterie: unknown };
const DETAIL_ECO = tailleDetail(ECH.exemple) as TailleDetail;
const DETAIL_MAX = tailleDetail(ECH.exemple_avec_batterie) as TailleDetail;

// ── (1) LA SOURCE ───────────────────────────────────────────────────────────

describe('QJW9 — le câblage à la main a disparu de l’îlot', () => {
  it('les quatre fonctions câblées ne sont plus définies dans la page', () => {
    // `appliquerChampHero` portait la copie champ par champ du héros ;
    // `peindreCumulAnnuel` reconstruisait le tableau année par année.
    expect(SOURCE).not.toContain('appliquerChampHero');
    expect(SOURCE).not.toContain('peindreCumulAnnuel');
    expect(SOURCE).not.toContain('texteDeLaCarteSelectionnee');
    // `marquerChargement` n'est plus DÉFINI ici : il est importé du moteur.
    expect(SOURCE).not.toContain('function marquerChargement(');
  });

  it('la région de swap tient en une orchestration courte, pas en ~500 lignes de câblage', () => {
    const debut = ILOT.indexOf('LA RÉGION DE SWAP, DÉSORMAIS DÉCLARATIVE');
    const fin = ILOT.indexOf('async function chargerDetail');
    expect(debut).toBeGreaterThan(-1);
    expect(fin).toBeGreaterThan(debut);
    const region = ILOT.slice(debut, fin).split('\n');
    const codeSeul = region.filter((l) => {
      const t = l.trim();
      return t.length > 0 && !t.startsWith('//') && !t.startsWith('*') && !t.startsWith('/*');
    });
    expect(codeSeul.length).toBeLessThanOrEqual(60);
  });

  it('les ~50 constantes de nœuds du swap sont parties : plus une seule ne subsiste', () => {
    for (const constante of [
      'const heroTtcCard', 'const heroTtcValue', 'const heroEcoCard', 'const heroEcoValue',
      'const heroKwcItem', 'const heroKwcValue', 'const heroPanneauxItem',
      'const heroPanneauxValue', 'const heroProductionCard', 'const heroProductionValue',
      'const heroEcoAnnualCard', 'const heroEcoAnnualValue', 'const heroCouvertureCard',
      'const heroTtcOriginal', 'const heroEcoOriginal', 'const heroKwcOriginal',
      'const heroPanneauxOriginal', 'const heroProductionOriginal', 'const heroEcoAnnualOriginal',
      'const ecoMoisSans', 'const ecoMoisAvec', 'const ecoTotal', 'const ecoTotalAvec',
      'const ecoBanque', 'const ecoBloc', 'const couvArc', 'const couvValue',
      'const cumulCard', 'const cumulValue', 'const paybackCard', 'const paybackValue',
      'const cumulAnnuelBloc', 'const cumulAnnuelCorps',
    ]) {
      expect(ILOT.includes(constante), `constante encore présente dans l’îlot : ${constante}`).toBe(false);
    }
  });

  it('l’îlot importe les tables et le moteur, et alias `appliquer` (il a déjà le sien)', () => {
    expect(SOURCE).toContain("from '../../lib/proposition/liaisons'");
    expect(SOURCE).toContain("from '../../lib/proposition/swap'");
    expect(SOURCE).toContain('appliquer as appliquerLiaisons');
    expect(SOURCE).toContain('appliquerLiaisons(PROFONDS, detail)');
    expect(SOURCE).toContain('restaurer(PROFONDS, originauxProfonds)');
    expect(SOURCE).toContain('marquerChargement(PROFONDS, true)');
    expect(SOURCE).toContain('marquerChargement(PROFONDS, false)');
  });

  it('`chargerDetail` et `appliquer` gardent leur rôle d’orchestration', () => {
    expect(SOURCE).toContain('async function chargerDetail(): Promise<void>');
    expect(SOURCE).toContain('function appliquer(): void');
    expect(SOURCE).toContain('void chargerDetail();');
  });

  it('les régions WJ128 du simulateur batterie ne sont pas touchées', () => {
    expect(SOURCE).toContain('const batteryCapacityKnown =');
    expect(SOURCE).toContain('id="battery-sim-units"');
  });
});

// ── (2) LE COMPORTEMENT ─────────────────────────────────────────────────────

/** Les textes que le SERVEUR a rendus pour le devis officiel (« Recommandé »). */
const SSR = {
  ttc: '150 000 MAD',
  eco: '18 000 MAD',
  payback: '6,5 ans',
  kwc: '12 kWc',
  panneaux: '22',
  production: '19 000 kWh',
  ecoAnnuelle: '18 000 MAD',
};

/** Ce que la carte « Éco » a rendu, côté serveur, dans la variante « sans ». */
const CARTE_ECO = {
  ttc: '71 400 MAD',
  eco: '9 840 MAD',
  payback: '7,3 ans',
  kwc: '7,7 kWc',
  panneaux: '14',
  production: '12 180 kWh',
};

/** La carte « Max » ne rend PAS de production : ce champ doit disparaître. */
const CARTE_MAX = {
  ttc: '227 600 MAD',
  eco: '23 040 MAD',
  payback: '9,9 ans',
  kwc: '18,7 kWc',
  panneaux: '34',
};

function carteHtml(cle: string, v: Record<string, string>): string {
  const champ = (attr: string, val: string | undefined) =>
    val === undefined ? '' : `<dd ${attr}>${val}</dd>`;
  return `
    <article data-taille-carte data-taille-cle="${cle}">
      <div data-taille-bloc data-taille-variante="sans">
        ${champ('data-taille-ttc-value', v.ttc)}
        ${champ('data-taille-eco-value', v.eco)}
        ${champ('data-taille-payback-value', v.payback)}
        ${champ('data-taille-kwc-value', v.kwc)}
        ${champ('data-taille-panneaux-value', v.panneaux)}
        ${champ('data-taille-production-value', v.production)}
      </div>
    </article>`;
}

function pageHtml(kind: 'eco' | 'payback'): string {
  return `
  <div data-hero-ttc-card><span data-hero-ttc-value>${SSR.ttc}</span></div>
  <div data-hero-eco-card data-hero-eco-kind="${kind}">
    <span data-hero-eco-value>${kind === 'payback' ? SSR.payback : SSR.eco}</span>
    <p data-hero-eco-sub>1 500 MAD / mois</p>
  </div>
  <li data-hero-kwc-item><span data-hero-kwc-value>${SSR.kwc}</span></li>
  <span data-hero-legend-sep>·</span>
  <li data-hero-panneaux-item><span data-hero-panneaux-value>${SSR.panneaux}</span></li>
  <div data-hero-production-card><span data-hero-production-value>${SSR.production}</span></div>
  <div data-hero-eco-annual-card><span data-hero-eco-annual-value>${SSR.ecoAnnuelle}</span></div>
  <div data-hero-couverture-card>
    <svg><circle data-detail-couverture-arc data-detail-donut-r="50" stroke-dasharray="200.00 114.16"></circle></svg>
    <text data-detail-couverture-value>62%</text>
  </div>
  <div data-detail-eco-bloc>
    ${Array.from({ length: 12 }, (_, i) => `<p data-detail-eco-mois>${1000 + i} MAD</p><p data-detail-eco-mois-avec>${2000 + i} MAD</p>`).join('')}
    <span data-detail-eco-total>13 000 MAD</span>
    <span data-detail-eco-total-avec-bloc>26 000 MAD</span>
    <p data-detail-banque hidden></p>
    <p data-detail-echec hidden><button data-detail-retry>Réessayer</button></p>
  </div>
  <div data-detail-cumul-card><span data-detail-cumul-value>300 000 MAD</span></div>
  <div data-detail-payback-card><span data-detail-payback-value>6,5 ans</span></div>
  <div data-cumul-annuel><table><tbody><tr><td>1</td><td>-80 000 MAD</td></tr></tbody></table></div>
  <section data-tailles>
    ${carteHtml('recommande', { ttc: SSR.ttc, eco: SSR.eco, payback: SSR.payback, kwc: SSR.kwc, panneaux: SSR.panneaux, production: SSR.production })}
    ${carteHtml('eco', CARTE_ECO)}
    ${carteHtml('max', CARTE_MAX)}
  </section>`;
}

/**
 * Le MÊME enchaînement que l'îlot après la bascule : `synchroniserDetailPage`
 * (restaurer sur le défaut, sinon appliquer les liaisons de tête) puis
 * `chargerDetail` (restaurer sur le défaut, sinon marquer/appliquer/démarquer).
 */
function creerPage(kind: 'eco' | 'payback') {
  document.body.innerHTML = pageHtml(kind);
  const liaisonsTete = liaisonsHero(kind);
  const originauxHero = capturerOriginaux(liaisonsTete);
  const originauxProfonds = capturerOriginaux(PROFONDS);
  const ecoEchec = document.querySelector<HTMLElement>('[data-detail-echec]');
  const heroEcoSub = document.querySelector<HTMLElement>('[data-hero-eco-sub]');
  const heroLegendSep = document.querySelector<HTMLElement>('[data-hero-legend-sep]');
  const enveloppeHeroVisible = (cleHero: string): boolean => {
    const h = HERO.find((x) => x.cle === cleHero);
    const el = h ? document.querySelector<HTMLElement>(h.enveloppe) : null;
    return !!el && !el.hidden;
  };

  return {
    cliquer(cle: string, detail: TailleDetail | null): void {
      const surLeDefaut = cle === 'recommande';
      const contexte: ContexteHero = {
        texteCarte(selecteur: string): string | null {
          const carte = Array.from(document.querySelectorAll<HTMLElement>('[data-taille-carte]'))
            .find((c) => c.dataset.tailleCle === cle);
          const bloc = carte?.querySelector<HTMLElement>('[data-taille-bloc][data-taille-variante="sans"]');
          const noeud = bloc?.querySelector<HTMLElement>(selecteur);
          return noeud ? noeud.textContent : null;
        },
      };
      if (surLeDefaut) restaurer(liaisonsTete, originauxHero);
      else appliquer(liaisonsTete, contexte);
      if (heroEcoSub) heroEcoSub.hidden = !surLeDefaut;
      if (heroLegendSep) {
        heroLegendSep.hidden = !(enveloppeHeroVisible('kwc') && enveloppeHeroVisible('panneaux'));
      }
      if (surLeDefaut) {
        restaurer(PROFONDS, originauxProfonds);
        if (ecoEchec) ecoEchec.hidden = true;
        return;
      }
      marquerChargement(PROFONDS, true);
      marquerChargement(PROFONDS, false);
      if (ecoEchec) ecoEchec.hidden = detail !== null;
      appliquer(PROFONDS, detail);
    },
  };
}

const txt = (sel: string) => document.querySelector(sel)!.textContent;
const cache = (sel: string) => document.querySelector<HTMLElement>(sel)!.hidden;

describe('QJW9 — Éco / Recommandé / Max échangent les SEPT champs de tête et les SIX chapitres profonds', () => {
  let page: ReturnType<typeof creerPage>;
  let auChargement: string;

  beforeEach(() => {
    page = creerPage('eco');
    auChargement = document.body.innerHTML;
  });

  it('cliquer « Éco » remplace les six champs de tête actifs par CEUX DE SA CARTE', () => {
    page.cliquer('eco', DETAIL_ECO);
    expect(txt('[data-hero-ttc-value]')).toBe(CARTE_ECO.ttc);
    expect(txt('[data-hero-eco-value]')).toBe(CARTE_ECO.eco);
    expect(txt('[data-hero-kwc-value]')).toBe(CARTE_ECO.kwc);
    expect(txt('[data-hero-panneaux-value]')).toBe(CARTE_ECO.panneaux);
    expect(txt('[data-hero-production-value]')).toBe(CARTE_ECO.production);
    expect(txt('[data-hero-eco-annual-value]')).toBe(CARTE_ECO.eco);
    // La ligne MAD/mois est du texte traduit qu'aucune carte ne sert.
    expect(cache('[data-hero-eco-sub]')).toBe(true);
  });

  it('cliquer « Éco » charge les six chapitres PROFONDS depuis le contrat servi', () => {
    page.cliquer('eco', DETAIL_ECO);
    expect(txt('[data-detail-eco-total]')).toBe('9 940 MAD');
    expect(document.querySelectorAll('[data-detail-eco-mois]')[0]!.textContent).toBe('640 MAD');
    expect(txt('[data-detail-couverture-value]')).toBe('48 %');
    expect(txt('[data-detail-cumul-value]')).toBe('231 400 MAD');
    expect(txt('[data-detail-payback-value]')).toBe('7,3 ans');
    expect(document.querySelectorAll('[data-cumul-annuel] tbody tr')).toHaveLength(5);
    // Éco n'a pas de banque : le chapitre disparaît, il n'emprunte rien.
    expect(cache('[data-detail-banque]')).toBe(true);
  });

  it('cliquer « Max » : un champ que SA carte ne sert pas DISPARAÎT — jamais le chiffre du devis à sa place', () => {
    page.cliquer('max', DETAIL_MAX);
    expect(txt('[data-hero-ttc-value]')).toBe(CARTE_MAX.ttc);
    // La carte Max ne rend pas de production : l'enveloppe est masquée, et le
    // nœud garde SON texte, masqué — jamais réécrit avec celui du devis.
    expect(cache('[data-hero-production-card]')).toBe(true);
    expect(txt('[data-hero-production-value]')).toBe(SSR.production);
    // Et le tableau année par année, que le détail Max ne sert pas, disparaît
    // au lieu d'afficher la série du Recommandé (l'incident F2).
    expect(cache('[data-cumul-annuel]')).toBe(true);
    expect(txt('[data-detail-banque]')).toBe('Batterie · 6 × 5 kWh · 27 kWh utiles');
    expect(cache('[data-detail-banque]')).toBe(false);
  });

  it('revenir sur « Recommandé » restaure la page À L’OCTET (aller-retour simple)', () => {
    page.cliquer('eco', DETAIL_ECO);
    page.cliquer('recommande', null);
    expect(document.body.innerHTML).toBe(auChargement);
  });

  it('revenir sur « Recommandé » restaure la page À L’OCTET (les trois offres, aller et retour)', () => {
    page.cliquer('eco', DETAIL_ECO);
    page.cliquer('max', DETAIL_MAX);
    page.cliquer('eco', DETAIL_ECO);
    page.cliquer('recommande', null);
    expect(document.body.innerHTML).toBe(auChargement);
  });

  it('un échec réseau sur une autre offre puis retour : la page revient AUSSI à l’octet', () => {
    page.cliquer('eco', null);
    expect(cache('[data-detail-echec]')).toBe(false);
    expect(cache('[data-detail-eco-bloc]')).toBe(false);
    expect(Array.from(document.querySelectorAll<HTMLElement>('[data-detail-eco-mois]')).every((n) => n.hidden)).toBe(true);
    page.cliquer('recommande', null);
    expect(document.body.innerHTML).toBe(auChargement);
  });

  it('le séparateur de légende ne survit que si kWc ET panneaux sont visibles', () => {
    page.cliquer('eco', DETAIL_ECO);
    expect(cache('[data-hero-legend-sep]')).toBe(false);
    // Une carte qui ne sert ni kWc ni panneaux fait tomber les deux items…
    document.querySelector('[data-taille-cle="max"] [data-taille-kwc-value]')!.remove();
    document.querySelector('[data-taille-cle="max"] [data-taille-panneaux-value]')!.remove();
    page.cliquer('max', DETAIL_MAX);
    expect(cache('[data-hero-kwc-item]')).toBe(true);
    expect(cache('[data-hero-panneaux-item]')).toBe(true);
    expect(cache('[data-hero-legend-sep]')).toBe(true);
  });
});

describe('QJW9 — la SEPTIÈME ligne de tête : le créneau rendu en PAYBACK', () => {
  it('lit le payback de la carte, jamais son économie — et revient à l’octet', () => {
    const page = creerPage('payback');
    const auChargement = document.body.innerHTML;
    page.cliquer('eco', DETAIL_ECO);
    expect(txt('[data-hero-eco-value]')).toBe(CARTE_ECO.payback);
    // Le bandeau « Économie estimée / an », lui, reste sur l'économie.
    expect(txt('[data-hero-eco-annual-value]')).toBe(CARTE_ECO.eco);
    page.cliquer('recommande', null);
    expect(document.body.innerHTML).toBe(auChargement);
  });
});
