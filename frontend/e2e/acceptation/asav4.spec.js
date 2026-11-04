// ASAV123, ASAV124 — rejeu en direct : RMA résolue « remplacement » (neuf au parc et au contrat) ; scan SLA au quart d'heure
// (technicien sinon managers, sans doublon avec le balayage quotidien).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage } from '../helpers.js'

const etape = groupe('ASAV', ['ASAV123', 'ASAV124'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

async function chantierAvecAppareil(m, serie) {
  return py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import Equipement, ContratMaintenance, Ticket
a = U.objects.get(username='demo_admin')
today = timezone.localdate()
cl = Client.objects.create(company_id=1, nom='ASAV123 ${m}', prenom='Essai')
inst = Installation.objects.create(company_id=1, reference='CHT-A123-${m}', client=cl)
p = Produit.objects.create(company_id=1, nom='Onduleur A123 ${m}', sku='OND-A123-${m}', prix_achat=0, prix_vente=5000, garantie_mois=60)
e = Equipement.objects.create(company_id=1, produit=p, installation=inst, numero_serie=${JSON.stringify(serie)}, date_pose=today - datetime.timedelta(days=180))
ct = ContratMaintenance.objects.create(company_id=1, client=cl, installation=inst, actif=True, date_debut=today - datetime.timedelta(days=30))
ct.equipements.add(e)
t = Ticket.objects.create(company_id=1, reference='SAV-A123-${m}', client=cl, installation=inst, created_by=a)
sortie(dict(produit=p.id, inst=inst.id, ancien=e.id, contrat=ct.id, ticket=t.id))`)
}

etape('P123.1', ['ASAV123'], async ({ page }) => {
  const m = marque()
  const sa = `SNA${m}`
  const sn = `SNB${m}`
  const x = await chantierAvecAppareil(m, sa)
  await lireJson(await page.request.post(`${API}/sav/tickets/${x.ticket}/pieces-retirees/`, {
    ...T, data: { produit: x.produit, numero_serie: sa, destination: 'retour_fournisseur' },
  }), 'pièce retirée')
  const etat = () => py(`from apps.sav.models import Equipement, ContratMaintenance, WarrantyClaim
c = ContratMaintenance.objects.get(pk=${x.contrat})
sortie(dict(rma=list(WarrantyClaim.objects.filter(ticket_id=${x.ticket}).values_list('id', flat=True)),
  parc=sorted(Equipement.objects.filter(installation_id=${x.inst}).values_list('numero_serie', 'statut')),
  contrat=sorted(c.equipements.values_list('numero_serie', flat=True))))`)
  const e0 = await etat()
  expect(e0.rma.length, 'RMA créée par le retrait').toBe(1)
  const rma = e0.rma[0]
  // Série déjà au parc : 409 sous `serie_neuve`, rien écrit.
  const doublon = await page.request.patch(`${API}/sav/warranty-claims/${rma}/`, { ...T, data: { statut: 'resolu', resolution: 'remplacement', serie_neuve: sa } })
  expect(doublon.status(), 'série déjà au parc').toBe(409)
  expect(JSON.stringify(await doublon.json()), 'nomme serie_neuve').toContain('serie_neuve')
  expect((await etat()).contrat, 'rien écrit').toEqual([sa])
  const ok = await page.request.patch(`${API}/sav/warranty-claims/${rma}/`, { ...T, data: { statut: 'resolu', resolution: 'remplacement', serie_neuve: sn } })
  expect(ok.status(), 'résolu remplacement').toBe(200)
  const e1 = await etat()
  const neuf = e1.parc.filter((p) => p[0] === sn)
  expect(neuf.length, 'neuf une fois au parc').toBe(1)
  expect(neuf[0][1], 'neuf en service').toBe('en_service')
  expect(e1.contrat, 'neuf au contrat à la place de l\'ancien').toEqual([sn])
  await page.reload().catch(() => null)
  expect((await etat()).contrat, 'persistance').toEqual([sn])
})

etape('P124.1', ['ASAV124'], async () => {
  // Société neuve et transaction annulée : le scan parcourt toutes les sociétés actives, borné ici à celle-ci (même patron
  // que la sonde C-ASAV-VER3-21), pour ne pas notifier toute la démo.
  const r = await py(`from unittest.mock import patch
from django.db import transaction
from authentication.models import Company
from apps.crm.models import Client
from apps.notifications.models import Notification
from apps.notifications.sweeps import _sweep_sav_breaching
from apps.notifications.types_evenements import EventType
from apps.sav.models import SavSlaSettings, Ticket
from apps.sav.tasks import scan_sla_breaches
res = {}
with transaction.atomic():
    today = timezone.localdate()
    co = Company.objects.create(nom='Accept ASAV124', slug='accept-asav124')
    mgr = U.objects.create_user(username='accept124-mgr', password='x', company=co, role_legacy='admin')
    tech = U.objects.create_user(username='accept124-tech', password='x', company=co, role_legacy='technicien')
    rg = SavSlaSettings.get(co); rg.sla_breach_enabled = True; rg.save()
    cl = Client.objects.create(company=co, nom='Client', prenom='A124')
    def mk(ref, **kw):
        return Ticket.objects.create(company=co, client=cl, reference=ref, statut=Ticket.Statut.EN_COURS, created_by=mgr,
                                     date_ouverture=today - datetime.timedelta(days=8), sla_due_at=today - datetime.timedelta(days=2), **kw)
    sans, avec = mk('SAV-A124-S'), mk('SAV-A124-A', technicien_responsable=tech)
    def qui(t):
        return sorted(Notification.objects.filter(company=co, event_type=EventType.SAV_TICKET_BREACHING, link__in=[f'/sav?id={t.pk}', f'/sav/tickets/{t.pk}']).values_list('recipient__username', flat=True))
    with patch('authentication.selectors.active_company_ids', return_value=[co.pk]):
        scan_sla_breaches()
    res['scan'] = [qui(sans), qui(avec)]
    _sweep_sav_breaching(co); _sweep_sav_breaching(co)
    res['balayages'] = [qui(sans), qui(avec)]
    sans.refresh_from_db(); res['breach'] = sans.sla_breach
    co2 = Company.objects.create(nom='Accept ASAV124 off', slug='accept-asav124-off')
    mgr2 = U.objects.create_user(username='accept124-mgr2', password='x', company=co2, role_legacy='admin')
    rg2 = SavSlaSettings.get(co2); rg2.sla_breach_enabled = False; rg2.save()
    cl2 = Client.objects.create(company=co2, nom='Client', prenom='A124b')
    Ticket.objects.create(company=co2, client=cl2, reference='SAV-A124-O', statut=Ticket.Statut.EN_COURS, created_by=mgr2, date_ouverture=today - datetime.timedelta(days=8), sla_due_at=today - datetime.timedelta(days=2))
    with patch('authentication.selectors.active_company_ids', return_value=[co2.pk]):
        scan_sla_breaches()
    res['off'] = Notification.objects.filter(company=co2, event_type=EventType.SAV_TICKET_BREACHING).count()
    transaction.set_rollback(True)
sortie(res)`)
  expect(r.scan, 'scan : sans technicien → manager ; avec → technicien').toEqual([['accept124-mgr'], ['accept124-tech']])
  expect(r.breach, 'sla_breach posé').toBe(true)
  expect(r.balayages, 'aucun doublon après deux balayages').toEqual([['accept124-mgr'], ['accept124-tech']])
  expect(r.off, 'SLA désactivé : 0').toBe(0)
})
