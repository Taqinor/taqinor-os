/**
 * YBW27 — page Confidentialité (FR + EN, un gabarit), sur le HTML RENDU.
 *  - avec une fixture complète, chaque section s'affiche dans les deux langues ;
 *  - tout ce qu'elle affirme est COMPARÉ aux faits : registre des champs
 *    (contrat YBW50), registre des sous-traitants (YBW26), durée = code de l'ERP,
 *    aucune IP transmise (contrat), anonymisation (jamais « supprimé ») ;
 *  - état réel : la route n'existe pas (champs `null`, anonymisation non armée).
 */
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import Confidentialite from '../src/pages/confidentialite.astro';
import { CONSERVATION_PROSPECTS, confidentialiteComplete, LEGAL, type Legal, routesJuridiquesCompletes } from '../src/lib/legal';
import { CLES_CHAMPS, donneesCollectees } from '../src/lib/rdv/champs';
import { SOUS_TRAITANTS } from '../src/lib/subprocessors';
import { creerWorker } from '../worker/pipeline.mjs';
import { LEGAL_COMPLET } from './fixtures/legal-complet';

const ARMEE = { ans: CONSERVATION_PROSPECTS.ans, anonymisationArmee: true };
const lire = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const CONTRAT = JSON.parse(lire('../src/contract_samples/demande_rdv_site.json')) as { jamais_transmis: string[] };
const DSR_ERP = lire('../../../backend/django_core/apps/crm/dsr_provider.py');

async function rendre(props: Record<string, unknown>): Promise<Document> {
  const container = await AstroContainer.create();
  return new JSDOM(await container.renderToString(Confidentialite, { props })).window.document;
}
const section = (doc: Document, id: string) => doc.querySelector(`[data-section="${id}"]`);
const texte = (doc: Document) => doc.body.textContent ?? '';

