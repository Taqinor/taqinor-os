// Rejeux du 04/11 (vague 35) — clauses laissées ouvertes par les rejeux nominaux : porte d'import et autres portes (ACVI),
// livechat, cas sans série, férié société, facture sans devis, PDF lus et QR décodé, BCF. Gestes par l'API réelle ;
// le shell Django ne pose que ce qu'aucun geste ne pose et relit ce que l'API ne sert pas.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, listeDe, telephoneMobileUnique, assurerSessionPage, isoDansJours, uniq, textePdf } from '../helpers.js'

fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const courriel = () => `${uniq('r35').toLowerCase().replace(/[^a-z0-9]/g, '')}@example.invalid`
const nouveauLead = async (r, nom, extra = {}) => lireJson(await r.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: courriel(), ...extra },
}), 'lead')
const relu = async (r, id) => lireJson(await r.get(`${API}/crm/leads/${id}/`, T), 'lead relu')
const touches = async (r, lid) => listeDe(await lireJson(await r.get(`${API}/crm/relance-etapes/?lead=${lid}`, T), 'touches'))
const aFaire = (ts, cadence) => ts.filter((t) => t.statut === 'a_faire' && (!cadence || t.cadence === cadence))
const historique = async (r, lid) => listeDe(await lireJson(await r.get(`${API}/crm/leads/${lid}/historique/`, T), 'historique'))
const texteHist = (h) => h.map((a) => a.body || a.message || a.description || '').join(' | ')

// ═══════════════════════════ ACVI ═══════════════════════════
const etapeA = groupe('ACVI', ['ACVI88', 'ACVI24', 'ACVI13'])

etapeA('PA1.03.import_cadence', ['ACVI88'], async ({ page }) => {
  const m = marque()
  const tel = telephoneMobileUnique()
  const temoin = await nouveauLead(page.request, `ACVI88I temoin ${m}`)
  const csv = `nom,telephone,email\nACVI88I avec ${m},${tel},av${m}@example.invalid\nACVI88I sansnum ${m},,sn${m}@example.invalid\n`
  const rep = await lireJson(await page.request.post(`${API}/imports/commit/`, {
    ...T, multipart: { target: 'leads', mode: 'creer', file: { name: `acvi88-${m}.csv`, mimeType: 'text/csv', buffer: Buffer.from(csv) } },
  }), 'import')
  expect(JSON.stringify(rep).slice(0, 300), 'deux leads créés').toMatch(/2/)
  const trouver = async (q) => listeDe(await lireJson(await page.request.get(`${API}/crm/leads/?search=${encodeURIComponent(q)}`, T), 'recherche'))
  const avec = (await trouver(`ACVI88I avec ${m}`))[0]
  const sans = (await trouver(`ACVI88I sansnum ${m}`))[0]
  expect(avec && sans, 'les deux leads importés existent').toBeTruthy()
  expect((await relu(page.request, avec.id)).stage, 'lead NEW').toBe('NEW')
  const nTemoin = aFaire(await touches(page.request, temoin.id), 'contact').length
  expect(nTemoin, 'témoin ≥ 1 touche').toBeGreaterThanOrEqual(1)
  expect(aFaire(await touches(page.request, avec.id), 'contact').length, 'import avec numéro : cadence contact comme un lead de la fiche').toBe(nTemoin)
  expect(aFaire(await touches(page.request, sans.id), 'contact').length, 'sans numéro : 0 touche').toBe(0)
  expect(texteHist(await historique(page.request, sans.id)), 'refus nommé au chatter').toContain('Cadence de relance non initialisée')
  expect(aFaire(await touches(page.request, avec.id), 'contact').length, 'relu').toBe(nTemoin)
  expect(texteHist(await historique(page.request, sans.id)), 'note relue').toContain('Cadence de relance non initialisée')
})

