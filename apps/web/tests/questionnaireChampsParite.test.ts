// QJR632 — parité contrat ↔ page : toute colonne que le serveur dit « écrite »
// (colonnes_ecrites du contrat QJR512) doit avoir un contrôle sur la page,
// c'est-à-dire figurer dans collectSectionRaw de [token].astro.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { EQUIPEMENT_KEYS } from '../src/lib/questionnaire';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const contrat = JSON.parse(
  read('../../../backend/django_core/apps/crm/contract_samples/questionnaire_lead.json'),
) as { colonnes_ecrites: Record<string, string[]> };
const src = read('../src/pages/questionnaire/[token].astro');
const debut = src.indexOf('function collectSectionRaw');
const fin = src.indexOf('function ', debut + 10);
const collect = src.slice(debut, fin);

// Sections posées par le SERVEUR (contrat d'abord, PACT10) AVANT la page qui les
// dessine. Une entrée = un identifiant de tâche, jamais « plus tard ». La tâche
// nommée RETIRE l'entrée : le test « encore en attente » ci-dessous rougit dès que
// la page porte toutes les colonnes, pour que l'exemption ne survive pas au code.
const SECTIONS_POSEES_AVANT_LA_PAGE: Readonly<Record<string, string>> = {
  pompage: 'AGR411 (serveur, sur main) — la page /questionnaire/[token] la dessine avec AGW408 (WEB_PLAN).',
};

describe('questionnaire — parité colonnes_ecrites ↔ collectSectionRaw', () => {
  it('collectSectionRaw est bien localisé', () => {
    expect(debut).toBeGreaterThan(0);
    expect(collect.length).toBeGreaterThan(200);
  });

  it('chaque section en attente existe dans le contrat (aucune exemption périmée)', () => {
    for (const section of Object.keys(SECTIONS_POSEES_AVANT_LA_PAGE)) {
      expect(contrat.colonnes_ecrites[section], section).toBeDefined();
    }
  });

  for (const [section, colonnes] of Object.entries(contrat.colonnes_ecrites)) {
    if (SECTIONS_POSEES_AVANT_LA_PAGE[section] !== undefined) {
      it(`${section} est encore en attente de sa page (${SECTIONS_POSEES_AVANT_LA_PAGE[section]})`, () => {
        expect(colonnes.length).toBeGreaterThan(0);
        expect(colonnes.every((col) => collect.includes(col))).toBe(false);
      });
      continue;
    }
    for (const col of colonnes) {
      it(`${section}.${col} a un contrôle sur la page`, () => {
        // Les équipements oui/non sont posés via la boucle EQUIPEMENT_KEYS.
        const viaBoucle = collect.includes('EQUIPEMENT_KEYS') && (EQUIPEMENT_KEYS as readonly string[]).includes(col);
        expect(collect.includes(col) || viaBoucle).toBe(true);
      });
    }
  }
});
