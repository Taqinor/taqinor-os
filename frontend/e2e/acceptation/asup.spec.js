// Preuves en direct du groupe ASUP (audit PF10 « suppression, archivage, restauration », dossier
// docs/audits/2026-11-11-parcours-PF10.md) : chaque étape joue le geste par la VRAIE route (comptes du rôle
// livré connectés par /token/) ou, quand la tâche nomme une commande / un beat, par le vrai code dans le shell
// Django ; données propres créées puis retirées ; clause de persistance = relecture en base après le geste.
// Sonde hôte du constat rejouée quand elle s'exécute encore (`repro` attendu faux) ; une sonde dont les
// bouchons sont périmés par le correctif est NOMMÉE dans les notes, jamais comptée comme preuve.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, textePdf, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ASUP', ['ASUP1', 'ASUP2', 'ASUP3', 'ASUP12', 'ASUP7', 'ASUP9', 'ASUP41', 'ASUP43', 'ASUP46'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`

/** Rejoue une sonde HÔTE du dossier (`docs/audits/sondes/ASUP/<c>.py`) ; renvoie {ok, res|err}. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'ASUP', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}

/** Compte d'essai du rôle LIVRÉ `nomRole` dans la société démo, connecté par /token/ ; {ctx, id}. */
async function session(testInfo, nom, nomRole) {
  const id = await py(`from apps.roles.models import Role
u = compte(${JSON.stringify(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${JSON.stringify(nomRole)}).pk, societe=${SOC})
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return { ctx, id }
}

// Fabrique Python commune : client ENTREPRISE complet + factures (statut, sans instantané) de la société démo.
const FABRIQUE = `
from decimal import Decimal
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture
CO = ${SOC}
def client_pro(m, **extra):
    d = dict(company_id=CO, nom='ASUP SARL ' + m, prenom='', type_client='entreprise', ice=str(int.from_bytes(m.encode(), 'big') % 10**15).rjust(15, '0'),
             if_fiscal='IF-' + m, rc='RC-' + m, adresse='12 rue ' + m + ', Casablanca', email=m + '@asup.invalid')
    d.update(extra)
    return Client.objects.create(**d)
def facture(cl, ref, statut):
    p, _ = Produit.objects.get_or_create(company_id=CO, sku='ASUP-ACCEPT', defaults={'nom': 'Centrale ASUP', 'prix_vente': Decimal('1000')})
    f = Facture.objects.create(company_id=CO, reference=ref, client=cl, statut=statut, taux_tva=Decimal('20'))
    LigneFacture.objects.create(facture=f, produit=p, designation='Centrale', quantite=Decimal('1'), prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
    return f
def nettoyer(client_ids):
    for f in Facture.objects.filter(client_id__in=client_ids):
        LigneFacture.objects.filter(facture=f).delete()
        f.delete()
    Client.objects.filter(pk__in=client_ids).delete()
`

etape('PF10.4-ASUP1', ['ASUP1'], async ({ page }) => {
  // Given/When/Then de la tâche, dans une transaction ANNULÉE : `figer_identite_acheteur` porte sur toutes les
  // sociétés ; le rejeu ne laisse rien derrière lui (persistance relue DANS la transaction, après --appliquer).
  const m = marque()
  const res = await py(`${FABRIQUE}
from io import StringIO
from django.core.management import call_command
from django.db import transaction
from apps.crm.dsr_provider import anonymiser_client
from apps.ventes.domain.instantanes_facture import acheteur_de_la_facture
def jouer(*a):
    out = StringIO(); call_command('figer_identite_acheteur', *a, stdout=out); return out.getvalue()
r = {}
with transaction.atomic():
    cl = client_pro('${m}')
    cibles = [facture(cl, 'FAC-ASUP1-${m}-' + s, s) for s in ('emise', 'payee', 'en_retard', 'annulee')]
    brouillon = facture(cl, 'FAC-ASUP1-${m}-brouillon', 'brouillon')
    figee = facture(cl, 'FAC-ASUP1-${m}-figee', 'emise')
    Facture.objects.filter(pk=figee.pk).update(identite_acheteur={'nom': 'Fige', 'ice': 'ICE-FIGE'})
    perdu = Client.objects.create(company_id=CO, nom='Deja anonymise ${m}', is_anonymized=True)
    perdue = facture(perdu, 'FAC-ASUP1-${m}-perdue', 'emise')
    dry = jouer()
    avant, _, apres = dry.partition('identité déjà perdue')
    r['dry_liste'] = [f.reference for f in cibles if (f.reference + ' | ASUP SARL ${m} | ' + f.statut) in avant]
    r['dry_perdue_a_part'] = ('FAC-ASUP1-${m}-perdue' in apres) and ('FAC-ASUP1-${m}-perdue' not in avant)
    r['dry_ignore'] = [x for x in ('FAC-ASUP1-${m}-brouillon', 'FAC-ASUP1-${m}-figee') if x in dry]
    r['dry_sans_ecriture'] = not Facture.objects.filter(pk__in=[f.pk for f in cibles], identite_acheteur__isnull=False).exists()
    jouer('--appliquer')
    r['ice_figes'] = [ (Facture.objects.get(pk=f.pk).identite_acheteur or {}).get('ice') for f in cibles ]
    r['brouillon'] = Facture.objects.get(pk=brouillon.pk).identite_acheteur
    r['perdue'] = Facture.objects.get(pk=perdue.pk).identite_acheteur
    r['figee'] = Facture.objects.get(pk=figee.pk).identite_acheteur
    ice = cl.ice
    anonymiser_client(cl.company, cl, motif='t')
    r['apres_anonymisation'] = [[a.nom, a.ice, a.if_fiscal, a.rc, a.adresse] for a in (acheteur_de_la_facture(Facture.objects.get(pk=f.pk)) for f in cibles)]
    r['attendu'] = ['ASUP SARL ${m}', ice, 'IF-${m}', 'RC-${m}', '12 rue ${m}, Casablanca']
    r['rejeu'] = [f.reference for f in cibles if f.reference in jouer()]
    r['jamais_reecrit'] = [ (Facture.objects.get(pk=f.pk).identite_acheteur or {}).get('ice') for f in cibles ]
    transaction.set_rollback(True)
r['rien_laisse'] = not Facture.objects.filter(reference__startswith='FAC-ASUP1-${m}').exists()
sortie(r)`)
  expect(res.dry_liste, 'dry-run : « référence | client | statut » des 4 non brouillon').toHaveLength(4)
  expect(res.dry_perdue_a_part, 'dry-run : facture du client anonymisé sous « identité déjà perdue »').toBe(true)
  expect(res.dry_ignore, 'dry-run : brouillon et facture figée jamais listés').toEqual([])
  expect(res.dry_sans_ecriture, 'dry-run : aucune écriture').toBe(true)
  expect(new Set(res.ice_figes).size === 1 && res.ice_figes[0] === res.attendu[1], `--appliquer fige les 4 (${res.ice_figes})`).toBe(true)
  expect([res.brouillon, res.perdue], 'brouillon et identité perdue inchangés').toEqual([null, null])
  expect(res.figee, 'facture déjà figée jamais réécrite').toEqual({ nom: 'Fige', ice: 'ICE-FIGE' })
  for (const a of res.apres_anonymisation) expect(a, 'acheteur après « Anonymiser » : nom, ICE, IF, RC, adresse d\'origine').toEqual(res.attendu)
  expect(res.rejeu, 'rejoué : rien listé').toEqual([])
  expect(res.jamais_reecrit, 'persistance : relue après rejeu, identique').toEqual(res.ice_figes)
  expect(res.rien_laisse, 'transaction annulée').toBe(true)
  await page.goto('/ventes/factures')
  await expect(page.locator('body')).toBeVisible()
})

etape('PF10.4-ASUP2', ['ASUP2'], async ({ page, testInfo }) => {
  const m = marque()
  const ids = await py(`${FABRIQUE}
cl = client_pro('${m}', telephone='${telephoneMobileUnique()}')
e = facture(cl, 'FAC-ASUP2-${m}', 'emise'); b = facture(cl, 'FAC-ASUP2-${m}-br', 'brouillon')
cl2 = client_pro('${m}b')
e2 = facture(cl2, 'FAC-ASUP2-${m}-dsr', 'emise')
sortie(dict(client=cl.pk, emise=e.pk, brouillon=b.pk, ice=cl.ice, client2=cl2.pk, emise2=e2.pk, ice2=cl2.ice, email2=cl2.email))`)
  try {
    const di = await session(testInfo, `asup2di_${m}`, 'Directeur')
    // 1) Le Directeur clique « Anonymiser (RGPD) » : la vraie route.
    const r = await di.ctx.post(`${API}/crm/clients/${ids.client}/anonymize/`, T)
    expect(r.status(), `anonymize : ${(await r.text()).slice(0, 300)}`).toBe(200)
    // Persistance : relecture en base.
    const lu = await py(`from apps.crm.models import Client
from apps.ventes.models import Facture
c = Client.objects.get(pk=${ids.client})
sortie(dict(anonymise=c.is_anonymized, ice_client=c.ice, emise=Facture.objects.get(pk=${ids.emise}).identite_acheteur, brouillon=Facture.objects.get(pk=${ids.brouillon}).identite_acheteur))`)
    expect(lu.anonymise, 'client anonymisé comme avant').toBe(true)
    expect(lu.ice_client || '', 'ICE du client vidé').toBe('')
    expect(lu.emise?.ice, 'facture émise : instantané = identité d\'avant').toBe(ids.ice)
    expect(lu.brouillon, 'brouillon : toujours sans instantané').toBeNull()
    // 2) Le PDF de la facture émise imprime encore l'acheteur (nom, ICE, IF, RC, adresse).
    const pdf = await di.ctx.get(`${API}/facturation/factures/${ids.emise}/telecharger-pdf/`, T)
    expect(pdf.status(), `PDF facture : ${pdf.status()}`).toBe(200)
    const texte = (await textePdf(await pdf.body())).replace(/\s+/g, ' ')
    const compact = texte.replace(/\s/g, '')
    for (const attendu of [`ASUP SARL ${m}`, `IF-${m}`, `RC-${m}`, `12 rue ${m}, Casablanca`]) {
      expect(compact, `PDF imprime « ${attendu} »`).toContain(attendu.replace(/\s/g, ''))
    }
    expect(compact, 'PDF imprime l\'ICE d\'origine').toContain(ids.ice)
    expect(texte, 'PDF : jamais « Client anonymisé » comme acheteur').not.toContain('Client anonymisé')
    // 3) Second cas : une demande d'effacement (`erase_crm`) fige aussi d'abord.
    const dsr = await py(`from apps.crm.dsr_provider import erase_crm
from apps.crm.models import Client
from apps.ventes.models import Facture
from authentication.models import Company
n = erase_crm(Company.objects.get(pk=${SOC}), '${ids.email2}')
sortie(dict(n=n, anonymise=Client.objects.get(pk=${ids.client2}).is_anonymized, fige=(Facture.objects.get(pk=${ids.emise2}).identite_acheteur or {}).get('ice')))`)
    expect(dsr.anonymise, `erase_crm a anonymisé le client (n=${dsr.n})`).toBe(true)
    expect(dsr.fige, 'erase_crm : facture émise figée avec l\'ICE d\'origine').toBe(ids.ice2)
    await di.ctx.dispose()
    await page.goto('/ventes/factures')
    await expect(page.locator('body')).toBeVisible()
  } finally {
    await py(`${FABRIQUE}
nettoyer([${ids.client}, ${ids.client2}])`)
  }
})

etape('PF10.4-ASUP3', ['ASUP3'], async ({ page, testInfo }) => {
  const m = marque()
  const ids = await py(`${FABRIQUE}
from core.models import DataSubjectRequest
from core import dsr
cl = client_pro('${m}')
f = facture(cl, 'FAC-ASUP3-${m}', 'emise')
d = DataSubjectRequest.objects.create(company_id=CO, subject_identifier=cl.email, kind=DataSubjectRequest.KIND_ERASURE)
sortie(dict(client=cl.pk, facture=f.pk, demande=d.pk, ice=cl.ice, gardes=sorted(dsr.list_erasure_guards())))`)
  try {
    expect(ids.gardes, 'registre des gardes').toContain('pieces_legales_sans_identite_figee')
    const di = await session(testInfo, `asup3di_${m}`, 'Directeur')
    const url = `${API}/core/dsr-requests/${ids.demande}/traiter/`
    const r1 = await di.ctx.post(url, T)
    const c1 = await r1.text()
    expect(r1.status(), `1er traiter : ${c1.slice(0, 300)}`).toBe(409)
    expect(c1, 'motif : référence de la facture').toContain(`FAC-ASUP3-${m}`)
    expect(c1, 'motif : la commande à jouer').toContain('figer_identite_acheteur')
    const intact = await py(`from apps.crm.models import Client
c = Client.objects.get(pk=${ids.client}); sortie([c.is_anonymized, c.ice])`)
    expect(intact, 'aucun fournisseur appelé : client intact').toEqual([false, ids.ice])
    await py(`from io import StringIO
from django.core.management import call_command
call_command('figer_identite_acheteur', '--appliquer', stdout=StringIO())`)
    const r2 = await di.ctx.post(url, T)
    expect(r2.status(), `2e traiter : ${(await r2.text()).slice(0, 300)}`).toBe(200)
    const apres = await py(`from apps.crm.models import Client
from apps.ventes.models import Facture
c = Client.objects.get(pk=${ids.client})
sortie([c.is_anonymized, (Facture.objects.get(pk=${ids.facture}).identite_acheteur or {}).get('ice')])`)
    expect(apres, 'effacement exécuté, identité figée gardée').toEqual([true, ids.ice])
    await di.ctx.dispose()
    await page.goto('/parametres')
    await expect(page.locator('body')).toBeVisible()
  } finally {
    await py(`${FABRIQUE}
from core.models import DataSubjectRequest
DataSubjectRequest.objects.filter(pk=${ids.demande}).delete()
nettoyer([${ids.client}])`)
  }
})

etape('PF10.4-ASUP12', ['ASUP12'], async ({ page, testInfo }) => {
  const s = sondeHote('C-ASUP-008')
  expect(s.ok, `sonde C-ASUP-008 exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde C-ASUP-008 : ${JSON.stringify(s.res.observe)}`).toBe(false)
  const m = marque()
  const tel = telephoneMobileUnique()
  const ids = await py(`${FABRIQUE}
from authentication.models import Company
from apps.calepinage.models import Calepinage
from apps.crm.models import Lead
from apps.ventes.models import EmailLog
cl = client_pro('${m}', type_client='particulier', nom='Jean ${m}', telephone='${tel}', ice='')
l1 = Lead.objects.create(company_id=CO, nom='Jean ${m}', client=cl, telephone='${tel}', gps_lat='33.5731', gps_lng='-7.5898')
l2 = Lead.objects.create(company_id=CO, nom='Jean archive ${m}', client=cl, email='arch_${m}@asup.invalid', is_archived=True)
mail = EmailLog.objects.create(company_id=CO, client=cl, direction='sortant', statut='envoye', to_email=cl.email, corps='Bonjour Jean ${m}')
cal = Calepinage.objects.create(company_id=CO, client_id=cl.pk, titre='12 rue ${m}, Casablanca')
autre = Company.objects.create(nom='ASUP autre ${m}', slug='asup-autre-${m}')
ailleurs = Lead.objects.create(company=autre, nom='Ailleurs ${m}', telephone='${tel}')
sortie(dict(client=cl.pk, leads=[l1.pk, l2.pk], mail=mail.pk, cal=cal.pk, autre=autre.pk, ailleurs=ailleurs.pk))`)
  try {
    const di = await session(testInfo, `asup12di_${m}`, 'Directeur')
    const r = await di.ctx.post(`${API}/crm/clients/${ids.client}/anonymize/`, T)
    expect(r.status(), `anonymize : ${(await r.text()).slice(0, 300)}`).toBe(200)
    const lu = await py(`from apps.calepinage.models import Calepinage
from apps.crm.models import Lead, Client
from apps.ventes.models import EmailLog
leads = [Lead.all_objects.get(pk=i) if hasattr(Lead, 'all_objects') else Lead.objects.get(pk=i) for i in ${JSON.stringify(ids.leads)}]
mail = EmailLog.objects.get(pk=${ids.mail}); cal = Calepinage.objects.get(pk=${ids.cal}); a = Lead.objects.get(pk=${ids.ailleurs})
sortie(dict(client=Client.objects.get(pk=${ids.client}).is_anonymized,
  leads=[[l.nom, l.telephone, l.email, l.gps_lat, l.gps_lng] for l in leads],
  mail=[mail.to_email, mail.corps], cal=cal.titre, ailleurs=[a.nom, bool(a.telephone)]))`)
    expect(lu.client, 'client anonymisé comme avant').toBe(true)
    for (const l of lu.leads) expect(l, 'lead du client (vivant et archivé) : plus de nom, téléphone, e-mail ni GPS').toEqual(['Anonymisé', null, null, null, null])
    expect(lu.mail, 'e-mail journalisé effacé').toEqual(['', ''])
    expect(lu.cal, 'calepinage : adresse effacée').toBe('')
    expect(lu.ailleurs, 'lead d\'une autre société intact').toEqual([`Ailleurs ${m}`, true])
    const r2 = await di.ctx.post(`${API}/crm/clients/${ids.client}/anonymize/`, T)
    expect(r2.status(), '409 inchangé si déjà anonymisé').toBe(409)
    await di.ctx.dispose()
    // Écran : la fiche du lead anonymisé s'ouvre et n'affiche plus le nom.
    await page.goto(`/crm?id=${ids.leads[0]}`)
    await expect(page.locator('body')).toBeVisible()
    await expect(page.getByText(`Jean ${m}`)).toHaveCount(0)
  } finally {
    await py(`${FABRIQUE}
from authentication.models import Company
from apps.calepinage.models import Calepinage
from apps.crm.models import Lead
from apps.ventes.models import EmailLog
EmailLog.objects.filter(pk=${ids.mail}).delete(); Calepinage.objects.filter(pk=${ids.cal}).delete()
M = getattr(Lead, 'all_objects', Lead.objects)
for pk in ${JSON.stringify([...ids.leads, ids.ailleurs])}:
    try: M.filter(pk=pk).delete()
    except Exception: pass
try: Company.objects.filter(pk=${ids.autre}).delete()
except Exception: pass
nettoyer([${ids.client}])`)
  }
})

etape('PF10.1-ASUP7', ['ASUP7'], async ({ page, testInfo }) => {
  const s = sondeHote('C-ASUP-004')
  expect(s.ok, `sonde C-ASUP-004 exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde C-ASUP-004 : ${JSON.stringify(s.res.observe)}`).toBe(false)
  const m = marque()
  const ids = await py(`${FABRIQUE}
from django.utils import timezone
from datetime import date
from apps.installations.models import Installation
from apps.monitoring.models import ProductionReading, ProductionWarranty
cl = client_pro('${m}')
annee = timezone.localdate().year
i1 = Installation.objects.create(company_id=CO, reference='ASUP7-${m}-1', client=cl, puissance_installee_kwc=Decimal('10'))
g1 = ProductionWarranty.objects.create(company_id=CO, installation=i1, start_year=annee, guaranteed_year1_kwh=Decimal('12000'), degradation_pct_per_year=Decimal('0'))
ProductionReading.objects.create(company_id=CO, installation=i1, date=date(annee, 1, 1), period_days=1, energy_kwh=Decimal('40'))
i2 = Installation.objects.create(company_id=CO, reference='ASUP7-${m}-2', client=cl, puissance_installee_kwc=Decimal('10'))
g2 = ProductionWarranty.objects.create(company_id=CO, installation=i2, start_year=annee + 1, guaranteed_year1_kwh=Decimal('12000'), degradation_pct_per_year=Decimal('0'))
sortie(dict(client=cl.pk, inst=[i1.pk, i2.pk], g1=g1.pk, g2=g2.pk))`)
  try {
    // Le Technicien (rôle livré, `sav_gerer`) supprime par la vraie route.
    const te = await session(testInfo, `asup7te_${m}`, 'Technicien')
    const r1 = await te.ctx.delete(`${API}/monitoring/warranties/${ids.g1}/`, T)
    const c1 = await r1.text()
    expect(r1.status(), `garantie commencée + relevé : ${c1.slice(0, 300)}`).toBe(409)
    expect(c1, 'message nommé').toContain('Garantie en cours : modifiez-la ou clôturez-la, elle fonde la compensation due.')
    const r2 = await te.ctx.delete(`${API}/monitoring/warranties/${ids.g2}/`, T)
    expect(r2.status(), 'garantie à venir sans relevé : supprimée comme avant').toBe(204)
    const reste = await py(`from apps.monitoring.models import ProductionWarranty
sortie([ProductionWarranty.objects.filter(pk=${ids.g1}).exists(), ProductionWarranty.objects.filter(pk=${ids.g2}).exists()])`)
    expect(reste, 'persistance : la garantie en cours reste, l\'autre est partie').toEqual([true, false])
    await te.ctx.dispose()
    await page.goto('/production/garanties')
    await expect(page.locator('body')).toBeVisible()
  } finally {
    await py(`${FABRIQUE}
from apps.installations.models import Installation
from apps.monitoring.models import ProductionReading, ProductionWarranty
ProductionReading.objects.filter(installation_id__in=${JSON.stringify(ids.inst)}).delete()
ProductionWarranty.objects.filter(installation_id__in=${JSON.stringify(ids.inst)}).delete()
Installation.objects.filter(pk__in=${JSON.stringify(ids.inst)}).delete()
nettoyer([${ids.client}])`)
  }
})

etape('PF10.3-ASUP9', ['ASUP9'], async ({ page, testInfo }) => {
  const s = sondeHote('C-ASUP-006')
  expect(s.ok, `sonde C-ASUP-006 exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde C-ASUP-006 : ${JSON.stringify(s.res.observe)}`).toBe(false)
  const m = marque()
  const cr = await session(testInfo, `asup9cr_${m}`, 'Commercial responsable')
  const [ta, tb, tc, te] = [telephoneMobileUnique(), telephoneMobileUnique(), telephoneMobileUnique(), telephoneMobileUnique()]
  const ids = await py(`from apps.crm.models import Lead
from apps.crm.leads_fusion import merge_leads
own = U.objects.get(pk=${cr.id})
mk = lambda nom, tel, **k: Lead.objects.create(company_id=${SOC}, nom=nom + ' ${m}', telephone=tel, owner=own, stage='NEW', **k)
b = mk('Survivant', '${tb}')
a = mk('Absorbe', '${ta}', email='abs_${m}@asup.invalid')
merge_leads(b, [a], own)
a.refresh_from_db()
c = mk('Archive doublon', '${tc}', is_archived=True)
d = mk('Doublon vivant', '${tc}')
e = mk('Archive seul', '${te}', is_archived=True)
sortie(dict(a=a.pk, b=b.pk, c=c.pk, d=d.pk, e=e.pk, a_archive=a.is_archived))`)
  const etat = (pks) => py(`from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Lead, LeadActivity
from apps.records.models import Activity
ct = ContentType.objects.get_for_model(Lead)
sortie({str(pk): [Lead.all_objects.get(pk=pk).is_archived, LeadActivity.objects.filter(lead_id=pk).count(), Activity.objects.filter(content_type=ct, object_id=pk).count()] for pk in ${JSON.stringify(pks)}})`)
  try {
    expect(ids.a_archive, 'fusion : A archivé').toBe(true)
    const avant = await etat([ids.a, ids.c])
    // Le Commercial responsable (rôle livré) clique « Restaurer » : la vraie route.
    const ra = await cr.ctx.post(`${API}/crm/leads/${ids.a}/restaurer/`, T)
    const ca = await ra.text()
    expect(ra.status(), `A : ${ca.slice(0, 300)}`).toBe(409)
    expect(ca, 'A : nomme le lead qui l\'a absorbé').toContain(`absorbé par le lead #${ids.b}`)
    const rc = await cr.ctx.post(`${API}/crm/leads/${ids.c}/restaurer/`, T)
    const cc = await rc.text()
    expect(rc.status(), `C : ${cc.slice(0, 300)}`).toBe(409)
    expect(cc, 'C : nomme le doublon vivant').toContain(`doublon vivant : lead #${ids.d}`)
    expect(await etat([ids.a, ids.c]), 'A et C : toujours archivés, aucune activité ni prochaine étape').toEqual(avant)
    const re = await cr.ctx.post(`${API}/crm/leads/${ids.e}/restaurer/`, T)
    expect(re.status(), 'E : restauré comme avant').toBe(200)
    expect((await etat([ids.e]))[String(ids.e)][0], 'E relu : non archivé').toBe(false)
    // Le lot : E ré-archivé, puis « Restaurer » en masse sur A, C, E.
    await py(`from apps.crm.models import Lead
Lead.objects.filter(pk=${ids.e}).update(is_archived=True)`)
    const lot = await cr.ctx.post(`${API}/crm/leads/bulk/`, { ...T, data: { action: 'unarchive', ids: [ids.a, ids.c, ids.e] } })
    const jl = await lot.json()
    expect(lot.status(), JSON.stringify(jl).slice(0, 300)).toBe(200)
    expect(jl.updated, 'lot : E restauré').toBe(1)
    const motifs = Object.fromEntries((jl.skipped || []).map((x) => [x.id, x.reason]))
    expect(motifs[ids.a] || '', 'lot : A refusé avec son motif').toContain(`#${ids.b}`)
    expect(motifs[ids.c] || '', 'lot : C refusé avec son motif').toContain(`#${ids.d}`)
    const fin = await etat([ids.a, ids.c, ids.e])
    expect([fin[String(ids.a)][0], fin[String(ids.c)][0], fin[String(ids.e)][0]], 'persistance : A, C archivés ; E restauré').toEqual([true, true, false])
    await page.goto(`/crm?id=${ids.a}`)
    await expect(page.locator('body')).toBeVisible()
  } finally {
    await cr.ctx.dispose()
    await py(`from apps.crm.models import Lead
for pk in ${JSON.stringify([ids.a, ids.b, ids.c, ids.d, ids.e])}:
    try: Lead.all_objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)`)
  }
})

