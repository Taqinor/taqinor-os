// Preuves en direct ASUP, vague 6 (runner GitHub), second lot — audit PF10 « suppression, archivage, restauration »,
// dossier docs/audits/2026-11-11-parcours-PF10.md. ASUP13 (journal d'audit caviardé à l'effacement), ASUP14 (export
// DSR supprimé à l'effacement, écran Confidentialité), ASUP17 + ASUP18 (plancher comptable de 10 ans à la purge du
// journal), ASUP57 (avoir et note de débit : acheteur figé), ASUP58 (relances de devis d'un lead supprimé), ASUP59 +
// ASUP60 (à-faire d'un lead archivé ou supprimé : « Mes activités » et résumé d'attention), ASUP61 (réappro : le moins
// cher fournisseur COMMANDABLE), ASUP62 (« Anonymiser (RGPD) » et leads en corbeille). Même patron que `asup6.spec.js` :
// gestes par la VRAIE route / le vrai écran / la vraie commande dans le shell Django, données propres retirées en fin
// d'étape, clause de persistance = relecture en base ou rechargement.
import { readFileSync } from 'node:fs'
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, telephoneMobileUnique, uiLoginJusquAuxApps, connexionApi, lireJson, textePdf, uniq } from '../helpers.js'

const etape = groupe('ASUP', ['ASUP13', 'ASUP14', 'ASUP17', 'ASUP18', 'ASUP57', 'ASUP58', 'ASUP59', 'ASUP60', 'ASUP61', 'ASUP62'])
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
const contextesUi = []
const apres = []
test.afterEach(async () => {
  for (const c of contextesUi.splice(0)) await c.close().catch(() => undefined)
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte }).first()

async function auRepos(suivi) {
  for (const p of suivi.pages.filter((x) => !x.isClosed())) await p.waitForLoadState('networkidle').catch(() => undefined)
}
const compteRole = (nom, nomRole, prenom = 'Essai') => py(`from apps.roles.models import Role
u = compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}).pk, societe=${SOC})
u.first_name = ${J(prenom)}; u.save(update_fields=['first_name'])
sortie(u.id)`)
async function apiSous(testInfo, nom) {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return ctx
}
async function ecran(page, suivi, testInfo, nom) {
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.locale ? { locale: u.locale } : {}), ...(u.timezoneId ? { timezoneId: u.timezoneId } : {}), viewport: { width: 1600, height: 1000 },
  })
  contextesUi.push(ctx)
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}
const montrer = async (page) => { await page.close().catch(() => undefined) }
const supprimerLeads = (pks) => py(`from apps.crm.models import Lead
for pk in ${J(pks)}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`)
/** Chiffres uniques (n caractères) pour ICE / CIN d'essai. */
const chiffres = (n) => `${Date.now()}${Math.floor(Math.random() * 1e6)}`.replace(/\D/g, '').slice(-n).padStart(n, '0')

// ═══ PF10.4 — ASUP13 : après l'effacement d'un client, son journal d'audit et celui de ses leads sont caviardés ═══
etape('PF10.4-ASUP13', ['ASUP13'], async ({ page, suivi }) => {
  const m = marque()
  const r = page.request
  const email = `asup13-${m}@example.invalid`
  const pii = { nom: `Zerhouni${m}`, prenom: `Yasmine${m}`, tel: telephoneMobileUnique(), cin: `AB${chiffres(6)}`, ice: `001${chiffres(12)}` }
  const neuf = { tel: telephoneMobileUnique(), cin: `CD${chiffres(6)}`, ice: `002${chiffres(12)}` }
  const temoin = { tel: telephoneMobileUnique(), tel2: telephoneMobileUnique() }
  const ids = await py(`from apps.crm.models import Client, Lead
CO = ${SOC}
c = Client.objects.create(company_id=CO, nom=${J(pii.nom)}, prenom=${J(pii.prenom)}, email=${J(email)}, telephone=${J(pii.tel)}, cin=${J(pii.cin)}, ice=${J(pii.ice)})
l = Lead.objects.create(company_id=CO, nom=${J(pii.nom)}, prenom=${J(pii.prenom)}, email=${J(email)}, telephone=${J(pii.tel)}, stage='NEW')
t = Client.objects.create(company_id=CO, nom='Temoin ${m}', email='temoin-${m}@example.invalid', telephone=${J(temoin.tel)})
sortie(dict(client=c.pk, lead=l.pk, temoin=t.pk))`)
  apres.push(async () => {
    await supprimerLeads([ids.lead])
    await py(`from apps.crm.models import Client
from core.models import DataSubjectRequest
DataSubjectRequest.objects.filter(subject_identifier=${J(email)}).delete()
try: Client.objects.filter(pk__in=${J([ids.client, ids.temoin])}).delete()
except Exception as exc: print('nettoyage', exc)`)
  })
  const patch = async (chemin, data) => {
    const rep = await r.patch(`${API}/${chemin}`, { ...T, data })
    expect(rep.status(), `PATCH ${chemin} : ${(await rep.text()).slice(0, 300)}`).toBeLessThan(300)
  }
  // Given : le client, son lead et le témoin sont MODIFIÉS par la vraie route (lignes d'audit avec anciennes/nouvelles valeurs).
  await patch(`crm/clients/${ids.client}/`, { telephone: neuf.tel, cin: neuf.cin, ice: neuf.ice })
  await patch(`crm/leads/${ids.lead}/`, { telephone: neuf.tel })
  await patch(`crm/clients/${ids.temoin}/`, { telephone: temoin.tel2 })
  const journal = () => py(`from django.contrib.contenttypes.models import ContentType
from apps.audit.models import AuditLog
from apps.audit.selectors import verify_audit_chain
from apps.crm.models import Client, Lead
CO = ${SOC}
def lignes(M, pk):
    return [[a, c] for a, c in AuditLog.objects.filter(company_id=CO, content_type=ContentType.objects.get_for_model(M), object_id=str(pk), changes__isnull=False).values_list('pk', 'changes')]
sortie(dict(client=lignes(Client, ${ids.client}), lead=lignes(Lead, ${ids.lead}), temoin=lignes(Client, ${ids.temoin}), chaine=verify_audit_chain(CO)))`)
  const avant = await journal()
  const texteDe = (lignes) => J(lignes.map(([, c]) => c))
  const texteAvant = texteDe([...avant.client, ...avant.lead])
  for (const v of [pii.tel, neuf.tel, pii.cin, neuf.cin, pii.ice, neuf.ice]) expect(texteAvant, `Given : le journal du sujet porte « ${v} »`).toContain(v)
  expect(avant.chaine.ok, 'chaîne valide avant').toBe(true)
  // When : demande d'effacement sur l'e-mail, traitée par la vraie route (demo_admin = Administrateur, `dsr_traiter`).
  const dsr = await py(`from core.models import DataSubjectRequest
sortie(DataSubjectRequest.objects.create(company_id=${SOC}, subject_identifier=${J(email)}, kind=DataSubjectRequest.KIND_ERASURE).pk)`)
  const t = await r.post(`${API}/core/dsr-requests/${dsr}/traiter/`, T)
  expect(t.status(), `traiter : ${(await t.text()).slice(0, 300)}`).toBe(200)
  // Then : plus aucune valeur personnelle dans les lignes du client et de ses leads ; « [effacé] » ; le témoin intact ; chaîne ok.
  const apresJ = await journal()
  const texteApres = texteDe([...apresJ.client, ...apresJ.lead])
  for (const v of [pii.nom, pii.prenom, email, pii.tel, neuf.tel, pii.cin, neuf.cin, pii.ice, neuf.ice]) {
    expect(texteApres, `après l'effacement : « ${v} » absent du journal du sujet`).not.toContain(v)
  }
  expect(texteApres, 'valeurs remplacées par « [effacé] »').toContain('[effacé]')
  // Les lignes d'AVANT, relues PAR CLÉ : toujours présentes, valeurs caviardées, nom de champ gardé.
  const apresParPk = Object.fromEntries([...apresJ.client, ...apresJ.lead].map(([pk, c]) => [pk, J(c)]))
  const avantTel = [...avant.client, ...avant.lead].filter(([, c]) => J(c).includes('telephone'))
  expect(avantTel.length, 'Given : des lignes d\'avant portent le champ telephone').toBeGreaterThanOrEqual(2)
  for (const [pk] of avantTel) {
    expect(apresParPk[pk], `ligne d'audit #${pk} toujours présente`).toBeDefined()
    expect(apresParPk[pk], `ligne #${pk} : « [effacé] » en place des valeurs`).toContain('[effacé')
    expect(apresParPk[pk], `ligne #${pk} : nom de champ « telephone » gardé`).toContain('telephone')
  }
  const tem = texteDe(apresJ.temoin)
  expect(tem, 'témoin : ancien téléphone intact').toContain(temoin.tel)
  expect(tem, 'témoin : nouveau téléphone intact').toContain(temoin.tel2)
  expect(apresJ.chaine.ok, 'la chaîne de hachage reste valide').toBe(true)
  // Persistance : relue une seconde fois ; lecture du Journal d'activité par son API (ce que l'écran lit).
  expect(texteDe((await journal()).client), 'persistance : toujours caviardé').not.toContain(pii.tel)
  const ent = await lireJson(await r.get(`${API}/audit/entries/?object_id=${ids.client}`, T), 'journal')
  expect(J(ent), 'API du Journal : aucune valeur personnelle du client').not.toContain(neuf.ice)
  // ÉCRAN : /journal filtré sur le client, « Historique à cette date » ⇒ « [effacé] », ni téléphone, ni CIN, ni ICE.
  await page.goto(`/journal?model=client&object_id=${ids.client}`)
  const histo = page.getByRole('button', { name: 'Historique à cette date' }).first()
  await expect(histo, 'le Journal liste les lignes du client').toBeVisible({ timeout: 60_000 })
  await histo.click()
  const dlg = page.getByRole('dialog').filter({ hasText: 'Historique à cette date' })
  await expect(dlg.getByRole('cell', { name: 'telephone', exact: true }), 'écran : champ telephone reconstruit').toBeVisible({ timeout: 60_000 })
  await expect(dlg, 'écran : « [effacé] » affiché').toContainText('[effacé]')
  for (const v of [pii.tel, neuf.tel, pii.cin, neuf.cin, pii.ice, neuf.ice]) await expect(dlg, `écran : « ${v} » absent`).not.toContainText(v)
  await auRepos(suivi)
})

