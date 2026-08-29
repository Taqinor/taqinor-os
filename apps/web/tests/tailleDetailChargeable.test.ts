/**
 * OPTIONS CHARGEABLES (ordre fondateur, 29/08/2026) — « i want the 3 options
 * to be LOADABLE in the webpage if client clicks on one of them », et « when
 * only ONE option is sent, the info-dense card must NOT disappear ».
 *
 * DEUX NIVEAUX, DÉLIBÉRÉMENT.
 *  1. `lib/tailleDetail.ts` est du code PUR : il s'exécute pour de vrai ici
 *     (lecture du contrat, omission champ par champ, clés de cache, URLs,
 *     longueur d'arc). C'est là que vivent les décisions, donc c'est là que
 *     vivent les vrais tests.
 *  2. L'îlot `<script>` de la page ne se teste, dans cette maison, que par
 *     assertions de chaîne sur la source `.astro` (même idiome que
 *     `offresTaillesTAILLES.test.ts`) : on y vérifie le CÂBLAGE — le fetch, le
 *     cache, l'état de chargement, le repli, la restauration — et la carte
 *     récapitulative mono-option.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  TAILLES_CHARGEABLES, arcDonut, cleCacheDetail, dasharrayDonut,
  detailProxyUrl, estChargeable, tailleDetail, tailleDetailEndpoint,
} from '../src/lib/tailleDetail';

const read = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const PAGE = read('../src/pages/proposition/[...token].astro').replace(/\r\n/g, '\n');
/** Le code SEUL : un commentaire ne doit jamais faire passer une assertion. */
const CODE = PAGE
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');

const PROXY = read('../src/pages/api/proposition-taille.ts');

const SERVI = {
  cle: 'eco',
  titre: 'Éco',
  variante: 'sans',
  est_le_devis: false,
  carte: {
    nb_panneaux: 14,
    puissance_kwc: 7.7,
    prix_ttc: 71400,
    economie_annuelle_mad: 9840,
    payback_annees: 7.26,
    couverture_pct: 48.2,
    production_annuelle_kwh: 12180,
    economies_cumulees_25_ans_mad: 231400,
  },
  economies_mensuelles: {
    valeurs: [640, 690, 810, 870, 930, 980, 1010, 990, 900, 800, 690, 630],
    total: 9940,
    devise: 'MAD',
  },
  cashflow: { cumulative: [-61560, -51720], horizon_annees: 25, escalade_tarifaire_pct: 0 },
};

// ── 1. QUELLE TAILLE SE CHARGE ─────────────────────────────────────────────

describe('quelles tailles sont chargeables', () => {
  it('« Recommandé » n’en est PAS une : c’est le devis, la page le restaure', () => {
    expect(estChargeable('recommande')).toBe(false);
    expect(TAILLES_CHARGEABLES).toEqual(['eco', 'max']);
  });

  it('Éco et Max le sont ; une clé inventée ne l’est pas', () => {
    expect(estChargeable('eco')).toBe(true);
    expect(estChargeable('max')).toBe(true);
    expect(estChargeable('moyenne')).toBe(false);
    expect(estChargeable(null)).toBe(false);
  });
});

// ── 2. LE CACHE : UN APPEL PAR TAILLE ET PAR VARIANTE ──────────────────────

describe('clé de cache navigateur', () => {
  it('sépare les tailles ET les variantes', () => {
    expect(cleCacheDetail('eco', 'sans')).not.toEqual(cleCacheDetail('eco', 'avec'));
    expect(cleCacheDetail('eco', 'sans')).not.toEqual(cleCacheDetail('max', 'sans'));
  });

  it('est stable : rebasculer sur une taille déjà vue ne rappelle pas le réseau', () => {
    expect(cleCacheDetail('max', 'avec')).toEqual(cleCacheDetail('max', 'avec'));
  });
});

// ── 3. LES URLS ────────────────────────────────────────────────────────────

describe('URLs', () => {
  it('le navigateur passe par le proxy SAME-ORIGIN, jamais par le backend', () => {
    const u = detailProxyUrl('jeton-abc', 'eco', 'avec');
    expect(u.startsWith('/api/proposition-taille?')).toBe(true);
    expect(u).toContain('token=jeton-abc');
    expect(u).toContain('cle=eco');
    expect(u).toContain('variante=avec');
    expect(u).not.toContain('http');
  });

  it('l’URL backend est celle du contrat, montée sous public/', () => {
    const u = tailleDetailEndpoint('https://api.taqinor.ma', 'j/e ton', 'max', 'sans');
    expect(u).toBe('https://api.taqinor.ma/api/django/public/proposal/j%2Fe%20ton/taille/max/?variante=sans');
  });

  it('une base vide retombe sur la production, sans double slash', () => {
    expect(tailleDetailEndpoint('https://api.taqinor.ma/', 'j', 'eco', 'sans'))
      .toContain('https://api.taqinor.ma/api/django/');
  });
});

