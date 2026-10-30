// ADEV43 — spec d'acceptation en direct du groupe ADEV (devis : création → édition → envoi → page publique →
// signature → révision), jouée par l'ORCHESTRATEUR sur la pile locale (CLAUDE.md 3-bis, METHODE §C.4, `_format.md`).
//
// Étapes = identifiants stables de l'audit devis (docs/audits, tâche ADEV43 de docs/plans/PLAN_AUDIT_DEVIS.md) :
// P1.2 préfixe société · P2.1 envoyé réenregistré sans toucher · P2.2 prix tapé sur un forfait · P7.2 barème modifié
// puis retouche d'un envoyé · P3.1 remise 15 % puis 60 % · P4.1 jeton client d'un brouillon · P4.3 code sans canal ·
// P2.4 option activée par le client puis écran ouvert avant · P5.1 client bloquant (lien, « Passer outre », Commercial) ·
// P5.2 refus avec motif · P6.1 révision d'un envoyé · P6.3 restaurer une version · P7.4 Commercial de portée équipe ·
// P7.4bis société étrangère · P4.2 duplication sans marqueur parasite.
//
// Principes :
// - chaque étape crée SES leads/devis par l'API réelle (supprimés, ou ARCHIVÉS quand ils sont envoyés : un envoyé ne se
//   supprime pas) ; les trois produits « ADEV43 … » (SKU ADEV43-PAN/OND/FOR-A|F) sont créés une fois puis réutilisés au
//   rejeu ; jamais la prod, jamais une dépendance à une autre étape ;
// - P1.2 et P3.1 règlent des PARAMÈTRES DE SOCIÉTÉ (préfixe, seuil de remise) : ils tournent sur la société
//   « TAQINOR Démo (complet) » (demo_admin_full / demo_resp_full, mot de passe lu du seed `seed_demo_company`) pour ne
//   pas modifier, même brièvement, la société 1 que d'autres rejeux utilisent en même temps ; les réglages sont
//   RESTAURÉS en `finally` ;
// - les contextes API des autres comptes (Responsable de la société complète, Commercial de portée équipe, administrateur
//   étranger) sont créés par l'étape ; le compte Commercial de test est fabriqué par l'API (pile locale seule) ;
// - la page publique `/proposition` (Astro, apps/web) n'est PAS lancée sur cette pile : le côté client est joué sur la
//   charge `GET public/proposal/<jeton>/data/` (celle que la page rend) + le PDF `/proposal` ;
// - le signataire du code (OTP de SIGNATURE) est un no-op tant que ESIGN_OTP_ENABLED n'est pas posé : P4.3 joue donc le
//   code de LECTURE (réglage par lien), qui exige un canal réel.
import { expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import {
  API_DJANGO, assurerSessionPage, connexionApi, lireJson, listeDe, telephoneMobileUnique, textePdf,
} from '../helpers.js'

const etape = groupe('ADEV', ['ADEV43'])
const API = API_DJANGO
const T = { timeout: 180_000 }
const MDP_COMPLET = 'DemoFull@2026!' // seed_demo_company.py::DEMO_PASSWORD (société 43)
const COMMERCIAL = { username: 'adev43_commercial', password: 'Adev43@Test2026!' } // compte de test local, créé ci-dessous
const NOM_ROLE_EQUIPE = 'ADEV43 Commercial équipe'
const SKU = { pan: 'ADEV43-PAN', ond: 'ADEV43-OND', forfait: 'ADEV43-FOR' }

let _n = 0
const uniqueTag = () => { _n += 1; return `${Date.now().toString(36)}${_n}` }
const plat = (s) => String(s).replace(/[\s\u00a0\u202f]+/g, '')
const aujourdhuiMaroc = () => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date())

// ── contextes API ───────────────────────────────────────────────────────────
async function contexte(testInfo, identifiants) {
  const api = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(api, identifiants)
  return api
}
const ADMIN_COMPLET = { username: 'demo_admin_full', password: MDP_COMPLET }
const RESP_COMPLET = { username: 'demo_resp_full', password: MDP_COMPLET }

// ── produits (réutilisés d'une étape à l'autre, supprimés par l'afterAll) ───
const produitsParContexte = new Map()
async function produits(api, cle) {
  if (produitsParContexte.has(cle)) return produitsParContexte.get(cle)
  const trouves = listeDe(await lireJson(await api.get(`${API}/stock/produits/?search=ADEV43&page_size=100`, T), 'produits ADEV43'))
  const creer = async (sku, corps) => {
    const existant = trouves.find((p) => p.sku === `${sku}-${cle}`)
    if (existant) return existant.id
    return (await lireJson(await api.post(`${API}/stock/produits/`, {
      ...T, data: { sku: `${sku}-${cle}`, quantite_stock: 50, ...corps },
    }), `produit ${sku}`)).id
  }
  const p = {
    pan: await creer(SKU.pan, { nom: 'ADEV43 Panneau 710W', prix_vente: '1200.00' }),
    ond: await creer(SKU.ond, { nom: 'ADEV43 Onduleur hybride Deye 5kW', prix_vente: '12500.00' }),
    forfait: await creer(SKU.forfait, {
      nom: 'ADEV43 Forfait accessoires', prix_vente: '1667.00', prix_fixe_ht: '100.00', prix_par_panneau_ht: '50.0000',
    }),
  }
  produitsParContexte.set(cle, p)
  return p
}

// ── lead + devis ────────────────────────────────────────────────────────────
async function creerLead(api, tag, { email = true, owner } = {}) {
  const t = uniqueTag()
  return lireJson(await api.post(`${API}/crm/leads/`, {
    ...T,
    data: {
      nom: `ADEV43 ${tag} ${t}`, telephone: telephoneMobileUnique(), ville: 'Casablanca',
      type_installation: 'residentiel', facture_hiver: '900',
      ...(email ? { email: `adev43-${t}@example.test` } : {}),
      ...(owner ? { owner } : {}),
    },
  }), `lead ${tag}`)
}

