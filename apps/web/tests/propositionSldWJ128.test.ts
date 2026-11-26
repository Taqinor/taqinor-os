// WJ128 — Schéma électrique (SLD) : présence conditionnelle (hasSldSvg — garde
// de rendu de la section [token].astro) + nom de fichier de téléchargement
// (sldSvgFilename). Fonctions PURES, aucun DOM : la page se contente de
// brancher `{showSld && (...)}` sur `hasSldSvg(data)` et de poser
// `data-sld-filename={sldSvgFilename(reference)}` sur le bouton de
// téléchargement (Blob + URL.createObjectURL côté client).
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { hasSldSvg, sldSvgFilename } from '../src/lib/proposition';
import { choisirSld, parseSchemaElectrique, planSchema } from '../src/lib/schemaElectrique';
import SchemaElectrique from '../src/components/proposition/SchemaElectrique.astro';
import BarreSoleil from '../src/components/proposition/BarreSoleil.astro';
import { parseRoofLayout } from '../src/lib/proposition';
import { lireVisionneuseSoleil } from '../src/lib/visionneuseSoleil';

vi.mock('cloudflare:workers', () => ({ env: {} }));

import Page from '../src/pages/proposition/[...token].astro';

const ici = (chemin: string) => fileURLToPath(new URL(chemin, import.meta.url));
const schemaContrat = JSON.parse(readFileSync(ici('../src/contract_samples/schema_electrique.json'), 'utf8')) as Record<string, any>;
const proposalContrat = JSON.parse(readFileSync(ici('../src/contract_samples/proposal_data.json'), 'utf8')) as Record<string, any>;
afterEach(() => vi.unstubAllGlobals());

describe('WJ128 — hasSldSvg (présence conditionnelle de la section « Schéma électrique »)', () => {
  it('SVG non vide → true (la section doit s’afficher)', () => {
    expect(hasSldSvg({ sld_svg: '<svg viewBox="0 0 10 10"></svg>' })).toBe(true);
  });

  it('null → false (aucune étude électrique : rien ne change sur la page)', () => {
    expect(hasSldSvg({ sld_svg: null })).toBe(false);
  });

  it('absent (undefined) → false', () => {
    expect(hasSldSvg({})).toBe(false);
  });

  it('chaîne vide ou uniquement des espaces → false', () => {
    expect(hasSldSvg({ sld_svg: '' })).toBe(false);
    expect(hasSldSvg({ sld_svg: '   ' })).toBe(false);
  });

  it('type inattendu (jamais un throw) → false', () => {
    // @ts-expect-error — payload backend douteux, la garde doit rester défensive.
    expect(hasSldSvg({ sld_svg: 42 })).toBe(false);
  });
});

describe('WJ128 — sldSvgFilename (nom de fichier du téléchargement SVG)', () => {
  it('référence simple → schema-electrique-<réf>.svg', () => {
    expect(sldSvgFilename('DEV-2026-0042')).toBe('schema-electrique-DEV-2026-0042.svg');
  });

  it('caractères non sûrs (slash, espace) → remplacés par un tiret, jamais rejetés', () => {
    expect(sldSvgFilename('DEV-2026-0042/A')).toBe('schema-electrique-DEV-2026-0042-A.svg');
    expect(sldSvgFilename('DEV 2026 0042')).toBe('schema-electrique-DEV-2026-0042.svg');
  });

  it('référence vide, null ou undefined → repli "devis" (jamais un nom de fichier vide)', () => {
    expect(sldSvgFilename('')).toBe('schema-electrique-devis.svg');
    expect(sldSvgFilename('   ')).toBe('schema-electrique-devis.svg');
    expect(sldSvgFilename(null)).toBe('schema-electrique-devis.svg');
    expect(sldSvgFilename(undefined)).toBe('schema-electrique-devis.svg');
  });

  it('référence composée UNIQUEMENT de caractères non sûrs → repli "devis" (pas de tirets nus)', () => {
    expect(sldSvgFilename('///')).toBe('schema-electrique-devis.svg');
  });

  it('toujours une extension .svg unique, jamais dupliquée', () => {
    expect(sldSvgFilename('REF.svg')).toMatch(/^schema-electrique-REF-svg\.svg$/);
  });
});

