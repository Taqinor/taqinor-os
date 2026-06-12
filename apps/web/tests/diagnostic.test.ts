import { describe, expect, it } from 'vitest';
import {
  canSubmit,
  nextStep,
  progressLabel,
  sunshineSignal,
  validateStep,
  type DiagnosticState,
} from '../src/lib/diagnostic';
import { qualifiesForCrm } from '../src/lib/billRange';

const empty: DiagnosticState = {
  billRange: '',
  roofType: '',
  city: '',
  fullName: '',
  phone: '',
  consent: false,
};

const complete: DiagnosticState = {
  billRange: '1500-3000',
  roofType: 'villa',
  city: 'Casablanca',
  fullName: 'Amina Benali',
  phone: '0661850410',
  consent: true,
};

describe('validateStep', () => {
  it('étape 1 : exige une tranche réelle et un type de toiture réel', () => {
    expect(validateStep(1, empty).ok).toBe(false);
    expect(validateStep(1, { ...empty, billRange: 'invalide', roofType: 'villa' }).ok).toBe(false);
    expect(validateStep(1, { ...empty, billRange: '1000-1500', roofType: 'villa' }).ok).toBe(true);
  });

  it('étape 2 : exige une ville', () => {
    expect(validateStep(2, empty).ok).toBe(false);
    expect(validateStep(2, { ...empty, city: 'Rabat' }).ok).toBe(true);
  });

  it('étape 3 : exige nom, téléphone marocain valide et consentement', () => {
    expect(validateStep(3, empty).ok).toBe(false);
    expect(validateStep(3, { ...complete, phone: '12345' }).ok).toBe(false);
    expect(validateStep(3, { ...complete, consent: false }).ok).toBe(false);
    expect(validateStep(3, complete).ok).toBe(true);
  });
});

describe('abandon en cours de parcours — rien ne part sans les 3 étapes', () => {
  it('étape 1 seule remplie : pas de soumission possible', () => {
    expect(canSubmit({ ...empty, billRange: '1500-3000', roofType: 'villa' })).toBe(false);
  });

  it('étapes 1 + 2 remplies, identité absente : pas de soumission possible', () => {
    expect(canSubmit({ ...empty, billRange: '1500-3000', roofType: 'villa', city: 'Fès' })).toBe(false);
  });

  it('consentement décoché au dernier moment : pas de soumission possible', () => {
    expect(canSubmit({ ...complete, consent: false })).toBe(false);
  });

  it('parcours complet : soumission possible', () => {
    expect(canSubmit(complete)).toBe(true);
  });
});

describe('nextStep — on ne saute jamais une étape invalide', () => {
  it("reste sur l'étape 1 tant qu'elle est invalide", () => {
    expect(nextStep(1, empty)).toBe(1);
  });
  it("avance 1 → 2 → 3 quand chaque étape est valide", () => {
    expect(nextStep(1, complete)).toBe(2);
    expect(nextStep(2, complete)).toBe(3);
    expect(nextStep(3, complete)).toBe(3);
  });
});

describe('parcours sous le seuil 1 000 MAD', () => {
  const sousSeuil: DiagnosticState = { ...complete, billRange: '800-1000' };

  it('le diagnostic accepte la tranche (l’utilisateur reçoit son extrait)', () => {
    expect(validateStep(1, sousSeuil).ok).toBe(true);
    expect(canSubmit(sousSeuil)).toBe(true);
  });

  it('mais la tranche reste non qualifiée pour le CRM (règle serveur intacte)', () => {
    expect(qualifiesForCrm('800-1000')).toBe(false);
    expect(qualifiesForCrm('lt800')).toBe(false);
    expect(qualifiesForCrm('1000-1500')).toBe(true);
  });
});

describe('progressLabel', () => {
  it('annonce la progression en français', () => {
    expect(progressLabel(1)).toBe('Étape 1 sur 3');
    expect(progressLabel(3)).toBe('Étape 3 sur 3');
  });
});

describe('sunshineSignal — signal préliminaire honnête', () => {
  it('vide tant que la ville est trop courte', () => {
    expect(sunshineSignal('')).toBe('');
    expect(sunshineSignal('A')).toBe('');
  });
  it('palier exceptionnel pour les villes les plus ensoleillées', () => {
    expect(sunshineSignal('Marrakech')).toContain('exceptionnel');
    expect(sunshineSignal('  OUARZAZATE ')).toContain('exceptionnel');
  });
  it('palier littoral pour Casablanca/Rabat (accents tolérés)', () => {
    expect(sunshineSignal('Casablanca')).toContain('littoral');
    expect(sunshineSignal('Salé')).toContain('littoral');
  });
  it('repli national pour toute autre commune', () => {
    expect(sunshineSignal('Khouribga')).toContain('2 800 à 3 400 h');
  });
});
