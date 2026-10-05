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
  // pompage : retiré par AGW408 (la page dessine toutes ses colonnes).
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

// AGW408 — choix fermés du bloc pompage IDENTIQUES au contrat lead_pompage.json.
describe('questionnaire — pompage : choix fermés = contrat', () => {
  const lp = JSON.parse(
    read('../../../backend/django_core/apps/crm/contract_samples/lead_pompage.json'),
  ) as { colonnes: Array<{ nom: string; choix?: string[] }> };
  const choix = (nom: string) => lp.colonnes.find((c) => c.nom === nom)?.choix;

  it('source_eau / irrigation_methode / pompe_alim_actuelle', async () => {
    const lib = await import('../src/lib/questionnaire');
    expect([...lib.SOURCE_EAU_VALUES]).toEqual(choix('source_eau'));
    expect([...lib.IRRIGATION_METHODE_VALUES]).toEqual(choix('irrigation_methode'));
    expect([...lib.POMPE_ALIM_VALUES]).toEqual(choix('pompe_alim_actuelle'));
  });

  it('page : champs numériques step="any" et 12 mois en boutons', () => {
    expect(src).toContain('data-mois={m}');
    expect(src).toContain('MOIS_IRRIGATION_VALUES');
    const bloc = src.slice(src.indexOf("id === 'pompage'"), src.indexOf("id === 'toiture'"));
    expect(bloc).not.toMatch(/step="1"/);
    expect(bloc).toContain('step="any"');
  });
});

// CIW406 — sections PRO (contrat CIQ400 `exemple_pro` + `segment_pro`) : chaque
// colonne ÉCRITE par une section pro a un contrôle, et seulement elle.
describe('questionnaire pro — parité exemple_pro ↔ collectSectionRaw', () => {
  const pro = JSON.parse(
    read('../../../backend/django_core/apps/crm/contract_samples/questionnaire_lead.json'),
  ) as {
    exemple_pro: { champs: Record<string, string[]> };
    segment_pro: { sections_pro: string[]; refusees_400: string[] };
  };
  const SECTIONS_PRO_ECRITES = ['reseau', 'activite', 'site', 'societe'] as const;

  for (const section of SECTIONS_PRO_ECRITES) {
    const colonnes = pro.exemple_pro.champs[section];
    it(`${section} : le contrat liste des colonnes`, () => {
      expect(colonnes.length).toBeGreaterThan(0);
    });
    for (const col of colonnes) {
      it(`${section}.${col} a un contrôle sur la page`, () => {
        expect(collect.includes(col)).toBe(true);
      });
    }
    it(`${section} : le bloc de la page ne dessine QUE des colonnes du contrat`, () => {
      const debutBloc = src.indexOf(`{id === '${section}' && (`);
      expect(debutBloc).toBeGreaterThan(-1);
      const reste = src.slice(debutBloc + 10);
      const suivant = reste.search(/\n {22}\{id === '/);
      const bloc = suivant > 0 ? reste.slice(0, suivant) : reste.slice(0, 20000);
      const demandees = [...bloc.matchAll(new RegExp(`demande\\('${section}', '([a-z_0-9]+)'\\)`, 'g'))].map((m) => m[1]);
      expect(demandees.length).toBeGreaterThan(0);
      for (const col of demandees) expect(colonnes, `${section}.${col}`).toContain(col);
      // …et chaque colonne du contrat est effectivement gatée par `demande`.
      for (const col of colonnes) expect(demandees, `${section}.${col}`).toContain(col);
    });
  }

  it('les sections pro du contrat sont TOUTES des sections connues de la page', async () => {
    const lib = await import('../src/lib/questionnaire');
    for (const s of pro.segment_pro.sections_pro) {
      expect((lib.QUESTIONNAIRE_SECTIONS as readonly string[]).includes(s), s).toBe(true);
    }
  });

  it('aucune question résidentielle dans les blocs pro (maison, foyer, équipements domestiques)', () => {
    const debut = src.indexOf("{id === 'reseau' && (");
    const fin = src.indexOf('{isPhotoSection(id) && (');
    // Les blocs pro sont insérés AVANT les photos ; ils ne contiennent aucune
    // question de la section résidentielle « occupation » / « équipements ».
    const blocPro = src.slice(debut, src.indexOf("{id === 'pompage' && (", debut) > 0 ? src.indexOf("{id === 'pompage' && (", debut) : fin);
    expect(blocPro.length).toBeGreaterThan(1000);
    for (const interdit of [
      'à la maison', 'at home', 'foyer', 'household', 'equip_', 'occupation_jour', 'Chauffe-eau électrique',
      'Véhicule électrique', 'Passez-vous',
    ]) {
      expect(blocPro.includes(interdit), interdit).toBe(false);
    }
  });

  it('Q21 : budget, délai, décideur, concurrents ne sont JAMAIS demandés par écrit', () => {
    for (const interdit of ['budget', 'delai', 'décideur', 'decideur', 'concurrent', 'devis_concurrents']) {
      expect(collect.toLowerCase().includes(interdit), interdit).toBe(false);
    }
  });

  it('les libellés pro existent en FR, EN et AR (data-en / data-ar sur chaque label pro)', () => {
    const debut = src.indexOf("{id === 'reseau' && (");
    const bloc = src.slice(debut, src.indexOf('{isPhotoSection(id) && (', debut));
    const labels = bloc.match(/<label [^>]*for=/g) ?? [];
    const labelsI18n = bloc.match(/<label [^>]*data-i18n/g) ?? [];
    expect(labels.length).toBeGreaterThan(20);
    // Les <label> à `for=` du bloc pro (hors lignes de relevé construites en boucle) portent la traduction.
    expect(labelsI18n.length).toBeGreaterThanOrEqual(labels.length - 1);
    expect(bloc).toContain('data-ar=');
    expect(bloc).toContain('data-en=');
  });
});
