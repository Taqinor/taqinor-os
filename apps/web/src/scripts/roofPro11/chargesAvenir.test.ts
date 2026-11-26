// @vitest-environment jsdom
// ACAL780 (REP-780) — l'écran des charges à venir : saisie → document → relecture. Fichier à part
// du test d'aller-retour : il exige jsdom (le reste de ce dossier tourne sans DOM).
import { describe, expect, it } from 'vitest';
import { monterChargesAvenir, releireCharges, type ChargeAvenir } from './chargesAvenir';
import { enregistrerAtelier, exempleRoofLayoutV2, ouvrirAtelier } from './harnaisDocument';
import { type Ctx } from './context';
import { type SerializedLayout } from './prefill';

const documentRiche = () => JSON.parse(JSON.stringify(exempleRoofLayoutV2())) as SerializedLayout;
const monter = (c: Ctx) => {
  const hote = document.createElement('div');
  document.body.appendChild(hote);
  monterChargesAvenir(hote, {
    lire: () => c.consCharges ?? releireCharges(c.documentRelu?.consumption),
    ecrire: (l) => { c.consCharges = l; },
  });
  return hote;
};
const saisir = (hote: HTMLElement, valeurs: Record<string, string>) => {
  for (const [cle, v] of Object.entries(valeurs)) {
    hote.querySelector<HTMLInputElement>(`[data-cons-charge-champ="${cle}"]`)!.value = v;
  }
  hote.querySelector<HTMLElement>('[data-cons-charge-ajouter]')!.click();
};

describe('ACAL780 — panneau des charges à venir', () => {
  it('une voiture saisie (30 km, 16 kWh/100 km, 22-24) sort dans le document et se relit à l’identique', () => {
    const doc = documentRiche() as unknown as { consumption: Record<string, unknown> };
    const c = ouvrirAtelier({ id: 9, geometrie: { roof_layout: doc as unknown as SerializedLayout }, cibleVendue: false }).c;
    const hote = monter(c);
    saisir(hote, { km_par_jour: '30', kwh_par_100km: '16', fenetre_recharge: '22-24' });
    const voiture: ChargeAvenir = { type: 'vehicule', km_par_jour: 30, kwh_par_100km: 16, fenetre_recharge: [22, 23, 0] };
    const ecrit = enregistrerAtelier(c).consumption as { charges?: ChargeAvenir[] };
    expect(ecrit.charges).toEqual([voiture]);
    // rechargement : le document enregistré rouvre la liste, sans toucher à l'écran
    const rouvert = ouvrirAtelier({
      id: 9, geometrie: { roof_layout: { ...doc, consumption: ecrit } as unknown as SerializedLayout }, cibleVendue: false,
    }).c;
    const hote2 = monter(rouvert);
    expect(hote2.querySelectorAll('[data-cons-charge]')).toHaveLength(1);
    expect(hote2.textContent).toContain('30 km/jour');
    expect((enregistrerAtelier(rouvert).consumption as { charges?: ChargeAvenir[] }).charges).toEqual([voiture]);
  });

  it('ACAL1645 — une climatisation saisie (12 000 BTU, EER 10, 10-15 h) est postée, enregistrée et relue', () => {
    const doc = documentRiche() as unknown as { consumption: Record<string, unknown> };
    const c = ouvrirAtelier({ id: 9, geometrie: { roof_layout: doc as unknown as SerializedLayout }, cibleVendue: false }).c;
    const hote = monter(c);
    const choix = hote.querySelector<HTMLSelectElement>('[data-cons-charge-type]')!;
    expect(Array.from(choix.options).map((o) => o.value)).toContain('clim');
    choix.value = 'clim';
    choix.dispatchEvent(new Event('change', { bubbles: true }));
    saisir(hote, { btu: '12000', eer: '10', heures_fonctionnement: '10-15' });
    // puissance_kw = BTU/h ÷ EER ÷ 1000 (définition de l'EER) : c'est ce que le serveur lit pour `clim`
    const clim: ChargeAvenir = { type: 'clim', btu: 12000, eer: 10, puissance_kw: 1.2, heures_fonctionnement: [10, 11, 12, 13, 14, 15] };
    const ecrit = enregistrerAtelier(c).consumption as { charges?: ChargeAvenir[] };
    expect(ecrit.charges).toEqual([clim]);
    const rouvert = ouvrirAtelier({
      id: 9, geometrie: { roof_layout: { ...doc, consumption: ecrit } as unknown as SerializedLayout }, cibleVendue: false,
    }).c;
    const hote2 = monter(rouvert);
    expect(hote2.textContent).toContain('Climatisation');
    expect((enregistrerAtelier(rouvert).consumption as { charges?: ChargeAvenir[] }).charges).toEqual([clim]);
  });

  it('un champ vide est refusé sous le champ, rien n’est écrit ; « déjà dans mes factures » se coche et se relit', () => {
    const doc = documentRiche() as unknown as SerializedLayout;
    const c = ouvrirAtelier({ id: 9, geometrie: { roof_layout: doc }, cibleVendue: false }).c;
    const hote = monter(c);
    saisir(hote, { km_par_jour: '30', kwh_par_100km: '', fenetre_recharge: '22-24' });
    expect(hote.querySelector('[data-cons-charge-refus="kwh_par_100km"]')?.textContent).toContain('à saisir');
    expect(c.consCharges).toBeUndefined();
    saisir(hote, { km_par_jour: '30', kwh_par_100km: '16', fenetre_recharge: '22-24' });
    hote.querySelector<HTMLInputElement>('[data-cons-charge-deja="0"]')!.click();
    expect(c.consCharges?.[0].deja_dans_les_factures).toBe(true);
  });
});
