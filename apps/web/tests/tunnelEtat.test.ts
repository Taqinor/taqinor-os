// RWEB17-M0 — contrat d'état du tunnel mon-toit hors DOM.
import { describe, expect, it } from 'vitest';
import { creerContexte, creerCrochets, type ConfigLocale } from '../src/lib/tunnel/contexte';
import { creerDom } from '../src/lib/tunnel/dom';
import { creerEtat, type WizardSnapshot } from '../src/lib/tunnel/etat';

// Valeurs attendues = ce que les pages calculent aujourd'hui (écrites à la main
// d'après les initialisations de mon-toit.astro, pas recalculées par le module).
const DEFAUTS_SELECTION = {
  proUnit: 'mad', tension: 'bt', activity: 'day', tensionTouched: false, activityTouched: false,
  surfaceType: '', waterSource: '', waterUnit: 'm3h', commercialCategory: '', ccUnit: 'mad',
  equipes: '', regionAgricole: '', roofInputMode: 'point',
};

describe('creerEtat — 6 instantanés', () => {
  it('aucun instantané : défauts de la page', () => {
    const e = creerEtat(null, 'fr');
    expect(e).toMatchObject({
      ...DEFAUTS_SELECTION, mode: '', step: 0, revealed: false, firstRender: true, currentLang: 'fr',
      restoring: false, hasEnteredData: false, submitted: false, clientRef: '', occupationJour: '',
      visitWindowPart: '', visitWindowWeek: '', estimateShown: null, lastKwc: null,
    });
    expect(e.dedupIdempotencyKey).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(e.dedupEventId).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(e.dedupIdempotencyKey).not.toBe(e.dedupEventId);
    expect(Object.keys(e)).toHaveLength(47);
  });

  it('instantané vide {}', () => {
    const e = creerEtat({}, 'en');
    expect(e).toMatchObject({ ...DEFAUTS_SELECTION, mode: '', step: 0, revealed: false });
  });

  it('ancien assistant : step 2 sans revealed → step borné à 1, revealed vrai (WJ61)', () => {
    const e = creerEtat({ step: 2 }, 'fr');
    expect(e.step).toBe(1);
    expect(e.revealed).toBe(true);
  });

  it('step hors bornes : borné à [0, 1]', () => {
    expect(creerEtat({ step: -3 }, 'fr').step).toBe(0);
    expect(creerEtat({ step: 9 }, 'fr').step).toBe(1);
    expect(creerEtat({ step: 1, revealed: false }, 'fr').revealed).toBe(false);
  });

  it('brouillon complet : jetons, mode, fenêtre de visite, sélections', () => {
    const snap: WizardSnapshot = {
      step: 1, revealed: true, mode: 'agricole', visitWindowPart: 'matin', visitWindowWeek: 'cette',
      idempotencyKey: 'idem-12345678', eventId: 'evt-12345678',
      sel: {
        occupationJour: 'absent', proUnit: 'kwh', tension: 'mt', activity: 'night',
        tensionTouched: '1', activityTouched: '1', surfaceType: 'toit', waterSource: 'puits',
        waterUnit: 'lh', commercialCategory: 'hotel', ccUnit: 'kwh', equipes: '3x8',
        regionAgricole: 'souss', roofInputMode: 'draw',
      },
    };
    const e = creerEtat(snap, 'ar');
    expect(e).toMatchObject({
      step: 1, revealed: true, mode: 'agricole', visitWindowPart: 'matin', visitWindowWeek: 'cette',
      dedupIdempotencyKey: 'idem-12345678', dedupEventId: 'evt-12345678', occupationJour: 'absent',
      proUnit: 'kwh', tension: 'mt', activity: 'night', tensionTouched: true, activityTouched: true,
      surfaceType: 'toit', waterSource: 'puits', waterUnit: 'lh', commercialCategory: 'hotel',
      ccUnit: 'kwh', equipes: '3x8', regionAgricole: 'souss', roofInputMode: 'draw', currentLang: 'fr',
    });
  });

  it('touched ≠ "1" et roofInputMode inconnu : retombent sur les défauts', () => {
    const e = creerEtat({ sel: { tensionTouched: '0', activityTouched: 'oui', roofInputMode: 'zzz' } }, 'fr');
    expect(e).toMatchObject({ tensionTouched: false, activityTouched: false, roofInputMode: 'point' });
  });

  it('chaque appel rend un état neuf (pas de tableau partagé)', () => {
    const a = creerEtat(null, 'fr');
    const b = creerEtat(null, 'fr');
    a.captureOutline.push([1, 2]);
    expect(b.captureOutline).toEqual([]);
  });
});

describe('registre de crochets', () => {
  it('lève « Crochet non installé : <nom> » pour un crochet absent', () => {
    const c = creerCrochets();
    expect(() => c.appeler('saveWizardState')).toThrow('Crochet non installé : saveWizardState');
    expect(c.a('saveWizardState')).toBe(false);
  });

  it('appelle un crochet installé avec ses arguments', () => {
    const c = creerCrochets();
    c.installer('add', (a: number, b: number) => a + b);
    expect(c.a('add')).toBe(true);
    expect(c.appeler('add', 2, 3)).toBe(5);
  });

  it('creerContexte assemble locale, état, dom, crochets, config', () => {
    const doc = { getElementById: () => null } as unknown as Document;
    const config: ConfigLocale = { locale: 'en', langueBasculable: false, formatNombre: (n) => String(n) };
    const ctx = creerContexte(creerDom(doc), creerEtat(null, 'en'), config);
    expect(ctx.locale).toBe('en');
    expect(ctx.config.langueBasculable).toBe(false);
    expect(() => ctx.crochets.appeler('x')).toThrow('Crochet non installé : x');
  });
});

describe('creerDom — Document injecté', () => {
  it('val/num/setText/setFieldError lisent et écrivent sur le document injecté', () => {
    const els: Record<string, any> = {
      a: { value: ' 12.5 ' }, b: { value: '' }, c: { value: 'x' }, t: { textContent: '' },
      i: { attrs: {} as Record<string, string>, setAttribute(k: string, v: string) { this.attrs[k] = v; } },
      er: { textContent: '', hidden: true },
    };
    const d = creerDom({ getElementById: (id: string) => els[id] ?? null } as unknown as Document);
    expect(d.val('a')).toBe(' 12.5 ');
    expect(d.num('a')).toBe(12.5);
    expect(d.num('b')).toBeNull();
    expect(d.num('c')).toBeNull();
    expect(d.val('absent')).toBe('');
    d.setText('t', 'ok');
    expect(els.t.textContent).toBe('ok');
    d.setFieldError('i', 'er', 'Erreur');
    expect(els.i.attrs['aria-invalid']).toBe('true');
    expect(els.er).toMatchObject({ textContent: 'Erreur', hidden: false });
    d.setFieldError('i', 'er', null);
    expect(els.er).toMatchObject({ textContent: '', hidden: true });
    expect(d.pct(0.42)).toBe(42);
    expect(d.pct(42.4)).toBe(42);
    expect(d.maxBillFor('inconnu')).toBe(200_000);
  });
});
