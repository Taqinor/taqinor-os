// @vitest-environment jsdom
// RWEB17-M3 — section « sélections » du tunnel mon-toit, hors page.
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { creerContexte } from '../src/lib/tunnel/contexte';
import { creerDom } from '../src/lib/tunnel/dom';
import { creerEtat, type LocaleTunnel } from '../src/lib/tunnel/etat';
import { installerSelections } from '../src/lib/tunnel/selections';

function monter() {
  document.body.innerHTML = `
    <button class="mt-tension" data-value="bt"></button><button class="mt-tension" data-value="mt"></button>
    <button class="mt-activity" data-value="day"></button><button class="mt-activity" data-value="night"></button>
    <button class="mt-equipes" data-value="1x8"></button><button class="mt-equipes" data-value="3x8"></button>
    <button class="mt-visit-part" data-value="matin"></button><button class="mt-visit-part" data-value="soir"></button>
    <button class="mt-occ-btn" data-occ-id="presence_jour"><span class="mt-occ-chosen" hidden></span></button>
    <button class="mt-occ-btn" data-occ-id="absence_jour"><span class="mt-occ-chosen" hidden></span></button>
    <svg id="mt-occ-chart"></svg><input id="mt-occupation-jour">
    <input type="checkbox" id="mt-equip-ve"><div data-equip-detail hidden><input id="mt-equip-ve-km"></div>
    <input id="mt-facture-hiver"><select id="mt-bill"><option value="">-</option><option value="1000-1500">1 000 à 1 500 MAD</option><option value="gt10000">+10k</option></select>
    <div id="mt-bill-wrap"></div><div id="mt-bill-detected" hidden><span id="mt-bill-detected-value"></span></div>
    <span id="mt-bill-err"></span>
    <select id="mt-culture"><option value=""></option><option value="olivier">o</option></select>
    <button class="mt-culture-card" data-value="olivier"></button>`;
}

function installer(locale: LocaleTunnel = 'fr') {
  const ctx = creerContexte(creerDom(document), creerEtat(null, locale), {
    locale, langueBasculable: locale !== 'en', formatNombre: String,
  });
  const calc = vi.fn(() => true);
  const mark = vi.fn();
  const save = vi.fn();
  ctx.crochets.installer('computeEstimate', calc);
  ctx.crochets.installer('markDataEntered', mark);
  ctx.crochets.installer('saveWizardState', save);
  const s = installerSelections(ctx);
  return { ctx, s, calc, mark, save };
}
const q = (sel: string) => [...document.querySelectorAll<HTMLElement>(sel)];
const clic = (el: Element) => el.dispatchEvent(new MouseEvent('click', { bubbles: true }));

beforeEach(monter);

describe('groupes de cartes', () => {
  it('un clic met à jour ctx.etat et aria-pressed, recalcule UNE fois', () => {
    const { ctx, s, calc, mark, save } = installer();
    s.brancherGroupes();
    expect(q('.mt-tension').map((b) => b.getAttribute('aria-pressed'))).toEqual(['true', 'false']); // défaut BT visible
    clic(q('.mt-tension')[1]);
    expect(ctx.etat.tension).toBe('mt');
    expect(q('.mt-tension').map((b) => b.getAttribute('aria-pressed'))).toEqual(['false', 'true']);
    expect(calc).toHaveBeenCalledTimes(1);
    expect(mark).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledTimes(1);
  });

  it('tensionTouched / activityTouched passent à vrai seulement après un clic', () => {
    const { ctx, s } = installer();
    s.brancherGroupes();
    expect(ctx.etat.tensionTouched).toBe(false);
    expect(ctx.etat.activityTouched).toBe(false);
    clic(q('.mt-tension')[0]);
    expect(ctx.etat.tensionTouched).toBe(true);
    expect(ctx.etat.activityTouched).toBe(false);
    clic(q('.mt-activity')[1]);
    expect(ctx.etat.activity).toBe('night');
    expect(ctx.etat.activityTouched).toBe(true);
  });

  it('allowUnset remet à « » ; sans allowUnset le même clic garde la valeur', () => {
    const { ctx, s } = installer();
    s.brancherGroupes();
    clic(q('.mt-equipes')[0]);
    expect(ctx.etat.equipes).toBe('1x8');
    clic(q('.mt-equipes')[0]);
    expect(ctx.etat.equipes).toBe('');
    expect(q('.mt-equipes')[0].getAttribute('aria-pressed')).toBe('false');
    clic(q('.mt-tension')[1]);
    clic(q('.mt-tension')[1]);
    expect(ctx.etat.tension).toBe('mt');
  });

  it('culture : clic bascule le <select> et recalcule', () => {
    const { s, calc } = installer();
    s.brancherGroupes();
    clic(q('.mt-culture-card')[0]);
    expect((document.getElementById('mt-culture') as HTMLSelectElement).value).toBe('olivier');
    expect(q('.mt-culture-card')[0].getAttribute('aria-pressed')).toBe('true');
    expect(calc).toHaveBeenCalledTimes(1);
  });
});

