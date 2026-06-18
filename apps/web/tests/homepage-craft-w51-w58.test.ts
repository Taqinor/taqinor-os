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
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const index = read('../src/pages/index.astro');
const form = read('../src/components/DiagnosticForm.astro');
const faq = read('../src/components/Faq.astro');

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

describe('W55 — bande de crédibilité du fondateur', () => {
  it('nomme le parcours approuvé (docteur-ingénieur + 3 maisons) et lie /à-propos', () => {
    expect(index).toContain('Le fondateur');
    expect(index).toContain('docteur-ingénieur');
    expect(index).toContain('Huawei, Ericsson et STMicroelectronics');
    expect(index).toContain('href="/à-propos"');
    // La conviction « chaque étude validée par le fondateur ».
    expect(index).toContain('Chaque étude validée par le fondateur');
  });

  it('ne ship AUCUN portrait inventé (bande texte uniquement)', () => {
    // La section fondateur n'introduit pas de <Picture> de portrait fabriqué.
    expect(index).not.toContain('name="fondateur"');
    expect(index).not.toContain('name="founder"');
  });
});

describe('W56 — bande de marques tier-1', () => {
  it('nomme les CINQ marques réelles et lie /équipement', () => {
    expect(index).toContain('Marques tier-1 · distributeurs officiels au Maroc');
    for (const b of ['Canadian Solar', 'JA Solar', 'Deye', 'Huawei', 'Dyness']) {
      expect(index, `marque manquante : ${b}`).toContain(b);
    }
    expect(index).toContain('href="/équipement"');
    // Exactement cinq marques dans le tableau de données.
    const m = index.match(/const brands\s*=\s*\[([^\]]*)\]/);
    expect(m, 'tableau brands introuvable').toBeTruthy();
    expect(m![1].split(',').filter((s) => s.trim()).length).toBe(5);
  });
});

describe('W57 — frise de parcours bout-en-bout', () => {
  it('intègre la séquence réelle (diagnostic → monitoring) dans « Comment ça se passe »', () => {
    expect(index).toContain('Diagnostic 60 secondes');
    expect(index).toContain('Visite technique & étude gratuite');
    expect(index).toContain('Mise en service');
    expect(index).toContain('Monitoring Deye Cloud');
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
    expect(form).toContain('focus:ring-brass-400/30'); // anneau de focus visible
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

  it('la carte latérale « dernière installation » est recolorée en navy/or', () => {
    // Plus de bg-blanc / azur-600 dans l'aside ; surface cine-card + accents brass.
    expect(index).toContain('border-t-4 border-t-brass-400');
    expect(index).toContain('Dernière installation livrée');
    expect(index).toMatch(/slot="aside"[^>]*cine-card/);
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
    expect(form).toContain('Recevoir mon étude sur WhatsApp');
    expect(form).toContain('Étape 1 sur 3');
  });

  it('le script de progression (bg-azur-600/100) reste piloté tel quel', () => {
    // Les segments statiques correspondent aux classes que le script bascule,
    // pour qu'aucun conflit de fond n'apparaisse (changement de classes seul).
    expect(form).toContain("seg.classList.toggle('bg-azur-600', on)");
    expect(form).toMatch(/data-seg="1" class="[^"]*bg-azur-600/);
  });
});
