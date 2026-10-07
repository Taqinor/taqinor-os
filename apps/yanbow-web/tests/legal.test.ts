/**
 * YBW25 — identités légales : tout inconnu à `null`, rien d'affiché pour une
 * entité qui n'existe pas ; avec une fixture complète, chaque élément requis
 * est produit.
 */
import { describe, expect, it } from 'vitest';
import {
  editeurComplet,
  FORME_SARLAU,
  hebergeurComplet,
  LEGAL,
  type Legal,
  lignesCommunes,
  lignesEditeur,
  lignesMaroc,
  marocComplet,
  nomResponsable,
} from '../src/lib/legal';
import { pagesRendues } from './builtHtml';

/** Fixture FICTIVE (jamais affichée par le site) — valeurs manifestement de test. */
export const LEGAL_COMPLET: Legal = {
  editeur: { nomExact: 'Fixture Test Ltd', partie: 'angleterre_galles', numero: 'TEST0001', siege: '1 Test Street, Testville', tva: 'GBTEST001' },
  maroc: {
    denomination: 'Fixture Test',
    capital: 'CAPITAL-TEST',
    siege: '2 rue du Test, Testville',
    rc: 'RC-TEST',
    ice: 'ICE-TEST',
    identifiantFiscal: 'IF-TEST',
    gerant: 'Gérant Test',
  },
  commun: {
    email: 'test@example.invalid',
    telephone: '+00 0 00 00 00 00',
    directeurPublication: 'Directeur Test',
    hebergeur: {
      valeur: { nom: 'Hébergeur Test', adresse: '3 Test Road', telephone: '+00 1' },
      urlSource: 'https://example.invalid/legal',
      dateLecture: '2026-10-07',
    },
    recepissesCndp: ['CNDP-TEST'],
    representantUe: 'Représentant Test',
    responsableTraitement: 'editeur',
  },
};

describe('YBW25 — état réel : tout est null', () => {
  it('aucun champ fourni', () => {
    expect(Object.values(LEGAL.editeur).every((v) => v === null)).toBe(true);
    expect(Object.values(LEGAL.maroc).every((v) => v === null)).toBe(true);
    const c = LEGAL.commun;
    expect([c.email, c.telephone, c.directeurPublication, c.recepissesCndp, c.representantUe, c.responsableTraitement]).toEqual([
      null,
      null,
      null,
      null,
      null,
      null,
    ]);
    expect(c.hebergeur).toEqual({ valeur: null, urlSource: null, dateLecture: null });
  });

  it('aucune ligne à afficher, aucun bloc complet', () => {
    expect(editeurComplet()).toBe(false);
    expect(marocComplet()).toBe(false);
    expect(hebergeurComplet()).toBe(false);
    expect(lignesEditeur()).toEqual([]);
    expect(lignesMaroc()).toEqual([]);
    expect(lignesCommunes()).toEqual([]);
    expect(nomResponsable()).toBeNull();
  });

  it('un bloc PARTIEL ne s’affiche pas (jamais « Ltd » sans le reste)', () => {
    const partiel: Legal = { ...LEGAL_COMPLET, editeur: { ...LEGAL_COMPLET.editeur, numero: null } };
    expect(lignesEditeur(partiel)).toEqual([]);
    const marocPartiel: Legal = { ...LEGAL_COMPLET, maroc: { ...LEGAL_COMPLET.maroc, ice: '  ' } };
    expect(lignesMaroc(marocPartiel)).toEqual([]);
    // Responsable désigné mais entité incomplète : la marque seule, jamais une forme juridique.
    expect(nomResponsable(partiel)).not.toMatch(/ltd|sarl/i);
  });

  for (const p of pagesRendues()) {
    it(`${p.url} : aucun « Ltd »/« SARL »/RC/ICE ni numéro d’entité rendu`, () => {
      const texte = `${p.document.documentElement.textContent ?? ''} ${p.document.head.innerHTML}`;
      expect(texte).not.toMatch(/\bLtd\b|\bLimited\b|\bSARLA?U?\b|\bICE\b|\bRC\s*:|Companies House|identifiant fiscal/i);
    });
  }
});

describe('YBW25 — fixture complète : chaque élément requis est produit', () => {
  it('bloc éditeur (nom exact, partie, numéro, siège, TVA si existe)', () => {
    expect(lignesEditeur(LEGAL_COMPLET, 'fr')).toEqual([
      { cle: 'nom', valeur: 'Fixture Test Ltd' },
      { cle: 'partie', valeur: 'Angleterre et pays de Galles' },
      { cle: 'numero', valeur: 'TEST0001' },
      { cle: 'siege', valeur: '1 Test Street, Testville' },
      { cle: 'tva', valeur: 'GBTEST001' },
    ]);
    expect(lignesEditeur(LEGAL_COMPLET, 'en')[1].valeur).toBe('England and Wales');
    const sansTva: Legal = { ...LEGAL_COMPLET, editeur: { ...LEGAL_COMPLET.editeur, tva: null } };
    expect(lignesEditeur(sansTva).map((l) => l.cle)).toEqual(['nom', 'partie', 'numero', 'siege']);
  });

  it('bloc SARLAU avec la mention « SARL d’associé unique »', () => {
    const lignes = lignesMaroc(LEGAL_COMPLET, 'fr');
    expect(lignes.map((l) => l.cle)).toEqual(['denomination', 'forme', 'capital', 'siege', 'rc', 'ice', 'if', 'gerant']);
    expect(lignes[1].valeur).toBe(FORME_SARLAU.fr);
    expect(FORME_SARLAU.fr).toBe("SARL d'associé unique");
  });

  it('champs communs (e-mail, téléphone, directeur, hébergeur sourcé, CNDP, représentant UE)', () => {
    expect(lignesCommunes(LEGAL_COMPLET).map((l) => l.cle)).toEqual(['email', 'telephone', 'directeurPublication', 'hebergeur', 'cndp', 'representantUe']);
    // Hébergeur sans source ni date : non affiché.
    const sansSource: Legal = { ...LEGAL_COMPLET, commun: { ...LEGAL_COMPLET.commun, hebergeur: { ...LEGAL_COMPLET.commun.hebergeur, urlSource: null } } };
    expect(lignesCommunes(sansSource).map((l) => l.cle)).not.toContain('hebergeur');
    expect(nomResponsable(LEGAL_COMPLET)).toBe('Fixture Test Ltd');
  });
});
