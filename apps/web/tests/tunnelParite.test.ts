// @vitest-environment jsdom
//
// QJW6 / QJW21 — PARITÉ DES TROIS LOCALES DU TUNNEL « mon-toit ».
//
// CE QUE CES TESTS EXISTENT POUR ATTRAPER, ET POURQUOI LES AUTRES NE LE
// POUVAIENT PAS. Le tunnel a vécu en trois copies complètes (FR, EN, AR) avec
// chacune son `buildBody()`. Neuf réponses L-WEBT (`occupation_jour` + les
// équipements et leurs détails kW/créneau) et le jeton anti-fraude
// `appareilId` n'étaient collectés QUE sur la copie française — pendant des
// mois, sans un seul test rouge. Vérifié : les tests de locale existants
// épinglent chacun SA propre fonctionnalité par regex sur la source, donc
// aucun d'eux ne pouvait remarquer ce qu'une locale ne fait PAS.
//
// QJW21 — CE QUE CETTE GARDE NE VOYAIT TOUJOURS PAS. Jusqu'ici elle
// construisait un `etatComplet()` À LA MAIN puis appelait `construireCorps`
// trois fois : elle comparait donc trois fois la MÊME lecture, et ne pouvait
// pas voir la seule omission qu'elle existe pour attraper — une locale dont la
// page ne LIT jamais la nouvelle question (ou n'en porte pas le champ) restait
// verte. Désormais chaque locale part de SON PROPRE DOM : le lecteur réel des
// pages (`lireChampsDomTunnel`, src/lib/tunnel/lecture.ts — le même code que
// les trois `lireEtatTunnel()` exécutent) tourne sur un document peuplé à
// partir de CETTE source `.astro`, et ce sont les corps émis qui sont comparés.
// Un champ absent du seul DOM anglais fait donc rougir la garde (épinglé
// ci-dessous par un test négatif permanent).
//
// Les assertions :
//
//  (1) COMPORTEMENTALE — la seule qui compte. Le MÊME contexte de page donné
//      aux trois locales, mais CHACUNE lue depuis SON DOM, doit produire le
//      MÊME ENSEMBLE de clés. L'égalité d'ensembles échoue automatiquement dès
//      qu'un champ part dans une locale et pas dans une autre.
//
//  (2) STRUCTURELLE — le balisage, lui, RESTE par locale (la mise en page RTL
//      arabe diffère réellement). Chaque descripteur du registre qui porte un
//      `domId` doit donc voir son identifiant présent dans les TROIS sources
//      `.astro` : c'est ce qui attrape la dérive de balisage, exactement le
//      défaut qui a laissé les 16 identifiants L-WEBT absents des pages EN et
//      AR.
//
//  (3) L'exhaustivité i18n n'a besoin d'AUCUNE assertion ici : `LIBELLES` est
//      un `Record` sur l'union littérale des clés du registre (QJW4), donc une
//      clé sans ses trois traductions est déjà une erreur `tsc`.

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { CHAMPS_TUNNEL, DOM_IDS_TUNNEL, etatVide, type EtatTunnel } from '../src/lib/tunnel/champs';
import { validateLead } from '../src/lib/lead';
import { CHAMPS_DOM_TUNNEL, lireChampsDomTunnel, type ChampDomTunnel } from '../src/lib/tunnel/lecture';
import { construireCorps, type LocaleTunnel } from '../src/lib/tunnel/corps';
import { ERREURS } from '../src/lib/tunnel/i18n';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const SOURCES: Array<[LocaleTunnel, string]> = [
  ['fr', read('../src/pages/devis/mon-toit.astro')],
  ['en', read('../src/pages/en/devis/mon-toit.astro')],
  ['ar', read('../src/pages/ar/devis/mon-toit.astro')],
];

const LOCALES: LocaleTunnel[] = ['fr', 'en', 'ar'];

/**
 * LE CONTEXTE DE PAGE — tout ce qui ne vient PAS d'un élément identifié :
 * l'état interne des groupes de cartes, la carte, les jetons de session, le
 * tracking, le mode. Il est VOLONTAIREMENT identique pour les trois locales :
 * c'est le DOM qu'on fait varier, et lui seul. (`languePreferee` reste ici une
 * valeur commune : la page EN passe réellement `''`, une divergence VOULUE et
 * documentée dans EtatTunnel, qui n'a rien à voir avec l'omission traquée.)
 */
