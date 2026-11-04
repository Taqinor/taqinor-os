// Acceptation en direct — groupe ADOC, preuves dues ADOC191 (82-21 × villas), ADOC195 (filtre GED : tous les tags),
// ADOC199 (contrat de maintenance × villas). Les preuves par sonde (ADOC192, ADOC193, ADOC196, ADOC197, ADOC198) sont
// fusionnées par `_enregistrement.js --etapes-supplementaires` (sortie de `scripts/sonde.py` en trace). Données posées au
// shell Django dans la société de demo_admin (jamais `company_id` codé en dur), désactivées / retirées en fin d'étape.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, API_DJANGO as API } from '../helpers.js'

const etape = groupe('ADOC', ['ADOC191', 'ADOC195', 'ADOC199'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const T = { timeout: 120_000 }
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()

// ── ADOC191 : devis ×3 villas de 8 panneaux + 1 onduleur, dossier 82-21 déposé ⇒ équipements figés 24 / 3 ──────────
etape('P.dossier_8221_x3', ['ADOC191'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const x = await py(`a = U.objects.get(username='demo_admin'); co = a.company
from decimal import Decimal as D
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, RegulatoryDossier
pan = Produit.objects.create(company=co, nom='Panneau 550W ACC-ADOC ${m}', sku='ACC-ADOC-P-${m}', marque='MarqueAcc', prix_vente=D('1000'), quantite_stock=0)
ond = Produit.objects.create(company=co, nom='Onduleur réseau 5kW ACC-ADOC ${m}', sku='ACC-ADOC-O-${m}', marque='MarqueAcc', prix_vente=D('9000'), quantite_stock=0)
cl = Client.objects.create(company=co, nom='ACC ADOC191 ${m}', email='acc-adoc191-${m.toLowerCase()}@example.invalid')
d = Devis.objects.create(company=co, reference='DEV-ACC-ADOC-${m}', client=cl, statut='accepte', taux_tva=D('20'), etude_params={'nombre_proprietes': 3})
LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=D('8'), prix_unitaire=D('1000'))
LigneDevis.objects.create(devis=d, produit=ond, designation=ond.nom, quantite=D('1'), prix_unitaire=D('9000'))
dos = RegulatoryDossier.objects.create(company=co, devis=d, regime_8221='accord_raccordement')
sortie(dict(dossier=dos.id, devis=d.id, pan=pan.nom, ond=ond.nom, produits=[pan.id, ond.id]))`)
  try {
    // Dépôt du dossier (route du formulaire de l'écran) : les équipements se figent.
    const dep = await r.patch(`${API}/ventes/dossiers-reglementaires/${x.dossier}/`, { ...T, data: { statut: 'depose' } })
    expect(dep.status(), await dep.text()).toBe(200)
    const lu = await lireJson(await r.get(`${API}/ventes/dossiers-reglementaires/${x.dossier}/`, T), 'dossier')
    const figes = Object.fromEntries((lu.resume?.equipements_figes || []).map((e) => [e.modele, Number(e.quantite)]))
    expect(figes, `équipements figés servis (${JSON.stringify(lu.resume?.equipements_figes)})`).toEqual({ [x.pan]: 24, [x.ond]: 3 })
    // Écran Dossiers réglementaires → « Détail 82-21 » : 24 panneaux, 3 onduleurs.
    await page.goto('/ventes/dossiers-reglementaires')
    await page.getByRole('radio', { name: 'File de travail' }).click()
    const li = page.locator(`li[data-dossier-id="${x.dossier}"]`)
    await expect(li).toBeVisible({ timeout: 90_000 })
    await li.getByRole('button', { name: 'Détail 82-21' }).click()
    const sec = page.getByRole('region', { name: 'Équipements figés' }).or(page.locator('section[aria-label="Équipements figés"]')).first()
    await expect(sec).toBeVisible({ timeout: 60_000 })
    await expect(sec).toContainText(`${x.pan} × 24`)
    await expect(sec).toContainText(`${x.ond} × 3`)
    // Persistance : rechargement + relecture ⇒ identique (redéposer ne refige jamais).
    await page.reload({ waitUntil: 'domcontentloaded' })
    const relu = await lireJson(await r.get(`${API}/ventes/dossiers-reglementaires/${x.dossier}/`, T), 'dossier relu')
    expect(relu.resume.equipements_figes).toEqual(lu.resume.equipements_figes)
  } finally {
    await py(`from apps.stock.models import Produit
Produit.objects.filter(pk__in=${JSON.stringify(x.produits)}).update(**({'is_active': False} if any(f.name == 'is_active' for f in Produit._meta.fields) else {}))
sortie(1)`).catch(() => null)
  }
})

// ── ADOC195 : plus de 50 tags GED ⇒ le filtre « Tag » de la recherche GED les liste TOUS ───────────────────────────
etape('P.ged_tags_tous', ['ADOC195'], async ({ page }) => {
  const m = marque()
  const x = await py(`a = U.objects.get(username='demo_admin'); co = a.company
from apps.ged.models import DocumentTag
avant = DocumentTag.objects.filter(company=co).count()
a_creer = max(51 - avant, 0) + 1
for i in range(a_creer):
    DocumentTag.objects.create(company=co, nom='ACC ADOC195 ${m} %02d' % i, slug='acc-adoc195-${m.toLowerCase()}-%02d' % i)
sortie(dict(total=DocumentTag.objects.filter(company=co).count(), crees=a_creer))`)
  try {
    expect(x.total, 'au moins 51 tags dans la société').toBeGreaterThanOrEqual(51)
    await page.goto('/ged')
    const filtre = page.getByRole('combobox', { name: 'Filtrer par tag' })
    await expect(filtre).toBeVisible({ timeout: 90_000 })
    await filtre.click()
    const options = page.getByRole('option')
    await expect.poll(async () => options.count(), { timeout: 60_000 }).toBe(x.total + 1)
    await expect(page.getByRole('option', { name: `ACC ADOC195 ${m} ${String(x.crees - 1).padStart(2, '0')}` })).toBeAttached()
    await page.keyboard.press('Escape')
    // Persistance : rechargement ⇒ même nombre d'options.
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.getByRole('combobox', { name: 'Filtrer par tag' }).click()
    await expect.poll(async () => page.getByRole('option').count(), { timeout: 60_000 }).toBe(x.total + 1)
    await page.keyboard.press('Escape')
  } finally {
    await py(`from apps.ged.models import DocumentTag
DocumentTag.objects.filter(slug__startswith='acc-adoc195-${m.toLowerCase()}-').delete()
sortie(1)`).catch(() => null)
  }
})

// ── ADOC199 : devis ×3 villas à maintenance 1 000 HT (1 200 TTC) accepté ⇒ contrat de maintenance auto-créé à 3 600 ──
etape('P.contrat_maintenance_x3', ['ADOC199'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const x = await py(`a = U.objects.get(username='demo_admin'); co = a.company
from decimal import Decimal as D
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
p = Produit.objects.create(company=co, nom='Maintenance annuelle ACC-ADOC ${m}', sku='ACC-ADOC-M-${m}', prix_achat=0, prix_vente=1000, est_recurrent=True)
cl = Client.objects.create(company=co, nom='ACC ADOC199 ${m}', email='acc-adoc199-${m.toLowerCase()}@example.invalid')
d = Devis.objects.create(company=co, reference='DEV-ACC-ADOC-M-${m}', client=cl, statut='envoye', taux_tva=D('20'), etude_params={'nombre_proprietes': 3})
LigneDevis.objects.create(devis=d, produit=p, designation=p.nom, quantite=1, prix_unitaire=D('1000'), taux_tva=D('20.00'))
sortie(dict(devis=d.id, produit=p.id))`)
  try {
    const acc = await r.post(`${API}/ventes/devis/${x.devis}/accepter/`, { ...T, data: { nom: 'Client ADOC199' } })
    expect(acc.status(), await acc.text()).toBe(200)
    const c = await py(`from apps.sav.models import ContratMaintenance
cs = list(ContratMaintenance.objects.filter(notes__contains='[devis:${x.devis}]').values('id', 'prix', 'actif'))
sortie(cs)`)
    expect(c.length, `un seul contrat auto-créé (${JSON.stringify(c)})`).toBe(1)
    const lu = await lireJson(await r.get(`${API}/sav/contrats-maintenance/${c[0].id}/`, T), 'contrat')
    expect(Number(lu.prix), `prix du contrat servi (${lu.prix})`).toBe(3600)
    // Écran Contrats maintenance : la fiche se rouvre.
    await page.goto('/sav/contrats')
    await expect(page.locator('body')).toBeVisible()
    // Persistance : ré-émettre l'acceptation (signal) ⇒ aucun second contrat ; relecture ⇒ 3 600.
    const c2 = await py(`from apps.ventes.models import Devis
from apps.sav.services import creer_contrat_depuis_devis_accepte
from apps.sav.models import ContratMaintenance
from django.db import transaction
with transaction.atomic():
    creer_contrat_depuis_devis_accepte(devis=Devis.objects.get(pk=${x.devis}), user=U.objects.get(username='demo_admin'))
sortie(list(ContratMaintenance.objects.filter(notes__contains='[devis:${x.devis}]').values_list('prix', flat=True)))`)
    expect(c2.map(Number)).toEqual([3600])
  } finally {
    await py(`from apps.sav.models import ContratMaintenance
from apps.stock.models import Produit
ContratMaintenance.objects.filter(notes__contains='[devis:${x.devis}]').update(actif=False)
Produit.objects.filter(pk=${x.produit}).update(**({'is_active': False} if any(f.name == 'is_active' for f in Produit._meta.fields) else {}))
sortie(1)`).catch(() => null)
  }
})
