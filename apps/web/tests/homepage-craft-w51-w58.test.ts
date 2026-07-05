// Gardes du lot CRAFT homepage (W51–W58) — lecture SOURCE en texte
// (convention de site-content-and-look.test.ts / content.test.ts), sans
// navigateur ni build. On affirme :
//   W54 — la section « Fiches chantier » a disparu, la galerie porte les données ;
//   W55 — la bande fondateur nomme le parcours approuvé et lie /à-propos ;
//   W56 — la bande de marques nomme les 5 marques réelles et lie /équipement ;
//   W57 — la frise de parcours bout-en-bout est intégrée (diagnostic → monitoring) ;
//   W58 — les cartes « Nos solutions » portent une iconographie SVG inline ;
//   W53 — la galerie est une grille (plus de masonry columns-*) ;
//   W51 — DiagnosticForm + Faq sont passés au système sombre (navy+or) ;
//   FROZEN — les invariants de comportement du formulaire restent intacts.
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { ui } from '../src/i18n/ui';

const uiFr = ui.fr as Record<string, string>;
const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const index = read('../src/pages/index.astro');
const form = read('../src/components/DiagnosticForm.astro');
const faq = read('../src/components/Faq.astro');
// W64/W65 — la bande fondateur et la bande de marques sont passées en
// composants (FounderPortrait / BrandStrip + src/lib/brands.ts) ; les gardes
// W55/W56 suivent le contenu là où il vit désormais.
const founderPortrait = read('../src/components/FounderPortrait.astro');
const brandStrip = read('../src/components/BrandStrip.astro');
const brandsLib = read('../src/lib/brands.ts');

describe('W54 — plus de double listing des installations', () => {
  it('aucune section ni titre « Fiches chantier » rendu (commentaires exclus)', () => {
    // On retire les commentaires HTML (où la décision est documentée) avant de
    // vérifier qu'aucun MARKUP « Fiches chantier » ne subsiste.
    const noComments = index.replace(/<!--[\s\S]*?-->/g, '');
    expect(noComments).not.toContain('Fiches chantier');
    expect(noComments).not.toContain('Ils produisent déjà leur électricité');
  });

  it('le tableau de cartes données `cases` a été retiré', () => {
    expect(index).not.toMatch(/const cases\s*=/);
    expect(index).not.toContain('cases.map');
  });

  it('la galerie photo reste la preuve : ville · kWc · production · matériel', () => {
    expect(index).toContain('gallery.map');
    // La légende compose ville + kWc + production (si publiée) + type/matériel.
    expect(index).toContain('{g.ville} · {g.kwc}');
    expect(index).toContain('g.prod ?');
    expect(index).toContain('{g.type}');
  });

  it('les cinq installations restent présentes et NON décomptées', () => {
    // 5 slugs distincts dans la galerie (El Jadida 17/6, Casablanca 11/6, Nouaceur 4).
    const slugs = [...index.matchAll(/slug:\s*'([^']+)'/g)].map((m) => m[1]);
    const distinct = new Set(slugs);
    expect(distinct.size).toBe(5);
    expect(distinct).toContain('nouaceur-4-kwc');
    // Aucun décompte trompeur (« N installations / projets »).
    expect(index).not.toMatch(/\b\d+\s+(installations|projets)\b/i);
  });
});