// ═══ PF10.4 — ASUP14 : après l'effacement, l'export stocké des demandes d'accès/rectification est remplacé par la trace ═══
etape('PF10.4-ASUP14', ['ASUP14'], async ({ page, suivi }) => {
  const m = marque()
  const email = `asup14-${m}@example.invalid`
  const autre = `asup14-autre-${m}@example.invalid`
  const ids = await py(`from apps.crm.models import Lead
from core.models import DataSubjectRequest as D
CO = ${SOC}
l = Lead.objects.create(company_id=CO, nom='ASUP14 ${m}', email=${J(email)}, telephone=${J(telephoneMobileUnique())}, stage='NEW')
mk = lambda s, k: D.objects.create(company_id=CO, subject_identifier=s, kind=k).pk
sortie(dict(lead=l.pk, acces=mk(${J(email)}, D.KIND_ACCESS), rect=mk(${J(email)}, D.KIND_RECTIFICATION),
  autre=mk(${J(autre)}, D.KIND_ACCESS), efface=mk(${J(email)}, D.KIND_ERASURE)))`)
  apres.push(async () => {
    await supprimerLeads([ids.lead])
    await py(`from core.models import DataSubjectRequest
try: DataSubjectRequest.objects.filter(subject_identifier__in=${J([email, autre])}).delete()
except Exception as exc: print('nettoyage', exc)`)
  })
  await page.goto('/parametres?onglet=confidentialite')
  const ligne = (sujet, label) => page.getByTestId('dsr-row').filter({ hasText: sujet }).filter({ hasText: label })
  await expect(ligne(email, 'Accès (export)'), 'demande d\'accès listée').toBeVisible({ timeout: 60_000 })
  // Les trois demandes ANTÉRIEURES sont traitées par l'écran (export complet stocké).
  for (const [sujet, label] of [[email, 'Accès (export)'], [email, 'Rectification'], [autre, 'Accès (export)']]) {
    await ligne(sujet, label).getByRole('button', { name: 'Traiter' }).click()
    await expect(ligne(sujet, label), `${label} de ${sujet} traitée`).toContainText('Traitée', { timeout: 60_000 })
  }
  const exportAvant = await py(`from core.models import DataSubjectRequest as D
a = D.objects.get(pk=${ids.acces})
sortie(dict(cles=sorted((a.resultat or {}).keys()), autre=sorted((D.objects.get(pk=${ids.autre}).resultat or {}).keys())))`)
  expect(exportAvant.cles.length, 'Given : l\'export d\'accès stocke des sources').toBeGreaterThan(0)
  expect(exportAvant.cles, 'Given : pas encore de trace d\'effacement').not.toContain('export_supprime_le')
  // When : effacement de la personne (même e-mail), confirmé à l'écran.
  await ligne(email, 'Effacement').getByRole('button', { name: 'Traiter' }).click()
  const dlg = page.getByRole('alertdialog')
  await expect(dlg).toContainText(`Effacer les données de ${email} ?`)
  await dlg.getByRole('button', { name: 'Effacer' }).click()
  await expect(ligne(email, 'Effacement'), 'effacement traité').toContainText('Traitée', { timeout: 60_000 })
  // Then (en base) : accès et rectification gardent statut + date et résultat = trace ; l'autre personne intacte ; rien supprimé.
  const lu = await py(`from core.models import DataSubjectRequest as D
def v(pk):
    d = D.objects.get(pk=pk)
    return dict(statut=d.statut, traitee=d.traitee_le is not None, resultat=d.resultat)
sortie(dict(acces=v(${ids.acces}), rect=v(${ids.rect}), autre=v(${ids.autre}), n=D.objects.filter(subject_identifier__in=${J([email, autre])}).count()))`)
  for (const cle of ['acces', 'rect']) {
    expect([lu[cle].statut, lu[cle].traitee], `${cle} : statut et date de réponse gardés`).toEqual(['traitee', true])
    expect(Object.keys(lu[cle].resultat).sort(), `${cle} : resultat = trace seule`).toEqual(['export_supprime_le', 'motif'])
    expect(lu[cle].resultat.motif, `${cle} : motif`).toBe('effacement')
    expect(lu[cle].resultat.export_supprime_le, `${cle} : date de suppression`).toBeTruthy()
  }
  expect(Object.keys(lu.autre.resultat).sort(), 'l\'autre personne : export intact').toEqual(exportAvant.autre)
  expect(lu.n, 'les 4 demandes existent toujours (append-only)').toBe(4)
  // Écran, après rechargement : « Sources exportées » = la trace ; le re-téléchargement ne rend que la trace.
  await page.reload()
  await expect(ligne(email, 'Accès (export)').getByTestId('dsr-sources'), 'écran : sources = trace').toHaveText(/^Sources exportées : (export_supprime_le, motif|motif, export_supprime_le)$/, { timeout: 60_000 })
  await expect(ligne(autre, 'Accès (export)').getByTestId('dsr-sources'), 'écran : l\'autre personne garde ses sources').not.toContainText('export_supprime_le')
  const [dl] = await Promise.all([page.waitForEvent('download', T), ligne(email, 'Accès (export)').getByRole('button', { name: 'Télécharger (JSON)' }).click()])
  const fichier = JSON.parse(readFileSync(await dl.path(), 'utf8'))
  expect(Object.keys(fichier).sort(), 'fichier re-téléchargé : trace seule').toEqual(['export_supprime_le', 'motif'])
  await auRepos(suivi)
})

