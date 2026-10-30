// ASTK239 — acceptation en direct UNIQUE du groupe ASTK côté stock : scénarios S-A à S-F de
// docs/audits/2026-10-06-stock.md §2 et P6 (WMS / portail fournisseur) rejoués sur la pile locale à
// deux sociétés (1 = « TAQINOR Démo », 43 = société voisine), par les VRAIES routes HTTP.
//
// Comptes : `acc239_*` créés par `manage.py shell` (E2E_DJANGO_EXEC) avec un mot de passe d'essai
// local, désactivés en fin de spec. Données : produits/BCF « ACC239 … » créés par la spec ; aucune
// donnée de production, aucun envoi réel (le « WhatsApp » d'un devis ne fait que préparer un lien).
// Une étape non jouable ici lève « NON JOUABLE : <raison> » — jamais un PASS.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawn } from 'node:child_process'
import { groupe } from './_oracles.js'
import { API_DJANGO, lireJson, telephoneMobileUnique, textePdf, uniq } from '../helpers.js'

const etape = groupe('ASTK', ['ASTK239'])
test.describe.configure({ timeout: 900_000 })

const PW = 'Acc239-essai-local-2026!'
const T = { timeout: 120_000 }
const ESPACES = new RegExp(String.raw`[\s` + String.fromCharCode(160, 0x202f) + ']+', 'g')
const plat = (s) => String(s).replace(ESPACES, '')

// ── manage.py shell persistant (comptes) ─────────────────────────────────────────────────────
const SERVEUR = [
  'import sys, json, base64, io, contextlib, traceback',
  'ns = {}',
  "print('@@PRET', flush=True)",
  'for ligne in sys.stdin:',
  '    ligne = ligne.strip()',
  '    if not ligne: continue',
  '    buf = io.StringIO()',
  '    try:',
  '        with contextlib.redirect_stdout(buf):',
  "            exec(base64.b64decode(ligne).decode(), ns)",
  "        sortie = {'ok': True, 'out': buf.getvalue()}",
  '    except BaseException:',
  "        sortie = {'ok': False, 'out': buf.getvalue(), 'err': traceback.format_exc()[-1800:]}",
  "    print('@@R' + json.dumps(sortie), flush=True)",
].join('\n')
let serveur = null
const attentes = []
let tampon = ''
function demarrerServeur() {
  if (serveur) return serveur.pret
  const [cmd, ...args] = (process.env.E2E_DJANGO_EXEC || 'docker compose exec -T django_core').split(' ')
  const proc = spawn(cmd, [...args, 'python', 'manage.py', 'shell', '-c', SERVEUR], { stdio: ['pipe', 'pipe', 'ignore'] })
  let pretOk
  const pret = new Promise((r) => { pretOk = r })
  proc.stdout.on('data', (d) => {
    tampon += d.toString()
    let i
    while ((i = tampon.indexOf('\n')) >= 0) {
      const l = tampon.slice(0, i).trim()
      tampon = tampon.slice(i + 1)
      if (l === '@@PRET') pretOk()
      else if (l.startsWith('@@R')) attentes.shift()?.(JSON.parse(l.slice(3)))
    }
  })
  serveur = { proc, pret }
  return pret
}
async function py(code) {
  await demarrerServeur()
  const rep = await new Promise((resolve) => {
    attentes.push(resolve)
    serveur.proc.stdin.write(`${Buffer.from(`import json\n${code}`).toString('base64')}\n`)
  })
  if (!rep.ok) throw new Error(`shell serveur : ${rep.err}`)
  const l = rep.out.split('\n').filter((x) => x.startsWith('@@')).pop()
  return l ? JSON.parse(l.slice(2)) : null
}
const PRELUDE = `
from django.contrib.auth import get_user_model
U = get_user_model()
def sortie(o): print('@@' + json.dumps(o, default=str))
`
const COMPTES = {
  acc239_com: { role: 4 }, // Commercial (société 1)
  acc239_tresp: { role: 5 }, // Technicien responsable (société 1)
  acc239_b: { role: 91, societe: 43 }, // Directeur de la société voisine
}
let pret = false
async function monterComptes() {
  if (pret) return
  await py(`${PRELUDE}
C = json.loads('${JSON.stringify(COMPTES)}')
for nom, c in C.items():
    soc = c.get('societe', 1)
    u, _ = U.objects.get_or_create(username=nom, defaults=dict(company_id=soc, role_id=c['role']))
    u.company_id = soc; u.role_id = c['role']; u.is_active = True
    u.email = nom + '@acc239.test'; u.must_change_password = False; u.failed_login_count = 0; u.locked_until = None
    u.totp_enabled = False; u.set_password('${PW}'); u.save()
sortie('ok')`)
  pret = true
}
test.afterAll(async () => {
  try {
    await py(`${PRELUDE}
U.objects.filter(username__startswith='acc239_').update(is_active=False)
sortie('ok')`)
  } catch { /* nettoyage au mieux */ }
  serveur?.proc.stdin.end()
})

const ctxCache = new Map()
/** Contexte API connecté (cookies) ; patiente le throttle « login » (429). */
async function api(testInfo, username) {
  if (ctxCache.has(username)) return ctxCache.get(username)
  const c = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await expect(async () => {
    const r = await c.post(`${API_DJANGO}/token/`, { data: { username, password: PW } })
    expect(r.status(), `connexion de ${username}`).toBe(200)
  }).toPass({ intervals: [10_000, 20_000, 30_000], timeout: 300_000 })
  ctxCache.set(username, c)
  return c
}

