// WJ131 — Garde-fou de l'appariement « ligne de devis → fiche technique ».
//
// Deux dangers, tous deux couverts ici :
//  1. LIER LA MAUVAISE MARQUE. Un « panneau 710 Wc » sans marque connue ne doit
//     JAMAIS renvoyer vers la fiche Canadian Solar par défaut — le client
//     lirait des faits qui ne sont pas ceux de son matériel.
//  2. LIER DANS LE VIDE. Chaque slug retourné est confronté au VRAI catalogue
//     (import de `fiches.ts`) : renommer ou retirer une fiche sans toucher au
//     matcher casse ce test, jamais la page en production.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { ficheSlugPourLigne } from '../src/lib/ficheMatcher';
import { FICHES, FICHE_ALIASES, ficheBySlug } from '../src/lib/fiches';

const PROPOSITION = readFileSync(
  fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
  'utf-8',
);

// CONTRAT UNIQUE « ligne → fiche » (fondateur 2026-08-18). Ce fichier VIT dans
// le backend parce que c'est LUI le porteur partagé (PACT10) : le moteur de
// devis Django et ce matcher web doivent rendre le même slug pour la même
// désignation, sinon le PDF et la page envoient le client sur deux fiches
// différentes. Le test jumeau côté Django lit EXACTEMENT le même fichier
// (apps/ventes/tests/test_quote_engine.py::test_fiche_slug_mapping).
const CONTRAT = JSON.parse(readFileSync(
  fileURLToPath(new URL(
    '../../../backend/django_core/apps/ventes/contract_samples/ligne_fiche_mapping.json',
    import.meta.url,
  )),
  'utf-8',
)) as {
  exemple: Record<string, string>;
  alias: Record<string, string>;
  decoupage: { residentiel: string[]; grands_projets: string[] };
};

/** Les cas d'appariement attendus : [désignation, marque | undefined, slug]. */
const APPARIEMENTS: Array<[string, string | undefined, string]> = [
  // Panneaux — la MARQUE est décisive, jamais la puissance seule.
  ['Panneau photovoltaïque 710 Wc', 'Canadian Solar', 'canadian-solar-710'],
  ['Panneau CANADIAN SOLAR 710W bifacial', undefined, 'canadian-solar-710'],
  // L'ORTHOGRAPHE RÉELLE DU CATALOGUE. Le produit seedé s'appelle « Panneau
  // Canadien Solar 710W » et porte la marque « Canadien Solar » : c'est la
  // ligne la plus fréquente de tous les devis résidentiels, et elle ne
  // recevait AUCUN lien côté web tant que la règle ne testait que `canadian`.
  ['Panneau Canadien Solar 710W', undefined, 'canadian-solar-710'],
  ['Panneau photovoltaïque 710 Wc', 'Canadien Solar', 'canadian-solar-710'],
  ['Module PV Jinko Tiger Neo 710 Wc', undefined, 'jinko-710'],
  ['Panneau photovoltaïque 710 Wc', 'JINKO', 'jinko-710'],
  // Onduleurs — la topologie ou la marque suffit, chacune vers SA fiche.
  ['Onduleur hybride 8 kW', undefined, 'onduleur-deye-hybride'],
  ['Onduleur DEYE SUN-12K-SG04LP3', undefined, 'onduleur-deye-hybride'],
  ['Onduleur réseau 10 kW', undefined, 'onduleur-huawei-reseau'],
  ['Onduleur Huawei SUN2000-10KTL', undefined, 'onduleur-huawei-reseau'],
  // Stockage.
  ['Batterie lithium 5,12 kWh', 'Dyness', 'batterie-dyness'],
  ['Batterie DYNESS DL5.0C', undefined, 'batterie-dyness'],
  // TOLÉRANCE HISTORIQUE — le catalogue a longtemps écrit « Deyness » (faute
  // corrigée le 2026-08-18) et les désignations FIGÉES des devis déjà émis la
  // portent encore : elles doivent continuer d'atteindre la fiche Dyness.
  ['Batterie Deyness 10 kWh', undefined, 'batterie-dyness'],
  ['Batterie lithium 5 kWh', 'Deyness', 'batterie-dyness'],
  // Supervision & comptage.
  ['Smart Meter triphasé', undefined, 'smart-meter-huawei'],
  ['Compteur intelligent DTSU666-H', undefined, 'smart-meter-huawei'],
  ['Dongle WiFi', undefined, 'wifi-dongle-huawei'],
  ['Smart Dongle WLAN-FE', 'Huawei', 'wifi-dongle-huawei'],
  // LES POSTES GÉNÉRIQUES — le cœur de la demande fondateur. Découpage du
  // 18/08 : la protection est SCINDÉE (le continu et l'alternatif ne se coupent
  // pas de la même façon), le câblage est séparé des accessoires de pose, et la
  // structure reçoit enfin sa fiche.
  // Un coffret combiné « AC/DC » atterrit du côté DC — la moitié spécifiquement
  // photovoltaïque, et la cible de l'alias de l'ancien slug.
  ['Tableau De Protection AC/DC', undefined, 'protection-dc'],
  ['Coffret de protection DC', undefined, 'protection-dc'],
  ['Coffret DC 2 strings', undefined, 'protection-dc'],
  ['Parafoudre DC type 2 1000 V', undefined, 'protection-dc'],
  ['Sectionneur DC 1000 V 25 A', undefined, 'protection-dc'],
  ['Fusible gPV 1000 VDC 15 A', undefined, 'protection-dc'],
  ['Porte-fusible 1000 VDC', undefined, 'protection-dc'],
  ['Coffret AC', undefined, 'protection-ac'],
  ['Parafoudre AC type 2', undefined, 'protection-ac'],
  ['Disjoncteur AC courbe C 16 A monophasé', undefined, 'protection-ac'],
  ['Différentiel (DDR) type A 300 mA 40 A', undefined, 'protection-ac'],
  // Câblage vs accessoires de pose : le CÂBLE d'un côté, ce qui le porte de l'autre.
  ['Câble solaire H1Z2Z2-K 6 mm² (au mètre)', undefined, 'cablage'],
  ['Câblage solaire et connecteurs MC4', undefined, 'cablage'],
  ['Connecteurs MC4', undefined, 'cablage'],
  ['Accessoires', undefined, 'accessoires-pose'],
  ['Accessoires de pose et de câblage', undefined, 'accessoires-pose'],
  ['Presse-étoupes', undefined, 'accessoires-pose'],
  ['Chemin de câbles et goulottes', undefined, 'accessoires-pose'],
  // Structure : la ligne que le client payait sans aucune explication.
  ['Structures acier', undefined, 'structure-fixation'],
  ['Structures aluminium', undefined, 'structure-fixation'],
  ['Socles', undefined, 'structure-fixation'],
  ['Structure de fixation en aluminium', undefined, 'structure-fixation'],
];

