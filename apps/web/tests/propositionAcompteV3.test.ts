// PREVIEW-V3 (16/09/2026) — ce que la page peut dire AVANT la signature.
//
// Trois helpers PURS, tous bâtis sur la même discipline que `resolveValidity`
// (le précédent maison « zéro chiffre inventé ») : clé absente, valeur
// illisible ou vide ⇒ rien n'est affiché, JAMAIS un chiffre de repli.
//   · resolveAcompte          — l'acompte réel du devis (tranche 1) ;
//   · resolveConditions       — les puces CGV que le PDF imprime ;
//   · promptConfirmationEmail — ne promettre l'e-mail que s'il partira ;
//   · mapAcceptResponseToUiState — le 403 `otp_required` cesse d'atterrir en
//     toutes lettres sous les yeux du client.
import { describe, expect, it } from 'vitest';

import {
  acompteMontantPourOption,
  mapAcceptResponseToUiState,
  promptConfirmationEmail,
  resolveAcompte,
  resolveConditions,
} from '../src/lib/proposition';

describe('resolveAcompte — l\'acompte réel, ou rien', () => {
  it('rend le pourcentage sans décimale inutile et le TTC du serveur', () => {
    const a = resolveAcompte({
      acompte: {
        pourcentage: '30.00', ttc: '34200.00', option: 'avec_batterie',
        montants: { sans_batterie: '23400.00', avec_batterie: '34200.00' },
      },
    } as never);
    expect(a).not.toBeNull();
    expect(a!.pct).toBe('30');
    expect(a!.ttc).toBe('34200.00');
    expect(a!.ttcNumber).toBe(34200);
    expect(a!.option).toBe('avec_batterie');
    expect(a!.montants).toEqual({ sans_batterie: 23400, avec_batterie: 34200 });
  });

  it('garde une décimale réelle, en virgule française', () => {
    const a = resolveAcompte({
      acompte: { pourcentage: '33.50', ttc: '1000.00' },
    } as never);
    expect(a!.pct).toBe('33,5');
  });

  it('rend null quand la clé est absente (backend antérieur)', () => {
    expect(resolveAcompte({} as never)).toBeNull();
    expect(resolveAcompte(null)).toBeNull();
    expect(resolveAcompte(undefined)).toBeNull();
  });

  it('rend null sur un montant nul, négatif ou illisible', () => {
    for (const ttc of ['0.00', '-10.00', '', 'trente', 'NaN']) {
      expect(resolveAcompte({
        acompte: { pourcentage: '30.00', ttc },
      } as never)).toBeNull();
    }
  });

  it('rend null sur un pourcentage absent ou nul — jamais un 30 % de repli', () => {
    for (const pct of [null, undefined, '', '0', 'x']) {
      expect(resolveAcompte({
        acompte: { pourcentage: pct as never, ttc: '3240.00' },
      } as never)).toBeNull();
    }
  });

  it('écarte une table de montants illisible sans perdre l’acompte lui-même', () => {
    // PREVIEW-V3-FIX — backend antérieur au correctif (ni `option` ni
    // `montants`), ou table malformée : l'acompte reste lisible, la table est
    // vide, et `acompteMontantPourOption` se taira plutôt que de deviner.
    for (const montants of [undefined, null, 'x', [], { sans_batterie: '0.00' },
      { autre_chose: '10.00' }]) {
      const a = resolveAcompte({
        acompte: { pourcentage: '30', ttc: '100.00', montants },
      } as never);
      expect(a!.ttcNumber).toBe(100);
      expect(a!.montants).toEqual({});
      expect(a!.option).toBeNull();
    }
  });
});