/** Devis atomique : 8 panneaux 1 200 HT (TVA 10), 1 onduleur 12 500, + forfait 500 / option 4 panneaux à la demande. */
async function creerDevis(api, p, lead, { remise, note, forfait = true, option = false } = {}) {
  const lignes = [
    { produit: p.pan, designation: 'ADEV43 Panneau 710W', quantite: '8.00', prix_unitaire: '1200.00', remise: '0.00', taux_tva: '10.00', type_ligne: 'produit', ordre: 0 },
    { produit: p.ond, designation: 'ADEV43 Onduleur hybride Deye 5kW', quantite: '1.00', prix_unitaire: '12500.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 1 },
  ]
  if (forfait) lignes.push({ produit: p.forfait, designation: 'ADEV43 Forfait accessoires', quantite: '1.00', prix_unitaire: '500.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 2 })
  if (option) lignes.push({ produit: p.pan, designation: 'ADEV43 Panneau 710W option', quantite: '4.00', prix_unitaire: '1200.00', remise: '0.00', taux_tva: '10.00', type_ligne: 'produit', ordre: 3, optionnelle: true })
  const corps = { lead: lead.id, taux_tva: '20.00', lignes }
  if (remise) corps.remise_globale = remise
  if (note !== undefined) corps.note = note
  const d = await lireJson(await api.post(`${API}/ventes/devis/atomic/`, { ...T, data: corps }), 'devis atomique')
  return lire(api, d.id)
}
const lire = async (api, id) => lireJson(await api.get(`${API}/ventes/devis/${id}/`, T), `devis ${id}`)
async function envoyer(api, id, corps = {}) {
  return lireJson(await api.post(`${API}/ventes/devis/${id}/share-link/`, { ...T, data: { envoi: true, ...corps } }), `envoi du devis ${id}`)
}
const lienClient = async (api, id, corps = {}) =>
  lireJson(await api.post(`${API}/ventes/devis/${id}/share-link/`, { ...T, data: corps }), `lien du devis ${id}`)
const donneesPubliques = (api, jeton) => api.get(`${API}/public/proposal/${jeton}/data/`, T)
const historique = async (api, id) => listeDe(await lireJson(await api.get(`${API}/ventes/devis/${id}/historique/`, T), 'chatter'))
const snapshots = async (api, id) =>
  (await lireJson(await api.get(`${API}/ventes/devis/${id}/historique-configuration/`, T), 'instantanés')).snapshots
async function pdfTexte(api, id) {
  const rep = await api.get(`${API}/ventes/devis/${id}/proposal/`, T)
  expect(rep.status(), `PDF /proposal du devis ${id}`).toBe(200)
  expect(rep.headers()['content-type'] || '').toContain('application/pdf')
  return textePdf(await rep.body())
}
const ttcPublic = (pub) => Number(pub.option_totals.sans_batterie.ttc)

async function nettoyer(api, { devis = [], leads = [] } = {}) {
  // Un devis envoyé ne se supprime pas (409 « archivez-le ») : on l'archive (is_active=false).
  for (const id of devis) {
    const sup = await api.delete(`${API}/ventes/devis/${id}/`, T).catch(() => null)
    if (!sup || !sup.ok()) await api.patch(`${API}/ventes/devis/${id}/`, { ...T, data: { is_active: false } }).catch(() => null)
  }
  for (const id of leads) await api.delete(`${API}/crm/leads/${id}/`, T).catch(() => null)
}

/** Ouvre la liste des devis filtrée (trace + oracles 1-4/8 sur un vrai écran). `compte` = contexte API dont on
 *  recopie la session dans la page (société complète). */
async function voirListe(page, context, q, compte = null) {
  if (compte) await context.addCookies((await compte.storageState()).cookies)
  else await assurerSessionPage(page)
  await page.goto(`/ventes/devis?q=${encodeURIComponent(q)}`)
  await expect(page.getByRole('heading', { name: /Devis/ }).first()).toBeVisible({ timeout: 60_000 })
}

// ── compte Commercial de portée équipe (rôle fabriqué par l'API, pile locale) ─
async function assurerCommercial(api) {
  const roles = listeDe(await lireJson(await api.get(`${API}/roles/?page_size=200`, T), 'rôles'))
  let equipe = roles.find((r) => r.nom === NOM_ROLE_EQUIPE)
  if (!equipe) {
    const modele = roles.find((r) => r.nom === 'Commercial')
    expect(modele, 'rôle système « Commercial » absent').toBeTruthy()
    const permissions = modele.permissions.map((x) => (x === 'records_scope_soi' ? 'records_scope_equipe' : x))
    equipe = await lireJson(await api.post(`${API}/roles/`, { ...T, data: { nom: NOM_ROLE_EQUIPE, permissions } }), 'rôle Commercial équipe')
  }
  expect(equipe.permissions, 'portée équipe').toContain('records_scope_equipe')
  expect(equipe.permissions, 'ventes_valider porté').toContain('ventes_valider')
  const r = await api.post(`${API}/users/`, {
    ...T,
    data: {
      username: COMMERCIAL.username, email: `${COMMERCIAL.username}@example.test`, password: COMMERCIAL.password,
      first_name: 'ADEV43', last_name: 'Commercial', role: equipe.id,
    },
  })
  if (!r.ok()) {
    const corps = await r.text()
    expect(/existe|exists|unique|déjà/i.test(corps), `création du Commercial de test refusée (${r.status()} ${corps.slice(0, 200)})`).toBeTruthy()
  }
}

// ════════════════════════════════════════════════════════════════════════════
etape('P1.2', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  const adm = await contexte(testInfo, ADMIN_COMPLET)
  const p = await produits(adm, 'F')
  const profilAvant = await lireJson(await adm.get(`${API}/parametres/`, T), 'profil société')
  const creeLeads = []
  const creeDevis = []
  try {
    // Préfixe société configuré → tout devis créé depuis un lead le porte.
    await lireJson(await adm.patch(`${API}/parametres/update/`, {
      ...T, data: { doc_prefixes: { devis: 'DVX', facture: 'FAC', avoir: 'AVO', bon_commande: 'BC' } },
    }), 'préfixe DVX')
    const lead = await creerLead(adm, 'prefixe'); creeLeads.push(lead.id)
    const devis = await creerDevis(adm, p, lead); creeDevis.push(devis.id)
    expect(devis.reference, 'préfixe appliqué').toMatch(/^DVX-\d{6}-\d{4}$/)
    // PERSISTANCE : relu, la référence est identique.
    expect((await lire(adm, devis.id)).reference).toBe(devis.reference)
    // CLIENT : page publique (jeton d'aperçu interne) et PDF /proposal affichent la référence configurée.
    const lien = await lienClient(adm, devis.id)
    const pub = await lireJson(await donneesPubliques(adm, lien.token_interne), 'charge publique')
    expect(pub.reference).toBe(devis.reference)
    expect(plat(await pdfTexte(adm, devis.id))).toContain(plat(devis.reference))
    // Sans préfixe configuré : « DEV- » comme avant.
    await lireJson(await adm.patch(`${API}/parametres/update/`, { ...T, data: { doc_prefixes: null } }), 'préfixe retiré')
    const lead2 = await creerLead(adm, 'sans prefixe'); creeLeads.push(lead2.id)
    const devis2 = await creerDevis(adm, p, lead2); creeDevis.push(devis2.id)
    expect(devis2.reference, 'sans préfixe configuré').toMatch(/^DEV-\d{6}-\d{4}$/)
    await voirListe(page, context, devis.reference, adm)
  } finally {
    await adm.patch(`${API}/parametres/update/`, { ...T, data: { doc_prefixes: profilAvant.doc_prefixes ?? null } }).catch(() => null)
    await nettoyer(adm, { devis: creeDevis, leads: creeLeads })
    await adm.dispose()
  }
})

etape('P2.1', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  await assurerSessionPage(page)
  const api = page.request
  const p = await produits(api, 'A')
  const lead = await creerLead(api, 'p21')
  const devis = await creerDevis(api, p, lead)
  try {
    await envoyer(api, devis.id)
    const avant = await lire(api, devis.id)
    expect(avant.statut).toBe('envoye')
    expect(Object.keys(avant.etude_params || {}).length, 'le devis porte une étude').toBeGreaterThan(0)
    const traces = (await historique(api, devis.id)).length
    const etude = JSON.stringify(avant.etude_params)
    // Premier enregistrement : il peut verser UNE FOIS un instantané de normalisation (date de validité posée à l'envoi,
    // absente de l'instantané de création — « normalisation au premier enregistrement », hors périmètre ADEV26) ; la
    // clause porte sur tout ce qui suit : l'étude, le chatter et les instantanés ne bougent plus.
    await lireJson(await api.patch(`${API}/ventes/devis/${devis.id}/`, { ...T, data: {} }), 'PATCH vide (1er enregistrement)')
    const instantanes = (await snapshots(api, devis.id)).length
    // « Rouvrir et enregistrer sans toucher » : PATCH vide, puis le même en-tête renvoyé tel que lu.
    await lireJson(await api.patch(`${API}/ventes/devis/${devis.id}/`, { ...T, data: {} }), 'PATCH vide')
    await lireJson(await api.patch(`${API}/ventes/devis/${devis.id}/`, {
      ...T, data: { taux_tva: avant.taux_tva, remise_globale: avant.remise_globale, date_validite: avant.date_validite, note: avant.note ?? '' },
    }), 'PATCH en-tête identique')
    // PERSISTANCE : relu après coup, l'étude est identique à l'octet près, aucune trace nouvelle.
    const apres = await lire(api, devis.id)
    expect(JSON.stringify(apres.etude_params) === etude, 'étude octet-identique').toBe(true)
    expect((await historique(api, devis.id)).length, 'aucune trace au chatter').toBe(traces)
    expect((await snapshots(api, devis.id)).length, 'aucun instantané de plus').toBe(instantanes)
    expect(apres.total_ttc).toBe(avant.total_ttc)
    // Une vraie correction d'en-tête (validité) ne ré-écrit pas les études.
    const plusTard = new Date(Date.now() + 20 * 86400000).toISOString().slice(0, 10)
    await lireJson(await api.patch(`${API}/ventes/devis/${devis.id}/`, { ...T, data: { date_validite: plusTard } }), 'PATCH validité')
    // (la trace « corrigé après envoi — en-tête » et son marqueur `resync_apres_envoi` s'ajoutent : QJR518 ; les valeurs
    // d'étude, elles, restent identiques)
    const sansMarqueur = (e) => JSON.stringify(Object.fromEntries(Object.entries(e || {}).filter(([k]) => k !== 'resync_apres_envoi')))
    expect(sansMarqueur((await lire(api, devis.id)).etude_params) === sansMarqueur(avant.etude_params), 'valeurs d\'étude intactes après un champ d\'en-tête').toBe(true)
    await voirListe(page, context, devis.reference)
  } finally {
    await nettoyer(api, { devis: [devis.id], leads: [lead.id] })
  }
})

etape('P2.2', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  await assurerSessionPage(page)
  const api = page.request
  const p = await produits(api, 'A')
  const lead = await creerLead(api, 'p22')
  const devis = await creerDevis(api, p, lead, { forfait: false })
  try {
    const ajout = await lireJson(await api.post(`${API}/ventes/devis-lignes/`, {
      ...T,
      data: { devis: devis.id, produit: p.forfait, designation: 'ADEV43 Forfait accessoires', quantite: '1.00', prix_unitaire: '12345.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 2 },
    }), 'ajout du forfait à 12 345')
    const lireLigne = async () => lireJson(await api.get(`${API}/ventes/devis-lignes/${ajout.id}/`, T), 'ligne relue')
    expect(Number((await lireLigne()).prix_unitaire), 'prix tapé conservé (ajout)').toBe(12345)
    const modif = await lireJson(await api.patch(`${API}/ventes/devis-lignes/${ajout.id}/`, { ...T, data: { prix_unitaire: '22222.00' } }), 'modif 22 222')
    const relue = await lireLigne()
    // La réponse HTTP égale la ligne relue en base ; le prix est verrouillé.
    expect(Number(modif.prix_unitaire), 'réponse = base').toBe(Number(relue.prix_unitaire))
    expect(Number(relue.prix_unitaire), 'prix tapé conservé (modification)').toBe(22222)
    expect(relue.prix_manuel, 'marqueur manuel').toBe(true)
    // PERSISTANCE : une autre retouche du devis ne remet pas le forfait au barème.
    const panneau = (await lire(api, devis.id)).lignes.find((l) => /Panneau/.test(l.designation))
    await lireJson(await api.patch(`${API}/ventes/devis-lignes/${panneau.id}/`, { ...T, data: { designation: 'ADEV43 Panneau 710W (retouche)' } }), 'retouche voisine')
    expect(Number((await lireLigne()).prix_unitaire), 'prix conservé après une retouche voisine').toBe(22222)
    // CLIENT : page publique (aperçu) et /proposal montrent 22 222 HT = 26 666,40 TTC sur la ligne.
    const lien = await lienClient(api, devis.id)
    const pub = await lireJson(await donneesPubliques(api, lien.token_interne), 'charge publique')
    const ligneClient = pub.quote.all_items.find((l) => /Forfait/.test(l.designation))
    expect(ligneClient.prix_unit_ht, 'page publique : prix HT du forfait').toBe(22222)
    expect(Math.round(ligneClient.prix_unit_ttc * 100), 'page publique : prix TTC du forfait').toBe(2666640)
    const texteP22 = await pdfTexte(api, devis.id)
    // Le PDF imprime le P.U. et le total HT de la ligne (22 222,00) et le Total TTC du devis.
    expect(/22[\s\u00a0\u202f]?222,00/.test(texteP22), '/proposal : la ligne forfait à 22 222,00 HT').toBe(true)
    const ttcDevis = Number((await lire(api, devis.id)).total_ttc).toFixed(2).replace('.', ',')
    expect(plat(texteP22).includes(plat(ttcDevis)), `/proposal : Total TTC du devis ${ttcDevis}`).toBe(true)
    await voirListe(page, context, devis.reference)
  } finally {
    await nettoyer(api, { devis: [devis.id], leads: [lead.id] })
  }
})

etape('P7.2', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  await assurerSessionPage(page)
  const api = page.request
  const p = await produits(api, 'A')
  const lead = await creerLead(api, 'p72')
  const devis = await creerDevis(api, p, lead)
  const bareme = { prix_fixe_ht: '100.00', prix_par_panneau_ht: '50.0000' }
  try {
    const lien = await envoyer(api, devis.id)
    const avant = await lire(api, devis.id)
    const ttc0 = avant.total_ttc
    const forfait0 = avant.lignes.find((l) => /Forfait/.test(l.designation)).prix_unitaire
    // Le barème du jour est relevé de 100 par panneau, puis on retouche UNE désignation d'une autre ligne.
    await lireJson(await api.patch(`${API}/stock/produits/${p.forfait}/`, { ...T, data: { prix_par_panneau_ht: '150.0000' } }), 'barème relevé')
    const panneau = avant.lignes.find((l) => /Panneau/.test(l.designation))
    await lireJson(await api.patch(`${API}/ventes/devis-lignes/${panneau.id}/`, { ...T, data: { designation: 'ADEV43 Panneau 710W (retouche)' } }), 'retouche de désignation')
    // PERSISTANCE : relu, le TTC et la ligne forfait n'ont pas bougé.
    const apres = await lire(api, devis.id)
    expect(apres.total_ttc, 'TTC inchangé à l\'écran').toBe(ttc0)
    expect(apres.lignes.find((l) => /Forfait/.test(l.designation)).prix_unitaire, 'forfait inchangé').toBe(forfait0)
    // CLIENT : lien client = écran = /proposal.
    const pub = await lireJson(await donneesPubliques(api, lien.token), 'lien client')
    expect(ttcPublic(pub), 'lien client').toBe(Number(ttc0))
    expect(plat(await pdfTexte(api, devis.id))).toContain(plat(Number(ttc0).toFixed(2).replace('.', ',')))
    await voirListe(page, context, devis.reference)
  } finally {
    await api.patch(`${API}/stock/produits/${p.forfait}/`, { ...T, data: { prix_par_panneau_ht: bareme.prix_par_panneau_ht } }).catch(() => null)
    await nettoyer(api, { devis: [devis.id], leads: [lead.id] })
  }
})