etape('PF10.2-ASUP41', ['ASUP41'], async ({ page }) => {
  const s = sondeHote('C-ASUP-015')
  expect(s.ok, `sonde C-ASUP-015 exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde C-ASUP-015 : ${JSON.stringify(s.res.observe)}`).toBe(false)
  const m = marque()
  // Société d'essai isolée dans une transaction ANNULÉE (les commerciaux de la démo ne faussent pas la rotation).
  const res = await py(`from django.db import transaction
from authentication.models import Company
from apps.roles.models import Role
from apps.crm.models import Lead
from apps.crm.leads_attribution import _next_balanced_round_robin_commercial, _leads_ouverts_count
from apps.crm.dispatch import _ligne_membre
r = {}
with transaction.atomic():
    co = Company.objects.create(nom='ASUP41 ${m}', slug='asup41-${m}')
    role = Role.objects.create(company=co, nom='Commercial', permissions=[])
    c1 = U.objects.create_user(username='asup41c1_${m}', password='x', company=co, role=role)
    c2 = U.objects.create_user(username='asup41c2_${m}', password='x', company=co, role=role)
    mk = lambda o, **k: Lead.objects.create(company=co, nom='L', owner=o, stage='NEW', **k)
    arch = [mk(c1, is_archived=True) for _ in range(3)]
    mk(c1); mk(c1, is_deleted=True); mk(c2); mk(c2)
    r['recoit'] = _next_balanced_round_robin_commercial(co, 3).username
    ligne = _ligne_membre(c1, 3)
    r['ligne_c1'] = [ligne['leads_ouverts'], ligne['au_plafond']]
    Lead.objects.filter(pk=arch[0].pk).update(is_archived=False)
    r['apres_restauration'] = _leads_ouverts_count(c1)
    transaction.set_rollback(True)
r['rien_laisse'] = not Company.objects.filter(slug='asup41-${m}').exists()
sortie(r)`)
  expect(res.recoit, 'C1 (1 ouvert + 3 archivés + 1 supprimé) reçoit le lead suivant').toBe(`asup41c1_${m}`)
  expect(res.ligne_c1, 'file d\'attribution : charge 1, pas au plafond').toEqual([1, false])
  expect(res.apres_restauration, 'un lead restauré compte de nouveau').toBe(2)
  expect(res.rien_laisse, 'transaction annulée').toBe(true)
  await page.goto('/crm')
  await expect(page.locator('body')).toBeVisible()
})

