/**
 * TAILLES (ordre fondateur, 26/08/2026) — « Explorer d'autres tailles ».
 *
 * Deux moitiés testées ici :
 *  1. la BIBLIOTHÈQUE (`src/lib/offresTailles.ts`), contre le CONTRAT lui-même
 *     (`apps/ventes/contract_samples/offres_tailles.json`) — pas contre un
 *     échantillon réécrit à la main, qui divergerait le jour où le backend bouge ;
 *  2. la PAGE, par assertions de chaîne sur le `.astro` (idiome de la maison),
 *     avec la version SANS COMMENTAIRES pour qu'un commentaire ne puisse jamais
 *     faire passer un test.
 *
 * L'épingle la plus importante du fichier est la DERNIÈRE section : la VUE PAR
 * DÉFAUT de la page doit rester celle d'aujourd'hui. C'est la contrainte dure du
 * fondateur, et c'est la seule qu'un refactor peut casser sans que rien d'autre
 * ne bronche.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  offresTailles,
  varianteAffichee,
  tailleParDefaut,
  peutSigner,
  messageDemandeTaille,
  cumulAnnuelServi,
  aUneDiffMateriel,
  FAMILLES_COMPARABLES,
} from '../src/lib/offresTailles';

const read = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const PAGE = read('../src/pages/proposition/[...token].astro').replace(/\r\n/g, '\n');
/** Le code SEUL : un commentaire ne doit jamais faire passer une assertion. */
const CODE = PAGE
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');

const CONTRAT = JSON.parse(
  read('../../../backend/django_core/apps/ventes/contract_samples/offres_tailles.json'),
);
const SERVI = CONTRAT.exemple;
const SERVI_SANS_BATTERIE = CONTRAT.exemple_sans_option_batterie;

/** Le bloc `#tailles` du gabarit, borné à ses propres frontières. */
function sectionTailles(source: string): string {
  const debut = source.indexOf('id="tailles"');
  expect(debut, 'la section #tailles doit exister').toBeGreaterThan(0);
  const fin = source.indexOf('id="options"', debut);
  expect(fin, '#options doit suivre #tailles').toBeGreaterThan(debut);
  return source.slice(debut, fin);
}

// ── 1. LA BIBLIOTHÈQUE, CONTRE LE CONTRAT ───────────────────────────────────

