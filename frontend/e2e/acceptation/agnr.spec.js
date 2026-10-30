// AGNR42 — spec d'acceptation en direct du groupe AGNR (générateur de devis `/ventes/devis/nouveau`), jouée par
// l'ORCHESTRATEUR sur la pile locale (CLAUDE.md 3-bis, METHODE §C.4, `_format.md`).
//
// Étapes = identifiants de la tâche AGNR42 (docs/plans/PLAN_AUDIT_GENERATEUR.md) :
// P1.1 lead plus ancien / lead A→B · P1.3 profil de site après factures tapées · P2.1 Rail sans champ TVA, prix
// tapé gardé · P2.2 décimales tapées jamais refusées ni arrondies dans le champ · P3.1 « Facture réelle » 150 ⇒
// 1 282 kWh/an · P3.3 agricole sans « Heures » · P3.5 Σ graphe = cartes, curseur diurne retiré · P4.1 échéancier
// refusé / création coupée ⇒ un seul devis · P4.2 C&I rouvrir→enregistrer, V1→×4→restaurer V1 · P4.3 étude
// refusée ⇒ formulaire conservé, Réduction 12,345 normalisée · P5.1 les quatre marchés créer→enregistrer→rouvrir→
// enregistrer sans toucher · P5.2 désignations retouchées ⇒ rail « Sans batterie » inchangé.
//
// Principes : données PROPRES à chaque étape (leads/devis créés par l'API réelle, ARCHIVÉS ou supprimés à la fin) ;
// jamais la prod ; clause PERSISTANCE = F5/rouvrir puis relire ; clause CLIENT = total TTC écran = serveur = /proposal.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import {
  API_DJANGO, creerDevisCommercialDepuisLead, creerDevisIndustrielDepuisLead,
  lireJson, nombrePagesPdf, ouvrirGenerateurDepuisLeadAgricole, retirerLignesPrixARenseigner,
  telephoneMobileUnique, textePdf, uniq,
} from '../helpers.js'

const etapeBase = groupe('AGNR', ['AGNR42'])
test.describe.configure({ timeout: 1_200_000 })
// Machine chargée : le délai par défaut des actions (15 s) est trop court pour la composition serveur et l'enregistrement.
const etape = (id, taches, corps, options) => etapeBase(id, taches, async (contexte) => {
  contexte.page.setDefaultTimeout(180_000)
  await corps(contexte)
}, options)
const API = API_DJANGO
const T = { timeout: 180_000 }
const plat = (s) => String(s).replace(/\s+/g, '')

// ── données ─────────────────────────────────────────────────────────────────
async function creerLead(api, tag, extra = {}) {
  return lireJson(await api.post(`${API}/crm/leads/`, {
    ...T,
    data: {
      nom: uniq(`AGNR42 ${tag}`), telephone: telephoneMobileUnique(), ville: 'Casablanca',
      type_installation: 'residentiel', ...extra,
    },
  }), `lead ${tag}`)
}
const lireDevis = async (api, id) => lireJson(await api.get(`${API}/ventes/devis/${id}/`, T), `devis ${id}`)
async function nettoyer(api, { devis = [], leads = [] }) {
  for (const id of devis) await api.post(`${API}/ventes/devis/${id}/archiver/`, T).catch(() => undefined)
  for (const id of leads) await api.delete(`${API}/crm/leads/${id}/`, T).catch(() => undefined)
}
const ouvrirGenerateur = async (page, url) => {
  await page.goto(url)
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' })).toBeVisible({ timeout: 45_000 })
}
/** Montant (nombre) d'un texte « 42 600,00 MAD ». */
const nombre = (t) => Number(String(t).replace(/[^\d,.-]/g, '').replace(',', '.'))

/** Clique « Créer le devis » et rend le JSON d'`atomic/`. La pile locale (serveur de dev partagé, chargé) dépasse
 *  parfois le délai de 20 s de l'écran (`axios` REQUEST_TIMEOUT_MS) : l'écran affiche alors « La connexion a été
 *  interrompue — vérifiez la liste des devis avant de recréer ». Le geste d'un utilisateur est de recliquer
 *  « Créer » : la même Idempotency-Key (AGNR40) rejoue le PREMIER devis côté serveur au lieu d'en créer un second.
 *  Chaque reprise est notée en annotation (jamais cachée) ; l'appelant vérifie l'unicité du devis du lead. */
const reprises = []
async function creerAvecReprise(page, { essais = 3 } = {}) {
  const bouton = page.locator('#gen-form').getByRole('button', { name: /Créer le devis/ })
  for (let essai = 1; essai <= essais; essai += 1) {
    const reponse = page.waitForResponse((r) => r.request().method() === 'POST'
      && /\/ventes\/devis\/atomic\/$/.test(new URL(r.url()).pathname) && r.status() < 300, { timeout: 240_000 })
    reponse.catch(() => undefined)
    await expect(bouton).toBeEnabled({ timeout: 240_000 })
    await bouton.click()
    const refus = page.getByTestId('erreur-enregistrement')
    const issue = await Promise.race([
      reponse.then((r) => ({ r })),
      refus.waitFor({ state: 'visible', timeout: 240_000 }).then(async () => ({ refus: (await refus.textContent()) || '' }), () => new Promise(() => {})),
    ])
    if (issue.r) return issue.r.json()
    if (!/connexion|expir|interrompu/i.test(issue.refus) || essai === essais) throw new Error(`« Créer le devis » refusé à l'écran : ${issue.refus}`)
    reprises.push(`essai ${essai} : ${issue.refus.trim().slice(0, 120)}`)
    test.info().annotations.push({ type: 'reprise après délai dépassé', description: issue.refus.trim().slice(0, 200) })
    await page.waitForLoadState('networkidle') // laisse le premier envoi aboutir côté serveur avant le rejeu idempotent
  }
  throw new Error('inatteignable')
}
/** Devis du lead (API) : l'unicité après reprise est la preuve que le rejeu n'a rien dupliqué. */
async function devisDuLead(api, leadId) {
  const corps = await lireJson(await api.get(`${API}/ventes/devis/?lead=${leadId}&page_size=50`, T), `devis du lead ${leadId}`)
  return (Array.isArray(corps) ? corps : corps.results || []).filter((d) => d.is_active !== false)
}


/** Résidentiel depuis un lead : ouvrir, attendre le lead appliqué + l'aperçu horaire, Auto-remplir (composition
 *  serveur — jusqu'à 3 min sur une machine chargée), Créer. Renvoie la réponse d'`atomic/`. */
async function creerResidentielDepuisLead(page, lead) {
  const apercu = page.waitForResponse((r) => r.request().method() === 'POST' && /\/etude-horaire\/preview\/$/.test(new URL(r.url()).pathname) && r.status() === 200,
    { timeout: 180_000 })
  await ouvrirGenerateur(page, `/ventes/devis/nouveau?lead=${lead.id}`)
  await expect(page.locator('#gen-lead')).toContainText(lead.nom, { timeout: 90_000 })
  await apercu
  await page.getByTestId('btn-auto-remplir').click()
  await attendreComposition(page)
  await retirerLignesPrixARenseigner(page)
  return creerAvecReprise(page)
}
/** Une ligne « Panneau… » à quantité > 0 = la composition serveur est posée. */
async function attendreComposition(page) {
  await page.waitForFunction(() => [...document.querySelectorAll('table.lines-table tbody tr')].some((tr) => {
    const champs = [...tr.querySelectorAll('input')].map((i) => i.value)
    return /panneau/i.test(champs[0] || '') && Number(champs[1]) > 0
  }), null, { timeout: 180_000 })
}

/** Total TTC affiché par l'écran (barre d'actions, même valeur que le rail). */
async function totalEcran(page) {
  const t = page.getByTestId('gen-barre-total').first()
  await expect(t).toBeVisible({ timeout: 30_000 })
  return nombre(await t.textContent())
}
async function textePdfDevis(api, id) {
  const rep = await api.get(`${API}/ventes/devis/${id}/proposal/`, T)
  expect(rep.status(), `/proposal du devis ${id}`).toBe(200)
  const octets = await rep.body()
  return { texte: await textePdf(octets), pages: await nombrePagesPdf(octets) }
}
const formatPdf = (n) => Number(n).toFixed(2).replace('.', ',')
/** Total TTC serveur d'un devis (`total_affiche` ?? `total_ttc`). */
const ttcServeur = (d) => Number(d.total_affiche ?? d.total_ttc)

