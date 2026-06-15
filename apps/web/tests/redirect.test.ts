// Redirection canonique workers.dev → taqinor.ma (301, chemin + query préservés).
import { describe, expect, it } from 'vitest';

// @ts-expect-error — module JS pur sans déclaration de types (copié dans dist/server au build)
import { canonicalTarget, CANONICAL_ORIGIN } from '../worker/canonical.mjs';
// @ts-expect-error — module JS pur sans déclaration de types (copié dans dist/server au build)
import { pathRedirect, trailingSlashRedirect } from '../worker/redirects.mjs';

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

describe('trailingSlashRedirect — forme canonique = avec barre finale', () => {
  it('301 une page sans barre → avec barre (chemin + query préservés)', () => {
    expect(trailingSlashRedirect('https://taqinor.ma/contact')).toEqual({
      target: 'https://taqinor.ma/contact/',
      status: 301,
    });
    expect(trailingSlashRedirect('https://taqinor.ma/loi-82-21?utm_source=g')).toEqual({
      target: 'https://taqinor.ma/loi-82-21/?utm_source=g',
      status: 301,
    });
  });

  it('301 aussi les slugs accentués (déjà encodés dans l’URL)', () => {
    expect(trailingSlashRedirect('https://taqinor.ma/r%C3%A9sidentiel')).toEqual({
      target: 'https://taqinor.ma/r%C3%A9sidentiel/',
      status: 301,
    });
  });

  it('ne touche PAS la racine ni les chemins déjà terminés par une barre', () => {
    expect(trailingSlashRedirect('https://taqinor.ma/')).toBeNull();
    expect(trailingSlashRedirect('https://taqinor.ma/contact/')).toBeNull();
  });

  it('EXEMPTE /api/* (le formulaire live et l’estimateur postent sans barre)', () => {
    expect(trailingSlashRedirect('https://taqinor.ma/api/simulate')).toBeNull();
    expect(trailingSlashRedirect('https://taqinor.ma/api/roof-config')).toBeNull();
    expect(trailingSlashRedirect('https://taqinor.ma/api/roof-yield')).toBeNull();
  });

  it('EXEMPTE les POST (jamais de 301 sur une soumission de formulaire)', () => {
    expect(trailingSlashRedirect('https://taqinor.ma/contact', 'POST')).toBeNull();
    expect(trailingSlashRedirect('https://taqinor.ma/api/simulate', 'POST')).toBeNull();
  });

  it('EXEMPTE les fichiers à extension (sitemap.xml, robots.txt, favicon.svg, assets)', () => {
    expect(trailingSlashRedirect('https://taqinor.ma/sitemap-index.xml')).toBeNull();
    expect(trailingSlashRedirect('https://taqinor.ma/robots.txt')).toBeNull();
    expect(trailingSlashRedirect('https://taqinor.ma/favicon.svg')).toBeNull();
    expect(trailingSlashRedirect('https://taqinor.ma/_astro/app.js')).toBeNull();
  });

  it('canonicalise aussi les previews privées (cohérence de routage)', () => {
    expect(trailingSlashRedirect('https://taqinor.ma/preview/toiture-3d-pro-3')).toEqual({
      target: 'https://taqinor.ma/preview/toiture-3d-pro-3/',
      status: 301,
    });
  });
});