etape('P3.1', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  const adm = await contexte(testInfo, ADMIN_COMPLET)
  const resp = await contexte(testInfo, RESP_COMPLET)
  const p = await produits(adm, 'F')
  const avant = await lireJson(await adm.get(`${API}/parametres/`, T), 'profil société')
  const creeLeads = []
  const creeDevis = []
  try {
    await lireJson(await adm.patch(`${API}/parametres/update/`, { ...T, data: { discount_approval_threshold: '10' } }), 'seuil 10 %')
    const lead = await creerLead(adm, 'p31'); creeLeads.push(lead.id)
    const devis = await creerDevis(adm, p, lead, { remise: '15', forfait: false }); creeDevis.push(devis.id)
    // (0) 15 % > 10 % sans approbation : envoi du Responsable refusé.
    const sans = await resp.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } })
    expect(sans.status(), 'envoi sans approbation').toBe(400)
    // (a) l'admin approuve 15 % ; le Responsable passe la remise à 60 % ; l'envoi est refusé et le devis reste brouillon.
    const approuve = await lireJson(await adm.post(`${API}/ventes/devis/${devis.id}/approuver-remise/`, T), 'approbation')
    expect(approuve.remise_approuvee).toBe(true)
    expect(Number(approuve.remise_approuvee_pct)).toBe(15)
    await lireJson(await resp.patch(`${API}/ventes/devis/${devis.id}/`, { ...T, data: { remise_globale: '60' } }), 'remise 60 %')
    const refus = await resp.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } })
    expect(refus.status(), 'envoi à 60 % refusé').toBe(400)
    expect(await refus.text(), 'message nommant la profondeur approuvée').toMatch(/15/)
    const relu = await lire(adm, devis.id)
    expect(relu.statut, 'reste brouillon').toBe('brouillon')
    expect(Number(relu.remise_globale)).toBe(60)
    expect(Number(relu.remise_approuvee_pct), 'profondeur approuvée persistée').toBe(15)
    // (b) un envoyé approuvé à 15 % : le Responsable ne peut pas porter une ligne à 60 % (409 nommant `remise`).
    const lead2 = await creerLead(adm, 'p31b'); creeLeads.push(lead2.id)
    const devis2 = await creerDevis(adm, p, lead2, { remise: '15', forfait: false }); creeDevis.push(devis2.id)
    await lireJson(await adm.post(`${API}/ventes/devis/${devis2.id}/approuver-remise/`, T), 'approbation 2')
    await envoyer(adm, devis2.id)
    const ligne = (await lire(adm, devis2.id)).lignes[0]
    const lr = await resp.patch(`${API}/ventes/devis-lignes/${ligne.id}/`, { ...T, data: { remise: '60' } })
    expect(lr.status(), 'ligne à 60 % sur un envoyé').toBe(409)
    expect(Object.keys(await lr.json())).toContain('remise')
    expect(Number((await lireJson(await adm.get(`${API}/ventes/devis-lignes/${ligne.id}/`, T), 'ligne relue')).remise), 'ligne inchangée').toBe(0)
    // Un administrateur passe comme avant.
    await lireJson(await adm.patch(`${API}/ventes/devis-lignes/${ligne.id}/`, { ...T, data: { remise: '60' } }), 'admin passe')
    await voirListe(page, context, devis.reference, adm)
  } finally {
    await adm.patch(`${API}/parametres/update/`, { ...T, data: { discount_approval_threshold: avant.discount_approval_threshold ?? null } }).catch(() => null)
    await nettoyer(adm, { devis: creeDevis, leads: creeLeads })
    await adm.dispose()
    await resp.dispose()
  }
})

