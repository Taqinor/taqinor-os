/**
 * ACAL308 (D-ACAL-20) — le jeu de réglages mémorisé (`jeuReglages`) s'applique à CHAQUE
 * nouveau pan, jamais aux pans existants, et une valeur saisie à la main prime.
 *
 * Source réelle : `panVierge` (la fabrique de pans du builder) et la liste `CLES_DE_ZONE` de
 * `services/gabarits.py` (lue dans le fichier Python, pas recopiée à la main).
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import process from 'node:process';
import { describe, it, expect } from 'vitest';
import { panVierge } from './zones';
import {
  CLES_JEU,
  appliquerJeuAuPan,
  lireJeuReglages,
  mentionJeuReglages,
  valeursPourPan,
} from './jeuReglages';

const DOCUMENT = {
  version: 2,
  zones: [],
  jeuReglages: {
    presetId: 'toiture-plate-sud',
    libelle: 'Toiture inclinée Est-Ouest',
    valeurs: {
      roofType: 'pitched',
      pitchDeg: 30,
      facingAzimuthDeg: 90,
      facingManual: true,
      // Clés d'un jeu qui ne sont PAS des champs de pan (règles du traducteur) :
      orientation: 'portrait',
      famille: 'est_ouest',
      allee_m: 0.6,
    },
  },
};

describe('ACAL308 — lecture du jeu mémorisé', () => {
  it('relit {presetId, libelle, valeurs} du document', () => {
    const jeu = lireJeuReglages(DOCUMENT);
    expect(jeu?.libelle).toBe('Toiture inclinée Est-Ouest');
    expect(jeu?.presetId).toBe('toiture-plate-sud');
  });

  it('document sans jeu, ou jeu illisible : null', () => {
    expect(lireJeuReglages(null)).toBeNull();
    expect(lireJeuReglages({ zones: [] })).toBeNull();
    expect(lireJeuReglages({ jeuReglages: { libelle: 'x' } })).toBeNull();
    expect(lireJeuReglages({ jeuReglages: { libelle: 'x', valeurs: [] } })).toBeNull();
  });

  it('la mention de l’en-tête nomme le jeu', () => {
    expect(mentionJeuReglages(lireJeuReglages(DOCUMENT)))
      .toBe('Jeu de réglages Toiture inclinée Est-Ouest appliqué aux nouveaux pans');
    expect(mentionJeuReglages(null)).toBe('');
  });
});

describe('ACAL308 — application aux nouveaux pans', () => {
  it('un pan ajouté reçoit les valeurs du jeu', () => {
    const jeu = lireJeuReglages(DOCUMENT);
    const pan = panVierge([]);
    const posees = appliquerJeuAuPan(pan, jeu);

    expect(pan.roofType).toBe('pitched');
    expect(pan.pitchDeg).toBe(30);
    expect(pan.facingAzimuthDeg).toBe(90);
    expect(pan.facingManual).toBe(true);
    expect(posees).toEqual({ roofType: 'pitched', pitchDeg: 30, facingAzimuthDeg: 90, facingManual: true });
    // Les clés qui ne sont pas des champs de pan ne sont JAMAIS posées sur le pan.
    expect(pan).not.toHaveProperty('orientation');
    expect(pan).not.toHaveProperty('famille');
    expect(pan).not.toHaveProperty('allee_m');
  });

  it('deux pans dessinés portent chacun les valeurs du jeu', () => {
    const jeu = lireJeuReglages(DOCUMENT);
    const pans = [panVierge([])];
    pans.push(panVierge(pans));
    for (const pan of pans) appliquerJeuAuPan(pan, jeu);
    expect(pans.map((p) => p.pitchDeg)).toEqual([30, 30]);
    expect(pans.map((p) => p.id)).toEqual(['area-1', 'area-2']);
  });

  it('les pans existants ne changent pas', () => {
    const jeu = lireJeuReglages(DOCUMENT);
    const existant = panVierge([]);
    const avant = JSON.stringify(existant);
    // Ajouter un pan : seul le NOUVEAU reçoit le jeu.
    const neuf = panVierge([existant]);
    appliquerJeuAuPan(neuf, jeu);
    expect(JSON.stringify(existant)).toBe(avant);
    expect(existant.roofType).toBe('flat');
    expect(neuf.roofType).toBe('pitched');
  });

  it('une valeur saisie à la main prime : le jeu n’est posé qu’à la naissance du pan', () => {
    const jeu = lireJeuReglages(DOCUMENT);
    const pan = panVierge([]);
    appliquerJeuAuPan(pan, jeu);
    pan.pitchDeg = 12; // saisie à la main après la création
    // Rien ne ré-applique le jeu au pan existant : la valeur saisie reste.
    expect(pan.pitchDeg).toBe(12);
    // Et une valeur déjà posée sur un pan n'est écrasée que par une NOUVELLE création.
    const autre = panVierge([pan]);
    appliquerJeuAuPan(autre, jeu);
    expect(pan.pitchDeg).toBe(12);
    expect(autre.pitchDeg).toBe(30);
  });

  it('une valeur illisible est ignorée : le pan garde son défaut sur ce point', () => {
    const jeu = lireJeuReglages({
      jeuReglages: { libelle: 'x', valeurs: { roofType: 'dome', pitchDeg: 'raide', facingAzimuthDeg: 400, neededAuto: false } },
    });
    expect(valeursPourPan(jeu)).toEqual({ neededAuto: false });
    const pan = panVierge([]);
    appliquerJeuAuPan(pan, jeu);
    expect(pan.roofType).toBe('flat');
    expect(pan.pitchDeg).toBe(22);
    expect(pan.neededAuto).toBe(false);
  });

  it('sans jeu : le pan reste celui d’aujourd’hui, octet pour octet', () => {
    const pan = panVierge([]);
    const avant = JSON.stringify(pan);
    expect(appliquerJeuAuPan(pan, null)).toEqual({});
    expect(JSON.stringify(pan)).toBe(avant);
  });
});

describe('ACAL308 — parité avec le serveur et câblage', () => {
  it('CLES_JEU = CLES_DE_ZONE de services/gabarits.py (aucune seconde définition d’un jeu)', () => {
    const source = readFileSync(
      resolve(process.cwd(), '../../backend/django_core/apps/calepinage/services/gabarits.py'), 'utf8');
    const bloc = /CLES_DE_ZONE\s*=\s*\(([^)]*)\)/.exec(source)?.[1] ?? '';
    const serveur = [...bloc.matchAll(/'([A-Za-z]+)'/g)].map((m) => m[1]);
    expect([...CLES_JEU]).toEqual(serveur);
  });

  it('addArea applique le jeu au pan NEUF (garde de câblage)', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/scripts/roof-tool-pro11.ts'), 'utf8');
    const debut = source.indexOf('function addArea()');
    const corps = source.slice(debut, source.indexOf('function poserValeursJeuVives', debut));
    expect(corps).toContain('appliquerJeuAuPan(fresh, jeu)');
    expect(corps).toContain('poserValeursJeuVives(posees)');
  });
});
