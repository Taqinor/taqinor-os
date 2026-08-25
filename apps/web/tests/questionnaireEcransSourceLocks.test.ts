// Ordre fondateur 25/08/2026 — « you are adding the address while the client
// already have given its GPS position ??? … search well on the questions we
// should ask, and also on the right order, and finally the number of pages
// those questions should be in ».
//
// Verrous de SOURCE sur /questionnaire/<token>.astro : la logique pure vit
// dans lib/questionnaire.ts (couverte par questionnaire.test.ts), mais le
// CÂBLAGE — chaque question gatée sur `demande()`, la pagination par ÉCRAN,
// la barre de progression qui compte les écrans — vit dans des expressions
// Astro et un <script> qu'aucun test comportemental n'exécute. Sans ces
// verrous, la question d'adresse pourrait revenir sans que rien ne rougisse.
// Même discipline « lecture de la source brute » que visiteSourceLocksTWEB.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const src = read('../src/pages/questionnaire/[token].astro');

describe('questionnaire/[token].astro — on ne redemande JAMAIS une donnée connue', () => {
  it("le champ Adresse est gaté sur demande('contact', 'adresse')", () => {
    expect(src).toContain("{demande('contact', 'adresse') && (");
    // …et le gate précède bien l'input (jamais un champ dessiné hors du gate).
    const gate = src.indexOf("{demande('contact', 'adresse') && (");
    const input = src.indexOf('id="q-adresse"');
    expect(gate).toBeGreaterThan(-1);
    expect(input).toBeGreaterThan(gate);
  });

  it('AUCUN input adresse ne subsiste hors du gate', () => {
    expect(src.match(/id="q-adresse"/g)).toHaveLength(1);
  });

  it('`demande` dérive de `champs` servi par le serveur, jamais d’une devinette locale', () => {
    expect(src).toContain('const champs = data?.champs ?? {};');
    expect(src).toContain('champDemande(champs, section, cle)');
  });

  it('chaque question à valeur des sections mixtes est gatée', () => {
    for (const cle of ['email', 'ville', 'adresse']) {
      expect(src).toContain(`demande('contact', '${cle}')`);
    }
    for (const cle of ['facture_hiver', 'ete_differente', 'raccordement']) {
      expect(src).toContain(`demande('energie', '${cle}')`);
    }
    for (const cle of ['type_toiture', 'surface_toiture_m2', 'roof_age', 'ownership']) {
      expect(src).toContain(`demande('toiture', '${cle}')`);
    }
    expect(src).toContain("demande('equipements', eq.key)");
  });

  it('le GPS déjà connu est ANNONCÉ au client, avec ses vraies coordonnées', () => {
    expect(src).toContain('const gpsDejaConnu =');
    expect(src).toContain('Position déjà enregistrée');
    // Les coordonnées affichées viennent du prefill — jamais une valeur écrite en dur.
    expect(src).toContain("prefillStr('gps_lat')");
  });
});

describe('questionnaire/[token].astro — pagination par ÉCRAN', () => {
  it('regroupe les sections via ecransActifs / initialEcranIndex', () => {
    expect(src).toContain("ecransActifs,");
    expect(src).toContain('const ecrans = ok ? ecransActifs(sections) : [];');
    expect(src).toContain('const startIndex = ok ? initialEcranIndex(ecrans, repondu) : 0;');
  });

  it('la barre de progression compte les ÉCRANS, jamais les sections', () => {
    expect(src).toContain('const total = ecrans.length;');
    expect(src).toContain('{ecrans.map((_, i) => (');
    // La pastille de section (`sections.map`) ne pilote plus la progression.
    expect(src).not.toContain('{sections.map((_, i) => (');
  });

  it('chaque fieldset porte l’index de SON écran et la visibilité en dépend', () => {
    expect(src).toContain('data-ecran={ecranIndex}');
    expect(src).toContain('const idx = Number(fs.dataset.ecran);');
  });

  it('« Continuer » POSTe chaque section de l’écran séparément (contrat POST intact)', () => {
    expect(src).toContain('const sectionsDeLEcran = activeSectionIds();');
    expect(src).toContain('for (const section of sectionsDeLEcran) {');
    // T-WEB : appareil_id reste joint au corps, à l'identique.
    expect(src).toContain('buildQuestionnairePostBody(section, raw, photo, appareilId());');
  });

  it('une section n’est marquée répondue que si quelque chose est PARTI', () => {
    expect(src).toContain('if (result.envoye) repondu[section] = true;');
  });

  it('plus aucun bouton « Passer cette étape » par photo (il sautait les 3)', () => {
    expect(src).not.toContain('-skip`');
  });
});
