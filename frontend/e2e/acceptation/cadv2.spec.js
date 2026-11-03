// CADV — 2e spec d'acceptation en direct (parcours PA1, cadence v4) : plafond WhatsApp, export, archivage,
// Standby, week-end, chaîne d'acceptation, pro trimestriel, pièces, frein, kanban, Froid en lot, cockpit, « À prendre »,
// validité du PDF, escalade J+14. Données créées par l'API réelle ; le shell Django (`_django.js`) ne pose que
// ce qu'aucun geste ne peut poser en direct (horloge gelée, état daté du passé, équipe, compte d'essai).
import { test, expect, request as pwRequest } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import {
  uniq, lireJson, listeDe, telephoneMobileUnique, connexionApi, assurerSessionPage, textePdf, nombrePagesPdf,
} from '../helpers.js'

const etape = groupe('CADV', ['CADV10', 'CADV67', 'CADV61', 'CADV77', 'CADV78', 'CADV30', 'CADV36', 'CADV102', 'CADV26', 'CADV29', 'CADV62', 'CADV74', 'CADV88', 'CADV105', 'CADV83', 'CADV112'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.beforeEach(async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000)
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const email = () => `${uniq('cadv').toLowerCase().replace(/[^a-z0-9]/g, '')}@example.invalid`
const nouveauLead = async (request, nom, extra = {}) => lireJson(await request.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: email(), ...extra },
}), 'lead')
const touches = async (request, lid) => listeDe(await lireJson(await request.get(`${API}/crm/relance-etapes/?lead=${lid}`, T), 'touches'))
const leadRelu = async (request, lid) => lireJson(await request.get(`${API}/crm/leads/${lid}/`, T), 'lead')
const fait = (request, id, data) => request.post(`${API}/crm/relance-etapes/${id}/fait/`, { ...T, data })