describe('W55/W64 — bande de crédibilité du fondateur (composant FounderPortrait)', () => {
  it("l'accueil NE monte PAS le portrait du fondateur (WA1 / RÈGLE A, 2026-07-04 — pas de visage ni de signature à la première personne sur l'accueil dans aucune locale ; le portrait vit uniquement sur /à-propos ; SUPERSEDE la décision W266 du 2026-07-02)", () => {
    expect(index).not.toContain('FounderPortrait');
  });

  it('nomme le parcours approuvé (docteur-ingénieur + 3 maisons) et lie /à-propos', () => {
    expect(founderPortrait).toContain('Le fondateur');
    expect(founderPortrait).toContain('Huawei, Ericsson et STMicroelectronics');
    // W67 : le lien est désormais localisé via localizeNavHref('/à-propos', locale)
    // (FR inchangé). On vérifie la cible /à-propos plutôt que href="/à-propos".
    expect(founderPortrait).toContain('/à-propos');
    // La conviction « chaque étude validée par le fondateur ».
    expect(founderPortrait).toContain('Chaque étude validée par le fondateur');
  });

  it('portrait fondateur RÉEL servi — FOUNDER_PHOTO pointe un fichier présent (W153, zéro portrait inventé)', () => {
    // W153 (2026-06-21) : le fondateur a fourni son portrait. FOUNDER_PHOTO nomme
    // désormais une base réelle ET chaque dérivé référencé existe sur disque —
    // la garde « aucune image inventée » devient « aucune référence fantôme » :
    // soit null (repli texte), soit un nom dont les fichiers existent vraiment.
    const m = founderPortrait.match(/FOUNDER_PHOTO\s*:\s*string\s*\|\s*null\s*=\s*(?:null|'([^']+)')/);
    expect(m, 'déclaration FOUNDER_PHOTO introuvable').not.toBeNull();
    const base = m![1];
    if (base) {
      for (const w of [640, 480]) {
        for (const ext of ['avif', 'webp']) {
          const p = fileURLToPath(new URL(`../public/photos/${base}-${w}.${ext}`, import.meta.url));
          expect(existsSync(p), `dérivé portrait manquant : ${base}-${w}.${ext}`).toBe(true);
        }
      }
    }
  });
});

describe('W56/W65 — bande de marques tier-1 (composant BrandStrip + brands.ts)', () => {
  it("l'accueil monte le composant BrandStrip", () => {
    expect(index).toContain('<BrandStrip');
    expect(index).toContain("import BrandStrip from '../components/BrandStrip.astro'");
    // L'ancien tableau inline `const brands` a disparu (déplacé en lib).
    expect(index).not.toMatch(/const brands\s*=/);
  });

  it('nomme les marques réelles (dont Jinko, Huawei, Nexans) et lie /équipement', () => {
    expect(brandStrip).toContain('Marques tier-1 · distributeurs officiels au Maroc');
    for (const b of ['Canadian Solar', 'JA Solar', 'Deye', 'Huawei', 'Dyness', 'Jinko', 'Nexans']) {
      expect(brandsLib, `marque manquante : ${b}`).toContain(b);
    }
    // W67 : le lien est désormais localisé via localizeNavHref('/équipement', locale)
    // (FR inchangé : /équipement n'est pas traduit → repli FR, jamais de lien mort).
    expect(brandStrip).toContain('/équipement');
  });
});

describe('W57 — frise de parcours bout-en-bout', () => {
  it('intègre la séquence réelle (diagnostic → monitoring) dans « Comment ça se passe »', () => {
    expect(index).toContain('Diagnostic 60 secondes');
    expect(index).toContain('Visite technique & étude gratuite');
    expect(index).toContain('Mise en service');
    expect(index).toContain('Suivi en temps réel');
    expect(index).toContain('journey.map');
    // L'ancien <ol> à 3 pas n'est plus rendu en double.
    expect(index).not.toContain("Diagnostic en 60 secondes — fourchette immédiate");
  });
});