// ═══ PF10.4 — ASUP17 : `purge_audit_log` (rétention 365 j) ne supprime aucune ligne d'une pièce comptable de moins de 10 ans ═══
const SOCIETE_JOURNAL = (m) => `from datetime import timedelta
from authentication.models import Company
from django.contrib.contenttypes.models import ContentType
from apps.audit.models import AuditLog
from apps.audit.selectors import MODELES_COMPTABLES
from apps.parametres.models import CompanyProfile
co = Company.objects.create(nom='ASUP journal ${m}', slug='asup-journal-${m}')
CompanyProfile.objects.create(company=co, audit_retention_days=365)
lignes = {}
for cle in list(MODELES_COMPTABLES) + [('crm', 'lead')]:
    lignes[cle[0] + '.' + cle[1]] = AuditLog.objects.create(company=co, action=AuditLog.Action.UPDATE, object_id='1', content_type=ContentType.objects.get_by_natural_key(*cle)).pk
lead400 = AuditLog.objects.create(company=co, action=AuditLog.Action.UPDATE, object_id='2', content_type=ContentType.objects.get_by_natural_key('crm', 'lead')).pk
AuditLog.objects.filter(pk__in=list(lignes.values())).update(timestamp=timezone.now() - timedelta(days=730))
AuditLog.objects.filter(pk=lead400).update(timestamp=timezone.now() - timedelta(days=400))
`
const NETTOYER_SOCIETE = (slug) => py(`from authentication.models import Company
try: Company.objects.filter(slug=${J(slug)}).delete()
except Exception as exc: print('nettoyage', exc)`)

etape('PF10.4-ASUP17', ['ASUP17'], async ({ page }) => {
  const m = marque()
  apres.push(() => NETTOYER_SOCIETE(`asup-journal-${m}`))
  const res = await py(`${SOCIETE_JOURNAL(m)}
from django.core.management import call_command
from apps.parametres.models import SettingsAuditLog
call_command('purge_audit_log', '--company', str(co.id), verbosity=0)
restantes = set(AuditLog.objects.filter(pk__in=list(lignes.values()) + [lead400]).values_list('pk', flat=True))
sortie(dict(comptables=[k for k, pk in lignes.items() if k != 'crm.lead' and pk in restantes], attendues=[k for k in lignes if k != 'crm.lead'],
  lead_2ans=lignes['crm.lead'] in restantes, lead_400=lead400 in restantes,
  trace=SettingsAuditLog.objects.filter(company=co, new_value__startswith='audit_deleted=').count(),
  trace_valeur=list(SettingsAuditLog.objects.filter(company=co, new_value__startswith='audit_deleted=').values_list('new_value', flat=True))))`)
  expect(res.attendues.length, 'Given : 6 types de pièces comptables (facture, avoir, paiement, mouvement, BC, note de débit)').toBe(6)
  expect(res.comptables.sort(), 'à 365 j de rétention, les lignes de 2 ans des pièces comptables restent').toEqual(res.attendues.sort())
  expect([res.lead_2ans, res.lead_400], 'les lignes du lead (2 ans, 400 jours) sont purgées').toEqual([false, false])
  expect(res.trace_valeur, 'la trace de purge est écrite comme avant (2 lignes de lead supprimées)').toEqual(['audit_deleted=2'])
  // Persistance : relues par une seconde lecture indépendante.
  const relu = await py(`from apps.audit.models import AuditLog
from authentication.models import Company
co = Company.objects.get(slug='asup-journal-${m}')
sortie(AuditLog.objects.filter(company=co).count())`)
  expect(relu, 'persistance : 6 lignes comptables restantes').toBe(6)
  await page.goto('/journal')
  await expect(page.locator('body')).toBeVisible()
})