// ── montage de données (par l'API, société 1, demo_admin = page.request) ──────────────────────
const listeJson = (x) => (Array.isArray(x) ? x : (x?.results ?? []))
const j = async (res, quoi, statut) => {
  if (statut) expect(res.status(), `${quoi} → ${(await res.text()).slice(0, 300)}`).toBe(statut)
  return lireJson(res, quoi)
}
const creerProduit = (r, extra = {}) => r.post(`${API_DJANGO}/stock/produits/`, {
  ...T, data: { nom: uniq('ACC239 produit'), prix_vente: '1000.00', prix_achat: '600.00', quantite_stock: 0, tva: '20.00', ...extra },
}).then((x) => j(x, 'produit', 201))
const fournisseurDemo = async (r) => {
  const l = await j(await r.get(`${API_DJANGO}/stock/fournisseurs/?page_size=5`, T), 'fournisseurs')
  return l.results[0].id
}
async function creerBcfEnvoye(r, produit, quantite = 10, pu = '100.00') {
  const four = await fournisseurDemo(r)
  const bcf = await j(await r.post(`${API_DJANGO}/stock/bons-commande-fournisseur/`, {
    ...T, data: { fournisseur: four, date_commande: '2026-10-30', lignes: [{ produit, quantite, prix_achat_unitaire: pu }] },
  }), 'BCF', 201)
  await j(await r.post(`${API_DJANGO}/stock/bons-commande-fournisseur/${bcf.id}/envoyer/`, T), 'envoi BCF', 200)
  const relu = await j(await r.get(`${API_DJANGO}/stock/bons-commande-fournisseur/${bcf.id}/`, T), 'BCF relu')
  return { ...relu, ligne: relu.lignes[0].id, fournisseur: four }
}
async function recevoir(r, bcf, quantite, confirmer = true) {
  const rec = await j(await r.post(`${API_DJANGO}/stock/receptions-fournisseur/`, {
    ...T, data: { bon_commande: bcf.id, date_reception: '2026-10-30', lignes: [{ ligne_commande: bcf.ligne, quantite }] },
  }), 'réception', 201)
  if (confirmer) await j(await r.post(`${API_DJANGO}/stock/receptions-fournisseur/${rec.id}/confirmer/`, T), 'confirmation', 200)
  return rec
}
const stockDe = async (r, id) => Number((await j(await r.get(`${API_DJANGO}/stock/produits/${id}/`, T), 'produit relu')).quantite_stock)
async function creerDevis(r, produit, prix, { envoyer = false, lead } = {}) {
  const l = lead || await j(await r.post(`${API_DJANGO}/crm/leads/`, {
    ...T, data: { nom: uniq('ACC239 lead'), ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '800' },
  }), 'lead', 201)
  const d = await j(await r.post(`${API_DJANGO}/ventes/devis/`, {
    ...T, data: { lead: l.id, taux_tva: '20.00', mode_installation: 'residentiel' },
  }), 'devis', 201)
  await j(await r.post(`${API_DJANGO}/ventes/devis/${d.id}/replace-lines/`, {
    ...T, data: { lignes: [{ produit, designation: 'ACC239', quantite: '1.00', prix_unitaire: prix, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] },
  }), 'lignes', 200)
  if (envoyer) await j(await r.post(`${API_DJANGO}/ventes/devis/${d.id}/whatsapp/`, { ...T, data: {} }), 'envoi (lien WhatsApp préparé)', 200)
  return { devis: d, lead: l }
}
const lireDevis = async (r, id) => j(await r.get(`${API_DJANGO}/ventes/devis/${id}/`, T), 'devis relu')
const pdfDevis = async (r, id) => {
  const rep = await r.get(`${API_DJANGO}/ventes/devis/${id}/proposal/?pdf_mode=onepage`, T)
  expect(rep.status(), `/proposal devis ${id}`).toBe(200)
  return plat(await textePdf(await rep.body()))
}

// ── S-A — le prix catalogue bouge : brouillon suit, envoyé figé, négocié intact ───────────────
etape('S-A', ['ASTK239'], async ({ page, suivi }) => {
  const r = page.request
  const produit = await creerProduit(r, { prix_vente: '1000.00' })
  const a = await creerDevis(r, produit.id, '1000.00') // brouillon au prix catalogue
  const b = await creerDevis(r, produit.id, '1000.00', { envoyer: true }) // envoyé
  const c = await creerDevis(r, produit.id, '900.00', { lead: a.lead }) // brouillon au prix négocié
  expect((await lireDevis(r, b.devis.id)).statut).toBe('envoye')
  await j(await r.patch(`${API_DJANGO}/stock/produits/${produit.id}/`, { ...T, data: { prix_vente: '1500.00' } }), 'correction du prix', 200)
  await expect(async () => {
    const d = await lireDevis(r, a.devis.id)
    expect(d.lignes[0].prix_unitaire, 'brouillon recalé').toBe('1500.00')
    expect(d.total_ttc, 'total du brouillon recalculé').toBe('1800.00')
  }).toPass({ timeout: 90_000, intervals: [2_000, 3_000] })
  const envoye = await lireDevis(r, b.devis.id)
  expect(envoye.statut).toBe('envoye')
  expect(envoye.lignes[0].prix_unitaire, 'envoyé figé').toBe('1000.00')
  expect(envoye.total_ttc).toBe('1200.00')
  await expect(async () => {
    const h = await j(await r.get(`${API_DJANGO}/ventes/devis/${b.devis.id}/historique/`, T), 'historique')
    const note = h.find((x) => x.field === 'catalogue_envoye_conserve')
    expect(note, 'note « devis envoyé conservé »').toBeTruthy()
    expect(note.body).toMatch(/envoyé conservé/)
  }).toPass({ timeout: 60_000 })
  const negocie = await lireDevis(r, c.devis.id)
  expect(negocie.lignes[0].prix_unitaire, 'prix négocié intouchable').toBe('900.00')
  // Écran = /proposal (règle #4) : le PDF dit le même chiffre que le devis relu.
  expect(await pdfDevis(r, a.devis.id)).toContain('1500,00')
  const pdfEnvoye = await pdfDevis(r, b.devis.id)
  expect(pdfEnvoye).toContain('1000,00')
  expect(pdfEnvoye).not.toContain('1500,00')
  // Persistance : tout est relu après rechargement de l'application.
  await page.goto('/stock')
  await page.reload()
  expect((await lireDevis(r, b.devis.id)).lignes[0].prix_unitaire).toBe('1000.00')
  expect((await lireDevis(r, a.devis.id)).lignes[0].prix_unitaire).toBe('1500.00')
  suivi.verifie(6)
})

// ── S-B — aller-retour produit et kit : enregistrer sans toucher ⇒ objet identique ─────────────
etape('S-B', ['ASTK239'], async ({ page }) => {
  const r = page.request
  const champsMaitres = {
    code_barres: `ACC239${Date.now()}`.slice(0, 20), code_sh: '8541.40', pays_origine: 'CN', unite_stock: 'unité',
    avertissement_vente: 'Fragile', avertissement_bloquant: true, classe_danger: 'AUCUNE', quantite_reappro_cible: 12,
    suivi_serie: true, politique_facturation_achat: 'sur_reception', louable: true, tarif_location_jour: '15.00',
    est_recurrent: false, seuil_alerte: 3,
  }
  const cree = await creerProduit(r, champsMaitres)
  const avant = await j(await r.get(`${API_DJANGO}/stock/produits/${cree.id}/`, T), 'produit rouvert')
  for (const [k, v] of Object.entries(champsMaitres)) {
    if (k === 'code_barres') continue
    expect(String(avant[k]), `champ maître ${k} conservé à la création`).toBe(String(v))
  }
  // « Enregistrer sans rien toucher » : le corps complet relu est renvoyé tel quel (PUT puis PATCH).
  const lectureSeule = new Set(['id', 'company', 'date_creation', 'date_mise_a_jour'])
  const corps = Object.fromEntries(Object.entries(avant).filter(([k]) => !lectureSeule.has(k)))
  await j(await r.put(`${API_DJANGO}/stock/produits/${cree.id}/`, { ...T, data: corps }), 'PUT sans changement', 200)
  await j(await r.patch(`${API_DJANGO}/stock/produits/${cree.id}/`, { ...T, data: corps }), 'PATCH sans changement', 200)
  const apres = await j(await r.get(`${API_DJANGO}/stock/produits/${cree.id}/`, T), 'produit relu')
  const diff = Object.keys({ ...avant, ...apres }).filter((k) => k !== 'date_mise_a_jour' && JSON.stringify(avant[k]) !== JSON.stringify(apres[k]))
  expect(diff, `champs altérés par un enregistrement sans toucher : ${diff.join(', ')}`).toEqual([])
  // Kit : composants avec perte conservée (ids de composants exclus de la comparaison).
  const kit = await j(await r.post(`${API_DJANGO}/stock/kits/`, {
    ...T, data: { nom: uniq('ACC239 kit'), description: 'essai', composants: [{ produit: cree.id, quantite: '2.00', taux_perte_pct: '5.00' }] },
  }), 'kit', 201)
  const kAvant = await j(await r.get(`${API_DJANGO}/stock/kits/${kit.id}/`, T), 'kit rouvert')
  const kCorps = Object.fromEntries(Object.entries(kAvant).filter(([k]) => !['id', 'date_creation', 'date_mise_a_jour'].includes(k)))
  await j(await r.put(`${API_DJANGO}/stock/kits/${kit.id}/`, { ...T, data: kCorps }), 'PUT kit sans changement', 200)
  const kApres = await j(await r.get(`${API_DJANGO}/stock/kits/${kit.id}/`, T), 'kit relu')
  const sansIds = (k) => ({ ...k, date_mise_a_jour: null, composants: k.composants.map((c) => ({ ...c, id: null })) })
  expect(sansIds(kApres), 'kit identique (hors identifiants de composants)').toEqual(sansIds(kAvant))
  expect(kApres.composants[0].taux_perte_pct).toBe('5.00')
  // Persistance : l'écran stock rechargé liste toujours la fiche.
  await page.goto('/stock')
  await page.reload()
  await expect(page.getByText(avant.nom).first()).toBeVisible({ timeout: 60_000 }).catch(() => undefined)
})

// ── S-C — prix_achat absent de tout JSON servi hors rôle autorisé ─────────────────────────────
etape('S-C', ['ASTK239'], async ({ page, testInfo, suivi }) => {
  await monterComptes()
  const r = page.request
  const MARQUE = '737.37'
  const produit = await creerProduit(r, { prix_achat: MARQUE, prix_vente: '1000.00' })
  const bcf = await creerBcfEnvoye(r, produit.id, 5, MARQUE)
  await recevoir(r, bcf, 5)
  const { devis } = await creerDevis(r, produit.id, '1000.00', { envoyer: true })
  const kit = await j(await r.post(`${API_DJANGO}/stock/kits/`, {
    ...T, data: { nom: uniq('ACC239 kit C'), composants: [{ produit: produit.id, quantite: '1.00' }] },
  }), 'kit', 201)
  // Référence : le Directeur, lui, voit le prix d'achat (la sonde sait lire).
  const admin = await j(await r.get(`${API_DJANGO}/stock/produits/${produit.id}/`, T), 'admin produit')
  expect(admin.prix_achat, 'le Directeur voit le prix d\'achat').toBe(MARQUE)
  const lus = []
  for (const compte of ['acc239_com', 'acc239_tresp']) {
    const c = await api(testInfo, compte)
    const urls = [
      `/stock/produits/${produit.id}/`, `/stock/produits/?search=ACC239&page_size=50`, `/stock/kits/${kit.id}/`,
      '/stock/kits/', `/ventes/devis/${devis.id}/`, `/ventes/devis-lignes/?devis=${devis.id}`,
      '/stock/catalogue-b2b/', `/stock/mouvements/?produit=${produit.id}`, '/stock/fournisseurs/',
    ]
    for (const u of urls) {
      const rep = await c.get(`${API_DJANGO}${u}`, T)
      const corps = await rep.text()
      lus.push(`${compte} ${u} → ${rep.status()}`)
      expect([200, 403, 404], `${compte} ${u} → ${rep.status()}`).toContain(rep.status())
      expect(corps, `${compte} ${u} : prix d'achat ${MARQUE} servi`).not.toContain(MARQUE)
      expect(corps, `${compte} ${u} : clé prix_achat avec une valeur`).not.toMatch(/"prix_achat":\s*"[1-9]/)
    }
    // Achats : que le rôle y accède ou non, le montant d'achat (737,37) n'est jamais servi.
    for (const u of ['/stock/bons-commande-fournisseur/', `/stock/bons-commande-fournisseur/${bcf.id}/`,
      '/stock/factures-fournisseur/', '/stock/paiements-fournisseur/', '/stock/receptions-fournisseur/',
      `/stock/prix-fournisseurs/?produit=${produit.id}`]) {
      const rep = await c.get(`${API_DJANGO}${u}`, T)
      const corps = await rep.text()
      lus.push(`${compte} ${u} → ${rep.status()}`)
      expect(corps, `${compte} ${u} : prix d'achat ${MARQUE} servi`).not.toContain(MARQUE)
      expect(corps, `${compte} ${u} : prix_achat_unitaire servi`).not.toMatch(/"prix_achat_unitaire":\s*"[1-9]/)
    }
  }
  // Page fournisseur à jeton : jamais de montant d'achat.
  const four = await fournisseurDemo(r)
  const jeton = await j(await r.post(`${API_DJANGO}/stock/fournisseurs/${four}/portail-tokens/`, { ...T, data: {} }), 'jeton portail', 201)
  const pub = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const portail = await pub.get(`${API_DJANGO}/public/stock/portail-fournisseur/${jeton.token}/`, T)
  expect(portail.status()).toBe(200)
  const texte = await portail.text()
  lus.push(`portail fournisseur → 200 (${texte.length} octets)`)
  expect(texte).not.toContain(MARQUE)
  expect(texte).not.toMatch(/prix_achat|total_achat|montant_ht|prix_unitaire/)
  // D-ASTK239-PORTAIL-MONTANTS (fondateur, 30/10/2026, réponse a) : la page du lien privé rend au fournisseur les totaux
  // (montant_ttc, solde_du) de SES PROPRES factures — normal pour un fournisseur ; ce qui reste masqué est le prix d'achat
  // UNITAIRE / le coût (vérifié ci-dessus : ni 737,37 ni prix_achat/total_achat/montant_ht/prix_unitaire). Le texte de la
  // tâche ASTK239 (« aucun montant d'achat ») est à lire dans ce sens. La spec ne fait donc PAS échouer sur montant_ttc/solde_du.
  const totauxSesFactures = /montant_ttc/.test(texte)
  lus.push(`portail : totaux de SES factures (montant_ttc/solde_du) servis = ${totauxSesFactures} (admis, D-ASTK239-PORTAIL-MONTANTS a)`)
  // PDF client du devis : ni la valeur ni le mot « prix d'achat ».
  const pdf = await pdfDevis(r, devis.id)
  expect(pdf).not.toContain('737,37')
  expect(pdf.toLowerCase()).not.toMatch(/prixd'achat|prixachat|marge/)
  lus.push('PDF /proposal du devis : sans prix d\'achat')
  suivi.verifie(7)
  await j(await r.post(`${API_DJANGO}/stock/fournisseurs/${four}/portail-tokens/${jeton.id}/revoquer/`, { ...T, data: {} }), 'révocation', 200)
  testInfo.annotations.push({ type: 'surfaces lues', description: lus.join(' | ') })
})

// ── S-D — achat bout en bout : BCF → envoi → réception partielle → solde → facture → acompte + paiement ──
etape('S-D', ['ASTK239'], async ({ page, suivi }) => {
  const r = page.request
  const produit = await creerProduit(r, { prix_achat: '0.00' })
  const bcf = await creerBcfEnvoye(r, produit.id, 10, '100.00')
  expect(bcf.statut).toBe('envoye')
  await j(await r.post(`${API_DJANGO}/stock/acomptes-fournisseur/`, {
    ...T, data: { bon_commande: bcf.id, montant: '300.00', date_versement: '2026-10-30', mode: 'virement' },
  }), 'acompte', 201)
  const r1 = await recevoir(r, bcf, 4)
  expect(await stockDe(r, produit.id), 'réception partielle').toBe(4)
  const partiel = await j(await r.get(`${API_DJANGO}/stock/bons-commande-fournisseur/${bcf.id}/`, T), 'BCF')
  expect([partiel.lignes[0].quantite_recue, partiel.lignes[0].quantite_restante], 'BCF partiellement reçu : 4 reçus, 6 restants').toEqual([4, 6])
  const r2 = await recevoir(r, bcf, 6)
  expect(await stockDe(r, produit.id), 'réception du solde').toBe(10)
  expect((await j(await r.get(`${API_DJANGO}/stock/bons-commande-fournisseur/${bcf.id}/`, T), 'BCF')).statut).toBe('recu')
  // Valorisation : le coût moyen du produit = prix du BCF ; valeur = 10 × 100 = montant HT facturé.
  const valorisation = async () => {
    const v = await j(await r.get(`${API_DJANGO}/stock/produits/valorisation-a-date/?date=2026-10-30`, T), 'valorisation à date')
    return v.lignes.find((x) => x.produit_id === produit.id)
  }
  const val10 = await valorisation()
  expect([val10.quantite, val10.cout_moyen, val10.valeur], 'valorisation après réception du solde').toEqual([10, 100, 1000])
  const f1 = await j(await r.post(`${API_DJANGO}/stock/receptions-fournisseur/${r1.id}/facturer/`, T), 'facture 1', 201)
  const f2 = await j(await r.post(`${API_DJANGO}/stock/receptions-fournisseur/${r2.id}/facturer/`, T), 'facture 2', 201)
  expect(Number(f1.montant_ht) + Number(f2.montant_ht), 'HT facturé = valeur reçue').toBe(1000)
  const g1 = await j(await r.get(`${API_DJANGO}/stock/factures-fournisseur/${f1.id}/`, T), 'facture 1 relue')
  expect(g1.total_acomptes_imputes, 'acompte imputé').toBe('300.00')
  expect(g1.solde_du, 'reste à payer après acompte').toBe('180.00')
  // Un paiement trop grand est refusé clairement, le juste paiement solde la facture.
  const trop = await r.post(`${API_DJANGO}/stock/paiements-fournisseur/`, { ...T, data: { facture: f1.id, montant: '500.00', date_paiement: '2026-10-30', mode: 'virement' } })
  expect(trop.status()).toBe(409)
  for (const [f, montant] of [[f1, '180.00'], [f2, '720.00']]) {
    await j(await r.post(`${API_DJANGO}/stock/paiements-fournisseur/`, { ...T, data: { facture: f.id, montant, date_paiement: '2026-10-30', mode: 'virement' } }), 'paiement', 201)
    const g = await j(await r.get(`${API_DJANGO}/stock/factures-fournisseur/${f.id}/`, T), 'facture relue')
    expect(g.solde_du, `reste à payer ${g.reference}`).toBe('0.00')
    expect(g.statut).toBe('payee')
  }
  // Annuler une réception facturée : refus clair, stock inchangé.
  const refus = await r.post(`${API_DJANGO}/stock/receptions-fournisseur/${r2.id}/annuler/`, T)
  expect(refus.status()).toBe(400)
  expect(await refus.text()).toMatch(/factur/i)
  expect(await stockDe(r, produit.id)).toBe(10)
  // Annuler une réception non facturée ⇒ stock restauré.
  const bcf2 = await creerBcfEnvoye(r, produit.id, 3, '100.00')
  const r3 = await recevoir(r, bcf2, 3)
  expect(await stockDe(r, produit.id)).toBe(13)
  await j(await r.post(`${API_DJANGO}/stock/receptions-fournisseur/${r3.id}/annuler/`, T), 'annulation de réception', 200)
  expect(await stockDe(r, produit.id), 'stock restauré').toBe(10)
  expect((await valorisation()).valeur, 'valorisation restaurée avec le stock').toBe(1000)
  // Écrans : les documents sont listés après rechargement (F5).
  await page.goto('/stock/bons-commande-fournisseur')
  await page.reload()
  await expect(page.getByText(bcf.reference).first()).toBeVisible({ timeout: 60_000 })
  await page.goto('/stock/factures-fournisseur')
  await page.reload()
  await expect(page.getByText(f1.reference).first()).toBeVisible({ timeout: 60_000 })
  suivi.verifie(5)
})

// ── S-E — étanchéité entre sociétés : ids de la société 1 lus par la société 43 ───────────────
const PREFIXES_STOCK = [
  'produits', 'categories', 'fournisseurs', 'mouvements', 'marques', 'bons-commande-fournisseur', 'emplacements',
  'transferts', 'prix-fournisseurs', 'retours-fournisseur', 'receptions-fournisseur', 'factures-fournisseur',
  'paiements-fournisseur', 'inventaire-sessions', 'kits', 'acomptes-fournisseur', 'avoirs-fournisseur',
  'lots-entrepot', 'inventaires-annuels', 'revalorisations-stock', 'conditionnements', 'modeles-bcf',
  'vagues-picking', 'unites-logistiques', 'quais', 'rendez-vous-transporteur', 'expeditions', 'alertes-rappel',
  'portails-tiers', 'retours-client', 'consignations', 'accords-rfa-fournisseur', 'documents-fournisseur',
  'contacts-fournisseur', 'categories-fournisseur', 'budgets-departement', 'engagements-budget',
]
etape('S-E', ['ASTK239'], async ({ page, testInfo }) => {
  await monterComptes()
  const r = page.request
  const b = await api(testInfo, 'acc239_b')
  const moi = await j(await b.get(`${API_DJANGO}/auth/me/`, T), 'société voisine')
  expect(moi.company ?? moi.company_id, 'le compte voisin n\'est pas en société 1').not.toBe(1)
  const sondes = []
  const sansDonnees = []
  const strip = (t) => String(t).replace(/"request_id":\s*"[^"]*"/g, '')
  for (const p of PREFIXES_STOCK) {
    const liste = await r.get(`${API_DJANGO}/stock/${p}/?page_size=1`, T)
    if (liste.status() !== 200) { sansDonnees.push(`${p} (liste ${liste.status()})`); continue }
    const corps = await liste.json()
    const premier = (Array.isArray(corps) ? corps : corps.results || [])[0]
    if (!premier) { sansDonnees.push(`${p} (aucun objet en société 1)`); continue }
    const id = premier.id
    for (const [methode, data] of [['get'], ['patch', {}], ['delete']]) {
      const rep = await b[methode](`${API_DJANGO}/stock/${p}/${id}/`, { ...T, data })
      const texte = await rep.text()
      sondes.push(`${p}/${id} ${methode.toUpperCase()} → ${rep.status()}`)
      // Paire identique : même statut ET même corps que pour un id qui n'existe pas du tout
      // (405 = verbe non porté par la route, identique pour un id absent).
      const absent = await b[methode](`${API_DJANGO}/stock/${p}/987654321/`, { ...T, data })
      expect([404, 405], `${methode} ${p}/${id} depuis la société 43 : ${texte.slice(0, 160)}`).toContain(rep.status())
      expect(rep.status(), `${p} ${methode} : statut d'un id étranger ≠ statut d'un id absent`).toBe(absent.status())
      expect(strip(texte), `${p} : réponse d'un id étranger ≠ réponse d'un id absent`).toBe(strip(await absent.text()))
    }
    // La liste de la société 43 ne contient jamais l'objet de la société 1.
    const l43 = await (await b.get(`${API_DJANGO}/stock/${p}/?page_size=200`, T)).json().catch(() => ({}))
    const ids43 = (Array.isArray(l43) ? l43 : l43.results || []).map((x) => x.id)
    expect(ids43, `${p} : liste de la société 43`).not.toContain(id)
  }
  // Substitution d'ids dans une écriture : refus comme un id absent (400), jamais 403 ni donnée.
  const prod1 = await creerProduit(r)
  const four1 = await fournisseurDemo(r)
  const sub = await b.post(`${API_DJANGO}/stock/bons-commande-fournisseur/`, {
    ...T, data: { fournisseur: four1, date_commande: '2026-10-30', lignes: [{ produit: prod1.id, quantite: 1, prix_achat_unitaire: '1.00' }] },
  })
  sondes.push(`POST BCF avec ids étrangers → ${sub.status()}`)
  expect([400, 404], `BCF aux ids étrangers → ${sub.status()} ${(await sub.text()).slice(0, 200)}`).toContain(sub.status())
  expect(await sub.text()).not.toContain(prod1.nom)
  // Jeton portail révoqué ⇒ 404 (page publique).
  const jeton = await j(await r.post(`${API_DJANGO}/stock/fournisseurs/${four1}/portail-tokens/`, { ...T, data: {} }), 'jeton', 201)
  const pub = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  expect((await pub.get(`${API_DJANGO}/public/stock/portail-fournisseur/${jeton.token}/`, T)).status()).toBe(200)
  await j(await r.post(`${API_DJANGO}/stock/fournisseurs/${four1}/portail-tokens/${jeton.id}/revoquer/`, { ...T, data: {} }), 'révocation', 200)
  expect((await pub.get(`${API_DJANGO}/public/stock/portail-fournisseur/${jeton.token}/`, T)).status(), 'jeton révoqué').toBe(404)
  testInfo.annotations.push({ type: 'sondes', description: `${sondes.length} sondes 404 ; sans objet en société 1 : ${sansDonnees.join(', ') || 'aucun'}` })
  testInfo.annotations.push({ type: 'couverture', description: `préfixes sondés : ${PREFIXES_STOCK.length - sansDonnees.length}/${PREFIXES_STOCK.length}` })
  // Les préfixes sans objet en société 1 ne sont PAS sondés avec un id : lacune dite, pas masquée.
  expect(PREFIXES_STOCK.length - sansDonnees.length, 'au moins les routes à données sondées').toBeGreaterThan(15)
  if (sansDonnees.length) {
    console.log(`[S-E] non sondés par id (aucune donnée en société 1) : ${sansDonnees.join(', ')}`)
  }
})

// ── S-F — correction après coup : refus clair ou révision tracée ──────────────────────────────
etape('S-F', ['ASTK239'], async ({ page }) => {
  const r = page.request
  const produit = await creerProduit(r, { prix_achat: '0.00' })
  const bcf = await creerBcfEnvoye(r, produit.id, 10, '100.00')
  const rec = await recevoir(r, bcf, 10)
  const refus = []
  const exiger = async (quoi, rep, statuts, motif) => {
    const texte = await rep.text()
    refus.push(`${quoi} → ${rep.status()}`)
    expect(statuts, `${quoi} → ${rep.status()} ${texte.slice(0, 200)}`).toContain(rep.status())
    if (motif) expect(texte, quoi).toMatch(motif)
  }
  // Ligne de BCF déjà reçue : modification directe refusée (« réviser »), rien ne bouge.
  await exiger('PATCH ligne de BCF reçu', await r.patch(`${API_DJANGO}/stock/bons-commande-fournisseur/${bcf.id}/`, {
    ...T, data: { lignes: [{ id: bcf.ligne, produit: produit.id, quantite: 3, prix_achat_unitaire: '50.00' }] },
  }), [409], /réviser/)
  const bcfRelu = await j(await r.get(`${API_DJANGO}/stock/bons-commande-fournisseur/${bcf.id}/`, T), 'BCF relu')
  expect(bcfRelu.lignes[0].quantite).toBe(10)
  expect(bcfRelu.lignes[0].prix_achat_unitaire).toBe('100.00')
  // Réception confirmée : non modifiable.
  await exiger('PATCH réception confirmée', await r.patch(`${API_DJANGO}/stock/receptions-fournisseur/${rec.id}/`, { ...T, data: { date_reception: '2026-01-01' } }), [409], /non modifiable/)
  // Facture payée : montants verrouillés, suppression refusée ; réception facturée non annulable.
  const f = await j(await r.post(`${API_DJANGO}/stock/receptions-fournisseur/${rec.id}/facturer/`, T), 'facture', 201)
  await j(await r.post(`${API_DJANGO}/stock/paiements-fournisseur/`, { ...T, data: { facture: f.id, montant: f.montant_ttc, date_paiement: '2026-10-30', mode: 'virement' } }), 'paiement', 201)
  await exiger('PATCH montant de facture payée', await r.patch(`${API_DJANGO}/stock/factures-fournisseur/${f.id}/`, { ...T, data: { montant_ht: '1.00' } }), [409], /verrouill/)
  await exiger('DELETE facture payée', await r.delete(`${API_DJANGO}/stock/factures-fournisseur/${f.id}/`, T), [409], /paiements réels/)
  await exiger('annulation de réception facturée', await r.post(`${API_DJANGO}/stock/receptions-fournisseur/${rec.id}/annuler/`, T), [400], /factur/)
  const g = await j(await r.get(`${API_DJANGO}/stock/factures-fournisseur/${f.id}/`, T), 'facture relue')
  expect(g.montant_ht).toBe('1000.00')
  expect(await stockDe(r, produit.id), 'stock ↔ valorisation : aucun écart silencieux').toBe(10)
  // Session d'inventaire validée : non modifiable.
  const s = await j(await r.post(`${API_DJANGO}/stock/inventaire-sessions/`, { ...T, data: { nom: uniq('ACC239 inv') } }), 'session', 201)
  await j(await r.patch(`${API_DJANGO}/stock/inventaire-sessions/${s.id}/`, { ...T, data: { lignes: [{ produit: produit.id, quantite_comptee: 10 }] } }), 'comptage', 200)
  await j(await r.post(`${API_DJANGO}/stock/inventaire-sessions/${s.id}/valider/`, T), 'validation', 200)
  await exiger('PATCH session d\'inventaire validée', await r.patch(`${API_DJANGO}/stock/inventaire-sessions/${s.id}/`, { ...T, data: { motif: 'x' } }), [409], /non modifiable/)
  // Emplacement non vide : archivage refusé.
  const e = await j(await r.post(`${API_DJANGO}/stock/emplacements/`, { ...T, data: { nom: uniq('ACC239 empl') } }), 'emplacement', 201)
  await j(await r.post(`${API_DJANGO}/stock/transferts/`, { ...T, data: { produit: produit.id, source: 1, destination: e.id, quantite: 2 } }), 'transfert', 201)
  await exiger('archivage d\'un emplacement non vide', await r.patch(`${API_DJANGO}/stock/emplacements/${e.id}/`, { ...T, data: { archived: true } }), [409], /détient du stock/)
  test.info().annotations.push({ type: 'refus', description: refus.join(' | ') })
  // Non rejoués ici (aucune route / donnée sur cette pile) : unité logistique scellée, exercice non clos figé.
  await page.goto('/stock')
})

// ── P6 — WMS de bout en bout et portail fournisseur ──────────────────────────────────────────
etape('P6.1', ['ASTK239'], async ({ page, testInfo }) => {
  const r = page.request
  const produit = await creerProduit(r, { prix_achat: '0.00' })
  const bcf = await creerBcfEnvoye(r, produit.id, 4, '100.00')
  const four = bcf.fournisseur
  const jeton = await j(await r.post(`${API_DJANGO}/stock/fournisseurs/${four}/portail-tokens/`, { ...T, data: {} }), 'jeton', 201)
  const pub = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const doc = await j(await pub.get(`${API_DJANGO}/public/stock/portail-fournisseur/${jeton.token}/`, T), 'portail')
  const vu = doc.bons_commande.find((x) => x.id === bcf.id)
  expect(vu, 'le BCF envoyé figure sur le portail').toBeTruthy()
  const conf = await pub.post(`${API_DJANGO}/public/stock/portail-fournisseur/${jeton.token}/bcf/${bcf.id}/confirmer/`, { ...T, data: { date_confirmee_fournisseur: '2026-11-15' } })
  expect([200, 201], `confirmation : ${(await conf.text()).slice(0, 200)}`).toContain(conf.status())
  const relu = await j(await r.get(`${API_DJANGO}/stock/bons-commande-fournisseur/${bcf.id}/`, T), 'BCF relu')
  expect(relu.date_confirmee_fournisseur, 'confirmation du fournisseur tracée côté ERP').toBeTruthy()
  const cren = await j(await pub.get(`${API_DJANGO}/public/stock/portail-fournisseur/${jeton.token}/creneaux-disponibles/`, T), 'créneaux')
  expect(Array.isArray(cren.creneaux)).toBe(true)
  await j(await r.post(`${API_DJANGO}/stock/fournisseurs/${four}/portail-tokens/${jeton.id}/revoquer/`, { ...T, data: {} }), 'révocation', 200)
  expect((await pub.get(`${API_DJANGO}/public/stock/portail-fournisseur/${jeton.token}/`, T)).status()).toBe(404)
  await page.goto('/stock/bons-commande-fournisseur')
  await page.reload()
  await expect(page.getByText(bcf.reference).first()).toBeVisible({ timeout: 60_000 })
})

// ── P6.2 — parcours WMS de bout en bout (D-ASTK239 : société 1 n'a AUCUNE donnée WMS ; le montage est fait ICI) ──
// Fixture posée par `manage.py shell` (modèles + services propres au module stock, société 1, préfixe ACC239W),
// retirée en fin d'étape. Les GESTES sont les vraies routes HTTP (et les vraies pages pour le kiosque et la lecture).
const WMS_FIXTURE = (sfx) => `${PRELUDE}
import datetime
from decimal import Decimal
from apps.installations.models import BinLocation, BinAffectation
from apps.stock.models import Produit, EmplacementStock, Categorie, LotEntrepot
from apps.stock.models_wms import Quai
from apps.crm.models import Client
from apps.stock.services_consignation import creer_depot_consignation
from authentication.models import Company
co = Company.objects.get(pk=1)
admin = U.objects.get(username='demo_admin')
sfx = '${sfx}'
emp = EmplacementStock.objects.create(company=co, nom='ACC239W Dépôt ' + sfx)
cat = Categorie.objects.create(company=co, nom='ACC239W FEFO ' + sfx, strategie_picking_defaut=Categorie.StrategiePicking.FEFO)
def prod(nom, stock, categorie=None):
    return Produit.objects.create(company=co, nom=nom + ' ' + sfx, sku='ACC239W-' + nom[:3].upper() + '-' + sfx, categorie=categorie,
        prix_achat=Decimal('10'), prix_vente=Decimal('20'), quantite_stock=stock)
pr = prod('Reappro', 60)
pl = prod('Lots', 15, cat)
pc = prod('Consigne', 10)
src = BinLocation.objects.create(company=co, emplacement=emp, code='ACCS-' + sfx, zone='S', allee='01', casier='01', ordre=120)
cib = BinLocation.objects.create(company=co, emplacement=emp, code='ACCP-' + sfx, zone='P', allee='01', casier='01', ordre=100)
BinAffectation.objects.create(company=co, bin=src, produit=pr, quantite=40)
BinAffectation.objects.create(company=co, bin=cib, produit=pr, quantite=2)
lot_r = LotEntrepot.objects.create(company=co, produit=pl, numero_lot='ACCR-' + sfx, date_peremption=datetime.date(2027, 1, 1), quantite_recue=10, quantite_restante=10)
lot_s = LotEntrepot.objects.create(company=co, produit=pl, numero_lot='ACCL-' + sfx, date_peremption=datetime.date(2028, 1, 1), quantite_recue=5, quantite_restante=5)
cl = Client.objects.create(company=co, nom='Consigne ACC239W ' + sfx, prenom='Client', email='acc239w@example.invalid')
depot = creer_depot_consignation(company=co, user=admin, client_id=cl.id, produit_id=pc.id, quantite=4, date_depot=datetime.date(2026, 10, 1), adresse_site='ACC239W site')
quai = Quai.objects.create(company=co, nom='ACC239W Quai R1 ' + sfx, type_quai=Quai.TypeQuai.RECEPTION, emplacement=emp)
sortie(dict(slug=co.slug, emp=emp.id, cat=cat.id, pr=pr.id, pl=pl.id, pc=pc.id, src=src.id, cib=cib.id, lot_r=lot_r.id, lot_s=lot_s.id,
    lot_r_num=lot_r.numero_lot, cl=cl.id, depot=depot.id, quai=quai.id, quai_nom=quai.nom, cib_code=cib.code, pr_nom=pr.nom, cl_nom=cl.nom))`

const WMS_NETTOYAGE = (ids) => `${PRELUDE}
ids = json.loads('${JSON.stringify(ids)}')
reste = {}
def sup(nom, qs):
    try:
        n = qs.count(); qs.delete(); reste[nom] = 'supprime:%s' % n
    except Exception as e:
        reste[nom] = 'RESTE (%s)' % type(e).__name__
from apps.stock import models as m, models_wms as w, models_reappro_casier as rc, models_consignation as mc
from apps.installations.models import BinLocation, BinAffectation
from apps.ventes.models import Facture
from apps.crm.models import Client
sup('rdv', w.RendezVousTransporteur.objects.filter(quai_id=ids['quai']))
sup('expeditions', w.ExpeditionTransporteur.objects.filter(unite_logistique__lignes__produit_id=ids['pr']))
sup('unites', w.UniteLogistique.objects.filter(lignes__produit_id=ids['pr']))
sup('vagues', w.VaguePicking.objects.filter(lignes__produit_id=ids['pr']))
sup('blocages', w.BlocageQualite.objects.filter(produit_id=ids['pl']))
sup('alertes', w.AlerteRappel.objects.filter(produit_id=ids['pl']))
sup('taches', rc.TacheReapproInterne.objects.filter(produit_id=ids['pr']))
sup('seuils', rc.SeuilReapproCasier.objects.filter(produit_id=ids['pr']))
sup('lots', m.LotEntrepot.objects.filter(produit_id=ids['pl']))
sup('factures', Facture.objects.filter(pk__in=ids.get('factures', []), statut='brouillon'))
sup('depot', mc.DepotConsignation.objects.filter(pk=ids['depot']))
sup('quai', w.Quai.objects.filter(pk=ids['quai']))
sup('affectations', BinAffectation.objects.filter(bin_id__in=[ids['src'], ids['cib']]))
sup('casiers', BinLocation.objects.filter(pk__in=[ids['src'], ids['cib']]))
try:
    m.Produit.objects.filter(pk__in=[ids['pr'], ids['pl'], ids['pc']]).delete(); reste['produits'] = 'supprime'
except Exception as e:
    m.Produit.objects.filter(pk__in=[ids['pr'], ids['pl'], ids['pc']]).update(is_archived=True)
    reste['produits'] = 'ARCHIVES (mouvements protegent la suppression : %s)' % type(e).__name__
sup('client', Client.objects.filter(pk=ids['cl']))
sup('categorie', m.Categorie.objects.filter(pk=ids['cat']))
sup('emplacement', m.EmplacementStock.objects.filter(pk=ids['emp']))
sortie(reste)`

etape('P6.2', ['ASTK239'], async ({ page, testInfo, suivi }) => {
  testInfo.setTimeout(900_000)
  const r = page.request
  const sfx = String(Date.now()).slice(-8)
  const jour = new Date()
  const iso = (d) => d.toISOString().slice(0, 10)
  const f = await py(WMS_FIXTURE(sfx))
  const ids = { ...f, factures: [] }
  const lus = []
  let jeton = null
  try {
    // ── 1. Casier sous seuil → tâche de réappro → exécutée ─────────────────────────────────────────────
    const seuil = await j(await r.post(`${API_DJANGO}/stock/seuils-reappro-casier/`, { ...T, data: { bin: f.cib, produit: f.pr, seuil: 10, quantite_cible: 20, actif: true } }), 'seuil', 201)
    expect(seuil.bin_code).toBe(f.cib_code)
    const dus = await j(await r.get(`${API_DJANGO}/stock/casiers-a-reapprovisionner/`, T), 'casiers dus')
    expect(dus.casiers.map((c) => c.bin), 'le casier sous seuil (2 < 10) est dû').toContain(f.cib)
    const gen = await j(await r.post(`${API_DJANGO}/stock/casiers-a-reapprovisionner/`, { ...T, data: {} }), 'génération des tâches', 200)
    expect(gen.taches_creees).toBeGreaterThanOrEqual(1)
    const taches = await j(await r.get(`${API_DJANGO}/stock/taches-reappro-interne/?statut=a_faire`, T), 'tâches à faire')
    const tache = listeJson(taches).find((x) => x.bin_cible === f.cib)
    expect(tache, 'tâche de réappro du casier').toBeTruthy()
    const faite = await j(await r.post(`${API_DJANGO}/stock/taches-reappro-interne/${tache.id}/executer/`, { ...T, data: {} }), 'exécution', 200)
    expect(faite.statut).toBe('faite')
    const apres = await j(await r.get(`${API_DJANGO}/stock/casiers-a-reapprovisionner/`, T), 'casiers dus après')
    expect(apres.casiers.map((c) => c.bin), "le casier n'est plus dû").not.toContain(f.cib)
    const qte = await py(`${PRELUDE}
from apps.installations.models import BinAffectation
sortie({str(a.bin_id): a.quantite for a in BinAffectation.objects.filter(bin_id__in=[${f.src}, ${f.cib}])})`)
    expect(qte[String(f.cib)], 'casier cible rempli à la cible').toBe(20)
    expect(qte[String(f.src)], 'casier source diminué du transfert').toBe(22)
    lus.push(`réappro : tâche ${tache.id} faite, casiers ${JSON.stringify(qte)}`)

    // ── 2. Vague → prélèvement → unité scellée → expédition étiquetée → stock décrémenté ───────────────
    const avantStock = await stockDe(r, f.pr)
    const vague = await j(await r.post(`${API_DJANGO}/stock/vagues-picking/`, { ...T, data: { besoins: [{ produit_id: f.pr, quantite: 5 }] } }), 'vague', 201)
    const lancee = await j(await r.post(`${API_DJANGO}/stock/vagues-picking/${vague.id}/lancer/`, { ...T, data: {} }), 'lancement', 200)
    expect(lancee.statut).toBe('lancee')
    for (const l of lancee.lignes) {
      await j(await r.post(`${API_DJANGO}/stock/vagues-picking/${vague.id}/lignes/${l.id}/prelever/`, { ...T, data: { quantite: l.quantite_demandee } }), 'prélèvement', 200)
    }
    const vagueRelue = await j(await r.get(`${API_DJANGO}/stock/vagues-picking/${vague.id}/`, T), 'vague relue')
    expect(vagueRelue.statut, 'vague terminée quand tout est prélevé').toBe('terminee')
    const unite = await j(await r.post(`${API_DJANGO}/stock/unites-logistiques/`, { ...T, data: { type_unite: 'colis' } }), 'unité', 201)
    await j(await r.post(`${API_DJANGO}/stock/unites-logistiques/${unite.id}/lignes/`, { ...T, data: { produit: f.pr, quantite: 5 } }), "ligne d'unité", 201)
    const scellee = await j(await r.post(`${API_DJANGO}/stock/unites-logistiques/${unite.id}/sceller/`, { ...T, data: {} }), 'scellage', 200)
    expect([scellee.statut, scellee.est_figee]).toEqual(['scelle', true])
    const exp = await j(await r.post(`${API_DJANGO}/stock/expeditions/`, { ...T, data: { unite_logistique: unite.id, destination: 'Rabat' } }), 'expédition', 201)
    const eti = await j(await r.post(`${API_DJANGO}/stock/expeditions/${exp.id}/generer-etiquette/`, { ...T, data: {} }), 'étiquette', 200)
    expect(eti.statut).toBe('etiquette')
    expect(eti.numero_suivi, 'numéro de suivi interne').toMatch(/^INT-/)
    expect(eti.a_une_etiquette, 'étiquette PDF posée').toBe(true)
    expect(await stockDe(r, f.pr), "stock décrémenté de 5 à l'expédition").toBe(avantStock - 5)
    await j(await r.post(`${API_DJANGO}/stock/expeditions/${exp.id}/generer-etiquette/`, { ...T, data: {} }), 'étiquette rejouée', 200)
    expect(await stockDe(r, f.pr), 'rejeu idempotent : pas de second décrément').toBe(avantStock - 5)
    lus.push(`vague ${vague.reference} terminée ; unité ${unite.sscc} scellée ; expédition ${eti.numero_suivi} étiquetée ; stock ${avantStock} → ${avantStock - 5}`)

    // ── 3. Rappel → lot bloqué → absent du picking ─────────────────────────────────────────────────────
    const plan = async () => (await j(await r.get(`${API_DJANGO}/stock/produits/${f.pl}/plan-picking/?quantite=3&strategie=fefo`, T), 'plan de picking')).lignes
    expect((await plan()).map((x) => x.numero_lot), "avant rappel : le lot qui périme d'abord est proposé").toContain(f.lot_r_num)
    const alerte = await j(await r.post(`${API_DJANGO}/stock/alertes-rappel/`, { ...T, data: { produit: f.pl, lot: f.lot_r, motif: 'Défaut cellule ACC239W' } }), 'rappel', 201)
    expect(alerte.blocages.map((b) => [b.lot, b.statut, b.quantite])).toEqual([[f.lot_r, 'en_quarantaine', 10]])
    expect((await plan()).map((x) => x.numero_lot), 'après rappel : le lot rappelé est ABSENT du picking').not.toContain(f.lot_r_num)
    const sortie409 = await r.post(`${API_DJANGO}/stock/lots-entrepot/${f.lot_r}/sortir/`, { ...T, data: { quantite: 1 } })
    const corps409 = await sortie409.text()
    expect(sortie409.status(), corps409).toBe(409)
    expect(corps409).toContain(f.lot_r_num)
    expect(await stockDe(r, f.pl), 'aucun stock ne bouge sur un lot rappelé').toBe(15)
    const sainSort = await j(await r.post(`${API_DJANGO}/stock/lots-entrepot/${f.lot_s}/sortir/`, { ...T, data: { quantite: 2 } }), 'sortie du lot sain', 200)
    expect(sainSort.quantite_restante, 'lot sain décrémenté').toBe(3)
    lus.push(`rappel ${alerte.id} : lot ${f.lot_r_num} en quarantaine, absent du plan, sortie refusée (409) ; lot sain 5 → 3`)

    // ── 4. Consignation → déclaration de consommation → facture BROUILLON ──────────────────────────────
    const decl = await j(await r.post(`${API_DJANGO}/stock/consignations/${f.depot}/declarer-consommation/`, { ...T, data: { quantite: 2, date_declaration: iso(jour) } }), 'déclaration', 201)
    expect(decl.statut).toBe('facturee')
    expect(decl.facture_id).toBeTruthy()
    ids.factures.push(decl.facture_id)
    const fac = await j(await r.get(`${API_DJANGO}/ventes/factures/${decl.facture_id}/`, T), 'facture de consignation')
    expect(fac.statut, 'facture de consignation = brouillon').toBe('brouillon')
    expect(fac.reference).toBe(decl.facture_reference)
    const releve = await j(await r.get(`${API_DJANGO}/stock/consignations/${f.depot}/releve/`, T), 'relevé')
    expect([releve.quantite_facturee, releve.quantite_restante]).toEqual([2, 2])
    expect(JSON.stringify(releve), "relevé sans prix d'achat").not.toMatch(/prix_achat/)
    lus.push(`consignation : déclaration ${decl.id} → facture brouillon ${decl.facture_reference}`)

    // ── 5. Lien fournisseur → créneau proposé réservé → planning des quais ─────────────────────────────
    const four = await fournisseurDemo(r)
    jeton = await j(await r.post(`${API_DJANGO}/stock/fournisseurs/${four}/portail-tokens/`, { ...T, data: {} }), 'jeton', 201)
    const pub = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
    const demain = new Date(jour.getTime() + 86_400_000)
    const urlCreneaux = `${API_DJANGO}/public/stock/portail-fournisseur/${jeton.token}/creneaux-disponibles/?quai=${f.quai}&date_debut=${iso(demain)}&periode=7`
    const dispo = await j(await pub.get(urlCreneaux, T), 'créneaux')
    expect(dispo.creneaux.length, 'créneaux proposés sur le quai de réception').toBeGreaterThan(0)
    const choisi = dispo.creneaux[0]
    const rdv = await j(await pub.post(`${API_DJANGO}/public/stock/portail-fournisseur/${jeton.token}/reserver-creneau/`, { ...T, data: { quai: f.quai, debut: choisi.debut, chauffeur_nom: 'ACC239W Chauffeur' } }), 'réservation', 201)
    expect(rdv.code_checkin).toMatch(/^[A-Z0-9]{8}$/)
    const encore = await j(await pub.get(urlCreneaux, T), 'créneaux relus')
    expect(encore.creneaux.map((c) => c.debut), "un créneau réservé n'est plus proposé").not.toContain(choisi.debut)
    const planning = await j(await r.get(`${API_DJANGO}/stock/quais/planning/?date=${choisi.date}&vue=jour&quai=${f.quai}`, T), 'planning des quais')
    const rdvs = planning.quais.flatMap((q) => q.rendez_vous)
    expect(rdvs.map((x) => x.id), 'le rendez-vous réservé figure au planning du quai').toContain(rdv.id)
    expect(rdvs.find((x) => x.id === rdv.id).statut).toBe('planifie')
    lus.push(`créneau ${choisi.debut} réservé (rdv ${rdv.id}) et présent au planning du quai`)

    // ── 6. Kiosque (VRAIE page publique /quai/checkin) → arrivée enregistrée ───────────────────────────
    await page.goto(`/quai/checkin?societe=${f.slug}`)
    await page.getByLabel("Code d'arrivée").fill(rdv.code_checkin)
    await page.getByRole('button', { name: 'Je suis arrivé' }).click()
    await expect(page.getByText(/Arrivée enregistrée/)).toBeVisible({ timeout: 60_000 })
    await expect(async () => {
      const rdvRelu = await j(await r.get(`${API_DJANGO}/stock/rendez-vous-transporteur/${rdv.id}/`, T), 'rendez-vous relu')
      expect(rdvRelu.statut, 'arrivée tracée côté ERP').toBe('arrive')
    }).toPass({ timeout: 60_000 })
    lus.push(`kiosque : code ${rdv.code_checkin} → rendez-vous ${rdv.id} « arrivé »`)

    // ── 7. Lecture à l'écran (rechargement F5) des objets créés, sans 4xx/5xx ni console.error ─────────
    const ecrans = [
      ['/stock/entrepot/picking', vague.reference], ['/stock/entrepot/expeditions', eti.numero_suivi],
      ['/stock/entrepot/quais', f.quai_nom], ['/stock/entrepot/qualite', f.lot_r_num],
      ['/stock/negoce/consignations', 'ACC239W site'], ['/stock/entrepot/casiers', f.cib_code],
    ]
    const vus = []
    for (const [route, texte] of ecrans) {
      await page.goto(route)
      await page.reload()
      await expect(page.getByText(texte).filter({ visible: true }).first(), `${route} montre « ${texte} »`).toBeVisible({ timeout: 90_000 })
      vus.push(route)
    }
    lus.push(`écrans relus après F5 : ${vus.join(', ')}`)
    suivi.verifie(7)
  } finally {
    try {
      if (jeton) await r.post(`${API_DJANGO}/stock/fournisseurs/${await fournisseurDemo(r)}/portail-tokens/${jeton.id}/revoquer/`, { ...T, data: {} })
    } catch { /* au mieux */ }
    let reste = null
    try { reste = await py(WMS_NETTOYAGE(ids)) } catch (e) { reste = `nettoyage en échec : ${String(e.message).slice(0, 300)}` }
    console.log(`[P6.2] nettoyage fixture WMS : ${JSON.stringify(reste)}`)
    testInfo.annotations.push({ type: 'nettoyage fixture WMS', description: JSON.stringify(reste) })
    console.log(`[P6.2] surfaces jouées : ${lus.join(' | ')}`)
    testInfo.annotations.push({ type: 'surfaces WMS jouées', description: lus.join(' | ') })
  }
})