function contextePage(): Omit<EtatTunnel, keyof ReturnType<typeof lireChampsDomTunnel>> {
  const { ...vide } = etatVide();
  return {
    ...vide,
    adresseCarte: '',
    adresseSecours: '',
    mode: 'industriel',
    languePreferee: 'fr',
    factureProValeur: 4000,
    factureProUnite: 'mad',
    tarifProMadKwh: 1.2,
    tension: 'bt',
    activite: 'day',
    categorieCommerciale: 'hotel',
    equipes: '3x8',
    typeSurface: 'bac_acier',
    sourceEau: 'puits',
    uniteEau: 'm3h',
    regionAgricole: 'gharb-loukkos',
    creneauVisitePartie: 'matin',
    creneauVisiteSemaine: 'cette_semaine',
    occupationJour: 'present',
    // Jetons au FORMAT RÉEL : la liste blanche de lead.ts les valide (regex
    // clientRef `^[A-Z0-9-]{4,24}$`, jetons 8–64, appareilId = uuid v4). Des
    // valeurs bidon seraient écartées par le FORMAT, pas par la liste blanche,
    // et brouilleraient ce que la garde QJW22 mesure.
    clientRef: 'TQ-AB2C',
    idempotencyKey: 'a'.repeat(32),
    eventId: 'b'.repeat(32),
    appareilId: '3f0c1e8a-7b21-4a5e-9c3d-2b4f6a8e1d20',
    estimationAffichee: { kwc: 6.4, nbPanneaux: 9 },
    tracking: { utm_source: 'meta', fbclid: 'fb-1' },
    repereToit: { lat: 33.57, lng: -7.59 },
    // Contour PLAUSIBLE (Casablanca) : `cleanRoofOutline` borne les coordonnées
    // au Maroc — un triangle [1,2]/[3,4]/[5,6] serait rejeté par le FORMAT et
    // non par la liste blanche.
    contourToit: [[33.57, -7.59], [33.571, -7.59], [33.571, -7.589]],
  } as Omit<EtatTunnel, keyof ReturnType<typeof lireChampsDomTunnel>>;
}

/** Valeur de démonstration d'un champ lu au DOM — réaliste (le corps doit
 *  rester JUGEABLE par validateLead) et IDENTIQUE pour les trois locales. */
const VALEURS_TEXTE: Record<string, string> = {
  'mt-name': 'Reda Kasri',
  'mt-phone': '0612345678',
  'mt-email': 'reda@example.ma',
  'mt-city': 'Casablanca',
  'mt-bill': '1500-3000',
  'mt-raison-sociale': 'SARL Atlas',
  'mt-culture': 'avocatier',
  'mt-hp': '', // honeypot : vide, comme chez un visiteur humain
};

function valeurTexte(c: ChampDomTunnel): string {
  // 'soir' est la SEULE valeur commune aux quatre énumérations de créneau de
  // lead.ts (chauffe-eau, VE, clim, piscine) : une valeur hors énumération
  // serait écartée par le FORMAT, pas par la liste blanche, et fausserait ce
  // que mesure la garde QJW22.
  return VALEURS_TEXTE[c.domId] ?? (c.domId.endsWith('-creneau') ? 'soir' : 'x');
}

/**
 * Le DOM d'une locale, peuplé À PARTIR DE SA SOURCE : un champ que cette page
 * ne porte pas n'existe pas dans son document — exactement l'amputation que la
 * garde doit voir.
 */
function domPourSource(src: string): Document {
  const doc = document.implementation.createHTMLDocument('tunnel');
  for (const c of CHAMPS_DOM_TUNNEL) {
    if (!src.includes(`id="${c.domId}"`)) continue;
    const el = doc.createElement('input');
    el.id = c.domId;
    if (c.type === 'case') {
      el.type = 'checkbox';
      el.checked = true;
    } else if (c.type === 'nombre') {
      el.value = '12';
    } else {
      el.value = valeurTexte(c);
    }
    doc.body.appendChild(el);
  }
  return doc;
}

/** Le corps RÉELLEMENT émis par une locale : son DOM, lu par le lecteur des
 *  pages, puis le constructeur partagé. */
function corpsDeLocale(locale: LocaleTunnel, src: string) {
  const etat = { ...contextePage(), ...lireChampsDomTunnel(domPourSource(src)) } as EtatTunnel;
  return construireCorps(etat, { messages: ERREURS[locale] });
}

const clesEmises = (locale: LocaleTunnel, src: string): string[] => Object.keys(corpsDeLocale(locale, src).body).sort();

/**
 * QJW22 — LE CORPS QUI PART VRAIMENT AU WEBHOOK, c'est-à-dire APRÈS la liste
 * blanche. `capture-lead.ts` (comme simulate/preview-lead) ne transmet pas le
 * corps construit par le registre : il transmet `validateLead(corps).lead`.
 * Une clé correctement déclarée au registre mais jamais ajoutée à la liste
 * blanche de `lib/lead.ts` est donc SILENCIEUSEMENT JETÉE — et les assertions
 * de parité, qui portaient sur le corps d'AVANT, ne pouvaient structurellement
 * pas le voir.
 */
