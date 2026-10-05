// AGW302 — « Nos hypothèses » suit le VRAI mode du devis (clé machine
// `mode_installation`), pas `quote.inst_type` (libellé capitalisé que le builder
// produit : « Agricole », « Industrielle », « Commerciale », « Résidentielle »).
import { describe, expect, it } from 'vitest';
import { proposalAssumptions, type ProposalResponse } from '../src/lib/proposition';

function proposal(mode: string, instType: string, extra: Record<string, unknown> = {}): ProposalResponse {
  return {
    reference: 'DEV-2026-302',
    date: '01/10/2026',
    client_name: 'Client',
    statut: 'envoye',
    mode_installation: mode,
    quote: {
      ref: 'DEV-2026-302',
      date: '01/10/2026',
      client_name: 'Client',
      inst_type: instType,
      totaux_sans: { ht_brut: 900000, remise: 0, ht_net: 900000, tva: 180000, ttc: 1080000 },
      display_total: 1080000,
      nb_options: 1,
    },
    roof_image_url: null,
    option_totals: { sans_batterie: 1080000, avec_batterie: 0, display_total: 1080000, nb_options: 1 },
    accepted: false,
    ...extra,
  } as unknown as ProposalResponse;
}

const tout = (items: ReturnType<typeof proposalAssumptions>) =>
  items.map((i) => `${i.label} ${i.value} ${i.valueAr} ${i.valueEn} ${i.labelEn}`).join(' | ');
const typeLigne = (items: ReturnType<typeof proposalAssumptions>) =>
  items.find((i) => i.label === "Type d'installation");

describe('AGW302 — les 4 valeurs réelles d\'inst_type', () => {
  it('« Agricole » : libellé pompage, aucune ligne 82-21 ni ONEE ni horizon de panneau', () => {
    const items = proposalAssumptions(
      proposal('agricole', 'Agricole', {
        mode_kpis: { pompe_cv: 7.5, hmt_m: 58.7, debit_hmt_m3h: 30.5, m3_jour: 134, heures_pompage: 4.4 },
      }),
    );
    expect(typeLigne(items)?.value).toContain('Pompage solaire');
    const txt = tout(items);
    expect(txt).not.toMatch(/82-21|ONEE|SRM|Cadre tarifaire|Horizon d'analyse/);
    expect(txt).toContain('4,4'); // heures de pompage lues dans le payload
    expect(txt).toMatch(/HMT 58,7 m/);
    expect(txt).toMatch(/30,5 m³\/h/);
    expect(items.some((i) => i.label === 'Heures de pompage')).toBe(true);
  });

  it('agricole : la provenance déclaré/mesuré apparaît quand synthese_agricole est servie', () => {
    const items = proposalAssumptions(
      proposal('agricole', 'Agricole', {
        mode_kpis: { hmt_m: 58.7, heures_pompage: 4.4 },
        synthese_agricole: {
          provenance: {
            volume_m3_jour: { origine: 'lead', detail: 'client', date: '2026-09-12' },
            niveau_statique_m: { origine: 'lead', detail: 'mesure_visite', date: '2026-09-15' },
            debit_exploitation_m3h: { origine: 'saisie', detail: 'foreur', date: '2026-09-15' },
          },
        },
      }),
    );
    const prov = items.find((i) => i.label === 'Provenance des données');
    expect(prov).toBeDefined();
    expect(prov!.value).toContain('déclaré par le client');
    expect(prov!.value).toContain('mesuré lors de la visite');
    expect(prov!.valueEn).toContain('measured during the site visit');
  });

  it('agricole sans synthese_agricole ni KPI : aucune provenance inventée', () => {
    const items = proposalAssumptions(proposal('agricole', 'Agricole'));
    expect(items.some((i) => i.label === 'Provenance des données')).toBe(false);
    expect(typeLigne(items)?.value).toContain('Pompage solaire');
  });

  it.each([
    ['industriel', 'Industrielle', 'Autoconsommation industrielle'],
    ['commercial', 'Commerciale', 'Autoconsommation commerciale'],
    ['residentiel', 'Résidentielle', 'Résidentiel (simulateur)'],
  ])('« %s / %s » : bon libellé, distributeur « SRM », plus d\'ONEE', (mode, instType, attendu) => {
    const items = proposalAssumptions(proposal(mode, instType));
    expect(typeLigne(items)?.value).toContain(attendu);
    const txt = tout(items);
    expect(txt).toContain('SRM');
    expect(txt).not.toContain('ONEE');
    expect(txt).toContain('82-21');
    expect(items.some((i) => i.label === "Horizon d'analyse")).toBe(true);
  });

  it('le libellé ne dépend JAMAIS de inst_type : la clé machine l\'emporte', () => {
    // inst_type dit « Résidentielle » mais la clé machine dit agricole.
    const items = proposalAssumptions(proposal('agricole', 'Résidentielle'));
    expect(typeLigne(items)?.value).toContain('Pompage solaire');
    expect(tout(items)).not.toMatch(/82-21|ONEE/);
  });
});