describe('offresTailles — lit le contrat, ne calcule rien', () => {
  it('lit les trois tailles de l’exemple servi, dans l’ordre du contrat', () => {
    const bloc = offresTailles(SERVI);
    expect(bloc).not.toBeNull();
    expect(bloc!.offres.map((t) => t.cle)).toEqual(['eco', 'recommande', 'max']);
    expect(bloc!.avecServable).toBe(true);
    expect(bloc!.horizonAnnees).toBe(25);
  });

  it('les nombres sont REPRIS tels quels du contrat — jamais un second arrondi', () => {
    const bloc = offresTailles(SERVI)!;
    const reco = bloc.offres.find((t) => t.cle === 'recommande')!;
    const servi = SERVI.offres_tailles.offres.find((o: { cle: string }) => o.cle === 'recommande');
    const v = varianteAffichee(reco, true)!;
    expect(v.prixTtc).toBe(servi.avec.prix_ttc);
    expect(v.prixParKwcTtc).toBe(servi.avec.prix_par_kwc_ttc);
    expect(v.economieAnnuelleMad).toBe(servi.avec.economie_annuelle_mad);
    expect(v.economiesCumulees25AnsMad).toBe(servi.avec.economies_cumulees_25_ans_mad);
    expect(v.couverturePct).toBe(servi.avec.couverture_pct);
    expect(v.batterie!.capaciteUtileKwh).toBe(servi.avec.batterie.capacite_utile_kwh);
  });

  it('sans option batterie servie : aucune bascule (avecServable faux)', () => {
    const bloc = offresTailles(SERVI_SANS_BATTERIE)!;
    expect(bloc.avecServable).toBe(false);
    expect(bloc.offres.every((t) => t.avec === null)).toBe(true);
  });

  it('clé absente ⇒ null (la section n’existe alors pas dans le DOM)', () => {
    expect(offresTailles({})).toBeNull();
    expect(offresTailles(null)).toBeNull();
    expect(offresTailles({ offres_tailles: null })).toBeNull();
    expect(offresTailles({ offres_tailles: { offres: 'pas un tableau' } })).toBeNull();
  });

  it('MOINS DE DEUX tailles ⇒ null : une comparaison à une carte n’explore rien', () => {
    const uneSeule = {
      offres_tailles: {
        avec_servable: false,
        offres: [SERVI.offres_tailles.offres[0]],
      },
    };
    expect(offresTailles(uneSeule)).toBeNull();
  });

  it('OMISSION — une variante sans panneaux NI prix est écartée, jamais rendue vide', () => {
    const creuse = {
      offres_tailles: {
        avec_servable: false,
        offres: [
          { cle: 'eco', titre: 'Éco', sans: { puissance_kwc: 7.7 } },
          SERVI.offres_tailles.offres[1],
        ],
      },
    };
    // La taille creuse tombe ⇒ il n'en reste qu'une ⇒ pas de section du tout.
    expect(offresTailles(creuse)).toBeNull();
  });

  it('OMISSION — un champ absent devient null, jamais un zéro fabriqué', () => {
    const bloc = offresTailles({
      offres_tailles: {
        avec_servable: false,
        offres: [
          { cle: 'eco', titre: 'Éco', sans: { nb_panneaux: 10 } },
          { cle: 'recommande', titre: 'Recommandé', est_le_devis: true, sans: { nb_panneaux: 14, prix_ttc: 71400 } },
        ],
      },
    })!;
    const eco = bloc.offres[0].sans!;
    expect(eco.prixTtc).toBeNull();
    expect(eco.economieAnnuelleMad).toBeNull();
    expect(eco.couverturePct).toBeNull();
    expect(eco.batterie).toBeNull();
    // …et surtout PAS un zéro.
    expect(eco.prixTtc).not.toBe(0);
  });

  it('ANTICOPIE — le vocabulaire des familles est BORNÉ à trois mots', () => {
    expect([...FAMILLES_COMPARABLES]).toEqual(['panneau', 'onduleur', 'batterie']);
    const bloc = offresTailles({
      offres_tailles: {
        avec_servable: false,
        offres: [
          {
            cle: 'eco', titre: 'Éco',
            sans: {
              nb_panneaux: 10, prix_ttc: 1,
              // Une famille de nomenclature ne doit JAMAIS franchir la frontière.
              familles: ['panneau', 'structure', 'transport', 'onduleur'],
              familles_diff: { ajoutees: ['cablage'], retirees: ['batterie'] },
            },
          },
          SERVI.offres_tailles.offres[1],
        ],
      },
    })!;
    const v = bloc.offres[0].sans!;
    expect(v.familles).toEqual(['panneau', 'onduleur']);
    expect(v.famillesDiff!.ajoutees).toEqual([]);
    expect(v.famillesDiff!.retirees).toEqual(['batterie']);
  });

  it('GARANTIE — publiée UNIQUEMENT quand la fiche la porte (_gar_de_la_fiche)', () => {
    const bloc = offresTailles(SERVI)!;
    const eco = bloc.offres.find((t) => t.cle === 'eco')!;
    const materiel = eco.sans!.materiel;
    const panneau = materiel.find((m) => m.role === 'panneau')!;
    const onduleur = materiel.find((m) => m.role === 'onduleur_hybride')!;
    expect(panneau.garantieAns).toBe(12);
    // Le contrat n'en sert pas pour cet onduleur : le champ est OMIS, pas à 0.
    expect(onduleur.garantieAns).toBeNull();
    // Marque + modèle sont TOUJOURS publiés (décision fondateur).
    expect(panneau.marque).toBe('Longi');
    expect(onduleur.modele).toBe('SUN-8K-SG05LP3');
  });

  it('la taille PAR DÉFAUT est celle du devis officiel', () => {
    const bloc = offresTailles(SERVI)!;
    expect(tailleParDefaut(bloc).cle).toBe('recommande');
    expect(tailleParDefaut(bloc).estLeDevis).toBe(true);
  });

  it('« ce qui change » est OMIS quand aucune taille ne porte de différence', () => {
    const bloc = offresTailles({
      offres_tailles: {
        avec_servable: false,
        offres: [
          { cle: 'eco', titre: 'Éco', sans: { nb_panneaux: 10, prix_ttc: 1 } },
          { cle: 'max', titre: 'Max', sans: { nb_panneaux: 20, prix_ttc: 2 } },
        ],
      },
    })!;
    expect(aUneDiffMateriel(bloc, false)).toBe(false);
    // …et présent dès qu'une taille en porte une (l'exemple du contrat).
    expect(aUneDiffMateriel(offresTailles(SERVI)!, false)).toBe(true);
  });

  it('ARTEFACTS PAR OPTION — absents aujourd’hui, et un faux SVG est refusé', () => {
    const bloc = offresTailles(SERVI)!;
    // Le contrat n'en sert aucun : la page garde ses artefacts uniques.
    expect(bloc.offres.every((t) => t.sans?.calepinageSvg == null)).toBe(true);
    const injecte = offresTailles({
      offres_tailles: {
        avec_servable: false,
        offres: [
          {
            cle: 'eco', titre: 'Éco',
            sans: {
              nb_panneaux: 1, prix_ttc: 1,
              calepinage_svg: '<img src=x onerror=alert(1)>',
              schema_svg: '<svg viewBox="0 0 1 1"></svg>',
            },
          },
          SERVI.offres_tailles.offres[1],
        ],
      },
    })!;
    expect(injecte.offres[0].sans!.calepinageSvg).toBeNull();
    expect(injecte.offres[0].sans!.schemaSvg).toContain('<svg');
  });
});