// ── 4. LA LONGUEUR D'ARC — UNE SEULE DÉFINITION ────────────────────────────

describe('anneau de couverture', () => {
  it('la longueur d’arc est une géométrie, pas un recalcul du pourcentage', () => {
    const { dash, circ } = arcDonut(50, 42);
    expect(circ).toBeCloseTo(2 * Math.PI * 42, 6);
    expect(dash).toBeCloseTo(circ / 2, 6);
  });

  it('borne à 0..100 : un pourcentage aberrant ne déborde jamais l’anneau', () => {
    expect(arcDonut(140, 42).dash).toBeCloseTo(arcDonut(100, 42).dash, 6);
    expect(arcDonut(-5, 42).dash).toBe(0);
    expect(arcDonut(null, 42).dash).toBe(0);
  });

  it('rend un `stroke-dasharray` à DEUX décimales, comme le rendu serveur', () => {
    expect(dasharrayDonut(50, 42)).toMatch(/^\d+\.\d{2} \d+\.\d{2}$/);
  });

  it('la page appelle CETTE fonction des deux côtés (SSR et îlot)', () => {
    expect(CODE).toContain("import { dasharrayDonut } from '../../lib/tailleDetail'");
    expect(CODE).toContain('const donutDasharray = dasharrayDonut(');
    expect(CODE).toContain('stroke-dasharray={donutDasharray}');
    expect(CODE).toContain('dasharrayDonut(pct, rayon)');
  });
});

// ── 5. LECTURE DU CONTRAT — ET L'OMISSION HÉRITÉE ──────────────────────────

describe('lecture du contrat taille_detail', () => {
  it('lit un détail complet', () => {
    const d = tailleDetail(SERVI)!;
    expect(d.cle).toBe('eco');
    expect(d.titre).toBe('Éco');
    expect(d.variante).toBe('sans');
    expect(d.estLeDevis).toBe(false);
    expect(d.carte!.couverturePct).toBe(48.2);
    expect(d.economiesMensuelles!.valeurs).toHaveLength(12);
    expect(d.economiesMensuelles!.total).toBe(9940);
    expect(d.cashflow!.cumulative).toEqual([-61560, -51720]);
    expect(d.cashflow!.horizonAnnees).toBe(25);
  });

  it('refuse un payload qui n’en est pas un', () => {
    expect(tailleDetail(null)).toBeNull();
    expect(tailleDetail('eco')).toBeNull();
    expect(tailleDetail({ cle: 'eco' })).toBeNull();
    expect(tailleDetail({ ...SERVI, variante: 'peut-etre' })).toBeNull();
  });

  it('refuse « recommande » même si le serveur l’envoyait', () => {
    // Défense en profondeur : la page ne doit JAMAIS repeindre ses chapitres
    // profonds depuis un aller-retour réseau pour le devis officiel.
    expect(tailleDetail({ ...SERVI, cle: 'recommande' })).toBeNull();
  });

  it('OMET une série de onze mois plutôt que de la montrer', () => {
    const onze = { ...SERVI.economies_mensuelles, valeurs: SERVI.economies_mensuelles.valeurs.slice(1) };
    const d = tailleDetail({ ...SERVI, economies_mensuelles: onze })!;
    expect(d.economiesMensuelles).toBeNull();
    // …et le reste du détail survit : l'omission est PAR BLOC.
    expect(d.carte!.prixTtc).toBe(71400);
  });

  it('OMET la série dès qu’une valeur n’est pas un nombre', () => {
    const sale = { ...SERVI.economies_mensuelles, valeurs: [...SERVI.economies_mensuelles.valeurs] };
    (sale.valeurs as unknown[])[4] = null;
    expect(tailleDetail({ ...SERVI, economies_mensuelles: sale })!.economiesMensuelles).toBeNull();
  });

  it('ne RESOMME jamais le total : il est servi ou la série est omise', () => {
    const sansTotal = { valeurs: SERVI.economies_mensuelles.valeurs, devise: 'MAD' };
    expect(tailleDetail({ ...SERVI, economies_mensuelles: sansTotal })!.economiesMensuelles).toBeNull();
  });

  it('un champ absent de la carte reste `null`, jamais un zéro', () => {
    const d = tailleDetail({ ...SERVI, carte: { nb_panneaux: 14 } })!;
    expect(d.carte!.couverturePct).toBeNull();
    expect(d.carte!.paybackAnnees).toBeNull();
    expect(d.carte!.batterie).toBeNull();
    expect(d.carte!.nbPanneaux).toBe(14);
  });

  it('lit la banque batterie quand la variante « avec » la porte', () => {
    const d = tailleDetail({
      ...SERVI, variante: 'avec',
      carte: { ...SERVI.carte, batterie: { nb_modules: 3, module_kwh: 5, capacite_utile_kwh: 13.5, remplissage_ok: false } },
    })!;
    expect(d.carte!.batterie).toEqual({
      nbModules: 3, moduleKwh: 5, capaciteUtileKwh: 13.5, remplissageOk: false,
    });
  });

  it('un cashflow vide est OMIS, jamais une courbe à zéro', () => {
    expect(tailleDetail({ ...SERVI, cashflow: { cumulative: [] } })!.cashflow).toBeNull();
    expect(tailleDetail({ ...SERVI, cashflow: null })!.cashflow).toBeNull();
  });
});

