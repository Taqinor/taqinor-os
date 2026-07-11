// WJ116 — parrainage : code réel + le funnel principal transmet enfin le
// tracking de référence. Deux défauts réels corrigés :
//  (1) /parrainage racontait un code INVENTÉ par le parrain (son prénom, son
//      numéro de dossier) alors que le backend QX35 (LIVE) ne crédite QUE un
//      code qui correspond à un `Client.code_parrainage` EXISTANT (forme
//      `TQ-<id>`) — un code inventé ne matche aucun client, le parrain n'est
//      donc jamais crédité. La copie doit désormais dire la vérité : le code
//      est attribué par Taqinor (conseiller / espace client).
//  (2) devis/mon-toit (le funnel PRINCIPAL) construisait son corps de POST
//      sans jamais joindre les fbclid/utm_* persistés par le Layout — donc
//      TOUTE attribution (parrainage compris) était silencieusement perdue
//      sur le CTA principal, alors que DiagnosticForm (legacy) le faisait
//      déjà et que validateLead accepte déjà ces clés.
// Convention : lecture SOURCE en texte pour les fichiers .astro (comme
// propositionFoldWJ114.test.ts) — pas de montage DOM d'un .astro ici.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { validateLead } from '../src/lib/lead';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const PARRAINAGE_FR = read('../src/pages/parrainage.astro');
const PARRAINAGE_EN = read('../src/pages/en/parrainage.astro');
const PARRAINAGE_AR = read('../src/pages/ar/parrainage.astro');

const MON_TOIT_FR = read('../src/pages/devis/mon-toit.astro');
const MON_TOIT_EN = read('../src/pages/en/devis/mon-toit.astro');
const MON_TOIT_AR = read('../src/pages/ar/devis/mon-toit.astro');

const TRACK_KEYS = ['utm_source', 'utm_campaign', 'utm_medium', 'utm_content', 'utm_term', 'fbclid'];

describe('WJ116 — /parrainage raconte le VRAI mécanisme du code', () => {
  it('FR : ne dit plus « choisissez vous-même » / « votre prénom », référence un code Taqinor (TQ-, conseiller/espace client)', () => {
    expect(PARRAINAGE_FR).not.toContain('choisissez vous-même');
    expect(PARRAINAGE_FR).not.toContain('votre prénom');
    expect(PARRAINAGE_FR).toContain('TQ-');
    expect(
      PARRAINAGE_FR.includes('conseiller') || PARRAINAGE_FR.includes('espace client'),
    ).toBe(true);
  });

  it('EN : no longer says the referrer chooses/makes up the code (first name), references a Taqinor-assigned TQ- code (advisor/customer portal)', () => {
    expect(PARRAINAGE_EN).not.toContain('choose yourself');
    expect(PARRAINAGE_EN).not.toContain('your first name');
    expect(PARRAINAGE_EN).toContain('TQ-');
    expect(
      PARRAINAGE_EN.includes('advisor') || PARRAINAGE_EN.includes('customer portal'),
    ).toBe(true);
  });

  it('AR : ne dit plus « رمز تختاره بنفسك » / « اسمك الأول », référence un code Taqinor (TQ-, مستشار/فضاء العميل)', () => {
    expect(PARRAINAGE_AR).not.toContain('تختاره بنفسك');
    expect(PARRAINAGE_AR).not.toContain('اسمك الأول');
    expect(PARRAINAGE_AR).toContain('TQ-');
    expect(
      PARRAINAGE_AR.includes('مستشار') || PARRAINAGE_AR.includes('فضاء العميل'),
    ).toBe(true);
  });

  it('les trois pages gardent le même lien /devis/mon-toit?utm_source=parrainage&utm_campaign=', () => {
    for (const src of [PARRAINAGE_FR, PARRAINAGE_EN, PARRAINAGE_AR]) {
      expect(src).toContain('devis/mon-toit?utm_source=parrainage&utm_campaign=');
    }
  });
});

describe('WJ116 — devis/mon-toit (funnel principal) transmet enfin fbclid/UTM', () => {
  it.each([
    ['FR', MON_TOIT_FR],
    ['EN', MON_TOIT_EN],
    ['AR', MON_TOIT_AR],
  ])('%s : buildBody lit sessionStorage.getItem("tq_"+k) et joint les 6 TRACK_KEYS', (_label, src) => {
    expect(src).toContain("sessionStorage.getItem('tq_'");
    for (const k of TRACK_KEYS) {
      expect(src).toContain(k);
    }
    // La jonction se fait bien DANS buildBody, avant le point d'insertion du
    // repère GPS facultatif (WJ4) qui suit immédiatement la fermeture du corps.
    const buildBodyIdx = src.indexOf('function buildBody(');
    const mergeCallIdx = src.indexOf('Object.assign(body, readTrackingParams())');
    expect(buildBodyIdx).toBeGreaterThan(0);
    expect(mergeCallIdx).toBeGreaterThan(buildBodyIdx);
  });
});

describe('WJ116 — validateLead accepte déjà utm_source=parrainage / utm_campaign=TQ-482 (contrat inchangé)', () => {
  it('un body qualifié avec utm_source=parrainage + utm_campaign=TQ-482 ressort dans lead.utm', () => {
    const body = {
      fullName: 'Karim Benali',
      phone: '0612345678',
      city: 'Casablanca',
      roofType: 'villa',
      billRange: '1500-3000',
      consent: true,
      utm_source: 'parrainage',
      utm_campaign: 'TQ-482',
    };
    const r = validateLead(body);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.utm.utm_source).toBe('parrainage');
    expect(r.lead.utm.utm_campaign).toBe('TQ-482');
  });
});