etape('P4.1', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  await assurerSessionPage(page)
  const api = page.request
  const p = await produits(api, 'A')
  const lead = await creerLead(api, 'p41')
  const devis = await creerDevis(api, p, lead)
  try {
    // Lien frappé SANS envoi : le jeton client d'un brouillon ne sert rien.
    const lien = await lienClient(api, devis.id)
    const lecture = await donneesPubliques(api, lien.token)
    expect(lecture.status(), 'GET data au jeton client d\'un brouillon').toBe(404)
    const signe = await api.post(`${API}/public/proposal/${lien.token}/accept/`, { ...T, data: { nom: 'Client', consent_esign: true } })
    expect(signe.status(), 'POST accept').toBe(409)
    expect((await signe.json()).code).toBe('brouillon')
    // Le devis reste brouillon : ni signature ni chantier.
    const relu = await lire(api, devis.id)
    expect(relu.statut).toBe('brouillon')
    expect(relu.chantier ?? null).toBeNull()
    // « Ouvrir la page client » (aperçu interne) : la charge est servie.
    const apercu = await donneesPubliques(api, lien.token_interne)
    expect(apercu.status(), 'jeton d\'aperçu interne').toBe(200)
    expect((await apercu.json()).reference).toBe(devis.reference)
    // Dès l'envoi, le jeton client sert normalement (même jeton).
    await envoyer(api, devis.id)
    expect((await donneesPubliques(api, lien.token)).status(), 'jeton client après envoi').toBe(200)
    await voirListe(page, context, devis.reference)
  } finally {
    await nettoyer(api, { devis: [devis.id], leads: [lead.id] })
  }
})

