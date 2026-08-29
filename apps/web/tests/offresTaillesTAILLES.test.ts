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
  FAMILLE_LABELS,
  calepinageOptions,
  dessinDeLOption,
  sldDecritLOption,
  parametresSite,
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

/** CORRECTION #8 — le contrat du DESSIN par option, chargé depuis le fichier
 *  comme le font les tests backend : un échantillon recopié à la main
 *  divergerait le jour où le backend bouge, et c'est précisément cette
 *  divergence qui a fait inventer des clés `calepinage_svg` inexistantes. */
const CONTRAT_CALEP = JSON.parse(
  read('../../../backend/django_core/apps/ventes/contract_samples/calepinage_options.json'),
);
const CALEP = CONTRAT_CALEP.exemple;

/** Le bloc `#tailles` du gabarit, borné à ses PROPRES frontières.
 *
 * LA BORNE EST LA BALISE FERMANTE DE LA SECTION, PAS LA SECTION SUIVANTE.
 * Elle était `id="options"` — ce qui marchait tant que `#tailles` vivait juste
 * au-dessus de lui. Depuis que l'aperçu remonte SOUS LE HÉROS (fondateur,
 * 26/08/2026), une borne « jusqu'à #options » avalerait tout ce qui les sépare
 * désormais : calepinage, installation, production, économies, schéma,
 * confiance, FAQ. Toutes les assertions NÉGATIVES de ce fichier (« ce bloc ne
 * contient pas “populaire” ») et tous ses comptes d'occurrences seraient alors
 * évalués sur la moitié de la page — verts ou rouges pour de mauvaises raisons.
 *
 * `#tailles` ne contient AUCUNE `<section>` imbriquée (des `div` et une table),
 * donc le premier `</section>` qui suit son ouverture EST le sien. La borne ne
 * dépend plus de la position de la section dans la page. */