function clesApresListeBlanche(corps: Record<string, unknown>): string[] {
  const v = validateLead(corps);
  if (!v.ok) throw new Error(`corps refusé par validateLead : ${JSON.stringify(v.errors)}`);
  return Object.keys(v.lead).sort();
}

/**
 * Les clés du corps que `validateLead` RENOMME ou CONSOMME délibérément — la
 * seule liste d'exceptions autorisée. Tout le reste doit ressortir sous son
 * propre nom, sinon c'est une clé jetée en silence.
 */
const RENOMMEES: Record<string, string> = {
  phone: 'phoneE164',
  utm_source: 'utm',
  utm_medium: 'utm',
  utm_campaign: 'utm',
  utm_content: 'utm',
  utm_term: 'utm',
};

/**
 * La SEULE clé du tunnel qui doit être jetée : le honeypot. Il part au serveur
 * pour être JUGÉ (`isHoneypotTripped`) et ne doit jamais atteindre le CRM —
 * son absence de la liste blanche est le comportement voulu, pas un oubli.
 */
const JETEES_VOULUES = new Set(['website_url']);

/** Les clés du corps que la liste blanche a JETÉES (hors renommages connus). */
function clesJetees(corps: Record<string, unknown>): string[] {
  const survivantes = new Set(clesApresListeBlanche(corps));
  return Object.keys(corps)
    .filter((k) => !JETEES_VOULUES.has(k) && !survivantes.has(RENOMMEES[k] ?? k))
    .sort();
}

describe('QJW21 (1) — égalité d’ENSEMBLES des clés, chaque locale lue depuis SON DOM', () => {
  it('les trois pages émettent exactement les mêmes clés — APRÈS liste blanche', () => {
    // QJW22 — l'assertion porte désormais sur le corps RÉELLEMENT ÉMIS au
    // webhook (post-liste-blanche), pas seulement sur celui que le registre a
    // construit. Les deux sont vérifiés, dans cet ordre d'importance.
    const [refEmis, ...autresEmis] = SOURCES.map(([locale, src]) =>
      clesApresListeBlanche(corpsDeLocale(locale, src).body),
    );
    for (const [i, cles] of autresEmis.entries()) {
      expect(cles, `${SOURCES[i + 1][0]} (corps webhook)`).toEqual(refEmis);
    }

    const [reference, ...autres] = SOURCES.map(([locale, src]) => clesEmises(locale, src));
    for (const [i, cles] of autres.entries()) {
      expect(cles, `${SOURCES[i + 1][0]} (corps registre)`).toEqual(reference);
    }
  });

  it('un DOM VIDE aussi (le cas où rien n’a été répondu)', () => {
    const vide = document.implementation.createHTMLDocument('vide');
    const corps = LOCALES.map((l) =>
      Object.keys(
        construireCorps({ ...contextePage(), ...lireChampsDomTunnel(vide) } as EtatTunnel, { messages: ERREURS[l] })
          .body,
      ).sort(),
    );
    expect(corps[1], 'en').toEqual(corps[0]);
    expect(corps[2], 'ar').toEqual(corps[0]);
  });

  it('LE TEST NÉGATIF — un champ retiré du seul DOM anglais fait ROUGIR la garde', () => {
    // C'est la raison d'être de QJW21 : avant, l'état était construit à la main
    // et cette amputation passait inaperçue. Ici on ampute la source anglaise
    // (le champ ne sera donc pas dans son DOM) et on exige la divergence.
    const [, srcFr] = SOURCES[0];
    const [, srcEn] = SOURCES[1];
    const ampute = srcEn.replace('id="mt-equip-clim-kw"', 'id="mt-equip-clim-kw-RETIRE"');
    expect(ampute, 'la source anglaise devrait porter mt-equip-clim-kw').not.toBe(srcEn);
    expect(clesEmises('en', ampute)).not.toEqual(clesEmises('fr', srcFr));
  });

  it('les 16 clés L-WEBT et appareilId sont bien DANS cet ensemble commun', () => {
    // Ce sont exactement celles qu'aucun visiteur anglophone ou arabophone
    // n'alimentait avant QJW5.
    const cles = clesEmises('en', SOURCES[1][1]);
    for (const cle of [
      'occupation_jour',
      'equip_chauffe_eau_electrique', 'equip_chauffe_eau_kw', 'equip_chauffe_eau_creneau',
      'equip_voiture_electrique', 'equip_ve_km_semaine', 'equip_ve_chargeur_kw', 'equip_ve_creneau',
      'equip_clim', 'equip_clim_pieces', 'equip_clim_kw', 'equip_clim_creneau',
      'equip_piscine', 'equip_piscine_pompe_kw', 'equip_piscine_heures_jour', 'equip_piscine_creneau',
      'appareilId',
    ]) {
      expect(cles, cle).toContain(cle);
    }
  });

  it('la locale ne change QUE les messages d’erreur, jamais les clés', () => {
    // Un DOM vide : les trois locales refusent les mêmes champs, avec leurs
    // propres mots. Le corps, lui, reste identique clé pour clé.
    const vide = document.implementation.createHTMLDocument('vide');
    // Sans repère de carte : un GPS explicite rend la ville FACULTATIVE côté
    // validateLead — il n'y aurait alors aucune erreur `city` à traduire.
    const invalide = {
      ...contextePage(),
      ...lireChampsDomTunnel(vide),
      mode: 'residentiel',
      repereToit: null,
      contourToit: [],
    } as EtatTunnel;
    const rendus = LOCALES.map((l) => construireCorps(invalide, { messages: ERREURS[l] }));
    const champsEnErreur = rendus.map((r) => Object.keys(r.errors).sort());
    expect(champsEnErreur[1]).toEqual(champsEnErreur[0]);
    expect(champsEnErreur[2]).toEqual(champsEnErreur[0]);
    expect(Object.keys(rendus[1].body)).toEqual(Object.keys(rendus[0].body));
    // …et les mots, eux, diffèrent bien (sinon la couche i18n ne sert à rien).
    expect(rendus[1].errors.city).not.toBe(rendus[0].errors.city);
    expect(rendus[2].errors.city).not.toBe(rendus[0].errors.city);
  });
});