etape('P4.3', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  await assurerSessionPage(page)
  const api = page.request
  const p = await produits(api, 'A')
  const sans = await creerLead(api, 'p43 sans mail', { email: false })
  const avec = await creerLead(api, 'p43 avec mail')
  const dSans = await creerDevis(api, p, sans)
  const dAvec = await creerDevis(api, p, avec)
  try {
    // Client SANS e-mail : le lien ne peut pas exiger un code de lecture (400 nommant `otp_lecture`).
    const refus = await api.post(`${API}/ventes/devis/${dSans.id}/share-link/`, { ...T, data: { envoi: true, otp_lecture: true } })
    expect(refus.status(), 'otp_lecture refusé sans canal').toBe(400)
    expect(Object.keys(await refus.json())).toContain('otp_lecture')
    expect((await lire(api, dSans.id)).statut, 'aucun effet de bord : reste brouillon').toBe('brouillon')
    // Client AVEC e-mail : le code de lecture part (« Code envoyé. »).
    const lien = await envoyer(api, dAvec.id, { otp_lecture: true })
    expect(lien.otp_lecture).toBe(true)
    const part = await api.post(`${API}/public/proposal/${lien.token}/otp-lecture/demander/`, { ...T, data: {} })
    expect(part.status()).toBe(200)
    expect((await part.json()).detail).toBe('Code envoyé.')
    // Le client perd son e-mail : plus aucun canal → 409 `aucun_canal` avec le message nommé.
    const clientId = (await lire(api, dAvec.id)).client
    await lireJson(await api.patch(`${API}/crm/clients/${clientId}/`, { ...T, data: { email: null } }), 'e-mail retiré')
    const aucun = await api.post(`${API}/public/proposal/${lien.token}/otp-lecture/demander/`, { ...T, data: {} })
    expect(aucun.status(), 'code sans canal').toBe(409)
    const corps = await aucun.json()
    expect(corps.code).toBe('aucun_canal')
    expect(corps.detail).toMatch(/^Aucun moyen d'envoyer le code/)
    // PERSISTANCE : la demande suivante donne le même verdict (aucun code gardé en cache).
    expect((await api.post(`${API}/public/proposal/${lien.token}/otp-lecture/demander/`, { ...T, data: {} })).status()).toBe(409)
    await voirListe(page, context, dAvec.reference)
  } finally {
    await nettoyer(api, { devis: [dSans.id, dAvec.id], leads: [sans.id, avec.id] })
  }
})

etape('P2.4', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  await assurerSessionPage(page)
  const api = page.request
  const p = await produits(api, 'A')
  const lead = await creerLead(api, 'p24')
  const devis = await creerDevis(api, p, lead, { forfait: false, option: true })
  try {
    const lien = await envoyer(api, devis.id)
    const ouvert = await lire(api, devis.id) // l'écran ouvert avant (jeton t0)
    const option = ouvert.lignes.find((l) => l.optionnelle)
    expect(option, 'ligne optionnelle').toBeTruthy()
    const ttc0 = Number(ouvert.total_ttc)
    // Le client active l'option sur la page publique.
    const act = await api.post(`${API}/public/proposal/${lien.token}/activer-option/`, { ...T, data: { ligne_id: option.id } })
    expect(act.status()).toBe(200)
    const apresClient = await lire(api, devis.id)
    expect(Number(apresClient.total_ttc), 'l\'option entre dans le total').toBeGreaterThan(ttc0)
    // L'interne enregistre l'écran ouvert avant : 409 `devis_modifie`, le choix du client n'est pas effacé.
    const lignes = ouvert.lignes.map((l) => ({
      produit: l.produit, designation: l.designation, quantite: l.quantite, prix_unitaire: l.prix_unitaire,
      remise: l.remise, taux_tva: l.taux_tva, type_ligne: l.type_ligne, ordre: l.ordre, optionnelle: l.optionnelle,
    }))
    const enreg = await api.post(`${API}/ventes/devis/${devis.id}/replace-lines/`, { ...T, data: { lignes, expected_updated_at: ouvert.updated_at } })
    expect(enreg.status(), 'enregistrement du jeton périmé').toBe(409)
    expect((await enreg.json()).code).toBe('devis_modifie')
    // PERSISTANCE : relu, la ligne reste activée et le total inclut l'option.
    const relu = await lire(api, devis.id)
    expect(relu.lignes.find((l) => l.id === option.id).optionnelle, 'option toujours activée').toBe(false)
    expect(Number(relu.total_ttc)).toBe(Number(apresClient.total_ttc))
    // Trace « corrigé après envoi — option client » au chatter.
    expect((await historique(api, devis.id)).some((h) => /option client/i.test(`${h.new_value || ''} ${h.body || ''}`))).toBe(true)
    // CLIENT : la page publique inclut l'option.
    expect(ttcPublic(await lireJson(await donneesPubliques(api, lien.token), 'charge publique'))).toBe(Number(relu.total_ttc))
    await voirListe(page, context, devis.reference)
  } finally {
    await nettoyer(api, { devis: [devis.id], leads: [lead.id] })
  }
})

