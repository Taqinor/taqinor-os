/**
 * LOT 6 (SCHEL-W1) — le « schéma électrique » du devis sur la page client /proposition.
 *
 * Module PUR (aucun DOM, aucun import de `proposition.ts`) :
 *  - `parseSchemaElectrique(p)` lit la clé ADDITIVE `schema_electrique = {options: {sans_batterie,
 *    avec_batterie}}` de la charge publique, dans la forme figée par le contrat
 *    `src/contract_samples/schema_electrique.json`. Toute forme inattendue → `null` (jamais un throw,
 *    jamais une valeur devinée) ; une grandeur `null` reste `null` et le dessin l'OMET.
 *  - `choisirSld(data)` décide ce que la section #sld affiche : le schéma neuf, l'ancien `sld_svg`
 *    (backend pas encore déployé / ancien devis : comportement INCHANGÉ), ou rien.
 *  - `planSchema(doc)` compose le modèle de dessin (libellés FR/EN/AR déjà formés) lu par
 *    `components/proposition/SchemaElectrique.astro`.
 *
 * Aucun montant, aucun prix : le contrat n'en porte pas et ce module n'en lit jamais.
 */

export type OptionSchema = 'sans_batterie' | 'avec_batterie';
export const OPTIONS_SCHEMA: readonly OptionSchema[] = ['sans_batterie', 'avec_batterie'];

export interface Tri {
  fr: string;
  en: string;
  ar: string;
}

export interface SchemaOrgane {
  clef: string;
  repere: string | null;
  titre: string;
  calibre: string | null;
  quantite: number | null;
}
export interface SchemaChaine {
  numero: number;
  couleurIndex: number | null;
  couleur: string | null;
  nbPanneaux: number;
  onduleur: number | null;
  entree: number | null;
}
export interface SchemaOnduleur {
  designation: string | null;
  puissanceKw: number | null;
  nombre: number | null;
  nbEntrees: number | null;
}
export interface SchemaBatterie {
  designation: string | null;
  unites: number | null;
  capaciteKwh: number | null;
  tensionV: number | null;
}
export interface SchemaBloc {
  titre: string;
  detail: string | null;
}
export interface SchemaBlocMt {
  clef: string;
  titre: string;
  detail: string | null;
}
export type EtatCoteReseau = 'calcule' | 'a_calculer' | 'hors_reseau';
export interface SchemaDoc {
  option: OptionSchema;
  source: 'calepinage' | 'conception_devis' | 'lignes_devis';
  calibresMasques: boolean;
  panneaux: { nombre: number | null; designation: string | null; puissanceWc: number | null };
  chainesReparties: boolean;
  chaines: SchemaChaine[];
  coffretDc: SchemaOrgane[] | null;
  onduleurs: SchemaOnduleur[];
  batterie: SchemaBatterie | null;
  coffretAc: SchemaOrgane[] | null;
  compteurProduction: SchemaBloc | null;
  tgbt: SchemaBloc | null;
  etageMt: SchemaBlocMt[];
  reseau: SchemaBloc | null;
  coteReseau: { etat: EtatCoteReseau; motif: string | null };
  liaisons: {
    dc: { sectionMm2: number | null; longueurM: number | null } | null;
    ac: { sectionMm2: number | null; longueurM: number | null } | null;
  };
  terre: boolean;
}
export interface SchemaElectrique {
  options: Record<OptionSchema, SchemaDoc | null>;
}

// ── Lecture défensive ────────────────────────────────────────────────────────

class Rejet extends Error {}

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v);

function refuser(): never {
  throw new Rejet();
}
function nombreOuNull(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  return refuser();
}
function entierOuNull(v: unknown): number | null {
  const n = nombreOuNull(v);
  if (n !== null && !Number.isInteger(n)) refuser();
  return n;
}
function entierPositif(v: unknown): number {
  const n = entierOuNull(v);
  if (n === null || n < 0) refuser();
  return n;
}
function texteOuNull(v: unknown): string | null {
  if (v === null || v === undefined) return null;
  if (typeof v === 'string') return v.trim() === '' ? null : v;
  return refuser();
}
function texte(v: unknown): string {
  const t = texteOuNull(v);
  if (t === null) refuser();
  return t;
}
function liste(v: unknown): unknown[] {
  if (Array.isArray(v)) return v;
  return refuser();
}
function objet(v: unknown): Obj {
  if (isObj(v)) return v;
  return refuser();
}
function objetOuNull(v: unknown): Obj | null {
  if (v === null || v === undefined) return null;
  return objet(v);
}
function boolOuDefaut(v: unknown, defaut: boolean): boolean {
  if (v === null || v === undefined) return defaut;
  if (typeof v === 'boolean') return v;
  return refuser();
}

