// @vitest-environment jsdom
/**
 * QJW10 — LA GARDE DE COUVERTURE : le test qui aurait attrapé l'oubli du
 * tableau de trésorerie.
 *
 * L'INCIDENT, DOCUMENTÉ DANS LA PAGE ELLE-MÊME. Le tableau année par année
 * (`data-cumul-annuel`) était rendu au serveur depuis le DEVIS OFFICIEL, et
 * l'îlot ne le touchait pas : on cliquait « Éco », le grand chiffre du cumul
 * changeait, et les vingt-cinq lignes en dessous continuaient d'afficher la
 * série du Recommandé — des chiffres RÉELS attribués à la MAUVAISE offre. La
 * série de la taille servie existait pourtant déjà dans le contrat
 * (`cashflow.cumulative`) : elle n'était lue par personne. Il a fallu une revue
 * Fable pour la voir (commentaire « F2 (revue Fable 29/08/2026) »).
 *
 * POURQUOI AUCUN TEST NE POUVAIT L'ATTRAPER. Un CÂBLAGE ne s'énumère pas : on
 * ne peut pas demander à quatre fonctions écrites à la main « quels champs
 * connaissez-vous ? ». Depuis QJW7/QJW9, la page est pilotée par deux TABLES —
 * et une table, elle, s'énumère.
 *
 * CE QUE CETTE GARDE EXIGE. Pour CHAQUE clé feuille de
 * `src/contract_samples/taille_detail.json` : soit une liaison la LIT
 * réellement (son nom apparaît dans un `lire`), soit elle figure dans
 * `NON_AFFICHE` avec une RAISON ÉCRITE. Une clé de charge utile ajoutée demain
 * fait rougir ce fichier jusqu'à ce que quelqu'un décide, par écrit, de
 * l'afficher ou de ne pas l'afficher.
 *
 * CE QUE `NON_AFFICHE` VEUT DIRE, EXACTEMENT : « aucune liaison ne LIT cette
 * clé ». Ce n'est pas toujours « ce nombre n'est nulle part sur la page » : les
 * chiffres de TÊTE (prix, kWc, panneaux, production…) sont bien affichés, mais
 * ils sont RECOPIÉS du texte que le serveur a déjà rendu dans la carte — c'est
 * la parade au « 21 contre 22 », un seul chemin par nombre. Leur clé de payload
 * n'est donc délibérément pas lue, et la raison le dit.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { PROFONDS } from '../src/lib/proposition/liaisons';
import { appliquer, capturerOriginaux, restaurer } from '../src/lib/proposition/swap';
import { tailleDetail } from '../src/lib/tailleDetail';

const read = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const ECHANTILLON = JSON.parse(read('../src/contract_samples/taille_detail.json')) as Record<string, unknown>;
const LIAISONS = read('../src/lib/proposition/liaisons.ts').replace(/\r\n/g, '\n');

/** Les deux blocs du contrat qui sont des CHARGES UTILES, pas de la prose. */
const EXEMPLES = ['exemple', 'exemple_avec_batterie'] as const;

/**
 * Toutes les feuilles du document, en chemins pointés. Un TABLEAU est une
 * feuille (`valeurs[]`) : c'est la série entière qui est servie ou omise, pas
 * ses éléments un par un.
 */
function feuilles(noeud: unknown, prefixe: string, sortie: Set<string>): void {
  if (Array.isArray(noeud)) { sortie.add(`${prefixe}[]`); return; }
  if (noeud && typeof noeud === 'object') {
    for (const [k, v] of Object.entries(noeud as Record<string, unknown>)) {
      feuilles(v, prefixe ? `${prefixe}.${k}` : k, sortie);
    }
    return;
  }
  sortie.add(prefixe);
}

/** Les chemins de la CHARGE UTILE (union des deux exemples), sans leur préfixe. */
function cheminsPayload(): string[] {
  const out = new Set<string>();
  for (const ex of EXEMPLES) {
    const brut = new Set<string>();
    feuilles(ECHANTILLON[ex], '', brut);
    for (const p of brut) out.add(p);
  }
  return [...out].sort();
}