describe('QJW21 — les trois pages passent par LE MÊME lecteur de DOM', () => {
  it.each(SOURCES)('%s — appelle lireChampsDomTunnel(document) dans son lireEtatTunnel', (locale, src) => {
    expect(src, `${locale} : n'importe pas le lecteur partagé`).toContain("lib/tunnel/lecture'");
    expect(src, `${locale} : ne l'applique pas à son propre DOM`).toContain('lireChampsDomTunnel(document)');

    // …et n'a pas GARDÉ une lecture recopiée à côté (le défaut d'origine).
    // Portée : le corps de `lireEtatTunnel` SEUL — ces mêmes ids sont lus
    // légitimement ailleurs dans la page (estimation en direct, deeplink
    // WhatsApp), ce n'est pas de la duplication de LECTURE D'ÉTAT.
    const debut = src.indexOf('function lireEtatTunnel(): EtatTunnel {');
    expect(debut, `${locale} : lireEtatTunnel introuvable`).toBeGreaterThan(-1);
    const corps = src.slice(debut, src.indexOf('\n  }', debut));
    const recopies = CHAMPS_DOM_TUNNEL.filter((c) => corps.includes(`'${c.domId}'`)).map((c) => c.domId);
    expect(recopies, `${locale} : champs encore lus à la main dans lireEtatTunnel`).toEqual([]);
  });

  it('tout domId du registre est LU quelque part (sinon la question est morte)', () => {
    // Les seuls ids lus autrement que par la table : ceux dont la page tient
    // l'état dans une variable (groupe de cartes) et ne fait que MIROITER la
    // valeur dans un input caché.
    const LUS_PAR_LETAT_DE_PAGE = ['mt-occupation-jour'];
    const nonLus = DOM_IDS_TUNNEL.filter(
      (id) => !CHAMPS_DOM_TUNNEL.some((c) => c.domId === id) && !LUS_PAR_LETAT_DE_PAGE.includes(id),
    );
    expect(nonLus, 'ids déclarés au registre que personne ne lit').toEqual([]);
  });
});

