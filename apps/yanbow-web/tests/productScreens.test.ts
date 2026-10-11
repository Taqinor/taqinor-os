import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import sharp from 'sharp';
import { describe, expect, it } from 'vitest';
import {
  controlerTexte,
  DOSSIER_SORTIE,
  ECRANS,
  ecrireCapture,
  enregistrer,
  estHoteLocal,
  exigerRouteSansVeille,
  lireCaptures,
  routeDe,
  SOCIETE_CAPTURE,
} from '../scripts/capture-product-screens.mjs';
import { CHIFFRE_AVEC_UNITE } from '../scripts/check-claims.mjs';
import { AFFIRMATIONS } from '../src/lib/claims';
import { CAPTURES, capturesPubliables, ECRANS_PRODUIT, LEGENDE, produitDe } from '../src/data/productScreens';

const SCRIPT = join(process.cwd(), 'scripts/capture-product-screens.mjs');

describe('YBW41 — pile LOCALE uniquement (jamais la production)', () => {
  it.each(['http://localhost', 'http://localhost:5173/x', 'http://127.0.0.1', 'http://[::1]:8080', 'http://erp.localhost'])(
    'accepte %s',
    (url) => expect(estHoteLocal(url)).toBe(true),
  );
  it.each([
    'https://api.taqinor.ma',
    'https://taqinor.ma',
    'http://178.105.192.116',
    'https://178-105-192-116.sslip.io',
    'http://localhost.evil.example',
    'file:///etc/passwd',
    'pas une url',
  ])('refuse %s', (url) => expect(estHoteLocal(url)).toBe(false));

  it('le script s’ARRÊTE avant tout navigateur sur un hôte distant (processus réel)', () => {
    const r = spawnSync(process.execPath, [SCRIPT], {
      env: { ...process.env, CAPTURE_ERP_URL: 'https://api.taqinor.ma' },
      encoding: 'utf8',
      timeout: 30_000,
    });
    expect(r.status).toBe(1);
    expect(r.stderr).toContain('pile locale');
  });

  it('le script exige les identifiants dans l’environnement (rien en dur)', () => {
    const r = spawnSync(process.execPath, [SCRIPT, '--ecran', 'crm-pipeline'], {
      env: { ...process.env, CAPTURE_ERP_URL: 'http://localhost', CAPTURE_IDENTIFIANT: '', CAPTURE_MOT_DE_PASSE: '' },
      encoding: 'utf8',
      timeout: 30_000,
    });
    expect(r.status).toBe(1);
    expect(r.stderr).toContain('CAPTURE_IDENTIFIANT');
  });

  it('la société de capture est la société fictive renommée', () => {
    expect(SOCIETE_CAPTURE).toBe('YanBow — démo');
  });
});

describe('YBW41 — jamais d’écran de veille (D-YBW-7)', () => {
  it.each(['/publicite/veille', '/publicite/ad-library', '/x/bibliotheque-publicitaire'])('refuse %s', (r) =>
    expect(() => exigerRouteSansVeille(r)).toThrow(/veille/),
  );
  it('aucun écran déclaré ne mène à la veille', () => {
    for (const e of ECRANS) if (e.route) expect(() => exigerRouteSansVeille(e.route!)).not.toThrow();
    for (const e of ECRANS_PRODUIT) expect(e.id).not.toMatch(/veille/i);
  });
  it('les routes à identifiant exigent CAPTURE_ID_CALEPINAGE entier', () => {
    const e = ECRANS.find((x) => x.id === 'calepinage-3d')!;
    expect(() => routeDe(e, {})).toThrow(/CAPTURE_ID_CALEPINAGE/);
    expect(() => routeDe(e, { CAPTURE_ID_CALEPINAGE: '1;drop' })).toThrow();
    expect(routeDe(e, { CAPTURE_ID_CALEPINAGE: '12' })).toBe('/calepinage/12');
  });
});

describe('YBW41 — contrôle du texte de la zone capturée', () => {
  it.each([
    ['TAQINOR Démo (complet)', 'entreprise d’installation nommée'],
    ['Total 12 500 MAD', 'devise'],
    ['Total 12 500 DH', 'devise'],
    ['Total 1 200 €', 'devise'],
    ['Prix d’achat : 900', 'prix d’achat'],
    ['prix_achat', 'prix d’achat'],
    ['Marge 18 %', 'marge'],
    ['Veille concurrentielle', 'veille'],
  ])('« %s » → %s', (texte, nom) => expect(controlerTexte(texte)).toContain(nom));

  it('un écran conforme passe', () => {
    expect(controlerTexte('Pipeline — Nouveau, Contacté, Devis envoyé. Projet Exemple, toiture sud.')).toEqual([]);
  });
});

