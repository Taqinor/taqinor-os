// L-ECO (ordre fondateur, 24/08/2026) — sous le graphe « Sur une journée », la
// page doit dire ce que la courbe VAUT : économies du jour type affiché (qui
// changent avec la puce saison ET la puce de profil), du mois, de l'ANNÉE (qui
// ne change PAS avec la saison) et retour sur investissement.
//
// LA GARANTIE QUE CES TESTS PROTÈGENT : la page ne calcule AUCUNE économie.
// Toutes les combinaisons sont rendues par le serveur
// (`apps/ventes/economies_periodes.py` → clé `economies_periodes` du payload
// public) et le script ne fait que basculer `hidden`. `economiesPeriodes` est
// le parseur PUR — `null` sur une clé absente/malformée, jamais un chiffre de
// repli.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { economiesPeriodes, varianteDuProfil } from '../src/lib/economiesPeriodes';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
const PAGE = read('../src/pages/proposition/[...token].astro').replace(/\r\n/g, '\n');
const CODE = PAGE
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');

const moisSerie = (base: number) =>
  Array.from({ length: 12 }, (_, i) => ({
    mois: i + 1,
    jours: 30,
    saison: i < 2 || i === 11 ? 'hiver' : i >= 5 && i <= 7 ? 'ete' : 'mi_saison',
    mad: base + i,
    jour_mad: 10 + i,
  }));

const variante = (base: number, roi: number | null = 7.2) => ({
  annuel_mad: base * 12,
  mois: moisSerie(base),
  saisons: {
    hiver: { mad: 900, jours: 90, nb_mois: 3, jour_mad: 10, mois_moyen_mad: 300 },
    mi_saison: { mad: 1800, jours: 180, nb_mois: 6, jour_mad: 10, mois_moyen_mad: 300 },
    ete: { mad: 1200, jours: 90, nb_mois: 3, jour_mad: 13.33, mois_moyen_mad: 400 },
  },
  ...(roi === null ? {} : { retour_investissement_ans: roi }),
});

const PAYLOAD = {
  economies_periodes: {
    devise: 'MAD',
    estimation: false,
    sans: variante(300, 7.2),
    avec: variante(400, 9.8),
    profils: [
      { occupation: 'presence_jour', est_profil_reel: true, sans: variante(300, null), avec: variante(400, null) },
      { occupation: 'absence_jour', est_profil_reel: false, sans: variante(250, null) },
    ],
  },
};

