// @vitest-environment jsdom
//
// QJW8 — LE MOTEUR APPLIQUER / RESTAURER, ET SURTOUT SA RÈGLE FONDATRICE.
//
// CE QUE CE FICHIER PROUVE, ET POURQUOI IL EXISTE. La page proposition est
// rendue au serveur avec les nombres du DEVIS OFFICIEL. Quand le client charge
// « Éco » ou « Max », tout champ que cette taille NE SERT PAS doit
// DISPARAÎTRE : le repli « tant pis, on remet l'original » écrirait un nombre
// RÉEL sous une carte qui n'est pas la sienne. La page avait dû corriger ce bug
// à la main, deux fois, dans deux fonctions différentes. Le moteur l'encode
// désormais UNE fois — et le test central ci-dessous (« lire → null ») le
// PROUVE de deux façons indépendantes : `peindre` n'est pas appelé DU TOUT, et
// le texte du nœud est resté MOT POUR MOT celui du chargement, sous une
// enveloppe masquée.
import { beforeEach, describe, expect, it } from 'vitest';

// Import JSON direct (et non `readFileSync(import.meta.url)`) : sous
// l'environnement jsdom, `import.meta.url` n'est PAS une URL `file:` — c'est
// l'origine du document simulé, et `fileURLToPath` refuse. L'échantillon est
// donc résolu par vite, exactement comme un module.
import echantillon from '../src/contract_samples/taille_detail.json';

import {
  PROFONDS,
  liaisonsHero,
  unHtml,
  type ContexteHero,
  type Liaison,
  type NoeudsResolus,
} from '../src/lib/proposition/liaisons';
import {
  appliquer,
  capturerOriginaux,
  marquerChargement,
  restaurer,
} from '../src/lib/proposition/swap';
import { tailleDetail, type TailleDetail } from '../src/lib/tailleDetail';

const ECHANTILLON = echantillon as unknown as { exemple: unknown; exemple_avec_batterie: unknown };

const DETAIL_ECO = tailleDetail(ECHANTILLON.exemple) as TailleDetail;
const DETAIL_MAX = tailleDetail(ECHANTILLON.exemple_avec_batterie) as TailleDetail;

function monter(html: string): void {
  document.body.innerHTML = html;
}

// ── UNE LIAISON JOUET, POUR OBSERVER LE MOTEUR SANS LA PAGE ─────────────────

interface Espion {
  peintures: number;
  liaison: Liaison<string | null, string>;
}

function liaisonEspionne(): Espion {
  const espion: Espion = {
    peintures: 0,
    liaison: {
      cle: 'jouet',
      enveloppe: '#enveloppe',
      noeuds: { valeur: { sel: '#valeur' } },
      lire(ctx: string | null): string | null {
        return ctx;
      },
      peindre(noeuds: NoeudsResolus, texte: string): void {
        espion.peintures += 1;
        const el = unHtml(noeuds, 'valeur');
        if (el) el.textContent = texte;
      },
    },
  };
  return espion;
}

const JOUET_HTML = '<div id="enveloppe"><span id="valeur">12 000 MAD</span></div>';