// ── 2. LA RÈGLE CTA (critique Fable) ────────────────────────────────────────

describe('peutSigner — le lien de signature n’existe que sur l’état OFFICIEL', () => {
  const bloc = offresTailles(SERVI)!;
  const reco = bloc.offres.find((t) => t.cle === 'recommande')!;
  const eco = bloc.offres.find((t) => t.cle === 'eco')!;
  const max = bloc.offres.find((t) => t.cle === 'max')!;

  it('OUI : la taille du devis, non ajustée, dans la variante retenue', () => {
    expect(peutSigner(reco, true, 'avec')).toBe(true);
  });

  it('NON : la même carte dans l’AUTRE variante (basculer quitte l’état officiel)', () => {
    expect(peutSigner(reco, false, 'avec')).toBe(false);
    expect(peutSigner(reco, true, 'sans')).toBe(false);
  });

  it('NON : une autre taille, quelle que soit la variante', () => {
    for (const t of [eco, max]) {
      expect(peutSigner(t, false, 'sans')).toBe(false);
      expect(peutSigner(t, true, 'avec')).toBe(false);
    }
  });

  it('NON : une taille AJUSTÉE à la main n’est plus le devis', () => {
    // `max` porte `ajuste: true` dans le contrat — et n'est de toute façon pas
    // le devis. On force le cas exact : devis + ajusté.
    const ajuste = { ...reco, ajuste: true };
    expect(peutSigner(ajuste, true, 'avec')).toBe(false);
  });

  it('NON : sans prix réel, il n’y a rien à signer', () => {
    const sansPrix = { ...reco, avec: { ...reco.avec!, prixTtc: null } };
    expect(peutSigner(sansPrix, true, 'avec')).toBe(false);
  });
});