// Couleur de chaîne servie (`rgb(r, g, b)` ou `#rgb[a]`) : toute autre forme est ignorée
// (la chaîne garde un trait neutre) — jamais injectée telle quelle dans un style.
const RE_RGB = /^rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)$/;
const RE_HEX = /^#[0-9a-fA-F]{3,8}$/;
export function couleurSure(v: unknown): string | null {
  if (typeof v !== 'string') return null;
  const c = v.trim();
  return RE_RGB.test(c) || RE_HEX.test(c) ? c : null;
}

function organes(v: unknown): SchemaOrgane[] | null {
  const o = objetOuNull(v);
  if (o === null) return null;
  const out = liste(o.organes).map((raw) => {
    const x = objet(raw);
    return {
      clef: texte(x.clef),
      repere: texteOuNull(x.repere),
      titre: texte(x.titre),
      calibre: texteOuNull(x.calibre),
      quantite: entierOuNull(x.quantite),
    };
  });
  return out.length ? out : null;
}
function bloc(v: unknown): SchemaBloc | null {
  const o = objetOuNull(v);
  if (o === null) return null;
  return { titre: texte(o.titre), detail: texteOuNull(o.detail) };
}
function liaison(v: unknown): { sectionMm2: number | null; longueurM: number | null } | null {
  const o = objetOuNull(v);
  if (o === null) return null;
  return { sectionMm2: nombreOuNull(o.section_mm2), longueurM: nombreOuNull(o.longueur_m) };
}

function lireDoc(raw: unknown, cle: OptionSchema): SchemaDoc {
  const d = objet(raw);
  if (d.version !== 1) refuser();
  // Le document d'une option porte SON option : jamais celui de l'autre sous son nom.
  if (d.option !== cle) refuser();
  const source = d.source;
  if (source !== 'calepinage' && source !== 'conception_devis' && source !== 'lignes_devis') refuser();

  const pan = objet(d.panneaux);
  const mod = objetOuNull(pan.module);
  const cote = objet(d.cote_reseau);
  const etat = cote.etat;
  if (etat !== 'calcule' && etat !== 'a_calculer' && etat !== 'hors_reseau') refuser();

  const chaines = liste(d.chaines).map((c) => {
    const x = objet(c);
    return {
      numero: entierPositif(x.numero),
      couleurIndex: entierOuNull(x.couleur_index),
      couleur: couleurSure(x.couleur),
      nbPanneaux: entierPositif(x.nb_panneaux),
      onduleur: entierOuNull(x.onduleur),
      entree: entierOuNull(x.entree),
    };
  });
  const onduleurs = liste(d.onduleurs).map((o) => {
    const x = objet(o);
    return {
      designation: texteOuNull(x.designation),
      puissanceKw: nombreOuNull(x.puissance_kw),
      nombre: entierOuNull(x.nombre),
      nbEntrees: entierOuNull(x.nb_entrees),
    };
  });
  const bat = objetOuNull(d.batterie);
  const liaisons = d.liaisons === undefined || d.liaisons === null ? {} : objet(d.liaisons);

  return {
    option: cle,
    source,
    calibresMasques: boolOuDefaut(d.calibres_masques, false),
    panneaux: {
      nombre: entierOuNull(pan.nombre),
      designation: mod ? texteOuNull(mod.designation) : null,
      puissanceWc: mod ? nombreOuNull(mod.puissance_wc) : null,
    },
    chainesReparties: boolOuDefaut(d.chaines_reparties, chaines.length > 0),
    chaines: chaines.sort((a, b) => a.numero - b.numero),
    coffretDc: organes(d.coffret_dc),
    onduleurs,
    batterie: bat
      ? {
          designation: texteOuNull(bat.designation),
          unites: entierOuNull(bat.unites),
          capaciteKwh: nombreOuNull(bat.capacite_kwh),
          tensionV: nombreOuNull(bat.tension_v),
        }
      : null,
    coffretAc: organes(d.coffret_ac),
    compteurProduction: bloc(d.compteur_production),
    tgbt: bloc(d.tgbt),
    etageMt: (d.etage_mt === undefined || d.etage_mt === null ? [] : liste(d.etage_mt)).map((m) => {
      const x = objet(m);
      return { clef: texte(x.clef), titre: texte(x.titre), detail: texteOuNull(x.detail) };
    }),
    reseau: bloc(d.reseau),
    coteReseau: { etat, motif: texteOuNull(cote.motif) },
    liaisons: { dc: liaison(liaisons.dc), ac: liaison(liaisons.ac) },
    terre: boolOuDefaut(d.terre, false),
  };
}