etape('PF10.2-ASUP43', ['ASUP43'], async ({ page, testInfo }) => {
  const s = sondeHote('C-ASUP-017')
  expect(s.ok, `sonde C-ASUP-017 exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde C-ASUP-017 : ${JSON.stringify(s.res.observe)}`).toBe(false)
  const m = marque()
  const co = await session(testInfo, `asup43co_${m}`, 'Commercial')
  const ids = await py(`from datetime import timedelta
from django.utils import timezone
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
u = U.objects.get(pk=${co.id})
Notification.objects.filter(recipient=u).delete()
et = EventType.choices[0][0]
mk = lambda t: Notification.objects.create(company_id=u.company_id, recipient=u, event_type=et, title=t)
vieilles = [mk('ASUP43 archivée %d' % i) for i in range(12)]
Notification.objects.filter(pk__in=[n.pk for n in vieilles]).update(archived=True, created_at=timezone.now() - timedelta(days=70))
recentes = [mk('ASUP43 récente %d' % i) for i in range(3)]
sortie(dict(vieilles=[n.pk for n in vieilles], recentes=[n.pk for n in recentes]))`)
  try {
    const base = `${API}/notifications/notifications/`
    const n = await (await co.ctx.get(`${base}unread-count/`, T)).json()
    const liste = await (await co.ctx.get(`${base}?page_size=100`, T)).json()
    const lignes = Array.isArray(liste) ? liste : liste.results
    const nonLuesListe = lignes.filter((x) => !x.read).length
    expect(n.unread, 'badge = 3 non lues récentes').toBe(3)
    expect(n.unread, 'badge = nombre de non lues de la liste').toBe(nonLuesListe)
    const tout = await (await co.ctx.post(`${base}read-all/`, T)).json()
    expect([...tout.ids].sort((a, b) => a - b), '« tout marquer lu » = les 3 récentes').toEqual([...ids.recentes].sort((a, b) => a - b))
    const lu = await py(`from apps.notifications.models import Notification
sortie([Notification.objects.filter(pk__in=${JSON.stringify(ids.vieilles)}, read=False, archived=True).count(), Notification.objects.filter(pk__in=${JSON.stringify(ids.recentes)}, read=True).count()])`)
    expect(lu, 'persistance : 12 archivées non lues intouchées, 3 récentes lues').toEqual([12, 3])
    const det = await co.ctx.get(`${base}${ids.vieilles[0]}/`, T)
    expect(det.status(), 'lien profond d\'une archivée : 200').toBe(200)
    const apres = await (await co.ctx.get(`${base}unread-count/`, T)).json()
    expect(apres.unread, 'badge après « tout marquer lu »').toBe(0)
    await page.goto('/apps')
    await expect(page.locator('body')).toBeVisible()
  } finally {
    await co.ctx.dispose()
    await py(`from apps.notifications.models import Notification
Notification.objects.filter(recipient_id=${co.id}).delete()`)
  }
})