// LOT 6 (SCHEL-W2) — la section #sld ne régresse JAMAIS sur l'ancien payload : tant que le backend ne
// sert pas `schema_electrique` (site déployé avant l'ERP, devis ancien), le SVG historique s'affiche
// comme avant, et `hasSldSvg` garde ses règles. Le schéma neuf n'ajoute qu'une voie.
describe('WJ128 — repli sur sld_svg sans schema_electrique (LOT 6)', () => {
  const svg = '<svg viewBox="0 0 10 10"></svg>';
  it('ancien payload : choisirSld rend le même SVG que celui que hasSldSvg valide', () => {
    expect(hasSldSvg({ sld_svg: svg })).toBe(true);
    expect(choisirSld({ sld_svg: svg })).toEqual({ mode: 'svg', svg });
  });
  it('ancien payload sans schéma : section absente exactement quand hasSldSvg est faux', () => {
    for (const sld_svg of [null, undefined, '', '   ']) {
      expect(hasSldSvg({ sld_svg })).toBe(false);
      expect(choisirSld({ sld_svg }).mode).toBe('aucun');
    }
  });
  it('clé schema_electrique malformée : le SVG historique reste servi', () => {
    expect(choisirSld({ sld_svg: svg, schema_electrique: 'x' })).toEqual({ mode: 'svg', svg });
  });
});

// ── LOT 6 (SCHEL-W1) — lecture défensive du « schéma électrique » (exemples du contrat
// `src/contract_samples/schema_electrique.json`) et plan de dessin.
const exemple = () => structuredClone(schemaContrat.exemple.schema_electrique);
const exempleStandard = () => structuredClone(schemaContrat.exemple_standard.schema_electrique);

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
    expect(p.coffretDc?.organes[0].texte.fr).toBe('F1 · Fusibles gPV · 25 A × 8');
    expect(p.coteReseau?.coffretAc?.organes.map((o) => o.texte.fr)).toContain('QAC1 · Disjoncteur AC · 32 A / 400 V');
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
    expect(p.coffretDc?.organes[0].texte.fr).toBe('F1 · Fusibles gPV × 8');
    expect(p.legende.sections).toBeNull();
  });

  it('côté réseau non calculé (hors réseau OU à calculer) : AUCUN bloc, ni creux ni motif', () => {
    for (const etat of ['hors_reseau', 'a_calculer'] as const) {
      const a = parseSchemaElectrique(exemple())!.options.avec_batterie!;
      a.coteReseau = { etat, motif: 'Pas de simulation.' };
      const p = planSchema(a);
      expect(p.coteReseau).toBeNull();
      expect(p.legende.reseau).toBe(false);
    }
  });

  it('étage moyenne tension jamais dessiné ; calculé sans coffret AC : pas de coffret', () => {
    const a = parseSchemaElectrique(exemple())!.options.avec_batterie!;
    a.etageMt = [{ clef: 'poste', titre: 'Poste MT', detail: null }];
    a.coffretAc = null;
    const p = planSchema(a);
    expect(p.coteReseau?.coffretAc).toBeNull();
    expect(p.coteReseau?.blocs.map((b) => b.cle)).toEqual(['compteur_production', 'tgbt', 'reseau']);
  });

  it('organes dans les trois langues et accords arabes (duel, plus de 10)', () => {
    const p = planSchema(doc('avec_batterie'));
    expect(p.coffretDc?.organes[0].texte.en).toBe('F1 · gPV fuses · 25 A × 8');
    expect(p.coffretDc?.organes[0].texte.ar).toBe('F1 · منصهرات gPV · 25 A × 8');
    const d = doc('avec_batterie');
    d.chaines[0].nbPanneaux = 2;
    d.chaines[1].nbPanneaux = 11;
    d.batterie!.unites = 2;
    d.onduleurs[0].nbEntrees = 2;
    const q = planSchema(d);
    expect(q.chaines[0].titre.ar).toBe('السلسلة 1 · لوحان');
    expect(q.chaines[1].titre.ar).toBe('السلسلة 2 · 11 لوحًا');
    expect(q.batterie?.unites?.ar).toBe('وحدتان');
    expect(q.onduleurs[0].entrees?.ar).toBe('مدخلان');
  });

  it('sans découpage servi : « 48 panneaux » sans répéter le mot, aucune chaîne inventée', () => {
    const d = parseSchemaElectrique(exemple())!.options.avec_batterie!;
    d.chainesReparties = false;
    d.chaines = [];
    const p = planSchema(d);
    expect(p.chaines).toHaveLength(0);
    expect(p.sansDecoupage?.titre.fr).toBe('48 panneaux');
  });

  it('trois langues pour chaque libellé propre', () => {
    const p = planSchema(doc('avec_batterie'));
    expect(p.chaines[0].titre.en).toBe('String 1 · 12 panels');
    expect(p.chaines[0].titre.ar).toContain('12');
  });
});

