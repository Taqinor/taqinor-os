// P2-C (ordre fondateur 25/08/2026, soir) — « add more than just 2 batteries
// in the web page battery option ; extra batteries might add extra panels
// with extra cost, that is still fine. » Sélecteur de paliers de capacité
// batterie sur la carte « Avec batterie » (section #options) de la page
// publique /proposition/<token>.
//
// `paliersBatterie`/`palierBatterieRetenu` sont les parseurs PURS (même
// discipline « zéro chiffre inventé » que `storageSweepInfo`,
// storageSweepBatt2.test.ts) : liste vide sur une clé absente/malformée,
// chaque champ sanitisé individuellement (`null` plutôt qu'un défaut
// fabriqué). Les tests « Source pin » pincent le câblage réel dans
// [...token].astro (le code, commentaires retirés — un commentaire ne doit
// jamais faire passer un test) : la sélection reste une EXPLORATION qui ne
// touche jamais le prix officiel ni la signature, et réutilise le flux
// existant « Demander une modification » plutôt qu'un canal inventé.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { paliersBatterie, palierBatterieRetenu } from '../src/lib/proposition';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
const PAGE = read('../src/pages/proposition/[...token].astro').replace(/\r\n/g, '\n');
const CODE = PAGE
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');

describe('paliersBatterie — paliers de capacité batterie, client-safe', () => {
  it('liste vide quand `paliers_batterie` est absent', () => {
    expect(paliersBatterie({})).toEqual([]);
  });

  it('liste vide quand `paliers_batterie` est null ou n’est pas un tableau', () => {
    expect(paliersBatterie({ paliers_batterie: null })).toEqual([]);
    expect(paliersBatterie({ paliers_batterie: 'oups' as unknown as never })).toEqual([]);
  });

  it('lit un palier complet (contrat fondateur du 25/08/2026)', () => {
    const r = paliersBatterie({
      paliers_batterie: [
        {
          capacite_kwh: 15.0,
          nb_batteries_5: 1,
          nb_batteries_10: 1,
          nb_panneaux: 26,
          puissance_kwc: 18.46,
          prix_ttc: 148655.0,
          economies_annuelles: 28088.0,
          payback_annees: 5.5,
          remplissage_ok: true,
          retenu: true,
        },
      ],
    });
    expect(r).toEqual([
      {
        capaciteKwh: 15,
        nbBatteries5: 1,
        nbBatteries10: 1,
        nbPanneaux: 26,
        puissanceKwc: 18.46,
        prixTtc: 148655,
        economiesAnnuelles: 28088,
        paybackAnnees: 5.5,
        remplissageOk: true,
        retenu: true,
      },
    ]);
  });

  it('un palier sans capacite_kwh lisible est omis (rien à nommer sur sa pilule)', () => {
    const r = paliersBatterie({
      paliers_batterie: [
        { capacite_kwh: 15, nb_panneaux: 26 },
        { nb_panneaux: 30 },
        { capacite_kwh: null, nb_panneaux: 32 },
        { capacite_kwh: Number.NaN, nb_panneaux: 34 },
      ],
    });
    expect(r).toHaveLength(1);
    expect(r[0].capaciteKwh).toBe(15);
  });

  it('un nombre non fini (NaN, chaîne) devient null plutôt qu’un chiffre inventé', () => {
    const r = paliersBatterie({
      paliers_batterie: [
        { capacite_kwh: 15, nb_panneaux: 'trente' as unknown as number, prix_ttc: Number.NaN },
      ],
    });
    expect(r[0].nbPanneaux).toBeNull();
    expect(r[0].prixTtc).toBeNull();
  });

  it('remplissage_ok absent ou vrai ⇒ palier servable ; seul `false` explicite désactive', () => {
    const r = paliersBatterie({
      paliers_batterie: [
        { capacite_kwh: 15 },
        { capacite_kwh: 20, remplissage_ok: true },
        { capacite_kwh: 25, remplissage_ok: false },
      ],
    });
    expect(r.map((t) => t.remplissageOk)).toEqual([true, true, false]);
  });

  it('retenu absent ou faux ⇒ palier non retenu ; seul `true` explicite le marque', () => {
    const r = paliersBatterie({
      paliers_batterie: [
        { capacite_kwh: 15 },
        { capacite_kwh: 20, retenu: false },
        { capacite_kwh: 25, retenu: true },
      ],
    });
    expect(r.map((t) => t.retenu)).toEqual([false, false, true]);
  });

  it('une entrée illisible (pas un objet) est ignorée sans planter le tableau entier', () => {
    const r = paliersBatterie({
      paliers_batterie: [null, 'oups', { capacite_kwh: 15 }] as unknown as never,
    });
    expect(r).toHaveLength(1);
    expect(r[0].capaciteKwh).toBe(15);
  });
});