async function sessionEssai(testInfo, nom, role, context) {
  await py(`compte(${JSON.stringify(nom)}, role=${role}); sortie(1)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  if (context) await context.addCookies((await ctx.storageState()).cookies)
  return ctx
}

async function devisBrouillon(request, lid, tag) {
  const produit = await lireJson(await request.post(`${API}/stock/produits/`, {
    ...T, data: { nom: `Onduleur ${tag} ${marque()}`, prix_vente: '10000.00', prix_achat: '4321.09' },
  }), 'produit')
  return lireJson(await request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: lid,
      lignes: [{ produit: produit.id, designation: 'Onduleur', quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
    },
  }), 'devis')
}

async function devisEnvoye(request, lid, tag) {
  const devis = await devisBrouillon(request, lid, tag)
  await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  return lireJson(await request.get(`${API}/ventes/devis/${devis.id}/`, T), 'devis relu')
}

const caseLead = (page, texte) => page.getByRole('checkbox', { name: new RegExp(`Sélectionner .*${texte}`) })
const ouvrirListe = async (page, q, extra = '') => {
  await page.goto(`/crm/leads?view=liste&q=${encodeURIComponent(q)}${extra}`)
  await expect(caseLead(page, q.trim()).first()).toBeVisible({ timeout: 60_000 })
}
const joursDepuisAujourdhui = (e) => Math.round((new Date(`${e.due_date}T12:00:00Z`) - new Date(`${new Date().toISOString().slice(0, 10)}T12:00:00Z`)) / 864e5)
const isoDansJours = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10)

// ── CADV10 — plafond de 25 préparations WhatsApp par jour et par utilisateur, trace par lead ─────────
etape('PA1.cadence_contact.plafond_whatsapp', ['CADV10'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  const nom = `cadv10_${m}`
  const dir = await sessionEssai(testInfo, nom, 1, context)
  const a = await nouveauLead(dir, `CADV10 ${m} A`)
  const b = await nouveauLead(dir, `CADV10 ${m} B`)
  const c = await nouveauLead(dir, `CADV10 ${m} C`)
  const tpl = await lireJson(await dir.post(`${API}/crm/message-templates/`, { ...T, data: { nom: `CADV10 ${m}`, langue: 'fr', corps: 'Bonjour {prenom}.' } }), 'modèle')
  // 24 préparations RÉELLES (POST bulk, mêmes lignes de chatter) sur 24 leads d'essai.
  const vingtQuatre = []
  for (let i = 0; i < 24; i += 1) vingtQuatre.push((await nouveauLead(dir, `CADV10 ${m} lot${i}`)).id)
  const lot = await lireJson(await dir.post(`${API}/crm/leads/bulk/`, { ...T, data: { action: 'prepare_whatsapp', ids: vingtQuatre, template_id: tpl.id } }), 'lot de 24')
  expect(lot.queue, '24 liens').toHaveLength(24)
  // L'écran : trois leads cochés → WhatsApp en masse.
  await ouvrirListe(page, `CADV10 ${m} `)
  await caseLead(page, `${m} A`).click()
  await caseLead(page, `${m} B`).click()
  await caseLead(page, `${m} C`).click()
  await page.getByRole('button', { name: "Plus d'actions en masse" }).click()
  await page.getByRole('menuitem', { name: 'WhatsApp en masse' }).click()
  await page.locator('.bulk-panel').getByRole('combobox').click()
  await page.getByRole('option', { name: `CADV10 ${m}` }).click()
  const [rep] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/crm/leads/bulk/') && r.request().method() === 'POST', T),
    page.getByRole('button', { name: 'Préparer les liens' }).click(),
  ])
  const corps = await rep.json()
  expect(corps.queue.map((q) => q.lead_id), 'un seul lead passe').toHaveLength(1)
  expect(corps.skipped, 'les deux autres sont refusés').toHaveLength(2)
  for (const s of corps.skipped) expect(s.reason).toBe('plafond journalier atteint (25)')
  const file = page.getByTestId('lp-wa-queue')
  await expect(file.getByRole('link')).toHaveCount(1)
  await expect(file, "le motif du refus se lit à l'écran").toContainText('plafond journalier atteint (25)')
  // Persistance : le chatter du lead préparé porte UNE ligne ; recompté : 25 traces de l'utilisateur.
  const passe = corps.queue[0].lead_id
  expect([a.id, b.id, c.id]).toContain(passe)
  const histo = await lireJson(await dir.get(`${API}/crm/leads/${passe}/historique/`, T), 'historique')
  expect(listeDe(histo).filter((h) => (h.body || '').startsWith('WhatsApp préparé en lot')), 'une ligne par lead préparé').toHaveLength(1)
  const n = await py(`from apps.crm.models import LeadActivity
sortie(LeadActivity.objects.filter(user__username=${JSON.stringify(nom)}, body__startswith='WhatsApp préparé en lot').count())`)
  expect(n, '25 traces du jour').toBe(25)
  suivi.verifie(5)
})

// ── CADV67 — export .xlsx d'une sélection dont un lead opposé ────────────────────────────────────────
etape('PA1.arrivee_lead_crm.export_oppose', ['CADV67'], async ({ page, suivi }) => {
  const m = marque()
  await nouveauLead(page.request, `CADV67 ${m} Normal`)
  const b = await nouveauLead(page.request, `CADV67 ${m} Oppose`)
  await lireJson(await page.request.patch(`${API}/crm/leads/${b.id}/`, { ...T, data: { ne_plus_contacter: true } }), 'opposition')
  await ouvrirListe(page, `CADV67 ${m}`, '&perdus=avec')
  await caseLead(page, `${m} Normal`).click()
  await caseLead(page, `${m} Oppose`).click()
  const [dl] = await Promise.all([page.waitForEvent('download', T), page.getByRole('button', { name: /Exporter Excel/ }).click()])
  const chemin = join(mkdtempSync(join(tmpdir(), 'cadv67-')), 'leads.xlsx')
  await dl.saveAs(chemin)
  const texte = execFileSync('python', ['-I', '-c',
    "import sys,zipfile;sys.stdout.reconfigure(encoding='utf-8');z=zipfile.ZipFile(sys.argv[1]);print(' '.join(z.read(n).decode('utf-8','replace') for n in z.namelist() if n.endswith('.xml')))", chemin],
  { encoding: 'utf8', maxBuffer: 50_000_000 })
  expect(texte, 'le lead normal est dans le fichier').toContain(`CADV67 ${m} Normal`)
  expect(texte, "le lead opposé n'est PAS dans le fichier").not.toContain(`CADV67 ${m} Oppose`)
  expect(texte, 'ni son téléphone').not.toContain(b.telephone)
  suivi.verifie(5)
})

// ── CADV61 — archiver arrête les touches ; restaurer n'en ressuscite aucune ──────────────────────────
etape('PA1.cadence_contact.archivage', ['CADV61'], async ({ page, suivi }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `CADV61 ${m}`)
  const avant = (await touches(page.request, l.id)).filter((e) => e.statut === 'a_faire')
  expect(avant.length, 'une cadence active').toBeGreaterThan(0)
  await lireJson(await page.request.post(`${API}/crm/leads/${l.id}/archiver/`, T), 'archiver')
  const apres = await touches(page.request, l.id)
  expect(apres.filter((e) => e.statut === 'a_faire'), 'plus aucune touche à faire').toHaveLength(0)
  for (const e of apres.filter((x) => avant.some((a) => a.id === x.id))) {
    expect(e.statut).toBe('annulee')
    expect(e.note || '').toMatch(/lead archivé/)
  }
  await page.goto('/crm/cockpit')
  await expect(page.getByTestId('relances-du-jour-widget')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByTestId('relances-du-jour-widget'), 'la file du jour ne porte plus ce lead').not.toContainText(`CADV61 ${m}`)
  await lireJson(await page.request.post(`${API}/crm/leads/${l.id}/restaurer/`, T), 'restaurer')
  expect((await touches(page.request, l.id)).filter((e) => e.statut === 'a_faire'), 'restaurer ne ressuscite rien').toHaveLength(0)
  suivi.verifie(5)
})

/** Un lead dont une touche d'appel est ouverte (les messages d'avant sont sautés). */
async function leadAvecAppelOuvert(request, nom, extra = {}) {
  const l = await nouveauLead(request, nom, extra)
  for (let i = 0; i < 6; i += 1) {
    const ouverte = (await touches(request, l.id)).find((e) => e.statut === 'a_faire')
    if (ouverte.canal === 'appel') return { lead: l, appel: ouverte }
    const r = await request.post(`${API}/crm/relance-etapes/${ouverte.id}/sauter/`, { ...T, data: { note: 'rejeu' } })
    expect(r.ok(), `sauter ${ouverte.ordre}`).toBeTruthy()
  }
  throw new Error("pas de touche d'appel")
}

// ── CADV77 / CADV78 — « Plus tard » écrit Standby ; 3e réponse hors trimestre = Froid ────────────────
etape('PA1.cadence_contact.plus_tard', ['CADV77', 'CADV78'], async ({ page, suivi }) => {
  const m = marque()
  const { lead, appel } = await leadAvecAppelOuvert(page.request, `CADV77 ${m}`)
  const quand = isoDansJours(20)
  const fr = await fait(page.request, appel.id, { reponse: 'plus_tard', rappel_le: quand })
  expect(fr.ok(), `plus tard (${fr.status()})`).toBeTruthy()
  let relu = await leadRelu(page.request, lead.id)
  expect([relu.parc_etat, relu.parc_raison, relu.parc_jusqu_au], 'Standby et la date').toEqual(['standby', 'plus_tard_date', quand])
  const deplacee = (await touches(page.request, lead.id)).find((e) => e.id === appel.id)
  expect(deplacee.statut, 'même barreau').toBe('a_faire')
  expect(deplacee.due_date).toBe(quand)
  const [a, mm, j] = quand.split('-')
  await page.goto(`/crm/leads/${lead.id}`)
  await expect(page.getByTestId('cadence-frise')).toContainText(`${j}/${mm}/${a}`, { timeout: 60_000 })
  await expect(page.getByTestId('parc-standby'), 'la fiche montre Standby et la date').toHaveText(`Standby jusqu’au ${j}/${mm}/${a}`, { timeout: 30_000 })
  await page.reload()
  await expect(page.getByTestId('cadence-frise')).toContainText(`${j}/${mm}/${a}`, { timeout: 60_000 })
  await expect(page.getByTestId('parc-standby')).toHaveText(`Standby jusqu’au ${j}/${mm}/${a}`, { timeout: 30_000 })
  const chatter = listeDe(await lireJson(await page.request.get(`${API}/crm/leads/${lead.id}/historique/`, T), 'chatter'))
  expect(chatter.filter((x) => x.field === 'parc_raison'), 'une ligne de chatter').toHaveLength(1)
  // CADV78 : 2e « Plus tard » : encore Standby ; 3e hors du trimestre : Froid.
  const fr2 = await fait(page.request, appel.id, { reponse: 'plus_tard', rappel_le: isoDansJours(25) })
  expect(fr2.ok(), `2e plus tard (${fr2.status()})`).toBeTruthy()
  relu = await leadRelu(page.request, lead.id)
  expect(relu.parc_etat, '2e cycle : Standby').toBe('standby')
  const ouverte = (await touches(page.request, lead.id)).find((e) => e.statut === 'a_faire')
  const fr3 = await fait(page.request, ouverte.id, { reponse: 'plus_tard', rappel_le: `${new Date().getFullYear() + 1}-03-01` })
  expect(fr3.ok(), `3e plus tard (${fr3.status()})`).toBeTruthy()
  relu = await leadRelu(page.request, lead.id)
  expect([relu.parc_etat, relu.parc_raison, relu.stage], '3e hors trimestre : Froid').toEqual(['nurture', 'pas_maintenant_sans_date', 'COLD'])
  suivi.verifie(5)
})

// ── CADV30 — identité du week-end : samedi 10 h, dimanche 17 h, jamais en appel ──────────────────────
etape('PA1.contact_message.week_end', ['CADV30'], async ({ page, suivi }) => {
  const m = marque()
  const tel = () => telephoneMobileUnique()
  // Donnée exigée par la tâche (« barreau 1 de la société samedi_ok ») : posée pour l'étape, rétablie à la fin.
  const barreau = `from apps.parametres.models_relance import CadenceRelanceEtape as C
b = C.objects.filter(company_id=1, cadence='contact', ordre=1)`
  const avant = await py(`${barreau}
sortie(b.first().samedi_ok)
b.update(samedi_ok=True)`)
  const ids = await py(`
ids = {}
for cle, iso, nom, tel in (('sam', '2026-11-14T03:00:00+00:00', 'Sam', '${tel()}'), ('dim', '2026-11-15T11:00:00+00:00', 'Dim', '${tel()}'), ('mar', '2026-11-17T11:00:00+00:00', 'Mar', '${tel()}')):
    code, corps = a_l_heure(iso, 'post', '/api/django/crm/leads/', dict(nom='CADV30 ${m} ' + nom, ville='Casablanca', telephone=tel, email=cle + '${m}@example.invalid'))
    assert code == 201, (code, corps)
    ids[cle] = corps['id']
sortie(ids)`)
  // L'heure légale du Maroc est celle du SERVEUR (décret : GMT depuis le 20/09/2026, tzdata 2026.4 de requirements.txt) :
  // l'échéance se lit au fuseau serveur ; le Chromium de test peut embarquer un ICU d'avant le décret (+01).
  const lue = await py(`from apps.crm.models import RelanceEtape as R
from apps.crm import horaires
f = lambda pk: [(e.canal, e.due_at.astimezone(horaires.CASABLANCA).strftime('%w %d/%m %H:%M')) for e in R.objects.filter(lead_id=pk, template_cle='identite')]
sortie({k: f(v) for k, v in ${JSON.stringify(ids)}.items()})`)
  expect(lue.sam, 'samedi 10:00, jamais en appel').toEqual([['whatsapp', '6 14/11 10:00']])
  expect(lue.dim, 'dimanche 17:00').toEqual([['whatsapp', '0 15/11 17:00']])
  expect(lue.mar, 'le mardi : identité immédiate').toEqual([['whatsapp', '2 17/11 11:00']])
  const appel = (await touches(page.request, ids.sam)).filter((e) => e.canal === 'appel' && e.statut === 'a_faire')
  for (const e of appel) expect(new Date(`${e.due_date}T12:00:00Z`).getUTCDay(), "aucun appel posé le week-end sur ce lead").not.toBe(6)
  // L'écran : la frise du lead du samedi lit la même échéance ; rechargée, identique.
  const identite = (await touches(page.request, ids.sam)).find((e) => e.template_cle === 'identite')
  await page.goto(`/crm/leads/${ids.sam}`)
  await expect(page.getByTestId('cadence-frise')).toContainText('14/11/2026', { timeout: 60_000 })
  const attendu = await page.evaluate((iso) => new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca' }).format(new Date(iso)), identite.due_at)
  await expect(page.getByTestId('cadence-frise')).toContainText(`14/11/2026 ${attendu}`)
  await page.reload()
  await expect(page.getByTestId('cadence-frise')).toContainText(`14/11/2026 ${attendu}`, { timeout: 60_000 })
  await py(`${barreau}
b.update(samedi_ok=${avant ? 'True' : 'False'})
sortie(1)`)
  suivi.verifie(5)
})

const accepterDevis = async (request, devisId, nom) => lireJson(await request.post(`${API}/ventes/devis/${devisId}/accepter/`, { ...T, data: { nom } }), 'acceptation')

// ── CADV36 — acceptation : confirmation J+2 et acompte J+7 après l'arrêt des cadences ────────────────
etape('PA1.generique.chaine_acceptation', ['CADV36'], async ({ page, suivi }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `CADV36 ${m}`)
  const d = await devisEnvoye(page.request, l.id, 'CADV36')
  await accepterDevis(page.request, d.id, `Client ${m}`)
  const ouvertes = (await touches(page.request, l.id)).filter((e) => e.statut === 'a_faire')
  expect(ouvertes.map((e) => e.libelle).sort(), 'deux étapes ouvertes, rien d\'autre').toEqual(['Acompte : relancer le client', 'Confirmer la signature et la suite'])
  const par = Object.fromEntries(ouvertes.map((e) => [e.libelle, e]))
  expect(par['Confirmer la signature et la suite'].canal).toBe('appel')
  expect(joursDepuisAujourdhui(par['Confirmer la signature et la suite']), 'J+2 (recalé au créneau ouvert au plus)').toBeGreaterThanOrEqual(2)
  expect(joursDepuisAujourdhui(par['Confirmer la signature et la suite'])).toBeLessThanOrEqual(4)
  expect(joursDepuisAujourdhui(par['Acompte : relancer le client']), 'J+7').toBeGreaterThanOrEqual(7)
  expect(joursDepuisAujourdhui(par['Acompte : relancer le client'])).toBeLessThanOrEqual(9)
  expect((await leadRelu(page.request, l.id)).stage, 'stage Signé').toBe('SIGNED')
  await page.goto(`/crm/leads/${l.id}`)
  await expect(page.getByTestId('cadence-frise')).toContainText('Confirmer la signature', { timeout: 60_000 })
  await expect(page.getByTestId('cadence-frise')).toContainText('Acompte : relancer le client')
  await page.reload()
  await expect(page.getByTestId('cadence-frise')).toContainText('Confirmer la signature', { timeout: 60_000 })
  // Un second signal ne double rien.
  const n = await py(`from apps.crm.models import RelanceEtape
from apps.ventes.models import Devis
from apps.crm.cadence_filet import poser_chaine_apres_acceptation
poser_chaine_apres_acceptation(Devis.objects.get(pk=${d.id}), None)
sortie(RelanceEtape.objects.filter(lead_id=${l.id}, statut='a_faire').count())`)
  expect(n, 'pas de doublon').toBe(2)
  suivi.verifie(5)
})

// ── CADV102 — pro en fin de cadence : Standby trimestriel ; cycles épuisés : Froid ───────────────────
etape('PA1.reveil_appel.pro_trimestriel', ['CADV102'], async ({ page, suivi }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `CADV102 ${m} Cimenterie`, { type_installation: 'industriel' })
  await devisEnvoye(page.request, l.id, 'CADV102')
  const clore = async (e) => {
    const r = e.canal === 'appel'
      ? await fait(page.request, e.id, { outcome: 'non_joint', note: 'rejeu CADV102' })
      : await page.request.post(`${API}/crm/relance-etapes/${e.id}/sauter/`, { ...T, data: { note: 'rejeu CADV102' } })
    expect(r.ok(), `clore ${e.libelle} (${r.status()})`).toBeTruthy()
  }
  for (let i = 0; i < 40; i += 1) {
    const ouverte = (await touches(page.request, l.id)).find((e) => e.statut === 'a_faire')
    if (!ouverte || ouverte.libelle === 'Appel trimestriel') break
    await clore(ouverte)
  }
  let relu = await leadRelu(page.request, l.id)
  expect(relu.stage, 'jamais au Froid').not.toBe('COLD')
  expect([relu.parc_etat, relu.parc_raison]).toEqual(['standby', 'plus_tard_date'])
  const t = await touches(page.request, l.id)
  const tri = t.filter((e) => e.statut === 'a_faire')
  expect(tri.map((e) => e.libelle), 'UNE étape trimestrielle').toEqual(['Appel trimestriel'])
  expect(t.filter((e) => e.cadence === 'reveil'), 'aucun réveil').toHaveLength(0)
  const ecart = Math.round((new Date(`${relu.parc_jusqu_au}T12:00:00Z`) - Date.now()) / 864e5)
  expect(ecart, '+3 mois').toBeGreaterThanOrEqual(88)
  expect(ecart).toBeLessThanOrEqual(95)
  expect(tri[0].due_date, 'même date que le parc').toBe(relu.parc_jusqu_au)
  await page.goto(`/crm/leads/${l.id}`)
  await expect(page.getByTestId('cadence-frise')).toContainText('Appel trimestriel', { timeout: 60_000 })
  await expect(page.getByTestId('cadence-frise')).not.toContainText('Réveil')
  await page.reload()
  await expect(page.getByTestId('cadence-frise')).toContainText('Appel trimestriel', { timeout: 60_000 })
  // Quatre trimestres au plus : chaque appel trimestriel est clos à SON trimestre (horloge gelée) ;
  // clos le même jour, le parcage serait le même (idempotent) et aucun cycle ne compterait.
  let quand = new Date(`${relu.parc_jusqu_au}T11:00:00+01:00`)
  for (let i = 0; i < 4; i += 1) {
    const ouverte = (await touches(page.request, l.id)).find((e) => e.statut === 'a_faire')
    if (!ouverte) break
    const code = await py(`code, corps = a_l_heure('${quand.toISOString().replace('Z', '+00:00')}', 'post', '/api/django/crm/relance-etapes/${ouverte.id}/fait/', dict(outcome='non_joint', note='rejeu CADV102'))
sortie(code)`)
    expect(code, `clore le trimestre ${i + 1}`).toBe(200)
    quand = new Date(quand.getTime() + 92 * 864e5)
  }
  relu = await leadRelu(page.request, l.id)
  expect([relu.parc_raison, relu.stage], 'cycles épuisés : Froid').toEqual(['pas_maintenant_sans_date', 'COLD'])
  suivi.verifie(5)
})

// ── CADV26 — frein principal et déclencheur sur la fiche ─────────────────────────────────────────────
etape('PA1.qualification.frein', ['CADV26'], async ({ page, suivi }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `CADV26 ${m}`, { type_installation: 'residentiel' })
  await page.goto(`/crm/leads/${l.id}`)
  const frein = page.locator('#lf-frein-principal')
  await expect(frein).toBeVisible({ timeout: 60_000 })
  await frein.selectOption({ label: 'Prix' })
  await page.locator('#lf-declencheur').selectOption({ label: 'Les économies' })
  await expect.poll(async () => {
    const r = await leadRelu(page.request, l.id)
    return [r.frein_principal, r.declencheur]
  }, { timeout: 30_000, intervals: [500, 1000] }).toEqual(['prix', 'economies'])
  await page.reload()
  await expect(page.locator('#lf-frein-principal')).toHaveValue('prix', { timeout: 60_000 })
  await expect(page.locator('#lf-declencheur')).toHaveValue('economies')
  suivi.verifie(5)
})

// ── CADV29 — pièces reçues ? à J+3 puis J+7 pour un pro « joint » ────────────────────────────────────
etape('PA1.generique.pieces_recues', ['CADV29'], async ({ page, suivi }) => {
  const m = marque()
  const { lead, appel } = await leadAvecAppelOuvert(page.request, `CADV29 ${m} Atlas`, { type_installation: 'industriel' })
  const r = await fait(page.request, appel.id, { outcome: 'joint', note: 'rejeu CADV29' })
  expect(r.ok(), `joint (${r.status()})`).toBeTruthy()
  const ouvertes = async () => (await touches(page.request, lead.id)).filter((e) => e.cle === 'pieces_recues' && e.statut === 'a_faire')
  let p = await ouvertes()
  expect(p, 'une seule étape « Pièces reçues ? »').toHaveLength(1)
  expect(p[0].canal).toBe('whatsapp')
  expect(joursDepuisAujourdhui(p[0]), 'à J+3').toBeGreaterThanOrEqual(3)
  expect(joursDepuisAujourdhui(p[0])).toBeLessThanOrEqual(5)
  await page.goto(`/crm/leads/${lead.id}`)
  await expect(page.getByTestId('cadence-frise')).toContainText(p[0].libelle, { timeout: 60_000 })
  await page.reload()
  await expect(page.getByTestId('cadence-frise')).toContainText(p[0].libelle, { timeout: 60_000 })
  // Close sans pièce : la 2e relance à J+7 ; close encore : l'étape devis.
  const r2 = await fait(page.request, p[0].id, { note: 'rejeu' })
  expect(r2.ok(), `1re relance close (${r2.status()}) ${await r2.text()}`).toBeTruthy()
  p = await ouvertes()
  expect(p, 'la 2e relance').toHaveLength(1)
  expect(joursDepuisAujourdhui(p[0]), 'à J+7').toBeGreaterThanOrEqual(7)
  expect(joursDepuisAujourdhui(p[0])).toBeLessThanOrEqual(9)
  const r3 = await fait(page.request, p[0].id, { note: 'rejeu' })
  expect(r3.ok(), `2e relance close (${r3.status()}) ${await r3.text()}`).toBeTruthy()
  expect(await ouvertes(), 'plus de relance pièces').toHaveLength(0)
  const reste = (await touches(page.request, lead.id)).filter((e) => e.statut === 'a_faire')
  expect(reste.some((e) => /devis/i.test(e.libelle)), `l'étape devis : ${reste.map((e) => e.libelle)}`).toBeTruthy()
  // Le résidentiel identique reçoit l'étape devis tout de suite.
  const res = await leadAvecAppelOuvert(page.request, `CADV29 ${m} Villa`, { type_installation: 'residentiel' })
  expect((await fait(page.request, res.appel.id, { outcome: 'joint', note: 'rejeu' })).ok()).toBeTruthy()
  expect((await touches(page.request, res.lead.id)).filter((e) => e.cle === 'pieces_recues'), 'pas de pièces pour un résidentiel').toHaveLength(0)
  suivi.verifie(5)
})