describe('economiesPeriodes — parseur PUR, chiffres SERVEUR', () => {
  it('null quand la clé est absente ou malformée', () => {
    expect(economiesPeriodes({})).toBeNull();
    expect(economiesPeriodes({ economies_periodes: null })).toBeNull();
    expect(economiesPeriodes({ economies_periodes: {} })).toBeNull();
    expect(economiesPeriodes({ economies_periodes: { sans: {} } })).toBeNull();
    expect(economiesPeriodes(null)).toBeNull();
    expect(economiesPeriodes('texte')).toBeNull();
  });

  it('null quand la série mensuelle n’a pas douze mois', () => {
    const tronque = { economies_periodes: { sans: { annuel_mad: 100, mois: moisSerie(10).slice(0, 5) } } };
    expect(economiesPeriodes(tronque)).toBeNull();
  });

  it('lit les valeurs TELLES QUELLES, sans les retoucher', () => {
    const bloc = economiesPeriodes(PAYLOAD)!;
    expect(bloc.sans.annuelMad).toBe(3600);
    expect(bloc.sans.mois).toHaveLength(12);
    expect(bloc.sans.mois[0].mad).toBe(300);
    expect(bloc.sans.saisons.ete.moisMoyenMad).toBe(400);
    expect(bloc.sans.saisons.ete.jourMad).toBe(13.33);
    expect(bloc.avec!.annuelMad).toBe(4800);
    expect(bloc.devise).toBe('MAD');
  });

  it('un retour sur investissement absent, nul ou négatif est `null` — jamais « 0 an »', () => {
    for (const roi of [undefined, null, 0, -2, 'sept']) {
      const p = { economies_periodes: { sans: { ...variante(300, null), retour_investissement_ans: roi } } };
      expect(economiesPeriodes(p)!.sans.retourInvestissementAns).toBeNull();
    }
    expect(economiesPeriodes(PAYLOAD)!.sans.retourInvestissementAns).toBe(7.2);
  });

  it('`avec` reste `null` quand le serveur ne le sert pas (option non vendable)', () => {
    const sansAvec = { economies_periodes: { ...PAYLOAD.economies_periodes, avec: undefined } };
    const bloc = economiesPeriodes(sansAvec)!;
    expect(bloc.avec).toBeNull();
    expect(bloc.sans).not.toBeNull();
  });

  it('un profil sans série exploitable est ÉCARTÉ, jamais affiché avec les chiffres d’un autre', () => {
    const abime = {
      economies_periodes: {
        ...PAYLOAD.economies_periodes,
        profils: [...PAYLOAD.economies_periodes.profils, { occupation: 'presence_partielle' }],
      },
    };
    expect(economiesPeriodes(abime)!.profils.map((p) => p.occupancy))
      .toEqual(['presence_jour', 'absence_jour']);
  });

  it('varianteDuProfil ne mélange jamais deux comportements', () => {
    const bloc = economiesPeriodes(PAYLOAD)!;
    expect(varianteDuProfil(bloc, 'presence_jour', false)!.annuelMad).toBe(3600);
    expect(varianteDuProfil(bloc, 'absence_jour', false)!.annuelMad).toBe(3000);
    // Ce profil-là n'a pas de variante « avec » servie : on n'invente rien.
    expect(varianteDuProfil(bloc, 'absence_jour', true)).toBeNull();
    // Profil inconnu ⇒ on retombe sur le devis lui-même, jamais sur un voisin.
    expect(varianteDuProfil(bloc, 'inconnu', false)!.annuelMad).toBe(3600);
  });
});

describe('Source pin — le câblage RÉEL dans [...token].astro', () => {
  it('le bandeau existe et porte ses quatre périodes', () => {
    expect(CODE).toContain('data-eco-periodes');
    for (const cle of ['data-eco-valeur="jour"', 'data-eco-valeur="mois"', 'data-eco-valeur="annuel"']) {
      expect(CODE).toContain(cle);
    }
    expect(CODE).toContain('ecoRetourAns(variante)');
  });

  it('le total ANNUEL ne porte AUCUNE clé de saison (il ne peut donc pas en dépendre)', () => {
    const debut = CODE.indexOf('data-eco-valeur="annuel"');
    expect(debut).toBeGreaterThan(-1);
    const balise = CODE.slice(debut, CODE.indexOf('>', debut));
    expect(balise).not.toContain('data-eco-saison');
    expect(balise).toContain('data-eco-profil');
  });

  it('le jour type et le mois portent BIEN la saison ET le profil', () => {
    for (const cle of ['data-eco-valeur="jour"', 'data-eco-valeur="mois"']) {
      const debut = CODE.indexOf(cle);
      const bloc = CODE.slice(debut, debut + 400);
      expect(bloc).toContain('data-eco-saison');
      expect(bloc).toContain('data-eco-profil');
    }
  });

  it('AUCUNE arithmétique dans le script du bandeau', () => {
    const debut = CODE.indexOf("querySelector<HTMLElement>('[data-eco-periodes]')");
    expect(debut).toBeGreaterThan(-1);
    const script = CODE.slice(debut, CODE.indexOf('})();', debut));
    expect(script).not.toMatch(/[*/+-]\s*\d|\d\s*[*/+]|reduce\(|Math\./);
  });

  it('les libellés du bandeau sont traduits FR/EN/AR', () => {
    const debut = CODE.indexOf('data-eco-periodes');
    const bloc = CODE.slice(debut, CODE.indexOf('data-eco-periodes]', debut));
    for (const attr of ['data-fr=', 'data-en=', 'data-ar=']) {
      expect(bloc).toContain(attr);
    }
    expect(bloc).toContain('data-i18n');
  });
});
