// Garde-fou des fiches techniques (W141–W145) : la bibliothèque /produits et
// l'alignement des slugs avec le moteur de devis Django.
import { existsSync, readFileSync, statSync } from 'node:fs';
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

  it('datasheetMono, quand présent, est en https (même garde que datasheet)', () => {
    for (const f of FICHES) {
      if (f.datasheetMono === undefined) continue;
      expect(f.datasheetMono).toMatch(/^https:\/\//);
    }
  });

  // G4 (2026-08-19, plainte fondateur) — le SG04LP1 (mono) ne doit plus
  // survivre nulle part dans le catalogue de fiches : la datasheet mono
  // vérifiée est la SG05LP1 (deyeinverter.com, 2023-07-31).
  it('onduleur-deye-hybride pointe SG05LP1 (mono) et SG05LP3 (tri), jamais SG04/SG03', () => {
    const f = ficheBySlug('onduleur-deye-hybride')!;
    expect(f.datasheetMono?.toLowerCase()).toContain('sg05lp1');
    expect(f.datasheet?.toLowerCase()).toContain('sg05lp3');
    expect(f.datasheet?.toLowerCase()).not.toMatch(/sg0[34]/);
    expect(f.datasheetMono?.toLowerCase()).not.toMatch(/sg0[34]/);
    expect(f.modele.toLowerCase()).not.toMatch(/sg0[34]/);
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

  // W199 (fondateur 2026-08-20) — `/fiches/*` est servi
  // `Cache-Control: immutable, max-age=1 an` (apps/web/public/_headers) : un
  // remplacement de contenu SOUS LE MÊME NOM reste invisible pour tout
  // navigateur qui a déjà l'ancien fichier en cache, jusqu'à un an plus tard
  // (bug constaté : le fondateur voyait un aperçu « faux »/cassé alors que
  // `curl` servait déjà le bon fichier). Verrou : chaque PDF auto-hébergé
  // porte un suffixe de version `-AAMM` dans son NOM (schéma documenté en
  // tête de `src/lib/fiches.ts`) — un remplacement de contenu doit donc
  // TOUJOURS produire un nouveau nom de fichier, jamais réécrire le même.
  it('chaque PDF auto-hébergé porte un suffixe de VERSION dans son nom', () => {
    for (const f of FICHES) {
      if (f.pdf === null) continue;
      const filename = f.pdf.split('/').pop()!;
      expect(filename, `pdf sans suffixe de version (schéma <slug>-<modèle>-AAMM.pdf) : ${f.slug} → ${filename}`)
        .toMatch(/-\d{4}\.pdf$/);
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
      // Scindée de la précédente le 18/08/2026 (« a page for each ») : le
      // châssis d'un côté, les plots béton qui le lestent de l'autre.
      'socles-lestage',
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
// La famille `structure` en porte DEUX depuis le 18/08/2026 (ordre fondateur
// « a page for each ») : le châssis et les socles de lestage — deux pièces,
// deux questions du client, deux pages ; une seule famille de devis.
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

  // Découpage fondateur du 18/08/2026 : le châssis et les socles qui le lestent
  // sont deux pages. Chacune reste donc à UN clic de l'autre — sinon le client
  // lirait la moitié de ce qu'il paie, exactement le défaut corrigé sur AC/DC.
  it('la structure et les socles se citent l’une l’autre, et ne se mélangent plus', () => {
    const structure = ficheBySlug('structure-fixation')!;
    const socles = ficheBySlug('socles-lestage')!;
    expect(structure.voirAussi).toContain('socles-lestage');
    expect(socles.voirAussi).toContain('structure-fixation');
    // La cote des plots (fondateur 18/08) vit désormais SUR la fiche socles…
    expect(socles.faits.join(' ')).toContain('30 × 30 × 20 cm');
    // …et la question « faut-il percer ? » avec elle.
    expect(socles.faq!.map((q) => q.q).join(' ')).toContain('percer');
    // La fiche structure, elle, porte les cotes du châssis et plus les socles.
    expect(structure.faits.join(' ')).toContain('41 × 41 mm');
    expect(structure.faits.join(' ')).toContain('120 × 60 mm');
    expect(structure.faits.join(' '), 'la cote des socles traîne encore sur la fiche structure')
      .not.toContain('30 × 30 × 20');
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
    'structure-fixation', 'socles-lestage', 'protection-dc', 'protection-ac',
    'cablage', 'accessoires-pose', 'poste-mt-raccordement',
    'supervision-comptage', 'structures-grandes-installations',
  ];

  it('les 9 fiches de famille portent les 7 blocs, remplis', () => {
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
    // EXCEPTION : `cablage` (fondateur 2026-08-20, V2) — ce poste générique
    // nomme déjà une marque unique dans ses `faits` (« Marque Nexans, choix
    // Taqinor confirmé ») : contrairement aux AUTRES postes génériques
    // (accessoires-pose, structure-fixation…), il a une VRAIE fiche
    // constructeur Nexans H1Z2Z2-K derrière lui, désormais auto-hébergée
    // pour l'aperçu intégré. `protection-ac` cite Schneider de la même façon
    // mais SANS PDF Nexans/Schneider auto-hébergé demandé par le fondateur :
    // elle reste donc dans la règle générale ci-dessous, `cablage` seul en
    // sort.
    for (const slug of GENERIQUES) {
      if (slug === 'cablage') continue;
      expect(ficheBySlug(slug)!.pdf, `PDF constructeur inventé : ${slug}`).toBeNull();
    }
    expect(ficheBySlug('cablage')!.pdf).toBe('/fiches/cablage-h1z2z2k-2608.pdf');
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

  // G4 (2026-08-19) — le second lien datasheet (gamme monophasée) est rendu
  // SOUS CONDITION, comme tout bloc optionnel de ce gabarit : absent pour
  // toute fiche sans `datasheetMono`.
  it('le second lien datasheet (mono) est rendu sous condition', () => {
    expect(slugPage).toContain('{fiche.datasheetMono && (');
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

// ── PHOTOS D'ILLUSTRATION (fondateur 2026-08-18) ─────────────────────────────
// Une fiche peut porter une photo — mais SEULEMENT si ses droits sont
// vérifiables. Le registre `public/fiches/photos/CREDITS.md` est la source de
// vérité (fichier · fiche · page source · auteur · licence · attribution
// requise) et ces tests l'opposent à `fiches.ts` : déclarer une photo sans
// l'inscrire au registre, ou l'y inscrire « attribution requise » sans rendre
// de crédit, casse la suite.
describe('photos des fiches — droits vérifiables', () => {
  const PHOTOS_DIR = resolve(PUBLIC_DIR, 'fiches/photos');
  const CREDITS_PATH = resolve(PHOTOS_DIR, 'CREDITS.md');

  /** Une ligne du tableau de CREDITS.md, décodée. */
  interface CreditRow {
    fichier: string;
    slug: string;
    source: string;
    auteur: string;
    licence: string;
    attributionRequise: boolean;
  }

  const credits: CreditRow[] = readFileSync(CREDITS_PATH, 'utf-8')
    .split('\n')
    .filter((ligne) => /^\|\s*`[^`]+\.(jpe?g|png|webp|avif)`\s*\|/i.test(ligne))
    .map((ligne) => {
      const cellules = ligne.split('|').slice(1, -1).map((c) => c.trim());
      return {
        fichier: cellules[0].replace(/`/g, ''),
        slug: cellules[1].replace(/`/g, ''),
        source: cellules[2],
        auteur: cellules[3],
        licence: cellules[4],
        attributionRequise: /\boui\b/i.test(cellules[5]),
      };
    });

  const avecPhoto = FICHES.filter((f) => f.photo);

  // DEUX classes de droits, et deux seulement (règle fondateur du 18/08/2026).
  //
  //  1. PHOTO DE CHANTIER TAQINOR — droits fondateur. La MEILLEURE classe :
  //     notre matériel, notre équipe, notre pose réelle. Aucune page de licence
  //     externe n'existe et aucune attribution n'est due ; la colonne « Source »
  //     enregistre à la place l'ORIGINAL `/photos/` dont le JPEG dérive, qui
  //     doit exister sur disque — c'est la traçabilité qui remplace l'URL.
  //  2. Photo libre EXTERNE : Wikimedia Commons, Unsplash, Pexels, et rien
  //     d'autre. Une médiathèque constructeur exige une autorisation écrite
  //     pour l'usage commercial — elle n'entre jamais ici.
  const LICENCE_TAQINOR = /droits fondateur/i;
  const HOTES_AUTORISES = ['commons.wikimedia.org', 'unsplash.com', 'pexels.com'];
  // Familles de licences EXTERNES acceptées, telles qu'écrites au registre.
  const LICENCES_OK = /(CC BY|CC BY-SA|CC0|domaine public|Unsplash|Pexels)/i;

  it('le registre CREDITS.md existe et décrit au moins une image', () => {
    expect(existsSync(CREDITS_PATH), `registre manquant : ${CREDITS_PATH}`).toBe(true);
    expect(credits.length, 'aucune ligne d’image lisible dans CREDITS.md').toBeGreaterThan(0);
  });

  it('une photo est TOUJOURS auto-hébergée sous /fiches/photos (jamais un hotlink)', () => {
    for (const f of avecPhoto) {
      expect(f.photo!.startsWith('/fiches/photos/'), `chemin hors dossier : ${f.slug} → ${f.photo}`).toBe(true);
      expect(f.photo!, `hotlink interdit sur ${f.slug}`).not.toMatch(/^https?:\/\//);
    }
  });

  it('chaque photo déclarée existe réellement sur disque, et reste légère', () => {
    for (const f of avecPhoto) {
      const surDisque = resolve(PUBLIC_DIR, '.' + f.photo!);
      expect(existsSync(surDisque), `fichier image manquant : ${surDisque}`).toBe(true);
      // Garde-fou de poids : on sert l'original en attendant AVIF/WebP, il ne
      // doit donc jamais être un 20 Mpx sorti tel quel de Commons.
      const ko = statSync(surDisque).size / 1024;
      expect(ko, `${f.photo} pèse ${Math.round(ko)} Ko`).toBeLessThan(400);
    }
  });

  it('chaque photo est inscrite au registre, sur la bonne fiche, avec une source autorisée', () => {
    for (const f of avecPhoto) {
      const fichier = f.photo!.split('/').pop()!;
      const ligne = credits.find((c) => c.fichier === fichier);
      expect(ligne, `photo absente de CREDITS.md : ${fichier}`).toBeTruthy();
      expect(ligne!.slug, `CREDITS.md rattache ${fichier} à la mauvaise fiche`).toBe(f.slug);
      expect(ligne!.auteur.length, `auteur manquant pour ${fichier}`).toBeGreaterThan(0);

      if (LICENCE_TAQINOR.test(ligne!.licence)) {
        // Photo de chantier TAQINOR : pas d'URL de licence à citer — le registre
        // enregistre l'ORIGINAL `/photos/` dont ce JPEG dérive, et cet original
        // doit RÉELLEMENT exister (sinon la provenance n'est plus vérifiable).
        const original = ligne!.source.replace(/`/g, '').trim();
        expect(original.startsWith('/photos/'), `origine TAQINOR illisible pour ${fichier} : ${ligne!.source}`).toBe(true);
        expect(
          existsSync(resolve(PUBLIC_DIR, '.' + original)),
          `original introuvable pour ${fichier} : ${original}`,
        ).toBe(true);
        // Elle ne peut PAS exiger d'attribution : le fondateur en détient les droits.
        expect(ligne!.attributionRequise, `attribution exigée à tort sur ${fichier}`).toBe(false);
      } else {
        expect(ligne!.licence, `licence non reconnue pour ${fichier} : ${ligne!.licence}`).toMatch(LICENCES_OK);
        expect(ligne!.source, `source non https pour ${fichier}`).toMatch(/https:\/\//);
        expect(
          HOTES_AUTORISES.some((h) => ligne!.source.includes(h)),
          `source interdite pour ${fichier} : ${ligne!.source}`,
        ).toBe(true);
      }
    }
  });

  // Les deux fiches de structure montrent NOTRE pose, pas un équivalent trouvé
  // en ligne : c'est tout l'objet de l'ordre du 18/08 (« the old picture »).
  it('la structure et les socles sont illustrés par nos PROPRES photos de chantier', () => {
    for (const slug of ['structure-fixation', 'socles-lestage']) {
      const f = ficheBySlug(slug)!;
      expect(f.photo, `photo manquante sur ${slug}`).toBeTruthy();
      const ligne = credits.find((c) => c.fichier === f.photo!.split('/').pop()!)!;
      expect(ligne.licence, `${slug} n'est pas illustré par une photo TAQINOR`).toMatch(LICENCE_TAQINOR);
      // Droits fondateur ⇒ aucune attribution rendue.
      expect(f.photoCredit, `crédit inventé sur ${slug}`).toBeUndefined();
    }
  });

  // LA RÈGLE, encodée : licence à attribution ⇒ crédit obligatoire ; licence
  // sans attribution ⇒ pas de crédit inventé.
  it('licence à attribution ⇒ photoCredit obligatoire (et inversement)', () => {
    for (const f of avecPhoto) {
      const fichier = f.photo!.split('/').pop()!;
      const ligne = credits.find((c) => c.fichier === fichier)!;
      expect(
        !!f.photoCredit,
        ligne.attributionRequise
          ? `photoCredit manquant alors que ${fichier} est sous ${ligne.licence}`
          : `photoCredit inventé alors que ${fichier} n’exige aucune attribution`,
      ).toBe(ligne.attributionRequise);
    }
  });

  it('un photoCredit nomme l’auteur du registre ET sa licence', () => {
    for (const f of avecPhoto) {
      if (!f.photoCredit) continue;
      const ligne = credits.find((c) => c.fichier === f.photo!.split('/').pop()!)!;
      expect(f.photoCredit, `crédit sans « © » : ${f.slug}`).toContain('©');
      expect(f.photoCredit, `crédit sans auteur : ${f.slug}`).toContain(ligne.auteur);
      expect(f.photoCredit, `crédit sans licence : ${f.slug}`).toMatch(LICENCES_OK);
    }
  });

  it('aucun photoCredit ne pend sans photo', () => {
    for (const f of FICHES) {
      if (f.photo) continue;
      expect(f.photoCredit, `crédit orphelin sur ${f.slug}`).toBeUndefined();
    }
  });

  it('les fiches de MARQUE restent sans photo (jamais le matériel d’un autre fabricant)', () => {
    // Montrer un module ou un onduleur d'une AUTRE marque sous le nom du
    // produit vendu serait un fait faux — règle « faits vérifiés uniquement ».
    for (const slug of [
      'canadian-solar-710', 'jinko-710', 'onduleur-deye-hybride',
      'onduleur-huawei-reseau', 'batterie-dyness', 'smart-meter-huawei',
      'wifi-dongle-huawei',
    ]) {
      expect(ficheBySlug(slug)!.photo, `photo générique sur une fiche de marque : ${slug}`).toBeUndefined();
    }
  });
});

describe('rendu de la photo sur /produits/<slug>', () => {
  const slugPage = readFileSync(
    resolve(dirname(fileURLToPath(import.meta.url)), '../src/pages/produits/[slug].astro'),
    'utf-8',
  );

  it('la photo n’est rendue que si elle existe (absente = AUCUN changement)', () => {
    expect(slugPage).toContain('{fiche.photo && (');
    expect(slugPage).toContain('src={fiche.photo}');
  });

  it('l’image est lazy, décrite en français, et fluide', () => {
    expect(slugPage).toMatch(/src=\{fiche\.photo\}[\s\S]{0,400}?loading="lazy"/);
    expect(slugPage).toContain('alt={`${fiche.nom} — ${fiche.modele}`}');
    expect(slugPage).toMatch(/w-full/);
  });

  it('la boîte réserve son ratio → zéro CLS même avant chargement', () => {
    expect(slugPage).toMatch(/aspect-\[16\/9\]/);
    expect(slugPage).toMatch(/object-cover/);
  });

  it('la ligne de crédit est discrète et conditionnelle', () => {
    expect(slugPage).toContain('{fiche.photoCredit && (');
    expect(slugPage).toMatch(/<figcaption[^>]*text-xs/);
  });

  it('l’optimisation AVIF/WebP différée est documentée dans le code', () => {
    expect(slugPage).toContain('scripts/process-photos.mjs');
  });
});