describe('messageDemandeTaille — dit la CONFIGURATION demandée, jamais un prix', () => {
  const bloc = offresTailles(SERVI)!;
  const eco = bloc.offres.find((t) => t.cle === 'eco')!;

  it('nomme la taille, les panneaux, la puissance et la banque', () => {
    const msg = messageDemandeTaille(eco, true);
    expect(msg).toContain('Éco');
    expect(msg).toContain('16 panneaux');
    expect(msg).toContain('8.8 kWc');
    expect(msg).toContain('2 × 5 kWh de batterie');
  });

  it('dit « sans batterie » du côté sans, et ne cite AUCUN montant', () => {
    const msg = messageDemandeTaille(eco, false);
    expect(msg).toContain('sans batterie');
    for (const montant of ['71400', '71 400', 'MAD', '9840', 'DH']) {
      expect(msg, montant).not.toContain(montant);
    }
  });
});

// ── 3. LE CUMUL 25 ANS — LU, JAMAIS RECONSTRUIT ─────────────────────────────

describe('cumulAnnuelServi — lit la série que la page trace déjà', () => {
  it('lit `quote.cashflow_sans` / `cashflow_avec` telles quelles', () => {
    const payload = { quote: { cashflow_sans: [-50000, -40000, 10000], cashflow_avec: [-70000, -55000] } };
    expect(cumulAnnuelServi(payload, false)).toEqual([
      { annee: 1, cumuleMad: -50000 },
      { annee: 2, cumuleMad: -40000 },
      { annee: 3, cumuleMad: 10000 },
    ]);
    expect(cumulAnnuelServi(payload, true)).toHaveLength(2);
  });

  it('série absente / annulée par le backend ⇒ [] (aucun tableau rendu)', () => {
    expect(cumulAnnuelServi({ quote: {} }, false)).toEqual([]);
    expect(cumulAnnuelServi({ quote: { cashflow_avec: null } }, true)).toEqual([]);
    expect(cumulAnnuelServi({}, false)).toEqual([]);
    expect(cumulAnnuelServi(null, false)).toEqual([]);
  });

  it('une série TROUÉE s’arrête au trou — jamais une continuité inventée', () => {
    const trouee = { quote: { cashflow_sans: [-50000, null, 10000] } };
    expect(cumulAnnuelServi(trouee, false)).toEqual([{ annee: 1, cumuleMad: -50000 }]);
  });
});

// ── 4. LA PAGE — STRUCTURE ET DISCIPLINE ────────────────────────────────────

