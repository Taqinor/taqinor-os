import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { champsLegauxManquants, etatReel, lirePortes, portesOuvertes } from '../scripts/check-launch-gates.mjs';

const LEGAL_VIDE = {
  editeur: { nomExact: null, partie: null, numero: null, siege: null, tva: null },
  maroc: { denomination: null, capital: null, siege: null, rc: null, ice: null, identifiantFiscal: null, gerant: null },
  commun: { email: null, directeurPublication: null, responsableTraitement: null },
};
const LEGAL_PLEIN = {
  editeur: { nomExact: 'X Ltd', partie: 'angleterre_galles', numero: '123', siege: 'Adresse', tva: null },
  maroc: { denomination: null, capital: null, siege: null, rc: null, ice: null, identifiantFiscal: null, gerant: null },
  commun: { email: 'a@b.test', directeurPublication: 'Quelqu’un', responsableTraitement: 'editeur' },
};
const TOUTES = ['/mentions-legales', '/en/legal', '/confidentialite', '/en/privacy'];
const ETAT_VERT = { portes: [], legal: LEGAL_PLEIN, routesCompletes: TOUTES, origine: 'https://x.test', perimees: [], erreursClaims: [] };

describe('YBW85 — contrôle de lancement', () => {
  it('état entièrement franchi : aucune porte ouverte', () => {
    expect(portesOuvertes(ETAT_VERT)).toEqual([]);
  });

  it('chaque cause ouvre sa porte, en français, une ligne par porte', () => {
    expect(portesOuvertes({ ...ETAT_VERT, legal: LEGAL_VIDE }).some((l: string) => l.includes('nom exact'))).toBe(true);
    expect(portesOuvertes({ ...ETAT_VERT, routesCompletes: [] })).toHaveLength(4);
    expect(portesOuvertes({ ...ETAT_VERT, origine: null })).toEqual([expect.stringContaining('Domaine canonique')]);
    expect(portesOuvertes({ ...ETAT_VERT, perimees: ['SB-CRM : x'] })).toEqual([expect.stringContaining('SB-CRM')]);
    expect(portesOuvertes({ ...ETAT_VERT, portes: [{ id: 'DOMAINE', coche: false, description: 'd' }] })).toEqual([
      expect.stringContaining('DOMAINE'),
    ]);
    expect(portesOuvertes({ ...ETAT_VERT, portes: [{ id: 'DOMAINE', coche: true, description: 'd' }] })).toEqual([]);
  });

  it('SARLAU exigée dès qu’une page la cite, pas avant', () => {
    expect(champsLegauxManquants(LEGAL_PLEIN)).toEqual([]);
    const cite = { ...LEGAL_PLEIN, commun: { ...LEGAL_PLEIN.commun, responsableTraitement: 'maroc' } };
    expect(champsLegauxManquants(cite).filter((c: string) => c.startsWith('SARLAU'))).toHaveLength(7);
    const partielle = { ...LEGAL_PLEIN, maroc: { ...LEGAL_PLEIN.maroc, ice: '1' } };
    expect(champsLegauxManquants(partielle).filter((c: string) => c.startsWith('SARLAU'))).toHaveLength(6);
  });

  it('lit les portes du fichier réel', () => {
    const portes = lirePortes(readFileSync(new URL('../docs/LAUNCH_GATES.md', import.meta.url), 'utf-8'));
    expect(portes.length).toBeGreaterThan(10);
    expect(portes.map((p: { id: string }) => p.id)).toContain('TEXTE-FR');
  });

  it('sur l’état actuel : liste exactement les portes ouvertes (manuelles non cochées incluses)', async () => {
    const etat = await etatReel();
    const lignes: string[] = portesOuvertes(etat);
    const ouvertes = etat.portes.filter((p: { coche: boolean }) => !p.coche);
    expect(ouvertes.length).toBeGreaterThan(0);
    for (const p of ouvertes) expect(lignes.some((l) => l.includes(`Porte manuelle ${p.id} `))).toBe(true);
    for (const p of etat.portes.filter((x: { coche: boolean }) => x.coche)) expect(lignes.join('\n')).not.toContain(`Porte manuelle ${p.id} `);
    // une seule ligne par porte : aucune ligne dupliquée
    expect(new Set(lignes).size).toBe(lignes.length);
    // tant que le domaine n'est pas posé, la porte DOMAINE est signalée par le contrôle ET par le fichier
    if (!etat.origine) expect(lignes.some((l) => l.startsWith('Domaine canonique'))).toBe(true);
  }, 60_000);
});