// ── CADV62 — perdus et opposés masqués par défaut du kanban ──────────────────────────────────────────
etape('PA1.arrivee_lead_crm.kanban_masque', ['CADV62'], async ({ page, suivi }) => {
  const m = marque()
  const ids = []
  for (const x of ['Normal', 'Perdu', 'Oppose']) ids.push((await nouveauLead(page.request, `CADV62 ${m} ${x}`)).id)
  // État d'essai : les trois en Relance (FOLLOW_UP), un perdu, un opposé.
  await py(`from apps.crm.models import Lead
from apps.crm import stages
Lead.objects.filter(pk__in=${JSON.stringify(ids)}).update(stage=stages.FOLLOW_UP)
Lead.objects.filter(pk=${ids[1]}).update(perdu=True)
Lead.objects.filter(pk=${ids[2]}).update(ne_plus_contacter=True)
sortie(1)`)
  const colonne = () => page.getByLabel(/^Étape Relance/)
  await page.goto(`/crm/leads?view=kanban&q=${encodeURIComponent(`CADV62 ${m}`)}`)
  await expect(colonne()).toHaveAttribute('aria-label', /1 lead$/, { timeout: 60_000 })
  await page.getByRole('button', { name: /^Filtres/ }).click()
  await page.getByRole('radio', { name: 'Avec perdus' }).click()
  await expect(colonne()).toHaveAttribute('aria-label', /3 leads$/)
  await expect(page, "l'écriture d'URL est débouncée à 300 ms").toHaveURL(/perdus=avec/)
  await page.reload()
  await expect(colonne(), "l'URL garde « Avec perdus »").toHaveAttribute('aria-label', /3 leads$/, { timeout: 60_000 })
  suivi.verifie(5)
})