/** Les chemins qui ne sont PAS de la charge utile (documentation du contrat). */
function cheminsDocumentation(): string[] {
  const out = new Set<string>();
  for (const [k, v] of Object.entries(ECHANTILLON)) {
    if ((EXEMPLES as readonly string[]).includes(k)) continue;
    feuilles(v, k, out);
  }
  return [...out].sort();
}

/** `economies_cumulees_25_ans_mad` → `economiesCumulees25AnsMad`. */
function camel(snake: string): string {
  const [tete, ...reste] = snake.split('_');
  return (tete ?? '') + reste.map((m) => m.charAt(0).toUpperCase() + m.slice(1)).join('');
}

/**
 * LE CORPS DES `lire` — et RIEN d'autre. C'est là, et seulement là, qu'une
 * liaison consomme le contrat : chercher le nom d'une clé dans tout le module
 * ferait passer `cle` pour « lue » parce que chaque entrée de table porte un
 * champ `cle:`. La garde doit être précise pour valoir quelque chose.
 */
function corpsDesLire(): string {
  const morceaux: string[] = [];
  let i = LIAISONS.indexOf('lire(');
  while (i !== -1) {
    const fin = LIAISONS.indexOf('peindre(', i);
    morceaux.push(LIAISONS.slice(i, fin === -1 ? LIAISONS.length : fin));
    i = LIAISONS.indexOf('lire(', fin === -1 ? LIAISONS.length : fin);
  }
  return morceaux.join('\n');
}

const LIRE = corpsDesLire();

/** Une clé est LIÉE quand son nom, en camel, apparaît dans un `lire`. */
function estLiee(chemin: string): boolean {
  const feuille = chemin.replace(/\[\]$/, '').split('.').pop() ?? '';
  return new RegExp(String.raw`\b${camel(feuille)}\b`).test(LIRE);
}

/**
 * LES DÉCISIONS ÉCRITES. Chaque clé que AUCUNE liaison ne lit doit être ici,
 * avec la raison — c'est le prix à payer pour qu'un oubli devienne rouge.
 */