describe('QJW8 — `lire` rend `null` : CACHER, et n’écrire RIEN', () => {
  beforeEach(() => monter(JOUET_HTML));

  it('l’enveloppe est masquée ET `peindre` n’est JAMAIS appelé', () => {
    const espion = liaisonEspionne();
    const liaisons = [espion.liaison];
    capturerOriginaux(liaisons);

    appliquer(liaisons, null);

    expect(document.querySelector<HTMLElement>('#enveloppe')!.hidden).toBe(true);
    expect(espion.peintures).toBe(0);
  });

  it('AUCUNE valeur n’est écrite : le texte du nœud reste MOT POUR MOT celui du chargement', () => {
    const espion = liaisonEspionne();
    const liaisons = [espion.liaison];
    capturerOriginaux(liaisons);

    appliquer(liaisons, null);

    // Le nœud n'a pas été blanchi, pas remplacé par un tiret, pas mis à zéro —
    // et surtout pas relu depuis l'original pour être reposé « au cas où ».
    // Il est INTACT, sous une enveloppe masquée : l'omission honnête.
    expect(document.querySelector('#valeur')!.textContent).toBe('12 000 MAD');
  });

  it('l’original N’EST PAS relu sous une autre carte : après une valeur servie puis un `null`, on masque — on ne revient pas au chiffre du devis', () => {
    const espion = liaisonEspionne();
    const liaisons = [espion.liaison];
    capturerOriginaux(liaisons);

    appliquer(liaisons, '9 840 MAD');
    expect(document.querySelector('#valeur')!.textContent).toBe('9 840 MAD');
    expect(document.querySelector<HTMLElement>('#enveloppe')!.hidden).toBe(false);

    appliquer(liaisons, null);
    expect(document.querySelector<HTMLElement>('#enveloppe')!.hidden).toBe(true);
    // Le texte reste celui de la taille précédente, MASQUÉ — jamais réécrit
    // avec l'original du devis officiel, qui appartient à une autre carte.
    expect(document.querySelector('#valeur')!.textContent).toBe('9 840 MAD');
    expect(espion.peintures).toBe(1);
  });

  it('`undefined` est traité comme `null` (une liaison qui oublie de rendre `null` ne peut pas ouvrir une brèche)', () => {
    const espion = liaisonEspionne();
    const liaisons: Liaison<string | null, string>[] = [{
      ...espion.liaison,
      lire(): string | null {
        return undefined as unknown as null;
      },
    }];
    capturerOriginaux(liaisons);
    appliquer(liaisons, 'ignoré');
    expect(document.querySelector<HTMLElement>('#enveloppe')!.hidden).toBe(true);
    expect(document.querySelector('#valeur')!.textContent).toBe('12 000 MAD');
  });

  it('l’enveloppe n’est DÉMASQUÉE qu’après la peinture (jamais un bloc visible portant encore l’ancien chiffre)', () => {
    monter('<div id="enveloppe" hidden><span id="valeur">12 000 MAD</span></div>');
    const ordre: string[] = [];
    const liaisons: Liaison<string, string>[] = [{
      cle: 'ordre',
      enveloppe: '#enveloppe',
      noeuds: { valeur: { sel: '#valeur' } },
      lire: (ctx: string) => ctx,
      peindre(_noeuds: NoeudsResolus, _v: string) {
        ordre.push(`peindre:hidden=${document.querySelector<HTMLElement>('#enveloppe')!.hidden}`);
      },
    }];
    appliquer(liaisons, 'x');
    expect(ordre).toEqual(['peindre:hidden=true']);
    expect(document.querySelector<HTMLElement>('#enveloppe')!.hidden).toBe(false);
  });
});

