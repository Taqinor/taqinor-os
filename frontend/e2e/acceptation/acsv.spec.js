// Acceptation en direct — groupe ACSV (chantiers / SAV, run 99392c vague 10) : preuves dues d'ACSV114 (mise en service
// datée dans le futur refusée), ACSV115 (deux mesures de fiche saisies d'affilée, réseau ralenti), ACSV116 (facture d'un
// ticket sans la ligne F11 à 0) et ACSV111 (clôture refusée quand la seule pièce vient d'une fiche F11).
// Données posées au shell Django dans la société de demo_admin (marquées, jamais `company_id` codé en dur) ; gestes par
// les VRAIES routes (mise-en-service, renseigner-fiche, valider-consommation, facturer, cloturer) et les vrais écrans
// (fiche chantier, « Ma journée », fiche ticket). Le balayage d'auto-clôture est joué dans une transaction ANNULÉE
// (il parcourt toute la société) : seul l'état du ticket de l'étape y est lu.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, API_DJANGO as API } from '../helpers.js'

const etape = groupe('ACSV', ['ACSV114', 'ACSV115', 'ACSV116', 'ACSV111'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 480_000 })
// Écran large : la barre d'actions de la fiche ticket déborde du panneau latéral à 1280 px (constat asav.spec.js).
test.use({ viewport: { width: 1920, height: 1080 }, actionTimeout: 60_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const T = { timeout: 120_000 }
const J = JSON.stringify
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()
const aujourdhui = () => py(`sortie(timezone.localdate().isoformat())`)

// ── ACSV114 : chantier « Installé » né d'un devis accepté ─────────────────────────────────────────────────────────
async function chantierInstalle() {
  const m = marque()
  return py(`a = U.objects.get(username='demo_admin'); co = a.company
from decimal import Decimal as D
from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.installations.models import Installation
from apps.installations.services import create_installation_from_devis
p = Produit.objects.create(company=co, nom='Panneau ACC-ACSV114 ${m}', sku='ACC-ACSV114-${m}', prix_vente=D('100'), prix_achat=D('60'), quantite_stock=50, tva=D('20.00'))
cl = Client.objects.create(company=co, nom='ACC ACSV114', prenom='${m}', email='acc-acsv114-${m.toLowerCase()}@example.invalid')
kw = dict(company=co, nom='ACC ACSV114', prenom='${m}', stage=stages.SIGNED, type_installation='residentiel')
if any(f.name == 'client' for f in Lead._meta.fields): kw['client'] = cl
lead = Lead.objects.create(**kw)
d = Devis.objects.create(company=co, reference='DEV-ACC-ACSV114-${m}', client=cl, lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=D('20'), mode_installation='residentiel')
LigneDevis.objects.create(devis=d, produit=p, designation='Panneau ACC-ACSV114 ${m}', quantite=D('2'), prix_unitaire=D('100'), taux_tva=D('20.00'))
inst, _ = create_installation_from_devis(d, a, co)
Installation.objects.filter(pk=inst.pk).update(statut='installe')
sortie(dict(chantier=inst.id, ref=inst.reference, client=cl.id))`)
}
const etatChantier = (id) => py(`from apps.installations.models import Installation
from apps.sav.models import Equipement
i = Installation.objects.get(pk=${id})
sortie(dict(statut=i.statut, reception=i.date_reception, mes=i.date_mise_en_service,
            parc=Equipement.objects.filter(installation_id=i.pk).count()))`)

etape('P.mise_en_service_future', ['ACSV114'], async ({ page, suivi }) => {
  const r = page.request
  const x = await chantierInstalle()
  const jour = await aujourdhui()
  const futur = await py(`sortie((timezone.localdate() + datetime.timedelta(days=366)).isoformat())`)
  const avant = await etatChantier(x.chantier)
  expect(avant, `chantier « Installé » sans réception (${J(avant)})`).toMatchObject({ statut: 'installe', reception: null })
  const url = `${API}/installations/chantiers/${x.chantier}/mise-en-service/`
  for (const mauvaise of [futur, '2026-13-40']) {
    const rep = await r.post(url, { ...T, data: { date_mise_en_service: mauvaise, mes_production_test: '5', mes_tension: '230' } })
    const corps = await rep.json().catch(() => ({}))
    expect(rep.status(), `${mauvaise} : 400 (${J(corps)})`).toBe(400)
    expect(Object.keys(corps), `${mauvaise} : erreur nommant date_mise_en_service`).toContain('date_mise_en_service')
    // Persistance : relu en base après le refus — statut, réception, parc inchangés.
    expect(await etatChantier(x.chantier), `${mauvaise} : chantier inchangé`).toEqual(avant)
  }
  // Écran : fiche chantier → « Jalons & gates » → Mise en service à une date de l'an prochain ⇒ message d'erreur.
  await page.goto(`/chantiers?id=${x.chantier}`)
  await page.getByRole('tab', { name: /Jalons/ }).click({ timeout: 60_000 })
  await expect(page.locator('#mes-date')).toBeVisible({ timeout: 60_000 })
  await page.locator('#mes-date').fill(futur)
  await page.locator('#mes-prod').fill('5')
  await page.locator('#mes-tension').fill('230')
  suivi.attendre(/\/installations\/chantiers\/\d+\/mise-en-service\/?$/, 400)
  const refus = page.waitForResponse((q) => q.request().method() === 'POST' && /\/mise-en-service\/?$/.test(new URL(q.url()).pathname), T)
  await page.getByRole('button', { name: 'Enregistrer la mise en service' }).click()
  // ACSV36 : checklist incomplète ⇒ dialogue « Réception du chantier » (Continuer) avant l'envoi.
  const continuer = page.getByRole('button', { name: 'Continuer', exact: true })
  if (await continuer.isVisible({ timeout: 8_000 }).catch(() => false)) await continuer.click()
  expect((await refus).status(), 'écran : la date future part et revient 400').toBe(400)
  await expect(page.getByText('Enregistrement de la mise en service impossible.').first(), 'message d’erreur affiché').toBeVisible({ timeout: 30_000 })
  // Persistance : rechargement de la fiche ⇒ toujours « Installé », aucune mise en service enregistrée.
  await page.reload()
  await page.getByRole('tab', { name: /Jalons/ }).click({ timeout: 60_000 })
  await expect(page.getByRole('button', { name: 'Enregistrer la mise en service' })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText(/Mise en service enregistrée le/)).toHaveCount(0)
  expect(await etatChantier(x.chantier), 'après le refus de l’écran : chantier inchangé').toEqual(avant)
  // La date du jour passe : 200, « Réceptionné » daté du jour.
  const ok = await r.post(url, { ...T, data: { date_mise_en_service: jour, mes_production_test: '5', mes_tension: '230' } })
  expect(ok.status(), `date du jour : 200 (${(await ok.text()).slice(0, 300)})`).toBe(200)
  const apres = await etatChantier(x.chantier)
  expect([apres.statut, apres.reception], `réceptionné le ${jour}`).toEqual(['receptionne', jour])
})

// ── ACSV115 : fiche à deux mesures (gabarit du type d'intervention), intervention du jour de demo_admin ────────────
etape('P.fiche_deux_mesures_reseau_lent', ['ACSV115'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const x = await py(`a = U.objects.get(username='demo_admin'); co = a.company
from apps.installations.models import Installation, Intervention, FicheInterventionTemplate, FicheInterventionChamp
types = [c for c, _ in Intervention.Type.choices]
pris = set(FicheInterventionTemplate.objects.filter(company=co).values_list('type_intervention', flat=True))
libres = [t for t in types if t not in pris]
t = libres[0] if libres else types[0]
tpl = FicheInterventionTemplate.objects.filter(company=co, type_intervention=t).first()
cree = tpl is None
actif_avant = None if cree else tpl.actif
if cree:
    tpl = FicheInterventionTemplate.objects.create(company=co, nom='Fiche ACSV115 ${m}', type_intervention=t, actif=True)
elif not tpl.actif:
    tpl.actif = True; tpl.save(update_fields=['actif'])
ca = FicheInterventionChamp.objects.create(company=co, template=tpl, cle='acsv115_a_${m.toLowerCase()}', libelle='Tension ACSV115 ${m}', type_champ='mesure', unite='V', ordre=900)
cb = FicheInterventionChamp.objects.create(company=co, template=tpl, cle='acsv115_b_${m.toLowerCase()}', libelle='Courant ACSV115 ${m}', type_champ='mesure', unite='A', ordre=901)
inst = Installation.objects.create(company=co, reference='CH-ACSV115-${m}')
iv = Intervention.objects.create(company=co, installation=inst, type_intervention=t, technicien=a, date_prevue=timezone.localdate(), created_by=a)
sortie(dict(itv=iv.id, ref=inst.reference, tpl=tpl.id, cree=cree, actif_avant=actif_avant, champs=[ca.id, cb.id], type=t))`)
  try {
    const fiche = await lireJson(await r.get(`${API}/installations/interventions/${x.itv}/fiche/`, T), 'fiche')
    const valeur = (champ) => (fiche.valeurs || []).find((v) => v.champ === champ || v.champ_id === champ || v.champ_libelle?.startsWith(champ))
    const vA = valeur(`Tension ACSV115 ${m}`)
    const vB = valeur(`Courant ACSV115 ${m}`)
    expect(vA && vB, `fiche à deux mesures servie (${J(fiche).slice(0, 300)})`).toBeTruthy()
    // Réseau ralenti : la réponse du PREMIER envoi (A) est retenue jusqu'à ce que B soit saisi.
    let lacher
    const porte = new Promise((ok) => { lacher = ok })
    const envois = []
    await page.route(/\/installations\/interventions\/\d+\/renseigner-fiche\/?$/, async (route) => {
      envois.push(route.request().postDataJSON())
      if (envois.length === 1) {
        const rep = await route.fetch()
        await porte
        await route.fulfill({ response: rep })
      } else {
        await route.continue()
      }
    })
    await page.goto('/ma-journee')
    await page.getByRole('button', { name: new RegExp(x.ref) }).first().click({ timeout: 60_000 })
    await page.getByRole('tab', { name: 'Fiche', exact: true }).click({ timeout: 60_000 })
    const A = page.getByLabel(new RegExp(`^Tension ACSV115 ${m}`))
    const B = page.getByLabel(new RegExp(`^Courant ACSV115 ${m}`))
    await expect(A).toBeVisible({ timeout: 60_000 })
    await A.fill('230')
    const repA = page.waitForResponse((q) => /renseigner-fiche/.test(q.url()) && q.request().postDataJSON()?.valeur_id === vA.id, T)
    await B.click() // quitter A ⇒ envoi de A (réponse retenue)
    await expect.poll(() => envois.length, { timeout: 30_000 }).toBe(1)
    await B.fill('12') // saisi PENDANT l'envoi de A
    const relu = page.waitForResponse((q) => q.request().method() === 'GET' && /\/interventions\/\d+\/fiche\/?$/.test(new URL(q.url()).pathname), T)
    lacher()
    expect((await repA).status(), 'envoi de A').toBe(200)
    await relu
    await expect(B, 'B affiche toujours 12 après la relecture déclenchée par A').toHaveValue('12')
    await expect(A, 'A relu du serveur').toHaveValue(/^230/)
    const repB = page.waitForResponse((q) => /renseigner-fiche/.test(q.url()) && q.request().postDataJSON()?.valeur_id === vB.id, T)
    await B.press('Tab') // quitter B ⇒ envoi de B
    const rb = await repB
    expect(rb.status(), 'envoi de B').toBe(200)
    expect(rb.request().postDataJSON()?.valeur, 'B part avec « 12 »').toBe('12')
    // Persistance : relire la fiche (getFiche) ⇒ A = 230, B = 12 ; puis l'écran rechargé les affiche.
    const apres = await lireJson(await r.get(`${API}/installations/interventions/${x.itv}/fiche/`, T), 'fiche relue')
    const lu = (v) => Number((apres.valeurs || []).find((w) => w.id === v.id)?.valeur)
    expect([lu(vA), lu(vB)], 'serveur : A = 230, B = 12').toEqual([230, 12])
    await page.unroute(/\/installations\/interventions\/\d+\/renseigner-fiche\/?$/)
    await page.reload()
    await page.getByRole('button', { name: new RegExp(x.ref) }).first().click({ timeout: 60_000 }).catch(() => undefined)
    await page.getByRole('tab', { name: 'Fiche', exact: true }).click({ timeout: 60_000 })
    await expect(page.getByLabel(new RegExp(`^Tension ACSV115 ${m}`))).toHaveValue(/^230/, { timeout: 60_000 })
    await expect(page.getByLabel(new RegExp(`^Courant ACSV115 ${m}`))).toHaveValue(/^12/)
    void suivi
  } finally {
    await py(`from apps.installations.models import FicheInterventionTemplate, FicheInterventionChamp, Intervention
Intervention.objects.filter(pk=${x.itv}).update(annulee=True) if any(f.name == 'annulee' for f in Intervention._meta.fields) else None
FicheInterventionChamp.objects.filter(pk__in=${J(x.champs)}).delete()
if ${x.cree ? 'True' : 'False'}:
    FicheInterventionTemplate.objects.filter(pk=${x.tpl}).delete()
elif ${x.actif_avant === false ? 'True' : 'False'}:
    FicheInterventionTemplate.objects.filter(pk=${x.tpl}).update(actif=False)
sortie(1)`).catch(() => null)
  }
})

// ── ACSV116 / ACSV111 : ticket correctif « facturable » Résolu, intervention de dépannage, fiche F11 validée ────────
async function ticketF11(r, lignes) {
  const m = marque()
  const x = await py(`a = U.objects.get(username='demo_admin'); co = a.company
from decimal import Decimal as D
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention, MaterielConsommation, ConsommationLigne
from apps.sav.models import Ticket
from apps.stock.models import Produit
cl = Client.objects.create(company=co, nom='ACC ACSV', prenom='${m}', email='acc-acsv-${m.toLowerCase()}@example.invalid')
inst = Installation.objects.create(company=co, reference='CH-ACC-ACSV-${m}', client=cl)
t = Ticket.objects.create(company=co, reference='SAV-ACC-ACSV-${m}', client=cl, installation=inst, type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.RESOLU, created_by=a)
iv = Intervention.objects.create(company=co, installation=inst, ticket=t, type_intervention=Intervention.Type.DEPANNAGE, created_by=a)
conso = MaterielConsommation.objects.create(company=co, intervention=iv)
prods = {}
for i, (nom, pv, q) in enumerate(${J(lignes)}):
    p = Produit.objects.create(company=co, nom=nom + ' ACSV ${m}', sku='ACC-ACSV-%d-${m}' % i, prix_vente=D(pv), prix_achat=D('4'), quantite_stock=5)
    # Hors nomenclature : la route valider-consommation (ensure_consommation) retire les lignes nomenclature absentes du BOM.
    ConsommationLigne.objects.create(company=co, consommation=conso, produit=p, designation=p.nom, quantite_utilisee=D(q),
                                     justification='remplacé', hors_nomenclature=True)
    prods[nom] = p.id
Ticket.objects.filter(pk=t.pk).update(couverture='facturable', heures_main_oeuvre=0)
sortie(dict(ticket=t.id, ref=t.reference, itv=iv.id, prods=prods))`)
  const v = await r.post(`${API}/installations/interventions/${x.itv}/valider-consommation/`, { ...T, data: {} })
  expect(v.status(), `valider-consommation (${(await v.text()).slice(0, 300)})`).toBe(200)
  await py(`from apps.installations.models import Intervention
Intervention.objects.filter(pk=${x.itv}).update(statut=Intervention.Statut.TERMINEE)
sortie(1)`)
  return x
}
const lireTicket = async (r, id) => lireJson(await r.get(`${API}/sav/tickets/${id}/`, T), `ticket ${id}`)
async function ouvrirTicket(page, id) {
  await page.goto(`/sav?id=${id}`)
  await expect(page.getByText(/Ticket SAV — SAV-/).first()).toBeVisible({ timeout: 60_000 })
}
const supprimerBrouillon = (r, factureId) => (factureId ? r.delete(`${API}/ventes/factures/${factureId}/`, T).catch(() => null) : null)

etape('P.facture_sans_ligne_f11_nulle', ['ACSV116'], async ({ page }) => {
  const r = page.request
  const x = await ticketF11(r, [['Fusible', '40', '1'], ['Câble', '4', '0']])
  let factureId = null
  try {
    const rendu = await py(`from apps.installations.selectors import consommations_appliquees_du_ticket
co = U.objects.get(username='demo_admin').company
sortie([[c.produit.id, str(c.quantite)] for c in consommations_appliquees_du_ticket(co, ${x.ticket})])`)
    expect(rendu.map(([p, q]) => [p, Number(q)]), 'consommations appliquées : [Fusible ×1] seulement').toEqual([[x.prods.Fusible, 1]])
    // Écran : fiche ticket → « Facturer ».
    await ouvrirTicket(page, x.ticket)
    const rep = page.waitForResponse((q) => q.request().method() === 'POST' && q.url().includes(`/sav/tickets/${x.ticket}/facturer/`), T)
    await page.getByRole('button', { name: /^Facturer$/ }).press('Enter')
    const reponse = await rep
    expect(reponse.status(), `Facturer (${(await reponse.text()).slice(0, 300)})`).toBeLessThan(300)
    factureId = (await lireTicket(r, x.ticket)).facture_id_ext
    expect(factureId, 'facture posée sur le ticket').toBeTruthy()
    const f = await lireJson(await r.get(`${API}/ventes/factures/${factureId}/`, T), 'facture')
    expect(f.statut, 'facture brouillon').toBe('brouillon')
    expect((f.lignes || []).map((l) => [l.designation, Number(l.quantite)]), 'facture à UNE ligne : le fusible ×1, jamais le câble à 0')
      .toEqual([[expect.stringContaining('Fusible'), 1]])
    // Persistance : rechargement de la fiche (« Facture générée ») + relecture des lignes.
    await page.reload()
    await expect(page.getByText('Facture générée').first()).toBeVisible({ timeout: 60_000 })
    const relu = await lireJson(await r.get(`${API}/ventes/factures/${factureId}/`, T), 'facture relue')
    expect((relu.lignes || []).length, 'relu : une ligne').toBe(1)
  } finally {
    await supprimerBrouillon(r, factureId)
  }
})

etape('P.cloture_refusee_piece_f11', ['ACSV111'], async ({ page, suivi }) => {
  const r = page.request
  const x = await ticketF11(r, [['Fusible', '40', '1']])
  let factureId = null
  try {
    const refus = await r.post(`${API}/sav/tickets/${x.ticket}/cloturer/`, { ...T, data: {} })
    const corps = await refus.json().catch(() => ({}))
    expect(refus.status(), `Clôturer : 409 (${J(corps)})`).toBe(409)
    expect(corps.code, 'code ticket_non_facture').toBe('ticket_non_facture')
    // Balayage d'auto-clôture (réglage à 1 j, ticket dormant) joué dans une transaction ANNULÉE : il le laisse Résolu.
    const balayage = await py(`from django.db import transaction
from apps.sav import tasks
from apps.sav.models import Ticket, TicketActivity, SavSlaSettings
co = U.objects.get(username='demo_admin').company
res = {}
with transaction.atomic():
    sla = SavSlaSettings.get(co); sla.auto_cloture_jours = 1; sla.save()
    il_y_a = timezone.now() - datetime.timedelta(days=2)
    TicketActivity.objects.filter(ticket_id=${x.ticket}).update(created_at=il_y_a)
    Ticket.objects.filter(pk=${x.ticket}).update(date_modification=il_y_a)
    tasks.scan_auto_cloture_tickets_resolus()
    res['statut'] = Ticket.objects.get(pk=${x.ticket}).statut
    transaction.set_rollback(True)
sortie(res)`)
    expect(balayage.statut, 'le balayage le laisse Résolu').toBe('resolu')
    // Écran : fiche ticket → Statut « Clôturé » → Mettre à jour → assistant → « Clôture rapide » ⇒ refus affiché.
    await ouvrirTicket(page, x.ticket)
    await page.getByRole('combobox').filter({ hasText: 'Résolu' }).first().click()
    await page.getByRole('option', { name: 'Clôturé', exact: true }).click()
    await page.getByRole('button', { name: /Mettre à jour/ }).click()
    const assistant = page.getByRole('dialog').filter({ hasText: 'Assistant de clôture' })
    await expect(assistant).toBeVisible({ timeout: 30_000 })
    suivi.attendre(new RegExp(`/sav/tickets/${x.ticket}/cloturer/?$`), 409)
    const rep = page.waitForResponse((q) => q.request().method() === 'POST' && q.url().includes(`/sav/tickets/${x.ticket}/cloturer/`), T)
    await assistant.getByRole('button', { name: 'Clôture rapide' }).click()
    expect((await rep).status(), 'écran : Clôturer ⇒ 409').toBe(409)
    await expect(page.getByTestId('cloture-sans-facture'), 'refus affiché : forçage motivé proposé').toBeVisible({ timeout: 30_000 })
    if (corps.detail) await expect(page.getByRole('alert').filter({ hasText: corps.detail }).first()).toBeVisible()
    // Persistance : rechargement ⇒ toujours Résolu, sans facture.
    await page.reload()
    const relu = await lireTicket(r, x.ticket)
    expect([relu.statut, relu.facture_id_ext || null], 'relu : Résolu, facture_id_ext nul').toEqual(['resolu', null])
    // Après « facturer » : la clôture passe.
    const f = await r.post(`${API}/sav/tickets/${x.ticket}/facturer/`, { ...T, data: {} })
    expect(f.status(), `facturer (${(await f.text()).slice(0, 200)})`).toBe(201)
    factureId = (await lireTicket(r, x.ticket)).facture_id_ext
    const c = await r.post(`${API}/sav/tickets/${x.ticket}/cloturer/`, { ...T, data: {} })
    expect(c.status(), `clôture après facture (${(await c.text()).slice(0, 200)})`).toBe(200)
    // Témoin : seule ligne F11 à quantité 0 ⇒ rien à facturer, clôture 200.
    const zero = await ticketF11(r, [['Fusible', '40', '0']])
    const cz = await r.post(`${API}/sav/tickets/${zero.ticket}/cloturer/`, { ...T, data: {} })
    expect(cz.status(), `F11 à 0 seule : clôture 200 (${(await cz.text()).slice(0, 200)})`).toBe(200)
  } finally {
    void factureId
  }
})