describe('visite, occupation, équipements', () => {
  it('créneau de visite : bascule unique, second clic remet à « »', () => {
    const { ctx, s } = installer();
    s.brancherVisiteOccupationEquipements();
    clic(q('.mt-visit-part')[0]);
    expect(ctx.etat.visitWindowPart).toBe('matin');
    clic(q('.mt-visit-part')[1]);
    expect(ctx.etat.visitWindowPart).toBe('soir');
    clic(q('.mt-visit-part')[1]);
    expect(ctx.etat.visitWindowPart).toBe('');
  });

  it("occupation : vocabulaire lead (present/absent), champ caché et badge suivent", () => {
    const { ctx, s } = installer();
    s.brancherVisiteOccupationEquipements();
    expect(document.querySelectorAll('[data-occ-line]')).toHaveLength(3);
    clic(q('.mt-occ-btn')[0]);
    expect(ctx.etat.occupationJour).toBe('present');
    expect((document.getElementById('mt-occupation-jour') as HTMLInputElement).value).toBe('present');
    expect(q('.mt-occ-chosen')[0].hidden).toBe(false);
    clic(q('.mt-occ-btn')[1]);
    expect(ctx.etat.occupationJour).toBe('absent');
    clic(q('.mt-occ-btn')[1]);
    expect(ctx.etat.occupationJour).toBe('');
  });

  it('équipement : le détail apparaît seulement si la case est cochée', () => {
    const { s } = installer();
    s.brancherVisiteOccupationEquipements();
    const wrap = document.querySelector<HTMLElement>('[data-equip-detail]')!;
    expect(wrap.hidden).toBe(true);
    const chk = document.getElementById('mt-equip-ve') as HTMLInputElement;
    chk.checked = true;
    chk.dispatchEvent(new Event('change'));
    expect(wrap.hidden).toBe(false);
  });
});

describe('facture mensuelle', () => {
  const set = (id: string, v: string) => { (document.getElementById(id) as HTMLInputElement).value = v; };

  it('montant exact prioritaire, sinon milieu de tranche, sinon null', () => {
    const { s } = installer();
    expect(s.resolveMonthlyBill()).toBeNull();
    set('mt-bill', '1000-1500');
    expect(s.resolveMonthlyBill()).toBe(1250);
    set('mt-bill', 'gt10000');
    expect(s.resolveMonthlyBill()).toBe(12000);
    set('mt-facture-hiver', '1800');
    expect(s.resolveMonthlyBill()).toBe(1800);
    set('mt-facture-hiver', '0');
    expect(s.resolveMonthlyBill()).toBe(12000);
  });

  it.each([['fr', '1 000 – 1 500 MAD'], ['en', '1,000 – 1,500 MAD'], ['ar', '1 000 à 1 500 MAD']] as const)(
    'tranche détectée depuis le montant exact (%s)',
    (locale, attendu) => {
      const { s } = installer(locale);
      set('mt-facture-hiver', '1200');
      s.syncBillRangeFromExact();
      expect((document.getElementById('mt-bill') as HTMLSelectElement).value).toBe('1000-1500');
      expect((document.getElementById('mt-bill-wrap') as HTMLElement).hidden).toBe(true);
      expect((document.getElementById('mt-bill-detected') as HTMLElement).hidden).toBe(false);
      const txt = document.getElementById('mt-bill-detected-value')!.textContent;
      if (locale === 'fr') expect(txt).toBeTruthy(); // billRangeLabel du dépôt
      else expect(txt).toBe(attendu);
    },
  );

  it('montant exact vidé : le <select> réapparaît', () => {
    const { s } = installer();
    set('mt-facture-hiver', '1200');
    s.syncBillRangeFromExact();
    set('mt-facture-hiver', '');
    s.syncBillRangeFromExact();
    expect((document.getElementById('mt-bill-wrap') as HTMLElement).hidden).toBe(false);
    expect((document.getElementById('mt-bill-detected') as HTMLElement).hidden).toBe(true);
  });
});

describe('sélections — Document injecté (≠ global)', () => {
  it('les cartes se câblent et se peignent dans le Document injecté, pas dans le global', () => {
    monter();
    const avant = document.body.innerHTML;
    const autre = document.implementation.createHTMLDocument('autre');
    autre.body.innerHTML = document.body.innerHTML;
    const ctx = creerContexte(creerDom(autre), creerEtat(null, 'en'), {
      locale: 'en', langueBasculable: false, formatNombre: String,
    });
    const calc = vi.fn(() => true);
    ctx.crochets.installer('computeEstimate', calc);
    ctx.crochets.installer('markDataEntered', () => {});
    ctx.crochets.installer('saveWizardState', () => {});
    const s = installerSelections(ctx);
    s.brancherVisiteOccupationEquipements();
    s.brancherGroupes();
    const btn = autre.querySelectorAll<HTMLElement>('.mt-tension')[1];
    btn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(ctx.etat.tension).toBe('mt');
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    expect(calc).toHaveBeenCalledTimes(1);
    expect(autre.querySelectorAll('[data-occ-line]')).toHaveLength(3);
    // clic sur le bouton du Document global : aucun effet sur l'état
    document.querySelectorAll<HTMLElement>('.mt-tension')[0].dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(ctx.etat.tension).toBe('mt');
    expect(document.body.innerHTML).toBe(avant);
  });
});
