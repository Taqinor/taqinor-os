// Preuve en direct ASUP63 (audit PF10 « suppression, archivage, restauration », dossier
// docs/audits/2026-11-11-parcours-PF10.md) : après « Anonymiser (RGPD) » d'un client entreprise, le journal
// des ventes, l'export comptable (xlsx + csv) et le grand livre portent sur la facture, l'avoir et la note de
// débit le nom et l'ICE FIGÉS de la facture d'origine — jamais « Client anonymisé » ni un ICE vide.
// Étape PF10.4 rejouée À L'ÉCRAN sous le rôle livré Directeur (connexion par l'écran) : fiche client →
// « Anonymiser (RGPD) », puis liste des factures → Exporter → « Journal comptable… » et « Export comptable… » ;
// les classeurs téléchargés par l'écran (corps des réponses) sont OUVERTS (openpyxl dans le shell Django) et
// relus cellule par cellule. Le grand livre n'a pas d'entrée d'écran : lu par la route, même session.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, uiLoginJusquAuxApps, connexionApi } from '../helpers.js'

const etape = groupe('ASUP', ['ASUP63'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 420_000 })
const INIT = () => {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
}
test.beforeEach(async ({ page }) => { await page.addInitScript(INIT); await assurerSessionPage(page) })
const ouverts = []
test.afterEach(async () => { for (const c of ouverts.splice(0)) await (c.dispose ? c.dispose() : c.close()).catch(() => undefined) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte }).first()

/** Classeur xlsx (octets) ouvert par openpyxl : lignes portant une des `refs`, et cellules « anonymis… ». */
const lireClasseur = (octets, refs) => py(`import base64, io
from openpyxl import load_workbook
wb = load_workbook(io.BytesIO(base64.b64decode('${Buffer.from(octets).toString('base64')}')), read_only=True, data_only=True)
lignes = {r: [] for r in ${J(refs)}}
anonymes = []
feuilles = []
for ws in wb.worksheets:
    feuilles.append(ws.title)
    for row in ws.iter_rows(values_only=True):
        cellules = [str(c) for c in row if c is not None]
        for r in lignes:
            if any(r in c for c in cellules): lignes[r].append(cellules)
        anonymes += [c for c in cellules if 'anonymis' in c.lower()]
sortie({'feuilles': feuilles, 'lignes': lignes, 'anonymes': anonymes})`)
/** CSV (`;`, BOM UTF-8) : mêmes relevés. */
function lireCsv(texte, refs) {
  const rows = texte.replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean).map((l) => l.split(';').map((c) => c.replace(/^"|"$/g, '')))
  const lignes = Object.fromEntries(refs.map((r) => [r, rows.filter((cells) => cells.some((c) => c.includes(r)))]))
  return { lignes, anonymes: rows.flat().filter((c) => /anonymis/i.test(c)) }
}