describe('QJW8 — `capturerOriginaux` moissonne texte, HTML, attribut ET visibilité', () => {
  it('les trois natures de capture et le `hidden` rendu au serveur sont restitués à l’identique', () => {
    monter(`
      <div id="env">
        <span id="txt">231 400 MAD</span>
        <table><tbody id="corps"><tr><td>1</td><td>-61 560 MAD</td></tr></tbody></table>
        <svg><circle id="arc" stroke-dasharray="151.32 162.68" data-detail-donut-r="50"></circle></svg>
        <p id="cachee" hidden>déjà masqué au chargement</p>
      </div>
    `);
    const liaisons: Liaison<boolean>[] = [{
      cle: 'trois',
      enveloppe: '#env',
      noeuds: {
        txt: { sel: '#txt' },
        corps: { sel: '#corps', capture: 'html' },
        arc: { sel: '#arc', capture: { attribut: 'stroke-dasharray' } },
        cachee: { sel: '#cachee' },
      },
      lire: (ctx: boolean) => (ctx ? 'x' : null),
      peindre(noeuds: NoeudsResolus) {
        unHtml(noeuds, 'txt')!.textContent = 'FAUX';
        unHtml(noeuds, 'corps')!.innerHTML = '<tr><td>FAUX</td></tr>';
        document.querySelector('#arc')!.setAttribute('stroke-dasharray', '0 314');
        const c = unHtml(noeuds, 'cachee')!;
        c.hidden = false;
      },
    }];
    const originaux = capturerOriginaux(liaisons);

    appliquer(liaisons, true);
    expect(document.querySelector('#txt')!.textContent).toBe('FAUX');
    expect(document.querySelector<HTMLElement>('#cachee')!.hidden).toBe(false);

    restaurer(liaisons, originaux);
    expect(document.querySelector('#txt')!.textContent).toBe('231 400 MAD');
    expect(document.querySelector('#corps')!.innerHTML).toBe('<tr><td>1</td><td>-61 560 MAD</td></tr>');
    expect(document.querySelector('#arc')!.getAttribute('stroke-dasharray')).toBe('151.32 162.68');
    // Un nœud masqué au chargement REDEVIENT masqué : la restauration repose
    // l'état du serveur, elle ne « démasque tout » pas.
    expect(document.querySelector<HTMLElement>('#cachee')!.hidden).toBe(true);
  });

  it('un sélecteur multiple apparie chaque nœud à SON original (les douze mois, pas un seul)', () => {
    monter('<div id="env">' + [0, 1, 2].map((i) => `<span data-m>M${i}</span>`).join('') + '</div>');
    const liaisons: Liaison<number[] | null, number[]>[] = [{
      cle: 'mois',
      enveloppe: '#env',
      noeuds: { mois: { sel: '[data-m]', tous: true } },
      lire: (ctx: number[] | null) => ctx,
      peindre(noeuds: NoeudsResolus, v: number[]) {
        const els = Array.from(document.querySelectorAll('[data-m]'));
        els.forEach((el, i) => { el.textContent = String(v[i]); });
        void noeuds;
      },
    }];
    const originaux = capturerOriginaux(liaisons);
    appliquer(liaisons, [7, 8, 9]);
    expect(Array.from(document.querySelectorAll('[data-m]')).map((e) => e.textContent)).toEqual(['7', '8', '9']);
    restaurer(liaisons, originaux);
    expect(Array.from(document.querySelectorAll('[data-m]')).map((e) => e.textContent)).toEqual(['M0', 'M1', 'M2']);
  });
});

describe('QJW8 — `marquerChargement` masque, il ne grise pas', () => {
  beforeEach(() => monter(JOUET_HTML));

  it('en cours : enveloppe masquée + `aria-busy`', () => {
    const liaisons = [liaisonEspionne().liaison];
    marquerChargement(liaisons, true);
    const env = document.querySelector<HTMLElement>('#enveloppe')!;
    expect(env.hidden).toBe(true);
    expect(env.getAttribute('aria-busy')).toBe('true');
  });

  it('fin de chargement : `aria-busy` retiré, mais RIEN n’est démasqué — c’est `appliquer`/`restaurer` qui décide', () => {
    const liaisons = [liaisonEspionne().liaison];
    marquerChargement(liaisons, true);
    marquerChargement(liaisons, false);
    const env = document.querySelector<HTMLElement>('#enveloppe')!;
    expect(env.getAttribute('aria-busy')).toBeNull();
    expect(env.hidden).toBe(true);
  });
});

// ── LE MOTEUR SUR LES VRAIES TABLES ─────────────────────────────────────────

const PAGE_HTML = `
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
`;