describe('[...token].astro — la section « Explorer d’autres tailles »', () => {
  it('branche la bibliothèque, et disparaît quand la clé n’est pas servie', () => {
    expect(CODE).toContain('offresTailles(data)');
    expect(CODE).toContain('{tailles && tailleDefaut && (');
  });

  it('est placée AVANT #options (les tailles décident, #options détaille)', () => {
    const tailles = PAGE.indexOf('id="tailles"');
    const options = PAGE.indexOf('id="options"');
    expect(tailles).toBeGreaterThan(0);
    expect(options).toBeGreaterThan(tailles);
  });

  it('le badge dit un FAIT vérifiable, jamais « populaire » ni une urgence', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('data-fr="Recommandé — c’est votre devis officiel"');
    // Interdits fondateur : badge de popularité, urgence fabriquée, prix barré.
    for (const mot of ['populaire', 'le plus choisi', 'offre limitée', 'plus que', 'best-seller']) {
      expect(bloc.toLowerCase(), mot).not.toContain(mot);
    }
  });

  it('UNE seule bascule, AU-DESSUS des cartes, pilotée par `avec_servable`', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('{tailles.avecServable && (');
    expect(bloc).toContain('data-tailles-switch');
    // Une seule : elle apparaît avant la grille de cartes, et il n'en existe
    // pas une par carte (le contre-modèle explicitement banni par le fondateur).
    expect((bloc.match(/data-tailles-switch/g) || []).length).toBe(1);
    expect(bloc.indexOf('data-tailles-switch')).toBeLessThan(bloc.indexOf('data-tailles-cartes'));
  });

  it('CTA : #signer UNIQUEMENT derrière `peutSigner`, sinon la demande de modification', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('peutSigner(t, avecBatterie, recoVariante)');
    // Le lien de signature vit dans la branche `signable ? ... : ...`, et nulle
    // part ailleurs dans la section.
    expect((bloc.match(/href="#signer"/g) || []).length).toBe(1);
    const signable = bloc.indexOf('{signable ? (');
    expect(signable).toBeGreaterThan(0);
    expect(bloc.indexOf('href="#signer"')).toBeGreaterThan(signable);
    // L'autre branche est la demande de modification, PRÉREMPLIE.
    expect(bloc).toContain('data-taille-cta="demander"');
    expect(bloc).toContain('data-taille-message={messageDemandeTaille(t, avecBatterie)}');
  });

  it('la demande passe par le flux EXISTANT — aucun second canal, aucun endpoint neuf', () => {
    const script = CODE.slice(CODE.indexOf('function setupTaillesOffres'));
    const corps = script.slice(0, script.indexOf('})();'));
    expect(corps).toContain('[data-revision-token]');
    expect(corps).toContain('data-revision-kind=');
    // Le script des tailles n'ouvre AUCUNE requête réseau.
    for (const interdit of ['fetch(', 'XMLHttpRequest', 'navigator.sendBeacon']) {
      expect(corps, interdit).not.toContain(interdit);
    }
  });

  it('ZÉRO CHIFFRE CALCULÉ CÔTÉ CLIENT : les deux variantes sont rendues au SERVEUR', () => {
    const bloc = sectionTailles(CODE);
    // Chaque carte rend ses deux variantes, l'une masquée — basculer n'est donc
    // qu'un show/hide, et un chiffre affiché NE PEUT PAS diverger d'un servi.
    expect(bloc).toContain('data-taille-bloc data-taille-variante={v}');
    expect(bloc).toContain('hidden={v !== tailleVarianteDefaut}');
    const script = CODE.slice(CODE.indexOf('function setupTaillesOffres'));
    const corps = script.slice(0, script.indexOf('})();'));
    // Aucun formatage monétaire, aucune arithmétique de montant dans le script.
    for (const interdit of ['formatMAD', 'formatNumber', 'formatPercent', 'toFixed', 'Math.round']) {
      expect(corps, interdit).not.toContain(interdit);
    }
  });

  it('la note d’hypothèse est AU-DESSUS des chiffres à 25 ans, et vient d’un drapeau SERVI', () => {
    const bloc = sectionTailles(CODE);
    expect(CODE).toContain('const tailleSansEscalade = tailles?.escaladeTarifairePct === 0;');
    expect(bloc).toContain('{tailleSansEscalade && (');
    expect(bloc).toContain('aucune hausse tarifaire supposée');
    // « au-dessus » n'est pas une figure de style : la note précède la grille.
    expect(bloc.indexOf('aucune hausse tarifaire supposée'))
      .toBeLessThan(bloc.indexOf('data-tailles-cartes'));
  });

  it('MOBILE — défilement horizontal à accroche, jamais un empilage qui tue la comparaison', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('snap-x');
    expect(bloc).toContain('snap-center');
    expect(bloc).toContain('overflow-x-auto');
    // …et la grille reprend dès `sm` (les trois cartes visibles d'un coup).
    expect(bloc).toContain('sm:grid-cols-3');
    // La bascule reste sous la main pendant le défilement.
    expect(bloc).toContain('sticky');
    // Le pré-centrage agit sur le CONTENEUR : `scrollIntoView` ferait sauter la
    // page entière au chargement (et casserait la vue par défaut).
    const script = CODE.slice(CODE.indexOf('function setupTaillesOffres'));
    const corps = script.slice(0, script.indexOf('})();'));
    expect(corps).toContain('scroller.scrollLeft =');
  });

  it('le tableau « ce qui change » ne nomme que des FAMILLES (anticopie)', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('data-tailles-comparatif');
    for (const interdit of ['prix_unit', 'prix_achat', 'quantite', 'nomenclature', 'calibre']) {
      expect(bloc, interdit).not.toContain(interdit);
    }
  });

  it('i18n — chaque nouvelle chaîne de la section porte ses TROIS langues', () => {
    const bloc = sectionTailles(PAGE);
    const fr = (bloc.match(/data-fr=/g) || []).length;
    const en = (bloc.match(/data-en=/g) || []).length;
    const ar = (bloc.match(/data-ar=/g) || []).length;
    expect(fr).toBeGreaterThan(20);
    expect(en).toBe(fr);
    expect(ar).toBe(fr);
    // Chaque `data-i18n` a bien un trio derrière lui.
    expect((bloc.match(/data-i18n/g) || []).length).toBeLessThanOrEqual(fr);
  });

  it('chaque nombre affiché est isolé en `dir="ltr"` (lecture arabe correcte)', () => {
    const bloc = sectionTailles(CODE);
    expect((bloc.match(/dir="ltr"/g) || []).length).toBeGreaterThan(8);
  });

  it('chaque élément interactif porte un point d’accroche `data-*` stable', () => {
    const bloc = sectionTailles(CODE);
    for (const hook of [
      'data-tailles', 'data-tailles-switch', 'data-tailles-variante',
      'data-tailles-cartes', 'data-taille-carte', 'data-taille-cle',
      'data-taille-bloc', 'data-taille-cta', 'data-taille-banc',
      'data-tailles-comparatif', 'data-taille-detail',
    ]) {
      expect(bloc, hook).toContain(hook);
    }
  });
});