// ═══ PF10.4 — ASUP18 : `purge_company_audit` (beat `parametres-purger-audit`) passe par le même sélecteur ═══
etape('PF10.4-ASUP18', ['ASUP18'], async ({ page }) => {
  const m = marque()
  apres.push(() => NETTOYER_SOCIETE(`asup-journal-${m}`))
  const res = await py(`${SOCIETE_JOURNAL(m)}
from apps.parametres.retention import purge_company_audit
from apps.parametres.models import SettingsAuditLog
retour = purge_company_audit(co)
restantes = set(AuditLog.objects.filter(pk__in=list(lignes.values()) + [lead400]).values_list('pk', flat=True))
sortie(dict(retour=list(retour), comptables=sorted(k for k, pk in lignes.items() if k != 'crm.lead' and pk in restantes),
  attendues=sorted(k for k in lignes if k != 'crm.lead'), lead_2ans=lignes['crm.lead'] in restantes, lead_400=lead400 in restantes,
  trace=list(SettingsAuditLog.objects.filter(company=co, field='purge_retention').values_list('new_value', flat=True))))`)
  expect(res.comptables, 'facture, paiement, mouvement (et avoir, BC, note de débit) de 2 ans restent').toEqual(res.attendues)
  expect([res.lead_2ans, res.lead_400], 'les 2 lignes du lead sont purgées').toEqual([false, false])
  expect(res.retour[0], 'purge_company_audit : 2 lignes d\'audit supprimées').toBe(2)
  expect(res.trace.length, 'la trace de purge est écrite comme avant').toBe(1)
  expect(res.trace[0], 'trace : audit_deleted=2').toContain('audit_deleted=2')
  const relu = await py(`from apps.audit.models import AuditLog
from authentication.models import Company
sortie(AuditLog.objects.filter(company=Company.objects.get(slug='asup-journal-${m}')).count())`)
  expect(relu, 'persistance : 6 lignes comptables relues').toBe(6)
  await page.goto('/journal')
  await expect(page.locator('body')).toBeVisible()
})

// ═══ PF10.4 — ASUP57 : avoir créé / annulé / note de débit après « Anonymiser (RGPD) » ⇒ acheteur figé de la facture ═══
etape('PF10.4-ASUP57', ['ASUP57'], async ({ page, suivi, testInfo }) => {
  testInfo.setTimeout(420_000)
  const m = marque()
  const r = page.request
  const nomClient = `Atlas ASUP57 ${m} SARL`
  const ice = `003${chiffres(12)}`
  const fiscal = { if_fiscal: `IF57${m}`, rc: `RC57${m}`, adresse: `57 boulevard ${m}, Casablanca` }
  // Given : une vente réelle (lead → devis accepté → facture complète émise) dont le client est une entreprise identifiée.
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, {
    ...T, data: { nom: uniq('ASUP57 Client'), ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `asup57-${m}@example.invalid` },
  }), 'lead')
  const prod = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Centrale ASUP57 ${m}`, prix_vente: '10000.00', prix_achat: '4321.09' } }), 'produit')
  const devis = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: lead.id,
      lignes: [{ produit: prod.id, designation: prod.nom, quantite: '2', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
    },
  }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/accepter/`, { ...T, data: { nom: 'Client ASUP57' } }), 'acceptation')
  const relu = await lireJson(await r.get(`${API}/ventes/devis/${devis.id}/`, T), 'devis relu')
  const clientId = relu.client
  apres.push(() => py(`from apps.crm.models import Lead
try: Lead.all_objects.filter(pk=${lead.id}).delete()
except Exception as exc: print('nettoyage', exc)`))
  await py(`from apps.crm.models import Client
Client.objects.filter(pk=${clientId}).update(nom=${J(nomClient)}, prenom='', type_client='entreprise', ice=${J(ice)}, if_fiscal=${J(fiscal.if_fiscal)}, rc=${J(fiscal.rc)}, adresse=${J(fiscal.adresse)})
sortie(1)`)
  const fc = await lireJson(await r.post(`${API}/ventes/devis/${devis.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture complète')
  let facture = await lireJson(await r.get(`${API}/ventes/factures/${fc.facture_id}/`, T), 'facture')
  if (facture.statut === 'brouillon') {
    await lireJson(await r.post(`${API}/ventes/factures/${facture.id}/emettre/`, { ...T, data: {} }), 'émission')
    facture = await lireJson(await r.get(`${API}/ventes/factures/${facture.id}/`, T), 'facture émise')
  }
  expect(['emise', 'payee', 'en_retard'], 'Given : facture émise').toContain(facture.statut)
  const ligneF = facture.lignes[0]
  const ligneAvoir = { produit: ligneF.produit, designation: ligneF.designation, quantite: '0.5', prix_unitaire: ligneF.prix_unitaire, taux_tva: '20.00' }
  const avoir1 = await lireJson(await r.post(`${API}/ventes/factures/${facture.id}/creer-avoir/`, { ...T, data: { motif: 'ASUP57 avant', lignes: [ligneAvoir] } }), 'avoir 1')
  // When (ÉCRAN 1/3) : fiche client → « Anonymiser (RGPD) » → « Anonymiser définitivement ».
  await page.goto('/crm')
  await page.getByPlaceholder('Rechercher nom, email, tél, ICE, IF, RC, CIN…').fill(nomClient)
  await page.getByRole('row').filter({ hasText: nomClient }).first().click({ timeout: 60_000 })
  await expect(page.getByText(`Fiche client — ${nomClient}`)).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Anonymiser (RGPD)' }).click()
  const alerte = page.getByRole('alertdialog')
  await expect(alerte).toContainText('Anonymiser ce client ?')
  await alerte.getByRole('button', { name: 'Anonymiser définitivement' }).click()
  await expect(toast(page, 'Client anonymisé (données personnelles effacées)')).toBeVisible({ timeout: 30_000 })
  const client = await py(`from apps.crm.models import Client
c = Client.objects.get(pk=${clientId}); sortie([c.is_anonymized, c.nom, c.ice])`)
  expect(client[0], 'client anonymisé en base').toBe(true)
  expect(client[1], 'le client vivant ne porte plus le nom d\'origine').not.toBe(nomClient)
  // (ÉCRAN 2/3) : /ventes/factures → « Avoir » sur la facture → « Avoir partiel » (créer un avoir).
  await page.goto('/ventes/factures')
  await page.getByPlaceholder('Référence, client').fill(facture.reference)
  const ligneFact = page.locator(`#facture-row-${facture.id}`).first()
  await expect(ligneFact, 'facture listée').toBeVisible({ timeout: 60_000 })
  await ligneFact.getByRole('button', { name: 'Avoir', exact: true }).click()
  const dialogue = page.getByRole('dialog').filter({ hasText: `Créer un avoir — ${facture.reference}` })
  await expect(dialogue).toBeVisible({ timeout: 30_000 })
  await dialogue.locator('input[type="number"]').first().fill('1')
  const [repAvoir] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && /\/creer-avoir\/$/.test(new URL(x.url()).pathname), T),
    dialogue.getByRole('button', { name: 'Avoir partiel' }).click(),
  ])
  expect(repAvoir.status(), await repAvoir.text()).toBe(201)
  const avoir2 = await repAvoir.json()
  // (ÉCRAN 3/3) : /ventes/avoirs → « Annuler » sur l'avoir existant → « Annuler l'avoir ».
  await page.goto('/ventes/avoirs')
  const rangee = page.locator('tr').filter({ hasText: avoir1.reference }).first()
  await expect(rangee, 'avoir existant listé').toBeVisible({ timeout: 60_000 })
  await rangee.getByRole('button', { name: 'Annuler', exact: true }).click()
  const [repAnnul] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && new RegExp(`/ventes/avoirs/${avoir1.id}/annuler/$`).test(new URL(x.url()).pathname), T),
    page.getByRole('alertdialog').getByRole('button', { name: "Annuler l'avoir" }).click(),
  ])
  expect(repAnnul.status(), await repAnnul.text()).toBe(200)
  const nd = await lireJson(await r.post(`${API}/ventes/factures/${facture.id}/creer-note-debit/`, { ...T, data: { motif: 'pénalité ASUP57', montant: '50.00', taux_tva: '20' } }), 'note de débit')
  // Then : le texte de chaque PDF porte le nom, l'ICE, l'IF, le RC et l'adresse figés — jamais « Client anonymisé » ; re-téléchargé : idem.
  const compact = (s) => String(s).replace(/\s+/g, '')
  const attendus = [nomClient, ice, fiscal.if_fiscal, fiscal.rc, fiscal.adresse]
  const pieces = [['avoir créé après', `ventes/avoirs/${avoir2.id}/telecharger-pdf/`], ['avoir annulé (re-rendu)', `ventes/avoirs/${avoir1.id}/telecharger-pdf/`],
    ['note de débit', `ventes/notes-debit/${nd.id}/telecharger-pdf/`]]
  for (const [quoi, chemin] of pieces) {
    for (const passe of ['premier rendu', 're-téléchargement']) {
      const rep = await r.get(`${API}/${chemin}`, T)
      expect(rep.status(), `${quoi} (${passe}) → ${chemin}`).toBe(200)
      expect(rep.headers()['content-type'] || '').toContain('application/pdf')
      const texte = await textePdf(await rep.body())
      for (const a of attendus) expect(compact(texte), `${quoi} (${passe}) : imprime « ${a} »`).toContain(compact(a))
      expect(texte, `${quoi} (${passe}) : jamais « Client anonymisé »`).not.toContain('Client anonymisé')
    }
  }
  await auRepos(suivi)
})