/** Rouvre `?edit=<id>`, enregistre sans rien toucher ; renvoie les requêtes d'écriture observées. */
async function reenregistrerSansToucher(page, id) {
  const ecritures = []
  const surRequete = (r) => {
    if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(r.method()) && /\/ventes\/devis\//.test(r.url())) {
      ecritures.push({ methode: r.method(), chemin: new URL(r.url()).pathname, corps: r.postData() })
    }
  }
  page.on('request', surRequete)
  await ouvrirGenerateur(page, `/ventes/devis/nouveau?edit=${id}`)
  await expect(page.locator('table.lines-table tbody tr').first()).toBeVisible({ timeout: 45_000 })
  const total = await totalEcran(page)
  // Même reprise que la création : au-delà de 20 s (pile locale chargée) l'écran coupe la requête et affiche
  // « L'enregistrement a échoué » ; l'utilisateur reclique (replace-lines remplace les lignes à l'identique).
  const bouton = page.getByRole('button', { name: /Enregistrer les modifications/ })
  for (let essai = 1; ; essai += 1) {
    const ecrit = page.waitForResponse((r) => r.request().method() === 'POST' && /\/replace-lines\/$/.test(new URL(r.url()).pathname) && r.status() < 300,
      { timeout: 240_000 })
    ecrit.catch(() => undefined)
    await expect(bouton).toBeEnabled({ timeout: 240_000 })
    await bouton.click()
    const refus = page.getByTestId('erreur-enregistrement')
    const issue = await Promise.race([
      ecrit.then(() => ({ ok: true })),
      refus.waitFor({ state: 'visible', timeout: 240_000 }).then(async () => ({ refus: (await refus.textContent()) || '' }), () => new Promise(() => {})),
    ])
    if (issue.ok) break
    if (essai >= 3) throw new Error(`« Enregistrer les modifications » refusé : ${issue.refus}`)
    reprises.push(`ré-enregistrement essai ${essai} : ${issue.refus.trim().slice(0, 120)}`)
    test.info().annotations.push({ type: 'reprise après délai dépassé', description: issue.refus.trim().slice(0, 200) })
    await page.waitForLoadState('networkidle')
  }
  await expect(page.getByTestId('erreur-enregistrement')).toHaveCount(0, { timeout: 30_000 })
  page.off('request', surRequete)
  return { ecritures, total }
}
/** Forme comparable d'un devis serveur (lignes + montants + étude) — « objet serveur identique ». */
const empreinte = (d) => JSON.stringify({
  lignes: (d.lignes || []).map((l) => [l.produit, l.designation, Number(l.quantite), Number(l.prix_unitaire), Number(l.taux_tva), Number(l.remise || 0), !!l.optionnelle]),
  remise: Number(d.remise_globale || 0), tva: Number(d.taux_tva), ttc: ttcServeur(d),
  opt: d.comparaison_options ? [d.comparaison_options.sans?.ttc, d.comparaison_options.avec?.ttc] : null,
  etude: d.etude_params || null,
})

// ── P5.1 — les quatre marchés ───────────────────────────────────────────────
async function parcoursMarche(page, nom, creer, { conserver }) {
  const api = page.request
  const id = await creer()
  conserver.devis.push(id)
  const avant = await lireDevis(api, id)
  const { texte: texte0 } = await textePdfDevis(api, id)
  const { ecritures, total } = await reenregistrerSansToucher(page, id)
  const apres = await lireDevis(api, id)
  expect(ecritures.some((e) => /replace-lines/.test(e.chemin)), `${nom} : replace-lines appelé`).toBeTruthy()
  // Objet serveur identique après « ouvrir → enregistrer sans toucher ».
  expect(empreinte(apres), `${nom} : objet serveur identique`).toBe(empreinte(avant))
  // Total TTC : écran = serveur = /proposal (devis à deux options : l'écran porte l'option retenue).
  const ttc = ttcServeur(apres)
  const candidats = [ttc, Number(apres.total_ttc), Number(apres.comparaison_options?.sans?.ttc), Number(apres.comparaison_options?.avec?.ttc)]
    .filter((x) => Number.isFinite(x))
  const ttcEcran = candidats.find((c) => Math.abs(c - total) < 0.51)
  expect(ttcEcran, `${nom} : total TTC écran ${total} ∈ serveur ${JSON.stringify(candidats)}`).toBeDefined()
  const { texte, pages } = await textePdfDevis(api, id)
  expect(plat(texte), `${nom} : /proposal imprime le total TTC ${formatPdf(ttcEcran)}`).toContain(plat(formatPdf(ttcEcran)))
  expect(plat(texte0), `${nom} : /proposal avant`).toContain(plat(formatPdf(ttcEcran)))
  // PERSISTANCE : F5 sur l'écran rouvert → même total.
  await page.reload()
  await expect(page.locator('table.lines-table tbody tr').first()).toBeVisible({ timeout: 45_000 })
  expect(Math.abs((await totalEcran(page)) - total), `${nom} : total après F5`).toBeLessThan(0.51)
  return { id, pages, ttc: ttcEcran, apres }
}

etape('P5.1', ['AGNR42'], async ({ page, suivi, testInfo }) => {
  const api = page.request
  const conserver = { devis: [], leads: [] }
  try {
    const detail = []
    // Résidentiel — lead « été différent » (hiver 800 / été 1 600, D-AGNR-1).
    const lr = await creerLead(api, 'P5.1 résidentiel', { facture_hiver: '800', facture_ete: '1600', ete_differente: true })
    conserver.leads.push(lr.id)
    const res = await parcoursMarche(page, 'résidentiel', async () => {
      const cree = await creerResidentielDepuisLead(page, lr)
      return cree.id ?? cree.devis?.id
    }, { conserver })
    detail.push(`résidentiel #${res.id} ${res.pages}p TTC ${res.ttc}`)
    expect((await devisDuLead(api, lr.id)).map((d) => d.id), 'résidentiel : un seul devis pour le lead').toEqual([res.id])
    // Devis du lead « été différent » étiqueté estimation (D-AGNR-1) : aucune série « réelle » enregistrée.
    expect(res.apres.etude_params?.factures_mensuelles_reelles, 'rampe « réelle » absente').toBeFalsy()
    // Commercial.
    const lc = await creerLead(api, 'P5.1 commercial', { type_installation: 'commercial' })
    conserver.leads.push(lc.id)
    const com = await parcoursMarche(page, 'commercial', () => creerDevisCommercialDepuisLead(page, lc.id), { conserver })
    detail.push(`commercial #${com.id} ${com.pages}p TTC ${com.ttc}`)
    // Industriel.
    const li = await creerLead(api, 'P5.1 industriel', { type_installation: 'industriel' })
    conserver.leads.push(li.id)
    const ind = await parcoursMarche(page, 'industriel', () => creerDevisIndustrielDepuisLead(page, li.id), { conserver })
    detail.push(`industriel #${ind.id} ${ind.pages}p TTC ${ind.ttc}`)
    // Agricole.
    const ag = await parcoursMarche(page, 'agricole', async () => {
      const lead = await ouvrirGenerateurDepuisLeadAgricole(page, api, 'AGNR42 ferme')
      conserver.leads.push(lead.id)
      await page.getByRole('radio', { name: 'Volume déclaré' }).click()
      await page.locator('#gen-besoin-volume').fill('60')
      await page.locator('#gen-hmt').fill('45')
      await page.getByRole('radio', { name: /Tri 380V/ }).click()
      await expect(page.getByTestId('resultat-pompage')).toBeVisible({ timeout: 45_000 })
      await page.getByTestId('btn-auto-remplir').click()
      await expect(page.getByTestId('pompage-auto-rempli')).toBeVisible({ timeout: 180_000 })
      await retirerLignesPrixARenseigner(page)
      const cree = await creerAvecReprise(page)
      return cree.id ?? cree.devis?.id
    }, { conserver })
    detail.push(`agricole #${ag.id} ${ag.pages}p TTC ${ag.ttc}`)
    expect((await devisDuLead(api, conserver.leads[conserver.leads.length - 1])).map((d) => d.id), 'agricole : un seul devis pour le lead').toEqual([ag.id])
    if (reprises.length) detail.push(`reprises après délai dépassé : ${reprises.join(' | ')}`)
    testInfo.annotations.push({ type: 'marchés', description: detail.join(' ; ') })
    suivi.verifie(6)
  } finally {
    await nettoyer(api, conserver)
  }
})

// ═══════════════════════════════════════════════════════════════════════════════
// AGNR42 — ÉTAPES À AJOUTER À frontend/e2e/acceptation/agnr.spec.js (après P5.1)
// BROUILLON NON JOUÉ : écrit par lecture du code, jamais exécuté (consigne).
//
// Dépendances DÉJÀ dans agnr.spec.js : etape, API, T, plat, nombre, creerLead, lireDevis, nettoyer,
//   ouvrirGenerateur, totalEcran, reenregistrerSansToucher, creerResidentielDepuisLead, attendreComposition,
//   textePdfDevis, formatPdf, ttcServeur ; imports helpers : lireJson, uniq, telephoneMobileUnique,
//   cliquerCreerDevis, retirerLignesPrixARenseigner, ouvrirGenerateurDepuisLeadAgricole.
// À AJOUTER PAR L'APPELANT : `creerAvecReprise(page)` (clique « Créer le devis », rejoue le clic sur
//   « La connexion a expiré », renvoie le JSON d'`atomic/`). Aucun autre import nouveau.
// Noms des helpers ci-dessous choisis pour ne pas entrer en collision avec ceux du spec.
// Étapes : P1.1 P1.3 P2.1 P2.2 P2.3 P3.1 P3.3 P4.1 P4.3 P5.2 (P1.2 P2.4 P3.4 P3.5 P4.2 non rédigées).
// ═══════════════════════════════════════════════════════════════════════════════

// Étapes RÉDIGÉES le 30/10 mais pas encore validées sur la pile (sélecteurs/données à corriger, voir le rapport
// du rejeu) : jouées seulement avec AGNR_BROUILLON=1, pour qu'un enregistrement n'impute jamais un défaut de
// SPEC au produit. P2.3 (validée en direct le 30/10) est jouée par défaut.
const etapeBrouillon = (...a) => (process.env.AGNR_BROUILLON ? etape(...a) : undefined)