etape('PF10.2-ASUP46', ['ASUP46'], async ({ page }) => {
  const s = sondeHote('C-ASUP-020')
  expect(s.ok, `sonde C-ASUP-020 exécutée : ${s.err || ''}`).toBe(true)
  expect(s.res.repro, `sonde C-ASUP-020 : ${JSON.stringify(s.res.observe)}`).toBe(false)
  const m = marque()
  // 1) Le beat des rappels (transaction ANNULÉE : rien n'est envoyé hors du rejeu).
  const beat = await py(`from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from apps.crm.models import Lead, Appointment
from apps.crm.visites_rdv import send_due_appointment_reminders
from apps.notifications.models import Notification
own = U.objects.get(username='demo_admin')
r = {}
with transaction.atomic():
    mk = lambda **k: Lead.objects.create(company_id=${SOC}, nom='ASUP46 ${m}', stage='NEW', owner=own, **k)
    rdv = lambda l: Appointment.objects.create(company_id=${SOC}, lead=l, scheduled_at=timezone.now() + timedelta(minutes=20))
    morts = [rdv(mk(is_archived=True)), rdv(mk(perdu=True)), rdv(mk(is_deleted=True))]
    temoin = rdv(mk())
    r['envoyes'] = send_due_appointment_reminders()
    r['temoin'] = Appointment.objects.get(pk=temoin.pk).reminder_sent
    r['morts'] = [Appointment.objects.get(pk=a.pk).reminder_sent for a in morts]
    r['notifs_morts'] = sum(Notification.objects.filter(body__contains='(RDV #%d)' % a.pk).count() for a in morts)
    transaction.set_rollback(True)
sortie(r)`)
  expect(beat.temoin, 'témoin (lead actif) rappelé').toBe(true)
  expect(beat.morts, 'archivé, perdu, supprimé : aucun rappel').toEqual([false, false, false])
  expect(beat.notifs_morts, 'aucune notification « RDV » pour eux').toBe(0)
  // 2) Le geste : archiver par la vraie route annule les rendez-vous À VENIR (passé intouché).
  const ids = await py(`from datetime import timedelta
from django.utils import timezone
from apps.crm.models import Lead, Appointment
own = U.objects.get(username='demo_admin')
l = Lead.objects.create(company_id=${SOC}, nom='ASUP46 geste ${m}', stage='NEW', owner=own)
S = Appointment.Statut
a = Appointment.objects.create(company_id=${SOC}, lead=l, scheduled_at=timezone.now() + timedelta(days=3))
c = Appointment.objects.create(company_id=${SOC}, lead=l, statut=S.CONFIRME, scheduled_at=timezone.now() + timedelta(days=4))
p = Appointment.objects.create(company_id=${SOC}, lead=l, scheduled_at=timezone.now() - timedelta(days=1))
sortie(dict(lead=l.pk, rdv=[a.pk, c.pk, p.pk]))`)
  try {
    const r = await page.request.post(`${API}/crm/leads/${ids.lead}/archiver/`, { ...T, data: {} })
    expect(r.status(), `archiver : ${(await r.text()).slice(0, 200)}`).toBe(200)
    const st = await py(`from apps.crm.models import Appointment
sortie([Appointment.objects.get(pk=pk).statut for pk in ${JSON.stringify(ids.rdv)}])`)
    expect(st, 'à venir et confirmé : annulés ; passé : intouché').toEqual(['annule', 'annule', 'planifie'])
    await page.goto(`/crm?id=${ids.lead}`)
    await expect(page.locator('body')).toBeVisible()
  } finally {
    await py(`from apps.crm.models import Lead, Appointment
Appointment.objects.filter(lead_id=${ids.lead}).delete()
Lead.all_objects.filter(pk=${ids.lead}).delete()`)
  }
})
