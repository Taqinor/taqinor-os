// Garde-fou des fiches techniques (W141–W145) : la bibliothèque /produits et
// l'alignement des slugs avec le moteur de devis Django.
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  FICHES,
  FICHE_CATEGORIES,
  FICHE_FAMILLES,
  FICHE_ALIASES,
  fichesByCategorie,
  ficheBySlug,
  ficheDownloadHref,
  relatedFiches,
  resolveFicheSlug,
} from '../src/lib/fiches';

// Racine des assets publics servis tels quels par Astro (apps/web/public).
const PUBLIC_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../public');

describe('fiches techniques — manifest', () => {
  it('chaque fiche a slug unique, datasheet https et catégorie connue', () => {
    const slugs = new Set<string>();
    for (const f of FICHES) {
      expect(f.slug).toMatch(/^[a-z0-9-]+$/);
      expect(slugs.has(f.slug)).toBe(false);
      slugs.add(f.slug);
      // `datasheet` peut être null (poste sans source officielle VÉRIFIÉE) —
      // mais jamais une URL bricolée : si elle existe, elle est en https.
      if (f.datasheet !== null) expect(f.datasheet).toMatch(/^https:\/\//);
      expect(FICHE_CATEGORIES).toContain(f.categorie);
      expect(f.faits.length).toBeGreaterThan(0);
    }
  });

  it('le téléchargement renvoie la copie auto-hébergée si présente, sinon la source', () => {
    for (const f of FICHES) {
      expect(ficheDownloadHref(f)).toBe(f.pdf ?? f.datasheet);
    }
  });

  it('aucun slug de fiche ne porte le nom d’un alias (l’ancien nom est LIBRE)', () => {
    // Sinon l'alias se mordrait la queue : /produits/<ancien> existerait ET
    // serait redirigé, deux vérités pour la même URL.
    for (const ancien of Object.keys(FICHE_ALIASES)) {
      expect(FICHES.some((f) => f.slug === ancien), `slug encore publié : ${ancien}`).toBe(false);
    }
  });

  // W146 : chaque PDF auto-hébergé (pdf non-null) DOIT exister sur disque sous
  // apps/web/public — sinon le lien /fiches/<slug>.pdf tomberait en 404.
  it('chaque PDF auto-hébergé existe réellement sous public/', () => {
    for (const f of FICHES) {
      if (f.pdf === null) continue;
      expect(f.pdf.startsWith('/'), `pdf doit être une URL absolue de site: ${f.pdf}`).toBe(true);
      // '/fiches/x.pdf' -> <public>/fiches/x.pdf
      const onDisk = resolve(PUBLIC_DIR, '.' + f.pdf);
      expect(existsSync(onDisk), `fichier PDF manquant: ${onDisk}`).toBe(true);
    }
  });

  it('le groupement par catégorie couvre toutes les fiches', () => {
    const grouped = fichesByCategorie().flatMap((g) => g.fiches);
    expect(grouped.length).toBe(FICHES.length);
  });

  // Les slugs DOIVENT correspondre à ceux que le devis premium émet
  // (apps/ventes/quote_engine/residential/theme.py:fiche_slug) — sinon les
  // liens du PDF tombent en 404.
  it('couvre tous les slugs ciblés par les liens du devis', () => {
    for (const slug of [
      'canadian-solar-710',
      'jinko-710',
      'onduleur-huawei-reseau',
      'onduleur-deye-hybride',
      'batterie-dyness',
      'smart-meter-huawei',
      'wifi-dongle-huawei',
      // Découpage fondateur 2026-08-18 — les postes génériques du devis.
      'structure-fixation',
      'cablage',
      'protection-dc',
      'protection-ac',
      'accessoires-pose',
    ]) {
      expect(ficheBySlug(slug), `fiche manquante pour le slug ${slug}`).toBeTruthy();
    }
  });
});

// ── DÉCOUPAGE 11 FAMILLES (fondateur 2026-08-18) ─────────────────────────────
// 8 familles résidentielles (panneaux, onduleur, batterie, structure, câblage,
// protection DC, protection AC, accessoires de pose) + 3 postes de grands
// projets. Les fiches de MARQUE (panneaux, onduleurs) restent plusieurs par
// famille : le client doit lire les faits de SON matériel, pas d'un générique.
describe('découpage 11 familles', () => {
  it('la table des familles compte exactement 11 entrées, 8 + 3', () => {
    expect(FICHE_FAMILLES.length).toBe(11);
    const grands = ['poste-mt-raccordement', 'supervision-comptage', 'structures-grandes-installations'];
    expect(FICHE_FAMILLES.slice(8).map((f) => f.id)).toEqual(grands);
  });

  it('chaque famille pointe des slugs qui existent RÉELLEMENT', () => {
    for (const famille of FICHE_FAMILLES) {
      expect(famille.slugs.length, `famille vide : ${famille.id}`).toBeGreaterThan(0);
      for (const slug of famille.slugs) {
        expect(ficheBySlug(slug), `slug inconnu du catalogue : ${slug}`).toBeTruthy();
      }
    }
  });

  it('les 3 fiches « grands projets » sont normatives, génériques et SANS marque', () => {
    for (const slug of ['poste-mt-raccordement', 'supervision-comptage', 'structures-grandes-installations']) {
      const f = ficheBySlug(slug)!;
      expect(f.categorie).toBe('Grands projets');
      // Contenu normatif : rôle + normes + points de vérification, obligatoires.
      expect(f.role, `rôle manquant : ${slug}`).toBeTruthy();
      expect(f.normes?.length, `normes manquantes : ${slug}`).toBeGreaterThan(0);
      expect(f.verifier?.length, `points de vérification manquants : ${slug}`).toBeGreaterThan(0);
      const texte = `${f.nom} ${f.marque} ${f.modele} ${f.resume} ${f.role} ${f.faits.join(' ')} ${(f.normes ?? []).join(' ')}`.toLowerCase();
      for (const marque of ['schneider', 'legrand', 'hager', 'abb', 'siemens', 'citel', 'nexans', 'huawei', 'deye', 'jinko', 'canadian', 'dyness']) {
        expect(texte, `marque « ${marque} » citée dans ${slug}`).not.toContain(marque);
      }
    }
  });

  it('RÈGLES DE MARQUE du 18/08 : AC peut nommer Schneider, câblage Nexans, DC AUCUNE', () => {
    const dc = ficheBySlug('protection-dc')!;
    const dcTexte = `${dc.nom} ${dc.marque} ${dc.modele} ${dc.resume} ${dc.role} ${dc.faits.join(' ')} ${(dc.benefices ?? []).join(' ')}`.toLowerCase();
    // Bascule Citel décidée mais pas achetée, offre deux-gammes à l'étude :
    // la fiche DC ne nomme AUCUN fabricant tant que ce n'est pas tranché.
    for (const marque of ['citel', 'schneider', 'legrand', 'hager', 'abb', 'siemens', 'dehn']) {
      expect(dcTexte, `marque « ${marque} » citée dans protection-dc`).not.toContain(marque);
    }
    expect(ficheBySlug('protection-ac')!.faits.join(' ')).toContain('Schneider');
    expect(ficheBySlug('cablage')!.faits.join(' ')).toContain('Nexans');
  });

  it('le câblage nomme le câble mais JAMAIS une marque de connecteur', () => {
    const f = ficheBySlug('cablage')!;
    const texte = `${f.resume} ${f.role} ${f.faits.join(' ')} ${(f.benefices ?? []).join(' ')} ${(f.faq ?? []).map((q) => `${q.q} ${q.r}`).join(' ')}`;
    expect(texte).toContain('H1Z2Z2-K');
    // Décision fondateur : les connecteurs restent « d'origine, certifiés du
    // fabricant de vos panneaux » — aucune référence commerciale publiée.
    expect(texte.toLowerCase()).not.toContain('mc4');
    expect(texte.toLowerCase()).not.toContain('stäubli');
    expect(texte.toLowerCase()).not.toContain('staubli');
    expect(texte).toContain('panachage');
  });

  it('AUCUNE fiche n’affiche un nombre d’installations (règle fondateur)', () => {
    for (const f of FICHES) {
      const texte = [
        f.resume, f.role ?? '', ...(f.benefices ?? []), ...f.faits,
        ...(f.normes ?? []), ...(f.verifier ?? []),
        ...(f.faq ?? []).flatMap((q) => [q.q, q.r]),
      ].join(' ').toLowerCase();
      expect(texte, `${f.slug} compte des installations`)
        .not.toMatch(/\d[\d\s]*\s*(installations|chantiers|clients|toitures) (posé|réalis|équipé|livré)/);
      expect(texte, `${f.slug} compte des installations`)
        .not.toMatch(/(plus de|déjà)\s*\d[\d\s]*\s*(installations|chantiers|clients)/);
    }
  });
});

// ── ALIAS DES ANCIENS SLUGS ──────────────────────────────────────────────────
describe('alias des anciens slugs (aucun lien émis ne casse)', () => {
  it('les deux anciens slugs résolvent vers leur fiche actuelle', () => {
    expect(resolveFicheSlug('tableau-protection-ac-dc')).toBe('protection-dc');
    expect(resolveFicheSlug('accessoires-cablage')).toBe('cablage');
    expect(ficheBySlug('tableau-protection-ac-dc')?.slug).toBe('protection-dc');
    expect(ficheBySlug('accessoires-cablage')?.slug).toBe('cablage');
  });

  it('un slug actuel ou inconnu traverse sans être réécrit', () => {
    expect(resolveFicheSlug('protection-dc')).toBe('protection-dc');
    expect(resolveFicheSlug('jinko-710')).toBe('jinko-710');
    expect(resolveFicheSlug('inexistant')).toBe('inexistant');
    expect(resolveFicheSlug(null)).toBe('');
    expect(resolveFicheSlug(undefined)).toBe('');
  });

  it('chaque cible d’alias est une fiche RÉELLE (jamais une redirection vers un 404)', () => {
    for (const [ancien, actuel] of Object.entries(FICHE_ALIASES)) {
      expect(ficheBySlug(actuel), `cible inconnue pour ${ancien} : ${actuel}`).toBeTruthy();
    }
  });

  it('la fiche qui recueille un ancien lien AC/DC mène à l’AUTRE moitié', () => {
    // Sans ce lien, un client venu d'un vieux devis « Tableau de protection
    // AC/DC » ne verrait plus que la moitié de ce qu'il a payé.
    const cible = ficheBySlug(FICHE_ALIASES['tableau-protection-ac-dc'])!;
    const soeurs = relatedFiches(cible).flatMap((g) => g.fiches).map((f) => f.slug);
    expect(soeurs).toContain('protection-ac');
  });
});

describe('fiches sœurs (voirAussi)', () => {
  it('chaque sœur existe et n’est jamais la fiche elle-même', () => {
    for (const f of FICHES) {
      for (const slug of f.voirAussi ?? []) {
        expect(slug, `${f.slug} se référence lui-même`).not.toBe(f.slug);
        expect(ficheBySlug(slug), `sœur inconnue de ${f.slug} : ${slug}`).toBeTruthy();
      }
    }
  });

  it('les deux moitiés de la protection se citent l’une l’autre', () => {
    expect(ficheBySlug('protection-dc')!.voirAussi).toContain('protection-ac');
    expect(ficheBySlug('protection-ac')!.voirAussi).toContain('protection-dc');
  });

  it('« se combine avec » les fait remonter sans jamais dupliquer une fiche', () => {
    for (const f of FICHES) {
      const slugs = relatedFiches(f).flatMap((g) => g.fiches).map((x) => x.slug);
      expect(new Set(slugs).size, `doublon dans « se combine avec » de ${f.slug}`).toBe(slugs.length);
      expect(slugs, `${f.slug} se propose lui-même`).not.toContain(f.slug);
    }
  });
});

// ── GABARIT 7 BLOCS ──────────────────────────────────────────────────────────
// rôle · bénéfices · specs · normes · garantie · à vérifier · FAQ.
// Obligatoire sur les fiches de FAMILLE (aucune fiche constructeur derrière
// elles) ; les fiches produit gardent specs + garantie et n'en portent pas plus.
describe('gabarit 7 blocs des fiches de famille', () => {
  const GENERIQUES = [
    'structure-fixation', 'protection-dc', 'protection-ac', 'cablage',
    'accessoires-pose', 'poste-mt-raccordement', 'supervision-comptage',
    'structures-grandes-installations',
  ];

  it('les 8 fiches de famille portent les 7 blocs, remplis', () => {
    for (const slug of GENERIQUES) {
      const f = ficheBySlug(slug)!;
      expect(f, `fiche manquante : ${slug}`).toBeTruthy();
      expect(f.role, `bloc 1 (rôle) manquant : ${slug}`).toBeTruthy();
      expect(f.benefices?.length, `bloc 2 (bénéfices) manquant : ${slug}`).toBeGreaterThan(0);
      expect(f.faits.length, `bloc 3 (specs) manquant : ${slug}`).toBeGreaterThan(0);
      expect(f.normes?.length, `bloc 4 (normes) manquant : ${slug}`).toBeGreaterThan(0);
      expect(f.garantie, `bloc 5 (garantie) manquant : ${slug}`).toBeTruthy();
      expect(f.verifier?.length, `bloc 6 (à vérifier) manquant : ${slug}`).toBeGreaterThan(0);
      expect(f.faq?.length, `bloc 7 (FAQ) manquant : ${slug}`).toBeGreaterThan(0);
    }
  });

  it('aucune fiche de famille ne prétend avoir une fiche constructeur', () => {
    for (const slug of GENERIQUES) {
      expect(ficheBySlug(slug)!.pdf, `PDF constructeur inventé : ${slug}`).toBeNull();
    }
  });

  it('chaque question de FAQ porte une réponse non vide', () => {
    for (const f of FICHES) {
      for (const item of f.faq ?? []) {
        expect(item.q.trim().length, `question vide dans ${f.slug}`).toBeGreaterThan(0);
        expect(item.r.trim().length, `réponse vide dans ${f.slug}`).toBeGreaterThan(0);
      }
    }
  });
});

// ── RENDU des blocs sur /produits/<slug> ─────────────────────────────────────
describe('rendu du gabarit 7 blocs sur /produits/<slug>', () => {
  const slugPage = readFileSync(
    resolve(dirname(fileURLToPath(import.meta.url)), '../src/pages/produits/[slug].astro'),
    'utf-8',
  );

  it('chaque bloc optionnel est rendu SOUS CONDITION (absent = omis)', () => {
    expect(slugPage).toContain('{fiche.role && (');
    expect(slugPage).toContain('{fiche.benefices && fiche.benefices.length > 0 && (');
    expect(slugPage).toContain('{fiche.normes && fiche.normes.length > 0 && (');
    expect(slugPage).toContain('{fiche.verifier && fiche.verifier.length > 0 && (');
    expect(slugPage).toContain('{fiche.faq && fiche.faq.length > 0 && (');
  });

  it('le bouton « source officielle » disparaît quand aucune n’a été vérifiée', () => {
    expect(slugPage).toContain('{downloadHref && (');
  });
});

// W147 — aperçu de la fiche intégré sur /produits/<slug> : embed si PDF
// auto-hébergé, repli téléchargement sinon ; boîte de hauteur réservée (zéro CLS).
describe('W147 — fiche intégrée sur /produits/<slug>', () => {
  const slugPage = readFileSync(
    resolve(dirname(fileURLToPath(import.meta.url)), '../src/pages/produits/[slug].astro'),
    'utf-8',
  );

  it('l’aperçu est strictement conditionné par la présence du PDF auto-hébergé (sinon téléchargement seul)', () => {
    // branche embed-vs-fallback : pas de PDF /fiches → pas d’aperçu intégré.
    expect(slugPage).toContain('{fiche.pdf && (');
  });

  it('l’aperçu inline est un iframe lazy pointant le PDF auto-hébergé', () => {
    expect(slugPage).toContain('<iframe');
    expect(slugPage).toContain('loading="lazy"');
    expect(slugPage).toContain('${fiche.pdf}#view=FitH');
  });

  it('un repli de téléchargement existe (mobile / sans lecteur PDF)', () => {
    expect(slugPage).toMatch(/href=\{fiche\.pdf\}/);
    expect(slugPage).toContain('Télécharger la fiche (PDF)');
  });

  it('la boîte d’aperçu réserve sa hauteur → zéro CLS', () => {
    expect(slugPage).toMatch(/h-\[80vh\]/);
  });

  it('au moins une fiche a un PDF auto-hébergé à prévisualiser (sinon W147 est inerte)', () => {
    expect(FICHES.some((f) => f.pdf !== null)).toBe(true);
  });
});