function sectionTailles(source: string): string {
  const debut = source.indexOf('id="tailles"');
  expect(debut, 'la section #tailles doit exister').toBeGreaterThan(0);
  const fin = source.indexOf('</section>', debut);
  expect(fin, '#tailles doit se refermer').toBeGreaterThan(debut);
  expect(
    source.slice(debut, fin).includes('<section'),
    '#tailles ne doit pas contenir de <section> imbriquée (la borne en dépend)',
  ).toBe(false);
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

  // (Les DESSINS par option ne vivent pas sur `offres_tailles` : ils ont leur
  //  propre clé racine `calepinage_options`, testée plus bas contre SON contrat.
  //  Un premier passage de cette lane avait deviné des champs `calepinage_svg` /
  //  `schema_svg` sur la variante : ils n'ont jamais existé — le backend ne rend
  //  AUCUN SVG de calepinage, le calepinage client EST la visionneuse WebGL.)
  it('une variante ne porte AUCUN champ de dessin — le dessin a sa propre clé', () => {
    const v = offresTailles(SERVI)!.offres[0].sans!;
    expect(v).not.toHaveProperty('calepinageSvg');
    expect(v).not.toHaveProperty('schemaSvg');
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

  // TROU DÉFENSIF (corrigé le 26/08) — `varianteAffichee` se rabat volontairement
  // sur l'autre variante quand celle demandée manque : c'est le bon
  // comportement pour AFFICHER une carte, mais un mensonge sous un bouton de
  // signature. Sur une carte « avec » incomplète, le repli aurait montré le prix
  // SANS batterie au-dessus d'« aller à la signature ».
  it('NON : la variante demandée n’existe pas — le repli ne doit JAMAIS signer', () => {
    const avecManquante = { ...reco, avec: null };
    expect(peutSigner(avecManquante, true, 'avec')).toBe(false);
    const sansManquante = { ...reco, estLeDevis: true, sans: null };
    expect(peutSigner(sansManquante, false, 'sans')).toBe(false);
    // …alors que l'AFFICHAGE, lui, se rabat toujours (comportement voulu).
    expect(varianteAffichee(avecManquante, true)).not.toBeNull();
  });
});

describe('FAMILLE_LABELS — les familles sont TRADUITES, jamais rendues brutes', () => {
  it('chaque famille du vocabulaire borné a ses trois langues', () => {
    for (const f of FAMILLES_COMPARABLES) {
      const l = FAMILLE_LABELS[f];
      expect(l, f).toBeTruthy();
      for (const langue of ['fr', 'en', 'ar'] as const) {
        expect(l[langue].trim().length, `${f}.${langue}`).toBeGreaterThan(0);
      }
      // L'anglais et l'arabe ne recopient pas le français : « − batterie » sous
      // les yeux d'un anglophone était exactement le défaut corrigé.
      expect(l.en, f).not.toBe(l.fr);
      expect(l.ar, f).not.toBe(l.fr);
      // L'arabe ne doit contenir AUCUN caractère latin.
      expect(/[A-Za-z]/.test(l.ar), `${f}.ar contient du latin`).toBe(false);
    }
  });

  it('la table est fermée sur le vocabulaire borné (aucune famille orpheline)', () => {
    expect(Object.keys(FAMILLE_LABELS).sort()).toEqual([...FAMILLES_COMPARABLES].sort());
  });

  it('la ligne « Matériel » du tableau rend les libellés, pas les clés de contrat', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('FAMILLE_LABELS[f].fr');
    expect(bloc).toContain('FAMILLE_LABELS[f].en');
    expect(bloc).toContain('FAMILLE_LABELS[f].ar');
    // La clé brute ne doit plus être interpolée nue dans une cellule.
    expect(bloc).not.toContain('>+ {f}<');
    expect(bloc).not.toContain('>− {f}<');
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

// ── 3bis. LE DESSIN DE CHAQUE OPTION, CONTRE SON VRAI CONTRAT ───────────────

describe('calepinageOptions — lit `calepinage_options`, ne dessine rien', () => {
  it('lit l’exemple servi : l’ancre, le pointeur SLD et les dessins', () => {
    const bloc = calepinageOptions(CALEP)!;
    expect(bloc).not.toBeNull();
    expect(bloc.nbPanneauxCalepines).toBe(22);
    expect(bloc.sld).toEqual({ cle: 'recommande', variante: 'avec' });
    expect(Object.keys(bloc.offres).sort()).toEqual(['eco', 'max', 'recommande']);
  });

  it('`origine: "devis"` ne porte AUCUN layout — la page réutilise la racine', () => {
    const bloc = calepinageOptions(CALEP)!;
    for (const v of ['sans', 'avec'] as const) {
      const d = dessinDeLOption(bloc, 'recommande', v)!;
      expect(d.origine).toBe('devis');
      expect(d.layout).toBeNull();
      expect(d.plafonne).toBe(false);
    }
  });

  it('un dessin DÉRIVÉ porte son layout, dans la forme de `roof_layout`', () => {
    const d = dessinDeLOption(calepinageOptions(CALEP)!, 'eco', 'sans')!;
    expect(d.origine).toBe('derive');
    expect(d.nbPanneaux).toBe(14);
    expect(d.nbPanneauxDessines).toBe(14);
    // La forme est celle que `parseRoofLayout` sait déjà lire — on ne la
    // re-décrit pas ici, on vérifie juste qu'on la laisse passer intacte.
    const layout = d.layout as { version?: number; zones?: unknown[] };
    expect(layout.version).toBe(2);
    expect(Array.isArray(layout.zones)).toBe(true);
  });

  it('PLAFOND — `max` dit que le TOIT a tranché, et dessine moins que demandé', () => {
    const d = dessinDeLOption(calepinageOptions(CALEP)!, 'max', 'sans')!;
    expect(d.plafonne).toBe(true);
    expect(d.nbPanneauxDessines!).toBeLessThan(d.nbPanneaux!);
    expect(d.nbPanneauxDessines).toBe(22);
  });

  it('un `derive` SANS layout exploitable est ÉCARTÉ — jamais un dessin vide', () => {
    const bloc = calepinageOptions({
      calepinage_options: {
        offres: {
          eco: { sans: { nb_panneaux: 10, origine: 'derive' } },
          max: { sans: { nb_panneaux: 20, origine: 'devis' } },
        },
      },
    })!;
    expect(dessinDeLOption(bloc, 'eco', 'sans')).toBeNull();
    expect(dessinDeLOption(bloc, 'max', 'sans')).not.toBeNull();
  });

  it('clé absente / illisible ⇒ null (la page garde son calepinage d’aujourd’hui)', () => {
    expect(calepinageOptions({})).toBeNull();
    expect(calepinageOptions(null)).toBeNull();
    expect(calepinageOptions({ calepinage_options: { offres: {} } })).toBeNull();
    // Une origine non reconnue ne dit pas d'où vient le dessin : on l'écarte.
    expect(calepinageOptions({
      calepinage_options: { offres: { eco: { sans: { origine: 'inventee' } } } },
    })).toBeNull();
  });

  it('le POINTEUR SLD ne désigne qu’UNE option — les autres ne le montrent pas', () => {
    const bloc = calepinageOptions(CALEP)!;
    expect(sldDecritLOption(bloc, 'recommande', 'avec')).toBe(true);
    // …et NULLE PART ailleurs : ni l'autre variante, ni une autre taille.
    expect(sldDecritLOption(bloc, 'recommande', 'sans')).toBe(false);
    expect(sldDecritLOption(bloc, 'eco', 'avec')).toBe(false);
    expect(sldDecritLOption(bloc, 'max', 'sans')).toBe(false);
    expect(sldDecritLOption(null, 'recommande', 'avec')).toBe(false);
  });

  it('un pointeur SLD incomplet est ignoré plutôt que deviné', () => {
    for (const sld of [{ cle: 'recommande' }, { variante: 'avec' }, { cle: 'x', variante: 'peut-etre' }]) {
      const bloc = calepinageOptions({
        calepinage_options: { sld, offres: { eco: { sans: { origine: 'devis' } } } },
      })!;
      expect(bloc.sld).toBeNull();
    }
  });

  it('un dessin ne se rabat JAMAIS sur l’autre variante (une géométrie n’est pas un chiffre)', () => {
    const bloc = calepinageOptions({
      calepinage_options: { offres: { eco: { sans: { origine: 'devis' } }, max: { avec: { origine: 'devis' } } } },
    })!;
    expect(dessinDeLOption(bloc, 'eco', 'avec')).toBeNull();
    expect(dessinDeLOption(bloc, 'max', 'sans')).toBeNull();
  });
});

describe('parametresSite — annexe du site, champ par champ', () => {
  it('lit l’exemple servi du contrat', () => {
    const p = parametresSite(CALEP)!;
    expect(p.orientationDeg).toBe(180);
    expect(p.orientation).toBe('Sud');
    expect(p.inclinaisonDeg).toBe(30);
    expect(p.typeToit).toBe('pitched');
    expect(p.irradiation).toEqual({ source: 'PVGIS', ville: 'Casablanca' });
    expect(p.chaines).toEqual({ nb: 2, modulesParChaine: [11, 11] });
    expect(p.ombrageMesure).toBe(true);
  });

  it('AUCUN DÉFAUT — un champ non servi reste null, jamais « 30° » ni « plein sud »', () => {
    const p = parametresSite({ parametres_site: { orientation: 'Sud' } })!;
    expect(p.orientation).toBe('Sud');
    expect(p.orientationDeg).toBeNull();
    expect(p.inclinaisonDeg).toBeNull();
    expect(p.typeToit).toBeNull();
    expect(p.irradiation).toBeNull();
    expect(p.chaines).toBeNull();
  });

  it('L’OMBRAGE EST UN FAIT MESURÉ, jamais un forfait', () => {
    // Absent, faux, ou objet vide ⇒ pas d'ombrage. SEUL `mesure: true` compte.
    for (const ombrage of [undefined, null, {}, { mesure: false }, { perte_pct: 4 }]) {
      const p = parametresSite({ parametres_site: { orientation: 'Sud', ombrage } })!;
      expect(p.ombrageMesure, JSON.stringify(ombrage)).toBe(false);
    }
    expect(parametresSite({ parametres_site: { ombrage: { mesure: true } } })!.ombrageMesure).toBe(true);
  });

  it('aucun champ réel ⇒ null : pas d’encadré « Paramètres du site » vide', () => {
    expect(parametresSite({})).toBeNull();
    expect(parametresSite({ parametres_site: {} })).toBeNull();
    expect(parametresSite({ parametres_site: { orientation: '   ' } })).toBeNull();
    expect(parametresSite({ parametres_site: { irradiation: {} } })).toBeNull();
  });

  it('ANTICOPIE — l’annexe ne peut porter AUCUNE coordonnée machine', () => {
    const p = parametresSite({
      parametres_site: {
        orientation: 'Sud',
        // Même servis par erreur, ces champs n'ont pas de porte d'entrée.
        origin: [-7.58, 33.57], vertices: [[1, 2]], surface_m2: 120, prix_achat: 42,
      },
    })!;
    for (const interdit of ['origin', 'vertices', 'surface_m2', 'prix_achat']) {
      expect(p, interdit).not.toHaveProperty(interdit);
    }
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

  it('APERÇU D’ABORD : les cartes suivent le HÉROS et précèdent TOUS les détails', () => {
    // ORDRE FONDATEUR (26/08/2026) — la section vivait après le calepinage,
    // l'installation, la production, les économies et le schéma : le client
    // traversait toute la page avant de découvrir qu'il avait un CHOIX. La
    // règle d'audit est l'aperçu d'abord.
    const hero = PAGE.indexOf('data-track-section="hero"');
    const tailles = PAGE.indexOf('id="tailles"');
    expect(hero, 'ancre héros absente').toBeGreaterThan(0);
    expect(tailles, 'ancre #tailles absente').toBeGreaterThan(0);
    expect(hero).toBeLessThan(tailles);
    for (const ancre of ['id="roof3d"', 'id="installation"', 'id="production"',
      'id="financing-headline"', 'id="sld"', 'id="confiance"', 'id="faq"',
      'id="options"', 'id="signer"']) {
      const idx = PAGE.indexOf(ancre);
      expect(idx, `ancre ${ancre} absente`).toBeGreaterThan(0);
      expect(tailles, `#tailles doit précéder ${ancre}`).toBeLessThan(idx);
    }
  });

  it('la VUE DE DÉTAIL VIVANTE voyage AVEC les cartes (une seule section)', () => {
    // Le déplacement est ATOMIQUE : la vue « Vous regardez … » suit la carte
    // sélectionnée, donc la laisser en bas de page pendant que les cartes
    // remontent en haut l'aurait orpheline à ~2 700 lignes de son sélecteur.
    expect(sectionTailles(PAGE)).toContain('data-taille-detail');
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
    // OPTIONS CHARGEABLES (29/08/2026) — le script ouvre DÉSORMAIS une
    // requête, et une seule : le DÉTAIL d'une taille que le client a cliquée
    // (ordre fondateur « i want the 3 options to be LOADABLE »). Ce que cette
    // garde protège reste entier : elle passe par le proxy SAME-ORIGIN
    // (`detailProxyUrl`, comme les quatre autres proxies `proposition-*`),
    // jamais par une URL backend écrite ici, et la DEMANDE DE MODIFICATION
    // continue de passer par le flux EXISTANT — aucun second canal.
    expect(corps).toContain('detailProxyUrl(jetonTailles, cle, variante)');
    for (const interdit of ['XMLHttpRequest', 'navigator.sendBeacon',
      'api.taqinor.ma', '/api/django/']) {
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
    // OPTIONS CHARGEABLES — le script FORMATE désormais des nombres SERVIS
    // (contrat `taille_detail.json`), avec les mêmes fonctions que le rendu
    // serveur. Ce qui reste interdit, et qui était le vrai sujet : qu'il en
    // CALCULE un. Aucun arrondi, aucune somme, aucun pourcentage refait.
    for (const interdit of ['toFixed', 'Math.round', 'Math.floor', 'Math.ceil',
      '* 100', '/ 100', '.reduce(']) {
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

  it('le dessin d’une option vient du VRAI contrat, jamais d’un SVG deviné', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('const dessin = dessinDeLOption(calepOptions, t.cle, v);');
    expect(bloc).toContain('{dessin && (');
    // Les clés inventées au premier passage ne doivent plus exister nulle part.
    for (const mort of ['calepinageSvg', 'schemaSvg', 'calepinage_svg', 'schema_svg',
      'data-taille-calepinage', 'data-taille-schema']) {
      expect(CODE, mort).not.toContain(mort);
    }
    // Aucun cadre vide, aucun « bientôt disponible ».
    for (const interdit of ['à venir', 'bientôt', 'coming soon', 'placeholder']) {
      expect(bloc.toLowerCase(), interdit).not.toContain(interdit.toLowerCase());
    }
  });

  it('`origine: "devis"` RENVOIE à la vue d’en haut au lieu d’en fabriquer une copie', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain("{dessin.origine === 'devis' ? (");
    expect(bloc).toContain('La vue 3D de votre toit, plus haut sur cette page, montre exactement cette configuration.');
  });

  it('un dessin DÉRIVÉ dit son compte et, s’il y a lieu, que le TOIT a tranché', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('{formatNumber(dessin.nbPanneauxDessines)}');
    expect(bloc).toContain('{dessin.plafonne && (');
    expect(bloc).toContain('Plafonné par votre toit');
  });

  it('LE SCHÉMA n’est proposé QUE sous l’option qu’il décrit (jamais mal étiqueté)', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc).toContain('const sldIci = sldDecritLOption(calepOptions, t.cle, v);');
    expect(bloc).toContain('{sldIci && (');
    // Le lien #sld de la vue de détail est DERRIÈRE la garde, et il est le seul.
    expect((bloc.match(/href="#sld"/g) || []).length).toBe(1);
    expect(bloc.indexOf('{sldIci && (')).toBeLessThan(bloc.indexOf('href="#sld"'));
  });

  it('la visionneuse reste UNIQUE : on échange le layout, on ne monte pas un 2e moteur', () => {
    // La section des tailles ÉMET un événement ; la visionneuse ÉCOUTE. Aucune
    // des deux n'atteint les nœuds de l'autre.
    expect(CODE).toContain("document.dispatchEvent(new CustomEvent('taqinor:calepinage-option'");
    expect(CODE).toContain("document.addEventListener('taqinor:calepinage-option'");
    // Un seul chemin de boot : on démonte et on remonte le MÊME.
    expect(CODE).toContain('function montrerCalepinageOption');
    expect(CODE).toContain('const layoutRacine = layout;');
    // …et aucun second moteur de rendu n'est importé par la lane.
    const emetteur = CODE.slice(CODE.indexOf('function setupTaillesOffres'));
    expect(emetteur.slice(0, emetteur.indexOf('\n  })();'))).not.toContain('import(');
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

  // GARDE DURCIE (26/08) — la version d'origine ne découpait que
  // `setupTaillesOffres` et ne connaissait que trois méthodes de requête. Elle
  // laissait donc passer `pilotherCurseurBatterie` (qui touche bel et bien le
  // curseur), `setupCalepinageStaleRequest`, et toute la famille
  // `getElementsByTagName` / `getElementsByClassName` / `.closest()` /
  // `document.body.querySelector`. On couvre désormais TOUTES les fonctions que
  // cette lane a ajoutées et TOUT le jeu de méthodes.
  const FONCTIONS_DE_LA_LANE = [
    'function setupTaillesOffres',
    'function pilotherCurseurBatterie',
    'function setupCalepinageStaleRequest',
  ];

  /** Le corps d'une fonction de la lane, du `function` à son `})();`/`}` final. */
  function corpsDe(nom: string): string {
    const debut = CODE.indexOf(nom);
    expect(debut, `${nom} doit exister`).toBeGreaterThan(0);
    const reste = CODE.slice(debut);
    const fin = reste.indexOf('\n  })();');
    return fin > 0 ? reste.slice(0, fin) : reste.slice(0, 6000);
  }

  it('toutes les fonctions de la lane ne touchent QUE leurs nœuds (+ les sorties documentées)', () => {
    // LES SORTIES AUTORISÉES, nommées explicitement :
    //   · le formulaire de modification EXISTANT (WJ54) ;
    //   · le curseur batterie et sa bascule de calque, seul maître batterie ;
    //   · LANE W (28/08/2026) — le détail de la page SUIT la carte cliquée :
    //     le bloc de chiffres du héros (`#prop-fold-figures`) et la légende
    //     kWc/panneaux de « Votre installation », les DEUX SEULS nœuds hors
    //     de #tailles que `synchroniserDetailPage` touche, chacun repéré par
    //     un `data-hero-*` propre à cette sortie (jamais un `data-taille-*`
    //     réutilisé, qui aurait fait croire à un nœud interne à la section).
    //   · OPTIONS CHARGEABLES (29/08/2026) — les chapitres PROFONDS suivent
    //     désormais la carte cliquée (économies mois par mois, anneau de
    //     couverture, banque, cumul 25 ans, payback). Comme pour LANE W, ces
    //     sorties portent UN SEUL préfixe documenté, `data-detail-`, jamais un
    //     id brut : le préfixe EST la déclaration de ce que la lane a le droit
    //     de toucher hors de #tailles.
    const SORTIES_DOCUMENTEES = [
      'data-revision-token', 'revision-detail',
      'battery-sim-slider', 'prod-battery-toggle', 'battery-sim',
      'roof3d-stale-request',
      'data-hero-',
      'data-detail-',
    ];
    // TOUT le jeu de méthodes de requête, pas seulement les trois évidentes.
    const REQUETES = String.raw`(?:getElementById|querySelectorAll|querySelector|getElementsByTagName|getElementsByClassName|getElementsByName|closest)`;
    const motif = new RegExp(String.raw`(?:document(?:\.body)?|window\.document)\s*\.\s*${REQUETES}\s*\([^)]*\)|\.closest\s*\([^)]*\)`, 'g');

    let verifiees = 0;
    for (const nom of FONCTIONS_DE_LA_LANE) {
      for (const sortie of corpsDe(nom).match(motif) || []) {
        verifiees += 1;
        const autorise =
          sortie.includes('data-tailles')
          || sortie.includes('data-taille-')
          || sortie.includes('data-batt-tier')
          // `.closest('a, button')` protège les CTA du clic de sélection : il ne
          // sort pas de la carte, il reste à l'intérieur de l'élément cliqué.
          || sortie.includes("closest('a, button')")
          || SORTIES_DOCUMENTEES.some((s) => sortie.includes(s));
        expect(autorise, `${nom} — sortie non autorisée : ${sortie}`).toBe(true);
      }
    }
    // La garde doit avoir VU quelque chose : un découpage cassé qui renverrait
    // zéro requête passerait sinon en silence.
    expect(verifiees).toBeGreaterThan(8);
  });

  it('aucune fonction de la lane ne FABRIQUE un nombre : zéro arithmétique', () => {
    // CE QUI A CHANGÉ, ET CE QUI N'A PAS CHANGÉ (OPTIONS CHARGEABLES,
    // 29/08/2026). Cette garde interdisait AUSSI les fonctions de formatage,
    // parce que la lane ne faisait alors que RECOPIER du texte déjà rendu.
    // Depuis que le client peut CHARGER une autre taille, la page reçoit des
    // NOMBRES servis (contrat `taille_detail.json`) et doit bien les écrire :
    // elle les formate avec les MÊMES `formatMAD`/`formatNumber`/
    // `formatPercent`/`formatPayback` que le rendu serveur, importés du même
    // module — donc jamais un second formatage maison.
    //
    // LA RÈGLE DE FOND EST INTACTE, et c'est elle que ce test protège
    // maintenant : la lane ne CALCULE rien. Aucun arrondi, aucune somme,
    // aucun pourcentage reconstitué, aucune longueur d'arc recalculée (elle
    // vient de `dasharrayDonut`, défini UNE fois et partagé avec le SSR).
    for (const nom of FONCTIONS_DE_LA_LANE) {
      const corps = corpsDe(nom);
      for (const interdit of ['toFixed', 'toLocaleString', 'Math.round',
        'Math.floor', 'Math.ceil', 'Math.PI', '* 100', '/ 100',
        '.reduce(']) {
        expect(corps, `${nom} : ${interdit}`).not.toContain(interdit);
      }
    }
  });

  it('les valeurs écrites par la lane viennent TOUTES du contrat servi', () => {
    // Chaque écriture de texte de la lane lit soit une valeur SERVIE (`detail`
    // / `mensuelles` / `banque` / `pct` / `cumul` / `payback`), soit un
    // ORIGINAL mis en cache au chargement. Un `formatMAD(quelqueChose)` dont
    // l'argument ne serait ni l'un ni l'autre serait un chiffre fabriqué.
    const corps = corpsDe('function setupTaillesOffres');
    const appels = corps.match(/format(?:MAD|Number|Percent|Payback)\s*\(([^)]*)\)/g) || [];
    expect(appels.length).toBeGreaterThan(3);
    for (const appel of appels) {
      const source =
        appel.includes('mensuelles.')
        || appel.includes('banque.')
        || appel.includes('detail?.')
        || appel.includes('pct')
        || appel.includes('cumul');
      expect(source, `argument non servi : ${appel}`).toBe(true);
    }
    // Et la longueur d'arc n'est JAMAIS réécrite ici : elle est importée.
    expect(corps).toContain('dasharrayDonut(pct, rayon)');
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

// ── 5bis. L'ANNEXE « PARAMÈTRES DU SITE » DANS LA PAGE (audit #23) ──────────

describe('page — l’annexe « paramètres du site »', () => {
  it('vit dans « Nos hypothèses » : c’est de la méthode, pas de l’argumentaire', () => {
    expect(CODE).toContain('const paramSite = ok ? parametresSite(data) : null;');
    expect(CODE).toContain('data-parametres-site');
    const hypotheses = CODE.indexOf('data-fr="Nos hypothèses"');
    expect(hypotheses).toBeGreaterThan(0);
    expect(CODE.indexOf('data-parametres-site')).toBeGreaterThan(hypotheses);
  });

  it('chaque ligne est gardée individuellement — jamais un champ vide affiché', () => {
    for (const garde of [
      '{paramSite.inclinaisonDeg !== null && (',
      '{paramSite.irradiation !== null && (',
      '{paramSite.chaines !== null && (',
      '{paramSite.ombrageMesure && (',
      '{typeToitLabel && (',
    ]) {
      expect(CODE, garde).toContain(garde);
    }
  });

  it('le TYPE DE TOITURE est traduit, jamais rendu comme clé machine', () => {
    // « pitched » sous les yeux d'un client est un mot d'ingénieur anglais ; une
    // clé inconnue fait DISPARAÎTRE la ligne au lieu de l'afficher brute.
    expect(CODE).toContain('const TYPE_TOIT_LABELS');
    expect(CODE).toContain("pitched: { fr: 'Toiture en pente'");
    expect(CODE).toContain('TYPE_TOIT_LABELS[paramSite.typeToit] ?? null');
    expect(CODE).not.toContain('>{paramSite.typeToit}<');
  });

  it('ANTICOPIE — l’annexe n’affiche aucune coordonnée machine', () => {
    const annexe = CODE.slice(CODE.indexOf('data-parametres-site'));
    const bloc = annexe.slice(0, annexe.indexOf('</dd>'));
    for (const interdit of ['origin', 'vertices', 'lat', 'lng', 'surface']) {
      expect(bloc.toLowerCase(), interdit).not.toContain(interdit);
    }
  });
});

// ── 6bis. CONSOLIDATION — QUATRE SURFACES DE PRIX, UNE HIÉRARCHIE ───────────

describe('CONSOLIDATION — la hiérarchie des surfaces de prix se lit', () => {
  it('les VERSIONS du devis ne s’appellent plus comme les TAILLES', () => {
    // « Autres tailles proposées » était quasi-homonyme d'« Explorer d'autres
    // tailles » alors qu'il dit tout autre chose : les autres DEVIS du client.
    expect(CODE).not.toContain('data-fr="Autres tailles proposées"');
    expect(CODE).toContain('data-fr="Autres versions de ce devis"');
    expect(CODE).toContain('data-en="Other versions of this quote"');
    // Le texte d'accompagnement suit le même vocabulaire.
    expect(CODE).toContain('l’une de ces versions');
  });

  it('gammes ET versions sont repliées, et s’ouvrent seules quand aucune taille ne les précède', () => {
    for (const fold of ['<details class="gammes-fold" open={!tailles}>',
      '<details class="versions-fold" open={!tailles}>']) {
      expect(CODE, fold).toContain(fold);
    }
  });

  it('SAFARI iOS — les <summary> qui se veulent sans puce le sont VRAIMENT', () => {
    // `list-none` seul laisse ::-webkit-details-marker dessiner son triangle.
    // Tout <summary> de cette lane qui masque sa puce doit porter le triptyque
    // du dépôt (Faq.astro) — d'autant que ces deux <details> sont OUVERTS par
    // défaut sur le chemin sans tailles, donc visibles sur la page ordinaire.
    const sansPuce = CODE.match(/<summary class="[^"]*list-none[^"]*"/g) || [];
    expect(sansPuce.length).toBeGreaterThan(1);
    for (const m of sansPuce) {
      // `marker:hidden` ou `marker:content-none` disent tous deux l'intention…
      expect(m, `summary sans règle marker : ${m}`).toMatch(/marker:(hidden|content-none)/);
      // …mais AUCUN des deux n'atteint le pseudo-élément de WebKit.
      expect(m, `summary sans garde webkit : ${m}`).toContain('[&::-webkit-details-marker]:hidden');
    }
  });

  it('le raccourci vers le curseur ANNONCE son plafonnement au lieu de l’avaler', () => {
    // Le clamp `Math.min(units, max)` faisait atterrir en silence sur une autre
    // taille que celle demandée.
    expect(CODE).toContain('id="battery-sim-clamp"');
    expect(CODE).toContain('id="battery-sim-clamp-n"');
    expect(CODE).toContain("document.getElementById('battery-sim-clamp')");
    // Masqué et vide au premier rendu — invisible sur tous les chemins.
    expect(CODE).toMatch(/id="battery-sim-clamp"[^>]*hidden/);
    expect(CODE).toContain('aria-live="polite"');
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
    // OPTIONS CHARGEABLES — la section porte `data-tailles-token={token}` :
    // c'est le token DÉJÀ dans la route, relu par l'îlot pour appeler le proxy
    // same-origin. Aucun identifiant NOUVEAU n'est fabriqué, et aucune URL
    // backend n'est écrite dans le balisage — c'est bien ce que cette garde
    // protège. On la retire donc du texte examiné, plutôt que d'assouplir la
    // règle pour tout le reste.
    const bloc = sectionTailles(CODE).replace('data-tailles-token={token}', ' ');
    for (const interdit of ['/api/', 'api.taqinor.ma', 'token=', '/proposition/']) {
      expect(bloc, interdit).not.toContain(interdit);
    }
  });
});

// ── 8. LANE W (28/08/2026) — ENVOI 1/2/3 OPTIONS : 2 OU 3 CARTES ────────────
// Le backend (LANE B, déjà foldée) peut désormais filtrer `offres` à 2 ou 3
// entrées selon les sections `taille_eco`/`taille_max` du ShareLink. Cette
// bibliothèque ne connaît PAS ce filtrage — elle lit juste la liste qu'on lui
// donne — donc ces épingles vérifient qu'elle reste GÉNÉRIQUE sur la longueur.

describe('LANE W — la liste `offres` peut porter 2 OU 3 cartes, MÊME ordre', () => {
  it('3 cartes servies (le contrat complet) : Éco → Recommandé → Max', () => {
    const bloc = offresTailles(SERVI)!;
    expect(bloc.offres).toHaveLength(3);
    expect(bloc.offres.map((t) => t.cle)).toEqual(['eco', 'recommande', 'max']);
  });

  it('2 cartes servies (le vendeur a décoché une taille) : l’ordre Éco → Recommandé survit', () => {
    const deux = {
      offres_tailles: {
        avec_servable: SERVI.offres_tailles.avec_servable,
        offres: [SERVI.offres_tailles.offres[0], SERVI.offres_tailles.offres[1]], // eco, recommande
      },
    };
    const bloc = offresTailles(deux)!;
    expect(bloc).not.toBeNull();
    expect(bloc.offres).toHaveLength(2);
    expect(bloc.offres.map((t) => t.cle)).toEqual(['eco', 'recommande']);
    expect(tailleParDefaut(bloc).cle).toBe('recommande');
  });

  it('2 cartes servies (Recommandé + Max, l’Éco décochée) : même discipline', () => {
    const deux = {
      offres_tailles: {
        avec_servable: SERVI.offres_tailles.avec_servable,
        offres: [SERVI.offres_tailles.offres[1], SERVI.offres_tailles.offres[2]], // recommande, max
      },
    };
    const bloc = offresTailles(deux)!;
    expect(bloc.offres).toHaveLength(2);
    expect(bloc.offres.map((t) => t.cle)).toEqual(['recommande', 'max']);
  });

  it('1 seule servie (le vendeur a décoché les deux cases) : AUCUNE section — la page d’avant', () => {
    // C'est exactement la garde « MOINS DE DEUX tailles ⇒ null » déjà testée
    // plus haut contre un échantillon à la main ; ici contre le VRAI contrat,
    // pour la scénario réel de l'envoi « 1 option ».
    const uneSeule = {
      offres_tailles: {
        avec_servable: SERVI.offres_tailles.avec_servable,
        offres: [SERVI.offres_tailles.offres[1]], // recommande seule
      },
    };
    expect(offresTailles(uneSeule)).toBeNull();
  });

  it('la page rend le NOMBRE DE CARTES SERVI, jamais un compte codé en dur (2 ou 3)', () => {
    const bloc = sectionTailles(CODE);
    // La grille itère `tailles.offres` — jamais `.slice(0, 3)` ni une longueur
    // supposée : un filtrage backend à 2 cartes doit se voir sans toucher au
    // gabarit.
    expect(bloc).toContain('{tailles.offres.map((t) => (');
    for (const interdit of ['.slice(0, 3)', '.slice(0,3)', 'offres[0], tailles.offres[1], tailles.offres[2]']) {
      expect(bloc, interdit).not.toContain(interdit);
    }
  });
});

// ── 9. LANE W — « LE DÉTAIL DE LA PAGE SUIT LA CARTE » ──────────────────────
// Ordre fondateur (28/08/2026) : cliquer une carte doit faire suivre le héros
// (prix/économie) et la légende kWc/panneaux de « Votre installation ». Ce
// module ne calcule toujours rien (règle zéro-chiffre-inventé) : le script
// COPIE le texte déjà rendu par la carte sélectionnée, ou RESTAURE le texte
// d'origine mis en cache — jamais un second `formatMAD`/`formatNumber`.

describe('LANE W — le héros et la légende « installation » suivent la carte cliquée', () => {
  function scriptTailles(): string {
    const debut = CODE.indexOf('function setupTaillesOffres');
    expect(debut, 'setupTaillesOffres doit exister').toBeGreaterThan(0);
    const reste = CODE.slice(debut);
    const fin = reste.indexOf('\n  })();');
    expect(fin, 'setupTaillesOffres doit se refermer').toBeGreaterThan(0);
    return reste.slice(0, fin);
  }

  it('les crochets `data-hero-*` existent, sur le héros ET la légende « installation »', () => {
    expect(CODE).toContain('data-hero-ttc-value');
    expect(CODE).toContain('data-hero-eco-value');
    expect(CODE).toContain('data-hero-eco-sub');
    expect(CODE).toContain('data-hero-kwc-value');
    expect(CODE).toContain('data-hero-panneaux-value');
    // Sur les DEUX bandeaux visés — pas un troisième nœud inventé.
    const hero = CODE.slice(CODE.indexOf('id="prop-fold-figures"'), CODE.indexOf('id="prop-fold-figures"') + 1700);
    expect(hero).toContain('data-hero-ttc-value');
    expect(hero).toContain('data-hero-eco-value');
    expect(hero).toContain('data-hero-eco-sub');
    const installation = CODE.slice(CODE.indexOf('id="installation"'), CODE.indexOf('id="installation"') + 1500);
    expect(installation).toContain('data-hero-kwc-value');
    expect(installation).toContain('data-hero-panneaux-value');
  });

  it('chaque carte porte le MÊME jeu de crochets, pour que le script ait quoi copier', () => {
    const bloc = sectionTailles(CODE);
    for (const hook of [
      'data-taille-ttc-value', 'data-taille-eco-value', 'data-taille-payback-value',
      'data-taille-panneaux-value', 'data-taille-kwc-value',
    ]) {
      expect(bloc, hook).toContain(hook);
    }
  });

  it('le script COPIE le texte déjà rendu — aucun second calcul, aucune requête réseau', () => {
    const corps = scriptTailles();
    expect(corps).toContain('function synchroniserDetailPage');
    expect(corps).toContain('texteDeLaCarteSelectionnee');
    expect(corps).toContain('.textContent');
    // La discipline « zéro chiffre CALCULÉ côté client » vaut toujours. Ce qui
    // a changé (OPTIONS CHARGEABLES, 29/08/2026) : les chiffres de TÊTE
    // continuent d'être COPIÉS de la carte, tandis que les chapitres PROFONDS
    // sont désormais CHARGÉS et formatés — deux mécanismes distincts, la
    // copie restant celui du héros. Ni l'un ni l'autre ne calcule.
    for (const interdit of ['toFixed', 'Math.round', 'Math.floor', 'Math.ceil',
      '* 100', '/ 100']) {
      expect(corps, interdit).not.toContain(interdit);
    }
    const synchro = corps.slice(corps.indexOf('function synchroniserDetailPage'),
      corps.indexOf('const jetonTailles ='));
    for (const interdit of ['formatMAD', 'formatNumber', 'formatPercent', 'fetch(']) {
      expect(synchro, interdit).not.toContain(interdit);
    }
  });

  it('appliquer() APPELLE la synchronisation à chaque changement de carte/variante', () => {
    const corps = scriptTailles();
    expect(corps).toContain('synchroniserDetailPage();');
    const appliquer = corps.slice(corps.indexOf('function appliquer'));
    expect(appliquer.indexOf('synchroniserDetailPage();')).toBeGreaterThan(0);
  });

  it('PRÉSERVATION — sur Recommandé + la variante par défaut, tout est RESTAURÉ, jamais recalculé', () => {
    const corps = scriptTailles();
    // `surLeDefaut` compare cle/variante aux deux valeurs par défaut, et
    // restaure alors le texte ORIGINAL mis en cache — pas un texte lu sur la
    // carte recommandée (qui pourrait légèrement diverger sur un devis à deux
    // options divergentes, cf. L-DEUXOPT).
    expect(corps).toContain('cle === cleDefaut && variante === varianteDefaut');
    expect(corps).toContain('heroTtcOriginal');
    expect(corps).toContain('heroEcoOriginal');
    expect(corps).toContain('heroKwcOriginal');
    expect(corps).toContain('heroPanneauxOriginal');
    expect(corps).toContain('appliquerChampHero(');
    expect(corps).toContain('valeur.textContent = original;');
  });

  it('OMISSION HONNÊTE — la ligne MAD/mois du héros est MASQUÉE hors de Recommandé, jamais retraduite en JS', () => {
    const corps = scriptTailles();
    // Aucune carte Éco/Max ne sert de valeur « mensuelle » : plutôt que de la
    // reconstruire (economie / 12, un calcul interdit) ou de retraduire une
    // phrase en trois langues depuis le script, la ligne est simplement
    // masquée hors de la sélection par défaut.
    expect(corps).toContain('heroEcoSub.hidden = !surLeDefaut');
    // …et elle ne contient AUCUN mot traduit en dur (ce serait un 4e canal
    // d'i18n, hors du mécanisme data-i18n de la page).
    expect(corps).not.toMatch(/heroEcoSub\.(?:textContent|innerHTML)\s*=/);
  });

  it('les sorties hors de #tailles restent UNIQUEMENT les deux bandeaux documentés', () => {
    // Régression du garde-fou « toutes les fonctions de la lane ne touchent
    // QUE leurs nœuds » : la seule famille d'attributs neuve est `data-hero-*`
    // — jamais un id brut (`getElementById('prop-fold-figures')` par ex.)
    // qui échapperait au garde-fou générique.
    const corps = scriptTailles();
    expect(corps).toContain("querySelector<HTMLElement>('[data-hero-ttc-value]')");
    expect(corps).not.toContain("getElementById('prop-fold-figures')");
    expect(corps).not.toContain("getElementById('installation')");
  });

  // ── REVUE ADVERSARIALE (correction, commit e5b5051e) ──────────────────────
  // Faille : quand la carte SÉLECTIONNÉE ne sert pas un champ, le code
  // repartait sur le texte ORIGINAL (celui du devis officiel) — un chiffre
  // RÉEL mais attribué à la MAUVAISE offre. Et le créneau « Économie / an »
  // pouvait recevoir un payback (« 4,7 ans ») sous un libellé pensé pour un
  // montant — un mal-étiquetage. Le correctif : masquer l'item plutôt que de
  // mentir par readback, et ne jamais croiser eco/payback.

  it('une carte SANS ce champ MASQUE l’item du héros — jamais le chiffre du devis officiel à sa place', () => {
    const corps = scriptTailles();
    // `appliquerChampHero` : hors défaut, `texteCarte === null` ⇒ l'item
    // ENTIER (le conteneur, pas seulement la valeur) est masqué — jamais un
    // repli sur `original`.
    expect(corps).toContain('function appliquerChampHero');
    const fn = corps.slice(corps.indexOf('function appliquerChampHero'));
    const corpsFn = fn.slice(0, fn.indexOf('\n    }\n'));
    expect(corpsFn).toContain('if (texteCarte === null) {');
    expect(corpsFn).toContain('item.hidden = true;');
    // Le readback interdit (`?? heroTtcOriginal` etc. sur une carte non
    // défaut) ne doit plus exister nulle part dans la fonction de synchro.
    const synchro = corps.slice(corps.indexOf('function synchroniserDetailPage'));
    const corpsSynchro = synchro.slice(0, synchro.indexOf('\n    }\n'));
    for (const interdit of [
      '?? heroTtcOriginal', '?? heroEcoOriginal', '?? heroKwcOriginal', '?? heroPanneauxOriginal',
    ]) {
      expect(corpsSynchro, interdit).not.toContain(interdit);
    }
  });

  it('les conteneurs à masquer sont les ITEMS ENTIERS (libellé + valeur), pas la seule valeur', () => {
    // Un libellé « Total TTC » orphelin au-dessus d'un vide serait aussi
    // trompeur qu'un mauvais chiffre : c'est tout le encadré/l'item qui
    // disparaît, jamais seulement le `<span>` du nombre.
    expect(CODE).toContain('data-hero-ttc-card');
    expect(CODE).toContain('data-hero-eco-card');
    expect(CODE).toContain('data-hero-kwc-item');
    expect(CODE).toContain('data-hero-panneaux-item');
    const corps = scriptTailles();
    expect(corps).toContain("querySelector<HTMLElement>('[data-hero-ttc-card]')");
    expect(corps).toContain("querySelector<HTMLElement>('[data-hero-eco-card]')");
    expect(corps).toContain("querySelector<HTMLElement>('[data-hero-kwc-item]')");
    expect(corps).toContain("querySelector<HTMLElement>('[data-hero-panneaux-item]')");
  });

  it('ÉCO ≠ PAYBACK — le créneau « Économie / an » ne lit JAMAIS le champ homonyme de l’autre nature', () => {
    // `data-hero-eco-kind`, figé au chargement (`ecoHero ? 'eco' : 'payback'`),
    // dit ce que CE bloc a réellement rendu ; le script ne lit le champ de la
    // carte QUE s'il porte le même nom — jamais un croisement.
    expect(CODE).toContain("data-hero-eco-kind={ecoHero ? 'eco' : 'payback'}");
    const corps = scriptTailles();
    expect(corps).toContain("heroEcoCard?.dataset.heroEcoKind === 'payback' ? 'payback' : 'eco'");
    const synchro = corps.slice(corps.indexOf('function synchroniserDetailPage'));
    expect(synchro).toContain("heroEcoKind === 'payback'");
    expect(synchro).toContain("texteDeLaCarteSelectionnee('[data-taille-payback-value]')");
    expect(synchro).toContain("texteDeLaCarteSelectionnee('[data-taille-eco-value]')");
    // La ligne qui choisit le champ est un ternaire STRICT eco/payback — pas
    // un enchaînement `??` qui accepterait l'un OU l'autre indifféremment.
    expect(synchro).not.toMatch(/texteDeLaCarteSelectionnee\('\[data-taille-eco-value\]'\)\s*\?\?\s*texteDeLaCarteSelectionnee\('\[data-taille-payback-value\]'\)/);
  });

  it('le séparateur de la légende « installation » ne reste JAMAIS orphelin', () => {
    expect(CODE).toContain('data-hero-legend-sep');
    const corps = scriptTailles();
    expect(corps).toContain('heroLegendSep.hidden = !(kwcVisible && panneauxVisible)');
  });

  it('PRÉSERVATION — restaurer démasque TOUJOURS (le retour sur Recommandé lève tout masquage)', () => {
    const corps = scriptTailles();
    const fn = corps.slice(corps.indexOf('function appliquerChampHero'));
    const corpsFn = fn.slice(0, fn.indexOf('\n    }\n'));
    expect(corpsFn).toContain('if (surLeDefaut) {');
    expect(corpsFn).toContain('item.hidden = false;');
  });

  // ── EXTENSION (revue Fable, ordre fondateur) — LES BANDEAUX RESTANTS ───────
  // « le détail de la page suit la carte » couvre aussi la production, le
  // bandeau « Économie estimée / an » (distinct du héros) et la couverture —
  // avec la MÊME discipline copier/masquer/restaurer, sauf pour l'anneau de
  // couverture (voir plus bas : son arc ne peut pas honnêtement suivre).

  it('la carte porte le crochet PRODUCTION, jumeau du crochet du bandeau', () => {
    const bloc = sectionTailles(CODE);
    expect(bloc, 'data-taille-production-value').toContain('data-taille-production-value');
    // Le nombre SEUL est isolé — jamais « kWh » dupliqué en copiant le texte
    // (le bandeau porte déjà son propre « kWh » statique).
    expect(bloc).toContain('<span data-taille-production-value>{formatNumber(va.productionAnnuelleKwh, 0)}</span> kWh');
  });

  it('le bandeau PRODUCTION suit la carte, avec les mêmes hooks card/value que le héros', () => {
    expect(CODE).toContain('data-hero-production-card');
    expect(CODE).toContain('data-hero-production-value');
    const corps = scriptTailles();
    expect(corps).toContain("querySelector<HTMLElement>('[data-hero-production-card]')");
    expect(corps).toContain("querySelector<HTMLElement>('[data-hero-production-value]')");
    const synchro = corps.slice(corps.indexOf('function synchroniserDetailPage'));
    expect(synchro).toContain('heroProductionValue, heroProductionCard, heroProductionOriginal, surLeDefaut');
    expect(synchro).toContain("texteDeLaCarteSelectionnee('[data-taille-production-value]')");
    // Même garde-fou zéro-calcul : pas de readback `?? heroProductionOriginal`
    // hors de `appliquerChampHero` (qui, lui, restaure QUE sur `surLeDefaut`).
    expect(synchro).not.toContain('?? heroProductionOriginal');
  });

  it('le bandeau « Économie estimée / an » est un NŒUD DISTINCT du héros — jamais un sélecteur partagé', () => {
    // La faille ciblée par la demande : ce bandeau vit dans le chapitre
    // production (`prodKwh || ecoHero`), le héros vit dans #prop-fold-figures
    // — deux endroits, donc deux crochets, jamais `data-hero-eco-value` réutilisé
    // (qui masquerait ou écrirait le MAUVAIS nœud).
    expect(CODE).toContain('data-hero-eco-annual-card');
    expect(CODE).toContain('data-hero-eco-annual-value');
    expect(CODE, 'un span dédié, pas le crochet du héros').toContain(
      '<span data-hero-eco-annual-value>{formatMAD(ecoHero)}</span>',
    );
    const corps = scriptTailles();
    expect(corps).toContain("querySelector<HTMLElement>('[data-hero-eco-annual-card]')");
    expect(corps).toContain("querySelector<HTMLElement>('[data-hero-eco-annual-value]')");
    const synchro = corps.slice(corps.indexOf('function synchroniserDetailPage'));
    expect(synchro).toContain('heroEcoAnnualValue, heroEcoAnnualCard, heroEcoAnnualOriginal, surLeDefaut');
    // Ce bandeau ne rend JAMAIS de payback au chargement (seulement sous
    // `ecoHero`) : il lit donc directement `data-taille-eco-value`, sans le
    // ternaire `heroEcoKind` du héros — pas de risque de croisement ici.
    expect(synchro).toContain(
      "heroEcoAnnualValue, heroEcoAnnualCard, heroEcoAnnualOriginal, surLeDefaut,\n        texteDeLaCarteSelectionnee('[data-taille-eco-value]')",
    );
  });

  it('COUVERTURE — l’anneau suit la taille CHARGÉE, et sa géométrie n’existe qu’UNE fois', () => {
    // CE QUI A CHANGÉ (OPTIONS CHARGEABLES, 29/08/2026). LANE W MASQUAIT cet
    // anneau hors de « Recommandé », faute de pouvoir le redessiner sans
    // écrire une SECONDE expression de sa géométrie dans l'îlot. Le fondateur
    // veut désormais que cliquer une carte CHARGE l'option ; l'anneau devait
    // donc suivre. La règle n'a pas été assouplie — la duplication a été
    // supprimée : la longueur d'arc vit dans `lib/tailleDetail.ts`
    // (`dasharrayDonut`), appelée par le rendu SERVEUR et par l'îlot. UNE
    // définition, deux lecteurs, aucun calcul écrit ici.
    //
    // ET LE POURCENTAGE, LUI, N'EST TOUJOURS CALCULÉ NULLE PART : il est
    // SERVI (`carte.couverture_pct`), et la carte reste MASQUÉE quand la
    // taille chargée ne le sert pas — l'omission, jamais un arc figé sous un
    // pourcentage qui n'est pas le sien.
    expect(CODE).toContain('data-hero-couverture-card');
    const corps = scriptTailles();
    expect(corps).toContain("querySelector<HTMLElement>('[data-hero-couverture-card]')");
    expect(corps).toContain('const pct = detail?.carte?.couverturePct ?? null;');
    expect(corps).toContain('if (heroCouvertureCard) heroCouvertureCard.hidden = pct === null;');
    expect(corps).toContain("couvArc.setAttribute('stroke-dasharray', dasharrayDonut(pct, rayon));");
    // AUCUNE lecture de TEXTE de carte pour ce champ : le pourcentage vient
    // du contrat, jamais d'un readback sur le DOM d'une carte.
    expect(corps).not.toContain("texteDeLaCarteSelectionnee('[data-taille-couverture");
    // Et surtout : aucun calcul de géométrie ÉCRIT dans le script — le rayon
    // est LU sur le DOM, la longueur d'arc est IMPORTÉE.
    for (const interdit of ['donutDash', 'donutCirc', 'Math.PI', '2 * Math.']) {
      expect(corps, interdit).not.toContain(interdit);
    }
  });

  it('les TROIS nouveaux bandeaux restent sous le prefixe documenté `data-hero-`', () => {
    // Régression du garde-fou PRÉSERVATION (SORTIES_DOCUMENTEES) : aucun
    // sélecteur brut par id n'est apparu pour ces trois extensions.
    const corps = scriptTailles();
    for (const interdit of [
      "getElementById('financing-headline')", "getElementById('production')",
    ]) {
      expect(corps, interdit).not.toContain(interdit);
    }
  });
});