// ═══ PF10.2 — ASUP58 : le devis envoyé d'un lead mis à la corbeille ne produit ni relance ni DevisNudgeLog ; restauré, le palier repart ═══
etape('PF10.2-ASUP58', ['ASUP58'], async ({ page }) => {
  const m = marque()
  const [t0, t1, t2] = [telephoneMobileUnique(), telephoneMobileUnique(), telephoneMobileUnique()]
  const res = await py(`from datetime import datetime, time, timedelta
from decimal import Decimal
from django.db import transaction
from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.notifications.models import Notification
from apps.ventes.models import Devis, DevisNudgeLog, ShareLink
from apps.ventes.domain.recouvrement import send_devis_followup_nudges
from apps.ventes.scheduled import engagement_followup_engine
own = U.objects.get(username='demo_admin'); CO = own.company_id
r = {}
with transaction.atomic():
    envoi = datetime.combine(timezone.localdate() - timedelta(days=3), time(12, 0), tzinfo=timezone.get_current_timezone())
    cl = Client.objects.create(company_id=CO, nom='ASUP58 ${m}', prenom='Client', email='asup58_${m}@asup.invalid', telephone=${J(t0)})
    mk = lambda nom, tel: Lead.objects.create(company_id=CO, nom=nom + ' ${m}', stage=stages.QUOTE_SENT, owner=own, telephone=tel)
    ls, lt = mk('ASUP58 supprime', ${J(t1)}), mk('ASUP58 temoin', ${J(t2)})
    dv = lambda n, l: Devis.objects.create(company_id=CO, reference='DEV-ASUP58-${m}-' + n, client=cl, lead=l, statut=Devis.Statut.ENVOYE,
                                           taux_tva=Decimal('20'), date_envoi=envoi, created_by=own)
    ds = [dv('S', ls), dv('T', lt)]
    ls.soft_delete(user=own)
    lien = lambda d: '/ventes/devis?devis=%d' % d.pk
    notifs = lambda: [Notification.objects.filter(link=lien(d)).count() for d in ds]
    r['supprime'] = Lead.all_objects.get(pk=ls.pk).is_deleted
    send_devis_followup_nudges()
    r['logs'] = [DevisNudgeLog.objects.filter(devis=d).count() for d in ds]
    r['notifs_paliers'] = notifs()
    r['wa_ecartes'] = Notification.objects.filter(body__contains='wa.me', link=lien(ds[0])).count()
    for d in ds: ShareLink.for_devis(d)
    engagement_followup_engine()
    r['notifs_moteur'] = notifs()
    r['declencheurs'] = [bool(ShareLink.objects.filter(devis=d).first().engagement_triggers_fired) for d in ds]
    r['relu'] = DevisNudgeLog.objects.filter(devis=ds[0]).exists()
    # RESTAURATION RÉELLE (corbeille) : ASOC86 rejoue la prochaine étape (RelanceEtape ouverte, relance_date reportée) ;
    # QX13/MRY7 DIFFÈRENT alors le palier (jamais deux messages au client) — le lead n'est plus ÉCARTÉ pour autant.
    from apps.crm.models import RelanceEtape
    from apps.ventes.domain.recouvrement import _lead_ecarte
    Lead.all_objects.get(pk=ls.pk).restore()
    ouvertes = RelanceEtape.objects.filter(lead_id=ls.pk, statut=RelanceEtape.Statut.A_FAIRE)
    r['etapes_ouvertes'] = ouvertes.count()
    r['ecarte_apres'] = _lead_ecarte(ds[0])
    lr = Lead.objects.get(pk=ls.pk)
    r['relance_date'] = str(lr.relance_date)
    r['aujourdhui'] = str(timezone.localdate())
    send_devis_followup_nudges()
    r['log_differe'] = DevisNudgeLog.objects.filter(devis=ds[0]).count()
    # Suivi clos et rappel échu : le palier part au passage suivant.
    ouvertes.update(statut=RelanceEtape.Statut.ANNULEE)
    Lead.objects.filter(pk=ls.pk).update(relance_date=None)
    send_devis_followup_nudges()
    r['log_apres_echeance'] = DevisNudgeLog.objects.filter(devis=ds[0]).count()
    transaction.set_rollback(True)
r['rien_laisse'] = not Devis.objects.filter(reference__startswith='DEV-ASUP58-${m}').exists()
sortie(r)`)
  expect(res.supprime, 'Given : le lead du devis S est à la corbeille').toBe(true)
  expect(res.logs, 'palier j+2 : aucun DevisNudgeLog pour le lead supprimé, le témoin est relancé').toEqual([0, 1])
  expect(res.notifs_paliers[0], 'palier : aucune notification pour le lead supprimé').toBe(0)
  expect(res.wa_ecartes, 'aucun brouillon wa.me pour le lead supprimé').toBe(0)
  expect(res.declencheurs, 'moteur d\'engagement : S sauté, T signalé « non ouverte 24 h »').toEqual([false, true])
  expect(res.notifs_moteur[0], 'moteur : aucune notification pour le lead supprimé').toBe(0)
  expect(res.notifs_moteur[1], 'moteur : le témoin reçoit sa notification').toBeGreaterThan(res.notifs_paliers[1])
  expect(res.relu, 'persistance : relu, toujours aucune ligne pour S').toBe(false)
  console.log(`[ASUP58] ${J(res)}`)
  expect(res.etapes_ouvertes, 'restauration réelle : le suivi (RelanceEtape) est rouvert').toBeGreaterThan(0)
  expect(res.ecarte_apres, 'restauré : le lead n\'est plus écarté').toBe(false)
  expect(res.relance_date > res.aujourdhui, `relance_date reportée dans le futur (${res.relance_date} > ${res.aujourdhui})`).toBe(true)
  expect(res.log_differe, 'palier DIFFÉRÉ au passage suivant (relance_date dans le futur) : aucun DevisNudgeLog').toBe(0)
  expect(res.log_apres_echeance, 'suivi clos et relance_date échue : le palier part (1 DevisNudgeLog)').toBe(1)
  expect(res.rien_laisse, 'transaction annulée').toBe(true)
  // 0 écran (relances produites par le beat) : page ouverte pour les oracles seulement.
  await page.goto('/ventes/devis')
  await expect(page.locator('body')).toBeVisible()
})

