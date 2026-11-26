// @vitest-environment jsdom
// ACAL837 — la grille « Mes factures (1 à 12 mois) » : le corps posté et les 12 barres lues
// dans `mois[]` de la réponse. La réponse est l'`exemple_factures_mois` du contrat committé.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { racineDepot } from './harnaisAtelier';
import { corpsDepuisLignes, facturesAEcrire, htmlBarres, liaisonFactures, monterGrilleFactures, MOTIF_LECTURE_VIDE, releireFacturesMois, type LectureFacture, type MoisPropose } from './consommationMois';

const CONTRAT = JSON.parse(readFileSync(join(
  racineDepot(), 'backend', 'django_core', 'apps', 'calepinage', 'contract_samples',
  'calepinage_consommation_proposee.json',
), 'utf8')) as Record<string, { mois: MoisPropose[] }>;
const MOIS = CONTRAT.exemple_factures_mois.mois;
const PHOTO = JSON.parse(readFileSync(join(
  racineDepot(), 'backend', 'django_core', 'apps', 'calepinage', 'contract_samples',
  'calepinage_consommation_photo_facture.json',
), 'utf8')) as Record<string, LectureFacture>;

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

// ACAL1643 — les 12 barres tiennent dans la colonne (269 px) comme à 1440 px : largeur RELATIVE, jamais le contenu qui impose.
describe('ACAL1643 — barres en largeur relative', () => {
  it('chaque barre se répartit à parts égales et peut rétrécir ; ses libellés se replient au lieu de déborder', () => {
    document.body.innerHTML = htmlBarres(MOIS);
    const barres = Array.from(document.querySelectorAll<HTMLElement>('[data-cons-mois-barre]'));
    expect(barres).toHaveLength(12);
    for (const b of barres) {
      expect(b.style.flexGrow).toBe('1');
      expect(b.style.flexShrink).toBe('1');
      expect(b.style.flexBasis).toMatch(/^0(%|px)?$/);
      expect(b.style.minWidth).toMatch(/^0(px)?$/);
      expect(b.style.overflowWrap).toBe('anywhere');
      expect(b.style.width).toBe(''); // aucune largeur fixe
    }
  });

  it('le conteneur des barres peut lui-même rétrécir dans la colonne', () => {
    const hote = document.createElement('div');
    document.body.appendChild(hote);
    monterGrilleFactures(hote, { lancer: () => {}, classe: () => 'residentiel', ecouter: () => {} });
    const conteneur = hote.querySelector<HTMLElement>('[data-cons-mois-barres]')!;
    expect(conteneur.style.minWidth).toMatch(/^0(px)?$/);
    expect(conteneur.style.width).toBe('100%');
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

describe('ACAL840 — lire une photo de facture', () => {
  const attendre = () => new Promise((r) => setTimeout(r, 0));
  function monterPhoto(disponible: { disponible: boolean; motif?: string | null }, lecture: LectureFacture) {
    const hote = document.createElement('div');
    document.body.appendChild(hote);
    const lire = vi.fn(async () => lecture);
    monterGrilleFactures(hote, {
      lancer: vi.fn(), classe: () => '', ecouter: () => undefined,
      lireFacture: { disponible: async () => disponible, lire },
    });
    return { hote, lire };
  }
  const choisirPhoto = async (hote: HTMLElement) => {
    const champ = hote.querySelector<HTMLInputElement>('[data-cons-photo-fichier]')!;
    Object.defineProperty(champ, 'files', { value: [new File(['x'], 'facture.jpg')] });
    champ.dispatchEvent(new Event('change', { bubbles: true }));
    await attendre();
  };

  it('bouton absent sans disponibilité : la raison seule, en petit texte', async () => {
    const { hote } = monterPhoto(PHOTO.exemple_indisponible, PHOTO.exemple_indisponible);
    await attendre();
    expect(hote.querySelector('[data-cons-photo-fichier]')).toBeNull();
    expect(hote.querySelector('[data-cons-photo-message]')?.textContent).toBe(PHOTO.exemple_indisponible.motif);
  });

  it('sans option fournie : aucun bloc photo', () => {
    const hote = document.createElement('div');
    monterGrilleFactures(hote, { lancer: vi.fn(), classe: () => '', ecouter: () => undefined });
    expect(hote.querySelector('[data-cons-photo]')).toBeNull();
  });

  it('une ligne gardée remplit janvier en kWh (le mois est choisi, le kWh lu)', async () => {
    const { hote } = monterPhoto(PHOTO.exemple_disponibilite, PHOTO.exemple);
    await attendre();
    await choisirPhoto(hote);
    const ligne = hote.querySelector<HTMLElement>('[data-cons-photo-ligne]')!;
    expect(ligne.querySelector<HTMLInputElement>('[data-cons-photo-kwh]')!.value).toBe('412');
    // « Garder » sans mois : refus sous le champ, la grille reste vide.
    ligne.querySelector<HTMLElement>('[data-cons-photo-garder]')!.click();
    expect(ligne.querySelector<HTMLElement>('[data-cons-photo-refus]')!.textContent).toContain('Choisissez le mois');
    expect(hote.querySelector<HTMLInputElement>('[data-cons-mois-ligne="1"] [data-cons-mois-valeur]')!.value).toBe('');
    const choix = ligne.querySelector<HTMLSelectElement>('[data-cons-photo-mois]')!;
    choix.value = '1';
    ligne.querySelector<HTMLElement>('[data-cons-photo-garder]')!.click();
    expect(hote.querySelector<HTMLInputElement>('[data-cons-mois-ligne="1"] [data-cons-mois-valeur]')!.value).toBe('412');
    expect(hote.querySelector('[data-cons-photo-ligne]')).toBeNull();
  });

  it('« Ignorer » retire la ligne sans rien remplir ; lecture vide : message de repli', async () => {
    const { hote } = monterPhoto(PHOTO.exemple_disponibilite, PHOTO.exemple);
    await attendre();
    await choisirPhoto(hote);
    hote.querySelector<HTMLElement>('[data-cons-photo-ignorer]')!.click();
    expect(hote.querySelector('[data-cons-photo-ligne]')).toBeNull();
    expect(hote.querySelector<HTMLInputElement>('[data-cons-mois-ligne="1"] [data-cons-mois-valeur]')!.value).toBe('');
    const vide = monterPhoto(PHOTO.exemple_disponibilite, { disponible: true, motif: null, lignes: [] });
    await attendre();
    await choisirPhoto(vide.hote);
    expect(vide.hote.querySelector('[data-cons-photo-message]')?.textContent).toBe(MOTIF_LECTURE_VIDE);
  });
});

// ACAL1610 — les factures mensuelles saisies sont relues du document (`consumption.factures_mois`,
// contrat ACAL1601) au rechargement, et réécrites au document à chaque frappe.
describe('ACAL1610 — grille remplie depuis le document relu', () => {
  const TROIS = [{ mois: 1, valeur: 520, unite: 'kwh' as const }, { mois: 2, valeur: 480, unite: 'kwh' as const },
    { mois: 3, valeur: 450, unite: 'kwh' as const }];
  function monterAvec(relues: unknown) {
    const hote = document.createElement('div');
    document.body.appendChild(hote);
    const ctx = { documentRelu: { consumption: { factures_mois: relues } } } as Record<string, unknown>;
    const lancer = vi.fn();
    monterGrilleFactures(hote, { lancer, classe: () => '', ecouter: () => undefined, factures: liaisonFactures(ctx as never) });
    const valeur = (m: number) => hote.querySelector<HTMLInputElement>(`[data-cons-mois-ligne="${m}"] [data-cons-mois-valeur]`)!;
    const unite = (m: number) => hote.querySelector<HTMLSelectElement>(`[data-cons-mois-ligne="${m}"] [data-cons-mois-unite]`)!;
    return { hote, ctx, lancer, valeur, unite };
  }

  it('janv. 520, févr. 480, mars 450 kWh relus, la proposition relancée (barres), un 4e mois s’ajoute aux trois', () => {
    const { ctx, lancer, valeur, unite } = monterAvec(TROIS);
    expect([1, 2, 3].map((m) => valeur(m).value)).toEqual(['520', '480', '450']);
    expect(unite(1).value).toBe('kwh');
    expect(valeur(4).value).toBe('');
    expect(lancer).toHaveBeenCalledTimes(1);
    expect(lancer.mock.calls[0][0].factures.mois).toEqual([{ mois: 1, kwh: 520 }, { mois: 2, kwh: 480 }, { mois: 3, kwh: 450 }]);
    valeur(4).value = '430';
    valeur(4).dispatchEvent(new Event('input', { bubbles: true }));
    expect(facturesAEcrire(ctx as never)).toEqual([...TROIS, { mois: 4, valeur: 430, unite: 'kwh' }]);
  });

  // ACAL1909 — dans l'atelier réel la grille est montée AVANT que le document relu soit posé au ctx.
  it('document relu posé APRÈS le montage : ouverture de la grille ⇒ trois mois relus, un 4e s’ajoute aux trois', () => {
    const hote = document.createElement('div');
    document.body.appendChild(hote);
    const ctx = {} as Record<string, unknown>;
    monterGrilleFactures(hote, { lancer: vi.fn(), classe: () => '', ecouter: () => undefined, factures: liaisonFactures(ctx as never) });
    const valeur = (m: number) => hote.querySelector<HTMLInputElement>(`[data-cons-mois-ligne="${m}"] [data-cons-mois-valeur]`)!;
    expect(valeur(1).value).toBe('');
    ctx.documentRelu = { consumption: { factures_mois: TROIS } };
    hote.querySelector<HTMLElement>('[data-cons-mois-grille]')!.dispatchEvent(new Event('toggle'));
    expect([1, 2, 3].map((m) => valeur(m).value)).toEqual(['520', '480', '450']);
    valeur(4).value = '430';
    valeur(4).dispatchEvent(new Event('input', { bubbles: true }));
    expect(facturesAEcrire(ctx as never)).toEqual([...TROIS, { mois: 4, valeur: 430, unite: 'kwh' }]);
  });

  it('un mois saisi avant toute relecture part avec les mois enregistrés, jamais seul ; un mois effacé à la main reste effacé', () => {
    const hote = document.createElement('div');
    document.body.appendChild(hote);
    const ctx = {} as Record<string, unknown>;
    monterGrilleFactures(hote, { lancer: vi.fn(), classe: () => '', ecouter: () => undefined, factures: liaisonFactures(ctx as never) });
    const valeur = (m: number) => hote.querySelector<HTMLInputElement>(`[data-cons-mois-ligne="${m}"] [data-cons-mois-valeur]`)!;
    ctx.documentRelu = { consumption: { factures_mois: TROIS } };
    valeur(4).value = '430';
    valeur(4).dispatchEvent(new Event('input', { bubbles: true }));
    expect(facturesAEcrire(ctx as never)).toEqual([...TROIS, { mois: 4, valeur: 430, unite: 'kwh' }]);
    valeur(1).value = '';
    valeur(1).dispatchEvent(new Event('input', { bubbles: true }));
    hote.querySelector<HTMLElement>('[data-cons-mois-grille]')!.dispatchEvent(new Event('toggle'));
    expect(valeur(1).value).toBe('');
  });

  it('une unité MAD relue revient en MAD ; une entrée hors contrat est ignorée', () => {
    const { valeur, unite } = monterAvec([{ mois: 7, valeur: 600, unite: 'mad' }, { mois: 13, valeur: 1, unite: 'kwh' }]);
    expect(valeur(7).value).toBe('600');
    expect(unite(7).value).toBe('mad');
    expect(releireFacturesMois({ factures_mois: [{ mois: 13, valeur: 1, unite: 'kwh' }, { mois: 2, valeur: 0, unite: 'kwh' }] })).toEqual([]);
  });

  it('le document enregistré porte consumption.factures_mois (aller-retour)', async () => {
    const { construireConsommation } = await import('./consommationSerialisee');
    const ctx = { consCurve: new Array(24).fill(0.5), consFacturesMois: TROIS } as never;
    expect(construireConsommation(ctx, [], false, false).factures_mois).toEqual(TROIS);
    const relu = { consCurve: new Array(24).fill(0.5), documentRelu: { consumption: { factures_mois: TROIS } } } as never;
    expect(construireConsommation(relu, [], false, false).factures_mois).toEqual(TROIS);
    expect('factures_mois' in construireConsommation({ consCurve: new Array(24).fill(0.5) } as never, [], false, false)).toBe(false);
  });

  it('T4-U4-025 — deux sérialisations sans geste, à 4 s d’écart : la même signature (aucun brouillon par tic)', async () => {
    const { construireConsommation } = await import('./consommationSerialisee');
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-24T17:55:28.193Z'));
    const ctx = { consCurve: new Array(24).fill(0.5) } as never;
    const premier = construireConsommation(ctx, [], false, false);
    vi.setSystemTime(new Date('2026-11-24T17:55:32.191Z'));
    const second = construireConsommation(ctx, [], false, false);
    expect(second.source).toEqual(premier.source);
    expect(premier.source).toEqual({ origine: 'atelier', saisi_le: '2026-11-24T17:55:28.193Z' });
    expect((ctx as { consSource?: unknown }).consSource).toBeUndefined(); // jamais « relue » pour autant
  });
});
