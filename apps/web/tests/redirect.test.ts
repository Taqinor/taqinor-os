// Redirection canonique workers.dev → taqinor.ma (301, chemin + query préservés).
import { describe, expect, it } from 'vitest';

// @ts-expect-error — module JS pur sans déclaration de types (copié dans dist/server au build)
import { canonicalTarget, CANONICAL_ORIGIN } from '../worker/canonical.mjs';

describe('canonicalTarget', () => {
  it('redirige la racine workers.dev vers taqinor.ma', () => {
    expect(canonicalTarget('https://taqinor-web.taqinor.workers.dev/')).toBe('https://taqinor.ma/');
  });

  it('préserve le chemin et la querystring', () => {
    expect(
      canonicalTarget('https://taqinor-web.taqinor.workers.dev/loi-82-21?utm_source=g&x=1'),
    ).toBe('https://taqinor.ma/loi-82-21?utm_source=g&x=1');
  });

  it('couvre les déploiements de préversion *.workers.dev', () => {
    expect(canonicalTarget('https://abc123-taqinor-web.taqinor.workers.dev/contact')).toBe(
      'https://taqinor.ma/contact',
    );
  });

  it('laisse passer le domaine canonique et tout autre hôte', () => {
    expect(canonicalTarget('https://taqinor.ma/')).toBeNull();
    expect(canonicalTarget('https://www.taqinor.ma/contact')).toBeNull();
    expect(canonicalTarget('http://localhost:4321/')).toBeNull();
  });

  it('expose le bon hôte canonique', () => {
    expect(CANONICAL_ORIGIN).toBe('https://taqinor.ma');
  });
});
