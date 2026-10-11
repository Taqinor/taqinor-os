import { expect, test, type Page } from '@playwright/test';
import { crawler, installerSondes } from './gardes';
import { CLE_E2E, demarrerFauxErp, URL_FAUX_ERP, type FauxErp } from './fauxErp';

/**
 * YBW56 — bout en bout RÉEL : formulaire (navigateur) → Worker (`astro
 * preview`, workerd) → faux ERP (vrai HTTP local, `fauxErp.ts`). Le Worker
 * reçoit `YANBOW_RDV_URL/CLE_ID/SECRET` de `playwright.config.ts`.
 *  - le faux ERP vérifie la signature, l'`idempotency_key` DU CORPS et les clés
 *    du corps contre le contrat (aucun `company*`) ;
 *  - même demande deux fois (y compris avec un autre en-tête
 *    `Idempotency-Key`) → un seul lead ; corps altéré → refusé ;
 *  - le crawl YBW15, rejoué après l'envoi, reste propre.
 */
test.describe.configure({ mode: 'serial' });

let erp: FauxErp;

test.beforeAll(async () => {
  erp = await demarrerFauxErp();
  expect(erp.url).toBe(URL_FAUX_ERP);
});

test.afterAll(async () => {
  await erp?.fermer();
});

/** Attend que le faux ERP ait reçu `n` requêtes (l'envoi est en arrière-plan). */
async function attendreRequetes(n: number): Promise<void> {
  await expect.poll(() => erp.requetes.length, { timeout: 15_000 }).toBeGreaterThanOrEqual(n);
}

async function remplir(page: Page): Promise<void> {
  await page.getByLabel('Nom et prénom').fill('  Jeanne   Test ');
  await page.getByLabel('Société').fill('Atelier Test');
  await page.getByLabel('E-mail').fill(' Jeanne.Test@Example.com ');
  await page.getByLabel('Téléphone (facultatif)').fill('+33 6 00 00 00 00');
  await page.getByLabel('Sujet du rendez-vous').selectOption('sur_mesure');
  await page.getByLabel('Message (facultatif)').fill('Bonjour, une démonstration ?');
  await page.getByLabel(/J.accepte/).check();
}

test('formulaire → Worker → faux ERP : un lead, signé, conforme au contrat ; crawl propre après envoi', async ({ page }) => {
  await installerSondes(page);
  const problemes: string[] = [];
  page.on('console', (m) => m.type() === 'error' && problemes.push(`console.error : ${m.text()}`));
  page.on('pageerror', (e) => problemes.push(`pageerror : ${e.message}`));
  page.on('response', (r) => r.status() >= 400 && problemes.push(`HTTP ${r.status()} : ${r.url()}`));

  await page.goto('/rendez-vous/?utm_source=e2e&utm_campaign=essai');
  // D'abord les erreurs : sous chaque champ et nommées dans le bandeau, rien envoyé.
  await page.getByRole('button', { name: 'Envoyer la demande' }).click();
  await expect(page.locator('[data-bandeau]')).toBeVisible();
  await expect(page.locator('[data-erreur-pour="nom"]')).toHaveText('Ce champ est obligatoire.');
  await expect(page.locator('[data-erreur-pour="consentement"]')).toBeVisible();
  await expect(page.locator('[data-bandeau-liste] a', { hasText: 'Nom et prénom' })).toBeVisible();
  expect(problemes).toEqual([]);
  expect(erp.requetes).toHaveLength(0);

  await remplir(page);
  const reponse = page.waitForResponse('**/api/rendez-vous');
  await page.getByRole('button', { name: 'Envoyer la demande' }).click();
  expect((await reponse).status()).toBe(200);
  await expect(page.locator('[data-succes]')).toBeVisible();
  await expect(page.locator('form[data-rendez-vous]')).toBeHidden();
  expect(page.url()).not.toContain('Jeanne');

  await attendreRequetes(1);
  const [r] = erp.requetes;
  expect(r.statut, r.motif).toBe(201);
  expect(r.entetes['x-site-cle']).toBe(CLE_E2E);
  const corps = JSON.parse(r.corps);
  expect(r.entetes['idempotency-key']).toBe(corps.idempotency_key);
  expect(corps).toMatchObject({
    nom: 'Jeanne Test',
    societe: 'Atelier Test',
    email: 'jeanne.test@example.com',
    produit: 'sur_mesure',
    langue: 'fr',
    consentement: true,
    page: '/rendez-vous/',
    utm_source: 'e2e',
    utm_campaign: 'essai',
  });
  expect(Object.keys(corps).some((k) => k.toLowerCase().startsWith('company'))).toBe(false);
  // Aucun agent ni IP du visiteur dans ce qui part vers l'ERP.
  const ua = await page.evaluate(() => navigator.userAgent);
  expect(r.corps).not.toContain(ua);
  expect(String(r.entetes['user-agent'] ?? '')).not.toBe(ua);
  expect(erp.leads.size).toBe(1);

  problemes.push(...(await crawler(page, '/rendez-vous/')));
  expect(problemes).toEqual([]);
});