// ── CADV74 — Froid en lot : le bouton exige la raison ────────────────────────────────────────────────
etape('PA1.qualification.froid_en_lot', ['CADV74'], async ({ page, suivi }) => {
  const m = marque()
  for (const x of ['A', 'B', 'C']) await nouveauLead(page.request, `CADV74 ${m} ${x}`)
  await ouvrirListe(page, `CADV74 ${m}`)
  for (const x of ['A', 'B', 'C']) await caseLead(page, `${m} ${x}`).click()
  await page.getByRole('button', { name: 'Étape', exact: true }).click()
  const panneau = page.locator('.bulk-panel')
  await expect(panneau.getByRole('combobox', { name: 'Raison de mise au Froid' }), 'autre étape : pas de sélecteur').toHaveCount(0)
  await panneau.getByRole('combobox').first().click()
  await page.getByRole('option', { name: 'Froid' }).click()
  const raison = panneau.getByRole('combobox', { name: 'Raison de mise au Froid' })
  await expect(raison).toBeVisible()
  const appliquer = panneau.getByRole('button', { name: 'Appliquer' })
  await expect(appliquer, 'inactif sans raison').toBeDisabled()
  await raison.click()
  await page.getByRole('option').first().click()
  await expect(appliquer, 'actif avec la raison').toBeEnabled()
  const [rq] = await Promise.all([
    page.waitForRequest((r) => r.url().includes('/crm/leads/bulk/') && r.method() === 'POST', T),
    appliquer.click(),
  ])
  const corps = rq.postDataJSON()
  expect(corps.stage).toBe('COLD')
  expect(corps.parc_raison, 'la raison part avec').toBeTruthy()
  suivi.verifie(5)
})