// ── helpers communs (ceux-ci à coller AVANT les étapes) ─────────────────────────
const listeAgnr = (c) => (Array.isArray(c) ? c : (c?.results || []))
const echapper = (s) => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
/** AAAA-MM-JJ « aujourd'hui » à Casablanca (même règle que etudeMarcheBloc.aujourdhuiCasablanca, AGNR38). */
const aujourdhuiCasablanca = () => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date())
const nouveauxConserves = () => ({ devis: [], leads: [], clients: [], listes: [], produits: [], profils: [] })

/** Nettoyage étendu (ordre : devis archivés → profils → clients → listes → clones). Tout est best-effort. */
async function nettoyerPlus(api, c) {
  await nettoyer(api, { devis: c.devis, leads: c.leads })
  for (const id of c.profils) await api.delete(`${API}/crm/site-profiles/${id}/`, T).catch(() => undefined)
  for (const id of c.clients) await api.delete(`${API}/crm/clients/${id}/`, T).catch(() => undefined)
  for (const id of c.listes) await api.delete(`${API}/ventes/listes-prix/${id}/`, T).catch(() => undefined)
  // DELETE d'un produit référencé = ARCHIVAGE (stock/views/produit.py:526-545), jamais une perte.
  for (const id of c.produits) await api.delete(`${API}/stock/produits/${id}/`, T).catch(() => undefined)
}

/** Catalogue actif et chiffré (GET /stock/produits/ — champs nom, prix_vente, tva, is_archived). */
async function catalogueAgnr(api) {
  const rep = await lireJson(await api.get(`${API}/stock/produits/?page_size=200`, T), 'catalogue')
  return listeAgnr(rep).filter((p) => !p.is_archived && Number(p.prix_vente) > 0)
}
/** n accessoires simples (20 %, ni solaire ni pompage) aux noms distincts. */
function produitsSimples(catalogue, n) {
  const vus = new Set()
  const bons = catalogue.filter((p) => (p.tva == null || Number(p.tva) === 20)
    && !/panneau|onduleur|batterie|pompe|variateur|structure|coffret|hybride|stockage/i.test(p.nom)
    && !vus.has(p.nom) && vus.add(p.nom))
  if (bons.length < n) throw new Error(`NON JOUABLE : le catalogue de la démo n'a pas ${n} accessoire(s) chiffré(s) à 20 % (seed_catalogue à rejouer)`)
  return bons.slice(0, n)
}
/** Devis brouillon créé par l'API réelle (POST devis + replace-lines), comme helpers.monterVenteAcceptee. */
async function devisParApi(api, lead, lignes, extra = {}) {
  const devis = await lireJson(await api.post(`${API}/ventes/devis/`, {
    ...T, data: { lead: lead.id, taux_tva: '20.00', mode_installation: 'residentiel', ...extra },
  }), 'création du devis')
  await lireJson(await api.post(`${API}/ventes/devis/${devis.id}/replace-lines/`, {
    ...T,
    data: {
      lignes: lignes.map((l, i) => ({
        produit: l.produit.id, designation: l.designation ?? l.produit.nom, quantite: String(l.quantite ?? '1.00'),
        prix_unitaire: Number(l.prixHt ?? l.produit.prix_vente).toFixed(2), remise: '0.00',
        taux_tva: String(l.taux_tva ?? '20.00'), type_ligne: 'produit', ordre: i,
      })),
    },
  }), 'lignes du devis')
  return devis
}
const nbDevisDuLead = async (api, leadId) => {
  const rep = await lireJson(await api.get(`${API}/ventes/devis/?lead=${leadId}&page_size=50`, T), `devis du lead ${leadId}`)
  return Number(rep.count ?? listeAgnr(rep).length)
}
/** Rouvre `?edit=<id>` et attend les lignes (DevisGenerator.jsx : chargeur `?edit=`). */
async function ouvrirEdition(page, id) {
  await ouvrirGenerateur(page, `/ventes/devis/nouveau?edit=${id}`)
  await expect(page.locator('table.lines-table tbody tr').first()).toBeVisible({ timeout: 90_000 })
}
/** Clique « Enregistrer les modifications » (scope `#gen-form`, comme e2e/devis-agricole-economie.spec.js:107). */
async function enregistrerEdition(page) {
  const ecrit = page.waitForResponse((r) => r.request().method() === 'POST' && /\/replace-lines\/$/.test(new URL(r.url()).pathname) && r.status() < 300,
    { timeout: 180_000 })
  await page.locator('#gen-form').getByRole('button', { name: /Enregistrer les modifications/ }).click()
  await ecrit
  // la fusion PATCH …/etude-params/ part APRÈS replace-lines (nocturne 37856987210) : ne pas naviguer avant.
  await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => undefined)
}
const lignesDom = (page) => page.locator('table.lines-table tbody tr[data-line-key]')
const celluleDe = (ligne, libelle) => ligne.locator(`td[data-label="${libelle}"]`)
// DevisLineRow.jsx:269 (« Prix unit. TTC »), :289 (« TVA % »), :251 (Qté, data-role="line-qty"), :160 (Désignation)
const champPrix = (ligne) => celluleDe(ligne, 'Prix unit. TTC').locator('input').first()
const champTva = (ligne) => celluleDe(ligne, 'TVA %').locator('input[type="number"]').first()
const champQte = (ligne) => ligne.locator('[data-role="line-qty"]')
const champDesignation = (ligne) => celluleDe(ligne, 'Désignation').locator('input').first()

/** Supprime toutes les lignes proposées par défaut (LigneTable → « Supprimer la ligne », DevisLineRow.jsx:354). */
async function viderLignes(page) {
  const lignes = lignesDom(page)
  await expect(lignes.first()).toBeVisible({ timeout: 90_000 })
  for (let i = 0; i < 80 && (await lignes.count()) > 0; i += 1) {
    await lignes.first().getByRole('button', { name: 'Supprimer la ligne' }).click()
  }
  await expect(lignes).toHaveCount(0)
}
/** Active « Composition libre » (Switch `#gen-composition-libre`, DevisGenerator.jsx:1899) — évite la garde panneau+onduleur. */
async function activerCompositionLibre(page) {
  const sw = page.locator('#gen-composition-libre')
  if ((await sw.getAttribute('aria-checked')) !== 'true') await sw.click()
  await expect(sw).toHaveAttribute('aria-checked', 'true')
}
/** « Ajouter ligne » (LigneTable.jsx:75) puis choix du produit dans le ProduitPicker
 *  (bouton de `td[data-label="Produit (stock)"]`, champ « Chercher un produit… », option role=option — ProduitPicker.jsx:97/162). */
async function ajouterLigneProduit(page, produit) {
  const lignes = lignesDom(page)
  const avant = await lignes.count()
  await page.getByRole('button', { name: /Ajouter ligne/ }).first().click()
  await expect(lignes).toHaveCount(avant + 1)
  const ligne = lignes.last()
  await celluleDe(ligne, 'Produit (stock)').locator('button').first().click()
  await page.getByPlaceholder(/Chercher un produit/).fill(produit.nom)
  await page.getByRole('option', { name: new RegExp(echapper(produit.nom)) }).first().click()
  await expect.poll(async () => Number(await champPrix(ligne).inputValue()), { timeout: 60_000, message: `prix de « ${produit.nom} » posé` }).toBeGreaterThan(0)
  return ligne
}
/** Choix d'un lead dans `#gen-lead` (Select Radix : CarteLeadClient.jsx:50 ; les options sont `nom [prénom] [(société)] [— N MAD/mois]`). */
async function choisirLeadParNom(page, lead) {
  await page.locator('#gen-lead').click()
  await page.getByRole('option', { name: new RegExp(echapper(lead.nom)) }).first().click()
}
const moisAffiches = (page) => page.locator('.gen-monthly-grid input').evaluateAll((els) => els.map((e) => e.value))

/** Saisie d'un nombre « à la française » dans un champ `type=number` : on essaie VRAIMENT la virgule (frappe) ; si le
 *  navigateur la refuse (locale), repli sur le point — dit dans l'annotation. Le contrôle porte sur la valeur DU CHAMP. */
async function taperDecimal(champ, texteFr, valeurDom, notes) {
  await champ.click()
  await champ.fill('')
  await champ.pressSequentially(texteFr)
  if ((await champ.inputValue()) !== valeurDom) {
    notes.push(`« ${texteFr} » : virgule refusée par le champ nombre du navigateur → saisie « ${valeurDom} »`)
    await champ.fill(valeurDom)
  }
  await champ.blur()
}
/** Clause P2.2 : jamais refusé (validité native) ni arrondi (valeur du champ inchangée après blur). */
async function exigerNonArrondi(champ, valeurDom, quoi) {
  await expect(champ, `${quoi} : valeur du champ après blur`).toHaveValue(valeurDom)
  const v = await champ.evaluate((el) => ({ valide: el.validity.valid, pas: el.validity.stepMismatch, bas: el.validity.rangeUnderflow, haut: el.validity.rangeOverflow }))
  expect(v, `${quoi} : validité native (noValidate + step="any")`).toEqual({ valide: true, pas: false, bas: false, haut: false })
}


