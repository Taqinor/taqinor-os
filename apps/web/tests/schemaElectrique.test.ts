// LOT 6 (SCHEL-W1) — lecture défensive du « schéma électrique » du devis (page client) et plan de
// dessin. Les exemples sont ceux du CONTRAT (`src/contract_samples/schema_electrique.json`).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { choisirSld, parseSchemaElectrique, planSchema } from '../src/lib/schemaElectrique';

const contrat = JSON.parse(
  readFileSync(resolve(__dirname, '../src/contract_samples/schema_electrique.json'), 'utf8'),
) as Record<string, any>;
const exemple = () => structuredClone(contrat.exemple.schema_electrique);
const exempleStandard = () => structuredClone(contrat.exemple_standard.schema_electrique);

describe('parseSchemaElectrique — exemples du contrat', () => {
  it('exemple complet : deux options lues', () => {
    const s = parseSchemaElectrique(exemple())!;
    expect(s).not.toBeNull();
    expect(s.options.sans_batterie?.chaines).toHaveLength(2);
    expect(s.options.avec_batterie?.chaines).toHaveLength(4);
    expect(s.options.avec_batterie?.batterie?.capaciteKwh).toBe(15.36);
    expect(s.options.sans_batterie?.batterie).toBeNull();
  });

  it('exemple standard : calibres masqués → champs null conservés null (jamais devinés)', () => {
    const s = parseSchemaElectrique(exempleStandard())!;
    expect(s.options.sans_batterie).toBeNull();
    const d = s.options.avec_batterie!;
    expect(d.calibresMasques).toBe(true);
    expect(d.batterie?.tensionV).toBeNull();
    expect(d.coffretDc?.every((o) => o.calibre === null)).toBe(true);
  });
});

describe('parseSchemaElectrique — formes inattendues → null, jamais un throw', () => {
  const mauvais: unknown[] = [
    undefined, null, 0, 'x', [], {}, { options: null }, { options: [] }, { options: {} },
    { options: { sans_batterie: null, avec_batterie: null } },
  ];
  it.each(mauvais.map((m, i) => [i, m]))('entrée %s', (_i, m) => {
    expect(parseSchemaElectrique(m)).toBeNull();
  });

  it('version inconnue → option ignorée', () => {
    const p = exemple();
    p.options.sans_batterie.version = 2;
    const s = parseSchemaElectrique(p)!;
    expect(s.options.sans_batterie).toBeNull();
    expect(s.options.avec_batterie).not.toBeNull();
  });

  it('document rangé sous la mauvaise option → ignoré (jamais celui de l’autre option)', () => {
    const p = exemple();
    p.options.sans_batterie = p.options.avec_batterie;
    expect(parseSchemaElectrique(p)!.options.sans_batterie).toBeNull();
  });

  it('chaîne sans nombre de panneaux valide → option ignorée', () => {
    const p = exemple();
    p.options.avec_batterie.chaines[0].nb_panneaux = '12';
    expect(parseSchemaElectrique(p)!.options.avec_batterie).toBeNull();
  });

  it('organe malformé, nombre infini, état de côté réseau inconnu → option ignorée', () => {
    const a = exemple();
    a.options.avec_batterie.coffret_dc.organes[0].titre = 42;
    expect(parseSchemaElectrique(a)!.options.avec_batterie).toBeNull();
    const b = exemple();
    b.options.avec_batterie.onduleurs[0].puissance_kw = Number.POSITIVE_INFINITY;
    expect(parseSchemaElectrique(b)!.options.avec_batterie).toBeNull();
    const c = exemple();
    c.options.avec_batterie.cote_reseau.etat = 'peut-etre';
    expect(parseSchemaElectrique(c)!.options.avec_batterie).toBeNull();
  });

  it('couleur de chaîne hors forme rgb()/#hex → null (jamais injectée)', () => {
    const p = exemple();
    p.options.avec_batterie.chaines[0].couleur = 'red;background:url(x)';
    expect(parseSchemaElectrique(p)!.options.avec_batterie!.chaines[0].couleur).toBeNull();
  });
});