/**
 * Lit `schema_electrique` de la charge publique. `null` si la clé est absente, de forme
 * inattendue, ou si aucune option n'a de document dessinable. Une option au document
 * malformé devient `null` (aucun schéma pour elle) sans invalider l'autre.
 */
export function parseSchemaElectrique(p: unknown): SchemaElectrique | null {
  try {
    if (!isObj(p)) return null;
    const opts = p.options;
    if (!isObj(opts)) return null;
    const options = { sans_batterie: null, avec_batterie: null } as Record<OptionSchema, SchemaDoc | null>;
    for (const cle of OPTIONS_SCHEMA) {
      const raw = opts[cle];
      if (raw === null || raw === undefined) continue;
      try {
        options[cle] = lireDoc(raw, cle);
      } catch {
        options[cle] = null;
      }
    }
    return options.sans_batterie || options.avec_batterie ? { options } : null;
  } catch {
    return null;
  }
}

export type ChoixSld =
  | { mode: 'schema'; schema: SchemaElectrique }
  | { mode: 'svg'; svg: string }
  | { mode: 'aucun' };

/**
 * Ce que la section #sld affiche. Le schéma neuf prime ; sans `schema_electrique` exploitable
 * (backend non déployé, ancien devis, case décochée) on retombe sur `sld_svg` EXACTEMENT comme
 * avant (mêmes règles que `hasSldSvg` : chaîne non vide), sinon rien.
 */
export function choisirSld(data: unknown): ChoixSld {
  if (!isObj(data)) return { mode: 'aucun' };
  const schema = parseSchemaElectrique(data.schema_electrique);
  if (schema) return { mode: 'schema', schema };
  const svg = data.sld_svg;
  if (typeof svg === 'string' && svg.trim().length > 0) return { mode: 'svg', svg };
  return { mode: 'aucun' };
}

// ── Plan de dessin (libellés trilingues) ─────────────────────────────────────

const nf = (n: number, lg: keyof Tri): string => {
  const s = String(Math.round(n * 100) / 100);
  return lg === 'fr' ? s.replace('.', ',') : s;
};
const tri = (f: (lg: keyof Tri) => string): Tri => ({ fr: f('fr'), en: f('en'), ar: f('ar') });

export interface LigneOrgane {
  texte: string; // « F1 · Fusibles gPV · 25 A × 8 », champs null omis
  titreTri: Tri;
}
export interface PlanChaine {
  numero: number;
  couleur: string | null;
  titre: Tri;
  tuiles: number;
  puissance: string | null; // « 12 × 715 Wc »
  entree: Tri | null; // « entrée 1 »
  flux: Tri | null; // « Chaîne 1 → entrée 1 »
}
export interface PlanSchema {
  option: OptionSchema;
  chainesReparties: boolean;
  chaines: PlanChaine[];
  sansDecoupage: { titre: Tri; puissance: string | null } | null;
  coffretDc: { organes: LigneOrgane[] } | null;
  onduleurs: Array<{ designation: string | null; puissanceKw: Tri | null; entrees: Tri | null }>;
  batterie: { designation: string | null; unites: Tri | null; capacite: Tri | null; tension: Tri | null } | null;
  coteReseau: {
    etat: EtatCoteReseau;
    motif: string | null;
    coffretAc: { organes: LigneOrgane[] } | null;
    blocs: Array<{ cle: string; titre: Tri; detail: Tri | null; aConfirmer: boolean }>;
  } | null;
  legende: { reseau: boolean; batterie: boolean; terre: boolean; sections: Tri | null };
}