// ── P1.1 — ?lead=<plus ancien> appliqué ; lead A → B sans facture héritée ──────
// Gestes : GET /crm/leads/?ordering=date_creation&page_size=1 (views.py:185 ordering_fields date_creation ; pagination 50 : core/pagination.py:62)
//  → /ventes/devis/nouveau?lead=<id> (DevisGenerator.jsx:1335-1350 : getLead(id) si absent de la liste, « Lead introuvable » :1322)
//  → #gen-lead (CarteLeadClient.jsx:50) / #gen-hiver (CarteFacturesElectriques.jsx:47) / .gen-monthly-grid (:68) / [data-testid=mois-non-saisis] (:85)
//  → lead A (hiver 2000) puis lead B (sans facture) dans le sélecteur ; devis de B créé en Composition libre (1 accessoire) ;
//    persistance = lire le devis + rouvrir ?edit (mois = valeurs d'exemple).
etapeBrouillon('P1.1', ['AGNR42'], async ({ page, testInfo }) => {
  const api = page.request
  const conserver = nouveauxConserves()
  try {
    // 1) lead le plus ancien (au-delà de la page 1 d'une liste de plus de 50 leads)
    const premiere = await lireJson(await api.get(`${API}/crm/leads/?ordering=date_creation&page_size=1`, T), 'lead le plus ancien')
    const ancien = listeAgnr(premiere)[0]
    expect(ancien, 'au moins un lead (GET /crm/leads/?ordering=date_creation&page_size=1)').toBeTruthy()
    const totalLeads = Number(premiere.count ?? 0)
    const libelleAncien = ancien.nom || ancien.prenom || ancien.societe
    await ouvrirGenerateur(page, `/ventes/devis/nouveau?lead=${ancien.id}`)
    await expect(page.locator('#gen-lead')).toContainText(libelleAncien, { timeout: 90_000 })
    await expect(page.getByText(/Lead introuvable/)).toHaveCount(0)
    if (Number(ancien.facture_hiver) > 0) {
      await expect.poll(async () => Number(await page.locator('#gen-hiver').inputValue()), { timeout: 60_000, message: 'factures du plus ancien lead appliquées' })
        .toBe(Number(ancien.facture_hiver))
    }

    // 2) lead A (hiver 2000) puis lead B (aucune facture)
    const leadA = await creerLead(api, 'P1.1 A', { facture_hiver: '2000' })
    conserver.leads.push(leadA.id)
    const leadB = await creerLead(api, 'P1.1 B')
    conserver.leads.push(leadB.id)
    await ouvrirGenerateur(page, '/ventes/devis/nouveau')
    await expect(lignesDom(page).first()).toBeVisible({ timeout: 90_000 })
    const defauts = await moisAffiches(page) // valeurs d'EXEMPLE d'un nouveau devis (AGNR13)
    await choisirLeadParNom(page, leadA)
    await expect.poll(async () => Number(await page.locator('#gen-hiver').inputValue()), { timeout: 60_000, message: 'A : hiver 2000 appliqué' }).toBe(2000)
    expect(await moisAffiches(page), 'A : le détail mensuel suit hiver/été').not.toEqual(defauts)
    await choisirLeadParNom(page, leadB)
    await expect(page.locator('#gen-hiver'), 'B : « Facture Hiver » vide (pas celle de A)').toHaveValue('', { timeout: 60_000 })
    await expect(page.locator('#gen-ete')).toHaveValue('')
    expect(await moisAffiches(page), 'B : détail mensuel revenu aux valeurs d\'exemple').toEqual(defauts)
    await expect(page.getByTestId('mois-non-saisis')).toHaveCount(0)

    // 3) le devis de B n'enregistre aucune facture de A — puis rouvrir
    await viderLignes(page)
    await activerCompositionLibre(page)
    const [produit] = produitsSimples(await catalogueAgnr(api), 1)
    await ajouterLigneProduit(page, produit)
    let cree
    cree = await creerAvecReprise(page)
    const idB = cree.id ?? cree.devis?.id
    expect(idB, 'devis de B créé').toBeTruthy()
    conserver.devis.push(idB)
    const devisB = await lireDevis(api, idB)
    const etude = devisB.etude_params || {}
    expect(etude.factures_mensuelles_reelles, 'B : aucune série « réelle » héritée de A').toBeFalsy()
    expect(Number(etude.factures_hiver_ete?.hiver_mad ?? 0), 'B : aucune facture hiver de A (2000) enregistrée').not.toBe(2000)
    await ouvrirEdition(page, idB)
    expect(await moisAffiches(page), 'B rouvert : valeurs d\'exemple (aucune facture héritée)').toEqual(defauts)
    await expect(page.locator('#gen-hiver')).toHaveValue('')

    testInfo.annotations.push({ type: 'leads', description: `plus ancien #${ancien.id}, ${totalLeads} leads au total (liste paginée à 50)` })
    if (totalLeads <= 50) {
      throw new Error(`NON JOUABLE (partie « plus ancien ») : ${totalLeads} leads seulement — le plus ancien tient dans la page 1 ; le reste de l'étape est passé`)
    }
  } finally {
    await nettoyerPlus(api, conserver)
  }
})