describe('planSchema', () => {
  const doc = (k: 'sans_batterie' | 'avec_batterie') => parseSchemaElectrique(exemple())!.options[k]!;

  it('avec batterie : 4 chaînes, entrées, onduleur, carte batterie, côté réseau', () => {
    const p = planSchema(doc('avec_batterie'));
    expect(p.chaines.map((c) => c.titre.fr)).toEqual([
      'Chaîne 1 · 12 panneaux',
      'Chaîne 2 · 12 panneaux',
      'Chaîne 3 · 12 panneaux',
      'Chaîne 4 · 12 panneaux',
    ]);
    expect(p.chaines[0].puissance).toBe('12 × 715 Wc');
    expect(p.chaines[2].flux?.fr).toBe('Chaîne 3 → entrée 2');
    expect(p.chaines[0].couleur).toBe('rgb(36, 130, 214)');
    expect(p.onduleurs[0].designation).toBe('Deye SUN-20K-SG05LP3');
    expect(p.onduleurs[0].entrees?.fr).toBe('2 entrées');
    expect(p.batterie?.unites?.fr).toBe('3 unités');
    expect(p.batterie?.capacite?.fr).toBe('15,36 kWh au total');
    expect(p.batterie?.tension?.fr).toBe('51,2 V');
    expect(p.coffretDc?.organes[0].texte).toBe('F1 · Fusibles gPV · 25 A × 8');
    expect(p.coteReseau?.coffretAc?.organes.map((o) => o.texte)).toContain('QAC1 · Disjoncteur AC · 32 A / 400 V');
    expect(p.coteReseau?.blocs.map((b) => b.cle)).toEqual(['compteur_production', 'tgbt', 'reseau']);
    expect(p.legende).toMatchObject({ reseau: true, batterie: true, terre: true });
  });

  it('sans batterie : aucune carte batterie, pas de ligne de légende batterie', () => {
    const p = planSchema(doc('sans_batterie'));
    expect(p.batterie).toBeNull();
    expect(p.legende.batterie).toBe(false);
    expect(p.chaines).toHaveLength(2);
  });

  it('niveau standard : champs masqués OMIS (ni tension, ni calibre, ni section)', () => {
    const d = parseSchemaElectrique(exempleStandard())!.options.avec_batterie!;
    const p = planSchema(d);
    expect(p.batterie?.tension).toBeNull();
    expect(p.coffretDc?.organes[0].texte).toBe('F1 · Fusibles gPV × 8');
    expect(p.legende.sections).toBeNull();
  });

  it('hors réseau : aucun côté alternatif ; à calculer : blocs en creux sans organes', () => {
    const a = parseSchemaElectrique(exemple())!.options.avec_batterie!;
    a.coteReseau = { etat: 'hors_reseau', motif: null };
    expect(planSchema(a).coteReseau).toBeNull();
    const b = parseSchemaElectrique(exemple())!.options.avec_batterie!;
    b.coteReseau = { etat: 'a_calculer', motif: 'Pas de simulation.' };
    const pb = planSchema(b);
    expect(pb.coteReseau?.coffretAc).toBeNull();
    expect(pb.coteReseau?.motif).toBe('Pas de simulation.');
  });

  it('sans découpage servi : une ligne « Panneaux », aucune chaîne inventée', () => {
    const d = parseSchemaElectrique(exemple())!.options.avec_batterie!;
    d.chainesReparties = false;
    d.chaines = [];
    const p = planSchema(d);
    expect(p.chaines).toHaveLength(0);
    expect(p.sansDecoupage?.titre.fr).toBe('Panneaux · 48 panneaux');
  });

  it('trois langues pour chaque libellé propre', () => {
    const p = planSchema(doc('avec_batterie'));
    expect(p.chaines[0].titre.en).toBe('String 1 · 12 panels');
    expect(p.chaines[0].titre.ar).toContain('12');
  });
});

describe('choisirSld — repli sur l’ancien payload', () => {
  const svg = '<svg viewBox="0 0 10 10"></svg>';
  it('payload ancien (sans schema_electrique) : sld_svg inchangé', () => {
    expect(choisirSld({ sld_svg: svg })).toEqual({ mode: 'svg', svg });
  });
  it('schema_electrique inexploitable : retombe sur sld_svg', () => {
    expect(choisirSld({ sld_svg: svg, schema_electrique: { options: 'x' } })).toEqual({ mode: 'svg', svg });
  });
  it('schema_electrique valide : prime sur sld_svg, et suffit sans sld_svg', () => {
    expect(choisirSld({ sld_svg: svg, schema_electrique: exemple() }).mode).toBe('schema');
    expect(choisirSld({ schema_electrique: exemple() }).mode).toBe('schema');
  });
  it('rien du tout, ou entrée absurde : aucun', () => {
    expect(choisirSld({})).toEqual({ mode: 'aucun' });
    expect(choisirSld({ sld_svg: '  ' })).toEqual({ mode: 'aucun' });
    expect(choisirSld(null)).toEqual({ mode: 'aucun' });
  });
});
