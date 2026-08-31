// @vitest-environment jsdom
//
// QJW19 — UNE RÉPONSE EN RETARD NE DÉCLARE PLUS « CHARGÉ » UNE SECTION ENCORE
// EN VOL.
//
// L'INCIDENT. `chargerDetail()` (îlot de `pages/proposition/[...token].astro`)
// appelait `marquerChargement(PROFONDS, false)` DÈS que SON appel réseau
// revenait — sans se demander si cet appel était encore celui de la carte
// affichée. Or ce geste retire `aria-busy` de TOUTES les enveloppes de la
// table. Une réponse arrivée en retard effaçait donc l'attente qu'une demande
// PLUS RÉCENTE, toujours en vol, venait légitimement de poser. Et comme la
// sortie de chargement ne DÉMASQUE rien (règle du moteur : c'est `appliquer`
// ou `restaurer` qui décide champ par champ), les chapitres restaient
// MASQUÉS : la technologie d'assistance annonçait une région stabilisée…
// vide, et toujours en chargement.
//
// La page savait déjà se garder d'une réponse périmée pour la PEINTURE
// (`if (cleCacheDetail(cle, variante) === demande) appliquerDetail(detail)`) —
// c'est l'ANNONCE de fin d'attente qui n'avait pas la même garde. QJW19 lui
// donne la même : un JETON de demande, et seule la demande courante efface
// l'attente.
//
// COMMENT CE FICHIER S'Y PREND, ET POURQUOI. Un îlot `<script>` Astro ne se
// monte pas dans vitest (idiome de la maison, cf. `propositionBasculeQJW9`) :
// on vérifie donc la SOURCE, puis le COMPORTEMENT. Mais le harnais de
// comportement n'est PAS une copie figée de l'îlot — sa politique de
// péremption est LUE dans le fichier réel (`ILOT_PERIME_LES_REPONSES_EN_RETARD`
// ci-dessous). Tant que l'îlot n'avait pas la garde, le scénario A-lente /
// B-rapide tournait ROUGE ; il ne devient VERT que parce que la garde est
// réellement dans la page. Retirer la garde du `.astro` rougit ce fichier.
import { beforeEach, describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { PROFONDS } from '../src/lib/proposition/liaisons';
import { appliquer, capturerOriginaux, marquerChargement, restaurer } from '../src/lib/proposition/swap';
import { cleCacheDetail, estChargeable, tailleDetail, type TailleDetail } from '../src/lib/tailleDetail';

const SOURCE = readFileSync(join(process.cwd(), 'src/pages/proposition/[...token].astro'), 'utf-8')
  .replace(/\r\n/g, '\n');

/** L'îlot des tailles seul — le frontmatter a des helpers aux noms voisins. */
const ILOT = SOURCE.slice(SOURCE.indexOf('function setupTaillesOffres'));

/** LE CORPS DE `chargerDetail` — la fonction dont l'ordonnancement est en jeu. */
const CHARGER_DETAIL = (() => {
  const debut = ILOT.indexOf('async function chargerDetail');
  const fin = ILOT.indexOf('\n    if (ecoEchec) {', debut);
  expect(debut, '`chargerDetail` introuvable dans l’îlot').toBeGreaterThan(-1);
  expect(fin, 'la fin de `chargerDetail` n’a pas été retrouvée').toBeGreaterThan(debut);
  return ILOT.slice(debut, fin);
})();

/** La branche « déjà en cache », qui court-circuite le réseau. */
const BRANCHE_CACHE = CHARGER_DETAIL.slice(
  CHARGER_DETAIL.indexOf('if (cacheDetail.has(clef))'),
  CHARGER_DETAIL.indexOf('const demande = clef;'),
);

/** Le jeton capturé AVANT le premier `await` — l'identité de CET appel. */
const CAPTURE_DU_JETON = /const (\w+) = \+\+jetonDemande;/.exec(CHARGER_DETAIL);

/** La garde de péremption, telle qu'elle est (ou non) écrite dans la page. */
const GARDE_DE_PEREMPTION = /if \((\w+) !== jetonDemande\) return;/.exec(CHARGER_DETAIL);

/**
 * LA POLITIQUE DE L'ÎLOT, LUE DANS L'ÎLOT. Le harnais de comportement plus bas
 * s'y conforme : c'est ce qui fait que ce fichier décrit la PAGE, et pas une
 * intention. Deux conditions, parce que les deux comptent — la garde doit
 * exister, ET précéder l'effacement d'`aria-busy` (une garde écrite APRÈS ne
 * garderait rien).
 */
const ILOT_PERIME_LES_REPONSES_EN_RETARD: boolean = (() => {
  if (!GARDE_DE_PEREMPTION || !CAPTURE_DU_JETON) return false;
  if (GARDE_DE_PEREMPTION[1] !== CAPTURE_DU_JETON[1]) return false;
  // La comparaison se fait DANS la région d'APRÈS-RÉPONSE : la branche « déjà
  // en cache », plus haut, lève elle aussi l'attente — la chercher depuis le
  // début de la fonction trouverait CETTE ligne-là et ne prouverait rien.
  const apres = CHARGER_DETAIL.slice(CHARGER_DETAIL.indexOf('cacheDetail.set(demande, detail)'));
  const iGarde = apres.indexOf(GARDE_DE_PEREMPTION[0]);
  const iFin = apres.indexOf('marquerChargement(PROFONDS, false)');
  return iGarde !== -1 && iFin !== -1 && iGarde < iFin;
})();

/** L'îlot met-il aussi fin à l'attente quand il sert un détail DÉJÀ en cache ? */
const ILOT_EFFACE_SUR_CACHE: boolean = BRANCHE_CACHE.includes('marquerChargement(PROFONDS, false)');

// ── (1) LA SOURCE ───────────────────────────────────────────────────────────

describe('QJW19 — l’îlot attache l’effacement d’`aria-busy` à l’identité de la requête', () => {
  it('un compteur de demandes vit dans l’îlot', () => {
    expect(ILOT).toMatch(/let jetonDemande = 0;/);
  });

  it('`chargerDetail` capture SON jeton avant tout `await`', () => {
    expect(CAPTURE_DU_JETON, '`chargerDetail` ne prend pas d’identité de requête').not.toBeNull();
    const iJeton = CHARGER_DETAIL.indexOf(CAPTURE_DU_JETON![0]);
    const iAwait = CHARGER_DETAIL.indexOf('await ');
    expect(iAwait, 'plus aucun appel réseau dans `chargerDetail` ?').toBeGreaterThan(-1);
    expect(iJeton, 'le jeton est pris APRÈS l’attente : il ne distingue plus rien')
      .toBeLessThan(iAwait);
  });

  it('seule la demande COURANTE a le droit d’effacer l’attente', () => {
    expect(ILOT_PERIME_LES_REPONSES_EN_RETARD).toBe(true);
  });

  it('la peinture garde SA garde d’origine (elle n’est pas remplacée, elle est complétée)', () => {
    expect(CHARGER_DETAIL)
      .toContain('if (cleCacheDetail(cle, variante) === demande) appliquerDetail(detail);');
  });

  it('un détail servi DEPUIS LE CACHE met lui aussi fin à l’attente', () => {
    // Sinon un `aria-busy` posé par une demande réseau, puis périmé par ce
    // raccourci, resterait collé à « true » pour toujours : la garde
    // ci-dessus interdit à la réponse en retard d'y toucher.
    expect(ILOT_EFFACE_SUR_CACHE).toBe(true);
  });
});

// ── (2) LE COMPORTEMENT ─────────────────────────────────────────────────────

const ECHANTILLON = JSON.parse(
  readFileSync(join(process.cwd(), 'src/contract_samples/taille_detail.json'), 'utf-8'),
) as { exemple: unknown; exemple_avec_batterie: unknown };

const DETAIL_ECO = tailleDetail(ECHANTILLON.exemple) as TailleDetail;
const DETAIL_MAX = tailleDetail(ECHANTILLON.exemple_avec_batterie) as TailleDetail;

/** Les six enveloppes de la table PROFONDS, telles que le serveur les rend. */
const PAGE_HTML = `
  <div data-hero-couverture-card>
    <svg viewBox="0 0 100 100">
      <circle data-detail-couverture-arc data-detail-donut-r="42" stroke-dasharray="163.72 100.16"></circle>
      <text data-detail-couverture-value>62%</text>
    </svg>
  </div>
  <div data-detail-eco-bloc>
    ${Array.from({ length: 12 }, (_, i) => `<p data-detail-eco-mois>${1000 + i} MAD</p>`).join('')}
    <span data-detail-eco-total>13 000 MAD</span>
    <p data-detail-banque hidden></p>
  </div>
  <div data-detail-cumul-card><span data-detail-cumul-value>300 000 MAD</span></div>
  <div data-detail-payback-card><span data-detail-payback-value>6,5 ans</span></div>
  <div data-cumul-annuel><table><tbody><tr><td>1</td><td>-80 000 MAD</td></tr></tbody></table></div>
`;

const ENVELOPPES = [
  '[data-hero-couverture-card]', '[data-detail-eco-bloc]',
  '[data-detail-cumul-card]', '[data-detail-payback-card]', '[data-cumul-annuel]',
] as const;

/** Les enveloppes qui annoncent encore une attente aux lecteurs d'écran. */
function occupees(): string[] {
  return ENVELOPPES.filter(
    (sel) => document.querySelector(sel)?.getAttribute('aria-busy') === 'true',
  );
}

/**
 * LE HARNAIS — l'ordonnancement de `chargerDetail`, joué sur le VRAI moteur
 * (`marquerChargement`/`appliquer`/`restaurer`) et les VRAIES tables, avec le
 * réseau remplacé par des promesses que le test résout À LA MAIN : c'est la
 * seule façon de tenir DEUX requêtes en vol en même temps.
 *
 * Sa politique de péremption est celle de l'îlot, LUE plus haut dans le
 * fichier réel — jamais une intention recopiée.
 */
function harnais() {
  document.body.innerHTML = PAGE_HTML;
  const originaux = capturerOriginaux(PROFONDS);
  const cacheDetail = new Map<string, TailleDetail | null>();
  const enVol = new Map<string, (d: TailleDetail | null) => void>();
  let jetonDemande = 0;
  let cle = 'recommande';
  let variante: 'sans' | 'avec' = 'sans';

  async function chargerDetail(): Promise<void> {
    const monJeton = ++jetonDemande;
    const surLeDefaut = cle === 'recommande' && variante === 'sans';
    if (surLeDefaut || !estChargeable(cle)) {
      restaurer(PROFONDS, originaux);
      return;
    }
    const clef = cleCacheDetail(cle, variante);
    if (cacheDetail.has(clef)) {
      if (ILOT_EFFACE_SUR_CACHE) marquerChargement(PROFONDS, false);
      appliquer(PROFONDS, cacheDetail.get(clef) ?? null);
      return;
    }
    const demande = clef;
    marquerChargement(PROFONDS, true);
    const detail = await new Promise<TailleDetail | null>((resoudre) => {
      enVol.set(demande, resoudre);
    });
    cacheDetail.set(demande, detail);
    if (ILOT_PERIME_LES_REPONSES_EN_RETARD && monJeton !== jetonDemande) return;
    marquerChargement(PROFONDS, false);
    if (cleCacheDetail(cle, variante) === demande) appliquer(PROFONDS, detail);
  }

  /** Un clic de carte : la sélection change, puis le détail est demandé. */
  function choisir(c: string, v: 'sans' | 'avec'): Promise<void> {
    cle = c;
    variante = v;
    return chargerDetail();
  }

  /** Le réseau répond pour UNE demande précise, dans l'ordre que le test veut. */
  async function repondre(c: string, v: 'sans' | 'avec', detail: TailleDetail | null): Promise<void> {
    const resoudre = enVol.get(cleCacheDetail(c, v));
    expect(resoudre, `aucune requête en vol pour ${c}/${v}`).toBeTruthy();
    enVol.delete(cleCacheDetail(c, v));
    resoudre!(detail);
    // Laisser la continuation de `chargerDetail` se dérouler entièrement.
    await new Promise((r) => setTimeout(r, 0));
  }

  return { choisir, repondre };
}

describe('QJW19 — A lente + B rapide : seule la demande courante lève l’attente', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('à l’arrivée de A, `aria-busy` RESTE posé tant que B est en vol', async () => {
    const page = harnais();

    void page.choisir('eco', 'sans');   // A part
    void page.choisir('max', 'avec');   // B part, plus récente
    expect(occupees(), 'l’attente devrait être annoncée sur les cinq enveloppes')
      .toHaveLength(ENVELOPPES.length);

    await page.repondre('eco', 'sans', DETAIL_ECO);   // A revient EN RETARD

    expect(
      occupees(),
      'une réponse périmée a déclaré « chargé » des chapitres encore en vol',
    ).toHaveLength(ENVELOPPES.length);
    // …et ils sont bien encore MASQUÉS : la région annoncée stabilisée serait
    // vide. C'est le défaut exact que la tâche décrit.
    for (const sel of ENVELOPPES) {
      expect(document.querySelector<HTMLElement>(sel)!.hidden, `${sel} démasquée trop tôt`).toBe(true);
    }
  });

  it('au retour de B, l’attente tombe ET les chapitres redeviennent visibles', async () => {
    const page = harnais();

    void page.choisir('eco', 'sans');
    void page.choisir('max', 'avec');
    await page.repondre('eco', 'sans', DETAIL_ECO);
    await page.repondre('max', 'avec', DETAIL_MAX);

    expect(occupees()).toEqual([]);
    expect(document.querySelector<HTMLElement>('[data-detail-eco-bloc]')!.hidden).toBe(false);
    expect(document.querySelector<HTMLElement>('[data-detail-cumul-card]')!.hidden).toBe(false);
    // Et ce sont bien les nombres de B — jamais ceux de A, ni ceux du devis.
    expect(document.querySelector('[data-detail-cumul-value]')!.textContent).toBe('541 800 MAD');
    expect(document.querySelector('[data-detail-banque]')!.textContent)
      .toBe('Batterie · 6 × 5 kWh · 27 kWh utiles');
  });

  it('une réponse SEULE en vol lève l’attente normalement (la garde ne bloque rien)', async () => {
    const page = harnais();

    void page.choisir('eco', 'sans');
    expect(occupees()).toHaveLength(ENVELOPPES.length);

    await page.repondre('eco', 'sans', DETAIL_ECO);

    expect(occupees()).toEqual([]);
    expect(document.querySelector('[data-detail-cumul-value]')!.textContent).toBe('231 400 MAD');
  });

  it('un retour sur « Recommandé » pendant un appel en vol lève l’attente lui aussi', async () => {
    const page = harnais();

    void page.choisir('eco', 'sans');
    await page.choisir('recommande', 'sans');   // restauration, sans réseau

    expect(occupees(), '« Recommandé » restaure : il n’y a plus rien à attendre').toEqual([]);

    // …et la réponse en retard de la carte abandonnée ne repeint rien.
    await page.repondre('eco', 'sans', DETAIL_ECO);
    expect(occupees()).toEqual([]);
    expect(document.querySelector('[data-detail-cumul-value]')!.textContent).toBe('300 000 MAD');
  });

  it('un détail servi DEPUIS LE CACHE ne laisse pas un `aria-busy` collé', async () => {
    const page = harnais();

    // Éco est chargée une première fois : la voilà en cache.
    void page.choisir('eco', 'sans');
    await page.repondre('eco', 'sans', DETAIL_ECO);

    // Max part sur le réseau (attente annoncée), puis le client revient sur
    // Éco, servie sans réseau. La réponse de Max, désormais périmée, ne
    // touchera plus à l'attente : c'est donc au raccourci de la lever.
    void page.choisir('max', 'avec');
    expect(occupees()).toHaveLength(ENVELOPPES.length);
    await page.choisir('eco', 'sans');

    expect(occupees(), 'l’attente est restée collée sur des chapitres déjà affichés').toEqual([]);
    expect(document.querySelector<HTMLElement>('[data-detail-eco-bloc]')!.hidden).toBe(false);
  });
});