describe('W58 — cartes « Nos solutions » enrichies (SVG inline)', () => {
  it('chaque carte porte un pictogramme SVG inline (currentColor/brass)', () => {
    expect(index).toContain('const solutionIcons');
    expect(index).toContain('solutionIcons[s.href]');
    // SVG au trait, teinte brass, aucune dépendance/image externe.
    expect(index).toMatch(/<svg[^>]*text-brass-400[^>]*set:html=\{solutionIcons/);
  });
});

describe('W53 — grille (plus de masonry)', () => {
  it('la galerie utilise une grille à hauteurs égales, pas columns-*', () => {
    expect(index).not.toContain('columns-1');
    expect(index).not.toContain('sm:columns-2');
    expect(index).not.toContain('md:columns-3');
    // Grille responsive + cartes à ratio uniforme.
    expect(index).toContain('grid gap-5 sm:grid-cols-2 lg:grid-cols-3');
    expect(index).toContain('aspect-[4/3]');
  });
});

describe('W52 — rythme vertical normalisé', () => {
  it('plus aucune section homepage en py-24 sm:py-32 ou pb-24 sm:pb-32', () => {
    expect(index).not.toContain('py-24 sm:py-32');
    expect(index).not.toContain('pb-24 sm:pb-32');
  });
});

describe('W51 — DiagnosticForm + Faq dans le système sombre', () => {
  it('le formulaire n’est plus sur fond clair (bg-blanc-azur / bg-blanc) — surface nuit', () => {
    expect(form).not.toContain('bg-blanc-azur');
    expect(form).toContain('bg-nuit');
    // Le bandeau d'en-tête, les champs et la réussite parlent désormais lune/or.
    expect(form).toContain('text-brass-300');
    expect(form).toMatch(/bg-nuit-800[^']*text-white/); // inputClass sombre + texte clair
    expect(form).toMatch(/focus:ring-brass-400\/[0-9]+/); // anneau de focus visible (W194: /60)
  });

  it('la FAQ n’est plus sur fond clair — fond nuit, texte lune, marqueur laiton', () => {
    expect(faq).not.toContain('bg-blanc-azur');
    expect(faq).toContain('bg-nuit');
    expect(faq).toContain('text-brass-300');
    expect(faq).toContain('border-brass-400'); // marqueur du résumé
    // Markup details/summary + JSON-LD préservés.
    expect(faq).toContain('<details');
    expect(faq).toContain('application/ld+json');
  });

  it('W249 — l’accueil ne monte plus DiagnosticForm ; la carte « dernière installation » survit hors aside, la capture passe par InstantEstimator', () => {
    // W249 (entonnoir unique) a retiré le second DiagnosticForm de fin d’accueil
    // (il doublonnait les deux widgets InstantEstimator déjà présents) ; la
    // carte navy/or « Dernière installation » reste, mais n’est plus le slot=aside
    // d’un formulaire. La capture se fait désormais via InstantEstimator (W250).
    expect(index).not.toMatch(/<DiagnosticForm\b/); // plus monté sur l’accueil
    expect(index).toContain('InstantEstimator');
    expect(index).toContain('border-t-4 border-t-brass-400');
    expect(index).toContain('Dernière installation livrée');
  });
});

describe('FROZEN — le comportement du formulaire est inchangé (classes seules)', () => {
  it('POST / fetch vers /api/simulate intact', () => {
    expect(form).toContain("fetch('/api/simulate'");
  });

  it('consentement requis + opt-in WhatsApp + champs cachés fbclid/UTM intacts', () => {
    expect(form).toMatch(/name="consent"[^>]*required/);
    expect(form).toMatch(/name="whatsappOptIn"[^>]*checked/);
    for (const k of ['fbclid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']) {
      expect(form).toContain(`name="${k}"`);
    }
  });

  it('les 3 étapes (fieldset data-step) et le texte de soumission sont intacts', () => {
    for (const n of [1, 2, 3]) expect(form).toContain(`data-step="${n}"`);
    // W67 — les libellés visibles du formulaire viennent du dictionnaire (clés
    // form.*) ; le FR reste byte-identique. On vérifie la source de vérité FR.
    expect(uiFr['form.submit']).toBe('Recevoir mon étude sur WhatsApp');
    expect(uiFr['form.progress'].replace('{step}', '1')).toBe('Étape 1 sur 3');
  });

  it('le script de progression (W189 : brass/white) reste piloté tel quel', () => {
    // W189 — les classes bg-azur-600/bg-azur-100 ont été remplacées par
    // bg-brass-400/bg-white/15 (barre plus haute, remplissage laiton).
    // Le script bascule toujours les classes via toggle (même mécanique).
    expect(form).toContain("seg.classList.toggle('bg-brass-400', on)");
    expect(form).toMatch(/data-seg="1" class="[^"]*bg-brass-400/);
  });
});