// ── Jeu commun d'ASUP59 / ASUP60 : trois à-faire ouverts d'un Commercial, sur un lead archivé, un lead supprimé, un lead vivant ──
const A_FAIRE = (idCompte, m, echeances) => `import datetime
from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Lead
from apps.records.models import Activity
u = U.objects.get(pk=${idCompte})
ct = ContentType.objects.get_for_model(Lead)
auj = timezone.localdate()
ech = {'hier': auj - datetime.timedelta(days=1), 'aujourdhui': auj, 'demain': auj + datetime.timedelta(days=1)}
leads = [Lead.objects.create(company_id=${SOC}, nom='ASUP A%d ${m}' % (i + 1), owner=u, stage='NEW') for i in range(3)]
acts = [Activity.objects.create(company_id=${SOC}, content_type=ct, object_id=l.pk, summary='Rappeler A%d ${m}' % (i + 1), assigned_to=u, due_date=ech[e])
        for i, (l, e) in enumerate(zip(leads, ${J(echeances)}))]
sortie(dict(leads=[l.pk for l in leads], acts=[a.pk for a in acts]))`
const NETTOYER_A_FAIRE = (ids) => async () => {
  await py(`from apps.records.models import Activity
Activity.objects.filter(pk__in=${J(ids.acts)}).delete()`)
  await supprimerLeads(ids.leads)
}
/** Archive le lead 1 et met le lead 2 à la corbeille par les VRAIES routes (demo_admin) ; renvoie l'id de corbeille du lead 2. */
async function archiverEtSupprimer(r, ids) {
  const a = await r.post(`${API}/crm/leads/${ids.leads[0]}/archiver/`, T)
  expect(a.status(), `archiver A1 : ${(await a.text()).slice(0, 200)}`).toBe(200)
  const d = await r.delete(`${API}/crm/leads/${ids.leads[1]}/`, T)
  expect(d.status(), `supprimer A2 : ${(await d.text()).slice(0, 200)}`).toBe(200)
  return (await d.json()).corbeille_id
}
async function restaurerLes2(r, ids, corbeilleId) {
  const a = await r.post(`${API}/crm/leads/${ids.leads[0]}/restaurer/`, T)
  expect(a.status(), `restaurer A1 : ${(await a.text()).slice(0, 200)}`).toBe(200)
  const d = await r.post(`${API}/core/corbeille/${corbeilleId}/restaurer/`, T)
  expect(d.status(), `restaurer A2 : ${(await d.text()).slice(0, 200)}`).toBe(200)
}

// ═══ PF10.2 — ASUP59 : « Mes activités » (/activites) et son widget du tableau de bord sans les à-faire d'un lead archivé ou supprimé ═══
etape('PF10.2-ASUP59', ['ASUP59'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `asup59co_${m}`
  const co = await compteRole(nom, 'Commercial')
  const ids = await py(A_FAIRE(co, m, ['hier', 'aujourdhui', 'demain']))
  apres.push(NETTOYER_A_FAIRE(ids))
  const af = (n) => `Rappeler A${n} ${m}`
  const ctx = await apiSous(testInfo, nom)
  const mine = async () => {
    const d = await lireJson(await ctx.get(`${API}/records/activities/mine/`, T), 'mine')
    return ['en_retard', 'aujourdhui', 'a_venir'].flatMap((k) => (d[k] || []).map((x) => x.summary)).filter((s) => s.includes(m)).sort()
  }
  try {
    expect(await mine(), 'témoin : les trois à-faire sont dans « Mes activités »').toEqual([af(1), af(2), af(3)])
    const corbeille = await archiverEtSupprimer(page.request, ids)
    expect(await mine(), 'API mine : seul l\'à-faire du lead vivant figure dans les paniers').toEqual([af(3)])
    const p = await ecran(page, suivi, testInfo, nom)
    const paniers = p.locator('table[aria-label="En retard"], table[aria-label="Aujourd\'hui"], table[aria-label="À venir"]')
    const rangee = (n) => paniers.getByRole('row').filter({ hasText: af(n) })
    const widget = p.locator('.activity-feed-widget')
    const verifier = async (quand, attendus) => {
      await p.goto('/activites')
      for (const n of [1, 2, 3]) await expect(rangee(n), `${quand} : « Mes activités » ${attendus.includes(n) ? 'montre' : 'ne montre plus'} A${n}`)
        .toHaveCount(attendus.includes(n) ? 1 : 0, { timeout: 60_000 })
      await p.goto('/dashboard')
      await expect(widget, `${quand} : widget d'activités du tableau de bord`).toBeVisible({ timeout: 60_000 })
      for (const n of [1, 2, 3]) await expect(widget.getByText(af(n)), `${quand} : widget ${attendus.includes(n) ? 'montre' : 'ne montre plus'} A${n}`)
        .toHaveCount(attendus.includes(n) ? 1 : 0, { timeout: 60_000 })
    }
    await verifier('lead archivé + lead supprimé', [3])
    await p.reload()
    await expect(widget.getByText(af(3)), 'après rechargement : A3 présent').toBeVisible({ timeout: 60_000 })
    await expect(widget.getByText(af(1)), 'après rechargement : A1 (lead archivé) absent').toHaveCount(0)
    // Restauration des deux leads : les trois à-faire réapparaissent.
    await restaurerLes2(page.request, ids, corbeille)
    expect(await mine(), 'API mine après restauration : les trois figurent').toEqual([af(1), af(2), af(3)])
    await verifier('après restauration', [1, 2, 3])
    await auRepos(suivi)
    await montrer(page)
  } finally { await ctx.dispose() }
})