// ── 6. LE PROXY SAME-ORIGIN ────────────────────────────────────────────────

describe('proxy /api/proposition-taille', () => {
  it('refuse un appel cross-site et rate-limite, comme ses quatre voisins', () => {
    expect(PROXY).toContain('isSameOriginRequest(request)');
    expect(PROXY).toContain('crossSiteRejection()');
    expect(PROXY).toContain("rateLimit(`proposition-taille:");
  });

  it('refuse « recommande » AVANT d’appeler le backend', () => {
    expect(PROXY).toContain('estChargeable(cle)');
  });

  it('ne fait qu’une LECTURE : aucun POST, aucune écriture', () => {
    expect(PROXY).toContain('export const GET');
    expect(PROXY).not.toContain('export const POST');
    expect(PROXY).toContain("method: 'GET'");
  });

  it('dégrade en { ok: false } plutôt que de faire remonter une erreur', () => {
    expect(PROXY).toContain('return json({ ok: false }, 200);');
  });
});

// ── 7. LE CÂBLAGE DE LA PAGE ───────────────────────────────────────────────

describe('page — les chapitres profonds suivent la carte cliquée', () => {
  it('les nœuds profonds portent un crochet `data-detail-*` (SSR)', () => {
    for (const crochet of [
      'data-detail-eco-bloc', 'data-detail-eco-mois={i}', 'data-detail-eco-mois-avec={i}',
      'data-detail-eco-total', 'data-detail-eco-total-avec-bloc',
      'data-detail-banque', 'data-detail-echec', 'data-detail-retry',
      'data-detail-couverture-arc', 'data-detail-couverture-value',
      'data-detail-cumul-card', 'data-detail-cumul-value',
      'data-detail-payback-card', 'data-detail-payback-value',
    ]) {
      expect(CODE, crochet).toContain(crochet);
    }
  });

  it('un clic de carte déclenche le chargement du détail', () => {
    expect(CODE).toContain('void chargerDetail();');
    expect(CODE).toContain('detailProxyUrl(jetonTailles, cle, variante)');
  });

  it('le jeton vient de la section elle-même, pas d’un nœud étranger', () => {
    expect(CODE).toContain('data-tailles-token={token}');
    expect(CODE).toContain('section.dataset.taillesToken');
  });

  it('UN SEUL appel par taille+variante : le cache sert les retours', () => {
    expect(CODE).toContain('const cacheDetail = new Map<string, TailleDetail | null>()');
    expect(CODE).toContain('if (cacheDetail.has(clef))');
    expect(CODE).toContain('cacheDetail.set(demande, detail)');
  });

  it('l’état de chargement MASQUE au lieu de griser', () => {
    // Griser les chiffres du devis officiel sous une carte Éco, c'est encore
    // les montrer : la lane les masque le temps de la réponse.
    expect(CODE).toContain('function marquerChargement(enCours: boolean)');
    expect(CODE).toContain("n.setAttribute('aria-busy', 'true'); n.hidden = true;");
  });

  it('une réponse en retard ne repeint jamais une autre carte', () => {
    expect(CODE).toContain('if (cleCacheDetail(cle, variante) === demande) appliquerDetail(detail);');
  });

  it('un échec MASQUE les chapitres et propose de réessayer', () => {
    expect(CODE).toContain('const echec = detail === null;');
    expect(CODE).toContain('if (ecoEchec) ecoEchec.hidden = !echec;');
    expect(CODE).toContain('cacheDetail.delete(cleCacheDetail(cle, variante));');
  });

  it('« Recommandé » RESTAURE les originaux — jamais un aller-retour réseau', () => {
    expect(CODE).toContain('restaurerDetail();');
    expect(CODE).toContain('if (surLeDefaut || !estChargeable(cle) || !jetonTailles)');
    expect(CODE).toContain('const originaux = {');
  });

  it('un champ que la taille ne sert pas fait MASQUER son bloc', () => {
    expect(CODE).toContain('if (heroCouvertureCard) heroCouvertureCard.hidden = pct === null;');
    expect(CODE).toContain('if (cumulCard) cumulCard.hidden = cumul === null;');
    expect(CODE).toContain('if (paybackCard) paybackCard.hidden = payback === null;');
  });

  it('la ligne « avec batterie » des cellules est masquée : un détail = UNE variante', () => {
    expect(CODE).toContain('for (const n of ecoMoisAvec) n.hidden = true;');
  });
});