etape('P5.1', ['ADEV43'], async ({ page, context, suivi, testInfo }) => {
  testInfo.setTimeout(900_000)
  await assurerSessionPage(page)
  await assurerCommercial(page.request)
  const api = page.request
  const com = await contexte(testInfo, COMMERCIAL)
  const p = await produits(api, 'A')
  const creeLeads = []
  const creeDevis = []
  try {
    // ── A. Lien client : message NEUTRE (aucun motif interne) ; aucune acceptation, aucun chantier ──
    const lead = await creerLead(api, 'p51'); creeLeads.push(lead.id)
    const devis = await creerDevis(api, p, lead, { forfait: false }); creeDevis.push(devis.id)
    const lien = await envoyer(api, devis.id)
    const clientId = (await lire(api, devis.id)).client
    await lireJson(await api.patch(`${API}/crm/clients/${clientId}/`, {
      ...T, data: { avertissement_vente: 'Client à traiter au comptant ADEV43', avertissement_bloquant: true },
    }), 'client bloquant')
    const pub = await lireJson(await donneesPubliques(api, lien.token), 'charge publique')
    const signe = await api.post(`${API}/public/proposal/${lien.token}/accept/`, {
      ...T, data: { nom: 'Client Test', consent_esign: true, empreinte_contenu: pub.empreinte_contenu },
    })
    expect(signe.status(), 'signature par le lien').toBe(409)
    const corpsSigne = await signe.json()
    expect(corpsSigne.code).toBe('validation_requise')
    expect(JSON.stringify(corpsSigne), 'le motif interne ne fuit pas').not.toMatch(/comptant|Avertissement de vente|ADEV43/)
    let relu = await lire(api, devis.id)
    expect(relu.statut, 'reste envoyé').toBe('envoye')
    expect(relu.chantier ?? null, 'aucun chantier').toBeNull()

    // ── B. Écran : accepter (date locale), motif du 403 affiché, « Passer outre » en admin ──
    suivi.attendre(new RegExp(`/ventes/devis/${devis.id}/accepter/$`), 403)
    await voirListe(page, context, devis.reference)
    const ligne = page.locator(`#devis-row-${devis.id}`)
    await expect(ligne).toBeVisible({ timeout: 60_000 })
    await ligne.getByRole('button', { name: /Accepter/ }).click()
    const dialogue = page.getByRole('dialog')
    await expect(dialogue).toBeVisible()
    const dateLocale = aujourdhuiMaroc()
    await expect(dialogue.locator('#accept-date'), 'date d\'acceptation = jour LOCAL').toHaveValue(dateLocale)
    await expect(dialogue.locator('#accept-date')).toHaveAttribute('max', dateLocale)
    await dialogue.locator('#accept-nom').fill('Client ADEV43')
    await dialogue.getByRole('button', { name: /Confirmer l'acceptation/ }).click()
    await expect(page.getByRole('alert').filter({ hasText: /Avertissement de vente bloquant/ })).toBeVisible({ timeout: 60_000 })
    relu = await lire(api, devis.id)
    expect(relu.statut, 'refus 403 : reste envoyé').toBe('envoye')
    await page.getByRole('button', { name: 'Passer outre' }).click()
    await expect.poll(async () => (await lire(api, devis.id)).statut, { timeout: 120_000 }).toBe('accepte')
    // PERSISTANCE : F5, la ligne reste « Accepté ».
    await page.reload()
    await expect(page.locator(`#devis-row-${devis.id}`)).toBeVisible({ timeout: 60_000 })

    // ── C. Commercial de portée équipe : 403 même avec le drapeau (seuls Responsable/Admin passent outre) ──
    const leadC = await creerLead(com, 'p51 commercial'); creeLeads.push(leadC.id)
    const devisC = await creerDevis(com, p, leadC, { forfait: false }); creeDevis.push(devisC.id)
    await envoyer(com, devisC.id)
    const clientC = (await lire(com, devisC.id)).client
    await lireJson(await api.patch(`${API}/crm/clients/${clientC}/`, {
      ...T, data: { avertissement_vente: 'Client à traiter au comptant ADEV43', avertissement_bloquant: true },
    }), 'client bloquant (Commercial)')
    const sans = await com.post(`${API}/ventes/devis/${devisC.id}/accepter/`, { ...T, data: { nom: 'Client C' } })
    expect(sans.status(), 'Commercial sans drapeau').toBe(403)
    const avec = await com.post(`${API}/ventes/devis/${devisC.id}/accepter/`, { ...T, data: { nom: 'Client C', override_avertissement: true } })
    expect(avec.status(), 'Commercial avec drapeau').toBe(403)
    expect((await avec.json()).detail).toMatch(/Un responsable ou un administrateur peut passer outre/)
    expect((await lire(api, devisC.id)).statut, 'Commercial : reste envoyé').toBe('envoye')
  } finally {
    await nettoyer(api, { devis: creeDevis, leads: creeLeads })
    await com.dispose()
  }
})

etape('P5.2', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  await assurerSessionPage(page)
  const api = page.request
  const p = await produits(api, 'A')
  const l1 = await creerLead(api, 'p52 motif')
  const l2 = await creerLead(api, 'p52 temoin')
  const d1 = await creerDevis(api, p, l1, { forfait: false })
  const d2 = await creerDevis(api, p, l2, { forfait: false })
  try {
    await envoyer(api, d1.id)
    await envoyer(api, d2.id)
    const motifs = listeDe(await lireJson(await api.get(`${API}/crm/motifs-perte/?page_size=100`, T), 'motifs de perte'))
    const motif = motifs.find((m) => m.nom === 'Concurrent' && !m.archived)
    expect(motif, 'motif « Concurrent » actif').toBeTruthy()
    // Un motif inconnu est refusé (400 nommant `motif`) ; le devis reste envoyé.
    const inconnu = await api.post(`${API}/ventes/devis/${d1.id}/refuser/`, { ...T, data: { motif: 'inconnu' } })
    expect(inconnu.status()).toBe(400)
    expect(Object.keys(await inconnu.json())).toContain('motif')
    expect((await lire(api, d1.id)).statut).toBe('envoye')
    // Refus avec motif + note ; le témoin est refusé SANS motif.
    const refuse = await lireJson(await api.post(`${API}/ventes/devis/${d1.id}/refuser/`, { ...T, data: { motif: motif.nom, note: 'Choisi un concurrent ADEV43' } }), 'refus avec motif')
    expect(refuse.motif_refus).toBe(motif.nom)
    await lireJson(await api.post(`${API}/ventes/devis/${d2.id}/refuser/`, { ...T, data: {} }), 'refus sans motif (témoin)')
    // Chatter : le motif y figure (PERSISTANCE : relu).
    const chatter = await historique(api, d1.id)
    expect(chatter.some((h) => /motif : Concurrent/.test(`${h.new_value || ''} ${h.body || ''}`)), 'motif au chatter').toBe(true)
    expect((await lire(api, d1.id)).motif_refus).toBe(motif.nom)
    // « Refusés sans motif » : le témoin y est, le refus motivé n'y est pas.
    const panier = (await lireJson(await api.get(`${API}/ventes/devis/action-requise/`, T), 'action requise')).buckets.refuses_sans_motif
    expect(panier.ids, 'témoin sans motif présent').toContain(d2.id)
    expect(panier.ids, 'refus motivé absent').not.toContain(d1.id)
    await voirListe(page, context, d1.reference)
  } finally {
    await nettoyer(api, { devis: [d1.id, d2.id], leads: [l1.id, l2.id] })
  }
})

etape('P6.1', ['ADEV43'], async ({ page, context, suivi, testInfo }) => {
  testInfo.setTimeout(900_000)
  await assurerSessionPage(page)
  const api = page.request
  const p = await produits(api, 'A')
  const lead = await creerLead(api, 'p61')
  const v1 = await creerDevis(api, p, lead, { forfait: false })
  const creeDevis = [v1.id]
  const envoyes = async () => Number((await lireJson(await api.get(`${API}/ventes/dashboard/`, T), 'tableau de bord')).devis.envoyes)
  try {
    await envoyer(api, v1.id)
    const n0 = await envoyes()
    // Réviser un envoyé : V2 brouillon, V1 remplacée.
    const v2 = await lireJson(await api.post(`${API}/ventes/devis/${v1.id}/reviser/`, T), 'révision'); creeDevis.push(v2.id)
    const v1Relu = await lire(api, v1.id)
    expect(v1Relu.is_active, 'V1 remplacée').toBe(false)
    expect(v1Relu.statut).toBe('envoye')
    // Les gestes d'envoi / refus sur V1 répondent 409 `version_remplacee`.
    const refus = await api.post(`${API}/ventes/devis/${v1.id}/refuser/`, { ...T, data: { motif: 'Concurrent' } })
    expect(refus.status()).toBe(409)
    expect((await refus.json()).code).toBe('version_remplacee')
    const renvoi = await api.post(`${API}/ventes/devis/${v1.id}/share-link/`, { ...T, data: { envoi: true } })
    expect(renvoi.status()).toBe(409)
    expect((await lire(api, v1.id)).statut, 'V1 reste envoyée').toBe('envoye')
    // Tableau de bord : la V1 remplacée n'est plus comptée ; l'envoi de la V2 remet le compte à N (pas N+1).
    await envoyer(api, v2.id)
    expect(await envoyes(), 'envoyés au tableau de bord (V1 non comptée)').toBe(n0)
    // Écran : la ligne de la V1 n'offre ni Refuser, ni Accepter, ni Relancer, ni Copier le lien, et dit « Remplacée par ».
    await voirListe(page, context, lead.nom) // le nom du client rassemble V1 et V2
    // Les versions remplacées sont masquées par défaut (U7) : on les affiche.
    const voir = page.getByRole('button', { name: /Voir les versions remplacées/ })
    await expect(voir).toBeVisible({ timeout: 60_000 })
    await voir.click()
    const ligne = page.locator(`#devis-row-${v1.id}`)
    await expect(ligne).toBeVisible({ timeout: 60_000 })
    await expect(ligne.getByTestId('devis-remplacee-par')).toContainText(/Remplacée par/)
    for (const nom of [/Refuser/, /Accepter/, /Relancer/, /Copier le lien/]) {
      await expect(ligne.getByRole('button', { name: nom }), `V1 sans « ${nom} »`).toHaveCount(0)
    }
    await expect(ligne.getByText(/Copier le lien/)).toHaveCount(0)
    // PERSISTANCE : F5, même constat ; la V2 garde ses gestes (envoyée).
    await page.reload()
    const bascule = page.getByRole('button', { name: /versions remplacées/ })
    await expect(bascule).toBeVisible({ timeout: 60_000 })
    if (/^Voir/.test((await bascule.innerText()).trim())) await bascule.click()
    await expect(page.locator(`#devis-row-${v1.id}`).getByTestId('devis-remplacee-par')).toBeVisible({ timeout: 60_000 })
    await expect(page.locator(`#devis-row-${v2.id}`).getByRole('button', { name: /Accepter/ })).toBeVisible()
    void suivi
  } finally {
    await nettoyer(api, { devis: creeDevis.reverse(), leads: [lead.id] })
  }
})

etape('P6.3', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  await assurerSessionPage(page)
  const api = page.request
  const p = await produits(api, 'A')
  const lead = await creerLead(api, 'p63')
  const NOTE0 = 'Note client d\'origine ADEV43'
  const devis = await creerDevis(api, p, lead, { forfait: false, note: NOTE0 })
  try {
    const lien = await envoyer(api, devis.id)
    expect((await lire(api, devis.id)).note).toBe(NOTE0)
    // Correction après envoi : la note change (et un instantané s'ajoute).
    const NOTE1 = 'Note corrigée ADEV43'
    await lireJson(await api.patch(`${API}/ventes/devis/${devis.id}/`, { ...T, data: { note: NOTE1 } }), 'correction de la note')
    expect((await lire(api, devis.id)).note).toBe(NOTE1)
    const instantanes = await snapshots(api, devis.id)
    const origine = instantanes.find((s) => (s.contenu?.note ?? null) === NOTE0)
    expect(origine, 'un instantané porte la note d\'origine').toBeTruthy()
    // « Revenir à cette version » = ré-enregistrement du contenu de l'instantané par l'enregistrement normal.
    const { entete } = origine.contenu
    await lireJson(await api.patch(`${API}/ventes/devis/${devis.id}/`, {
      ...T, data: { note: origine.contenu.note, taux_tva: entete.taux_tva, remise_globale: entete.remise_globale },
    }), 'restauration')
    // PERSISTANCE + CLIENT : la note d'origine est rétablie à l'écran et sur la page publique.
    expect((await lire(api, devis.id)).note, 'note rétablie').toBe(NOTE0)
    const pub = await lireJson(await donneesPubliques(api, lien.token), 'charge publique')
    expect(pub.note_client).toBe(NOTE0)
    expect(plat(await pdfTexte(api, devis.id))).toContain(plat(NOTE0))
    await voirListe(page, context, devis.reference)
  } finally {
    await nettoyer(api, { devis: [devis.id], leads: [lead.id] })
  }
})