describe('QJW22 — le registre du tunnel et la liste blanche de lead.ts sont APPARIÉS', () => {
  it('aucune clé émise par le registre n’est jetée en silence par la liste blanche', () => {
    // Le piège de maintenance : ajouter un champ au registre suffit à le faire
    // apparaître dans le corps construit, mais PAS à le faire arriver au CRM —
    // il faut aussi l'ajouter à la main dans `validateOptionalFields`. Sans
    // cette garde, l'oubli est invisible (les tests portaient sur le corps
    // d'AVANT liste blanche) et le champ disparaît sans une ligne de log.
    for (const [locale, src] of SOURCES) {
      const corps = corpsDeLocale(locale, src).body;
      expect(clesJetees(corps), `${locale} : clés du registre absentes du lead transmis`).toEqual([]);
    }
  });

  it('LE TEST NÉGATIF — une clé de registre absente de la liste blanche fait ROUGIR la garde', () => {
    // On simule EXACTEMENT l'oubli visé : une clé parfaitement formée dans le
    // corps du tunnel, qu'aucune ligne de `validateOptionalFields` ne connaît.
    const corps = corpsDeLocale('fr', SOURCES[0][1]).body;
    expect(clesJetees({ ...corps, champ_ajoute_au_registre: 'valeur' })).toEqual(['champ_ajoute_au_registre']);
  });

  it('les clés RENOMMÉES le sont volontairement, et sont toutes présentes sous leur nouveau nom', () => {
    const corps = corpsDeLocale('fr', SOURCES[0][1]).body;
    const survivantes = new Set(clesApresListeBlanche(corps));
    for (const [avant, apres] of Object.entries(RENOMMEES)) {
      if (!(avant in corps)) continue;
      expect(survivantes, `${avant} → ${apres}`).toContain(apres);
    }
  });

  it('le corps post-liste-blanche porte bien les réponses du tunnel (pas qu’un squelette)', () => {
    const cles = clesApresListeBlanche(corpsDeLocale('fr', SOURCES[0][1]).body);
    // Un échantillon transversal : identité, énergie, L-WEBT, jetons, carte.
    for (const cle of ['fullName', 'phoneE164', 'city', 'billRange', 'equip_clim_kw', 'appareilId', 'gpsLat']) {
      expect(cles, cle).toContain(cle);
    }
  });
});

describe('QJW6 (2) — chaque domId du registre existe dans les TROIS sources', () => {
  it.each(SOURCES)('%s — porte tous les identifiants du registre', (locale, src) => {
    const manquants = DOM_IDS_TUNNEL.filter((id) => !src.includes(`id="${id}"`));
    expect(manquants, `${locale} : identifiants absents du balisage`).toEqual([]);
  });

  it('le registre couvre bien les 16 identifiants L-WEBT', () => {
    for (const id of [
      'mt-occupation-jour',
      'mt-equip-chauffe-eau', 'mt-equip-chauffe-eau-kw', 'mt-equip-chauffe-eau-creneau',
      'mt-equip-ve', 'mt-equip-ve-km', 'mt-equip-ve-kw', 'mt-equip-ve-creneau',
      'mt-equip-clim', 'mt-equip-clim-pieces', 'mt-equip-clim-kw', 'mt-equip-clim-creneau',
      'mt-equip-piscine', 'mt-equip-piscine-kw', 'mt-equip-piscine-heures', 'mt-equip-piscine-creneau',
    ]) {
      expect(DOM_IDS_TUNNEL, id).toContain(id);
    }
  });
});

describe('QJW6 — plus aucune page ne construit son propre corps', () => {
  it.each(SOURCES)('%s — n’a plus de buildBody local et importe le module partagé', (locale, src) => {
    expect(src, `${locale} : un buildBody local subsiste`).not.toContain('function buildBody(');
    expect(src, `${locale} : dérivation de payload recopiée`).not.toContain('function resolveRoofType(');
    expect(src, `${locale} : dérivation de payload recopiée`).not.toContain('function resolveProBillRange(');
    expect(src, `${locale} : n'importe pas le constructeur partagé`)
      .toContain("lib/tunnel/corps'");
    expect(src).toContain('construireCorps(lireEtatTunnel()');
  });
});

describe('QJW6 — invariants du registre', () => {
  it('aucun webhookKey en double (deux champs ne peuvent pas se marcher dessus)', () => {
    const cles = CHAMPS_TUNNEL.map((c) => c.webhookKey);
    // `mt-water-need` alimente DEUX descripteurs (débit m³/h vs besoin m³/j),
    // mais sous deux webhookKey distinctes — c'est le domId qui se partage,
    // jamais la clé de sortie.
    expect(new Set(cles).size, `doublons : ${cles.filter((k, i) => cles.indexOf(k) !== i)}`)
      .toBe(cles.length);
  });

  it('aucune clé de registre en double', () => {
    const cles = CHAMPS_TUNNEL.map((c) => c.cle);
    expect(new Set(cles).size).toBe(cles.length);
  });

  it('aucun champ lu deux fois par la table de lecture', () => {
    const champs = CHAMPS_DOM_TUNNEL.map((c) => c.champ);
    expect(new Set(champs).size).toBe(champs.length);
    const ids = CHAMPS_DOM_TUNNEL.map((c) => c.domId);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