describe('acompteMontantPourOption — l’acompte de l’option COCHÉE (audit C1)', () => {
  const deuxOptions = resolveAcompte({
    acompte: {
      pourcentage: '30.00', ttc: '34200.00', option: 'avec_batterie',
      montants: { sans_batterie: '23400.00', avec_batterie: '34200.00' },
    },
  } as never);

  it('LE DÉFAUT C1 : cocher « sans batterie » ne montre plus l’acompte de l’AUTRE option', () => {
    expect(acompteMontantPourOption(deuxOptions, 'sans_batterie', true)).toBe(23400);
    expect(acompteMontantPourOption(deuxOptions, 'avec_batterie', true)).toBe(34200);
  });

  it('devis à option unique : le seul montant du devis, quelle que soit la clé', () => {
    const mono = resolveAcompte({
      acompte: {
        pourcentage: '30.00', ttc: '3240.00', option: '',
        montants: { sans_batterie: '3240.00' },
      },
    } as never);
    expect(acompteMontantPourOption(mono, 'sans_batterie', false)).toBe(3240);
    expect(acompteMontantPourOption(mono, 'avec_batterie', false)).toBe(3240);
  });

  it('backend antérieur (un seul `ttc` + `option`) : le montant UNIQUEMENT sur son option', () => {
    const ancien = resolveAcompte({
      acompte: { pourcentage: '30.00', ttc: '34200.00', option: 'avec_batterie' },
    } as never);
    expect(acompteMontantPourOption(ancien, 'avec_batterie', true)).toBe(34200);
    expect(acompteMontantPourOption(ancien, 'sans_batterie', true)).toBeNull();
  });

  it('sans acompte, sans option, ou option inconnue : rien — jamais un chiffre de repli', () => {
    expect(acompteMontantPourOption(null, 'sans_batterie', true)).toBeNull();
    expect(acompteMontantPourOption(deuxOptions, null, true)).toBeNull();
    expect(acompteMontantPourOption(undefined, 'avec_batterie', false)).toBeNull();
  });
});

describe('resolveConditions — les puces CGV du PDF', () => {
  it('rend les lignes telles quelles, détourées', () => {
    expect(resolveConditions({
      conditions: [' Acompte à la commande : 30% ', '60% à la réception du matériel'],
    } as never)).toEqual([
      'Acompte à la commande : 30%',
      '60% à la réception du matériel',
    ]);
  });

  it('rend [] quand la clé est absente ou mal formée (aucun lien mort)', () => {
    expect(resolveConditions({} as never)).toEqual([]);
    expect(resolveConditions({ conditions: null } as never)).toEqual([]);
    expect(resolveConditions({ conditions: 'texte' } as never)).toEqual([]);
    expect(resolveConditions(null)).toEqual([]);
  });

  it('écarte les entrées vides ou non textuelles', () => {
    expect(resolveConditions({
      conditions: ['Vraie ligne', '', '   ', 42, null],
    } as never)).toEqual(['Vraie ligne']);
  });
});

describe('promptConfirmationEmail — ne promettre que ce qui partira', () => {
  it('vrai seulement sur `true` explicite', () => {
    expect(promptConfirmationEmail({ confirmation_email: true } as never)).toBe(true);
  });

  it('faux quand absent, null ou false (loi 31-08 art. 32)', () => {
    expect(promptConfirmationEmail({} as never)).toBe(false);
    expect(promptConfirmationEmail({ confirmation_email: null } as never)).toBe(false);
    expect(promptConfirmationEmail({ confirmation_email: false } as never)).toBe(false);
    expect(promptConfirmationEmail(null)).toBe(false);
  });
});

describe('mapAcceptResponseToUiState — le 403 otp_required a enfin un écran', () => {
  it('200 → ok', () => {
    expect(mapAcceptResponseToUiState(200, null)).toEqual({ kind: 'ok' });
  });

  it('403 otp_required → bloc OTP de LECTURE (réglage par lien)', () => {
    expect(mapAcceptResponseToUiState(403, 'otp_required')).toEqual({ kind: 'otp-lecture' });
  });

  it('400 + message OTP e-signature → bloc OTP de signature', () => {
    const etat = mapAcceptResponseToUiState(
      400,
      'Un code de confirmation est requis. Demandez-le via le bouton « Envoyer le code ».',
    );
    expect(etat).toEqual({ kind: 'otp-esign', incorrect: false });
  });

  it('distingue le code INCORRECT (on ne redemande pas un code à chaque échec)', () => {
    const etat = mapAcceptResponseToUiState(
      400,
      'Code de confirmation incorrect. Vérifiez le code reçu et réessayez.',
    );
    expect(etat).toEqual({ kind: 'otp-esign', incorrect: true });
  });

  it('ne montre JAMAIS le littéral machine au client, même hors 403', () => {
    const etat = mapAcceptResponseToUiState(400, 'otp_required');
    expect(etat.kind).toBe('error');
    expect((etat as { message: string }).message).not.toContain('otp_required');
  });

  it('relaie un vrai message d\'erreur backend tel quel', () => {
    expect(mapAcceptResponseToUiState(400, 'Votre nom est requis pour signer la proposition.'))
      .toEqual({ kind: 'error', message: 'Votre nom est requis pour signer la proposition.' });
  });

  it('erreur sans detail → message lisible, jamais une chaîne vide', () => {
    const etat = mapAcceptResponseToUiState(500, '');
    expect(etat.kind).toBe('error');
    expect((etat as { message: string }).message.length).toBeGreaterThan(10);
  });
});
