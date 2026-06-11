import { describe, expect, it } from 'vitest';
import { determineRegime } from '../src/lib/regime';

describe('determineRegime — loi 82-21 / décret 2-25-100', () => {
  it('site isolé (non raccordé) → déclaration, quelle que soit la puissance', () => {
    expect(determineRegime({ powerKw: 3, gridConnected: false, voltage: 'BT' })).toBe('declaration');
    expect(determineRegime({ powerKw: 500, gridConnected: false, voltage: 'MT' })).toBe('declaration');
    expect(determineRegime({ powerKw: 10000, gridConnected: false, voltage: 'HT' })).toBe('declaration');
  });

  it('BT < 11 kW raccordé → déclaration', () => {
    expect(determineRegime({ powerKw: 3, gridConnected: true, voltage: 'BT' })).toBe('declaration');
    expect(determineRegime({ powerKw: 10.9, gridConnected: true, voltage: 'BT' })).toBe('declaration');
  });

  it('BT ≥ 11 kW → accord de raccordement (borne exacte)', () => {
    expect(determineRegime({ powerKw: 11, gridConnected: true, voltage: 'BT' })).toBe('accord');
    expect(determineRegime({ powerKw: 100, gridConnected: true, voltage: 'BT' })).toBe('accord');
  });

  it('MT sous 5 MW → accord de raccordement, même en petite puissance', () => {
    expect(determineRegime({ powerKw: 5, gridConnected: true, voltage: 'MT' })).toBe('accord');
    expect(determineRegime({ powerKw: 4999, gridConnected: true, voltage: 'MT' })).toBe('accord');
  });

  it('≥ 5 MW → autorisation (borne exacte, tous niveaux de tension)', () => {
    expect(determineRegime({ powerKw: 5000, gridConnected: true, voltage: 'MT' })).toBe('autorisation');
    expect(determineRegime({ powerKw: 5000, gridConnected: true, voltage: 'BT' })).toBe('autorisation');
    expect(determineRegime({ powerKw: 20000, gridConnected: true, voltage: 'HT' })).toBe('autorisation');
  });
});