// ── 5. #8 — LA VUE DE DÉTAIL, ET SON HONNÊTETÉ ──────────────────────────────

describe('#8 — vue de détail vivante', () => {
  it('UNE vue qui suit la sélection, jamais N pages statiques', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('data-taille-detail');
    expect(bloc).toContain('const estLEtatOfficiel = t.estLeDevis && !t.ajuste && v === recoVariante;');
  });

  it('quand la taille regardée n’est PAS le devis, la page le DIT', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('{estLEtatOfficiel ? (');
    expect(bloc).toContain('décrivent, eux, votre devis officiel');
  });

  it('les artefacts par option sont lus DÉFENSIVEMENT — absents, rien n’est rendu', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('{va?.calepinageSvg && (');
    expect(bloc).toContain('{va?.schemaSvg && (');
    // Aucun cadre vide, aucun « bientôt disponible ».
    for (const interdit of ['à venir', 'bientôt', 'coming soon', 'placeholder']) {
      expect(bloc.toLowerCase(), interdit).not.toContain(interdit.toLowerCase());
    }
  });
});

// ── 6. LA VUE PAR DÉFAUT DOIT RESTER CELLE D'AUJOURD'HUI ────────────────────
// C'est LA contrainte dure du fondateur, et la seule qu'un refactor peut casser
// en silence. On l'épingle des deux côtés : ce que la page CHOISIT au rendu, et
// ce que le script s'autorise à TOUCHER au chargement.