test('même demande deux fois (autre en-tête Idempotency-Key compris) → un seul lead ; corps altéré → refusé', async ({ request }) => {
  const avant = erp.leads.size;
  const demande = {
    idempotency_key: '0f0e0d0c-0b0a-4908-8706-050403020100',
    nom: 'Double Test',
    societe: 'Atelier Test',
    email: 'double@example.com',
    produit: 'solarbow',
    langue: 'fr',
    consentement: true,
    page: '/rendez-vous/',
  };
  const entetes = { 'sec-fetch-site': 'same-origin', 'content-type': 'application/json' };
  const n = erp.requetes.length;
  expect((await request.post('/api/rendez-vous', { data: demande, headers: entetes })).status()).toBe(200);
  expect((await request.post('/api/rendez-vous', { data: demande, headers: entetes })).status()).toBe(200);
  await attendreRequetes(n + 2);
  expect(erp.leads.size).toBe(avant + 1);
  expect(erp.requetes.slice(n).map((x) => x.statut)).toEqual([201, 200]);

  // Rejeu de la requête SIGNÉE capturée avec un autre en-tête Idempotency-Key : toujours un seul lead.
  const capturee = erp.requetes[n];
  const rejeu = await fetch(URL_FAUX_ERP, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-site-cle': String(capturee.entetes['x-site-cle']),
      'x-signature': String(capturee.entetes['x-signature']),
      'idempotency-key': 'un-autre-en-tete',
    },
    body: capturee.corps,
  });
  expect(rejeu.status).toBe(200);
  expect(await rejeu.json()).toMatchObject({ statut: 'deja_recu' });
  expect(erp.leads.size).toBe(avant + 1);

  // Corps altéré (même signature) → refusé, aucun lead.
  const altere = await fetch(URL_FAUX_ERP, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-site-cle': String(capturee.entetes['x-site-cle']),
      'x-signature': String(capturee.entetes['x-signature']),
    },
    body: capturee.corps.replace('Double Test', 'Autre Nom'),
  });
  expect(altere.status).toBe(401);
  expect(erp.leads.size).toBe(avant + 1);
});

test('une requête cross-site est refusée par le Worker et rien ne part', async ({ request }) => {
  const n = erp.requetes.length;
  const r = await request.post('/api/rendez-vous', {
    data: { nom: 'X', societe: 'Y', email: 'x@example.com', produit: 'solarbow', langue: 'fr', consentement: true },
    headers: { 'sec-fetch-site': 'cross-site', 'content-type': 'application/json' },
  });
  expect(r.status()).toBe(403);
  await new Promise((res) => setTimeout(res, 500));
  expect(erp.requetes.length).toBe(n);
});