// ── P1.3 — profil de site appliqué APRÈS factures tapées ⇒ saisie gardée ───────
// Gestes : client + SiteProfile (POST /crm/clients/, POST /crm/site-profiles/ facture_hiver 900 — crm/views.py:1987, serializers.py:1655)
//  → /ventes/devis/nouveau?client=<id> ; la réponse GET /ventes/devis/prefill-site/?client= (devis.py:782) est RETENUE par page.route,
//    le vendeur tape 1500 dans #gen-hiver, puis on libère → #gen-hiver reste 1500 et [data-testid=avis-factures]
//    « Profil de site non appliqué aux factures déjà saisies. » (useLeadClientEcran.js applySiteProfile ; CarteFacturesElectriques.jsx:66).
//  Témoin : sans frappe, le même profil s'applique (900).
etapeBrouillon('P1.3', ['AGNR42'], async ({ page }) => {
  const api = page.request
  const conserver = nouveauxConserves()
  try {
    const client = await lireJson(await api.post(`${API}/crm/clients/`, { ...T, data: { nom: uniq('AGNR42 P1.3 client') } }), 'client')
    conserver.clients.push(client.id)
    const profil = await lireJson(await api.post(`${API}/crm/site-profiles/`, {
      ...T, data: { client: client.id, facture_hiver: '900', type_installation: 'residentiel' },
    }), 'profil de site')
    conserver.profils.push(profil.id)

    // témoin : aucune saisie ⇒ le profil s'applique
    await ouvrirGenerateur(page, `/ventes/devis/nouveau?client=${client.id}`)
    await expect.poll(async () => Number(await page.locator('#gen-hiver').inputValue()), { timeout: 90_000, message: 'témoin : profil de site appliqué (900)' }).toBe(900)

    // cas testé : frappe AVANT l'arrivée du profil
    let liberer
    const barriere = new Promise((r) => { liberer = r })
    await page.route('**/ventes/devis/prefill-site/**', async (route) => { await barriere; await route.continue() })
    const reponse = page.waitForResponse((r) => /\/ventes\/devis\/prefill-site\//.test(r.url()) && r.status() === 200, { timeout: 180_000 })
    await ouvrirGenerateur(page, `/ventes/devis/nouveau?client=${client.id}`)
    await page.locator('#gen-hiver').fill('1500')
    liberer()
    await reponse
    await expect(page.getByTestId('avis-factures')).toContainText(/Profil de site non appliqué aux factures déjà saisies/, { timeout: 60_000 })
    await expect(page.locator('#gen-hiver')).toHaveValue('1500')
    await page.unroute('**/ventes/devis/prefill-site/**')
  } finally {
    await nettoyerPlus(api, conserver)
  }
})

// ── P2.1 — liste de prix 1 350 HT ⇒ 1 620 TTC ; Rail sans champ TVA ; clone ⇒ prix tapé gardé ───
// Routes : POST /ventes/listes-prix/ + POST …/{id}/lignes/ {produit, prix_unitaire} (views/liste_prix.py:78-136),
//   PATCH /crm/clients/{id}/ {liste_prix} (crm/models_clients.py:900), GET /ventes/prix-applicable/ (liste_prix.py:158 : prix HT, unite 'HT').
// Gestes : ?client=<id> → Composition libre → une ligne produit → champ « Prix unit. TTC » = 1620, badge « Tarif : <liste> »
//   (DevisLineRow.jsx:232) ; Rail : [data-testid=rail-tva-par-ligne] (RailArgent.jsx:86) et aucun input TVA ; créer (atomic) ;
//   API prix_unitaire 1350.00 ; rouvrir + enregistrer sans toucher (reenregistrerSansToucher) ⇒ inchangé ; /proposal ;
//   puis clone : désignation renommée + « Créer un nouveau produit… » (DevisGenerator.jsx:2281-2297) avec P.U. 9999 tapé ⇒ 9999 gardé.
etapeBrouillon('P2.1', ['AGNR42'], async ({ page, suivi }) => {
  const api = page.request
  const conserver = nouveauxConserves()
  try {
    const [produit] = produitsSimples(await catalogueAgnr(api), 1)
    const client = await lireJson(await api.post(`${API}/crm/clients/`, { ...T, data: { nom: uniq('AGNR42 P2.1 client') } }), 'client')
    conserver.clients.push(client.id)
    const liste = await lireJson(await api.post(`${API}/ventes/listes-prix/`, { ...T, data: { nom: uniq('AGNR42 Revendeur'), devise: 'MAD' } }), 'liste de prix')
    conserver.listes.push(liste.id)
    await lireJson(await api.post(`${API}/ventes/listes-prix/${liste.id}/lignes/`, { ...T, data: { produit: produit.id, prix_unitaire: '1350.00' } }), 'ligne de liste')
    await lireJson(await api.patch(`${API}/crm/clients/${client.id}/`, { ...T, data: { liste_prix: liste.id } }), 'client rattaché à la liste')
    const pa = await lireJson(await api.get(`${API}/ventes/prix-applicable/?produit=${produit.id}&client=${client.id}&quantite=1`, T), 'prix applicable')
    expect(pa, 'contrat prix_applicable.json (prix HT de la liste)').toMatchObject({ unite: 'HT', source: 'liste' })
    expect(Number(pa.prix)).toBe(1350)

    await ouvrirGenerateur(page, `/ventes/devis/nouveau?client=${client.id}`)
    await viderLignes(page)
    await activerCompositionLibre(page)
    const ligne = await ajouterLigneProduit(page, produit)
    await expect(celluleDe(ligne, 'Produit (stock)')).toContainText(`Tarif : ${liste.nom}`, { timeout: 60_000 })
    const tva = Number(await champTva(ligne).inputValue())
    expect(tva, 'produit choisi à 20 % (sinon l\'attendu 1 620 ne vaut pas)').toBe(20)
    await expect.poll(async () => Number(await champPrix(ligne).inputValue()), { timeout: 60_000, message: 'P.U. TTC = 1350 × 1,20' }).toBe(1620)
    expect(plat(await celluleDe(ligne, 'Prix unit. TTC').textContent())).toContain('HT:1350,00')

    // Rail : « TVA : par ligne (voir la table) », aucun champ de TVA
    const railTva = page.getByTestId('rail-tva-par-ligne').first()
    await expect(railTva).toContainText('TVA : par ligne (voir la table)')
    await expect(page.locator('.gen-discount-row').first().locator('input'), 'rangée Réduction/TVA du Rail : un seul champ (la réduction)').toHaveCount(1)

    // création + persistance
    const cree = await creerAvecReprise(page)
    const id = cree.id ?? cree.devis?.id
    expect(id, 'devis créé').toBeTruthy()
    conserver.devis.push(id)
    const d0 = await lireDevis(api, id)
    expect(Number(d0.lignes[0].prix_unitaire), 'prix enregistré = HT de la liste').toBe(1350)
    await ouvrirEdition(page, id)
    await expect.poll(async () => Number(await champPrix(lignesDom(page).first()).inputValue()), { timeout: 60_000, message: 'réouvert : 1620' }).toBe(1620)
    await reenregistrerSansToucher(page, id)
    const d1 = await lireDevis(api, id)
    expect(Number(d1.lignes[0].prix_unitaire), 'ré-enregistré sans toucher : prix HT inchangé').toBe(1350)
    const { texte } = await textePdfDevis(api, id)
    expect(plat(texte), '/proposal imprime le HT').toContain(plat('1350,00'))
    expect(plat(texte), '/proposal imprime le TTC').toContain(plat('1620,00'))
    suivi.verifie(6)

    // clone du produit : le prix tapé (9999) et la TVA de la ligne survivent
    await ouvrirEdition(page, id)
    const l0 = lignesDom(page).first()
    if (!(await champDesignation(l0).isEditable())) throw new Error('NON JOUABLE : désignation non éditable pour demo_admin (canRenameLine faux) — clone impossible')
    await champPrix(l0).fill('9999')
    const nomClone = uniq('AGNR42 Clone')
    await champDesignation(l0).fill(nomClone)
    await champDesignation(l0).blur()
    const dialogue = page.getByRole('dialog')
    await expect(dialogue).toContainText('Désignation modifiée')
    await dialogue.getByRole('button', { name: /Créer un nouveau produit/ }).click()
    await expect(dialogue).toHaveCount(0, { timeout: 60_000 })
    await expect(champPrix(l0), 'prix tapé gardé après le clone').toHaveValue('9999')
    await expect(champTva(l0)).toHaveValue('20')
    await enregistrerEdition(page)
    const d2 = await lireDevis(api, id)
    expect(d2.lignes[0].produit, 'la ligne pointe le clone').not.toBe(produit.id)
    conserver.produits.push(d2.lignes[0].produit)
    expect(Number(d2.lignes[0].prix_unitaire)).toBeCloseTo(9999 / 1.2, 1)
    await ouvrirEdition(page, id)
    await expect.poll(async () => Number(await champPrix(lignesDom(page).first()).inputValue()), { timeout: 60_000, message: 'clone rouvert : 9999' }).toBeCloseTo(9999, 0)
  } finally {
    await nettoyerPlus(api, conserver)
  }
})

// ── P2.2 — décimales tapées (« 1234,567 », « 0,5 », prix à 3 décimales) : jamais refusées ni arrondies DANS LE CHAMP ──
// Gestes : (a) champs de factures du générateur neuf (#gen-hiver/#gen-ete, CarteFacturesElectriques.jsx:47/54) ;
//   (b) devis API 1 ligne → ?edit : Qté (DevisLineRow.jsx:251) « 0,5 », P.U. TTC (:270) « 1234,567 », Réduction `.gen-discount-input`
//   (RailArgent.jsx:71) « 0,5 » ; valeur du champ inchangée après blur + validité native (formulaire noValidate, step="any") ;
//   enregistrer → relire l'API : quantité 0.50, remise 0.50 ; prix HT arrondi à 2 décimales = NOTE OPTIONNELLE (LGEN2 O1), jamais un échec.
etapeBrouillon('P2.2', ['AGNR42'], async ({ page, testInfo }) => {
  const api = page.request
  const conserver = nouveauxConserves()
  const notes = []
  try {
    // (a) sans écriture
    await ouvrirGenerateur(page, '/ventes/devis/nouveau')
    await taperDecimal(page.locator('#gen-hiver'), '1234,567', '1234.567', notes)
    await exigerNonArrondi(page.locator('#gen-hiver'), '1234.567', 'Facture Hiver « 1234,567 »')
    await taperDecimal(page.locator('#gen-ete'), '0,5', '0.5', notes)
    await exigerNonArrondi(page.locator('#gen-ete'), '0.5', 'Facture Été « 0,5 »')

    // (b) sur un devis réel rouvert
    const [produit] = produitsSimples(await catalogueAgnr(api), 1)
    const lead = await creerLead(api, 'P2.2')
    conserver.leads.push(lead.id)
    const devis = await devisParApi(api, lead, [{ produit }])
    conserver.devis.push(devis.id)
    await ouvrirEdition(page, devis.id)
    const ligne = lignesDom(page).first()
    await taperDecimal(champQte(ligne), '0,5', '0.5', notes)
    await exigerNonArrondi(champQte(ligne), '0.5', 'Qté « 0,5 »')
    await taperDecimal(champPrix(ligne), '1234,567', '1234.567', notes)
    await exigerNonArrondi(champPrix(ligne), '1234.567', 'P.U. TTC « 1234,567 »')
    const remise = page.locator('.gen-discount-input').first()
    await taperDecimal(remise, '0,5', '0.5', notes)
    await exigerNonArrondi(remise, '0.5', 'Réduction « 0,5 »')
    await enregistrerEdition(page)
    const d = await lireDevis(api, devis.id)
    expect(Number(d.lignes[0].quantite), 'quantité 0,5 stockée telle quelle').toBe(0.5)
    expect(Number(d.remise_globale), 'réduction 0,5 stockée telle quelle').toBe(0.5)
    const htAttendu = Number((1234.567 / 1.2).toFixed(2))
    notes.push(`prix de ligne stocké HT ${d.lignes[0].prix_unitaire} (TTC tapé 1234.567 ⇒ HT ${htAttendu} à 2 décimales) — OPTIONNEL LGEN2 O1 : ${Number(d.lignes[0].prix_unitaire) === htAttendu ? 'normalisé à 2 décimales, non signalé à l\'écran' : 'valeur différente, à lire'}`)
    // persistance
    await ouvrirEdition(page, devis.id)
    await expect(champQte(lignesDom(page).first())).toHaveValue(/^0\.5(0)?$/)
    await expect(page.locator('.gen-discount-input').first()).toHaveValue(/^0\.5(0)?$/)
    testInfo.annotations.push({ type: 'décimales', description: notes.join(' ; ') })
  } finally {
    await nettoyerPlus(api, conserver)
  }
})

// ── P2.3 — une section + une note ⇒ enregistrer → rouvrir ⇒ à leur place ──────
// Gestes : devis API [A, B] → ?edit → « + Section » (LigneTable.jsx:67) puis « Monter la ligne » ×2 (DevisLineRow.jsx:110) ;
//   « + Note » (:72) puis « Monter la ligne » ×1 ⇒ attendu [Section, A, Note, B] ; saisie du texte dans l'Input de la ligne
//   (DevisLineRow.jsx:137, rangée `data-line-type`) ; enregistrer ; API (ordre) puis DOM rouvert.
etape('P2.3', ['AGNR42'], async ({ page }) => {
  const api = page.request
  const conserver = nouveauxConserves()
  try {
    const [a, b] = produitsSimples(await catalogueAgnr(api), 2)
    const lead = await creerLead(api, 'P2.3')
    conserver.leads.push(lead.id)
    const devis = await devisParApi(api, lead, [{ produit: a }, { produit: b }])
    conserver.devis.push(devis.id)
    const texteSection = uniq('Section AGNR42')
    const texteNote = uniq('Note AGNR42')
    await ouvrirEdition(page, devis.id)
    const lignes = lignesDom(page)
    await page.getByRole('button', { name: '+ Section' }).click()
    await expect(lignes).toHaveCount(3)
    await lignes.last().locator('input').first().fill(texteSection)
    for (let i = 0; i < 2; i += 1) await lignes.nth(2 - i).getByRole('button', { name: 'Monter la ligne' }).click()
    await page.getByRole('button', { name: '+ Note' }).click()
    await expect(lignes).toHaveCount(4)
    await lignes.last().locator('input').first().fill(texteNote)
    await lignes.nth(3).getByRole('button', { name: 'Monter la ligne' }).click()
    const sequenceEcran = () => lignes.evaluateAll((trs) => trs.map((tr) => ({ type: tr.dataset.lineType || 'produit', texte: tr.querySelector('input')?.value || '' })))
    const attendu = [['section', texteSection], ['produit', a.nom], ['note', texteNote], ['produit', b.nom]]
    const lue = (await sequenceEcran()).map((x) => [x.type === 'section' || x.type === 'note' ? x.type : 'produit', x.texte])
    expect(lue, 'ordre à l\'écran avant enregistrement').toEqual(attendu)
    await enregistrerEdition(page)
    const d = await lireDevis(api, devis.id)
    const serveur = [...d.lignes].sort((x, y) => Number(x.ordre) - Number(y.ordre))
      .map((l) => [(l.type_ligne ?? l.typeLigne ?? 'produit') === 'produit' ? 'produit' : (l.type_ligne ?? l.typeLigne), l.designation])
    expect(serveur, 'ordre enregistré (API, tri par `ordre`)').toEqual(attendu)
    await ouvrirEdition(page, devis.id)
    const relu = (await sequenceEcran()).map((x) => [x.type === 'section' || x.type === 'note' ? x.type : 'produit', x.texte])
    expect(relu, 'ordre relu à la réouverture (F5)').toEqual(attendu)
  } finally {
    await nettoyerPlus(api, conserver)
  }
})

// ── P3.1 — « Facture réelle » 150 MAD/mois ⇒ 1 282 kWh/an affichés ET enregistrés ─
// Gestes : devis résidentiel créé par l'écran (creerResidentielDepuisLead, lead hiver 800) → ?edit → #gen-realbill (CarteFacturesElectriques.jsx:131)
//   en mode MAD (label « Facture réelle (MAD/mois) ») = 150 → « Consommation annuelle dérivée » (.gen-kwp, :148-150) = « 1 282 kWh/an » ;
//   enregistrer → etude_params.conso_annuelle = 1282 (API) ; ré-enregistrer sans toucher ⇒ idem ; réouverture : valeur dérivée relue
//   (reouverture = round(1282/12)×12 = 1284 en mode kWh : toléré à ±12, noté si ≠ 1282). Barème ONEE par défaut (distributeur).
etapeBrouillon('P3.1', ['AGNR42'], async ({ page, suivi, testInfo }) => {
  const api = page.request
  const conserver = nouveauxConserves()
  try {
    const lead = await creerLead(api, 'P3.1', { facture_hiver: '800' })
    conserver.leads.push(lead.id)
    const cree = await creerResidentielDepuisLead(page, lead)
    const id = cree.id ?? cree.devis?.id
    conserver.devis.push(id)
    await ouvrirEdition(page, id)
    const etiquette = page.locator('label[for="gen-realbill"]')
    if (!/Facture réelle \(MAD\/mois\)/.test(await etiquette.textContent())) {
      await page.locator('#gen-realbill').locator('xpath=..').getByRole('combobox').click()
      await page.getByRole('option', { name: 'MAD', exact: true }).click()
    }
    await expect(etiquette).toContainText('Facture réelle (MAD/mois)')
    const conso = page.locator('label', { hasText: 'Consommation annuelle dérivée' }).locator('xpath=..').locator('.gen-kwp')
    await page.locator('#gen-realbill').fill('150')
    await expect(conso, '150 MAD/mois ONEE ⇒ 1 282 kWh/an').toHaveText(/^\s*1[\s\u202f\u00a0]?282\s*kWh\/an\s*$/, { timeout: 60_000 })
    const etude = page.waitForResponse((r) => r.request().method() === 'PATCH' && /\/etude-params\/$/.test(new URL(r.url()).pathname) && r.status() < 300, { timeout: 180_000 })
    await enregistrerEdition(page)
    await etude
    expect(Number((await lireDevis(api, id)).etude_params.conso_annuelle), 'conso_annuelle enregistrée').toBe(1282)
    // réouverture + ré-enregistrement sans toucher
    await ouvrirEdition(page, id)
    const relu = Number(plat(await page.locator('label', { hasText: 'Consommation annuelle dérivée' }).locator('xpath=..').locator('.gen-kwp').textContent()).replace(/[^\d]/g, ''))
    expect(Math.abs(relu - 1282), `dérivée relue ${relu} (1282 ±12 : réouverture en kWh/mois arrondi)`).toBeLessThanOrEqual(12)
    if (relu !== 1282) testInfo.annotations.push({ type: 'note', description: `réouverture : dérivée affichée ${relu} au lieu de 1282 (arrondi kWh/mois, etatDevis.js:268-269)` })
    await reenregistrerSansToucher(page, id)
    expect(Number((await lireDevis(api, id)).etude_params.conso_annuelle), 'ré-enregistré sans toucher : même conso_annuelle').toBe(1282)
    await textePdfDevis(api, id) // CLIENT : /proposal rend (le chiffre d'économie est couvert par P5.1)
    suivi.verifie(6)
  } finally {
    await nettoyerPlus(api, conserver)
  }
})

// ── P3.3 — agricole : pas de champ « Heures » ; date de déclaration PAR donnée ──
// Gestes : lead agricole (ouvrirGenerateurDepuisLeadAgricole) comme P5.1 → aucun #gen-heures ni « Heures de pompage effectives »
//   (PanneauAgricole.jsx:619, AGNR26) ; déclaration butane (#gen-farm-fuel, #gen-eco-quantite/unite/periode/prix, #gen-eco-date = 2026-09-01 ;
//   PanneauAgricole.jsx:285-320, e2e/devis-agricole-economie.spec.js:39-45) ; créer ; API saisies_economie_pompage : prix et consommation datés
//   2026-09-01 ; rouvrir ⇒ #gen-eco-date vide (AGNR38) ; prix 45 → 52 ; enregistrer ⇒ prix daté d'AUJOURD'HUI (Casablanca), consommation reste
//   2026-09-01 ; rouvrir ⇒ 52. Pas d'horloge truquée : la date passée est TAPÉE dans #gen-eco-date.
etapeBrouillon('P3.3', ['AGNR42'], async ({ page }) => {
  const api = page.request
  const conserver = nouveauxConserves()
  try {
    const lead = await ouvrirGenerateurDepuisLeadAgricole(page, api, 'AGNR42 ferme P3.3')
    conserver.leads.push(lead.id)
    const sansHeures = async () => {
      await expect(page.locator('#gen-heures')).toHaveCount(0)
      await expect(page.getByText(/Heures de pompage effectives/)).toHaveCount(0)
    }
    await page.getByRole('radio', { name: 'Volume déclaré' }).click()
    await page.locator('#gen-besoin-volume').fill('60')
    await page.locator('#gen-hmt').fill('45')
    await page.getByRole('radio', { name: /Tri 380V/ }).click()
    await expect(page.getByTestId('resultat-pompage')).toBeVisible({ timeout: 45_000 })
    await sansHeures()
    await page.locator('#gen-farm-fuel').selectOption('butane')
    await page.locator('#gen-eco-quantite').fill('2')
    await page.locator('#gen-eco-unite').selectOption('bouteille_12kg')
    await page.locator('#gen-eco-periode').selectOption('mois')
    await page.locator('#gen-eco-prix').fill('45')
    await page.locator('#gen-eco-date').fill('2026-09-01')
    await page.getByTestId('btn-auto-remplir').click()
    await expect(page.getByTestId('pompage-auto-rempli')).toBeVisible({ timeout: 180_000 })
    await retirerLignesPrixARenseigner(page)
    const etude0 = page.waitForResponse((r) => r.request().method() === 'PATCH' && /\/etude-params\/$/.test(new URL(r.url()).pathname) && r.status() < 300, { timeout: 180_000 })
    const cree = await creerAvecReprise(page)
    const id = cree.id ?? cree.devis?.id
    conserver.devis.push(id)
    await etude0
    const saisies0 = (await lireDevis(api, id)).etude_params.saisies_economie_pompage
    expect(saisies0.depense_unitaire_payee, 'prix déclaré le 01/09').toMatchObject({ valeur: 45, saisi_le: '2026-09-01' })
    expect(saisies0.consommation.saisi_le, 'consommation déclarée le 01/09').toBe('2026-09-01')

    await ouvrirEdition(page, id)
    await expect(page.locator('#gen-farm-fuel')).toHaveValue('butane', { timeout: 45_000 })
    await sansHeures()
    await expect(page.locator('#gen-eco-date'), 'rien n\'est présenté comme saisi « aujourd\'hui »').toHaveValue('')
    await expect(page.locator('#gen-eco-prix')).toHaveValue('45')
    await page.locator('#gen-eco-prix').fill('52')
    await enregistrerEdition(page)
    const aujourdhui = aujourdhuiCasablanca()
    await expect.poll(async () => (await lireDevis(api, id)).etude_params?.saisies_economie_pompage?.depense_unitaire_payee?.valeur, { timeout: 60_000, message: 'prix 52 enregistré' }).toBe(52)
    const saisies1 = (await lireDevis(api, id)).etude_params.saisies_economie_pompage
    expect(saisies1.depense_unitaire_payee.saisi_le, 'le prix corrigé prend la date du jour (Casablanca)').toBe(aujourdhui)
    expect(saisies1.consommation.saisi_le, 'la consommation garde sa date du 01/09').toBe('2026-09-01')
    await ouvrirEdition(page, id)
    await expect(page.locator('#gen-eco-prix')).toHaveValue('52', { timeout: 45_000 })
    await expect(page.locator('#gen-eco-date')).toHaveValue('')
  } finally {
    await nettoyerPlus(api, conserver)
  }
})

// ── P4.1 — échéancier 70/60/10 refusé SOUS le champ ; quantité 0 annoncée ; création coupée ⇒ UN seul devis ──
// Partie 1 (devis API [A, B], ?edit) : « Personnaliser l'échéancier » (CarteEcheancier.jsx) → #gen-echeance-0/1/2 = 70/60/10 → Enregistrer :
//   aucune écriture, [data-testid=echeancier-somme] « Total des tranches : 140 % — il doit faire 100 % », bandeau
//   [data-testid=erreur-enregistrement] « Échéancier de paiement : … » (usePersistanceDevis.js:83-85) ; tranche vide ⇒ « Tranche 3 vide » ;
//   rien n'a changé côté serveur ; corrigé 50/40/10 + Qté de la 2ᵉ ligne = 0 ⇒ [data-testid=avis-quantite-nulle]
//   « 1 ligne à quantité 0 ne sera pas enregistrée : <désignation> » (DevisGenerator.jsx:2166) ; enregistrer ⇒ 1 ligne + 50/40/10 en API.
// Partie 2 (création coupée) : lead sans devis → générateur → Composition libre + 1 accessoire ; page.route sur POST …/devis/atomic/ :
//   route.fetch() (le SERVEUR valide la création) puis route.abort('timedout') ; message « La connexion a été interrompue — vérifiez la liste
//   des devis avant de recréer » (usePersistanceDevis.js:621 ; ou « expiré » si l'axios 20 s tombe avant) ; GET /ventes/devis/?lead= = 1 déjà ;
//   2ᵉ clic (creerAvecReprise, même Idempotency-Key, ventesApi.js:62) ⇒ même devis, toujours 1.
etapeBrouillon('P4.1', ['AGNR42'], async ({ page, suivi }) => {
  const api = page.request
  const conserver = nouveauxConserves()
  try {
    // ── Partie 1
    const [a, b] = produitsSimples(await catalogueAgnr(api), 2)
    const lead1 = await creerLead(api, 'P4.1 édition')
    conserver.leads.push(lead1.id)
    const devis = await devisParApi(api, lead1, [{ produit: a }, { produit: b }])
    conserver.devis.push(devis.id)
    const avant = await lireDevis(api, devis.id)
    await ouvrirEdition(page, devis.id)
    const ecritures = []
    page.on('request', (r) => { if (r.method() === 'POST' && /\/replace-lines\/$/.test(r.url())) ecritures.push(r.url()) })
    const perso = page.getByRole('button', { name: /Personnaliser l'échéancier/ })
    if (await perso.count()) await perso.click()
    const tranches = page.locator('[data-testid^="echeance-ligne-"]')
    if ((await tranches.count()) !== 3) throw new Error(`NON JOUABLE : l'échéancier de la société a ${await tranches.count()} jalons (3 attendus pour 70/60/10)`)
    const bouton = page.locator('#gen-form').getByRole('button', { name: /Enregistrer les modifications/ })
    const saisir = async (v) => { for (let i = 0; i < 3; i += 1) await page.locator(`#gen-echeance-${i}`).fill(String(v[i])) }
    await saisir([70, 60, 10])
    await expect(page.getByTestId('echeancier-somme')).toContainText('Total des tranches : 140 % — il doit faire 100 %')
    await bouton.click()
    await expect(page.getByTestId('erreur-enregistrement')).toContainText('Échéancier de paiement')
    await saisir([70, 60, ''])
    await bouton.click()
    await expect(page.getByTestId('echeancier-somme')).toContainText(/Tranche 3 vide/)
    expect(ecritures, 'aucune requête d\'écriture pour un échéancier refusé').toEqual([])
    expect((await lireDevis(api, devis.id)).echeancier ?? null, 'serveur inchangé après refus').toEqual(avant.echeancier ?? null)
    // corrigé + quantité 0
    await saisir([50, 40, 10])
    await expect(page.getByTestId('echeancier-somme')).toHaveCount(0)
    await champQte(lignesDom(page).nth(1)).fill('0')
    await expect(page.getByTestId('avis-quantite-nulle')).toContainText(`1 ligne à quantité 0 ne sera pas enregistrée : ${b.nom}`)
    await enregistrerEdition(page)
    const apres = await lireDevis(api, devis.id)
    expect(apres.lignes.length, 'la ligne à quantité 0 n\'est pas enregistrée').toBe(1)
    expect(apres.lignes[0].designation).toBe(a.nom)
    expect((apres.echeancier || []).map((t) => Number(t.pct_or_montant)), 'échéancier corrigé enregistré').toEqual([50, 40, 10])
    await ouvrirEdition(page, devis.id)
    await expect(page.locator('#gen-echeance-0')).toHaveValue('50')
    await expect(page.locator('#gen-echeance-2')).toHaveValue('10')

    // ── Partie 2
    const lead2 = await creerLead(api, 'P4.1 coupure')
    conserver.leads.push(lead2.id)
    await ouvrirGenerateur(page, `/ventes/devis/nouveau?lead=${lead2.id}`)
    await expect(page.locator('#gen-lead')).toContainText(lead2.nom, { timeout: 90_000 })
    await viderLignes(page)
    await activerCompositionLibre(page)
    await ajouterLigneProduit(page, a)
    const cles = []
    page.on('request', (r) => { if (r.method() === 'POST' && /\/ventes\/devis\/atomic\/$/.test(r.url())) cles.push(r.headers()['idempotency-key']) })
    suivi.attendre(/\/ventes\/devis\/atomic\//) // échec INJECTÉ par l'étape (oracles 2/3)
    let coupee = false
    let commit = null
    let finCommit
    const commitFini = new Promise((r) => { finCommit = r })
    await page.route('**/ventes/devis/atomic/', async (route) => {
      if (coupee) return route.continue()
      coupee = true
      try { commit = await route.fetch({ timeout: 170_000 }) } catch (e) { commit = e } // le SERVEUR enregistre ici
      finCommit()
      await route.abort('timedout').catch(() => undefined)
    })
    await page.locator('#gen-form').getByRole('button', { name: /Créer le devis/ }).click()
    await Promise.race([commitFini, page.getByTestId('erreur-enregistrement').waitFor({ state: 'visible', timeout: 180_000 })])
    if (!coupee) {
      throw new Error(`NON JOUABLE : « Créer le devis » refusé avant l'envoi — ${await page.getByTestId('erreur-enregistrement').textContent()}`)
    }
    await commitFini
    expect(commit && typeof commit.status === 'function' && commit.status() < 300, 'le serveur a bien commité la création (route.fetch)').toBeTruthy()
    await expect(page.getByTestId('erreur-enregistrement')).toContainText(/connexion a été interrompue — vérifiez la liste des devis avant de recréer|La connexion a expiré/, { timeout: 60_000 })
    await expect(page.getByTestId('erreur-enregistrement')).not.toContainText('vérifiez les champs')
    expect(await nbDevisDuLead(api, lead2.id), 'après la coupure : le devis existe déjà côté serveur').toBe(1)
    await page.unroute('**/ventes/devis/atomic/')
    const rejoue = await creerAvecReprise(page)
    const idUnique = rejoue.id ?? rejoue.devis?.id
    expect(await nbDevisDuLead(api, lead2.id), 'après le 2ᵉ clic : toujours UN seul devis').toBe(1)
    const liste = listeAgnr(await lireJson(await api.get(`${API}/ventes/devis/?lead=${lead2.id}&page_size=50`, T), 'devis du lead'))
    expect(liste[0].id, 'le 2ᵉ clic a rejoué le premier devis').toBe(idUnique)
    conserver.devis.push(idUnique)
    expect(cles.length, 'deux POST atomic observés').toBeGreaterThanOrEqual(2)
    expect(cles[0], 'Idempotency-Key présente').toBeTruthy()
    expect(new Set(cles).size, 'MÊME Idempotency-Key aux deux clics').toBe(1)
  } finally {
    await nettoyerPlus(api, conserver)
  }
})

// ── P4.3 — étude refusée ⇒ formulaire conservé ; « Réduction » 12,345 normalisée et signalée ─
// Gestes : devis résidentiel créé par l'écran (étude attachée) → ?edit → .gen-discount-input (RailArgent.jsx:71) = 12.345 ⇒
//   [data-testid=note-champ-remise_globale] « 12,345 → 12,35 » (RailArgent.jsx:41) ; page.route PATCH …/etude-params/ ⇒ 400 {detail} (injecté, étape
//   AGNR21 « Preuve en direct : page.route('**/etude-params/', 400) ») ; Enregistrer : replace-lines passe (lignes + en-tête 12.35 déjà écrits),
//   le formulaire RESTE (#gen-form) avec [data-testid=reserve-enregistrement] « Devis enregistré, étude non attachée : … »
//   (DevisGenerator.jsx:2171) ; retirer la route ⇒ nouvel essai ⇒ succès, toujours UN devis ; rouvrir ⇒ 12.35 et étude attachée.
etapeBrouillon('P4.3', ['AGNR42'], async ({ page, suivi }) => {
  const api = page.request
  const conserver = nouveauxConserves()
  try {
    const lead = await creerLead(api, 'P4.3', { facture_hiver: '800', facture_ete: '1600', ete_differente: true })
    conserver.leads.push(lead.id)
    const cree = await creerResidentielDepuisLead(page, lead)
    const id = cree.id ?? cree.devis?.id
    conserver.devis.push(id)
    await ouvrirEdition(page, id)
    const remise = page.locator('.gen-discount-input').first()
    await remise.fill('12.345')
    await expect(page.getByTestId('note-champ-remise_globale')).toHaveText('12,345 → 12,35')
    await expect(remise, 'la frappe n\'est pas arrondie dans le champ').toHaveValue('12.345')

    const REFUS = 'Facture(s) mensuelle(s) inférieure(s) aux lignes fixes du compteur (39,94 MAD TTC/mois).'
    let refus = 0
    suivi.attendre(/\/etude-params\//, 400) // refus INJECTÉ (écran seulement, le serveur n'est pas touché)
    await page.route('**/ventes/devis/*/etude-params/', async (route) => {
      if (route.request().method() !== 'PATCH') return route.continue()
      refus += 1
      await route.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ detail: REFUS }) })
    })
    const ecrit = page.waitForResponse((r) => r.request().method() === 'POST' && /\/replace-lines\/$/.test(new URL(r.url()).pathname) && r.status() < 300, { timeout: 180_000 })
    await page.locator('#gen-form').getByRole('button', { name: /Enregistrer les modifications/ }).click()
    await ecrit
    await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => undefined)
    if (refus === 0) throw new Error('NON JOUABLE : aucun PATCH etude-params émis par l\'enregistrement de ce devis — le refus ne peut pas être rejoué')
    await expect(page.getByTestId('reserve-enregistrement')).toContainText(/Devis enregistré, étude non attachée : Facture\(s\) mensuelle\(s\)/, { timeout: 60_000 })
    await expect(page.locator('#gen-form'), 'le formulaire reste monté').toBeVisible()
    expect(Number((await lireDevis(api, id)).remise_globale), 'les lignes + l\'en-tête sont déjà écrits : 12,35').toBe(12.35)

    await page.unroute('**/ventes/devis/*/etude-params/')
    await enregistrerEdition(page)
    expect(await nbDevisDuLead(api, lead.id), 'le nouvel essai édite le devis, jamais un second').toBe(1)
    await ouvrirEdition(page, id)
    await expect(page.locator('.gen-discount-input').first()).toHaveValue('12.35')
    const etude = (await lireDevis(api, id)).etude_params || {}
    expect(Object.keys(etude).length, 'étude attachée après correction').toBeGreaterThan(0)
  } finally {
    await nettoyerPlus(api, conserver)
  }
})