// ── 8. LA CARTE RÉCAPITULATIVE MONO-OPTION ─────────────────────────────────

describe('page — le récapitulatif « Recommandé » quand une seule option est envoyée', () => {
  it('n’existe QUE sans `offres_tailles` : jamais deux récapitulatifs', () => {
    expect(CODE).toContain('{ok && !tailles && (heroTtc !== null || ecoHero || paybackHero || heroKwc || prodKwh) && (');
    expect(CODE).toContain('data-recap-mono');
  });

  it('ouvre la page : il vient AVANT la section des tailles', () => {
    const recap = CODE.indexOf('data-recap-mono');
    const tailles = CODE.indexOf('id="tailles"');
    expect(recap).toBeGreaterThan(0);
    expect(tailles).toBeGreaterThan(recap);
  });

  it('reste DENSE : prix, économie, payback, puissance, production, couverture, batterie', () => {
    const debut = CODE.indexOf('data-recap-mono');
    // La fenêtre s'arrête à la section SUIVANTE : au-delà commence le bloc
    // des tailles, dont les `data-taille-*` ne sont pas ceux du récapitulatif.
    const bloc = CODE.slice(debut, CODE.indexOf('{tailles && tailleDefaut && (', debut));
    for (const valeur of [
      'formatMAD(heroTtc)', 'formatMAD(ecoHero)', '{paybackHero}',
      'formatNumber(heroKwc, 2)', 'formatNumber(prodKwh)',
      'formatPercent(couverture.pct, 0)', 'batteryUnitCapacityLabel',
    ]) {
      expect(bloc, valeur).toContain(valeur);
    }
  });

  it('n’a AUCUNE sémantique de sélection : c’est un résumé, pas un choix', () => {
    const debut = CODE.indexOf('data-recap-mono');
    // La fenêtre s'arrête à la section SUIVANTE : au-delà commence le bloc
    // des tailles, dont les `data-taille-*` ne sont pas ceux du récapitulatif.
    const bloc = CODE.slice(debut, CODE.indexOf('{tailles && tailleDefaut && (', debut));
    for (const interdit of ['data-taille-cle', 'data-taille-carte', 'aria-current', 'data-taille-cta']) {
      expect(bloc, interdit).not.toContain(interdit);
    }
  });

  it('chaque item est GARDÉ : jamais un zéro de remplissage', () => {
    const debut = CODE.indexOf('data-recap-mono');
    // La fenêtre s'arrête à la section SUIVANTE : au-delà commence le bloc
    // des tailles, dont les `data-taille-*` ne sont pas ceux du récapitulatif.
    const bloc = CODE.slice(debut, CODE.indexOf('{tailles && tailleDefaut && (', debut));
    for (const garde of ['{heroTtc !== null ? (', '{ecoHero ? (', '{paybackHero ? (',
      '{heroKwc ? (', '{prodKwh ? (', '{showCouvertureDonut && couverture ? (']) {
      expect(bloc, garde).toContain(garde);
    }
  });
});