const NON_AFFICHE: Readonly<Record<string, string>> = {
  // ── Identité et contrôle du payload, pas des valeurs à afficher ──────────
  'cle': 'Identifiant de la taille. Il PILOTE le swap (quelle carte est chargée, quelle clé de cache) ; ce n’est pas un nombre à peindre.',
  'titre': 'Le libellé « Éco »/« Max » est déjà rendu par le serveur sur la carte et sur la vue de détail — le réécrire depuis le payload ferait deux sources pour un même mot.',
  'variante': 'Sans/avec batterie : la page connaît déjà la variante active (c’est elle qui l’a demandée), et le détail n’en porte qu’une.',
  'est_le_devis': 'Drapeau de contrôle : « Recommandé » n’a pas d’endpoint et se RESTAURE depuis les originaux. Rien à afficher.',

  // ── Chiffres de TÊTE : affichés, mais RECOPIÉS du texte de la carte ──────
  // La carte a été formatée au serveur avec les mêmes fonctions que le héros :
  // recopier son texte garantit qu'un chiffre de tête ne peut pas diverger
  // d'un chiffre de carte. Lire le payload en plus créerait un SECOND chemin
  // pour le même nombre — exactement le « 21 contre 22 » que la page évite.
  'carte.prix_ttc': 'Affiché en tête, mais RECOPIÉ du texte de la carte (liaison HERO `ttc`) — un seul chemin par nombre.',
  'carte.puissance_kwc': 'Affiché en tête, mais RECOPIÉ du texte de la carte (liaison HERO `kwc`).',
  'carte.nb_panneaux': 'Affiché en tête, mais RECOPIÉ du texte de la carte (liaison HERO `panneaux`).',
  'carte.production_annuelle_kwh': 'Affiché dans le chapitre production, mais RECOPIÉ du texte de la carte (liaison HERO `production`).',
  'carte.economie_annuelle_mad': 'Affiché en tête et dans le bandeau « Économie estimée / an », mais RECOPIÉ du texte de la carte (liaisons HERO `eco` et `eco_annuelle`).',

  // ── Servis par le contrat, mais la PAGE ne les rend nulle part ───────────
  'carte.prix_par_kwc_ttc': 'La page ne rend aucun prix au kWc dans les chapitres qui suivent la carte ; l’ajouter serait une décision de contenu, pas de câblage.',
  'carte.taux_autoconsommation_pct': 'Aucun bloc de la page ne rend le taux d’autoconsommation par taille : seule la COUVERTURE a son anneau. Deux pourcentages voisins côte à côte se confondent.',
  'carte.familles[]': 'Liste de familles de matériel : elle sert au rendu SERVEUR des cartes (comparatif, sections), jamais au swap client.',
  'carte.toit_ok': 'Faisabilité de la pose sur le toit : rendue par le serveur sur la carte concernée, pas un chapitre profond qui suivrait la sélection.',
  'carte.batterie.remplissage_ok': 'Drapeau de composition de la banque. La ligne « Batterie · N × X kWh · Y kWh utiles » ne prétend rien sur le remplissage ; afficher un « incomplet » sans le texte qui l’explique inquiéterait sans informer.',
  'economies_mensuelles.devise': 'MAD est déjà dans le texte formaté par `formatMAD` : l’imprimer une seconde fois donnerait « 640 MAD MAD ».',
  'cashflow.horizon_annees': 'L’horizon est LU dans la longueur de la série repeinte (une ligne par année) — l’écrire en plus serait un second chiffre pour la même chose.',
  'cashflow.escalade_tarifaire_pct': 'Vaut 0 : projection à tarif PLAT. La page imprime déjà « aucune hausse tarifaire supposée » au-dessus du tableau, en texte rendu au serveur.',

  // ── La documentation du contrat : jamais servie à un navigateur ──────────
  'endpoint': 'Documentation du contrat : la route elle-même, pas une donnée.',
  'pourquoi': 'Documentation du contrat : la raison d’être de l’endpoint.',
  'notes.recommande_n_a_pas_d_endpoint': 'Note de contrat (documentation).',
  'notes.derivation': 'Note de contrat (documentation).',
  'notes.economies_mensuelles': 'Note de contrat (documentation).',
  'notes.cashflow': 'Note de contrat (documentation).',
  'notes.batterie': 'Note de contrat (documentation).',
  'notes.omission': 'Note de contrat (documentation).',
  'notes.gating': 'Note de contrat (documentation).',
  'notes.niveau': 'Note de contrat (documentation).',
  'notes.lecture_pure': 'Note de contrat (documentation).',
  'notes.cout': 'Note de contrat (documentation).',
  'exemple_404.commentaire': 'Documentation du refus 404 : la page traite indistinctement tout échec.',
};