const TITRES_ORGANES: Record<string, Tri> = {
  fusibles: { fr: 'Fusibles gPV', en: 'gPV fuses', ar: 'فيوزات gPV' },
  parafoudre_dc: { fr: 'Parafoudre DC Type 2', en: 'DC surge arrester Type 2', ar: 'مانع صواعق DC من النوع 2' },
  sectionneur_dc: { fr: 'Sectionneur DC', en: 'DC isolator', ar: 'فاصل DC' },
  disjoncteur_ac: { fr: 'Disjoncteur AC', en: 'AC breaker', ar: 'قاطع AC' },
  parafoudre_ac: { fr: 'Parafoudre AC Type 2', en: 'AC surge arrester Type 2', ar: 'مانع صواعق AC من النوع 2' },
  ddr: { fr: 'Différentiel (DDR)', en: 'Residual-current device', ar: 'قاطع تفاضلي' },
};
const TITRES_BLOCS: Record<string, Tri> = {
  'Compteur de production': { fr: 'Compteur de production', en: 'Production meter', ar: 'عداد الإنتاج' },
  TGBT: { fr: 'TGBT', en: 'Main LV switchboard (TGBT)', ar: 'اللوحة العامة (TGBT)' },
  'Compteur ONEE': { fr: 'Compteur ONEE', en: 'ONEE meter', ar: 'عداد ONEE' },
};
const DETAILS_BLOCS: Record<string, Tri> = {
  'énergie produite': { fr: 'énergie produite', en: 'energy produced', ar: 'الطاقة المنتَجة' },
  'injection / soutirage': { fr: 'injection / soutirage', en: 'export / import', ar: 'حقن / سحب' },
};
const soloTri = (s: string): Tri => ({ fr: s, en: s, ar: s });

function ligneOrgane(o: SchemaOrgane): LigneOrgane {
  const base = TITRES_ORGANES[o.clef];
  // Le français est celui servi (libellé éventuellement édité) ; EN/AR par clef connue, sinon tel quel.
  const titreTri: Tri = base ? { fr: o.titre, en: base.en, ar: base.ar } : soloTri(o.titre);
  const parts = [o.repere, o.titre, o.calibre].filter((x): x is string => !!x);
  const q = o.quantite !== null && o.quantite > 1 ? ` × ${o.quantite}` : '';
  return { texte: parts.join(' · ') + q, titreTri };
}

function plurielPanneaux(n: number, lg: keyof Tri): string {
  if (lg === 'fr') return `${n} panneau${n > 1 ? 'x' : ''}`;
  if (lg === 'en') return `${n} panel${n > 1 ? 's' : ''}`;
  return n === 1 ? 'لوح واحد' : n >= 3 && n <= 10 ? `${n} ألواح` : `${n} لوحًا`;
}

