// PV80 — Garde d'ARCHITECTURE de /proposition/<...token>.astro (lecture source).
//
// La page est le document commercial le plus critique du site. Cette garde fixe
// ce que la refonte a décidé, pour qu'une édition future ne le défasse pas par
// inadvertance : l'ordre des 8 chapitres, l'absence TOTALE de crédit, l'unicité
// du bloc graphique, et les ancres dont dépendent la télémétrie et les liens
// internes.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
const PROPOSITION = read('../src/pages/proposition/[...token].astro');

/**
 * Source PRIVÉE DE SES COMMENTAIRES. La garde anti-crédit ci-dessous doit
 * scanner ce que le CLIENT lit, jamais ce que le code raconte : les
 * commentaires de la refonte expliquent précisément ce qui a été supprimé
 * (« mensualité », « éco-prêt »…) et feraient échouer une recherche naïve —
 * pire, ils pousseraient une session future à censurer la documentation au
 * lieu de garder le rendu propre.
 */
const CODE = PROPOSITION
  .replace(/<!--[\s\S]*?-->/g, ' ')      // commentaires HTML/Astro
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ') // commentaires JSX
  .replace(/\/\*[\s\S]*?\*\//g, ' ')     // blocs /* … */
  .replace(/^[ \t]*\/\/.*$/gm, ' ');     // lignes // …

/** Position de la PREMIÈRE occurrence (−1 si absente). */
const at = (needle: string) => PROPOSITION.indexOf(needle);

describe('PV80 — route catch-all', () => {
  it('la page est bien la route catch-all (le fichier existe et lit le dernier segment)', () => {
    expect(PROPOSITION).toContain('tokenFromSegments(');
    // Le token n'est plus lu naïvement comme un paramètre simple.
    expect(CODE).not.toContain('const { token } = Astro.params');
  });

  it('tous les sous-appels partagent la MÊME variable token extraite', () => {
    expect(PROPOSITION).toContain('proposalEndpoint(API_BASE, token)');
    expect(PROPOSITION).toContain('proposalPdfEndpoint(API_BASE, token)');
    expect(PROPOSITION).toContain('data-contact-token={token}');
    expect(PROPOSITION).toContain('data-revision-token={token}');
  });
});

describe('PV80 — plus AUCUN crédit / financement / échelonnement', () => {
  // Formulations réellement affichées au client (jamais des sous-chaînes nues :
  // « taux d'autoconsommation » et « taux de couverture » sont légitimes).
  const BANNED = [
    'Comptant ou échelonné',
    'Paiement échelonné',
    'Comment financer',
    'éco-prêt',
    'À crédit',
    'avec votre banque',
    'offre bancaire',
    'Mensualités calculées',
    'mensualité',
    'taux annuel',
    'taux indicatif',
  ];
  for (const phrase of BANNED) {
    it(`ne contient plus « ${phrase} »`, () => {
      expect(CODE.toLowerCase()).not.toContain(phrase.toLowerCase());
    });
  }

  it('n’importe plus les fonctions de financement/échéancier dans la page', () => {
    expect(CODE).not.toContain('financingComparison,');
    expect(CODE).not.toContain('backendFinancing,');
    expect(CODE).not.toContain('installmentSplit,');
    expect(CODE).not.toContain('INSTALLMENT_MONTH_OPTIONS');
    expect(CODE).not.toContain('data-installment-ttc');
  });

  it('les KPI d’étude légitimes qui contiennent « taux » sont préservés', () => {
    expect(CODE).toContain("Taux d'autoconsommation");
    expect(CODE).toContain('Taux de couverture');
  });
});

describe('PV80 — les 8 chapitres sont dans l’ordre', () => {
  it('héros → toit 3D → installation → production → économies → schéma → prix/signature → confiance', () => {
    const hero = at('id="prop-fold-figures"');
    const roof3d = at('id="roof3d"');
    const install = at('id="installation"');
    const production = at('id="production"');
    const economies = at('id="financing-headline"');
    const sld = at('id="sld"');
    const prix = at('id="options"');
    const signer = at('id="signer"');
    const suite = at('id="etapes-suivantes"');
    for (const [name, idx] of Object.entries({ hero, roof3d, install, production, economies, sld, prix, signer, suite })) {
      expect(idx, `ancre ${name} absente`).toBeGreaterThan(0);
    }
    expect(hero).toBeLessThan(roof3d);
    expect(roof3d).toBeLessThan(install);
    expect(install).toBeLessThan(production);
    expect(production).toBeLessThan(economies);
    expect(economies).toBeLessThan(sld);
    expect(sld).toBeLessThan(prix);
    expect(prix).toBeLessThan(signer);
    expect(signer).toBeLessThan(suite);
  });

  it('« Demander une modification » suit immédiatement le bloc de signature', () => {
    expect(at('id="signer"')).toBeLessThan(at('data-revision-token'));
    expect(at('data-revision-token')).toBeLessThan(at('id="etapes-suivantes"'));
  });

  it('l’ancre lisible #economies double l’id historique observé par la télémétrie', () => {
    expect(PROPOSITION).toContain('id="economies"');
    // WJ55 observe la SECTION (seuil 40 % de surface) : l'id doit rester là.
    expect(PROPOSITION).toContain('<section id="financing-headline"');
    expect(PROPOSITION).toContain("document.getElementById('financing-headline')");
  });
});

describe('PV80 — chapitre 4 : UN SEUL bloc graphique', () => {
  it('les trois dessins sont des CALQUES du même bloc', () => {
    expect(PROPOSITION).toContain('data-prod-layer="monthly"');
    expect(PROPOSITION).toContain('data-prod-layer="daily"');
    expect(PROPOSITION).toContain('data-prod-layer="battery"');
    // ... tous à l'intérieur de la même <section id="production">.
    const start = at('<section id="production"');
    const end = PROPOSITION.indexOf('</section>', at('data-prod-battery-control'));
    for (const layer of ['monthly', 'daily', 'battery']) {
      const idx = at(`data-prod-layer="${layer}"`);
      expect(idx).toBeGreaterThan(start);
      expect(idx).toBeLessThan(end);
    }
  });

  it('la batterie est une CASE À COCHER, plus une section à part entière', () => {
    expect(PROPOSITION).toContain('id="prod-battery-toggle"');
    expect(CODE).not.toContain('<section class="mx-auto max-w-4xl px-5 pt-14 sm:px-8" id="battery-sim"');
    // Le moteur horaire garde ses ids : le script client est inchangé.
    expect(PROPOSITION).toContain('id="battery-sim"');
    expect(PROPOSITION).toContain('id="battery-sim-slider"');
    expect(PROPOSITION).toContain('data-battery-sim-config={batterySimConfig}');
  });

  it('les onglets Standard/Été/Ramadan sont conservés', () => {
    for (const v of ['normal', 'ete', 'ramadan']) {
      expect(PROPOSITION).toContain(`data-curve-variant-btn="${v}"`);
    }
  });

  it('le rendu serveur et le clic client partagent la même fonction pure', () => {
    expect(PROPOSITION).toContain("from '../../lib/propositionPage'");
    expect(PROPOSITION).toContain('productionLayers(prodState0, productionAvailability)');
    expect(PROPOSITION).toContain('productionLayers(state, availability)');
  });

  it('la classe .chart-svg (sonde du gate Lighthouse) survit à la fusion', () => {
    expect(PROPOSITION).toContain('class="chart-svg"');
  });
});

describe('PV80 — chapitre 3 : l’équipement est un tableau, jamais une facture', () => {
  it('le tableau structuré existe et vit AVANT la carte de prix', () => {
    expect(at('id="equipement"')).toBeGreaterThan(0);
    expect(at('id="equipement"')).toBeLessThan(at('id="options"'));
    expect(PROPOSITION).toContain('equipmentGroups.map((group)');
    expect(PROPOSITION).toContain('EQUIPMENT_GROUP_LABELS[group.id]');
  });

  it('aucun prix par ligne d’équipement (prix_unit_* jamais rendu)', () => {
    expect(CODE).not.toContain('prix_unit_ht');
    expect(CODE).not.toContain('prix_unit_ttc');
    // Discipline permanente : aucun prix d'achat / marge côté client.
    expect(CODE).not.toContain('prix_achat');
  });

  it('la carte de prix ne re-liste plus le matériel : elle y renvoie', () => {
    expect(PROPOSITION).toContain('href="#equipement"');
  });
});

describe('PV80 — i18n : tout nouveau texte porte ses trois langues', () => {
  const NEW_LABELS: Array<[string, string, string]> = [
    ['Votre installation', 'Your installation', 'تركيبكم'],
    ['Votre production', 'Your production', 'إنتاجكم'],
    ['Vos économies', 'Your savings', 'توفيراتكم'],
    ['Avec batterie', 'With a battery', 'مع بطارية'],
    ['Sur l’année', 'Over the year', 'على مدار السنة'],
    ['Sur une journée', 'Over a day', 'خلال يوم'],
    ['Ce qui sera posé chez vous', 'What will be installed', 'ما سيتم تركيبه عندكم'],
  ];
  for (const [fr, en, ar] of NEW_LABELS) {
    it(`« ${fr} » est traduit en EN et AR`, () => {
      expect(PROPOSITION).toContain(`data-fr="${fr}"`);
      expect(PROPOSITION).toContain(`data-en="${en}"`);
      expect(PROPOSITION).toContain(`data-ar="${ar}"`);
    });
  }

  it('les apostrophes des nouveaux libellés sont typographiques', () => {
    expect(CODE).not.toContain("data-fr=\"Sur l'année\"");
    expect(CODE).not.toContain("Ce qui sera pose");
    // Les libellés livrés portent bien l'apostrophe typographique.
    expect(PROPOSITION).toContain('data-fr="Sur l’année"');
  });
});
