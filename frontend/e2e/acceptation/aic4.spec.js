// AIC — preuve en direct AIC98 (D-COP-2 = guide_strict) : une BAISSE DE PRIX DE LIGNE compte comme une remise pour le seuil
// d'approbation (T17) — jouée À PART des specs LLM d'aic.spec.js / aic2.spec.js (aucun modèle, API seulement + écran liste
// des devis), vague d'acceptation 8 sur runner GitHub (METHODE §C.4 point 7).
// Montage : seuil de la société de démo posé à 2 % (rétabli en fin d'étape), un devis d'UNE ligne dont le prix de référence
// (prix standard du produit) vaut 10 000, baissé à 9 000 par la VRAIE route `PATCH /devis-lignes/` (qui pose `prix_manuel`,
// comme l'assistant), sans remise globale. L'envoi est celui d'un compte « Responsable » (un administrateur approuve
// implicitement : il ne sert que de geste d'approbation).
import { expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, connexionApi } from '../helpers.js'

const etape = groupe('AIC', ['AIC98'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()
const SOC = `U.objects.get(username='demo_admin').company_id`

etape('P4.1-AIC98-baisse-de-ligne', ['AIC98'], async ({ page, testInfo }) => {
  testInfo.setTimeout(600_000)
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
  const admin = page.request
  const m = marque()
  const resp = `aic98_resp_${m.toLowerCase()}`
  // Given : seuil 2 %, un « Responsable » (non administrateur), deux devis d'une ligne à 10 000 (prix de référence 10 000).
  const f = await py(`from decimal import Decimal as D
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
co = U.objects.get(username='demo_admin').company
profil = CompanyProfile.get(co)
avant = profil.discount_approval_threshold
CompanyProfile.objects.filter(pk=profil.pk).update(discount_approval_threshold=D('2'))
u = compte(${J(resp)}, role=Role.objects.get(company_id=co.id, nom='Responsable').pk, societe=co.id)
cl = Client.objects.create(company=co, nom='ACC AIC98', prenom='${m}', email='acc-aic98-${m.toLowerCase()}@example.invalid')
p = Produit.objects.create(company=co, nom='Onduleur ACC-AIC98 ${m}', sku='ACC-AIC98-${m}', prix_vente=D('10000'), prix_achat=D('6000'), quantite_stock=5)
def devis(suffixe, remise_globale='0', prix='10000', produit=True, manuel=False):
    d = Devis.objects.create(company=co, reference='DEV-ACC-AIC98-${m}-' + suffixe, client=cl, statut='brouillon', taux_tva=D('20'), remise_globale=D(remise_globale))
    l = LigneDevis.objects.create(devis=d, produit=p if produit else None, designation='Onduleur ACC-AIC98', quantite=1, prix_unitaire=D(prix), remise=D('0'), prix_manuel=manuel)
    return dict(id=d.id, ref=d.reference, ligne=l.id)
sortie(dict(avant=None if avant is None else str(avant), resp_admin=bool(u.is_admin_role), produit=p.id, client=cl.id,
  baisse=devis('B'), globale=devis('G', remise_globale='10'), reference=devis('R'), hausse=devis('H'), libre=devis('L', prix='9000', produit=False)))`)
  expect(f.resp_admin, 'le compte d\'envoi n\'est PAS administrateur').toBe(false)
  const profondeur = (id) => py(`from apps.ventes.domain.tarification import profondeur_remise_effective
from apps.ventes.models import Devis
sortie(str(profondeur_remise_effective(Devis.objects.get(pk=${id}))))`)
  const apres = []
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  apres.push(() => ctx.dispose())
  try {
    await connexionApi(ctx, { username: resp, password: MDP_ESSAI })
    const envoyer = (id) => ctx.post(`${API}/ventes/devis/${id}/share-link/`, { ...T, data: { envoi: true } })
    const lire = async (id) => lireJson(await admin.get(`${API}/ventes/devis/${id}/`, T), `devis ${id}`)

    // Contrôle : à 10 000 (prix de référence) la profondeur vaut 0 % ; une HAUSSE vaut 0 % ; une ligne SANS produit garde son prix saisi.
    expect(await profondeur(f.baisse.id), 'ligne au prix de référence ⇒ 0 %').toBe('0.00')
    expect(await profondeur(f.reference.id), 'ligne au prix de référence ⇒ 0 %').toBe('0.00')
    const hausse = await admin.patch(`${API}/ventes/devis-lignes/${f.hausse.ligne}/`, { ...T, data: { prix_unitaire: '12000' } })
    expect(hausse.status(), `PATCH hausse ${(await hausse.text()).slice(0, 200)}`).toBe(200)
    expect(await profondeur(f.hausse.id), 'une hausse de prix de ligne ⇒ 0 %').toBe('0.00')
    expect(await profondeur(f.libre.id), 'ligne sans produit ⇒ base = prix saisi ⇒ 0 %').toBe('0.00')

    // When : le prix de la ligne passe de 10 000 à 9 000 par la route de l'écran / de l'assistant (prix TAPÉ).
    const baisse = await admin.patch(`${API}/ventes/devis-lignes/${f.baisse.ligne}/`, { ...T, data: { prix_unitaire: '9000' } })
    expect(baisse.status(), `PATCH baisse ${(await baisse.text()).slice(0, 200)}`).toBe(200)
    const ligne = await lireJson(await admin.get(`${API}/ventes/devis-lignes/${f.baisse.ligne}/`, T), 'ligne relue')
    expect(Number(ligne.prix_unitaire), 'ligne relue à 9 000').toBe(9000)
    expect(ligne.prix_manuel, 'prix TAPÉ marqué').toBe(true)
    expect(Number((await lire(f.baisse.id)).remise_globale), 'aucune remise globale').toBe(0)

    // Then : profondeur effective 10 % et envoi refusé par le Responsable (400, nommant la remise et le seuil).
    expect(await profondeur(f.baisse.id), 'profondeur effective = 10 %').toBe('10.00')
    const refus = await envoyer(f.baisse.id)
    const corpsRefus = await refus.text()
    expect(refus.status(), `envoi refusé (${corpsRefus.slice(0, 300)})`).toBe(400)
    expect(corpsRefus, 'message : remise de 10 %').toMatch(/Remise de 10(?:[.,]0+)? %/)
    expect(corpsRefus, 'message : seuil de 2 %').toMatch(/seuil de 2(?:[.,]0+)? %/)
    // « comme pour une remise de 10 % » : le devis à remise globale 10 % est refusé avec le MÊME message.
    const refusGlobale = await envoyer(f.globale.id)
    const corpsGlobale = await refusGlobale.text()
    expect(refusGlobale.status(), `remise globale 10 % refusée (${corpsGlobale.slice(0, 300)})`).toBe(400)
    const nombres = (s) => (s.match(/\d+(?:[.,]\d+)?/g) || []).map((x) => Number(x.replace(',', '.')))
    expect(nombres(corpsRefus), 'même message (mêmes pourcentages) pour la baisse de ligne et pour la remise globale').toEqual(nombres(corpsGlobale))
    // Persistance : relu par l'API et en base ⇒ brouillon tant que l'accord manque ; prix de ligne inchangé à 9 000.
    for (const id of [f.baisse.id, f.globale.id]) {
      expect((await lire(id)).statut, `devis ${id} relu : brouillon`).toBe('brouillon')
    }
    expect(await py(`from apps.ventes.models import Devis
sortie([Devis.objects.get(pk=${f.baisse.id}).statut, Devis.objects.get(pk=${f.baisse.id}).remise_approuvee])`), 'relu en base : brouillon, aucune approbation').toEqual(['brouillon', false])
    // Écran : la liste des devis montre le devis toujours « Brouillon ».
    await page.goto(`/ventes/devis?q=${encodeURIComponent(f.baisse.ref)}`)
    const rangee = page.getByRole('row').filter({ hasText: f.baisse.ref })
    await expect(rangee.first(), 'liste des devis : la ligne du devis').toBeVisible({ timeout: 60_000 })
    await expect(rangee.first(), 'liste des devis : statut Brouillon').toContainText(/Brouillon/i)

    // Contrôle positif : l'accord d'un administrateur lève le refus (c'est bien la garde de remise qui refusait).
    await lireJson(await admin.post(`${API}/ventes/devis/${f.baisse.id}/approuver-remise/`, { ...T, data: {} }), 'approbation')
    const accord = await envoyer(f.baisse.id)
    expect(accord.status(), `envoi après approbation (${(await accord.text()).slice(0, 200)})`).toBe(200)
    expect((await lire(f.baisse.id)).statut, 'envoyé après accord').toBe('envoye')
  } finally {
    await py(`from decimal import Decimal as D
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Devis
co = U.objects.get(username='demo_admin').company
CompanyProfile.objects.filter(company=co).update(discount_approval_threshold=${f.avant === null ? 'None' : `D(${J(f.avant)})`})
Devis.objects.filter(client_id=${f.client}, statut='brouillon').delete()
Devis.objects.filter(client_id=${f.client}).update(is_active=False)
Produit.objects.filter(pk=${f.produit}).update(is_archived=True)
U.objects.filter(username=${J(resp)}).update(is_active=False)
sortie(1)`).catch((e) => console.log(`[nettoyage] ${e.message}`))
    for (const fn of apres) await fn().catch(() => undefined)
  }
})