describe('YBW27 — fixture complète, FR', () => {
  it('responsable, données (registre), finalité, base, destinataires (registre), transferts, durée, droits, plaintes', async () => {
    const doc = await rendre({ locale: 'fr', legal: LEGAL_COMPLET, conservation: ARMEE });
    expect(doc.documentElement.getAttribute('lang')).toBe('fr');
    expect(doc.querySelector('h1')?.textContent).toBe('Confidentialité');
    expect(doc.querySelector('[data-responsable]')?.textContent).toBe('Fixture Test Ltd');
    expect(section(doc, 'responsable')?.textContent).toContain('1 Test Street, Testville');
    expect(section(doc, 'responsable')?.querySelector('a')?.getAttribute('href')).toBe('mailto:test@example.invalid');

    // Données collectées = registre des champs = contrat, ligne pour ligne.
    const lignes = [...doc.querySelectorAll('[data-section="donnees"] tbody tr')];
    expect(lignes.map((l) => l.getAttribute('data-champ'))).toEqual(CLES_CHAMPS);
    for (const [i, d] of donneesCollectees('fr').entries()) {
      expect(lignes[i].children[0].textContent).toBe(d.donnee);
      expect(lignes[i].children[1].textContent).toBe(d.finalite);
      expect(lignes[i].children[2].textContent).toBe(d.obligatoire ? 'obligatoire' : 'facultatif');
    }

    expect(section(doc, 'finalite')?.textContent).toContain('Répondre à votre demande de rendez-vous.');
    expect(section(doc, 'base')?.textContent).toMatch(/consentement/);

    // Destinataires = registre des sous-traitants, entrée pour entrée.
    const st = [...doc.querySelectorAll('[data-sous-traitant]')].map((r) => r.getAttribute('data-sous-traitant'));
    expect(st).toEqual(SOUS_TRAITANTS.map((s) => s.id));
    expect(section(doc, 'destinataires')?.textContent).toContain('Allemagne');

    expect(section(doc, 'transferts')?.textContent).toMatch(/Royaume-Uni.*Union européenne.*Maroc/s);
    expect(doc.querySelector('[data-garanties]')?.textContent).toBe('Garanties de test.');
    expect(doc.querySelector('[data-duree]')?.textContent).toBe(
      "Trois ans après le dernier contact, votre demande est anonymisée dans l'ERP : elle ne permet plus de vous identifier.",
    );
    expect(section(doc, 'droits')?.textContent).toMatch(/09-08/);
    expect(section(doc, 'droits')?.textContent).toMatch(/RGPD.*UK GDPR/s);
    for (const autorite of ['CNDP', 'CNIL', 'ICO']) expect(section(doc, 'reclamation')?.textContent).toContain(autorite);
    expect(section(doc, 'representant')?.textContent).toContain('Représentant Test');
    expect(section(doc, 'whatsapp')?.textContent).toMatch(/aucune donnée n'est transmise avant le clic/);
    expect(section(doc, 'prospection')?.textContent).toMatch(/aucune prospection/i);
    expect(doc.querySelector('[data-foi]')?.textContent).toMatch(/version française/);
    expect(texte(doc)).not.toMatch(/undefined|null|\{n\}/);
  });

  it('représentant UE absent → section absente', async () => {
    const sans: Legal = { ...LEGAL_COMPLET, commun: { ...LEGAL_COMPLET.commun, representantUe: null } };
    expect(section(await rendre({ locale: 'fr', legal: sans, conservation: ARMEE }), 'representant')).toBeNull();
  });
});

describe('YBW27 — fixture complète, EN (même gabarit)', () => {
  it('libellés anglais, hreflang si en active, aucun mot français', async () => {
    const doc = await rendre({ locale: 'en', locales: ['fr', 'en'], legal: LEGAL_COMPLET, conservation: ARMEE });
    expect(doc.documentElement.getAttribute('lang')).toBe('en');
    expect(doc.querySelector('h1')?.textContent).toBe('Privacy');
    expect([...doc.querySelectorAll('link[rel="alternate"]')].map((l) => l.getAttribute('hreflang'))).toEqual(['fr', 'en', 'x-default']);
    expect(doc.querySelector('[data-duree]')?.textContent).toMatch(/^Three years after the last contact/);
    expect(doc.querySelector('[data-garanties]')?.textContent).toBe('Test safeguards.');
    expect(section(doc, 'destinataires')?.textContent).toContain('Germany');
    const corps = texte(doc).replace('Fixture Test Ltd', '').replace('1 Test Street, Testville', '');
    expect(corps).not.toMatch(/\b(Données|Responsable|Durée|Réclamation|obligatoire|facultatif|Allemagne|Royaume-Uni|consentement|anonymisée)\b/);
    expect(corps).not.toMatch(/undefined|\{n\}/);
  });
});

describe('YBW27 — aucune promesse que le code ne tient pas', () => {
  it('la durée = celle de l’ERP, et elle n’est annoncée qu’une fois l’anonymisation armée', () => {
    const m = /^DUREE_CONSERVATION_PROSPECTS_ANS\s*=\s*(\d+)\s*$/m.exec(DSR_ERP);
    expect(m, 'constante ERP introuvable').not.toBeNull();
    expect(CONSERVATION_PROSPECTS.ans).toBe(Number(m![1]));
    expect(DSR_ERP).toContain("RETENTION_ACTIF_SETTING = 'CRM_LEAD_RETENTION_ACTIF'");
    // L'ERP anonymise (jamais « supprime ») : la page aussi.
    expect(DSR_ERP).toMatch(/ne SUPPRIME rien : il anonymise/);
    expect(confidentialiteComplete(LEGAL_COMPLET, { ans: 3, anonymisationArmee: false })).toBe(false);
  });

  it('« aucune IP transmise » = le contrat', async () => {
    expect(CONTRAT.jamais_transmis).toEqual(expect.arrayContaining(['ip', 'user_agent']));
    expect(CLES_CHAMPS).not.toContain('ip');
    const doc = await rendre({ locale: 'fr', legal: LEGAL_COMPLET, conservation: ARMEE });
    expect(doc.querySelector('[data-aucune-ip]')?.textContent).toMatch(/Aucune adresse IP/);
  });

  it('jamais « supprimé » / « deleted », jamais un chiffre d’années', async () => {
    for (const locale of ['fr', 'en']) {
      const t = texte(await rendre({ locale, legal: LEGAL_COMPLET, conservation: ARMEE }));
      expect(t).not.toMatch(/supprim|deleted|delete\b/i);
      expect(t).not.toMatch(/\d+\s*(ans|années|years?)\b/i);
    }
  });

  it('la reprise KV n’apparaît que si elle existe, avec sa durée', async () => {
    const kv = { id: 'cloudflare-kv', nom: 'Cloudflare KV', role: 'Reprise.', csp: {}, dureeJours: 7 };
    const doc = await rendre({ locale: 'fr', legal: LEGAL_COMPLET, conservation: ARMEE, sousTraitants: [...SOUS_TRAITANTS, kv] });
    expect(doc.querySelector('[data-sous-traitant="cloudflare-kv"]')?.textContent).toContain('7 jours au plus');
    expect(SOUS_TRAITANTS.some((s) => s.id === 'cloudflare-kv')).toBe(false);
  });
});

describe('YBW27 — complétude et route', () => {
  it('complète seulement avec responsable + entité complète + e-mail + garanties + anonymisation armée', () => {
    expect(confidentialiteComplete(LEGAL_COMPLET, ARMEE)).toBe(true);
    expect(routesJuridiquesCompletes(LEGAL_COMPLET, ARMEE)).toEqual(['/mentions-legales', '/en/legal', '/confidentialite', '/en/privacy']);
    const variantes: Legal[] = [
      { ...LEGAL_COMPLET, commun: { ...LEGAL_COMPLET.commun, responsableTraitement: null } },
      { ...LEGAL_COMPLET, commun: { ...LEGAL_COMPLET.commun, email: null } },
      { ...LEGAL_COMPLET, commun: { ...LEGAL_COMPLET.commun, garantiesTransferts: null } },
      { ...LEGAL_COMPLET, commun: { ...LEGAL_COMPLET.commun, responsableTraitement: 'maroc' }, maroc: { ...LEGAL_COMPLET.maroc, ice: null } },
    ];
    for (const v of variantes) expect(confidentialiteComplete(v, ARMEE)).toBe(false);
  });

  it('état réel : non complète, rendu vide de toute affirmation', async () => {
    expect(CONSERVATION_PROSPECTS.anonymisationArmee).toBe(false);
    expect(confidentialiteComplete(LEGAL)).toBe(false);
    expect(routesJuridiquesCompletes(LEGAL)).not.toContain('/confidentialite');
    const doc = await rendre({ locale: 'fr' });
    expect(doc.querySelectorAll('[data-section]').length).toBe(0);
  });

  it('build : dossier retiré, le Worker répond 404 (fermé ET ouvert)', async () => {
    const client = fileURLToPath(new URL('../dist/client/', import.meta.url));
    const config = fileURLToPath(new URL('../dist/server/site-config.mjs', import.meta.url));
    if (!existsSync(config)) throw new Error('dist/ absent — lancer `npm run build` avant `npm test`');
    expect(existsSync(client + 'confidentialite')).toBe(false);
    const cfg = (await import(/* @vite-ignore */ pathToFileURL(config).href)) as { ROUTES_JURIDIQUES_COMPLETES: string[] };
    expect(cfg.ROUTES_JURIDIQUES_COMPLETES).not.toContain('/confidentialite');
    const app = { fetch: () => new Response('<html></html>', { headers: { 'content-type': 'text/html' } }) };
    const worker = creerWorker(app, { CANONICAL_ORIGIN: null, CSP_SOURCES: {}, ROUTES_JURIDIQUES_COMPLETES: cfg.ROUTES_JURIDIQUES_COMPLETES });
    for (const env of [{}, { SITE_PUBLIC: '1' }]) {
      expect((await worker.fetch(new Request('https://x.test/confidentialite/'), env, {})).status).toBe(404);
    }
  });
});
