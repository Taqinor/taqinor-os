/* ============================================================================
   CALX253 — SÉRIALISER LA CONSOMMATION DE L'ATELIER DANS LE DOCUMENT.
   ----------------------------------------------------------------------------
   `serializeLayout` n'émettait aucune des six clés de consommation de `Ctx`
   (`consCurve`, `consAppliances`, `consSeasonal`, `consSummerFactor`,
   `consWinterFactor`, `consHandEdited` — `context.ts:313-329`) : le panneau
   « Affiner ma consommation » (`consumption.ts`, W68/W95) repartait donc à
   zéro à chaque session. Ce fichier prouve `serializeConsumption` (CALX251,
   contrat `$defs/consumption` de `roof_layout_v2.schema.json`) :

     * un `Ctx` VIERGE (rien touché dans le panneau « Affiner ») sérialise un
       document SANS clé `consumption` — jamais une courbe plate inventée ;
     * une courbe éditée à la main (`consHandEdited`) + des appareils
       sérialisent `courbe24.length === 24`, `appareils.length === 2` et
       `methode === 'courbe'` — la courbe éditée PRIME sur les appareils ;
     * des appareils SANS édition manuelle ⇒ `methode === 'appareils'` ;
     * un socle mensuel seul (`consDailyTarget`) ⇒ `methode === 'facture'` ;
     * la modulation saisonnière (W95) n'est publiée QUE lorsqu'elle est
       activée ET que les deux facteurs sont finis ;
     * le contrat partagé (`contract_samples/roof_layout_v2.schema.json`,
       CALX251) EST LU ici — pas un mock écrit à la main — pour que ce test
       casse tout seul si le vocabulaire diverge entre les deux moitiés.
   ========================================================================== */
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  serializeLayout,
  serializeConsumption,
  type SerializedConsumption,
} from './prefill';
import { type Ctx } from './context';
import { panDeTest, ctxAvecConsommation, appareilDeTest, racineDepot } from './harnaisAtelier';
import { type AreaRecord } from './types';

const zone = panDeTest;

const makeCtx = ctxAvecConsommation;

const appliance = appareilDeTest;

describe('CALX253 — serializeConsumption : un Ctx vierge ne publie rien', () => {
  it('aucune clé cons* touchée ⇒ pas de bloc `consumption`', () => {
    expect(serializeConsumption(makeCtx([zone('z1')]))).toEqual({});
  });

  it('serializeLayout complet : un Ctx vierge sérialise un document SANS clé `consumption`', () => {
    const layout = serializeLayout(makeCtx([zone('z1')]));
    expect('consumption' in layout).toBe(false);
  });

  it('un Ctx CONSTRUIT PARTIELLEMENT (cast, comme dans prefill.test.ts) ne casse jamais la sérialisation', () => {
    // Même construction que `makeCtx` de prefill.test.ts : AUCUN champ cons* posé.
    const areas = [zone('z1')];
    const ctxPartiel = {
      areas,
      activeAreaId: 'z1',
      vertices: areas[0].vertices,
      obstacles: areas[0].obstacles,
      roofType: areas[0].roofType,
      pitchDeg: areas[0].pitchDeg,
      facingAzimuthDeg: areas[0].facingAzimuthDeg,
      facingManual: false,
      neededPanels: areas[0].neededPanels,
      neededAuto: areas[0].neededAuto,
      layoutPlan: null,
      layoutOptimalCount: 0,
    } as unknown as Ctx;
    expect(() => serializeLayout(ctxPartiel)).not.toThrow();
    expect('consumption' in serializeLayout(ctxPartiel)).toBe(false);
  });
});

