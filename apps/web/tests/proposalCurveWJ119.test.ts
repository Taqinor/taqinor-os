// WJ119 — Courbe journalière RÉELLE Maroc + par MODE. Preuve que la courbe
// cesse d'être la même pour une villa (résidentiel) et une usine (industriel) :
// silhouette soirée-dominante (BASELINE_SHAPE portée de applianceConsumption.ts)
// pour le résidentiel, variantes été/Ramadan, et profils dédiés par mode
// (industriel équipes, commercial, agricole pompage). Jamais un chiffre inventé
// — chaque forme est un profil normalisé [0,1], jamais présenté comme mesuré.
import { describe, expect, it } from 'vitest';
import {
  consumptionProfile,
  resolveProposalCurveMode,
  renderYearCurve,
  type ProposalCurveMode,
} from '../src/lib/proposalCurve';
// CJ1 — la base résidentielle n'est plus l'unique BASELINE_SHAPE mais l'une des
// TROIS silhouettes d'occupation ; le repli sans drapeau serveur est
// « présence partielle ».
import { OCCUPANCY_SHAPES } from '../src/lib/dayProfiles';

const HOURS = Array.from({ length: 17 }, (_, i) => 5 + i); // 5..21 (fenêtre du graphe)

describe('WJ119 — resolveProposalCurveMode (champ backend ProposalQuote.inst_type)', () => {
  it('valeurs RÉELLES observées aujourd’hui (builder.py) : Résidentielle/Agricole/combiné', () => {
    expect(resolveProposalCurveMode('Résidentielle')).toBe('residentiel');
    expect(resolveProposalCurveMode('Agricole')).toBe('agricole');
    // Le backend ne distingue pas encore industriel de commercial (une seule
    // catégorie combinée) — retombe sur 'industriel', son mode interne réel.
    expect(resolveProposalCurveMode('Industrielle / Commerciale')).toBe('industriel');
  });

  it('clés machine minuscules (future-proof) reconnues', () => {
    expect(resolveProposalCurveMode('residentiel')).toBe('residentiel');
    expect(resolveProposalCurveMode('industriel')).toBe('industriel');
    expect(resolveProposalCurveMode('commercial')).toBe('commercial');
    expect(resolveProposalCurveMode('agricole')).toBe('agricole');
    // 'professionnel' = nom interne du mode industriel côté simulateur (mon-toit.astro).
    expect(resolveProposalCurveMode('professionnel')).toBe('industriel');
  });

  it('absent/vide/inconnu → residentiel (repli honnête, jamais un mode fabriqué)', () => {
    expect(resolveProposalCurveMode(null)).toBe('residentiel');
    expect(resolveProposalCurveMode(undefined)).toBe('residentiel');
    expect(resolveProposalCurveMode('')).toBe('residentiel');
    expect(resolveProposalCurveMode('   ')).toBe('residentiel');
    expect(resolveProposalCurveMode('Autre chose')).toBe('residentiel');
  });
});