etape('PF10.4-ASUP63-ecran', ['ASUP63'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nomClient = `Société Atlas ${m}`
  const ice = String(Date.now()).slice(-13).padStart(15, '0')
  // Given : client entreprise (nom, ICE) ; sa facture émise à l'acheteur FIGÉ (instantané d'émission), un avoir
  // et une note de débit émis sur cette facture — tous datés du jour.
  const x = await py(`from decimal import Decimal
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Avoir, LigneAvoir, NoteDebit
from apps.ventes.domain.instantanes_facture import identite_acheteur_courante
CO = ${SOC}
c = Client.objects.create(company_id=CO, nom=${J(nomClient)}, prenom='', type_client='entreprise', ice='${ice}', email='atlas-${m}@asup.invalid')
p = Produit.objects.create(company_id=CO, nom='Kit ASUP63 ${m}', sku='ASUP63-${m}', prix_vente=Decimal('1000'))
f = Facture.objects.create(company_id=CO, reference='FAC-ASUP63-${m}', client=c, statut='emise', taux_tva=Decimal('20'))
LigneFacture.objects.create(facture=f, produit=p, designation='Centrale', quantite=Decimal('1'), prix_unitaire=Decimal('1000'), remise=Decimal('0'), taux_tva=Decimal('20'))
Facture.objects.filter(pk=f.pk).update(identite_acheteur=identite_acheteur_courante(f))
av = Avoir.objects.create(company_id=CO, reference='AVO-ASUP63-${m}', facture=f, client=c, statut='emise', taux_tva=Decimal('20'))
LigneAvoir.objects.create(avoir=av, designation='Retour', quantite=Decimal('1'), prix_unitaire=Decimal('200'), remise=Decimal('0'), taux_tva=Decimal('20'))
nd = NoteDebit.objects.create(company_id=CO, reference='ND-ASUP63-${m}', facture=f, client=c, statut='emise', taux_tva=Decimal('20'),
    montant_ht=Decimal('100'), montant_tva=Decimal('20'), montant_ttc=Decimal('120'))
f.refresh_from_db()
sortie(dict(client=c.pk, refs=[f.reference, av.reference, nd.reference], fige=f.identite_acheteur, jour=str(f.date_emission)))`)
  expect([x.fige?.nom, x.fige?.ice], 'Given : acheteur figé sur la facture').toEqual([nomClient, ice])
  const refs = x.refs
  // Compte Directeur (rôle livré), connexion par l'écran.
  const nom = `asup63di_${m}`
  await py(`from apps.roles.models import Role
compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom='Directeur').pk, societe=${SOC})
sortie(1)`)
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block', acceptDownloads: true,
    ...(u.locale ? { locale: u.locale } : {}), ...(u.timezoneId ? { timezoneId: u.timezoneId } : {}), viewport: { width: 1600, height: 1000 },
  })
  ouverts.push(ctx)
  await page.close()
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  // When (1) : fiche client → « Anonymiser (RGPD) » → « Anonymiser définitivement ».
  await p.goto('/crm')
  await p.getByPlaceholder('Rechercher nom, email, tél, ICE, IF, RC, CIN…').fill(nomClient)
  await p.getByRole('row').filter({ hasText: nomClient }).first().click({ timeout: 60_000 })
  await expect(p.getByText(`Fiche client — ${nomClient}`)).toBeVisible({ timeout: 30_000 })
  await p.getByRole('button', { name: 'Anonymiser (RGPD)' }).click()
  const alerte = p.getByRole('alertdialog')
  await expect(alerte).toContainText('Anonymiser ce client ?')
  await alerte.getByRole('button', { name: 'Anonymiser définitivement' }).click()
  await expect(toast(p, 'Client anonymisé (données personnelles effacées)')).toBeVisible({ timeout: 30_000 })
  const apresAnon = await py(`from apps.crm.models import Client
c = Client.objects.get(pk=${x.client})
sortie([c.is_anonymized, c.nom, c.ice])`)
  expect(apresAnon[0], `client anonymisé en base (${J(apresAnon)})`).toBe(true)
  expect(apresAnon[1], 'le nom vivant n\'est plus celui d\'origine').not.toBe(nomClient)
  // When (2) : liste des factures → Exporter → « Journal comptable… » (mois courant) → Télécharger.
  await p.goto('/ventes/factures')
  const exporter = async (entree, titre, motifs) => {
    await p.getByRole('button', { name: 'Exporter' }).first().click({ timeout: 60_000 })
    await p.getByRole('menuitem', { name: entree }).click()
    const dlg = p.getByRole('dialog').filter({ hasText: titre })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    const attentes = motifs.map((rx) => p.waitForResponse((r) => r.request().method() === 'GET' && rx.test(r.url()), T))
    await dlg.getByRole('button', { name: 'Télécharger' }).click()
    const reps = await Promise.all(attentes)
    await expect(dlg, `${titre} : dialogue refermé (téléchargement abouti)`).toBeHidden({ timeout: 60_000 })
    return Promise.all(reps.map(async (r) => {
      expect(r.status(), `${r.url()} → ${r.status()}`).toBe(200)
      return r.body()
    }))
  }
  const [journal] = await exporter('Journal comptable…', 'Journal comptable', [/\/ventes\/journal-ventes\/\?/])
  const [comptaXlsx, comptaCsv] = await exporter('Export comptable…', 'Export comptable',
    [/\/ventes\/export-comptable\/\?.*fmt=xlsx/, /\/ventes\/export-comptable\/\?.*fmt=csv/])
  // Grand livre : aucune entrée d'écran — même session Directeur, même période.
  const api = await pwRequest.newContext({ baseURL: u.baseURL })
  ouverts.push(api)
  await connexionApi(api, { username: nom, password: MDP_ESSAI })
  const jour = x.jour
  const debut = `${jour.slice(0, 8)}01`
  const gl = {}
  for (const fmt of ['xlsx', 'csv']) {
    const r = await api.get(`${API}/ventes/export-comptable/?start=${debut}&end=${jour}&layout=grand-livre&fmt=${fmt}`, T)
    expect(r.status(), `grand livre ${fmt}`).toBe(200)
    gl[fmt] = await r.body()
  }
  // Then : chaque classeur ouvert ; chaque ligne de la facture, de l'avoir et de la note de débit porte le nom et
  // l'ICE figés ; aucune cellule « anonymisé ».
  const releves = {
    'journal des ventes (xlsx, écran)': await lireClasseur(journal, refs),
    'export comptable (xlsx, écran)': await lireClasseur(comptaXlsx, refs),
    'export comptable (csv, écran)': lireCsv(comptaCsv.toString('utf8'), refs),
    'grand livre (xlsx)': await lireClasseur(gl.xlsx, refs),
    'grand livre (csv)': lireCsv(gl.csv.toString('utf8'), refs),
  }
  for (const [quoi, rel] of Object.entries(releves)) {
    for (const ref of refs) {
      const lignes = rel.lignes[ref]
      expect(lignes.length, `${quoi} : ${ref} listée`).toBeGreaterThan(0)
      for (const l of lignes) {
        expect(l.some((c) => c.includes(nomClient)), `${quoi} · ${ref} : nom figé « ${nomClient} » (${J(l).slice(0, 300)})`).toBe(true)
        expect(l.some((c) => c.includes(ice)), `${quoi} · ${ref} : ICE figé ${ice} (${J(l).slice(0, 300)})`).toBe(true)
        expect(l.filter((c) => /anonymis/i.test(c)), `${quoi} · ${ref} : jamais « anonymisé »`).toEqual([])
      }
    }
    expect(rel.anonymes.filter((c) => c.includes('Client anonymisé')), `${quoi} : aucune cellule « Client anonymisé »`).toEqual([])
    console.log(`[ASUP63] ${quoi} : ${refs.map((r) => `${r}×${rel.lignes[r].length}`).join(', ')}${rel.feuilles ? ` ; feuilles ${J(rel.feuilles)}` : ''}`)
  }
  // Persistance n/a (lecture recalculée) : l'acheteur figé de la facture est inchangé en base.
  expect(await py(`from apps.ventes.models import Facture
f = Facture.objects.get(reference=${J(refs[0])})
sortie([f.identite_acheteur.get('nom'), f.identite_acheteur.get('ice')])`), 'acheteur figé inchangé').toEqual([nomClient, ice])
})