describe('choisirSld — priorité (LOT 6)', () => {
  const svg = '<svg viewBox="0 0 10 10"></svg>';
  it('schema_electrique valide : prime sur sld_svg, et suffit sans sld_svg', () => {
    expect(choisirSld({ sld_svg: svg, schema_electrique: exemple() }).mode).toBe('schema');
    expect(choisirSld({ schema_electrique: exemple() }).mode).toBe('schema');
  });
  it('entrée absurde : aucun', () => {
    expect(choisirSld(null)).toEqual({ mode: 'aucun' });
  });
});

// ── Rendu du composant et de la page ────────────────────────────────────────
async function rendreSchema(schema: unknown, selected: string | null = 'avec_batterie'): Promise<string> {
  const container = await AstroContainer.create({ astroConfig: { site: 'https://taqinor.ma' } } as never);
  return container.renderToString(SchemaElectrique, { props: { schema: parseSchemaElectrique(schema)!, selected } });
}
const texteVisible = (html: string) =>
  html.replace(/<style\b[\s\S]*?<\/style>/gi, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
const panneau = (html: string, cle: string) =>
  html.split('<div class="sch-panel').find((p) => p.includes(`data-sld-option="${cle}"`)) ?? '';

describe('SchemaElectrique.astro — rendu (LOT 6)', () => {
  it('avec batterie : quatre chaînes et leurs comptes, batterie, organes des deux coffrets', async () => {
    const p = panneau(await rendreSchema(exemple()), 'avec_batterie');
    for (const n of [1, 2, 3, 4]) expect(p).toContain(`Chaîne ${n} · 12 panneaux`);
    expect(p.match(/class="sch-tile[" ]/g)).toHaveLength(48);
    expect(p).toContain('12 × 715 Wc');
    expect(p).toContain('Chaîne 3 → entrée 2');
    expect(p).toContain('Dyness BX51100');
    expect(p).toContain('3 unités');
    expect(p).toContain('15,36 kWh au total');
    expect(p).toContain('51,2 V');
    expect(p).toContain('F1 · Fusibles gPV · 25 A × 8');
    expect(p).toContain('QAC1 · Disjoncteur AC · 32 A / 400 V');
    expect(p).toContain('Coffret côté panneaux');
    expect(p).toContain('Coffret côté réseau');
  });

  it('aucun prix, aucun motif, aucune pastille « à … », aucun texte vendeur', async () => {
    const e = exemple();
    e.options.avec_batterie.cote_reseau.motif = 'MOTIF-VENDEUR-SECRET';
    e.options.avec_batterie.etage_mt = [{ clef: 'poste', titre: 'Poste MT', detail: 'x' }];
    const html = await rendreSchema(e);
    const txt = texteVisible(html);
    expect(txt).not.toMatch(/MAD|\bDH\b|\bTTC\b|\bHT\b|€|prix/i);
    expect(html).not.toContain('MOTIF-VENDEUR-SECRET');
    expect(txt).not.toMatch(/à confirmer|à dimensionner|visite technique|non disponible/i);
    expect(html).not.toContain('Poste MT');
  });

  it('sans batterie : aucune carte batterie', async () => {
    const p = panneau(await rendreSchema(exemple(), 'sans_batterie'), 'sans_batterie');
    expect(p).toContain('Chaîne 2 · 17 panneaux');
    expect(p).not.toContain('Batterie');
    expect(p).not.toContain('charge / décharge');
  });

  it('côté réseau non calculé : cette partie est absente (ni bande, ni coffret, ni compteur)', async () => {
    const e = exemple();
    e.options.avec_batterie.cote_reseau = { etat: 'a_calculer', motif: 'Pas de simulation.' };
    const html = await rendreSchema(e);
    const p = panneau(html, 'avec_batterie');
    expect(p).toContain('Côté panneaux');
    expect(p).not.toContain('Côté réseau · courant alternatif');
    expect(p).not.toContain('Coffret côté réseau');
    expect(p).not.toContain('TGBT');
    expect(html).not.toContain('Pas de simulation.');
  });

  it('calculé mais sans coffret AC : pas de boîte vide ni de pastille', async () => {
    const e = exemple();
    e.options.avec_batterie.coffret_ac = null;
    const p = panneau(await rendreSchema(e), 'avec_batterie');
    expect(p).not.toContain('Coffret côté réseau');
    expect(p).toContain('TGBT');
    expect(texteVisible(p)).not.toMatch(/à dimensionner|à confirmer/);
  });

  it('trois langues : organes EN/AR portés par data-en / data-ar', async () => {
    const p = panneau(await rendreSchema(exemple()), 'avec_batterie');
    expect(p).toContain('data-en="F1 · gPV fuses · 25 A × 8"');
    expect(p).toContain('data-ar="F1 · منصهرات gPV · 25 A × 8"');
  });

  it('option cochée sans document : jamais le schéma de l’autre option, aucune note', async () => {
    const e = exemple();
    e.options.sans_batterie = null;
    const html = await rendreSchema(e, 'sans_batterie');
    expect(html).not.toContain('data-sld-option="sans_batterie"');
    expect(panneau(html, 'avec_batterie')).toMatch(/hidden/);
    expect(texteVisible(html)).not.toContain('Schéma non disponible');
  });
});