// ── CADV88 — « Standby échus » au cockpit, en jours ouvrés ───────────────────────────────────────────
etape('PA1.cadence_contact.standby_echus', ['CADV88'], async ({ page, suivi }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `CADV88 ${m}`)
  // État daté du passé : seul le shell peut poser un Standby échu depuis 2 semaines.
  await py(`from apps.crm.models import Lead
Lead.objects.filter(pk=${l.id}).update(owner=U.objects.get(username='demo_admin'), parc_etat='standby', parc_raison='plus_tard_date', parc_jusqu_au=timezone.localdate() - datetime.timedelta(days=14))
sortie(1)`)
  const api = await lireJson(await page.request.get(`${API}/crm/relance-etapes/controle/?jours=14`, T), 'contrôle')
  const ligne = api.exceptions.standby_echus.lignes.find((x) => x.lead === l.id)
  expect(ligne, 'la ligne est servie').toBeTruthy()
  expect(ligne.depuis_jours_ouvres, 'des jours ouvrés').toBeGreaterThan(5)
  await page.goto('/crm/cockpit')
  await page.getByRole('button', { name: 'Voir le détail' }).first().click({ timeout: 60_000 })
  const bloc = page.getByTestId('controle-exception-standby_echus')
  await expect(bloc).toBeVisible({ timeout: 60_000 })
  await expect(bloc).toContainText('Standby échus')
  await expect(page.getByTestId('controle-total-standby_echus')).toHaveText(String(api.exceptions.standby_echus.total))
  if (!(await bloc.getByText(`CADV88 ${m}`).count())) await bloc.getByRole('button').first().click()
  const vue = bloc.getByTestId('controle-exception-ligne').filter({ hasText: `CADV88 ${m}` })
  await expect(vue).toContainText(`échu depuis ${ligne.depuis_jours_ouvres} jours ouvrés`, { timeout: 30_000 })
  await expect(vue).toContainText(ligne.owner_nom)
  await py(`from apps.crm.models import Lead
Lead.objects.filter(pk=${l.id}).update(parc_etat=None, parc_raison=None, parc_jusqu_au=None)
sortie(1)`)
  suivi.verifie(5)
})

