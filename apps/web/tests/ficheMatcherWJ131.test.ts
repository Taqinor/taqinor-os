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
import { FICHES, ficheBySlug } from '../src/lib/fiches';

const PROPOSITION = readFileSync(
  fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
  'utf-8',
);

/** Les cas d'appariement attendus : [désignation, marque | undefined, slug]. */
const APPARIEMENTS: Array<[string, string | undefined, string]> = [
  // Panneaux — la MARQUE est décisive, jamais la puissance seule.
  ['Panneau photovoltaïque 710 Wc', 'Canadian Solar', 'canadian-solar-710'],
  ['Panneau CANADIAN SOLAR 710W bifacial', undefined, 'canadian-solar-710'],
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
  // LES DEUX POSTES GÉNÉRIQUES — le cœur de la demande fondateur.
  ['Tableau De Protection AC/DC', undefined, 'tableau-protection-ac-dc'],
  ['Coffret de protection DC', undefined, 'tableau-protection-ac-dc'],
  ['Accessoires', undefined, 'accessoires-cablage'],
  ['Accessoires de pose et de câblage', undefined, 'accessoires-cablage'],
  ['Câblage solaire et connecteurs MC4', undefined, 'accessoires-cablage'],
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

  it('les deux fiches EXPLICATIVES des postes génériques sont publiées et sans marque produit', () => {
    for (const slug of ['tableau-protection-ac-dc', 'accessoires-cablage']) {
      const fiche = ficheBySlug(slug);
      expect(fiche, `fiche manquante : ${slug}`).toBeTruthy();
      expect(fiche!.faits.length).toBeGreaterThan(0);
      // Aucun constructeur : ces postes sont montés sur mesure, donc pas de PDF.
      expect(fiche!.pdf).toBeNull();
      expect(fiche!.datasheet).toMatch(/^https:\/\//);
      // Aucune marque de matériel ne doit s'inviter dans une fiche générique.
      const texte = `${fiche!.nom} ${fiche!.marque} ${fiche!.modele} ${fiche!.resume} ${fiche!.faits.join(' ')}`.toLowerCase();
      for (const marque of ['canadian', 'jinko', 'huawei', 'deye', 'dyness', 'schneider', 'legrand']) {
        expect(texte, `marque « ${marque} » citée dans ${slug}`).not.toContain(marque);
      }
    }
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
    for (const ligne of [
      'Structure de fixation en aluminium',
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
