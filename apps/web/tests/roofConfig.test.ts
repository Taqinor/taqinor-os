// Résolution de la clé MapTiler pour /api/roof-config.
//
// RÉGRESSION (bug live 2026-06-13) : la clé était posée en VARIABLE DE BUILD
// Cloudflare — présente au build (inlinée par Vite dans import.meta.env), mais
// ABSENTE du runtime (cf.env). L'endpoint ne lisait que cf.env → renvoyait
// available:false → repli affiché alors que la clé existait. Le helper doit
// accepter l'une OU l'autre source ; le repli ne reste QUE si aucune n'a de clé.
import { describe, expect, it } from 'vitest';
import { resolveMaptilerKey } from '../src/lib/roofConfig';

describe('resolveMaptilerKey — clé runtime OU build, repli seulement si aucune', () => {
  it('aucune source → chaîne vide (repli gracieux légitime)', () => {
    expect(resolveMaptilerKey(undefined, undefined)).toBe('');
    expect(resolveMaptilerKey('', '')).toBe('');
    expect(resolveMaptilerKey('   ', '   ')).toBe('');
  });

  it('variable de BUILD seule (le cas du bug) → utilisée', () => {
    expect(resolveMaptilerKey(undefined, 'BUILD_KEY')).toBe('BUILD_KEY');
    expect(resolveMaptilerKey('', 'BUILD_KEY')).toBe('BUILD_KEY');
  });

  it('variable RUNTIME seule → utilisée', () => {
    expect(resolveMaptilerKey('RUNTIME_KEY', undefined)).toBe('RUNTIME_KEY');
    expect(resolveMaptilerKey('RUNTIME_KEY', '')).toBe('RUNTIME_KEY');
  });

  it('les deux présentes → la runtime gagne (surcharge sans rebuild possible)', () => {
    expect(resolveMaptilerKey('RUNTIME_KEY', 'BUILD_KEY')).toBe('RUNTIME_KEY');
  });

  it('espaces ignorés (trim)', () => {
    expect(resolveMaptilerKey('  RK  ', undefined)).toBe('RK');
    expect(resolveMaptilerKey(undefined, '  BK  ')).toBe('BK');
  });
});