etapeA('PA1.08.rdv_annule_portes_locataire_devis', ['ACVI24'], async ({ page }) => {
  const m = marque()
  const porte = async (nom, geste) => {
    const l = await nouveauLead(page.request, `ACVI24b ${nom} ${m}`)
    const v = await lireJson(await page.request.post(`${API}/visites/visites/`, { ...T, data: { lead: l.id, date_prevue: isoDansJours(5) } }), `visite ${nom}`)
    expect((await relu(page.request, l.id)).visite_prevue_le, `${nom} : date posée`).toBeTruthy()
    await geste(l)
    const etat = await py(`from apps.crm.models import Lead
from apps.visites.models import VisiteTerrain
sortie([Lead.all_objects.get(pk=${l.id}).visite_prevue_le, VisiteTerrain.objects.get(pk=${v.id}).statut, Lead.all_objects.get(pk=${l.id}).perdu])`)
    expect(etat[0], `${nom} : date vidée`).toBeNull()
    expect(etat[1], `${nom} : visite annulée`).toBe('annulee')
    expect(etat[2], `${nom} : lead perdu`).toBe(true)
    expect(texteHist(await historique(page.request, l.id)), `${nom} : note système`).toContain('Rendez-vous de visite')
    expect((await relu(page.request, l.id)).visite_prevue_le, `${nom} : date vide relue`).toBeNull()
  }
  await porte('locataire', async (l) => lireJson(await page.request.post(`${API}/crm/leads/${l.id}/locataire/`, { ...T, data: { proprietaire_inconnu: true } }), 'locataire'))
  await porte('devis-refuse', async (l) => {
    const p = await lireJson(await page.request.post(`${API}/stock/produits/`, { ...T, data: { nom: `Prest ACVI24 ${m}`, prix_vente: '1000.00', prix_achat: '100.00' } }), 'produit')
    const d = await lireJson(await page.request.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: l.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
    await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
    await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/refuser/`, { ...T, data: { motif: 'Concurrent', marquer_lead_perdu: true } }), 'refus')
  })
})

etapeA('PA1.01.livechat_doublon_vivant', ['ACVI13'], async ({ testInfo, page }) => {
  const m = marque()
  const lettres = m.replace(/[^a-z]/gi, '') || 'x'
  const publique = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const discuter = async (nom, tel) => {
    const s = await lireJson(await publique.post(`${API}/crm/public/chat/sessions/`, T), 'session')
    return lireJson(await publique.post(`${API}/crm/public/chat/sessions/${s.token}/messages/`, { ...T, data: { message: `Bonjour, je m'appelle ${nom}, mon téléphone ${tel}` } }), 'message')
  }
  const parTel = (tel) => py(`from apps.crm.models import Lead
sortie(sorted(Lead.all_objects.filter(company_id=1, phone_normalise=${JSON.stringify(tel.slice(-9))}).values_list('id', flat=True)))`)
  const telA = telephoneMobileUnique()
  const a = await nouveauLead(page.request, `ACVI13L A ${m}`, { telephone: telA })
  await lireJson(await page.request.post(`${API}/crm/leads/${a.id}/archiver/`, { ...T, data: {} }), 'archiver A')
  const r1 = await discuter(`Livechat${lettres}`, telA)
  expect(r1.lead_created, 'lead créé').toBe(true)
  const ids = await parTel(telA)
  expect(ids.length, 'une fiche neuve en plus de A').toBe(2)
  const neuve = ids.find((i) => i !== a.id)
  expect((await relu(page.request, a.id)).is_archived, 'A inchangé (archivé)').toBe(true)
  expect(aFaire(await touches(page.request, neuve), 'contact').length, 'fiche neuve : cadence contact').toBeGreaterThanOrEqual(1)
  const telV = telephoneMobileUnique()
  const v = await nouveauLead(page.request, `ACVI13L V ${m}`, { telephone: telV })
  await discuter(`Vivant${lettres}`, telV)
  expect(await parTel(telV), 'absorbé par le vivant : une seule fiche').toEqual([v.id])
  const telF = telephoneMobileUnique()
  const f = await nouveauLead(page.request, `ACVI13L F ${m}`, { telephone: telF })
  const app = aFaire(await touches(page.request, f.id))[0]
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${app.id}/fait/`, { ...T, data: { outcome: 'non_joint', note: 'rejeu ACVI13 livechat' } }), 'appel')
  await lireJson(await page.request.patch(`${API}/crm/leads/${f.id}/`, { ...T, data: { stage: 'COLD', parc_raison: 'budget' } }), 'froid')
  await discuter(`Froid${lettres}`, telF)
  expect(await parTel(telF), 'Froid rouvert : pas de fiche neuve').toEqual([f.id])
  expect((await relu(page.request, f.id)).stage, 'plus au Froid').not.toBe('COLD')
  await publique.dispose()
})

// ═══════════════════════════ ASAV123 ═══════════════════════════
const etapeS = groupe('ASAV', ['ASAV123'])
etapeS('P123.2.sans_serie_et_garantie', ['ASAV123'], async ({ page }) => {
  const m = marque()
  const x = await py(`from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import Equipement, ContratMaintenance, Ticket
a = U.objects.get(username='demo_admin')
today = timezone.localdate()
cl = Client.objects.create(company_id=1, nom='ASAV123b ${m}', prenom='Essai')
inst = Installation.objects.create(company_id=1, reference='CHT-A123B-${m}', client=cl)
p = Produit.objects.create(company_id=1, nom='Onduleur A123b ${m}', sku='OND-A123B-${m}', prix_achat=0, prix_vente=5000, garantie_mois=60)
p2 = Produit.objects.create(company_id=1, nom='Onduleur court A123b ${m}', sku='OND-A123C-${m}', prix_achat=0, prix_vente=5000, garantie_mois=12)
e = Equipement.objects.create(company_id=1, produit=p, installation=inst, numero_serie='SNA${m}', date_pose=today - datetime.timedelta(days=180))
e.recompute_garanties(); e.save()
ct = ContratMaintenance.objects.create(company_id=1, client=cl, installation=inst, actif=True, date_debut=today - datetime.timedelta(days=30))
ct.equipements.add(e)
t = Ticket.objects.create(company_id=1, reference='SAV-A123B-${m}', client=cl, installation=inst, created_by=a)
sortie(dict(produit=p.id, court=p2.id, inst=inst.id, contrat=ct.id, ticket=t.id, reste=str(e.date_fin_garantie_effective), today=str(today)))`)
  await lireJson(await page.request.post(`${API}/sav/tickets/${x.ticket}/pieces-retirees/`, { ...T, data: { produit: x.produit, numero_serie: `SNA${m}`, destination: 'retour_fournisseur' } }), 'pièce retirée')
  const etat = () => py(`from apps.sav.models import Equipement, ContratMaintenance, WarrantyClaim
c = ContratMaintenance.objects.get(pk=${x.contrat})
sortie(dict(rma=list(WarrantyClaim.objects.filter(ticket_id=${x.ticket}).values_list('id', flat=True)),
  parc=sorted((s, st, str(g)) for s, st, g in Equipement.objects.filter(installation_id=${x.inst}).values_list('numero_serie', 'statut', 'date_fin_garantie')),
  contrat=sorted(c.equipements.values_list('numero_serie', flat=True))))`)
  const e0 = await etat()
  const rma = e0.rma[0]
  // Cas « sans série » : inchangé, 200, rien ajouté au parc ni au contrat.
  const sans = await page.request.patch(`${API}/sav/warranty-claims/${rma}/`, { ...T, data: { statut: 'resolu', resolution: 'remplacement' } })
  expect(sans.status(), `sans serie_neuve : ${(await sans.text()).slice(0, 200)}`).toBe(200)
  const e1 = await etat()
  expect(e1.parc, 'parc inchangé sans série').toEqual(e0.parc)
  expect(e1.contrat, 'contrat inchangé sans série').toEqual(e0.contrat)
  // Avec série et produit neuf à garantie COURTE (12 mois) : D-ASAV-1 « au moins la fin restante de l'ancien ».
  const ok = await page.request.patch(`${API}/sav/warranty-claims/${rma}/`, { ...T, data: { statut: 'resolu', resolution: 'remplacement', serie_neuve: `SNB${m}`, produit_neuf: x.court } })
  expect(ok.status(), `avec série : ${(await ok.text()).slice(0, 300)}`).toBe(200)
  const e2 = await etat()
  const neuf = e2.parc.find((p) => p[0] === `SNB${m}`)
  expect(neuf, 'neuf au parc').toBeTruthy()
  expect(neuf[1]).toBe('en_service')
  expect(neuf[2] >= x.reste, `garantie du neuf (${neuf[2]}) >= fin restante de l'ancien (${x.reste}) — jamais moins que ce que le client avait`).toBe(true)
  const douze = await py(`import datetime; t = timezone.localdate(); sortie(str(t + datetime.timedelta(days=366)))`)
  expect(neuf[2] > douze, 'la fin restante de l\'ancien (≈ 55 mois) l\'emporte sur les 12 mois du neuf').toBe(true)
  expect(e2.contrat, 'neuf au contrat à la place').toEqual([`SNB${m}`])
  expect((await etat()).contrat, 'relu').toEqual([`SNB${m}`])
})

// ═══════════════════════════ ALEA65 ═══════════════════════════
const etapeL = groupe('ALEA', ['ALEA65'])
etapeL('VER3-31.ferie_societe', ['ALEA65'], async () => {
  const r = await py(`from django.db import transaction
from authentication.models import Company
from apps.crm.models import Lead
from apps.crm import stages
from apps.crm.models_cadence import RelanceEtape
from apps.crm.cadence_selectors import relances_du_jour, ma_file_commercial_items
from apps.notifications.models import Holiday
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
res = {}
with transaction.atomic():
    co = Company.objects.create(nom='Accept ALEA65 ferie', slug='accept-alea65-ferie')
    CompanyProfile.objects.get_or_create(company=co)
    role = Role.objects.create(company=co, nom='Commercial A65f', permissions=list(COMMERCIAL_PERMISSIONS))
    u = U.objects.create_user(username='accept-alea65f', password='x', company=co, role=role)
    lead = Lead.objects.create(company=co, nom='Retard', prenom='R', owner=u, stage=stages.CONTACTED, telephone='+212661000966')
    RelanceEtape.objects.filter(lead=lead).delete()
    Lead.objects.filter(pk=lead.pk).update(relance_date=datetime.date(2026, 10, 9))
    def lu(j):
        return [lead.pk in set(relances_du_jour(co, u, scope='overdue', today=j).values_list('pk', flat=True)),
                any(i['kind'] == 'relance' and i['link'].endswith(f'lead={lead.pk}') and i['urgency'] == 'overdue' for i in ma_file_commercial_items(co, u, today=j))]
    res['sans_ferie_lundi'] = lu(datetime.date(2026, 10, 12))
    Holiday.objects.create(company=co, nom='Ferie societe essai', date=datetime.date(2026, 10, 12), recurrent_annuel=False)
    res['ferie_lundi'] = lu(datetime.date(2026, 10, 12))
    res['ferie_mardi'] = lu(datetime.date(2026, 10, 13))
    transaction.set_rollback(True)
sortie(res)`)
  expect(r.sans_ferie_lundi, 'sans férié : lundi 12/10 en retard partout').toEqual([true, true])
  expect(r.ferie_lundi, 'lundi 12/10 férié société : pas en retard (ni Relances ni Ma file)').toEqual([false, false])
  expect(r.ferie_mardi, 'mardi 13/10 : en retard partout').toEqual([true, true])
})

// ═══════════════════════════ AFAC103 ═══════════════════════════
const etapeF = groupe('AFAC', ['AFAC103'])
etapeF('P103.2.facture_sans_devis', ['AFAC103'], async ({ page }) => {
  const r = page.request
  const m = uniq('A103S').replace(/[^A-Za-z0-9]/g, '').slice(-8)
  const lead = await nouveauLead(r, `AFAC103S ${m}`)
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Prestation AFAC103S ${m}`, prix_vente: '10000.00', prix_achat: '100.00' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AFAC103S' } }), 'acceptation')
  const ids = await py(`from apps.ventes.models import Devis, Facture, LigneFacture
from decimal import Decimal as D
d = Devis.objects.get(pk=${d.id})
def fac(ref, devis, ttc):
    ttc = D(ttc); ht = (ttc / D('1.2')).quantize(D('0.01'))
    f = Facture.objects.create(company_id=1, devis=devis, client=d.client, reference=ref, statut='emise', type_facture='acompte', taux_tva=D('20.00'), date_emission=timezone.localdate())
    LigneFacture.objects.create(facture=f, produit=d.lignes.first().produit, designation='Acompte', quantite=D('1'), prix_unitaire=ht, remise=D('0'), taux_tva=D('20.00'))
    return f.id
sortie(dict(F=fac('FAC-SD-F-${m}', None, '12000.00'), G=fac('FAC-SD-G-${m}', d, '8000.00')))`)
  await lireJson(await r.post(`${API}/ventes/factures/${ids.F}/enregistrer-paiement/`, { ...T, data: { montant: '5000.00', date_paiement: new Date().toISOString().slice(0, 10), mode: 'virement', reference: `VIR-${m}` } }), 'paiement F')
  await page.goto('/ventes/factures')
  await page.getByPlaceholder('Référence, client').fill(m)
  const ligne = page.locator(`#facture-row-${ids.F}`).first()
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  await ligne.getByTitle("Plus d'actions").click()
  await page.getByTestId('annuler-facture').click()
  const dlg = page.getByRole('dialog').filter({ hasText: `Annuler la facture FAC-SD-F-${m}` })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.getByRole('radio', { name: /Transférer/ }).check()
  const select = dlg.getByLabel('Facture cible')
  await expect(select).toBeVisible()
  const options = await select.locator('option').evaluateAll((o) => o.map((x) => x.value).filter(Boolean))
  expect(options, `F sans devis : aucune cible listée, même avec G (même client) ouverte (${JSON.stringify(options)})`).toEqual([])
  const refus = await r.post(`${API}/ventes/factures/${ids.F}/annuler/`, { ...T, data: { acompte: { action: 'transferer', facture_cible: ids.G } } })
  expect(refus.status(), 'G refusée par le serveur').toBeGreaterThanOrEqual(400)
  expect(refus.status()).toBeLessThan(500)
})

// ═══════════════════════════ AARG57 ═══════════════════════════
const etapeG = groupe('AARG', ['AARG57'])
etapeG('PA4.11.escompte_j5_releve_pdf', ['AARG57'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const lead = await nouveauLead(r, `AARG57R ${m}`)
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Prestation AARG57R ${m}`, prix_vente: '1000.00', prix_achat: '100.00' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AARG57R' } }), 'acceptation')
  const fc = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture')
  await r.post(`${API}/ventes/factures/${fc.facture_id}/emettre/`, { ...T, data: {} })
  const f = await py(`from apps.ventes.models import Facture
t = timezone.localdate()
Facture.objects.filter(pk=${fc.facture_id}).update(escompte_pct=2, escompte_jours=10, date_emission=t - datetime.timedelta(days=5))
f = Facture.objects.get(pk=${fc.facture_id})
sortie(dict(client=f.client_id, emission=str(f.date_emission), ttc=str(f.total_ttc), j5=str(t)))`)
  expect(Number(f.ttc), 'facture 1 200 TTC').toBe(1200)
  await lireJson(await r.post(`${API}/ventes/factures/${fc.facture_id}/enregistrer-paiement/`, { ...T, data: { montant: '1176.00', mode: 'virement', date_paiement: f.j5 } }), 'paiement J+5')
  const e = await py(`from apps.ventes.models import Facture, Paiement, Avoir
f = Facture.objects.get(pk=${fc.facture_id})
pa = list(Paiement.objects.filter(facture=f))
sortie(dict(statut=f.statut, pa=[[str(x.montant), str(x.escompte_montant or 0), str(x.date_paiement)] for x in pa],
  av=[[str(x.total_ht), str(x.total_ttc - x.total_ht), str(x.total_ttc)] for x in Avoir.objects.filter(facture=f)]))`)
  expect(e.statut, 'payée').toBe('payee')
  expect(e.pa.map((x) => [Number(x[0]), Number(x[1]), x[2]]), 'un paiement 1 176 daté J+5 sans escompte_montant').toEqual([[1176, 0, f.j5]])
  expect(e.av.map((a) => a.map((v) => Math.abs(Number(v)))), 'avoir 20 HT / 4 TVA / 24 TTC').toEqual([[20, 4, 24]])
  const lirePdf = async () => {
    const rep = await r.get(`${API}/ventes/clients/${f.client}/releve-pdf/`, T)
    expect(rep.status(), 'relevé PDF').toBe(200)
    expect(rep.headers()['content-type']).toContain('pdf')
    return textePdf(await rep.body())
  }
  const txt = await lirePdf()
  const compact = txt.replace(/[\s  ]/g, '')
  expect(compact, `relevé : paiement 1 176 (${txt.slice(0, 600)})`).toMatch(/1176[,.]00/)
  expect(compact, 'relevé : avoir 24').toMatch(/24[,.]00/)
  expect(txt, 'relevé : aucune ligne « escompte »').not.toMatch(/escompte/i)
  expect(txt, 'relevé : mention d\'avoir').toMatch(/avoir/i)
  expect((await lirePdf()).replace(/[\s  ]/g, ''), 'relecture identique').toBe(compact)
})

// ═══════════════════════════ ADVS ═══════════════════════════
const etapeD = groupe('ADVS', ['ADVS3', 'ADVS14', 'ADVS40', 'ADVS43'])
const produitEssai = async (r, nom, pv) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom, prix_vente: pv, prix_achat: '111.11' } }), 'produit')
const ligneD = (p, q, pu, ordre = 0) => ({ produit: p.id, designation: p.nom, quantite: String(q), prix_unitaire: pu, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre })
async function devisStandard(r, tag) {
  const m = marque()
  const lead = await nouveauLead(r, `ADVS ${tag} ${m}`, { type_installation: 'residentiel', facture_hiver: '1500' })
  const pan = await produitEssai(r, `Panneau mono 550W ${m}`, '1000.00')
  const ond = await produitEssai(r, `Onduleur réseau 10kW ${m}`, '10000.00')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: [ligneD(pan, 12, '1000.00'), ligneD(ond, 1, '10000.00', 1)] } }), 'devis')
  return { lead, d, m }
}

etapeD('PA3-01.arrondi_centaine_cas_et_ecran', ['ADVS3'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const lead = await nouveauLead(r, `ADVS3b ${m}`, { type_installation: 'residentiel', facture_hiver: '1500' })
  const pan = await produitEssai(r, `Panneau mono 550W ${m}`, '833.33')
  const serveur = async (q, pu) => {
    const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: [ligneD(pan, q, pu)] } }), 'devis')
    const rel = await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'relu')
    const ht = Math.round(Number(rel.total_ht_net ?? rel.total_ht) * 100)
    const tva = Math.round(Number(rel.total_tva ?? rel.tva) * 100)
    expect(ht + tva, `ht_net + tva == ttc au centime (${q} × ${pu})`).toBe(Math.round(Number(rel.total_ttc) * 100))
    expect(Number(rel.lignes[0].prix_unitaire), 'aucune ligne repricée').toBeCloseTo(Number(pu), 2)
    return Number(rel.total_ttc)
  }
  const cas = [[3, '833.33'], [7, '833.33'], [6, '833.33'], [1, '2500.00'], [1, '2464.17'], [1, '47.50']]
  // 7 × 833,33 HT = 5 833,31 HT → 6 999,97 TTC → 7 000 (remonte) ; 6 × → 5 999,98 → 6 000.
  const attendus = { '3|833.33': 3000, '7|833.33': 7000, '6|833.33': 6000, '1|2500.00': 3000, '1|2464.17': 2900, '1|47.50': 57 }
  const lus = {}
  for (const [q, pu] of cas) lus[`${q}|${pu}`] = await serveur(q, pu)
  expect(lus, 'totaux serveur : remonte sous 1 MAD, 3 000,00 et 2 957 inchangés').toEqual(attendus)
  // Écran : le module réellement livré (`remise.js::totauxCanoniques`, celui du générateur) rend les MÊMES totaux.
  const { pathToFileURL } = await import('node:url')
  const { RACINE } = await import('./_enregistrement.js')
  const mod = await import(pathToFileURL(`${RACINE}frontend/src/features/ventes/remise.js`).href)
  const ecran = {}
  for (const k of Object.keys(attendus)) {
    const [q, pu] = k.split('|')
    ecran[k] = mod.totauxCanoniques([{ quantite: q, prix_unitaire: pu, taux: 20 }], 0, { arrondiPas: mod.PAS_ARRONDI_DEVIS }).ttc
  }
  expect(ecran, 'écran = serveur').toEqual(attendus)
})

etapeD('PA3-02.pdf_partage_lien_et_qr', ['ADVS14'], async ({ page }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS14b')
  const vu = await py(`import fitz, cv2, numpy as np
from rest_framework.test import APIClient
from apps.ventes.models import ShareLink, Devis
dv = Devis.objects.get(pk=${d.id})
c = APIClient(); c.force_authenticate(U.objects.get(username='demo_admin'))
rep = c.get('/api/django/ventes/devis/${d.id}/pdf-partage/', HTTP_HOST='localhost')
token = ShareLink.for_devis(dv).token
doc = fitz.open(stream=rep.content, filetype='pdf')
liens = [l.get('uri') for p in doc for l in p.get_links() if l.get('uri')]
texte = ' '.join(p.get_text() for p in doc)
qr = []
det = cv2.QRCodeDetector()
for p in doc:
    pix = p.get_pixmap(matrix=fitz.Matrix(4, 4), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY if pix.n == 3 else cv2.COLOR_RGBA2GRAY)
    val, pts, _ = det.detectAndDecode(img)
    if val: qr.append(val)
sortie(dict(code=rep.status_code, pages=doc.page_count, token=token, liens=liens, qr=qr, statut=Devis.objects.get(pk=${d.id}).statut,
            achat='111,11' in texte or '111.11' in texte))`)
  expect(vu.code).toBe(200)
  expect(vu.liens.some((l) => l.includes(`/proposition/${vu.token}`)), `lien /proposition/<token> dans le PDF (liens : ${JSON.stringify(vu.liens).slice(0, 300)})`).toBe(true)
  expect(vu.qr.length, `QR décodé sur une page (${vu.pages} pages)`).toBeGreaterThanOrEqual(1)
  expect(vu.qr.some((q) => q.includes(`/proposition/${vu.token}`)), `le QR décodé pointe sur /proposition/<token> (${JSON.stringify(vu.qr)})`).toBe(true)
  expect(vu.achat, 'prix d\'achat jamais imprimé').toBe(false)
  expect(vu.statut, 'GET sans effet : brouillon').toBe('brouillon')
})

etapeD('PA3-13.bcf_envoye_refus', ['ADVS40'], async ({ page }) => {
  const r = page.request
  const { d, lead } = await devisStandard(r, 'ADVS40b')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ADVS40b' } }), 'acceptation')
  const poser = (statut) => py(`from apps.installations.models import Installation
from apps.achats.models import BonCommandeFournisseur as B
from apps.stock.models import Fournisseur
i = Installation.objects.get(devis_id=${d.id})
fr = Fournisseur.objects.filter(company_id=1).first()
b = B.objects.create(company_id=1, fournisseur=fr, reference='BCF-ADVS40B-${d.id}-${statut}', statut='${statut}', chantier_origine=i)
sortie(dict(id=b.id, ref=b.reference, inst=i.id))`)
  const etat = (inst, bcf) => py(`from apps.installations.models import Installation
from apps.achats.models import BonCommandeFournisseur as B
from apps.ventes.models import Devis
i = Installation.objects.get(pk=${inst})
sortie(dict(etape=str(getattr(i, 'etape', '')), statut_inst=str(getattr(i, 'statut', '')), bcf=B.objects.get(pk=${bcf}).statut, devis=Devis.objects.get(pk=${d.id}).statut))`)
  // BCF brouillon : aucun blocage (le témoin vient d'abord, la sortie de « Signé » est ensuite rétablie).
  const brouillon = await poser('brouillon')
  const envoye = await poser('envoye')
  const avant = await etat(envoye.inst, envoye.id)
  const sortir = await r.patch(`${API}/crm/leads/${lead.id}/`, { ...T, data: { stage: 'QUOTE_SENT', confirme_recul: true } })
  const corps = await sortir.text()
  expect(sortir.status(), `sortie de Signé refusée (${corps.slice(0, 300)})`).toBe(409)
  expect(corps, 'raison exacte : BCF envoyé, annulez-le d\'abord').toContain(`le bon de commande fournisseur ${envoye.ref} est envoyé : annulez-le d'abord.`)
  expect(corps, 'le BCF brouillon n\'est pas nommé').not.toContain(brouillon.ref)
  expect(await etat(envoye.inst, envoye.id), 'chantier, devis, BCF inchangés après le refus').toEqual(avant)
  expect((await lireJson(await r.get(`${API}/crm/leads/${lead.id}/`, T), 'lead')).stage, 'lead toujours Signé').toBe('SIGNED')
  // Témoin : BCF envoyé annulé ET brouillon présent : plus de blocage.
  await py(`from apps.achats.models import BonCommandeFournisseur as B
B.objects.filter(pk=${envoye.id}).update(statut='annule')
sortie(1)`)
  const ok = await r.patch(`${API}/crm/leads/${lead.id}/`, { ...T, data: { stage: 'QUOTE_SENT', confirme_recul: true } })
  expect(ok.status(), `BCF brouillon/annulé : aucun blocage (${(await ok.text()).slice(0, 200)})`).toBe(200)
})

etapeD('PA3.meta_rejeu_parcours', ['ADVS43'], async ({ page }) => {
  const { RACINE } = await import('./_enregistrement.js')
  const { spawnSync } = await import('node:child_process')
  const { d } = await devisStandard(page.request, 'ADVS43')
  const jouer = (id) => spawnSync('python', ['scripts/rejouer_parcours.py', 'PA3', '--enregistrement', String(id), '--sans-enregistrement'], { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  const ok = jouer(d.id)
  const sortie = `${ok.stdout}\n${ok.stderr}`
  expect(sortie, `rejeu PA3 : PA3-01 joué (${sortie.slice(0, 400)})`).toMatch(/PA3-01 : POST \/api\/django\/ventes\/devis\/atomic\//)
  expect(sortie, 'base inchangée (transaction annulée)').toMatch(/Base inchangée/)
  // Contre-épreuve : un enregistrement qui n'existe pas fait ÉCHOUER le rejeu (il ne passe pas par accident).
  const faux = jouer(999999999)
  expect(faux.status, `contre-épreuve : enregistrement inexistant -> échec (code ${faux.status}) ${`${faux.stdout}${faux.stderr}`.slice(0, 300)}`).not.toBe(0)
})