describe('WJ119/CJ1 — résidentiel/normal porte une silhouette marocaine soirée-dominante', () => {
  it('19h-21h STRICTEMENT dominant sur la mi-journée (12h-16h)', () => {
    const evening = [19, 20, 21].map((h) => consumptionProfile(h));
    const midday = [12, 13, 14, 15, 16].map((h) => consumptionProfile(h));
    const minEvening = Math.min(...evening);
    const maxMidday = Math.max(...midday);
    expect(minEvening).toBeGreaterThan(maxMidday);
  });

  it('19h-21h concentre une part significative de l’énergie de la fenêtre 5h-21h (fenêtre de pointe ONEE)', () => {
    // Somme sur les heures ENTIÈRES 5..21 des poids BRUTS (avant normalisation)
    // de la silhouette de repli — importée ici directement pour vérifier le
    // PORTAGE, pas une nouvelle donnée inventée. L'invariant vaut pour LES TROIS
    // silhouettes : la pointe du soir est un fait de réseau marocain, pas une
    // caractéristique d'un profil particulier.
    for (const shape of Object.values(OCCUPANCY_SHAPES)) {
      const windowSum = HOURS.reduce((acc, h) => acc + shape[h], 0);
      const eveningSum = shape[19] + shape[20] + shape[21];
      expect(eveningSum / windowSum).toBeGreaterThan(0.25);
    }
  });

  // CJ1 — les TROIS silhouettes existent et se DISTINGUENT là où c'est le sujet :
  // la journée. Un foyer absent creuse, un foyer présent tient un plateau.
  it('les trois occupations diffèrent RÉELLEMENT en journée (10h-16h)', () => {
    const midday = (occupancy: 'presence_jour' | 'absence_jour' | 'presence_partielle') =>
      [10, 11, 12, 13, 14, 15, 16]
        .map((h) => consumptionProfile(h, { mode: 'residentiel', occupancy }))
        .reduce((a, b) => a + b, 0);
    expect(midday('presence_jour')).toBeGreaterThan(midday('presence_partielle'));
    expect(midday('presence_partielle')).toBeGreaterThan(midday('absence_jour'));
  });

  it('« absent en journée » garde une pointe du matin (départ) que « présent » n’a pas', () => {
    const morningAbsent = consumptionProfile(7, { mode: 'residentiel', occupancy: 'absence_jour' });
    const middayAbsent = consumptionProfile(12, { mode: 'residentiel', occupancy: 'absence_jour' });
    expect(morningAbsent).toBeGreaterThan(middayAbsent);
    const morningPresent = consumptionProfile(7, { mode: 'residentiel', occupancy: 'presence_jour' });
    const middayPresent = consumptionProfile(12, { mode: 'residentiel', occupancy: 'presence_jour' });
    expect(morningPresent).toBeLessThan(middayPresent);
  });

  it('toutes les heures restent dans [0,1] (profil normalisé, jamais un chiffre)', () => {
    for (const h of HOURS) {
      const v = consumptionProfile(h, { mode: 'residentiel' });
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
  });
});

describe('WJ119/CJ1 — variante été (résidentiel) : +50 % sur 13h-21h (climatisation)', () => {
  // CJ1 — la fenêtre s'arrêtait à 18h et coupait la moitié du phénomène : les
  // guides d'usage de la clim ET la fenêtre de pointe ONEE (18h-23h l'été)
  // situent la sollicitation des splits l'après-midi ET en début de soirée.
  // Comme la courbe est normalisée (comportement historique documenté), l'effet
  // se lit en PART DE JOURNÉE, pas en valeur absolue d'une heure — on teste
  // donc le déplacement RÉEL, exactement comme pour l'archétype commercial.
  it('la part de la journée qui tombe entre 13h et 21h augmente en été', () => {
    const share = (variant: 'normal' | 'ete') => {
      const all = Array.from({ length: 24 }, (_, h) =>
        consumptionProfile(h, { mode: 'residentiel', variant }),
      );
      const total = all.reduce((a, b) => a + b, 0);
      const window = all.slice(13, 22).reduce((a, b) => a + b, 0);
      return window / total;
    };
    expect(share('ete')).toBeGreaterThan(share('normal'));
  });

  it('l’après-midi climatisé monte RELATIVEMENT au matin non climatisé', () => {
    const ratio = (variant: 'normal' | 'ete') =>
      consumptionProfile(15, { mode: 'residentiel', variant }) /
      consumptionProfile(10, { mode: 'residentiel', variant });
    expect(ratio('ete')).toBeGreaterThan(ratio('normal'));
  });

  it('la soirée reste dans la fenêtre boostée (l’ancienne coupure à 18h est levée)', () => {
    const ratio = (variant: 'normal' | 'ete') =>
      consumptionProfile(21, { mode: 'residentiel', variant }) /
      consumptionProfile(10, { mode: 'residentiel', variant });
    expect(ratio('ete')).toBeGreaterThan(ratio('normal'));
  });

  it('reste borné [0,1] même après le boost (renormalisation interne)', () => {
    for (const h of HOURS) {
      expect(consumptionProfile(h, { mode: 'residentiel', variant: 'ete' })).toBeLessThanOrEqual(1);
    }
  });
});

describe('WJ119/CJ1 — variante Ramadan (résidentiel) : jour réduit, pic iftar, bosse suhoor', () => {
  // CJ1 — sans fenêtre calculée, le module retombe sur RAMADAN_FALLBACK_WINDOW
  // (imsak 5h30 / iftar 18h30, valeurs médianes d'un Ramadan à Casablanca) :
  // suhoor sur 3h-4h, jeûne 6h-17h, iftar à 18h. Les magnitudes (×2.5 / ×0.65 /
  // ×1.8) n'ont PAS changé — seules les heures sont devenues calculables.
  it('bosse suhoor (2 h avant l’imsak) : nettement au-dessus du creux nocturne environnant', () => {
    const suhoor = consumptionProfile(4, { mode: 'residentiel', variant: 'ramadan' });
    const before = consumptionProfile(2, { mode: 'residentiel', variant: 'ramadan' });
    const after = consumptionProfile(6, { mode: 'residentiel', variant: 'ramadan' });
    expect(suhoor).toBeGreaterThan(before);
    expect(suhoor).toBeGreaterThan(after);
    // Et strictement au-dessus de ce que le profil NORMAL montrait à la même heure
    // (la bosse suhoor n'existe QUE pendant le Ramadan).
    expect(suhoor).toBeGreaterThan(consumptionProfile(4, { mode: 'residentiel', variant: 'normal' }));
  });

  it('pic iftar (coucher du soleil) : devient le maximum de la journée', () => {
    const iftarHour = 18; // repli documenté : coucher médian 18h30 → heure 18
    const iftar = consumptionProfile(iftarHour, { mode: 'residentiel', variant: 'ramadan' });
    for (let h = 0; h < 24; h++) {
      if (h === iftarHour) continue;
      expect(iftar).toBeGreaterThanOrEqual(consumptionProfile(h, { mode: 'residentiel', variant: 'ramadan' }));
    }
  });

  it('journée de jeûne (heures pleines imsak→iftar) réduite par rapport au profil normal', () => {
    for (let h = 6; h <= 17; h++) {
      const normal = consumptionProfile(h, { mode: 'residentiel', variant: 'normal' });
      const ramadan = consumptionProfile(h, { mode: 'residentiel', variant: 'ramadan' });
      if (normal > 0) expect(ramadan).toBeLessThan(normal);
    }
  });

  // CJ1 — LE VRAI CORRECTIF : les heures SUIVENT la fenêtre fournie. Le codage
  // en dur « suhoor 3h-5h / iftar 19h » n'était juste que pour un Ramadan d'été
  // — or le Ramadan tombe en hiver jusqu'en 2033.
  it('une fenêtre PLUS TARDIVE déplace réellement le pic d’iftar (heures calculées, pas codées)', () => {
    const late = { imsakHour: 4.5, iftarHour: 20.5 };
    const at20 = consumptionProfile(20, { mode: 'residentiel', variant: 'ramadan', ramadan: late });
    const at18 = consumptionProfile(18, { mode: 'residentiel', variant: 'ramadan', ramadan: late });
    // 20h porte le ×1.8 ; 18h est retombé dans la journée de jeûne (×0.65).
    expect(at20).toBeGreaterThan(at18);
    const normal18 = consumptionProfile(18, { mode: 'residentiel', variant: 'normal' });
    expect(at18).toBeLessThan(normal18);
    // …et le suhoor a suivi lui aussi (2 h avant 4h30 → heures 2 et 3).
    const suhoorLate = consumptionProfile(2, { mode: 'residentiel', variant: 'ramadan', ramadan: late });
    expect(suhoorLate).toBeGreaterThan(consumptionProfile(2, { mode: 'residentiel', variant: 'normal' }));
  });
});

describe('WJ119 — industriel : profil de régime d’équipes (1x8/2x8/3x8)', () => {
  it('3x8 ≈ plat (production continue, quasi identique jour et nuit)', () => {
    const dayShift = consumptionProfile(10, { mode: 'industriel', industrialShift: '3x8' });
    const nightShift = consumptionProfile(2, { mode: 'industriel', industrialShift: '3x8' });
    expect(dayShift).toBeCloseTo(nightShift, 9);
    expect(dayShift).toBeCloseTo(1, 9);
  });

  it('1x8 : poste de jour actif, nuit nettement plus basse', () => {
    const poste = consumptionProfile(10, { mode: 'industriel', industrialShift: '1x8' });
    const nuit = consumptionProfile(2, { mode: 'industriel', industrialShift: '1x8' });
    expect(poste).toBeGreaterThan(nuit);
    expect(nuit).toBeGreaterThan(0); // jamais zéro (veille/éclairage de sécurité)
  });

  it('2x8 : plateau 06h-22h plus large que 1x8 (deux équipes)', () => {
    // 18h est hors du poste unique 1x8 (8h-16h) mais dans le plateau 2x8 (6h-22h).
    const shift1x8 = consumptionProfile(18, { mode: 'industriel', industrialShift: '1x8' });
    const shift2x8 = consumptionProfile(18, { mode: 'industriel', industrialShift: '2x8' });
    expect(shift2x8).toBeGreaterThan(shift1x8);
  });

  it('repli 1x8 par défaut quand aucun régime n’est précisé (ESTIMATION documentée)', () => {
    expect(consumptionProfile(10, { mode: 'industriel' })).toBe(
      consumptionProfile(10, { mode: 'industriel', industrialShift: '1x8' }),
    );
  });

  it('été/Ramadan sont ignorés pour un mode industriel (équipes fixes)', () => {
    const normal = consumptionProfile(14, { mode: 'industriel', variant: 'normal' });
    const ete = consumptionProfile(14, { mode: 'industriel', variant: 'ete' });
    const ramadan = consumptionProfile(14, { mode: 'industriel', variant: 'ramadan' });
    expect(ete).toBe(normal);
    expect(ramadan).toBe(normal);
  });
});

describe('WJ119 — commercial : UN archétype journée générique (pas de table par catégorie)', () => {
  it('heures d’ouverture (9h-19h) nettement au-dessus des heures fermées', () => {
    const open = consumptionProfile(12, { mode: 'commercial' });
    const closed = consumptionProfile(2, { mode: 'commercial' });
    expect(open).toBeGreaterThan(closed);
    expect(closed).toBeGreaterThan(0); // jamais zéro (petit socle hors ouverture)
  });

  it('la variante été déplace la part vers l’après-midi (climatisation en boutique)', () => {
    // L'archétype commercial est plat à 1.0 sur les heures d'ouverture ; comme la
    // courbe est normalisée à son propre maximum (comportement documenté, hérité de
    // l'ancienne gaussienne), un boost de l'après-midi ramène simplement ce nouveau
    // maximum à 1.0 — l'effet ÉTÉ est donc visible aux ÉPAULES (le matin/le soir
    // baissent RELATIVEMENT à l'après-midi climatisé), pas au pic lui-même. On teste
    // ce déplacement réel : le ratio après-midi (15h, boosté) / matin (10h, non
    // boosté) augmente en été.
    const normalRatio =
      consumptionProfile(15, { mode: 'commercial', variant: 'normal' }) /
      consumptionProfile(10, { mode: 'commercial', variant: 'normal' });
    const eteRatio =
      consumptionProfile(15, { mode: 'commercial', variant: 'ete' }) /
      consumptionProfile(10, { mode: 'commercial', variant: 'ete' });
    expect(eteRatio).toBeGreaterThan(normalRatio);
  });
});

describe('WJ119 — agricole : fenêtre de pompage = heures de jour (solaire direct, sans batterie)', () => {
  it('plate en journée, NULLE la nuit (aucune énergie stockée pour pomper après le coucher)', () => {
    expect(consumptionProfile(2, { mode: 'agricole' })).toBe(0);
    expect(consumptionProfile(23, { mode: 'agricole' })).toBe(0);
    expect(consumptionProfile(12, { mode: 'agricole' })).toBeCloseTo(1, 9);
    expect(consumptionProfile(9, { mode: 'agricole' })).toBeCloseTo(1, 9);
  });

  it('été/Ramadan sont ignorés (le pompage suit le soleil, pas la clim ni le jeûne)', () => {
    const normal = consumptionProfile(12, { mode: 'agricole', variant: 'normal' });
    const ete = consumptionProfile(12, { mode: 'agricole', variant: 'ete' });
    expect(ete).toBe(normal);
  });
});

describe('WJ119 — renderYearCurve accepte le mode/variante sans rien casser', () => {
  const modes: ProposalCurveMode[] = ['residentiel', 'industriel', 'commercial', 'agricole'];

  it('produit un SVG valide non vide pour chaque mode', () => {
    for (const mode of modes) {
      const out = renderYearCurve(10000, undefined, 'fr', { mode });
      expect(out.svg).toContain('<svg');
      expect(out.svg.length).toBeGreaterThan(100);
    }
  });

  it('rétro-compatible : appel à 3 arguments (sans options) toujours valide', () => {
    const out = renderYearCurve(10000, undefined, 'en');
    expect(out.svg).toContain('<svg');
    expect(out.hasRealScale).toBe(true);
  });

  it('la courbe de consommation (curve-cons-line) diffère entre résidentiel et industriel 3x8', () => {
    const res = renderYearCurve(10000, undefined, 'fr', { mode: 'residentiel' });
    const ind = renderYearCurve(10000, undefined, 'fr', { mode: 'industriel', industrialShift: '3x8' });
    const consPath = (svg: string) => svg.match(/class="curve-cons-line" d="([^"]+)"/)?.[1];
    expect(consPath(res.svg)).not.toBe(consPath(ind.svg));
  });
});