async function rendrePage(data: unknown): Promise<string> {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(data), { status: 200, headers: { 'content-type': 'application/json' } })),
  );
  const container = await AstroContainer.create({ astroConfig: { site: 'https://taqinor.ma' } } as never);
  const jeton = 'Zx8kq2Lm9Pq4Rt6Vw1Yb3Nc5Df7Gh0Jk';
  return container.renderToString(Page, {
    params: { token: jeton },
    request: new Request(`https://taqinor.ma/proposition/${jeton}`),
  });
}

describe('page /proposition — section #sld, deux payloads (LOT 6)', () => {
  it('ancien payload (sld_svg, sans schema_electrique) : section historique inchangée', async () => {
    // L'exemple du contrat porte `schema_electrique` depuis SCHEL-B3 : l'ancien payload la RETIRE de sa copie.
    const { schema_electrique: _neuf, ...ancien } = proposalContrat.exemple;
    const html = await rendrePage(ancien);
    expect(html).toContain('id="sld-teaser"');
    expect(html).toContain('id="sld-viewer"');
    expect(html).toContain('id="sld-download"');
    expect(html).not.toContain('data-sld-schema');
  });

  it('nouveau payload : schéma neuf, plus de teaser / plein écran / téléchargement / visionneuse', async () => {
    const html = await rendrePage({ ...proposalContrat.exemple, schema_electrique: exemple() });
    expect(html).toContain('data-sld-schema');
    expect(html).toContain('Chaîne 1 · 12 panneaux');
    for (const id of ['sld-teaser', 'sld-viewer', 'sld-download', 'sld-expand']) {
      expect(html).not.toContain(`id="${id}"`);
    }
  });

  it('nouveau payload sans sld_svg : la section existe quand même', async () => {
    const { sld_svg: _s, ...sans } = proposalContrat.exemple;
    const html = await rendrePage({ ...sans, schema_electrique: exemple() });
    expect(html).toContain('id="sld"');
    expect(html).toContain('data-sld-schema');
  });
});

// ── LOT 6 (D-ACAL-132 à 138) — section #roof3d : la visionneuse au soleil des liens de confiance ────────
const soleilContrat = JSON.parse(readFileSync(ici('../src/contract_samples/visionneuse_soleil.json'), 'utf8')) as Record<string, any>;
const C = Math.cos((33.574 * Math.PI) / 180);
const sommet = (x: number, y: number) => [-7.62 + x / (111_320 * C), 33.574 + y / 111_320];
// Le pan `zone-1` du contrat, six modules posés (calepinage réel : la visionneuse pleine peut démarrer).
const roofLayoutSoleil = {
  version: 2,
  zones: [{
    id: 'zone-1', label: 'Pan principal', vertices: [sommet(-8, -8), sommet(8, -8), sommet(8, 8), sommet(-8, 8)], obstacles: [],
    roofType: 'flat', pitchDeg: 0, facingAzimuthDeg: 180, neededPanels: 6,
    geometry: { azimuthDeg: 180, tiltDeg: 13, family: 'south', flush: false, count: 6, origin: [-7.62, 33.574], panels: [-3, -2, -1, 1, 2, 3].map((cx) => ({ cx: cx * 1.4, cy: 0 })) },
  }],
};
const soleil = (cle: 'exemple' | 'exemple_sans_mesure' = 'exemple') => structuredClone(soleilContrat[cle].visionneuse_soleil);
const lu = (cle?: 'exemple' | 'exemple_sans_mesure') => lireVisionneuseSoleil({ visionneuse_soleil: soleil(cle) }, parseRoofLayout(roofLayoutSoleil))!;
const section3d = (html: string) => html.slice(html.indexOf('id="roof3d"'), html.indexOf('</section>', html.indexOf('id="roof3d"')));

