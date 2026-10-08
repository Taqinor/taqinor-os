/**
 * YBW53 — le registre des champs du formulaire = le contrat partagé avec l'ERP.
 *  - clés du registre = clés du contrat (hors `refus` et pot de miel) ;
 *  - types, longueurs, obligatoire, valeurs permises identiques ;
 *  - jumeau `src/contract_samples/demande_rdv_site.json` JSON-égal à la copie ERP ;
 *  - aucun champ sensible ; une langue manquante = erreur de types.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { VALEURS_PRODUIT } from '../src/lib/brand';
import { AIDE_MESSAGE, CHAMPS, CLES_CHAMPS, CLES_REFUSEES, POT_DE_MIEL, donneesCollectees, type Champ } from '../src/lib/rdv/champs';

const lire = (rel: string) => JSON.parse(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8'));
const JUMEAU = lire('../src/contract_samples/demande_rdv_site.json');
const ERP = lire('../../../backend/django_core/apps/crm/contract_samples/demande_rdv_site.json');

const TYPES_CONTRAT: Record<string, string> = {
  uuid: 'uuid',
  texte: 'texte',
  email: 'email',
  enum: 'enum',
  booleen: 'booleen',
  'date-heure': 'date-heure ISO 8601 UTC',
  chemin: 'chemin',
};

describe('YBW53 — jumeau du contrat', () => {
  it('le jumeau du site est JSON-égal à la copie ERP', () => {
    expect(JUMEAU).toEqual(ERP);
  });
});

describe('YBW53 — registre = contrat', () => {
  it('mêmes clés, dans le même ordre (hors refus et pot de miel)', () => {
    expect(CLES_CHAMPS).toEqual(Object.keys(JUMEAU.champs));
    expect(Object.keys(JUMEAU.corps).filter((k) => !JUMEAU.refus.includes(k))).toEqual(
      CLES_CHAMPS.filter((k) => k in JUMEAU.corps),
    );
    expect(CLES_CHAMPS).not.toContain(POT_DE_MIEL);
    for (const k of CLES_REFUSEES) expect(CLES_CHAMPS).not.toContain(k);
    expect([...CLES_REFUSEES]).toEqual(JUMEAU.refus);
  });

  it('types, longueurs, obligatoire et valeurs identiques', () => {
    for (const cle of CLES_CHAMPS) {
      const c: Champ = CHAMPS[cle];
      const spec = JUMEAU.champs[cle];
      expect(TYPES_CONTRAT[c.type], cle).toBe(spec.type);
      expect(c.obligatoire, cle).toBe(spec.obligatoire);
      expect(c.max, cle).toBe(spec.max);
      expect(c.valeurs ? [...c.valeurs] : undefined, cle).toEqual(spec.valeurs);
    }
  });

  it('les valeurs de « produit » viennent de brand.ts', () => {
    expect(CHAMPS.produit.valeurs).toBe(VALEURS_PRODUIT);
  });

  it("aucun champ sensible, ni IP ni agent utilisateur", () => {
    const interdits = /cin|identite|passeport|sante|ip|user_agent|agent|naissance/i;
    for (const cle of CLES_CHAMPS) expect(cle).not.toMatch(interdits);
    expect(AIDE_MESSAGE.fr).toMatch(/aucune donnée sensible/);
    expect(AIDE_MESSAGE.en).toMatch(/sensitive data/);
  });

  it('chaque champ a sa donnée et sa finalité dans les deux langues', () => {
    for (const locale of ['fr', 'en'] as const) {
      const lignes = donneesCollectees(locale);
      expect(lignes.map((l) => l.cle)).toEqual(CLES_CHAMPS);
      for (const l of lignes) {
        expect(l.donnee.trim(), `${l.cle} ${locale}`).not.toBe('');
        expect(l.finalite.trim(), `${l.cle} ${locale}`).not.toBe('');
      }
    }
  });

  it('une langue manquante est une erreur de types (npm run check)', () => {
    // @ts-expect-error — finalité anglaise absente : `npm run check` doit rougir.
    const incomplet: Champ = { type: 'texte', obligatoire: false, saisi: true, donnee: { fr: 'x', en: 'x' }, finalite: { fr: 'x' } };
    expect(incomplet.finalite.fr).toBe('x');
  });
});
