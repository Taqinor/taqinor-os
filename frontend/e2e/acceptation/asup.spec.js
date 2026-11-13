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

const etape = groupe('ASUP', ['ASUP1', 'ASUP2', 'ASUP3', 'ASUP12'])
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