describe('QJW8 — la table PROFONDS pilotée par le moteur, sur l’échantillon de contrat', () => {
  beforeEach(() => monter(PAGE_HTML));

  it('un détail servi peint les chapitres et démasque leurs enveloppes', () => {
    capturerOriginaux(PROFONDS);
    appliquer(PROFONDS, DETAIL_ECO);

    expect(document.querySelector('[data-detail-eco-total]')!.textContent).toBe('9 940 MAD');
    expect(Array.from(document.querySelectorAll('[data-detail-eco-mois]'))[0]!.textContent).toBe('640 MAD');
    expect(document.querySelector('[data-detail-cumul-value]')!.textContent).toBe('231 400 MAD');
    expect(document.querySelector('[data-detail-payback-value]')!.textContent).toBe('7,3 ans');
    expect(document.querySelector('[data-detail-couverture-value]')!.textContent).toBe('48 %');
    expect(document.querySelector<HTMLElement>('[data-hero-couverture-card]')!.hidden).toBe(false);
    // Le tableau année par année SUIT la carte (le chapitre oublié à la
    // première livraison) : cinq lignes servies, pas les 25 du devis.
    expect(document.querySelectorAll('[data-cumul-annuel] tbody tr')).toHaveLength(5);
    // Les chiffres « avec batterie » sont d'une AUTRE variante : masqués.
    expect(Array.from(document.querySelectorAll<HTMLElement>('[data-detail-eco-mois-avec]')).every((n) => n.hidden)).toBe(true);
  });

  it('un chapitre NON SERVI est masqué, et son contenu d’origine n’est ni réécrit ni resservi ailleurs', () => {
    capturerOriginaux(PROFONDS);
    // L'exemple « Max » du contrat ne porte PAS de bloc `cashflow` : le
    // tableau année par année doit disparaître, pas afficher les 25 lignes du
    // devis officiel sous la carte Max.
    expect(DETAIL_MAX.cashflow).toBeNull();
    appliquer(PROFONDS, DETAIL_MAX);

    const bloc = document.querySelector<HTMLElement>('[data-cumul-annuel]')!;
    expect(bloc.hidden).toBe(true);
    expect(document.querySelectorAll('[data-cumul-annuel] tbody tr')).toHaveLength(1);
    expect(document.querySelector('[data-cumul-annuel] tbody')!.innerHTML)
      .toBe('<tr><td>1</td><td>-80 000 MAD</td></tr>');
    // Et la banque de la carte Max, elle, EST servie : elle apparaît.
    const banque = document.querySelector<HTMLElement>('[data-detail-banque]')!;
    expect(banque.hidden).toBe(false);
    expect(banque.textContent).toBe('Batterie · 6 × 5 kWh · 27 kWh utiles');
  });

  it('un échec (`detail === null`) laisse voir le message de réessai mais masque les douze chiffres du devis', () => {
    capturerOriginaux(PROFONDS);
    appliquer(PROFONDS, null);

    // L'enveloppe des économies reste VISIBLE : elle porte le « Réessayer ».
    expect(document.querySelector<HTMLElement>('[data-detail-eco-bloc]')!.hidden).toBe(false);
    // …mais aucun des douze mois du devis officiel n'est encore lisible.
    expect(Array.from(document.querySelectorAll<HTMLElement>('[data-detail-eco-mois]')).every((n) => n.hidden)).toBe(true);
    expect(document.querySelector<HTMLElement>('[data-detail-eco-total]')!.hidden).toBe(true);
    // Les autres chapitres, eux, disparaissent entièrement.
    for (const sel of ['[data-detail-cumul-card]', '[data-detail-payback-card]', '[data-hero-couverture-card]', '[data-cumul-annuel]']) {
      expect(document.querySelector<HTMLElement>(sel)!.hidden).toBe(true);
    }
  });

  it('le retour sur « Recommandé » restaure la page À L’OCTET (textes, HTML du tableau, arc, visibilités)', () => {
    const originaux = capturerOriginaux(PROFONDS);
    const avant = document.body.innerHTML;

    appliquer(PROFONDS, DETAIL_ECO);
    expect(document.body.innerHTML).not.toBe(avant);

    restaurer(PROFONDS, originaux);
    expect(document.body.innerHTML).toBe(avant);
  });

  it('un aller-retour PAR le chargement (masquage réseau compris) revient lui aussi à l’octet', () => {
    const originaux = capturerOriginaux(PROFONDS);
    const avant = document.body.innerHTML;

    marquerChargement(PROFONDS, true);
    appliquer(PROFONDS, DETAIL_MAX);
    marquerChargement(PROFONDS, false);
    restaurer(PROFONDS, originaux);

    expect(document.body.innerHTML).toBe(avant);
  });
});