describe('PRÉSERVATION — un client qui ne touche à rien voit la page d’avant', () => {
  it('la sélection par défaut EST le devis officiel (taille ET variante)', () => {
    expect(CODE).toContain('const tailleDefaut: OffreTaille | null = tailles ? tailleParDefaut(tailles) : null;');
    // La variante par défaut suit `recoVariante` — la variante réellement
    // retenue au devis, déjà résolue par `reco` : jamais un second avis sur
    // « quelle option recommander ».
    expect(CODE).toContain("tailles?.avecServable && recoVariante === 'avec' ? 'avec' : 'sans'");
    expect(CODE).toContain('data-taille-cle-defaut={tailleDefaut.cle}');
    expect(CODE).toContain('data-taille-variante-defaut={tailleVarianteDefaut}');
  });

  it('le script des tailles ne touche QUE ses propres nœuds (+ deux chemins documentés)', () => {
    const script = CODE.slice(CODE.indexOf('function setupTaillesOffres'));
    const corps = script.slice(0, script.indexOf('})();'));
    // Les seules sorties de la section sont : le formulaire de modification
    // EXISTANT, et le curseur batterie via son helper dédié.
    const sorties = corps.match(/document\.(getElementById|querySelector|querySelectorAll)\([^)]*\)/g) || [];
    for (const sortie of sorties) {
      const autorise =
        sortie.includes('data-tailles')
        || sortie.includes('data-taille-')
        || sortie.includes('data-revision-token')
        || sortie.includes('revision-detail');
      expect(autorise, `sortie non autorisée : ${sortie}`).toBe(true);
    }
  });

  it('les blocs EXISTANTS gardent leurs valeurs rendues au serveur', () => {
    // Un échantillon des surfaces que la refonte aurait pu déplacer : elles
    // rendent toujours EXACTEMENT la même expression qu'avant.
    for (const pin of [
      'id="battery-sim-units">{batterySimInitialN}',
      'id="prod-battery-toggle"',
      'id="prop-fold-figures"',
      '<p class="fig fig-md lum mt-3" dir="ltr">{formatMAD(optionTtc(data!, opt))}</p>',
      'id="batt-tier-prix"',
      'id="signer"',
    ]) {
      expect(CODE, pin).toContain(pin);
    }
  });

  it('l’ancre historique #options et les autres ancres internes survivent', () => {
    for (const ancre of ['id="options"', 'id="production"', 'id="sld"', 'id="gammes"',
      'id="confiance"', 'id="faq"', 'id="etapes-suivantes"', 'id="tarif-falaise"']) {
      expect(CODE, ancre).toContain(ancre);
    }
  });
});

// ── 7. LIENS ERP — AUCUN CHEMIN TOKENISÉ N'A BOUGÉ ──────────────────────────
// Contrainte dure du fondateur (26/08) : « quand tu changes quoi que ce soit,
// n'oublie pas nos liens vers l'ERP ». Tout ce que cette page ÉMET doit continuer
// de pointer là où l'ERP et le PDF l'attendent.

describe('LIENS ERP — les chemins tokenisés émis par la page sont intacts', () => {
  it('les endpoints proxy same-origin n’ont pas bougé', () => {
    for (const endpoint of [
      "fetch('/api/proposition-contact'",
      '/api/proposition-accept',
      '/api/proposition-otp',
      '/api/proposition-track',
    ]) {
      expect(CODE, endpoint).toContain(endpoint);
    }
  });

  it('les endpoints backend passent toujours par leurs constructeurs testés', () => {
    expect(CODE).toContain('proposalEndpoint(API_BASE, token)');
    expect(CODE).toContain('proposalPdfEndpoint');
    // La base API reste la base canonique.
    expect(CODE).toContain("'https://api.taqinor.ma'");
  });

  it('le lien de suivi réutilise le MÊME token — aucun identifiant nouveau', () => {
    expect(CODE).toContain('/suivi/${encodeURIComponent(token)}');
    // Le token vient toujours du dernier segment de la route catch-all.
    expect(CODE).toContain('tokenFromSegments(');
  });

  it('la section des tailles n’émet AUCUN lien tokenisé de son cru', () => {
    const bloc = sectionTailles(CODE);
    for (const interdit of ['/api/', 'api.taqinor.ma', 'token=', '/proposition/']) {
      expect(bloc, interdit).not.toContain(interdit);
    }
  });
});