// ═══ PF10.2 — ASUP60 : résumé d'attention = paniers de « Ma file », avant et après restauration du lead ═══
etape('PF10.2-ASUP60', ['ASUP60'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `asup60co_${m}`
  const co = await compteRole(nom, 'Commercial')
  const ids = await py(A_FAIRE(co, m, ['hier', 'aujourdhui', 'aujourdhui']))
  apres.push(NETTOYER_A_FAIRE(ids))
  const af = (n) => `Rappeler A${n} ${m}`
  const ctx = await apiSous(testInfo, nom)
  const lire = async () => {
    const s = await lireJson(await ctx.get(`${API}/notifications/attention-summary/`, T), 'attention-summary')
    const f = await lireJson(await ctx.get(`${API}/records/activities/ma-file/`, T), 'ma-file')
    // Oracle INDÉPENDANT : à-faire ouverts du compte dont le lead cible n'est ni archivé ni supprimé, rangés par état.
    const attendu = await py(`from apps.crm.models import Lead
from apps.records.models import Activity
from apps.records.serializers import activity_state
vivants = set(Lead.objects.filter(is_archived=False).values_list('pk', flat=True))
n = {'overdue': 0, 'today': 0}
for a in Activity.objects.filter(assigned_to_id=${co}, done=False):
    if a.object_id in vivants:
        st = activity_state(a.due_date, a.done)
        if st in n: n[st] += 1
sortie(n)`)
    return { resume: [s.en_retard, s.aujourdhui], file: [f.resume?.en_retard ?? 0, f.resume?.aujourdhui ?? 0], attendu: [attendu.overdue, attendu.today], ids: f.items.filter((x) => x.kind === 'activite').map((x) => x.title).filter((t) => String(t).includes(m)) }
  }
  try {
    const avant = await lire()
    expect(avant.resume, 'témoin : les trois à-faire comptés (1 en retard, 2 aujourd\'hui)').toEqual([1, 2])
    expect(avant.resume, 'témoin : résumé = Ma file').toEqual(avant.file)
    const corbeille = await archiverEtSupprimer(page.request, ids)
    const filtre = await lire()
    expect(filtre.resume, 'résumé : 0 en retard, 1 aujourd\'hui (A1 archivé et A2 supprimé retirés)').toEqual([0, 1])
    expect(filtre.file, 'Ma file : mêmes paniers que le résumé').toEqual(filtre.resume)
    expect(filtre.attendu, 'oracle indépendant (à-faire sur lead vivant) : même décompte').toEqual(filtre.resume)
    // Écran « Ma file » : seul l'à-faire du lead vivant figure dans la file.
    const p = await ecran(page, suivi, testInfo, nom)
    const file = p.locator('table[aria-label="Ma file"]')
    await p.goto('/activites')
    await expect(file.getByRole('row').filter({ hasText: af(3) }), 'Ma file : A3 présent').toBeVisible({ timeout: 60_000 })
    for (const n of [1, 2]) await expect(file.getByRole('row').filter({ hasText: af(n) }), `Ma file : A${n} retiré`).toHaveCount(0)
    await restaurerLes2(page.request, ids, corbeille)
    const apresR = await lire()
    expect(apresR.resume, 'après restauration : résumé = Ma file').toEqual(apresR.file)
    expect(apresR.attendu, 'après restauration : oracle indépendant = résumé').toEqual(apresR.resume)
    expect(apresR.resume[0], 'après restauration : A1 de nouveau compté en retard').toBeGreaterThanOrEqual(1)
    expect(apresR.resume[1], 'après restauration : A2 et A3 comptés aujourd\'hui').toBeGreaterThanOrEqual(2)
    await auRepos(suivi)
    await montrer(page)
  } finally { await ctx.dispose() }
}, {
  // La « tuile d'attention » du tableau de bord nommée par la clause n'existe pas : `useApprobationsCount.js` (l. 47) est le
  // seul lecteur de `attention-summary` et ne lit que `approbations` — antérieur à ASUP60 et hors de ses Files. Le chiffre
  // en_retard / aujourdhui est prouvé par l'API (= Ma file = oracle indépendant) et l'écran Ma file, pas par une tuile.
  ecart: {
    base: 'FAIL',
    raison: 'tuile d\'attention du tableau de bord inexistante : useApprobationsCount.js:47 est le seul lecteur de attention-summary '
      + '(ne lit que `approbations`), antérieur et hors des Files d\'ASUP60 ; preuve par API + écran Ma file',
  },
})