etape('P7.4', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  await assurerSessionPage(page)
  await assurerCommercial(page.request)
  const api = page.request
  const com = await contexte(testInfo, COMMERCIAL)
  const p = await produits(api, 'A')
  // Le lead d'« autrui » est posé sur l'administrateur : sans propriétaire explicite, l'attribution automatique des leads le
  // donnerait au Commercial de test (seul commercial de la société) et le devis serait légitimement dans sa portée.
  const moi = (await lireJson(await api.get(`${API}/auth/me/`, T), 'session')).id
  const lead = await creerLead(api, 'p74 autrui', { owner: moi })
  const autrui = await creerDevis(api, p, lead)
  const leadC = await creerLead(com, 'p74 propre')
  const propre = await creerDevis(com, p, leadC)
  try {
    // Hors portée : liste vide, 404 au détail et au PATCH, prix inchangé.
    const liste = await lireJson(await com.get(`${API}/ventes/devis-lignes/?page_size=100`, T), 'lignes du Commercial')
    const lignes = listeDe(liste)
    const idsAutrui = new Set(autrui.lignes.map((l) => l.id))
    expect(lignes.filter((l) => idsAutrui.has(l.id)), 'aucune ligne d\'autrui').toEqual([])
    // Tout ce qu'il voit appartient à SES devis (ceux de sa liste, auteur = lui) ; ses lignes propres y sont.
    const sesDevis = new Set(listeDe(await lireJson(await com.get(`${API}/ventes/devis/?page_size=200`, T), 'devis du Commercial')).map((d) => d.id))
    expect(sesDevis.has(autrui.id), 'le devis d\'autrui n\'est pas dans sa liste').toBe(false)
    expect(lignes.length, 'au moins ses propres lignes').toBeGreaterThanOrEqual(propre.lignes.length)
    expect(lignes.every((l) => sesDevis.has(l.devis)), '/devis-lignes/ ne montre que les lignes de SES devis').toBe(true)
    const cible = autrui.lignes.find((l) => /Forfait/.test(l.designation))
    expect((await com.get(`${API}/ventes/devis-lignes/${cible.id}/`, T)).status()).toBe(404)
    const patch = await com.patch(`${API}/ventes/devis-lignes/${cible.id}/`, { ...T, data: { prix_unitaire: '1.00' } })
    expect(patch.status(), 'PATCH hors portée').toBe(404)
    expect((await com.get(`${API}/ventes/devis/${autrui.id}/`, T)).status(), 'devis hors portée').toBe(404)
    // PERSISTANCE : le prix de la ligne d'autrui n'a pas bougé.
    const relu = (await lire(api, autrui.id)).lignes.find((l) => l.id === cible.id)
    expect(relu.prix_unitaire, 'prix inchangé').toBe(cible.prix_unitaire)
    // Ses propres lignes restent lisibles et modifiables.
    const sienne = propre.lignes.find((l) => /Panneau/.test(l.designation))
    expect((await com.get(`${API}/ventes/devis-lignes/${sienne.id}/`, T)).status()).toBe(200)
    const ok = await com.patch(`${API}/ventes/devis-lignes/${sienne.id}/`, { ...T, data: { designation: 'ADEV43 Panneau 710W (propre)' } })
    expect(ok.status(), 'ligne propre modifiable').toBe(200)
    await voirListe(page, context, autrui.reference)
  } finally {
    await nettoyer(api, { devis: [autrui.id], leads: [lead.id] })
    await nettoyer(com, { devis: [propre.id], leads: [leadC.id] })
    await com.dispose()
  }
})