// ── CADV105 — file « À prendre » : un simple membre prend un lead neuf ───────────────────────────────
etape('PA1.arrivee_formulaire_web.a_prendre', ['CADV105'], async ({ page, context, suivi, testInfo }) => {
  const m = marque()
  const nom = `cadv105_${m}`
  const l1 = await nouveauLead(page.request, `CADV105 ${m} Un`)
  const l2 = await nouveauLead(page.request, `CADV105 ${m} Deux`)
  const asmaa = await sessionEssai(testInfo, nom, 4, context)
  await py(`from apps.crm.dispatch import echeance_pour
from apps.crm.models import Lead
from apps.crm.models_clients import AttributionEnAttente, EquipeCommerciale
u = U.objects.get(username=${JSON.stringify(nom)})
e = EquipeCommerciale.objects.create(company_id=1, nom='CADV105 ${m}', actif=True, file_a_prendre=True, responsable=U.objects.get(username='demo_admin'))
e.membres.add(u)
for pk in (${l1.id}, ${l2.id}):
    Lead.objects.filter(pk=pk).update(owner=e.responsable)  # en attente : le lead reste chez le responsable (sinon « déjà décidé »)
    AttributionEnAttente.objects.create(company_id=1, lead=Lead.objects.get(pk=pk), equipe=e, proposee=None, raison='essai', echeance=echeance_pour(e, timezone.now()))
sortie(e.pk)`)
  await page.goto('/crm/attribution')
  const file = page.getByTestId('file-a-prendre')
  await expect(file).toContainText(`CADV105 ${m} Un`, { timeout: 60_000 })
  await file.getByRole('listitem').filter({ hasText: `CADV105 ${m} Un` }).getByRole('button', { name: 'Je le prends' }).click()
  await expect(file.getByRole('status')).toContainText(`Pris par vous : CADV105 ${m} Un`, { timeout: 30_000 })
  await expect(file.getByRole('listitem').filter({ hasText: `CADV105 ${m} Un` })).toHaveCount(0)
  await page.reload()
  await expect(page.getByTestId('file-a-prendre')).toContainText(`CADV105 ${m} Deux`, { timeout: 60_000 })
  await expect(page.getByTestId('file-a-prendre').getByRole('listitem').filter({ hasText: `CADV105 ${m} Un` }), 'relu : plus dans la file').toHaveCount(0)
  // Le serveur : le lead pris appartient à Asmaa ; un second clic reçoit 409.
  const me = await lireJson(await asmaa.get(`${API}/auth/me/`, T), 'moi')
  expect((await leadRelu(asmaa, l1.id)).owner).toBe(me.id)
  expect((await asmaa.post(`${API}/crm/dispatch/${l1.id}/attribuer/`, { ...T, data: { owner: me.id } })).status(), 'second arrivé : 409').toBe(409)
  // À l'écran : un autre a pris le 2e lead pendant qu'Asmaa regardait : « Déjà pris » sans casser la liste.
  await page.request.post(`${API}/crm/dispatch/${l2.id}/attribuer/`, { ...T, data: { owner: me.id } })
  suivi.attendre(new RegExp(`/crm/dispatch/${l2.id}/attribuer/`), 409)
  await page.getByTestId('file-a-prendre').getByRole('listitem').filter({ hasText: `CADV105 ${m} Deux` }).getByRole('button', { name: 'Je le prends' }).click()
  await expect(page.getByText('Déjà pris').first()).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('file-a-prendre')).toBeVisible()
  suivi.verifie(5)
})