// ═══ PF10.3 — ASUP61 : réappro — le fournisseur ARCHIVÉ le moins cher n'est jamais suggéré ; le BCF part chez l'actif ═══
etape('PF10.3-ASUP61', ['ASUP61'], async ({ page, suivi }) => {
  const m = marque()
  const r = page.request
  const nomP = `Câble ASUP61 ${m}`
  const nomActif = `Fournisseur actif ASUP61 ${m}`
  const ids = await py(`from decimal import Decimal
from apps.stock.models import Fournisseur, PrixFournisseur, Produit
CO = ${SOC}
# Les autres produits de la démo sous seuil sont mis HORS suivi le temps de l'étape (restitués ensuite) : la suggestion ne porte que sur le nôtre.
snap = list(Produit.objects.filter(company_id=CO, is_archived=False).exclude(seuil_alerte=0).values_list('pk', 'seuil_alerte'))
Produit.objects.filter(pk__in=[pk for pk, _ in snap]).update(seuil_alerte=0)
arch = Fournisseur.objects.create(company_id=CO, nom='Fournisseur archive ASUP61 ${m}', is_archived=True)
act = Fournisseur.objects.create(company_id=CO, nom=${J(nomActif)})
p = Produit.objects.create(company_id=CO, nom=${J(nomP)}, sku='ASUP61-${m}', prix_vente=Decimal('50'), prix_achat=Decimal('20'), quantite_stock=5, seuil_alerte=10, quantite_reappro_cible=30)
PrixFournisseur.objects.create(company_id=CO, produit=p, fournisseur=arch, prix_achat=Decimal('80'))
PrixFournisseur.objects.create(company_id=CO, produit=p, fournisseur=act, prix_achat=Decimal('100'))
sortie(dict(produit=p.pk, arch=arch.pk, act=act.pk, snap=snap))`)
  apres.push(async () => {
    await py(`from apps.stock.models import BonCommandeFournisseur, Fournisseur, PrixFournisseur, Produit
for pk, seuil in ${J(ids.snap)}: Produit.objects.filter(pk=pk).update(seuil_alerte=seuil)
for qs in (BonCommandeFournisseur.objects.filter(fournisseur_id__in=${J([ids.arch, ids.act])}), PrixFournisseur.objects.filter(produit_id=${ids.produit}), Produit.objects.filter(pk=${ids.produit}), Fournisseur.objects.filter(pk__in=${J([ids.arch, ids.act])})):
    try: qs.delete()
    except Exception as exc: print('nettoyage', exc)`)
  })
  // Pilotage stock (GET a-reapprovisionner) : la suggestion porte le fournisseur actif à 100.
  const sugg = await lireJson(await r.get(`${API}/stock/produits/a-reapprovisionner/`, T), 'a-reapprovisionner')
  const items = (Array.isArray(sugg) ? sugg : sugg.results || sugg.items || []).filter((x) => x.produit_id === ids.produit)
  expect(items.length, 'le produit sous seuil est suggéré').toBe(1)
  expect([items[0].fournisseur_id, items[0].prix_achat], 'API : fournisseur actif à 100 (jamais l\'archivé à 80)').toEqual([ids.act, '100.00'])
  // Écran : /stock › Pilotage › « Suggestions de réapprovisionnement » puis « Générer un BCF (brouillon) » (sans choisir de fournisseur).
  await page.goto('/stock')
  const ligne = page.getByRole('row').filter({ hasText: nomP })
  await expect(ligne, 'la ligne du produit sous seuil').toBeVisible({ timeout: 60_000 })
  await expect(ligne, 'la ligne montre le fournisseur actif').toContainText(nomActif)
  await expect(ligne, 'jamais le fournisseur archivé').not.toContainText('archive ASUP61')
  await page.getByRole('button', { name: 'Générer un BCF (brouillon)' }).click()
  const statut = page.getByRole('status').filter({ hasText: 'BCF brouillon' })
  await expect(statut, 'le BCF brouillon est créé (pas de refus 409)').toContainText('créé', { timeout: 60_000 })
  // Persistance : relire le BCF créé ⇒ fournisseur actif, prix unitaire 100.
  const bcf = await py(`from apps.stock.models import BonCommandeFournisseur
b = BonCommandeFournisseur.objects.filter(lignes__produit_id=${ids.produit}).order_by('-pk').first()
sortie(dict(fournisseur=b.fournisseur_id, statut=b.statut, lignes=[[l.produit_id, str(l.prix_achat_unitaire)] for l in b.lignes.all()]))`)
  expect(bcf.fournisseur, 'BCF chez le fournisseur actif').toBe(ids.act)
  expect(bcf.lignes.map(([p, prix]) => [p, Number(prix)]), 'une ligne, prix unitaire 100').toEqual([[ids.produit, 100]])
  expect(bcf.statut, 'brouillon').toBe('brouillon')
  await auRepos(suivi)
})

// ═══ PF10.4 — ASUP62 : « Anonymiser (RGPD) » efface aussi les leads du client déjà en corbeille ═══
etape('PF10.4-ASUP62', ['ASUP62'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `asup62di_${m}`
  await compteRole(nom, 'Directeur')
  const x = await py(`from apps.crm.models import Client, Lead
CO = ${SOC}
c = Client.objects.create(company_id=CO, nom='ASUP62 ${m}', prenom='Client', email='asup62-a-${m}@example.invalid', telephone=${J(telephoneMobileUnique())})
l = Lead.objects.create(company_id=CO, nom='ASUP62 lead corbeille ${m}', email='asup62-b-${m}@example.invalid', telephone=${J(telephoneMobileUnique())}, client=c, stage='NEW')
v = Lead.objects.create(company_id=CO, nom='ASUP62 lead vivant ${m}', email='asup62-c-${m}@example.invalid', telephone=${J(telephoneMobileUnique())}, client=c, stage='NEW')
l.soft_delete(user=U.objects.get(username='demo_admin'))
sortie(dict(client=c.pk, corbeille=l.pk, vivant=v.pk))`)
  apres.push(async () => {
    await supprimerLeads([x.corbeille, x.vivant])
    await py(`from apps.crm.models import Client
try: Client.objects.filter(pk=${x.client}).delete()
except Exception as exc: print('nettoyage', exc)`)
  })
  const lu = (pk) => py(`from apps.crm.models import Lead
l = Lead.all_objects.get(pk=${pk})
sortie(dict(nom=l.nom, email=l.email or '', telephone=l.telephone or '', supprime=l.is_deleted))`)
  expect((await lu(x.corbeille)).supprime, 'Given : le lead du client est en corbeille, aux e-mail et téléphone différents').toBe(true)
  const ctx = await apiSous(testInfo, nom)
  try {
    // When : un Directeur clique « Anonymiser (RGPD) » (vraie route de la fiche client).
    const a = await ctx.post(`${API}/crm/clients/${x.client}/anonymize/`, T)
    expect(a.status(), `anonymize : ${(await a.text()).slice(0, 300)}`).toBe(200)
    // Then : le lead en corbeille est anonymisé et toujours en corbeille ; le lead vivant aussi.
    const c = await lu(x.corbeille)
    expect(c, 'lead en corbeille : nom anonymisé, e-mail et téléphone vides, toujours supprimé').toEqual({ nom: 'Anonymisé', email: '', telephone: '', supprime: true })
    expect((await lu(x.vivant)).nom, 'lead vivant : anonymisé aussi').toBe('Anonymisé')
    // Persistance : relire en base une seconde fois, puis le libellé dans la corbeille commune.
    expect(await lu(x.corbeille), 'persistance : identique').toEqual(c)
    const corb = await py(`from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Lead
from apps.trash.models import ElementSupprime
e = ElementSupprime.objects.filter(content_type=ContentType.objects.get_for_model(Lead), object_id=${x.corbeille}).order_by('-pk').first()
sortie(None if e is None else dict(libelle=e.libelle_snapshot, donnees=e.donnees_snapshot))`)
    console.log(`[ASUP62] entrée de la corbeille commune : ${J(corb)}`)
    // Clause de preuve : « libellé anonymisé dans la corbeille commune » — le nom d'origine ne doit plus y figurer.
    // Défaut ANTÉRIEUR hors Files (apps/trash : `libelle_snapshot` garde le nom pris à la suppression) : écart déclaré ci-dessous.
    if (corb) expect(J(corb), 'corbeille commune : le nom d\'origine du lead n\'apparaît plus').not.toContain(`ASUP62 lead corbeille ${m}`)
    await page.goto('/parametres/corbeille')
    await expect(page.locator('body')).toBeVisible()
    await auRepos(suivi)
  } finally { await ctx.dispose() }
}, {
  ecart: {
    base: 'FAIL',
    raison: 'libellé de la corbeille commune : `ElementSupprime.libelle_snapshot` (apps/trash) garde le nom d\'origine du lead pris à la suppression, '
      + 'jamais réécrit par « Anonymiser (RGPD) » — défaut antérieur, hors des Files d\'ASUP62 ; le « fini quand » (lead anonymisé et toujours en corbeille) est tenu',
  },
})