describe('WJ131 — appariement ligne de devis → fiche technique', () => {
  for (const [designation, marque, slug] of APPARIEMENTS) {
    it(`« ${designation} »${marque ? ` (${marque})` : ''} → ${slug}`, () => {
      expect(ficheSlugPourLigne(designation, marque)).toBe(slug);
    });
  }

  it('chaque slug retourné existe RÉELLEMENT dans le catalogue des fiches', () => {
    for (const [designation, marque] of APPARIEMENTS) {
      const slug = ficheSlugPourLigne(designation, marque);
      expect(slug, `aucun slug pour « ${designation} »`).toBeTruthy();
      expect(ficheBySlug(slug as string), `fiche absente de fiches.ts : ${slug}`).toBeTruthy();
    }
  });

  it('les fiches EXPLICATIVES des postes génériques sont publiées, sans PDF constructeur', () => {
    for (const slug of ['protection-dc', 'protection-ac', 'cablage', 'accessoires-pose', 'structure-fixation']) {
      const fiche = ficheBySlug(slug);
      expect(fiche, `fiche manquante : ${slug}`).toBeTruthy();
      expect(fiche!.faits.length).toBeGreaterThan(0);
      // Aucun constructeur : ces postes sont montés sur mesure, donc pas de PDF.
      expect(fiche!.pdf).toBeNull();
      // La source faisant foi est une NORME (page officielle) — ou rien du tout,
      // jamais une URL devinée.
      if (fiche!.datasheet !== null) expect(fiche!.datasheet).toMatch(/^https:\/\//);
      // AUCUNE marque de matériel PV ne s'invite dans une fiche générique. Les
      // deux exceptions sont nommées et confirmées par le fondateur : Schneider
      // sur la protection AC, Nexans sur le câblage — traitées à part dans
      // tests/fiches.test.ts.
      const texte = `${fiche!.nom} ${fiche!.marque} ${fiche!.modele} ${fiche!.resume} ${fiche!.faits.join(' ')}`.toLowerCase();
      for (const marque of ['canadian', 'jinko', 'huawei', 'deye', 'dyness']) {
        expect(texte, `marque « ${marque} » citée dans ${slug}`).not.toContain(marque);
      }
    }
  });
});

// ── CONTRAT UNIQUE ligne → fiche (PACT10) ────────────────────────────────────
// La moitié WEB du contrat partagé. Sa jumelle Django lit le même fichier et
// vérifie `theme.fiche_slug` dessus : si les deux passent, le PDF et la page
// envoient forcément le client sur la MÊME fiche.
describe('contrat partagé ligne_fiche_mapping.json — moitié web', () => {
  it('chaque désignation-type du contrat donne EXACTEMENT le slug attendu', () => {
    for (const [designation, attendu] of Object.entries(CONTRAT.exemple)) {
      // '' côté Django = null côté web : la même absence de lien, deux langages.
      const obtenu = ficheSlugPourLigne(designation) ?? '';
      expect(obtenu, `« ${designation} » : contrat=${attendu || '(aucun)'} obtenu=${obtenu || '(aucun)'}`)
        .toBe(attendu);
    }
  });

  it('le contrat couvre les 11 familles du découpage, et rien de plus', () => {
    const familles = [...CONTRAT.decoupage.residentiel, ...CONTRAT.decoupage.grands_projets];
    expect(familles.length).toBe(11);
    // Chaque slug promis par le contrat existe dans le catalogue publié.
    for (const slug of Object.values(CONTRAT.exemple)) {
      if (!slug) continue;
      expect(ficheBySlug(slug), `slug absent du catalogue : ${slug}`).toBeTruthy();
    }
  });

  it('les alias du contrat sont EXACTEMENT ceux du catalogue (une seule vérité)', () => {
    expect(CONTRAT.alias).toEqual(FICHE_ALIASES);
  });
});

describe('WJ131 — casse, accents et ponctuation ne changent rien', () => {
  const EQUIVALENTS: Array<[string, string]> = [
    ['CÂBLAGE SOLAIRE', 'cablage solaire'],
    ['Tableau de protection AC/DC', 'TABLEAU DE PROTECTION AC-DC'],
    ['Onduleur RÉSEAU 10 kW', 'onduleur reseau 10 kw'],
    ['Panneau Canadian Solar 710 Wc', 'PANNEAU CANADIAN SOLAR 710 WC'],
  ];
  for (const [a, b] of EQUIVALENTS) {
    it(`« ${a} » et « ${b} » donnent le même résultat`, () => {
      const slug = ficheSlugPourLigne(a);
      expect(slug).toBeTruthy();
      expect(ficheSlugPourLigne(b)).toBe(slug);
    });
  }

  it('« Wi-Fi », « WiFi » et « wifi » désignent le même dongle', () => {
    expect(ficheSlugPourLigne('Dongle Wi-Fi')).toBe('wifi-dongle-huawei');
    expect(ficheSlugPourLigne('Dongle WiFi')).toBe('wifi-dongle-huawei');
    expect(ficheSlugPourLigne('dongle wifi')).toBe('wifi-dongle-huawei');
  });
});

describe('WJ131 — JAMAIS la mauvaise marque, JAMAIS de lien inventé', () => {
  it('un panneau 710 Wc de marque inconnue ne devient pas un Canadian Solar', () => {
    expect(ficheSlugPourLigne('Panneau photovoltaïque 710 Wc')).toBeNull();
    expect(ficheSlugPourLigne('Panneau monocristallin 710W', 'Longi')).toBeNull();
    expect(ficheSlugPourLigne('Module PV 550 Wc', 'Trina')).toBeNull();
  });

  it('une batterie d’une autre marque ne renvoie pas vers la fiche Dyness', () => {
    expect(ficheSlugPourLigne('Batterie lithium 5 kWh')).toBeNull();
    expect(ficheSlugPourLigne('Batterie LFP 5 kWh', 'Pylontech')).toBeNull();
    // Les DEUX batteries génériques RÉELLES du catalogue seedé (BAT-GEL-22,
    // plomb-gel 12 V, et BAT-LIT-5) : ni l'une ni l'autre n'est la LFP Dyness
    // que la fiche décrit — aucun lien, des deux côtés du contrat.
    expect(ficheSlugPourLigne('Batterie Gel 2.2 kWh')).toBeNull();
    expect(ficheSlugPourLigne('Batterie Lithium 5 kWh')).toBeNull();
  });

  it('l’appareillage et le câble d’une marque concurrente ne sont pas liés', () => {
    // Les fiches protection-ac et cablage NOMMENT une marque (Schneider,
    // Nexans) : elles suivent donc la même règle que les fiches produit.
    expect(ficheSlugPourLigne('Coffret AC Legrand 4 modules')).toBeNull();
    expect(ficheSlugPourLigne('Câble solaire Prysmian 6 mm²')).toBeNull();
    // protection-dc ne nomme AUCUNE marque : un coffret DC reste expliqué.
    expect(ficheSlugPourLigne('Coffret DC Hager 2 strings')).toBe('protection-dc');
  });

  it('un onduleur d’une marque concurrente ne renvoie vers aucune fiche onduleur', () => {
    expect(ficheSlugPourLigne('Onduleur hybride 8 kW', 'Growatt')).toBeNull();
    expect(ficheSlugPourLigne('Onduleur réseau 10 kW SMA Sunny Boy')).toBeNull();
    expect(ficheSlugPourLigne('Onduleur hybride Huawei LUNA')).toBeNull();
  });

  it('un compteur d’une autre marque ne renvoie pas vers le Smart Meter Huawei', () => {
    expect(ficheSlugPourLigne('Smart meter Chint DTSU')).toBeNull();
  });

  it('les postes hors catalogue de fiches ne reçoivent aucun lien', () => {
    // « Structure de fixation » a QUITTÉ cette liste le 18/08/2026 : elle a
    // désormais sa fiche (découpage fondateur). Ce qui reste ici n'est pas du
    // MATÉRIEL — pose, étude, transport, ou un métier que nous ne vendons pas.
    for (const ligne of [
      'Main-d’œuvre et mise en service',
      'Étude technique et démarches administratives',
      'Transport et livraison',
      'Groupe électrogène 5 kVA',
      'Pompe immergée 3 CV',
    ]) {
      expect(ficheSlugPourLigne(ligne), `« ${ligne} » ne devrait pas être lié`).toBeNull();
    }
  });

  it('une désignation vide ou absente ne casse rien et ne lie rien', () => {
    expect(ficheSlugPourLigne('')).toBeNull();
    expect(ficheSlugPourLigne('   ')).toBeNull();
    expect(ficheSlugPourLigne(null)).toBeNull();
    expect(ficheSlugPourLigne(undefined)).toBeNull();
    expect(ficheSlugPourLigne(undefined, 'Canadian Solar')).toBeNull();
  });

  it('aucun slug du matcher n’est orphelin : le catalogue les contient tous', () => {
    // Balayage large : tout ce que le matcher peut retourner doit exister.
    const echantillons = [
      ...APPARIEMENTS.map(([d, m]) => ficheSlugPourLigne(d, m)),
      ficheSlugPourLigne('Parafoudre AC type 2'),
      ficheSlugPourLigne('Presse-étoupes'),
    ].filter((s): s is string => s !== null);
    const slugsConnus = new Set(FICHES.map((f) => f.slug));
    for (const slug of echantillons) {
      expect(slugsConnus.has(slug), `slug inconnu du catalogue : ${slug}`).toBe(true);
    }
  });
});

describe('WJ131 — le tableau d’équipement rend bien le lien', () => {
  it('la page calcule le slug par ligne via la fonction pure', () => {
    expect(PROPOSITION).toContain("from '../../lib/ficheMatcher'");
    expect(PROPOSITION).toContain('ficheSlugPourLigne(it.designation, it.marque)');
  });

  it('le lien pointe /produits/<slug>, s’ouvre à part et reste conditionnel', () => {
    expect(PROPOSITION).toContain('{it.ficheSlug ? (');
    expect(PROPOSITION).toContain('href={`/produits/${it.ficheSlug}`}');
    expect(PROPOSITION).toContain('rel="noopener"');
  });

  it('le libellé porte ses trois langues', () => {
    expect(PROPOSITION).toContain('data-fr="Fiche technique" data-en="Datasheet" data-ar="الورقة التقنية"');
  });

  it('le lien vit dans le tableau d’équipement, jamais ailleurs', () => {
    const debut = PROPOSITION.indexOf('id="equipement"');
    const fin = PROPOSITION.indexOf('id="mode-agricole"');
    const idx = PROPOSITION.indexOf('href={`/produits/${it.ficheSlug}`}');
    expect(debut).toBeGreaterThan(0);
    expect(idx).toBeGreaterThan(debut);
    expect(idx).toBeLessThan(fin);
  });
});