async function rendreBarre(s: ReturnType<typeof lu>): Promise<string> {
  const container = await AstroContainer.create({ astroConfig: { site: 'https://taqinor.ma' } } as never);
  return container.renderToString(BarreSoleil, { props: { soleil: s } });
}

describe('BarreSoleil.astro — rendu (LOT 6)', () => {
  it('avec valeurs enregistrées : légende Ombragé → Plein soleil, lecture, curseur, Hiver / Été, instant choisi', async () => {
    const html = await rendreBarre(lu());
    expect(html).toContain('Ensoleillement de chaque panneau sur l’année');
    expect(html).toContain('Ombragé');
    expect(html).toContain('Plein soleil');
    expect(html).toContain('20 décembre · 16 h (heure solaire)');
    expect(html).toMatch(/data-soleil-saison="hiver"[^>]*aria-pressed="true"/);
    expect(html).toContain('data-soleil-lecture');
    expect(html).toContain('type="range"');
  });

  it('contrôles inertes jusqu’au branchement, trois langues, libellés accessibles traduits', async () => {
    const html = await rendreBarre(lu());
    for (const hook of ['data-soleil-lecture', 'data-soleil-heure', 'data-soleil-saison="hiver"', 'data-soleil-saison="ete"']) {
      expect(html).toMatch(new RegExp(`${hook}[^>]*disabled`));
    }
    expect(html).toContain('data-aria-label-ar="تشغيل مسار الشمس خلال اليوم"');
    expect(html).toContain('data-aria-label-en="Solar time of day"');
    expect(html).toContain('data-ar="الصيف"');
  });

  it('aucune valeur enregistrée : aucune légende (D-ACAL-136), le soleil reste pilotable', async () => {
    const html = await rendreBarre(lu('exemple_sans_mesure'));
    expect(html).not.toContain('data-soleil-legende');
    expect(html).not.toContain('Ombragé');
    expect(html).toContain('20 juin · 12 h (heure solaire)');
  });

  it('rien d’inventé ni d’incertain : aucun pourcentage, aucun prix, aucun « à confirmer » / « estimation »', async () => {
    const txt = texteVisible(await rendreBarre(lu()));
    expect(txt).not.toMatch(/\d\s*%|MAD|\bDH\b|TTC|prix|à confirmer|estimation|estimé/i);
  });
});

describe('page /proposition — section #roof3d, avec et sans visionneuse_soleil (LOT 6)', () => {
  // L'exemple du contrat porte la clé depuis le lot 6 (lane B) : le repli la RETIRE, comme un lien standard.
  const { visionneuse_soleil: _servie, ...sansCle } = proposalContrat.exemple;
  const base = { ...sansCle, roof_layout: roofLayoutSoleil };

  it('REPLI : sans la clé (lien standard, backend antérieur), section d’aujourd’hui — aucune barre, aucun attribut neuf', async () => {
    const html = await rendrePage(base);
    const s = section3d(html);
    expect(s).toContain('id="roof3d-stage"');
    expect(s).toContain('data-viewer-config=');
    expect(s).not.toContain('roof3d-soleil');
    expect(s).not.toContain('data-visionneuse-soleil');
    expect(s).not.toContain('Ensoleillement');
  });

  it('REPLI : une clé malformée rend EXACTEMENT la même section que la clé absente', async () => {
    const sans = section3d(await rendrePage(base));
    for (const casse of [null, 'x', { version: 2 }, { ...soleil(), zones: 'x' }]) {
      expect(section3d(await rendrePage({ ...base, visionneuse_soleil: casse }))).toBe(sans);
    }
  });

  it('clé servie : barre sous la scène, attribut portant l’ouverture et les objets voisins (jamais un libellé), configuration 3D inchangée', async () => {
    const sans = section3d(await rendrePage(base));
    const s = section3d(await rendrePage({ ...base, visionneuse_soleil: soleil() }));
    expect(s).toContain('id="roof3d-soleil"');
    expect(s.indexOf('id="roof3d-stage"')).toBeLessThan(s.indexOf('id="roof3d-soleil"'));
    const attr = /data-visionneuse-soleil="([^"]*)"/.exec(s)![1];
    expect(attr).toContain('&quot;ouverture&quot;:{&quot;jour&quot;:355,&quot;heure&quot;:16}');
    expect(attr).toContain('&quot;kind&quot;:&quot;arbre&quot;');
    expect(attr).not.toContain('label');
    const config = (x: string) => /data-viewer-config="([^"]*)"/.exec(x)![1];
    expect(config(s)).toBe(config(sans));
  });
});
