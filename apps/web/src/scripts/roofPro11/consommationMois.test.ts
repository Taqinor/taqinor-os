// @vitest-environment jsdom
// ACAL837 — la grille « Mes factures (1 à 12 mois) » : le corps posté et les 12 barres lues
// dans `mois[]` de la réponse. La réponse est l'`exemple_factures_mois` du contrat committé.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { racineDepot } from './harnaisAtelier';
import { corpsDepuisLignes, htmlBarres, monterGrilleFactures, type MoisPropose } from './consommationMois';

const CONTRAT = JSON.parse(readFileSync(join(
  racineDepot(), 'backend', 'django_core', 'apps', 'calepinage', 'contract_samples',
  'calepinage_consommation_proposee.json',
), 'utf8')) as Record<string, { mois: MoisPropose[] }>;
const MOIS = CONTRAT.exemple_factures_mois.mois;

afterEach(() => { vi.useRealTimers(); document.body.innerHTML = ''; });

describe('ACAL837 — corps posté', () => {
  it('3 mois en kWh : {source:factures, factures:{mois:[3 entrées]}}, sans classe', () => {
    const lignes = [1, 7, 10].map((m, i) => ({ mois: m, valeur: ['300', '500', '400'][i], unite: 'kwh' as const }));
    expect(corpsDepuisLignes(lignes, 'residentiel')).toEqual({
      source: 'factures', factures: { mois: [{ mois: 1, kwh: 300 }, { mois: 7, kwh: 500 }, { mois: 10, kwh: 400 }] },
    });
  });
  it('la classe n’est jointe que si une ligne est en MAD ; rien de saisi ⇒ aucun corps', () => {
    const corps = corpsDepuisLignes([{ mois: 1, valeur: '450,5', unite: 'mad' }], 'residentiel');
    expect(corps?.factures).toEqual({ mois: [{ mois: 1, mad: 450.5 }], classe: 'residentiel' });
    expect(corpsDepuisLignes([{ mois: 1, valeur: '', unite: 'kwh' }], 'residentiel')).toBeNull();
  });
});

describe('ACAL837 — 12 barres lues dans mois[]', () => {
  it('3 pleines (facture), 9 en pointillé avec « estimé »', () => {
    document.body.innerHTML = htmlBarres(MOIS);
    expect(document.querySelectorAll('[data-cons-mois-barre]')).toHaveLength(12);
    expect(document.querySelectorAll('[data-source="facture"]')).toHaveLength(3);
    const estimes = document.querySelectorAll('[data-source="estime"]');
    expect(estimes).toHaveLength(9);
    estimes.forEach((el) => expect(el.textContent).toContain('estimé'));
    expect(document.querySelector('[data-source="facture"]')?.textContent).not.toContain('estimé');
  });
});

describe('ACAL837 — la grille', () => {
  function monter() {
    const hote = document.createElement('div');
    document.body.appendChild(hote);
    let ecoute: Parameters<Parameters<typeof monterGrilleFactures>[1]['ecouter']>[0] = () => undefined;
    const lancer = vi.fn();
    monterGrilleFactures(hote, { lancer, classe: () => '', ecouter: (f) => { ecoute = f; } });
    const saisir = (mois: number, valeur: string) => {
      const champ = hote.querySelector<HTMLInputElement>(`[data-cons-mois-ligne="${mois}"] [data-cons-mois-valeur]`)!;
      champ.value = valeur;
      champ.dispatchEvent(new Event('input', { bubbles: true }));
    };
    return { hote, lancer, saisir, repondre: (...a: Parameters<typeof ecoute>) => ecoute(...a) };
  }

  it('600 ms après la dernière frappe : un seul envoi, puis 12 barres dont 9 en pointillé', async () => {
    vi.useFakeTimers();
    const { hote, lancer, saisir, repondre } = monter();
    saisir(1, '300'); saisir(7, '500'); saisir(10, '400');
    await vi.advanceTimersByTimeAsync(599);
    expect(lancer).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(2);
    expect(lancer).toHaveBeenCalledTimes(1);
    expect(lancer.mock.calls[0][0].factures.mois).toHaveLength(3);
    repondre({ mois: MOIS });
    expect(hote.querySelectorAll('[data-cons-mois-barre]')).toHaveLength(12);
    expect(hote.querySelectorAll('[data-source="estime"]')).toHaveLength(9);
  });

  it('un refus factures.mois[2].kwh s’affiche sous la ligne d’octobre', async () => {
    vi.useFakeTimers();
    const { hote, saisir, repondre } = monter();
    saisir(1, '300'); saisir(7, '500'); saisir(10, '-4');
    saisir(10, '4x');
    await vi.advanceTimersByTimeAsync(700);
    saisir(10, '400');
    await vi.advanceTimersByTimeAsync(700);
    repondre(null, { champs: { 'factures.mois[2].kwh': 'Cette facture est trop basse.' } });
    const refus = hote.querySelector<HTMLElement>('[data-cons-mois-ligne="10"] [data-cons-mois-refus]')!;
    expect(refus.hidden).toBe(false);
    expect(refus.textContent).toBe('Cette facture est trop basse.');
    expect(hote.querySelector<HTMLElement>('[data-cons-mois-ligne="7"] [data-cons-mois-refus]')!.hidden).toBe(true);
  });
});
