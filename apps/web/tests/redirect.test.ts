// Redirection canonique workers.dev → taqinor.ma (301, chemin + query préservés).
import { describe, expect, it } from 'vitest';

// @ts-expect-error — module JS pur sans déclaration de types (copié dans dist/server au build)
import { canonicalTarget, CANONICAL_ORIGIN } from '../worker/canonical.mjs';
// @ts-expect-error — module JS pur sans déclaration de types (copié dans dist/server au build)
import { pathRedirect } from '../worker/redirects.mjs';

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

describe('pathRedirect', () => {
  it('redirige les slugs sans accent vers le canonique accentué (301)', () => {
    expect(pathRedirect('https://taqinor.ma/residentiel')).toEqual({
      target: 'https://taqinor.ma/r%C3%A9sidentiel',
      status: 301,
    });
    expect(pathRedirect('https://taqinor.ma/equipement')).toEqual({
      target: 'https://taqinor.ma/%C3%A9quipement',
      status: 301,
    });
  });

  it('tolère une barre oblique finale et préserve la querystring', () => {
    expect(pathRedirect('https://taqinor.ma/accueil/?utm_source=g')).toEqual({
      target: 'https://taqinor.ma/?utm_source=g',
      status: 301,
    });
  });

  it('redirige /simulator et ses sous-chemins vers le sous-domaine (301, chemin préservé)', () => {
    expect(pathRedirect('https://taqinor.ma/simulator')).toEqual({
      target: 'https://simulateur.taqinor.ma/simulator',
      status: 301,
    });
    expect(pathRedirect('https://taqinor.ma/simulator/')).toEqual({
      target: 'https://simulateur.taqinor.ma/simulator/',
      status: 301,
    });
    expect(pathRedirect('https://taqinor.ma/simulator/login')).toEqual({
      target: 'https://simulateur.taqinor.ma/simulator/login',
      status: 301,
    });
    expect(pathRedirect('https://taqinor.ma/simulator?utm_source=g')).toEqual({
      target: 'https://simulateur.taqinor.ma/simulator?utm_source=g',
      status: 301,
    });
  });

  it('mappe les alias usuels vers la bonne page (301)', () => {
    expect(pathRedirect('https://taqinor.ma/regularisation')?.target).toBe(
      'https://taqinor.ma/regularization-article-33',
    );
    expect(pathRedirect('https://taqinor.ma/confidentialite')?.target).toBe(
      'https://taqinor.ma/politique-de-confidentialite',
    );
    expect(pathRedirect('https://taqinor.ma/mentions')?.target).toBe('https://taqinor.ma/mentions-legales');
    expect(pathRedirect('https://taqinor.ma/home')?.status).toBe(301);
  });

  it('laisse passer les vrais chemins du site (aucune redirection)', () => {
    expect(pathRedirect('https://taqinor.ma/')).toBeNull();
    expect(pathRedirect('https://taqinor.ma/contact')).toBeNull();
    expect(pathRedirect('https://taqinor.ma/loi-82-21')).toBeNull();
    expect(pathRedirect('https://taqinor.ma/résidentiel')).toBeNull();
  });
});