// ── LES LIAISONS DE TÊTE ────────────────────────────────────────────────────

const HERO_HTML = `
  <div data-hero-ttc-card><span data-hero-ttc-value>150 000 MAD</span></div>
  <div data-hero-eco-card data-hero-eco-kind="eco"><span data-hero-eco-value>18 000 MAD</span></div>
  <li data-hero-kwc-item><span data-hero-kwc-value>12 kWc</span></li>
  <li data-hero-panneaux-item><span data-hero-panneaux-value>22</span></li>
  <div data-hero-production-card><span data-hero-production-value>19 000 kWh</span></div>
  <div data-hero-eco-annual-card><span data-hero-eco-annual-value>18 000 MAD</span></div>
`;

function contexte(table: Record<string, string | null>): ContexteHero {
  return { texteCarte: (sel: string) => table[sel] ?? null };
}

describe('QJW8 — les liaisons de tête suivent la MÊME discipline', () => {
  beforeEach(() => monter(HERO_HTML));

  it('un champ que la carte ne sert pas masque son item — sans réécrire le chiffre du devis', () => {
    const liaisons = liaisonsHero('eco');
    capturerOriginaux(liaisons);
    appliquer(liaisons, contexte({
      '[data-taille-ttc-value]': '71 400 MAD',
      // ni kWc ni panneaux servis par cette carte
      '[data-taille-eco-value]': '9 840 MAD',
    }));

    expect(document.querySelector('[data-hero-ttc-value]')!.textContent).toBe('71 400 MAD');
    expect(document.querySelector<HTMLElement>('[data-hero-kwc-item]')!.hidden).toBe(true);
    expect(document.querySelector('[data-hero-kwc-value]')!.textContent).toBe('12 kWc');
    expect(document.querySelector<HTMLElement>('[data-hero-panneaux-item]')!.hidden).toBe(true);
  });

  it('`liaisonsHero` n’active QUE la ligne homonyme du créneau « Économie / an »', () => {
    expect(liaisonsHero('eco').map((l) => l.cle)).toEqual(
      ['ttc', 'eco', 'kwc', 'panneaux', 'production', 'eco_annuelle'],
    );
    expect(liaisonsHero('payback').map((l) => l.cle)).toEqual(
      ['ttc', 'eco_payback', 'kwc', 'panneaux', 'production', 'eco_annuelle'],
    );
  });

  it('en mode `payback`, le créneau lit le payback de la carte — jamais son économie', () => {
    const liaisons = liaisonsHero('payback');
    capturerOriginaux(liaisons);
    appliquer(liaisons, contexte({
      '[data-taille-eco-value]': '9 840 MAD',
      '[data-taille-payback-value]': '7,3 ans',
    }));
    expect(document.querySelector('[data-hero-eco-value]')!.textContent).toBe('7,3 ans');
  });

  it('le retour sur « Recommandé » restaure les sept champs de tête à l’octet', () => {
    const liaisons = liaisonsHero('eco');
    const originaux = capturerOriginaux(liaisons);
    const avant = document.body.innerHTML;
    appliquer(liaisons, contexte({ '[data-taille-ttc-value]': '71 400 MAD' }));
    expect(document.body.innerHTML).not.toBe(avant);
    restaurer(liaisons, originaux);
    expect(document.body.innerHTML).toBe(avant);
  });
});