export function planSchema(doc: SchemaDoc): PlanSchema {
  const wc = doc.panneaux.puissanceWc;
  const puissanceDe = (n: number): string | null => (wc !== null ? `${n} × ${nf(wc, 'en')} Wc` : null);

  const chaines: PlanChaine[] = doc.chaines.map((c) => ({
    numero: c.numero,
    couleur: c.couleur,
    titre: tri((lg) =>
      lg === 'fr'
        ? `Chaîne ${c.numero} · ${plurielPanneaux(c.nbPanneaux, lg)}`
        : lg === 'en'
          ? `String ${c.numero} · ${plurielPanneaux(c.nbPanneaux, lg)}`
          : `السلسلة ${c.numero} · ${plurielPanneaux(c.nbPanneaux, lg)}`,
    ),
    tuiles: c.nbPanneaux,
    puissance: puissanceDe(c.nbPanneaux),
    entree:
      c.entree !== null
        ? { fr: `entrée ${c.entree}`, en: `input ${c.entree}`, ar: `المدخل ${c.entree}` }
        : null,
    flux:
      c.entree !== null
        ? {
            fr: `Chaîne ${c.numero} → entrée ${c.entree}`,
            en: `String ${c.numero} → input ${c.entree}`,
            ar: `السلسلة ${c.numero} ← المدخل ${c.entree}`,
          }
        : null,
  }));

  const sansDecoupage =
    !doc.chainesReparties && chaines.length === 0 && doc.panneaux.nombre !== null && doc.panneaux.nombre > 0
      ? {
          titre: tri((lg) =>
            lg === 'fr'
              ? `Panneaux · ${plurielPanneaux(doc.panneaux.nombre as number, lg)}`
              : lg === 'en'
                ? `Panels · ${plurielPanneaux(doc.panneaux.nombre as number, lg)}`
                : `الألواح · ${plurielPanneaux(doc.panneaux.nombre as number, lg)}`,
          ),
          puissance: puissanceDe(doc.panneaux.nombre),
        }
      : null;

  const onduleurs = doc.onduleurs.map((o) => ({
    designation: o.designation !== null ? (o.nombre !== null && o.nombre > 1 ? `${o.nombre} × ` : '') + o.designation : null,
    puissanceKw: o.puissanceKw !== null ? tri((lg) => `${nf(o.puissanceKw as number, lg)} kW`) : null,
    entrees:
      o.nbEntrees !== null
        ? {
            fr: `${o.nbEntrees} entrée${o.nbEntrees > 1 ? 's' : ''}`,
            en: `${o.nbEntrees} input${o.nbEntrees > 1 ? 's' : ''}`,
            ar: `${o.nbEntrees} ${o.nbEntrees > 1 ? 'مداخل' : 'مدخل'}`,
          }
        : null,
  }));

  const b = doc.batterie;
  const batterie = b
    ? {
        designation: b.designation,
        unites:
          b.unites !== null
            ? {
                fr: `${b.unites} unité${b.unites > 1 ? 's' : ''}`,
                en: `${b.unites} unit${b.unites > 1 ? 's' : ''}`,
                ar: `${b.unites} ${b.unites > 1 ? 'وحدات' : 'وحدة'}`,
              }
            : null,
        capacite:
          b.capaciteKwh !== null
            ? tri((lg) =>
                lg === 'fr'
                  ? `${nf(b.capaciteKwh as number, lg)} kWh au total`
                  : lg === 'en'
                    ? `${nf(b.capaciteKwh as number, lg)} kWh in total`
                    : `${nf(b.capaciteKwh as number, lg)} kWh في المجموع`,
              )
            : null,
        tension: b.tensionV !== null ? tri((lg) => `${nf(b.tensionV as number, lg)} V`) : null,
      }
    : null;

  const aCalculer = doc.coteReseau.etat === 'a_calculer';
  const blocsReseau: NonNullable<PlanSchema['coteReseau']>['blocs'] = [];
  const pousser = (cle: string, b2: SchemaBloc | null): void => {
    if (!b2) return;
    const t = TITRES_BLOCS[b2.titre] ?? soloTri(b2.titre);
    const d = b2.detail !== null ? (DETAILS_BLOCS[b2.detail] ?? soloTri(b2.detail)) : null;
    blocsReseau.push({ cle, titre: t, detail: d, aConfirmer: false });
  };
  pousser('compteur_production', doc.compteurProduction);
  pousser('tgbt', doc.tgbt);
  for (const m of doc.etageMt) {
    blocsReseau.push({ cle: `mt_${m.clef}`, titre: soloTri(m.titre), detail: m.detail !== null ? soloTri(m.detail) : null, aConfirmer: true });
  }
  pousser('reseau', doc.reseau);

  const coteReseau =
    doc.coteReseau.etat === 'hors_reseau'
      ? null
      : {
          etat: doc.coteReseau.etat,
          motif: doc.coteReseau.motif,
          coffretAc: !aCalculer && doc.coffretAc ? { organes: doc.coffretAc.map(ligneOrgane) } : null,
          blocs: blocsReseau,
        };

  const sec = (l: { sectionMm2: number | null; longueurM: number | null } | null, lg: keyof Tri): string | null => {
    if (!l || l.sectionMm2 === null) return null;
    return `${nf(l.sectionMm2, lg)} mm²` + (l.longueurM !== null ? ` · ${nf(l.longueurM, lg)} m` : '');
  };
  const dcS = sec(doc.liaisons.dc, 'fr');
  const acS = sec(doc.liaisons.ac, 'fr');
  const sections =
    dcS || acS
      ? tri((lg) => {
          const d = sec(doc.liaisons.dc, lg);
          const a = sec(doc.liaisons.ac, lg);
          const pre = lg === 'fr' ? 'Section du câble' : lg === 'en' ? 'Cable cross-section' : 'مقطع الكابل';
          const dc = lg === 'fr' ? 'continu' : lg === 'en' ? 'DC' : 'مستمر';
          const ac = lg === 'fr' ? 'alternatif' : lg === 'en' ? 'AC' : 'متناوب';
          return `${pre} : ${[d ? `${dc} ${d}` : null, a ? `${ac} ${a}` : null].filter(Boolean).join(' ; ')}`;
        })
      : null;

  return {
    option: doc.option,
    chainesReparties: doc.chainesReparties,
    chaines,
    sansDecoupage,
    coffretDc: doc.coffretDc ? { organes: doc.coffretDc.map(ligneOrgane) } : null,
    onduleurs,
    batterie,
    coteReseau,
    legende: { reseau: coteReseau !== null, batterie: batterie !== null, terre: doc.terre, sections },
  };
}
