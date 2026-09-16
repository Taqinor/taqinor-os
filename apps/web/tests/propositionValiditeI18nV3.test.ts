// PREVIEW-V3-FIX (16/09/2026, audit C4) — LA DATE DE VALIDITÉ PARLE LA LANGUE
// DU LECTEUR.
//
// Le défaut : `resolveValidity` ne produisait qu'un libellé FRANÇAIS, injecté
// tel quel dans `data-en`/`data-ar`. Rendu constaté avant ce correctif :
// EN « valid up to and including 15 octobre 2026 » ; AR « إلى غاية 15 octobre
// 2026 ضمناً », que l'algorithme bidi réordonnait visuellement en « octobre 15
// 2026 » — sur la phrase de l'art. 29-6, la première que lit un client
// arabophone. Les trois rendus héros pré-existaient, mais DORMANTS :
// `date_validite` n'était pas servie ; merger le backend PREVIEW-V3 seul
// aurait réveillé le défaut en production.
//
// Deux gardes : les libellés PURS (mois marocains en arabe, mois anglais) et
// la dérivation côté page (lecture SOURCE, même convention que les autres
// modules de cette page).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { formatDateLang, parseBackendDate, resolveValidity } from '../src/lib/proposition';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const PROPOSITION = read('../src/pages/proposition/[...token].astro');
const LE_15_OCTOBRE = parseBackendDate('2026-10-15')!;

describe('audit C4 — le mois suit la langue', () => {
  it('formate le MÊME jour en français, anglais et arabe marocain', () => {
    expect(formatDateLang(LE_15_OCTOBRE, 'fr')).toBe('15 octobre 2026');
    expect(formatDateLang(LE_15_OCTOBRE, 'en')).toBe('15 October 2026');
    expect(formatDateLang(LE_15_OCTOBRE, 'ar')).toBe('15 أكتوبر 2026');
  });

  it('utilise les mois MAROCAINS, pas le jeu levantin', () => {
    // août → « غشت » (et non « أغسطس ») ; décembre → « دجنبر » (et non
    // « ديسمبر ») ; juillet → « يوليوز ». C'est le jeu du Bulletin officiel.
    expect(formatDateLang(parseBackendDate('2026-08-03')!, 'ar')).toBe('3 غشت 2026');
    expect(formatDateLang(parseBackendDate('2026-12-31')!, 'ar')).toBe('31 دجنبر 2026');
    expect(formatDateLang(parseBackendDate('2026-07-01')!, 'ar')).toBe('1 يوليوز 2026');
  });

  it('aucun mot français ne subsiste dans le libellé arabe ou anglais', () => {
    for (let mois = 1; mois <= 12; mois += 1) {
      const d = parseBackendDate(`2026-${String(mois).padStart(2, '0')}-15`)!;
      const fr = formatDateLang(d, 'fr');
      expect(formatDateLang(d, 'ar')).not.toBe(fr);
      expect(formatDateLang(d, 'en')).not.toBe(fr);
      // Aucun caractère latin accentué (le tell-tale du mois français).
      expect(formatDateLang(d, 'ar')).not.toMatch(/[a-zàâçéèêëîïôûùüÿœ]/i);
    }
  });

  it('resolveValidity sert les trois libellés, ou aucun', () => {
    const v = resolveValidity({ date_validite: '2026-10-15' } as never, new Date(Date.UTC(2026, 5, 22)));
    expect(v.label).toBe('15 octobre 2026');
    expect(v.labelEn).toBe('15 October 2026');
    expect(v.labelAr).toBe('15 أكتوبر 2026');
    const vide = resolveValidity({} as never, new Date(Date.UTC(2026, 5, 22)));
    expect(vide.label).toBeNull();
    expect(vide.labelEn).toBeNull();
    expect(vide.labelAr).toBeNull();
  });

  it('la page injecte labelEn/labelAr, plus jamais `label` dans data-en/data-ar', () => {
    // Les trois phrases de validité (héros, récap de signature, barre
    // collante) doivent lire le libellé de LEUR langue.
    expect(PROPOSITION).toContain('data-en={`Quote valid until ${validity.labelEn ?? validity.label}`}');
    expect(PROPOSITION).toContain('${validity.labelAr ?? validity.label} ضمناً.`}');
    expect(PROPOSITION).toContain('data-en={`This proposal and its price are valid up to and including ${validity.labelEn ?? validity.label}.`}');
    // Le littéral fautif (le libellé FR dans un attribut EN/AR) a disparu.
    expect(PROPOSITION).not.toContain('data-en={`Quote valid until ${validity.label}`}');
    expect(PROPOSITION).not.toContain('including ${validity.label}.`}');
  });

  it('la date de validité n’est plus affichée DEUX fois dans le héros', () => {
    // WJ15 : sa place est contre le PRIX. Le doublon du bloc Référence/Date
    // est parti ; seul l’état « offre échue » y reste.
    const occurrences = PROPOSITION.split('Devis valable jusqu’au').length - 1;
    // 2 = l’attribut data-fr + le texte visible de LA SEULE ligne restante.
    expect(occurrences).toBe(2);
  });

  it('« Capital » porte ses trois langues (RC/ICE sont des sigles)', () => {
    expect(PROPOSITION).toContain('Share capital ${LEGAL_IDENTITY.capital}');
    expect(PROPOSITION).toContain('رأس المال ${LEGAL_IDENTITY.capital}');
  });
});