describe('CALX253 — methode DÉDUITE (jamais choisie)', () => {
  it('courbe éditée à la main + 2 appareils ⇒ courbe24 (24), appareils (2), methode = courbe', () => {
    const areas = [zone('z1')];
    const courbe = Array.from({ length: 24 }, (_, h) => (h >= 18 && h <= 22 ? 1.2 : 0.1));
    const ctx = makeCtx(areas, {
      consHandEdited: true,
      consCurve: courbe,
      consAppliances: [appliance('clim', 8), appliance('frigo', 1.5)],
    });
    const layout = serializeLayout(ctx);
    const consumption = layout.consumption as SerializedConsumption;
    expect(consumption).toBeDefined();
    expect(consumption.courbe24).toHaveLength(24);
    expect(consumption.courbe24).toEqual(courbe);
    expect(consumption.appareils).toHaveLength(2);
    expect(consumption.methode).toBe('courbe');
  });

  it('des appareils SANS édition manuelle ⇒ methode = appareils', () => {
    const ctx = makeCtx([zone('z1')], {
      consAppliances: [appliance('ev', 10)],
    });
    const { consumption } = serializeConsumption(ctx);
    expect(consumption?.methode).toBe('appareils');
    expect(consumption?.appareils).toHaveLength(1);
  });

  it('un socle mensuel SEUL (consDailyTarget > 0) ⇒ methode = facture', () => {
    const ctx = makeCtx([zone('z1')], { consDailyTarget: 12 });
    const { consumption } = serializeConsumption(ctx);
    expect(consumption?.methode).toBe('facture');
    expect(consumption?.appareils).toBeUndefined();
  });

  it('la courbe éditée PRIME sur des appareils présents', () => {
    const ctx = makeCtx([zone('z1')], {
      consHandEdited: true,
      consAppliances: [appliance('ev', 10)],
    });
    const { consumption } = serializeConsumption(ctx);
    expect(consumption?.methode).toBe('courbe');
  });
});

describe('CALX253 — W95, la modulation saisonnière est publiée seulement si activée', () => {
  it('consSeasonal actif + facteurs finis ⇒ `saisons` publié', () => {
    const ctx = makeCtx([zone('z1')], {
      consHandEdited: true,
      consSeasonal: true,
      consSummerFactor: 1.4,
      consWinterFactor: 0.8,
    });
    const { consumption } = serializeConsumption(ctx);
    expect(consumption?.saisons).toEqual({ ete: 1.4, hiver: 0.8 });
  });

  it('consSeasonal inactif ⇒ `saisons` absent, même si les facteurs existent', () => {
    const ctx = makeCtx([zone('z1')], { consHandEdited: true, consSeasonal: false });
    const { consumption } = serializeConsumption(ctx);
    expect(consumption?.saisons).toBeUndefined();
  });
});

describe('CALX253 — contrat partagé roof_layout_v2.schema.json (CALX251), lu — pas un mock', () => {

  function schema(): Record<string, unknown> {
    const chemin = join(
      racineDepot(), 'backend', 'django_core', 'apps', 'calepinage',
      'contract_samples', 'roof_layout_v2.schema.json',
    );
    if (!existsSync(chemin)) {
      throw new Error(`Schéma introuvable : ${chemin} — le contrat part EN PREMIER (PACT10, CALX251).`);
    }
    return JSON.parse(readFileSync(chemin, 'utf8'));
  }

  it('le vocabulaire `methode` du schéma est EXACTEMENT celui que serializeConsumption émet', () => {
    const defs = schema()['$defs'] as Record<string, { properties: Record<string, { enum?: string[] }> }>;
    expect(defs.consumption.properties.methode.enum).toEqual(['facture', 'courbe', 'appareils']);
  });

  it('`courbe24`/`methode`/`source` sont les seules clés OBLIGATOIRES du bloc', () => {
    const defs = schema()['$defs'] as Record<string, { required: string[] }>;
    expect([...defs.consumption.required].sort()).toEqual(['courbe24', 'methode', 'source']);
  });

  it('le vocabulaire `billing` d’un appareil est EXACTEMENT celui d’`ApplianceBilling`', () => {
    const defs = schema()['$defs'] as Record<string, { properties: Record<string, { enum?: string[] }> }>;
    expect(defs.consumptionAppliance.properties.billing.enum).toEqual(['onTop', 'inBill']);
  });

  it("`consumption` reste OPTIONNEL à la racine (additif — CALX84 même discipline), mais l'exemple complet (ACAL2) en porte un bloc conforme", () => {
    const s = schema() as {
      required?: string[];
      exemple: Record<string, unknown>;
      $defs: Record<string, { required: string[]; properties: Record<string, { enum?: string[] }> }>;
    };
    expect(s.required ?? []).not.toContain('consumption');
    const bloc = s.exemple.consumption as Record<string, unknown>;
    expect(bloc).toBeDefined();
    for (const cle of s.$defs.consumption.required) expect(cle in bloc).toBe(true);
    expect(s.$defs.consumption.properties.methode.enum).toContain(bloc.methode);
    expect(bloc.courbe24).toHaveLength(24);
  });
});