describe('YBW41 — registre productScreens', () => {
  it('chaque écran du script a son entrée (et réciproquement)', () => {
    expect(ECRANS.map((e) => e.id).sort()).toEqual(ECRANS_PRODUIT.map((e) => e.id).sort());
  });

  it('chaque écran cite une affirmation PUBLIABLE existante', () => {
    for (const e of ECRANS_PRODUIT) {
      const a = AFFIRMATIONS.find((x) => x.id === e.affirmation);
      expect(a, e.id).toBeDefined();
      expect(a!.publiable, e.id).toBe(true);
      expect(['solarbow', 'marketingbow']).toContain(produitDe(e));
    }
  });

  it('la légende exacte, dans les deux langues', () => {
    expect(LEGENDE).toEqual({ fr: 'Données fictives', en: 'Fictional data' });
  });

  it('les textes alternatifs ne violent aucun contrôle et ne contiennent aucun chiffre avec unité', () => {
    for (const e of ECRANS_PRODUIT) {
      expect(controlerTexte(e.alt.fr), e.id).toEqual([]);
      expect(e.alt.fr, e.id).not.toMatch(CHIFFRE_AVEC_UNITE);
    }
  });
});

describe('YBW41 — chaque capture enregistrée est réelle, dimensionnée et revue', () => {
  it('registre lisible', () => {
    expect(Array.isArray(lireCaptures().captures)).toBe(true);
  });

  for (const c of CAPTURES) {
    it(`${c.ecran}@${c.largeur}`, async () => {
      expect(ECRANS_PRODUIT.map((e) => e.id)).toContain(c.ecran);
      for (const f of [c.avif, c.webp]) expect(existsSync(join(DOSSIER_SORTIE, f)), f).toBe(true);
      const meta = await sharp(readFileSync(join(DOSSIER_SORTIE, c.webp))).metadata();
      expect([meta.width, meta.height]).toEqual([c.width, c.height]);
      expect(meta.width).toBeLessThanOrEqual(c.largeur);
      expect(['ok', 'revue-seule']).toContain(c.controle_texte);
      expect(c.revue.trim(), 'revue zoomée humaine non consignée').not.toBe('');
    });
  }

  it('écriture réelle : AVIF + WebP, dimensions et revue vide (non publiable tant que non revue)', async () => {
    const dossier = mkdtempSync(join(tmpdir(), 'ybw41-'));
    const png = await sharp({ create: { width: 300, height: 120, channels: 3, background: '#FAF7F2' } })
      .png()
      .toBuffer();
    const entree = await ecrireCapture(png, 'crm-pipeline', 390, 'ok', dossier);
    expect(entree).toMatchObject({ width: 300, height: 120, revue: '', avif: 'crm-pipeline-390.avif' });
    expect((await sharp(readFileSync(join(dossier, entree.avif))).metadata()).format).toBe('heif');
    const fichier = join(dossier, 'captures.json');
    enregistrer([entree], fichier);
    enregistrer([{ ...entree, height: 121 }], fichier);
    expect(lireCaptures(fichier).captures).toHaveLength(1);
  });

  it('un écran sans capture figure « à capturer » dans CAPTURE.md (jamais d’image inventée)', () => {
    const guide = readFileSync(join(DOSSIER_SORTIE, '../../../scripts/CAPTURE.md'), 'utf8');
    for (const e of ECRANS_PRODUIT) {
      if (CAPTURES.some((c) => c.ecran === e.id)) continue;
      const ligne = guide.split('\n').find((l) => l.includes(`\`${e.id}\``) && l.includes('à capturer'));
      expect(ligne, `${e.id} sans capture ni mention « à capturer »`).toBeTruthy();
    }
  });

  it('une capture non revue n’est jamais publiable', () => {
    for (const e of ECRANS_PRODUIT) for (const c of capturesPubliables(e.id)) expect(c.revue.trim()).not.toBe('');
  });
});