// ── P5.2 — désignations retouchées ⇒ rail « Sans batterie » inchangé ───────────
// Gestes : devis API [panneaux ×8, onduleur hybride, batterie] (produits du catalogue, désignations = noms) → ?edit ;
//   mémoriser « Total SANS batterie » (.gen-total-item/.gen-total-value, RailArgent.jsx:57) ; renommer la ligne hybride en
//   « Onduleur Deye 5kW (garantie 10 ans) » et la batterie en « Stockage Dyness 5 kWh » (champ Désignation, DevisLineRow.jsx:166 ;
//   dialogue « Renommer sur ce devis seulement », DevisGenerator.jsx:2292) ⇒ « Total SANS batterie » et « AVEC » inchangés ; enregistrer ⇒
//   comparaison_options.sans.ttc inchangé (API) ; /proposal imprime le total SANS de l'écran.
etapeBrouillon('P5.2', ['AGNR42'], async ({ page, suivi }) => {
  const api = page.request
  const conserver = nouveauxConserves()
  try {
    const cat = await catalogueAgnr(api)
    const trouve = (re, exclure = null) => cat.find((p) => re.test(p.nom) && !(exclure && exclure.test(p.nom)))
    const panneau = trouve(/panneau/i)
    const hybride = cat.find((p) => /onduleur/i.test(p.nom) && /hybride/i.test(p.nom) && !/off.?grid|hors.?r[ée]seau/i.test(p.nom))
    const batterie = trouve(/batterie|stockage/i, /onduleur/i)
    const reseau = cat.find((p) => /onduleur/i.test(p.nom) && /r[ée]seau|huawei/i.test(p.nom) && !/hybride|off.?grid/i.test(p.nom))
    if (!panneau || !hybride || !batterie) {
      throw new Error(`NON JOUABLE : catalogue sans panneau (${!!panneau}) / onduleur hybride (${!!hybride}) / batterie (${!!batterie}) chiffrés`)
    }
    const lead = await creerLead(api, 'P5.2')
    conserver.leads.push(lead.id)
    const lignes = [{ produit: panneau, quantite: '8.00' }, ...(reseau ? [{ produit: reseau }] : []), { produit: hybride }, { produit: batterie }]
    const devis = await devisParApi(api, lead, lignes)
    conserver.devis.push(devis.id)
    const avant = await lireDevis(api, devis.id)
    await ouvrirEdition(page, devis.id)
    const valeurRail = async (libelle) => {
      const item = page.locator('.gen-total-item', { hasText: new RegExp(`^\\s*${libelle}`) }).first()
      if (!(await item.count())) throw new Error(`NON JOUABLE : le rail n'affiche pas « ${libelle} » pour ce devis (scénario à une seule option)`)
      return nombre(await item.locator('.gen-total-value').textContent())
    }
    const sans0 = await valeurRail('Total SANS batterie')
    const avec0 = await valeurRail('Total AVEC batterie')
    if (avant.comparaison_options?.sans?.ttc != null) {
      expect(Math.abs(sans0 - Number(avant.comparaison_options.sans.ttc)), `écran SANS ${sans0} = serveur ${avant.comparaison_options.sans.ttc}`).toBeLessThan(0.51)
    }
    const renommer = async (ancienNom, nouveau) => {
      const index = await lignesDom(page).evaluateAll((trs, nom) => trs.findIndex((tr) => tr.querySelector('td[data-label="Désignation"] input')?.value === nom), ancienNom)
      expect(index, `ligne « ${ancienNom} » trouvée`).toBeGreaterThanOrEqual(0)
      const champ = champDesignation(lignesDom(page).nth(index))
      if (!(await champ.isEditable())) throw new Error('NON JOUABLE : désignation non éditable pour demo_admin (canRenameLine faux)')
      await champ.fill(nouveau)
      await champ.blur()
      const dialogue = page.getByRole('dialog')
      await expect(dialogue).toContainText('Désignation modifiée')
      await dialogue.getByRole('button', { name: 'Renommer sur ce devis seulement' }).click()
      await expect(dialogue).toHaveCount(0, { timeout: 60_000 })
    }
    await renommer(hybride.nom, 'Onduleur Deye 5kW (garantie 10 ans)')
    await renommer(batterie.nom, 'Stockage Dyness 5 kWh')
    expect(await valeurRail('Total SANS batterie'), '« Total SANS batterie » inchangé après retouche des désignations').toBeCloseTo(sans0, 2)
    expect(await valeurRail('Total AVEC batterie'), '« Total AVEC batterie » inchangé').toBeCloseTo(avec0, 2)
    await enregistrerEdition(page)
    const apres = await lireDevis(api, devis.id)
    if (avant.comparaison_options?.sans?.ttc != null) {
      expect(Number(apres.comparaison_options.sans.ttc), 'serveur : option SANS inchangée').toBeCloseTo(Number(avant.comparaison_options.sans.ttc), 2)
    }
    await ouvrirEdition(page, devis.id)
    expect(await valeurRail('Total SANS batterie'), 'rouvert : « Total SANS batterie » identique').toBeCloseTo(sans0, 2)
    const { texte } = await textePdfDevis(api, devis.id)
    expect(plat(texte), '/proposal imprime le total SANS de l\'écran').toContain(plat(formatPdf(sans0)))
    suivi.verifie(6)
  } finally {
    await nettoyerPlus(api, conserver)
  }
})