describe('palierBatterieRetenu', () => {
  it('renvoie le palier marqué retenu', () => {
    const paliers = paliersBatterie({
      paliers_batterie: [
        { capacite_kwh: 15, retenu: false },
        { capacite_kwh: 20, retenu: true },
      ],
    });
    expect(palierBatterieRetenu(paliers)?.capaciteKwh).toBe(20);
  });

  it('renvoie null quand aucun palier n’est marqué retenu', () => {
    const paliers = paliersBatterie({
      paliers_batterie: [{ capacite_kwh: 15 }, { capacite_kwh: 20 }],
    });
    expect(palierBatterieRetenu(paliers)).toBeNull();
  });

  it('renvoie null sur une liste vide', () => {
    expect(palierBatterieRetenu([])).toBeNull();
  });
});

describe('[...token].astro — le sélecteur de paliers vit sur la carte « Avec batterie »', () => {
  it('lit le contrat via les parseurs purs, jamais un second calcul dans la page', () => {
    expect(CODE).toContain("const battTiers: PalierBatterie[] = ok ? paliersBatterie(data!) : [];");
    expect(CODE).toContain('const battTierRetenu = palierBatterieRetenu(battTiers);');
  });

  it('le sélecteur ne rend rien hors de la carte « avec_batterie », et seulement si des paliers existent', () => {
    expect(CODE).toContain("{opt === 'avec_batterie' && battTiers.length > 0 && (");
  });

  it('le palier retenu affiche les chiffres du devis réel, jamais une seconde source de vérité', () => {
    expect(CODE).toContain('const battTierRealPanneaux = dimAvec?.nbPanneaux ?? nbPanneaux;');
    expect(CODE).toContain('const battTierRealPrix = ok && hasRealPrice(data!, \'avec_batterie\') ? optionTtc(data!, \'avec_batterie\') : null;');
    expect(CODE).toContain('panneaux: t.retenu ? battTierRealPanneaux : t.nbPanneaux,');
  });

  it('un palier désactivé (remplissage_ok=false) porte l’attribut disabled — jamais sélectionnable', () => {
    expect(CODE).toContain('disabled={!t.remplissageOk}');
  });
});

describe('[...token].astro — l’exploration ne touche jamais le prix officiel ni la signature', () => {
  it('le script de sélection ne fait que du formatage (formatMAD/formatNumber), aucune arithmétique', () => {
    expect(CODE).toContain('function setupBatteryTierSelector(): void {');
    expect(CODE).toContain("const wrap = document.querySelector<HTMLElement>('[data-batt-tiers]');");
  });

  it('« Cette configuration vous intéresse ? » réutilise le flux EXISTANT « Demander une modification »', () => {
    // Jamais un second endpoint : le bouton déclenche le vrai clic du bouton
    // de type « batterie » déjà câblé par setupRevisionForm (WJ54), au lieu
    // de dupliquer sa logique ou d'inventer un nouveau canal.
    expect(CODE).toContain('const battKindBtn = revisionSection?.querySelector<HTMLButtonElement>(\'[data-revision-kind="batterie"]\');');
    expect(CODE).toContain('battKindBtn?.click();');
    expect(CODE).not.toContain('/api/proposition-batterie');
  });

  it('le message pré-rempli mentionne la capacité et le nombre de panneaux, jamais un chiffre inventé', () => {
    expect(CODE).toContain("detailEl.value = `Je souhaite l'option avec ${formatNumber(kwh, 1)} kWh de batterie${panneauxTxt}`;");
  });
});