describe('QJW10 — chaque clé du contrat est soit LIÉE, soit REFUSÉE par écrit', () => {
  const PAYLOAD = cheminsPayload();
  const DOCUMENTATION = cheminsDocumentation();

  it('l’échantillon est bien lu et non vide (une garde sur zéro clé ne garde rien)', () => {
    expect(PAYLOAD.length).toBeGreaterThan(20);
    expect(DOCUMENTATION.length).toBeGreaterThan(5);
    expect(LIRE.length).toBeGreaterThan(200);
  });

  it('CHAQUE clé feuille de la charge utile est liée OU justifiée par écrit', () => {
    const orphelines: string[] = [];
    for (const chemin of PAYLOAD) {
      if (estLiee(chemin)) continue;
      if (NON_AFFICHE[chemin]) continue;
      orphelines.push(chemin);
    }
    expect(
      orphelines,
      `clé(s) du contrat sans décision — les lier dans HERO/PROFONDS, ou les ajouter à NON_AFFICHE avec une raison ÉCRITE : ${orphelines.join(', ')}`,
    ).toEqual([]);
  });

  it('CHAQUE clé de la documentation du contrat est justifiée par écrit', () => {
    const orphelines = DOCUMENTATION.filter((c) => !NON_AFFICHE[c]);
    expect(orphelines, `documentation sans décision : ${orphelines.join(', ')}`).toEqual([]);
  });

  it('les six chapitres profonds LISENT bien leur clé du contrat', () => {
    for (const chemin of [
      'economies_mensuelles.valeurs[]', 'economies_mensuelles.total',
      'carte.batterie.nb_modules', 'carte.batterie.module_kwh', 'carte.batterie.capacite_utile_kwh',
      'carte.couverture_pct', 'carte.economies_cumulees_25_ans_mad', 'carte.payback_annees',
      'cashflow.cumulative[]',
    ]) {
      expect(estLiee(chemin), `${chemin} devrait être LUE par une liaison`).toBe(true);
      expect(NON_AFFICHE[chemin], `${chemin} ne peut pas être à la fois lue et refusée`).toBeUndefined();
    }
  });

  it('AUCUNE justification périmée : toute clé de NON_AFFICHE existe encore dans le contrat', () => {
    const connues = new Set([...PAYLOAD, ...DOCUMENTATION]);
    const perimees = Object.keys(NON_AFFICHE).filter((c) => !connues.has(c));
    expect(
      perimees,
      `justification(s) sans clé correspondante — le contrat a bougé : ${perimees.join(', ')}`,
    ).toEqual([]);
  });

  it('chaque raison est une VRAIE phrase, pas un « n/a » qui vide la garde de son sens', () => {
    for (const [cle, raison] of Object.entries(NON_AFFICHE)) {
      expect(raison.length, `${cle} : raison trop courte`).toBeGreaterThan(30);
      expect(raison, `${cle} : raison vide de contenu`).not.toMatch(/^(?:n\/a|na|tbd|todo|—|-)\.?$/i);
    }
  });
});

// ── LES DEUX TABLES ELLES-MÊMES ─────────────────────────────────────────────