etape('P7.4bis', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  await assurerSessionPage(page)
  const api = page.request
  const etranger = await contexte(testInfo, ADMIN_COMPLET) // société 43 : étrangère à la société 1
  const p = await produits(api, 'A')
  const lead = await creerLead(api, 'p74bis')
  const devis = await creerDevis(api, p, lead)
  try {
    const ligne = devis.lignes[0]
    const idsSoc1 = new Set(devis.lignes.map((l) => l.id))
    const get = await etranger.get(`${API}/ventes/devis/${devis.id}/`, T)
    expect(get.status(), 'GET devis d\'une autre société').toBe(404)
    const patch = await etranger.patch(`${API}/ventes/devis/${devis.id}/`, { ...T, data: { note: 'intrusion' } })
    expect(patch.status(), 'PATCH devis d\'une autre société').toBe(404)
    const lignesListe = await etranger.get(`${API}/ventes/devis-lignes/?devis=${devis.id}`, T)
    // La route liste n'a pas de filtre `?devis=` : elle répond 200 avec les seules lignes de LA société de l'appelant
    // (aucune du devis étranger) ou 404 — jamais une ligne de la société 1.
    const corps = lignesListe.status() === 200 ? listeDe(await lignesListe.json()) : []
    expect(lignesListe.status() === 404 || lignesListe.status() === 200, `lignes d'une autre société : HTTP ${lignesListe.status()}`).toBe(true)
    expect(corps.filter((l) => l.devis === devis.id || idsSoc1.has(l.id)), 'aucune ligne de la société 1').toEqual([])
    expect((await etranger.get(`${API}/ventes/devis-lignes/${ligne.id}/`, T)).status(), 'ligne d\'une autre société').toBe(404)
    expect((await etranger.patch(`${API}/ventes/devis-lignes/${ligne.id}/`, { ...T, data: { prix_unitaire: '1.00' } })).status()).toBe(404)
    expect((await etranger.get(`${API}/ventes/devis/${devis.id}/proposal/`, T)).status(), '/proposal d\'une autre société').toBe(404)
    // PERSISTANCE : rien n'a bougé côté société 1.
    const relu = await lire(api, devis.id)
    expect(relu.note ?? '').not.toBe('intrusion')
    expect(relu.lignes[0].prix_unitaire).toBe(ligne.prix_unitaire)
    await voirListe(page, context, devis.reference)
  } finally {
    await nettoyer(api, { devis: [devis.id], leads: [lead.id] })
    await etranger.dispose()
  }
})

etape('P4.2', ['ADEV43'], async ({ page, context, testInfo }) => {
  testInfo.setTimeout(600_000)
  await assurerSessionPage(page)
  const api = page.request
  const p = await produits(api, 'A')
  const lead = await creerLead(api, 'p42')
  const devis = await creerDevis(api, p, lead, { forfait: false, note: '' })
  let copie = null
  try {
    await envoyer(api, devis.id)
    copie = await lireJson(await api.post(`${API}/ventes/devis/${devis.id}/dupliquer/`, T), 'duplication')
    const relu = await lire(api, copie.id)
    expect(relu.note ?? '', 'la note client de la copie est vide').toBe('')
    // Le marqueur de provenance vit au chatter de la copie, jamais dans le texte client.
    expect((await historique(api, copie.id)).some((h) => /Copie de/.test(h.body || '')), 'marqueur au chatter').toBe(true)
    // CLIENT : page publique (aperçu) et /proposal sans « [Copie de … ] ».
    const lien = await lienClient(api, copie.id)
    const pub = await lireJson(await donneesPubliques(api, lien.token_interne), 'charge publique de la copie')
    expect(`${pub.note_client || ''} ${pub.quote?.note_client || ''}`).not.toMatch(/Copie de/)
    expect(await pdfTexte(api, copie.id)).not.toMatch(/Copie de/)
    await voirListe(page, context, relu.reference)
  } finally {
    await nettoyer(api, { devis: [copie?.id, devis.id].filter(Boolean), leads: [lead.id] })
  }
})