// ── CADV83 — « prix révisable au-delà » sur la ligne de validité, FR et AR, 3 pages ──────────────────
etape('PA1.proposal.validite', ['CADV83'], async ({ page, suivi }) => {
  const m = marque()
  const l = await nouveauLead(page.request, `CADV83 ${m}`, { type_installation: 'residentiel', facture_hiver: '800' })
  const pan = await lireJson(await page.request.post(`${API}/stock/produits/`, { ...T, data: { nom: `Panneau mono 550W ${m}`, prix_vente: '1000.00', prix_achat: '432.10' } }), 'panneau')
  const ond = await lireJson(await page.request.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur réseau 10kW ${m}`, prix_vente: '10000.00', prix_achat: '4321.09' } }), 'onduleur')
  const brouillon = await lireJson(await page.request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: l.id, mode_installation: 'residentiel',
      lignes: [
        { produit: pan.id, designation: pan.nom, quantite: '10', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 },
        { produit: ond.id, designation: ond.nom, quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 1 },
      ],
    },
  }), 'devis')
  await lireJson(await page.request.post(`${API}/ventes/devis/${brouillon.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  const d = await lireJson(await page.request.get(`${API}/ventes/devis/${brouillon.id}/`, T), 'devis relu')
  const pdf = async (q) => {
    const r = await page.request.get(`${API}/ventes/devis/${d.id}/proposal/${q}`, T)
    expect(r.ok(), `/proposal${q} (${r.status()})`).toBeTruthy()
    return r.body()
  }
  const [a, mm, j] = d.date_validite.split('-')
  const fr = await pdf('')
  const texteFr = (await textePdf(fr)).replace(/\s+/g, ' ').replace(/[’']/g, "'")
  expect(texteFr).toContain(`Validité : jusqu'au ${j}/${mm}/${a} · prix révisable au-delà`)
  expect(await nombrePagesPdf(fr), 'FR : 3 pages').toBe(3)
  expect(texteFr, "jamais le prix d'achat").not.toContain('4321')
  const ar = await pdf('?langue=ar')
  const texteAr = (await textePdf(ar)).replace(/\s+/g, ' ')
  expect(texteAr, 'AR : la date du devis').toContain(`${j}/${mm}/${a}`)
  expect(await nombrePagesPdf(ar), 'AR : 3 pages').toBe(3)
  expect(texteAr, "AR : la phrase n'est plus en français").not.toContain('prix révisable')
  suivi.verifie(6)
  suivi.verifie(7)
})

// ── CADV112 — escalade direction J+14 et annulation à l'acompte reçu ─────────────────────────────────
etape('PA1.generique.escalade_acompte', ['CADV112'], async ({ page, suivi }) => {
  const m = marque()
  // Passage préalable : les devis acceptés d'avant sont déjà escaladés (idempotent), la nôtre est la seule neuve en tête de cloche.
  await py(`from apps.crm.cadence_filet import traiter_chaine_acceptation
sortie(traiter_chaine_acceptation(timezone.now() + datetime.timedelta(days=14)))`)
  const l = await nouveauLead(page.request, `CADV112 ${m} Villa`)
  const d = await devisEnvoye(page.request, l.id, 'CADV112')
  await accepterDevis(page.request, d.id, `Client ${m}`)
  const passer = () => py(`from apps.crm.cadence_filet import traiter_chaine_acceptation
sortie(traiter_chaine_acceptation(timezone.now() + datetime.timedelta(days=14)))`)
  const un = await passer()
  expect(un.escalades, 'au moins la nôtre').toBeGreaterThanOrEqual(1)
  const marqueur = async (lid) => listeDe(await lireJson(await page.request.get(`${API}/crm/leads/${lid}/historique/`, T), 'chatter')).filter((h) => /Acompte non reçu à J\+14/.test(h.body || ''))
  expect(await marqueur(l.id), 'une ligne marqueur').toHaveLength(1)
  await passer()
  expect(await marqueur(l.id), 'second passage : aucune de plus').toHaveLength(1)
  // La cloche de la direction (demo_admin).
  const titre = `Acompte non reçu à J+14 — ${l.nom}`
  const notifs = listeDe(await lireJson(await page.request.get(`${API}/notifications/notifications/?page_size=100`, T), 'notifications'))
  expect(notifs.filter((n) => n.title === titre), 'UNE notification').toHaveLength(1)
  await page.goto('/dashboard')
  await page.getByRole('button', { name: /^Notifications \(/ }).first().click()
  await expect(page.getByText(titre).first(), 'la cloche la montre').toBeVisible({ timeout: 30_000 })
  // Acompte RÉELLEMENT payé (facture d'acompte émise puis encaissée) : pas d'escalade, chaîne annulée.
  const l2 = await nouveauLead(page.request, `CADV112 ${m} Payee`)
  const d2 = await devisEnvoye(page.request, l2.id, 'CADV112b')
  await accepterDevis(page.request, d2.id, `Client ${m} P`)
  const ac = await lireJson(await page.request.post(`${API}/ventes/devis/${d2.id}/facturer/`, { ...T, data: { nature: 'acompte', emettre: true } }), 'acompte émis')
  const facture = await lireJson(await page.request.get(`${API}/ventes/factures/${ac.facture.id}/`, T), 'facture')
  await lireJson(await page.request.post(`${API}/ventes/factures/${facture.id}/enregistrer-paiement/`, {
    ...T, data: { montant: facture.montant_du ?? facture.total_ttc, date_paiement: new Date().toISOString().slice(0, 10), mode: 'virement', reference: `CADV112-${m}` },
  }), 'paiement')
  await passer()
  const ch = (await touches(page.request, l2.id)).filter((e) => e.libelle === 'Confirmer la signature et la suite' || e.libelle === 'Acompte : relancer le client')
  for (const e of ch.filter((x) => x.statut !== 'faite')) {
    expect(e.statut, e.libelle).toBe('annulee')
    expect(e.note).toBe('acompte reçu')
  }
  expect(await marqueur(l2.id), "pas d'escalade").toHaveLength(0)
  suivi.verifie(5)
})