describe('QJW10 — les tables restent celles que la page attend', () => {
  it('HERO déclare sept lignes, dont deux mutuellement exclusives sur `siKind`', () => {
    const bloc = LIAISONS.slice(
      LIAISONS.indexOf('export const HERO'),
      LIAISONS.indexOf('export interface ContexteHero'),
    );
    expect((bloc.match(/^\s{4}cle: '/gm) || [])).toHaveLength(7);
    expect((bloc.match(/siKind: '/g) || [])).toHaveLength(2);
  });

  it('PROFONDS déclare six chapitres, chacun avec son enveloppe', () => {
    const bloc = LIAISONS.slice(LIAISONS.indexOf('export const PROFONDS'));
    expect((bloc.match(/profond</g) || [])).toHaveLength(6);
    expect((bloc.match(/^\s{4}enveloppe: '/gm) || [])).toHaveLength(6);
  });
});

// ── QJW17 — LE BLOC « TOTAL AVEC » N'EST PAS DU TEXTE, C'EST UNE STRUCTURE ──
//
// L'INCIDENT. `[data-detail-eco-total-avec-bloc]` (page `[...token].astro`)
// contient DEUX `<span>` : l'étiquette traduisible `data-i18n` et le montant
// stylé `dir="ltr"`. Il était déclaré avec la capture par DÉFAUT (`texte`),
// donc `swap.reposer` le restaurait par `el.textContent = …` — ce qui DÉTRUIT
// ses enfants.
//
// POURQUOI C'ÉTAIT VISIBLE DÈS LE PREMIER AFFICHAGE, ET PAS SEULEMENT APRÈS
// UN ALLER-RETOUR. `restaurer` tourne AU CHARGEMENT : `appliquer()` (fin de
// l'îlot) → `chargerDetail()` → `restaurerDetail()`. Et il tourne APRÈS
// `prepareI18n()`, qui a remplacé chaque nœud `data-i18n` par un TRIPLET de
// `<span>` (FR visible, EN et AR masqués). Le `textContent` moissonné
// contenait donc DÉJÀ les trois langues bout à bout : l'aplatir les rendait
// toutes les trois visibles — « · avec batterie :· with a battery:· مع
// بطارية: » — et emportait au passage le crochet de traduction, si bien que
// le sélecteur FR/EN/عربي ne pilotait plus ce bloc.
//
// LA GARANTIE RÉPARÉE. « Identité byte-à-byte après un aller-retour »
// (annoncée en tête de `liaisons.ts` et dans la page) est de nouveau vraie
// pour ce bloc : la capture `fragment` mémorise les nœuds enfants EUX-MÊMES —
// jamais des clones, sinon le triplet i18n rebranché serait un triplet
// FANTÔME que la bascule de langue ne toucherait plus.

/** Le triplet que `prepareI18n` fabrique pour un nœud `data-i18n`. */
interface Triplet { fr: HTMLElement; en: HTMLElement; ar: HTMLElement }

/** Le MÊME geste que `prepareI18n()` de la page — reproduit, pas approximé. */
function preparerI18n(racine: ParentNode): Triplet[] {
  const triplets: Triplet[] = [];
  racine.querySelectorAll<HTMLElement>('[data-i18n]').forEach((el) => {
    const arText = el.dataset.ar;
    if (typeof arText !== 'string') return;
    const enText = typeof el.dataset.en === 'string' ? el.dataset.en : el.innerHTML;
    const frSpan = document.createElement('span');
    frSpan.innerHTML = el.innerHTML;
    const enSpan = document.createElement('span');
    enSpan.textContent = enText;
    enSpan.hidden = true;
    const arSpan = document.createElement('span');
    arSpan.textContent = arText;
    arSpan.hidden = true;
    el.textContent = '';
    el.append(frSpan, enSpan, arSpan);
    triplets.push({ fr: frSpan, en: enSpan, ar: arSpan });
  });
  return triplets;
}

/** Le MÊME geste que `applyLang()` : on montre une langue, on masque les deux autres. */
function basculer(triplets: readonly Triplet[], lang: 'fr' | 'en' | 'ar'): void {
  for (const { fr, en, ar } of triplets) {
    fr.hidden = lang !== 'fr';
    en.hidden = lang !== 'en';
    ar.hidden = lang !== 'ar';
  }
}

/** Ce que le CLIENT lit réellement : le texte des nœuds non masqués. */
function texteVisible(el: Element): string {
  let out = '';
  el.childNodes.forEach((n) => {
    if (n.nodeType === 3) { out += n.textContent ?? ''; return; }
    if (n.nodeType !== 1) return;
    if (n instanceof HTMLElement && n.hidden) return;
    out += texteVisible(n as Element);
  });
  return out;
}

/** Le bloc des économies mensuelles, tel que le serveur le rend (extrait fidèle). */
const ECO_HTML = `
  <div data-detail-eco-bloc>
    <p class="mt-3 text-sm text-lune-soft">
      <span data-i18n data-fr="Total annuel estimé :" data-en="Estimated annual total:" data-ar="المجموع السنوي المقدّر:">Total annuel estimé :</span>
      <span class="font-semibold text-lune" dir="ltr" data-detail-eco-total>11 430 MAD</span>
      <span data-detail-eco-total-avec-bloc> <span data-i18n data-fr="· avec batterie :" data-en="· with a battery:" data-ar="· مع بطارية:">· avec batterie :</span> <span class="font-semibold text-brass-300" dir="ltr">14 950 MAD</span></span>
    </p>
    <p class="mt-2 text-xs text-lune-faint" data-detail-banque hidden></p>
  </div>
`;

describe('QJW17 — la restauration du bloc « total avec » PRÉSERVE ses nœuds enfants', () => {
  function monter(): { triplets: Triplet[]; bloc: HTMLElement } {
    document.body.innerHTML = ECO_HTML;
    const triplets = preparerI18n(document);
    return {
      triplets,
      bloc: document.querySelector<HTMLElement>('[data-detail-eco-total-avec-bloc]')!,
    };
  }

  it('les deux <span> enfants survivent, et le DOM revient à l’OCTET', () => {
    const { bloc } = monter();
    const avant = bloc.innerHTML;
    const originaux = capturerOriginaux(PROFONDS);

    restaurer(PROFONDS, originaux);

    expect(bloc.querySelectorAll(':scope > span')).toHaveLength(2);
    expect(bloc.querySelector('[data-i18n]'), 'le crochet de traduction a disparu').not.toBeNull();
    expect(bloc.innerHTML).toBe(avant);
  });

  it('le client ne lit PAS les trois langues mélangées après restauration', () => {
    const { bloc } = monter();
    const originaux = capturerOriginaux(PROFONDS);

    restaurer(PROFONDS, originaux);

    const vu = texteVisible(bloc);
    expect(vu).toContain('· avec batterie :');
    expect(vu, 'l’anglais est visible sous la page française').not.toContain('· with a battery:');
    expect(vu, 'l’arabe est visible sous la page française').not.toContain('· مع بطارية:');
  });

  it('la bascule FR/EN/عربي pilote ENCORE ce bloc après restauration', () => {
    const { triplets, bloc } = monter();
    const originaux = capturerOriginaux(PROFONDS);

    restaurer(PROFONDS, originaux);

    basculer(triplets, 'en');
    expect(texteVisible(bloc)).toContain('· with a battery:');
    expect(texteVisible(bloc)).not.toContain('· avec batterie :');
    basculer(triplets, 'ar');
    expect(texteVisible(bloc)).toContain('· مع بطارية:');
    basculer(triplets, 'fr');
    expect(texteVisible(bloc)).toContain('· avec batterie :');
    expect(texteVisible(bloc)).not.toContain('· with a battery:');
  });

  it('un aller-retour COMPLET (détail servi puis « Recommandé ») revient aussi à l’octet', () => {
    monter();
    const avant = document.body.innerHTML;
    const originaux = capturerOriginaux(PROFONDS);

    // Un détail servi masque le total « avec » (c'est une AUTRE variante)…
    appliquer(PROFONDS, tailleDetail(ECHANTILLON.exemple));
    expect(document.body.innerHTML).not.toBe(avant);

    // …et le retour sur « Recommandé » le repose EXACTEMENT tel quel.
    restaurer(PROFONDS, originaux);
    expect(document.body.innerHTML).toBe(avant);
  });
});

// ── QJW18 — L'ARC ET LE CHIFFRE DÉCRIVENT LA MÊME TAILLE ────────────────────
//
// L'INCIDENT. Le nombre au centre de l'anneau de couverture est un `<text>`
// SVG. La liaison le récupérait par `unHtml`, qui exige un `HTMLElement` — or
// un nœud SVG est un `SVGElement` : le helper rendait `null` et la peinture
// était SILENCIEUSEMENT sautée. L'arc, lui, passait par `unEl` et se
// redessinait correctement. Résultat sous les yeux du client : l'ANNEAU décrit
// la taille chargée pendant que le CHIFFRE au milieu garde le pourcentage du
// devis officiel — deux chiffres contradictoires dans la même figure.
//
// POURQUOI AUCUN TEST NE L'AVAIT VU. Le DOM de test écrivait le `<text>` À
// CÔTÉ du `<svg>`, pas DEDANS : hors contenu étranger, l'analyseur HTML en
// fait un `HTMLUnknownElement`… qui EST un `HTMLElement`. Le helper rendait
// donc un nœud, la peinture avait lieu, et le test était vert sur une
// structure que la page n'a jamais rendue. Le DOM ci-dessous met le `<text>`
// DANS le `<svg>`, comme la page (`[...token].astro` ~4384-4393), et la
// première assertion VÉRIFIE cette nature : sans elle, la garde retomberait
// dans le même faux vert au moindre copier-coller.

/** L'anneau, tel que le serveur le rend : le `<text>` est DANS le `<svg>`. */
const DONUT_HTML = `
  <div class="flex items-center gap-4" data-hero-couverture-card>
    <svg viewBox="0 0 100 100" width="112" height="112" role="img" aria-label="Couverture solaire : 62 %">
      <circle cx="50" cy="50" r="42" fill="none" stroke-width="10"></circle>
      <circle cx="50" cy="50" r="42" fill="none" stroke-width="10" stroke-linecap="round"
        stroke-dasharray="163.72 100.16" transform="rotate(-90 50 50)"
        data-detail-couverture-arc data-detail-donut-r="42"></circle>
      <text x="50" y="50" text-anchor="middle" dominant-baseline="central"
        font-size="24" font-weight="700" dir="ltr" data-detail-couverture-value>62%</text>
    </svg>
  </div>
`;

/** Le pourcentage que l'ARC dessine réellement, relu depuis sa géométrie. */
function pctDeLArc(arc: Element): number {
  const rayon = Number(arc.getAttribute('data-detail-donut-r'));
  const dash = Number((arc.getAttribute('stroke-dasharray') ?? '').split(/\s+/)[0]);
  return (dash / (2 * Math.PI * rayon)) * 100;
}

/** L'entier que le CHIFFRE affiche, relu depuis son texte. */
function pctDuChiffre(el: Element): number {
  return Number((el.textContent ?? '').replace(/[^\d]/g, ''));
}

describe('QJW18 — le pourcentage DANS l’anneau suit la taille chargée', () => {
  const arc = (): Element => document.querySelector('[data-detail-couverture-arc]')!;
  const chiffre = (): Element => document.querySelector('[data-detail-couverture-value]')!;

  function monterDonut(): void {
    document.body.innerHTML = DONUT_HTML;
  }

  it('le nœud du chiffre est bien un `<text>` SVG (et NON un HTMLElement)', () => {
    monterDonut();
    // La garde qui empêche le faux vert de revenir : si un jour ce nœud
    // redevenait un HTMLElement, c'est que le DOM de test aurait cessé de
    // ressembler à la page.
    expect(chiffre().namespaceURI).toBe('http://www.w3.org/2000/svg');
    expect(chiffre() instanceof HTMLElement).toBe(false);
  });

  it('une taille chargée repeint l’ARC **et** le CHIFFRE', () => {
    monterDonut();
    capturerOriginaux(PROFONDS);

    appliquer(PROFONDS, tailleDetail(ECHANTILLON.exemple));

    expect(document.querySelector<HTMLElement>('[data-hero-couverture-card]')!.hidden).toBe(false);
    expect(arc().getAttribute('stroke-dasharray')).not.toBe('163.72 100.16');
    expect(chiffre().textContent, 'le chiffre est resté sur le pourcentage du devis officiel')
      .toBe('48 %');
  });

  it('arc et chiffre décrivent LA MÊME taille, pas deux', () => {
    monterDonut();
    capturerOriginaux(PROFONDS);

    for (const exemple of [ECHANTILLON.exemple, ECHANTILLON.exemple_avec_batterie]) {
      appliquer(PROFONDS, tailleDetail(exemple));
      expect(
        Math.round(pctDeLArc(arc())),
        'l’anneau et le nombre au centre annoncent deux tailles différentes',
      ).toBe(pctDuChiffre(chiffre()));
    }
  });

  it('un aller-retour repose l’arc ET le chiffre du devis officiel, à l’octet', () => {
    monterDonut();
    const avant = document.body.innerHTML;
    const originaux = capturerOriginaux(PROFONDS);

    appliquer(PROFONDS, tailleDetail(ECHANTILLON.exemple));
    expect(document.body.innerHTML).not.toBe(avant);

    restaurer(PROFONDS, originaux);
    expect(document.body.innerHTML).toBe(avant);
  });

  it('sans pourcentage servi, le chiffre est OMIS — jamais un faux repeint', () => {
    monterDonut();
    capturerOriginaux(PROFONDS);

    // Le contrat ne sert PAS `carte.couverture_pct` : la carte entière
    // disparaît, et le chiffre du devis officiel n'est ni réécrit ni resservi
    // sous une autre offre — il reste intact, MASQUÉ avec son enveloppe.
    const sansCouverture = tailleDetail({
      cle: 'eco', titre: 'Éco', variante: 'sans', est_le_devis: false,
      carte: { prix_ttc: 71400 },
    });
    expect(sansCouverture!.carte!.couverturePct).toBeNull();

    appliquer(PROFONDS, sansCouverture);

    expect(document.querySelector<HTMLElement>('[data-hero-couverture-card]')!.hidden).toBe(true);
    expect(chiffre().textContent).toBe('62%');
    expect(arc().getAttribute('stroke-dasharray')).toBe('163.72 100.16');
  });
});
