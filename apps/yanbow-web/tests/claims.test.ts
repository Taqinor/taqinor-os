import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  affirmationsPerimees,
  executer,
  verifierChiffres,
  verifierCitations,
  verifierRegistre,
} from '../scripts/check-claims.mjs';
import { AFFIRMATIONS, cite, type Affirmation } from '../src/lib/claims';
import { fait } from '../src/lib/facts';

const SHA = '0123456789abcdef0123456789abcdef01234567';

/** Mini-dépôt temporaire : un fichier de preuve de 3 lignes. */
function depot(): string {
  const racine = mkdtempSync(join(tmpdir(), 'ybw18-'));
  mkdirSync(join(racine, 'src'));
  writeFileSync(join(racine, 'src/preuve.py'), 'a\nb\nc\n');
  return racine;
}

const base = (x: Partial<Affirmation> = {}): Affirmation => ({
  id: 'T-1',
  produit: 'solarbow',
  texte_fr: 'Un fait vérifié.',
  statut: 'construit',
  france: 'neutre',
  publiable: true,
  preuves: ['src/preuve.py:2'],
  verifie_a_sha: SHA,
  ...x,
});

describe('YBW18 — registre : fixtures rouges pour chaque cas', () => {
  const racine = depot();

  it('une affirmation correcte passe', () => {
    expect(verifierRegistre([base()], racine)).toEqual([]);
  });
  it('preuve : fichier absent → erreur', () => {
    expect(verifierRegistre([base({ preuves: ['src/absent.py:1'] })], racine).join()).toMatch(/introuvable/);
  });
  it('preuve : ligne au-delà du fichier → erreur', () => {
    expect(verifierRegistre([base({ preuves: ['src/preuve.py:99'] })], racine).join()).toMatch(/pas de ligne 99/);
  });
  it('preuve mal formée → erreur', () => {
    expect(verifierRegistre([base({ preuves: ['src/preuve.py'] })], racine).join()).toMatch(/mal formée/);
  });
  it('non publiable sans raison → erreur', () => {
    expect(verifierRegistre([base({ publiable: false })], racine).join()).toMatch(/sans raison/);
  });
  it('identifiant dupliqué → erreur', () => {
    expect(verifierRegistre([base(), base()], racine).join()).toMatch(/dupliqué/);
  });
  it('chiffre avec unité dans le texte → erreur', () => {
    expect(verifierRegistre([base({ texte_fr: 'Rentabilisé en 6 ans.' })], racine).join()).toMatch(/6 ans/);
  });
});

describe('YBW18 — citations dans les dictionnaires', () => {
  const reg = [base(), base({ id: 'T-NP', publiable: false, raison_non_publiable: 'non prouvé' })];
  it('citation connue et publiable → ok', () => {
    expect(verifierCitations([{ fichier: 'd.fr.ts', contenu: "titre: cite('T-1').texte_fr" }], reg)).toEqual([]);
  });
  it('citation inconnue → erreur', () => {
    expect(verifierCitations([{ fichier: 'd.fr.ts', contenu: "cite('X-9')" }], reg).join()).toMatch(/inconnue « X-9 »/);
  });
  it('citation non publiable → erreur', () => {
    expect(verifierCitations([{ fichier: 'd.fr.ts', contenu: 'cite("T-NP")' }], reg).join()).toMatch(/NON publiable/);
  });
  it('cite() lève aussi à l’exécution', () => {
    expect(() => cite('INCONNUE')).toThrow(/inconnue/);
    expect(() => cite('MB-EN-SERVICE')).toThrow(/non publiable/);
    expect(cite('MB-CREATION-EN-PAUSE').publiable).toBe(true);
  });
});

describe('YBW18 — chiffres avec unité hors facts.ts', () => {
  it('chiffre avec unité dans un dictionnaire → erreur', () => {
    for (const contenu of ["t: 'Jusqu’à 30 % d’économies'", "t: 'Installé en 2 jours'", "t: 'From 12 kWc'"]) {
      expect(verifierChiffres([{ fichier: 'src/i18n/pages/x.fr.ts', contenu }]).length, contenu).toBe(1);
    }
  });
  it('facts.ts est exempté ; un commentaire aussi ; un nombre sans unité aussi', () => {
    expect(verifierChiffres([{ fichier: 'src/lib/facts.ts', contenu: "v: '30 %'" }])).toEqual([]);
    expect(verifierChiffres([{ fichier: 'src/i18n/pages/x.fr.ts', contenu: '// délai 8 s\nt: "Étape 2"' }])).toEqual([]);
  });
  it('fait() lève sur une valeur absente du registre', () => {
    expect(() => fait('inconnu')).toThrow(/fait inconnu/);
    expect(fait('a', { a: { valeur: 1, source: 's', date: '2026-10-07', proprietaire: 'Reda' } }).valeur).toBe(1);
  });
});

describe('YBW18 — --stale', () => {
  it('liste les affirmations dont un fichier de preuve a changé', () => {
    const reg = [base(), base({ id: 'T-2', preuves: ['src/autre.py:1'] })];
    const perimees = affirmationsPerimees(reg, (_sha, f) => f === 'src/autre.py');
    expect(perimees).toHaveLength(1);
    expect(perimees[0]).toMatch(/^T-2 /);
  });
});

describe('YBW18 — le registre réel et le site réel sont propres', () => {
  it('MarketingBow « en service » = construit_non_prouve, NON publiable', () => {
    const a = AFFIRMATIONS.find((x) => x.id === 'MB-EN-SERVICE');
    expect(a?.statut).toBe('construit_non_prouve');
    expect(a?.publiable).toBe(false);
  });

  it('check-claims sur le dépôt : 0 erreur', async () => {
    const { erreurs } = await executer();
    expect(erreurs).toEqual([]);
  });
});
