// Acceptation en direct — groupe ASAV (SAV) : écarts de la contre-visite
// (ASAV114, couvre ASAV104-113) et parcours J4 (ASAV99). Format : `_format.md`.
//
// Données PROPRES à chaque étape, posées par l'API (`page.request` = demo_admin,
// contexte dédié = demo_tech, rôle système Technicien) : un client, un produit à
// 5 000 MAD, un équipement posé à la date voulue, des tickets à la date
// d'ouverture voulue, un contrat — jamais les fiches démo, jamais la prod.
// Nettoyage best-effort (une facture émise reste : PROTECT).
//
// « Non couvert » : une étape dont la donnée ne peut pas être montée lève
// `nonCouvert(...)` : FAIL, raison en notes, elle ne couvre rien.
import { expect, test, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import {
  API_DJANGO, assurerSessionPage, connexionApi, isoDansJours, lireJson, listeDe, uniq, telephoneMobileUnique,
} from '../helpers.js'

const plage = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => `ASAV${a + i}`)
// Pile locale partagée et chargée : budget large par étape.
test.describe.configure({ timeout: 300_000 })
// Écran de bureau large : à 1280 px la barre d'actions de la fiche ticket déborde
// du panneau latéral (« Facturer » rogné, clic intercepté — constaté le 29/10).
const ECRAN = { width: 1920, height: 1080 }
// Pile chargée : une requête API peut dépasser 15 s.
test.use({ viewport: ECRAN, actionTimeout: 60_000 })
const etape = groupe('ASAV', [...plage(104, 114), 'ASAV99'])
// La session du storageState expire au fil d'une longue passe : rouverte par l'API.
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const SAV = `${API_DJANGO}/sav`
const INST = `${API_DJANGO}/installations`
const TECH = { username: 'demo_tech', password: 'Demo@2026!' }

const JPEG_1X1 = Buffer.from(
  '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////'
  + 'wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=',
  'base64')
// En-tête ISO-BMFF « ftypheic » : une photo iPhone HEIC (refusée par le serveur).
const HEIC = Buffer.concat([Buffer.from([0, 0, 0, 0x18]), Buffer.from('ftypheic'), Buffer.alloc(32)])

const nonCouvert = (raison) => { throw new Error(`non couvert : ${raison}`) }
const fr = (iso) => iso.split('-').reverse().join('/')
function isoMois(n) {
  const d = new Date()
  d.setMonth(d.getMonth() + n)
  const p = (x) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

// ── Montage ─────────────────────────────────────────────────────────────────
async function creerClient(request, t, tag = 'ACC SAV') {
  const c = await lireJson(await request.post(`${API_DJANGO}/crm/clients/`, {
    data: { nom: uniq(tag), prenom: 'Acceptation', email: `${uniq('acc.sav').toLowerCase().replace(/[^a-z0-9.]/g, '')}@example.test`, telephone: telephoneMobileUnique() },
  }), 'client')
  t.clients.push(c.id)
  return c
}

async function creerProduit(request, t, { garantieMois = 8, prix = '5000.00' } = {}) {
  const p = await lireJson(await request.post(`${API_DJANGO}/stock/produits/`, {
    data: { nom: uniq('ACC Onduleur'), prix_vente: prix, garantie_mois: garantieMois },
  }), 'produit')
  t.produits.push(p.id)
  return p
}

async function creerEquipement(request, t, { client, produit, datePose, installation }) {
  const data = { produit: produit.id, numero_serie: uniq('ACC-SN').replace(/\s/g, ''), date_pose: datePose }
  if (installation) data.installation = installation
  else data.client_vente = client.id
  const e = await lireJson(await request.post(`${SAV}/equipements/`, { data }), 'équipement')
  t.equipements.push(e.id)
  return e
}

async function creerTicket(request, t, corps) {
  const tk = await lireJson(await request.post(`${SAV}/tickets/`, {
    data: { type: 'correctif', priorite: 'normale', description: uniq('ACC panne'), ...corps },
  }), 'ticket')
  t.tickets.push(tk.id)
  return tk
}

async function ajouterPiece(request, ticketId, produitId) {
  await lireJson(await request.post(`${SAV}/tickets/${ticketId}/pieces/`, {
    data: { produit: produitId, quantite: '1' },
  }), 'pièce consommée')
}

async function lireTicket(request, id) {
  return lireJson(await request.get(`${SAV}/tickets/${id}/`), `ticket ${id}`)
}

async function prixLignesFacture(request, factureId) {
  const f = await lireJson(await request.get(`${API_DJANGO}/ventes/factures/${factureId}/`), 'facture')
  return { facture: f, prix: (f.lignes ?? []).map((l) => Number(l.prix_unitaire)) }
}

// Contexte API dédié connecté en demo_tech (Technicien).
async function apiTechnicien(baseURL) {
  const api = await pwRequest.newContext({ baseURL })
  await connexionApi(api, TECH)
  const me = await lireJson(await api.get(`${API_DJANGO}/auth/me/`), 'profil technicien')
  await api.post(`${INST}/gps-consentements/mon-consentement/accepter/`)
  return { api, id: me.id }
}

// Chantier + intervention TERMINÉE aujourd'hui (préparation confirmée, photos des
// créneaux obligatoires, puis « Terminée ») : un ticket ouvert ensuite sur ce
// chantier est une récidive non facturable (détection serveur XFSM15).
async function chantierAvecInterventionTerminee(request, tech, t, client) {
  const inst = await lireJson(await request.post(`${INST}/chantiers/`, {
    data: { client: client.id, site_ville: 'Casablanca' },
  }), 'chantier')
  t.chantiers.push(inst.id)
  const iv = await lireJson(await request.post(`${INST}/interventions/`, {
    data: { installation: inst.id, type_intervention: 'depannage', date_prevue: isoDansJours(0), technicien: tech.id },
  }), 'intervention')
  await lireJson(await tech.api.post(`${INST}/interventions/${iv.id}/confirmer-charge/`, { data: {} }), 'tout est chargé')
  const photos = await lireJson(await request.get(`${INST}/interventions/${iv.id}/photos/`), 'créneaux photo')
  const creneaux = Object.values(photos.groupes ?? {}).flat().filter((s) => s.obligatoire)
  for (const s of creneaux) {
    await lireJson(await request.post(`${INST}/interventions/${iv.id}/ajouter-photo/`, {
      multipart: { slot: s.cle, phase: s.phase, file: { name: `${s.cle}.jpg`, mimeType: 'image/jpeg', buffer: JPEG_1X1 } },
    }), `photo ${s.cle}`)
  }
  const fin = await request.patch(`${INST}/interventions/${iv.id}/`, {
    data: { statut: 'terminee', date_realisee: isoDansJours(0) },
  })
  if (!fin.ok()) nonCouvert(`intervention « Terminée » refusée (${fin.status()} ${(await fin.text()).slice(0, 200)})`)
  return inst
}

// Lead → devis d'une ligne → accepté → chantier (patron `chantiers.spec.js`).
async function chantierDepuisDevis(request, t) {
  const produit = await creerProduit(request, t, { prix: '1000.00' })
  const lead = await lireJson(await request.post(`${API_DJANGO}/crm/leads/`, {
    data: {
      nom: uniq('ACC SAV Reception'), ville: 'Casablanca', telephone: telephoneMobileUnique(),
      type_installation: 'residentiel', facture_hiver: '800',
    },
  }), 'lead')
  const devis = await lireJson(await request.post(`${API_DJANGO}/ventes/devis/`, {
    data: { lead: lead.id, taux_tva: '20.00', mode_installation: 'residentiel' },
  }), 'devis')
  await lireJson(await request.post(`${API_DJANGO}/ventes/devis/${devis.id}/replace-lines/`, {
    data: {
      lignes: [{
        produit: produit.id, designation: produit.nom, quantite: '2.00', prix_unitaire: '1000.00',
        remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0,
      }],
    },
  }), 'lignes du devis')
  await lireJson(await request.post(`${API_DJANGO}/ventes/devis/${devis.id}/accepter/`, {
    data: { nom: 'Client ACC SAV' },
  }), 'acceptation du devis')
  const inst = await lireJson(await request.post(`${INST}/chantiers/creer-depuis-devis/`, {
    data: { devis: devis.id },
  }), 'chantier du devis')
  t.chantiers.push(inst.id)
  const relu = await lireJson(await request.get(`${INST}/chantiers/${inst.id}/`), 'chantier relu')
  if (!relu.client) nonCouvert('chantier du devis sans client résolu')
  return relu
}

export async function nettoyer(request, t) {
  const sup = (url) => request.delete(url).catch(() => null)
  for (const id of t.tickets) await sup(`${SAV}/tickets/${id}/`)
  for (const id of t.contrats) await sup(`${SAV}/contrats-maintenance/${id}/`)
  for (const id of t.equipements) await sup(`${SAV}/equipements/${id}/`)
  for (const id of t.chantiers) await sup(`${INST}/chantiers/${id}/`)
  for (const id of t.produits) await sup(`${API_DJANGO}/stock/produits/${id}/`)
}

// Données laissées en place (fiches « ACC … » de la démo locale) : les supprimer
// pendant que l'écran est ouvert déclenche des 404 de rechargement (oracle 2)
// qui ne disent rien du produit. `nettoyer` reste disponible pour un ménage manuel.
async function avecDonnees(_request, corps) {
  const t = { clients: [], produits: [], equipements: [], tickets: [], contrats: [], chantiers: [] }
  await corps(t)
}

// Fiche ticket ouverte par lien profond (`/sav?id=<id>`, useDeepLinkId).
async function ouvrirTicket(p, id) {
  await p.goto(`/sav?id=${id}`)
  await ficheVisible(p)
}

const sectionSuivi = (p) => p.locator('details').filter({ hasText: 'Suivi client & SLA' }).first()

// Fiche ticket (panneau latéral « Ticket SAV — SAV-… » sur grand écran).
const ficheVisible = (p) => expect(p.getByText(/Ticket SAV — SAV-/).first()).toBeVisible({ timeout: 30_000 })

// ════════════════════════════════════════════════════════════════════════════
// ASAV114 — écarts de la contre-visite (C-ASAV-VER-001 à 010)
// ════════════════════════════════════════════════════════════════════════════

etape('P114.1', ['ASAV104', 'ASAV114'], async ({ page, context, suivi, testInfo }) => {
  // (1) Technicien : « Facturer » le ticket récidive (403, aucun « Facturer quand
  // même »), puis POST `facturer` override → 403 ; aucune facture.
  const baseURL = testInfo.project.use.baseURL
  const tech = await apiTechnicien(baseURL)
  try {
    await avecDonnees(page.request, async (t) => {
      const client = await creerClient(page.request, t)
      const produit = await creerProduit(page.request, t)
      const inst = await chantierAvecInterventionTerminee(page.request, tech, t, client)
      const tk = await creerTicket(page.request, t, {
        client: client.id, installation: inst.id, technicien_responsable: tech.id,
      })
      expect(tk.est_recidive, 'récidive détectée par le serveur').toBe(true)
      expect(tk.non_facturable, 'non facturable par défaut').toBe(true)
      await ajouterPiece(page.request, tk.id, produit.id)

      const ctx = await context.browser().newContext({ baseURL, serviceWorkers: 'block', viewport: ECRAN })
      try {
        const p = suivi.surveiller(await ctx.newPage())
        await connexionApi(p.request, TECH)
        suivi.attendre(new RegExp(`/sav/tickets/${tk.id}/facturer/`), 403)
        await ouvrirTicket(p, tk.id)
        const bouton = p.getByRole('button', { name: /^Facturer$/ })
        await expect(bouton).toBeVisible()
        const rep = p.waitForResponse((r) => r.url().includes(`/sav/tickets/${tk.id}/facturer/`), { timeout: 120_000 })
        // La barre d'actions de la fiche déborde du panneau (bouton rogné, clic souris
        // intercepté) : activé au clavier, comme un utilisateur au Tab.
        await bouton.press('Enter')
        expect((await rep).status(), 'Facturer en Technicien').toBe(403)
        await expect(p.getByText(/override responsable requis/i).first()).toBeVisible()
        await expect(p.getByRole('button', { name: /Facturer quand même/ })).toHaveCount(0)
        const force = await p.request.post(`${SAV}/tickets/${tk.id}/facturer/`, { data: { override: true } })
        expect(force.status(), 'POST facturer override en Technicien').toBe(403)
        await p.reload()
        await ficheVisible(p)
        await expect(p.getByText('Facture générée')).toHaveCount(0)
      } finally { await ctx.close() }
      const relu = await lireTicket(page.request, tk.id)
      expect(relu.facture_id_ext, 'aucune facture').toBeNull()
    })
  } finally { await tech.api.dispose() }
})

etape('P114.2', ['ASAV105', 'ASAV114'], async ({ page }) => {
  // (2) Contrat créé aujourd'hui, ticket ouvert il y a 60 j : facture 5 000 MAD.
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const produit = await creerProduit(page.request, t)
    const eq = await creerEquipement(page.request, t, { client, produit, datePose: isoMois(-30) })
    const tk = await creerTicket(page.request, t, {
      client: client.id, equipement: eq.id, date_ouverture: isoDansJours(-60),
    })
    await ajouterPiece(page.request, tk.id, produit.id)
    const c = await lireJson(await page.request.post(`${SAV}/contrats-maintenance/`, {
      data: { client: client.id, date_debut: isoDansJours(0), duree_mois: 12, actif: true },
    }), 'contrat du jour')
    t.contrats.push(c.id)
    await ouvrirTicket(page, tk.id)
    const rep = page.waitForResponse((r) => r.url().includes(`/sav/tickets/${tk.id}/facturer/`), { timeout: 120_000 })
    await page.getByRole('button', { name: /^Facturer$/ }).press('Enter')
    const corps = await (await rep).json()
    expect(corps.couverture, 'contrat postérieur à l’ouverture : facturable').toBe('facturable')
    await page.reload()
    await ficheVisible(page)
    await expect(page.getByText('Facture générée')).toBeVisible()
    const { prix } = await prixLignesFacture(page.request, (await lireTicket(page.request, tk.id)).facture_id_ext)
    expect(prix, 'facture au prix catalogue').toEqual([5000])
  })
})

etape('P114.3', ['ASAV106', 'ASAV114'], async ({ page, context, suivi, testInfo }) => {
  // (3) Signalement public par QR : photo HEIC → 400 sous le champ ; renvoi sans
  // photo → NOUVELLE référence (jamais celle du ticket de J-30 au même texte).
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const produit = await creerProduit(page.request, t)
    const eq = await creerEquipement(page.request, t, { client, produit, datePose: isoMois(-6) })
    const texte = uniq('Onduleur bip')
    const ancien = await creerTicket(page.request, t, {
      client: client.id, equipement: eq.id, description: texte, date_ouverture: isoDansJours(-30),
    })
    const qr = await lireJson(await page.request.get(`${SAV}/equipements/${eq.id}/partage-qr/`), 'lien QR')
    const chemin = new URL(qr.url).pathname
    const prive = await context.browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block', viewport: ECRAN })
    try {
      const p = suivi.surveiller(await prive.newPage())
      suivi.attendre(/\/public\/sav\/equipement\/[^/]+\/signaler\//, 400)
      await p.goto(chemin)
      await p.locator('#es-description').fill(texte)
      await p.locator('#es-photo').setInputFiles({ name: 'photo.heic', mimeType: 'image/heic', buffer: HEIC })
      const r1 = p.waitForResponse((r) => /\/signaler\/$/.test(new URL(r.url()).pathname), { timeout: 120_000 })
      await p.getByRole('button', { name: /Envoyer le signalement/ }).click()
      expect((await r1).status(), 'HEIC refusée').toBe(400)
      await expect(p.getByRole('alert').first()).toBeVisible()
      await p.locator('#es-photo').setInputFiles([])
      const r2 = p.waitForResponse((r) => /\/signaler\/$/.test(new URL(r.url()).pathname), { timeout: 120_000 })
      await p.getByRole('button', { name: /Envoyer le signalement/ }).click()
      const rep2 = await r2
      expect(rep2.status(), 'renvoi sans photo').toBe(201)
      const ref = (await rep2.json()).reference
      expect(ref, 'nouvelle référence').toBeTruthy()
      expect(ref).not.toBe(ancien.reference)
      await expect(p.getByText(ref).first()).toBeVisible()
    } finally { await prive.close() }
    const tickets = listeDe(await lireJson(
      await page.request.get(`${SAV}/tickets/?equipement=${eq.id}&page_size=50`), 'tickets de l’équipement'))
    for (const x of tickets) if (!t.tickets.includes(x.id)) t.tickets.push(x.id)
    expect(tickets.length, 'ancien + nouveau ticket').toBe(2)
  })
})

etape('P114.4', ['ASAV107', 'ASAV114'], async ({ page }) => {
  // (4) Registre des garanties : équipement posé il y a 300 j, constructeur 8 mois
  // (échue) — badge NON expiré, fin = garantie légale.
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const produit = await creerProduit(page.request, t, { garantieMois: 8 })
    const eq = await creerEquipement(page.request, t, { client, produit, datePose: isoDansJours(-300) })
    expect(eq.date_fin_garantie < isoDansJours(0), 'garantie constructeur échue').toBeTruthy()
    const reg = await lireJson(await page.request.get(`${SAV}/equipements/registre-garanties/`), 'registre')
    const item = (reg.parcs ?? []).flatMap((x) => x.items ?? []).find((i) => i.equipement === eq.id)
    expect(item, 'équipement au registre').toBeTruthy()
    expect(item.date_fin_garantie_effective).toBe(eq.date_fin_garantie_legale)
    expect(item.statut_garantie).not.toBe('expiree')
    await page.goto('/equipements')
    await page.getByRole('button', { name: /Registre des garanties/ }).click()
    const ligne = page.getByRole('row').filter({ hasText: eq.numero_serie })
    await expect(ligne).toBeVisible({ timeout: 30_000 })
    await expect(ligne).toContainText(fr(eq.date_fin_garantie_legale))
    await expect(ligne).not.toContainText('Expirée')
  })
})

etape('P114.5', ['ASAV108', 'ASAV114'], async ({ page }) => {
  // (5) Deux tickets correctifs sous un contrat de quota 1 : note « quota » sur
  // le 2e seulement.
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const c = await lireJson(await page.request.post(`${SAV}/contrats-maintenance/`, {
      data: { client: client.id, date_debut: isoDansJours(-30), duree_mois: 12, actif: true, deplacements_inclus_an: 1 },
    }), 'contrat quota 1')
    t.contrats.push(c.id)
    const t1 = await creerTicket(page.request, t, { client: client.id, description: uniq('Premier déplacement') })
    const t2 = await creerTicket(page.request, t, { client: client.id, description: uniq('Second déplacement') })
    const quota = async (id) => (await lireJson(await page.request.get(`${SAV}/tickets/${id}/historique/`), 'historique'))
      .filter((a) => /quota/i.test(a.body || ''))
    expect(await quota(t1.id), '1er ticket : aucune note quota').toEqual([])
    const n2 = await quota(t2.id)
    expect(n2.length, '2e ticket : une note quota').toBe(1)
    expect(n2[0].body).toMatch(/déjà atteint/)
    await ouvrirTicket(page, t2.id)
    await expect(page.getByText(/déjà atteint/).first()).toBeVisible({ timeout: 30_000 })
  })
})

etape('P114.6', ['ASAV109', 'ASAV114'], async ({ page }) => {
  // (6) Ticket mis en attente client puis annulé : la pause est close.
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const tk = await creerTicket(page.request, t, { client: client.id })
    await ouvrirTicket(page, tk.id)
    await expect(sectionSuivi(page)).toHaveAttribute('open', '')
    await page.getByRole('button', { name: 'Mettre en attente client' }).click()
    await expect(page.getByRole('button', { name: 'Reprendre après attente client' })).toBeVisible()
    expect((await lireTicket(page.request, tk.id)).en_attente_client).toBe(true)
    await lireJson(await page.request.post(`${SAV}/tickets/${tk.id}/annuler/`, { data: { motif: 'Acceptation ASAV114' } }), 'annulation')
    const relu = await lireTicket(page.request, tk.id)
    expect(relu.annule).toBe(true)
    expect(relu.en_attente_client, 'pause close').toBe(false)
    expect(relu.attente_depuis).toBeNull()
    await page.reload()
    await ficheVisible(page)
    await expect(page.getByRole('button', { name: 'Reprendre après attente client' })).toHaveCount(0)
  })
})

etape('P114.7', ['ASAV110', 'ASAV114'], async ({ page }) => {
  // (7) Fiche d'un ticket résolu : aucun « Mettre en attente client » ; POST 409.
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const tk = await creerTicket(page.request, t, { client: client.id })
    await lireJson(await page.request.post(`${SAV}/tickets/${tk.id}/demarrer/`, { data: {} }), 'démarrer')
    await lireJson(await page.request.post(`${SAV}/tickets/${tk.id}/resoudre/`, { data: {} }), 'résoudre')
    await ouvrirTicket(page, tk.id)
    // Section « Suivi client & SLA » OUVERTE (sinon l'absence du bouton serait creuse).
    await expect(sectionSuivi(page)).toHaveAttribute('open', '')
    await expect(sectionSuivi(page).getByRole('button').first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Mettre en attente client' })).toHaveCount(0)
    const r = await page.request.post(`${SAV}/tickets/${tk.id}/attente-client/`, { data: {} })
    expect(r.status(), 'attente-client sur résolu').toBe(409)
    expect((await lireTicket(page.request, tk.id)).en_attente_client).toBe(false)
  })
})

etape('P114.8', ['ASAV111', 'ASAV114'], async ({ page }) => {
  // (8) Ticket ouvert sous garantie (légale), échue depuis : « Garantie jusqu'au … ».
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const produit = await creerProduit(page.request, t, { garantieMois: 8 })
    const eq = await creerEquipement(page.request, t, { client, produit, datePose: isoMois(-14) })
    const tk = await creerTicket(page.request, t, {
      client: client.id, equipement: eq.id, date_ouverture: isoDansJours(-120),
    })
    expect(tk.sous_garantie_effectif).toBe('oui')
    const fin = tk.equipement_fin_garantie_effective
    expect(fin < isoDansJours(0), 'garantie échue depuis l’ouverture').toBeTruthy()
    await ouvrirTicket(page, tk.id)
    await expect(page.getByText(`Garantie jusqu'au ${fr(fin)} (légale)`)).toBeVisible()
    await expect(page.getByText(/Garantie expirée le/)).toHaveCount(0)
    await page.reload()
    await expect(page.getByText(`Garantie jusqu'au ${fr(fin)} (légale)`)).toBeVisible({ timeout: 30_000 })
  })
})

etape('P114.9', ['ASAV112', 'ASAV114'], async ({ page }) => {
  // (9) Paramètres SAV › Service client : aucun interrupteur heures ouvrées (il
  // ne vit que dans l'onglet SLA).
  await page.goto('/sav/parametres')
  await page.getByRole('tab', { name: 'Service client' }).click()
  await expect(page.getByRole('tabpanel')).toBeVisible()
  await expect(page.getByRole('tabpanel').getByText('Décompter le SLA en heures ouvrées')).toHaveCount(0)
  await page.getByRole('tab', { name: 'SLA / Automatisation' }).click()
  await expect(page.getByRole('tabpanel').getByLabel('Décompter le SLA en heures ouvrées')).toHaveCount(1)
  await page.reload()
  await page.getByRole('tab', { name: 'Service client' }).click()
  await expect(page.getByRole('tabpanel').getByText('Décompter le SLA en heures ouvrées')).toHaveCount(0)
})

etape('P114.10', ['ASAV113', 'ASAV114'], async ({ page }) => {
  // (10) Réception d'un chantier d'un client au contrat échu (12 mois débuté il y
  // a 14 mois) : une activité « Proposer le contrat d'entretien ».
  await avecDonnees(page.request, async (t) => {
    // Chantier issu d'un devis accepté (le commercial = créateur du devis reçoit
    // l'activité) ; le contrat échu est posé sur le client résolu du lead.
    const inst = await chantierDepuisDevis(page.request, t)
    const c = await lireJson(await page.request.post(`${SAV}/contrats-maintenance/`, {
      data: {
        client: inst.client, date_debut: isoMois(-14), duree_mois: 12, actif: true,
        facturation_active: true, prix: '1200.00',
      },
    }), 'contrat échu')
    t.contrats.push(c.id)
    expect(c.expire, 'contrat échu au-delà de la grâce').toBe(true)
    const client = { id: inst.client }
    for (const statut of ['materiel_commande', 'planifie', 'en_cours', 'installe', 'receptionne']) {
      const pas = await page.request.patch(`${INST}/chantiers/${inst.id}/`, { data: { statut } })
      if (!pas.ok()) nonCouvert(`passage « ${statut} » refusé (${pas.status()} ${(await pas.text()).slice(0, 200)})`)
    }
    const acts = listeDe(await lireJson(await page.request.get(
      `${API_DJANGO}/records/activities/?model=crm.client&id=${client.id}`), 'activités du client'))
    const prop = acts.filter((a) => /Proposer le contrat d'entretien/.test(a.summary || ''))
    expect(prop.length, 'une activité « Proposer le contrat d’entretien »').toBe(1)
  })
})

// ════════════════════════════════════════════════════════════════════════════
// ASAV99 — parcours J4 parc → ticket → SLA → contrat → facture → page publique
// → alarmes → production → réglages (acceptation de groupe ASAV). Les étapes
// suspendues (remplacement d'onduleur ASAV9, quotas > 50 lignes) ne sont pas
// jouées : voir le rapport de l'orchestrateur.
// ════════════════════════════════════════════════════════════════════════════

// Réglages SLA société : lus, modifiés le temps de l'étape, TOUJOURS restaurés.
async function avecReglagesSla(request, modifs, corps) {
  const avant = await lireJson(await request.get(`${SAV}/sla-settings/`), 'réglages SLA')
  try {
    await lireJson(await request.post(`${SAV}/sla-settings/`, { data: modifs }), 'réglages SLA modifiés')
    await corps(avant)
  } finally {
    const retour = Object.fromEntries(Object.keys(modifs).map((k) => [k, avant[k]]))
    await request.post(`${SAV}/sla-settings/`, { data: retour }).catch(() => null)
  }
}

etape('P99.1', ['ASAV99'], async ({ page }) => {
  // (1) Parc : la note d'un équipement corrigée — fin de garantie inchangée.
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const produit = await creerProduit(page.request, t, { garantieMois: 24 })
    const eq = await creerEquipement(page.request, t, { client, produit, datePose: isoMois(-3) })
    const note = uniq('Note parc ASAV99')
    const maj = await lireJson(await page.request.patch(`${SAV}/equipements/${eq.id}/`, { data: { note } }), 'note')
    expect(maj.note).toBe(note)
    expect(maj.date_fin_garantie, 'fin de garantie inchangée').toBe(eq.date_fin_garantie)
    expect(maj.date_fin_garantie_effective).toBe(eq.date_fin_garantie_effective)
    await page.goto(`/equipements?id=${eq.id}`)
    await expect(page.getByText(eq.numero_serie).first()).toBeVisible({ timeout: 30_000 })
    await page.reload()
    await expect(page.getByText(eq.numero_serie).first()).toBeVisible({ timeout: 30_000 })
    const relu = await lireJson(await page.request.get(`${SAV}/equipements/${eq.id}/`), 'équipement relu')
    expect(relu.note).toBe(note)
    expect(relu.date_fin_garantie).toBe(eq.date_fin_garantie)
  })
})

etape('P99.2', ['ASAV99'], async ({ page }) => {
  // (2) Ticket : priorité urgente ⇒ échéance recalculée + ligne d'historique ;
  // attente client ; résolu (date posée par le serveur) ; rouvert.
  await avecReglagesSla(page.request, {
    sla_par_priorite: { urgente: { response: 0, resolution: 1 } }, sla_resolution_days: 7,
  }, async () => {
    await avecDonnees(page.request, async (t) => {
      const client = await creerClient(page.request, t)
      const tk = await creerTicket(page.request, t, { client: client.id })
      const urg = await lireJson(await page.request.patch(`${SAV}/tickets/${tk.id}/`, {
        data: { priorite: 'urgente' },
      }), 'priorité urgente')
      expect(urg.sla_due_at, 'échéance urgente recalculée').toBe(isoDansJours(1))
      const histo = await lireJson(await page.request.get(`${SAV}/tickets/${tk.id}/historique/`), 'historique')
      expect(histo.some((a) => a.field === 'priorite'), 'ligne d’historique « priorité »').toBe(true)
      await lireJson(await page.request.post(`${SAV}/tickets/${tk.id}/attente-client/`, { data: {} }), 'attente client')
      await lireJson(await page.request.post(`${SAV}/tickets/${tk.id}/reprendre/`, { data: {} }), 'reprise')
      await lireJson(await page.request.post(`${SAV}/tickets/${tk.id}/demarrer/`, { data: {} }), 'démarrer')
      const res = await lireJson(await page.request.post(`${SAV}/tickets/${tk.id}/resoudre/`, { data: {} }), 'résoudre')
      expect(res.date_resolution, 'date de résolution posée par le serveur').toBe(isoDansJours(0))
      const rouvert = await lireJson(await page.request.post(`${SAV}/tickets/${tk.id}/reouvrir/`, { data: {} }), 'rouvrir')
      expect(rouvert.statut).toBe('nouveau')
      expect(rouvert.date_resolution, 'date de résolution vidée').toBeNull()
      expect(rouvert.reopen_count).toBe(1)
      await ouvrirTicket(page, tk.id)
      await page.reload()
      await ficheVisible(page)
      const relu = await lireTicket(page.request, tk.id)
      expect(relu.priorite).toBe('urgente')
      expect(relu.statut).toBe('nouveau')
    })
  })
})

etape('P99.3', ['ASAV99'], async ({ page, testInfo }) => {
  // (3) Technicien : édition en masse et fusion sur le ticket d'un AUTRE — refusées.
  const tech = await apiTechnicien(testInfo.project.use.baseURL)
  try {
    await avecDonnees(page.request, async (t) => {
      const client = await creerClient(page.request, t)
      const autre = await creerTicket(page.request, t, { client: client.id })
      const sien = await creerTicket(page.request, t, { client: client.id, technicien_responsable: tech.id })
      const lot = await tech.api.post(`${SAV}/tickets/actions-groupees/`, {
        data: { ids: [autre.id], operation: 'priorite', priorite: 'urgente' },
      })
      if (lot.ok()) expect((await lot.json()).nb_traites, 'aucun ticket hors portée traité').toBe(0)
      else expect([403, 404]).toContain(lot.status())
      const fusion = await tech.api.post(`${SAV}/tickets/${sien.id}/fusionner/`, { data: { doublon_id: autre.id } })
      expect([403, 404], 'fusion hors portée refusée').toContain(fusion.status())
      const relu = await lireTicket(page.request, autre.id)
      expect(relu.priorite).toBe('normale')
      expect(relu.annule).toBe(false)
    })
  } finally { await tech.api.dispose() }
})

etape('P99.4', ['ASAV99'], async ({ page }) => {
  // (4) Contrat quota 1 : 1er ticket couvert facturé 0 MAD, 2e au prix ; un seul
  // bouton « Facturer » sur la fiche.
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const produit = await creerProduit(page.request, t)
    const c = await lireJson(await page.request.post(`${SAV}/contrats-maintenance/`, {
      data: { client: client.id, date_debut: isoDansJours(-30), duree_mois: 12, actif: true, deplacements_inclus_an: 1 },
    }), 'contrat quota 1')
    t.contrats.push(c.id)
    const prix = []
    for (let i = 0; i < 2; i += 1) {
      const tk = await creerTicket(page.request, t, { client: client.id })
      await ajouterPiece(page.request, tk.id, produit.id)
      if (i === 0) {
        await ouvrirTicket(page, tk.id)
        await expect(page.getByRole('button', { name: /^Facturer$/ }), 'un seul bouton « Facturer »').toHaveCount(1)
      }
      const f = await lireJson(await page.request.post(`${SAV}/tickets/${tk.id}/facturer/`, { data: {} }), `facturer ${i + 1}`)
      prix.push((await prixLignesFacture(page.request, f.facture_id)).prix)
    }
    expect(prix[0], '1er ticket couvert : 0 MAD').toEqual([0])
    expect(prix[1], '2e ticket : quota épuisé, au prix').toEqual([5000])
  })
})

etape('P99.6', ['ASAV99'], async ({ page, context, suivi, testInfo }) => {
  // (6) `/suivi/<token>` d'un ticket annulé, en navigation privée : « Annulé ».
  // Signalement QR avec photo HEIC : refusé sous le champ, AUCUN ticket créé.
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const produit = await creerProduit(page.request, t)
    const eq = await creerEquipement(page.request, t, { client, produit, datePose: isoMois(-2) })
    const tk = await creerTicket(page.request, t, { client: client.id, equipement: eq.id })
    const lien = await lireJson(await page.request.get(`${SAV}/tickets/${tk.id}/lien-client/`), 'lien de suivi')
    await lireJson(await page.request.post(`${SAV}/tickets/${tk.id}/annuler/`, { data: { motif: 'ASAV99' } }), 'annulation')
    const qr = await lireJson(await page.request.get(`${SAV}/equipements/${eq.id}/partage-qr/`), 'lien QR')
    const prive = await context.browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block' })
    try {
      const p = suivi.surveiller(await prive.newPage())
      await p.goto(new URL(lien.url).pathname)
      await expect(p.getByRole('status').filter({ hasText: 'Annulé' })).toBeVisible({ timeout: 30_000 })
      suivi.attendre(/\/public\/sav\/equipement\/[^/]+\/signaler\//, 400)
      await p.goto(new URL(qr.url).pathname)
      await p.locator('#es-description').fill(uniq('Panne QR ASAV99'))
      await p.locator('#es-photo').setInputFiles({ name: 'photo.heic', mimeType: 'image/heic', buffer: HEIC })
      await p.getByRole('button', { name: /Envoyer le signalement/ }).click()
      await expect(p.getByRole('alert').first()).toBeVisible({ timeout: 30_000 })
    } finally { await prive.close() }
    // `ouvert=tous` : la file par défaut cache les tickets annulés.
    const ids = listeDe(await lireJson(await page.request.get(
      `${SAV}/tickets/?equipement=${eq.id}&ouvert=tous&page_size=50`), 'tickets de l’équipement')).map((x) => x.id)
    expect(ids, 'aucun ticket créé par le refus').toEqual([tk.id])
  })
})

etape('P99.7', ['ASAV99'], async ({ page }) => {
  // (7) Alarmes : créée, acquittée, escaladée (ticket lié) ; visible à l'écran.
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const produit = await creerProduit(page.request, t)
    const eq = await creerEquipement(page.request, t, { client, produit, datePose: isoMois(-2) })
    const code = uniq('ACC-E').replace(/\s/g, '')
    const a = await lireJson(await page.request.post(`${SAV}/alarmes-onduleur/`, {
      data: { equipement: eq.id, code, gravite: 'critique', libelle: 'Défaut isolement ASAV99' },
    }), 'alarme')
    const ack = await lireJson(await page.request.post(`${SAV}/alarmes-onduleur/${a.id}/acquitter/`, { data: {} }), 'acquitter')
    expect(ack.statut).toBe('acquittee')
    const esc = await lireJson(await page.request.post(`${SAV}/alarmes-onduleur/${a.id}/escalader/`, { data: {} }), 'escalader')
    expect(esc.statut, 'escalade aboutie').toBe('escaladee')
    expect(esc.ticket, 'ticket créé par l’escalade').toBeTruthy()
    t.tickets.push(esc.ticket)
    await page.goto('/sav/alarmes')
    await expect(page.getByText(code).first()).toBeVisible({ timeout: 30_000 })
    await page.request.delete(`${SAV}/alarmes-onduleur/${a.id}/`).catch(() => null)
  })
})

etape('P99.8', ['ASAV99'], async ({ page }) => {
  // (8) Production : le même relevé saisi deux fois — le second refusé.
  await avecDonnees(page.request, async (t) => {
    const client = await creerClient(page.request, t)
    const inst = await lireJson(await page.request.post(`${INST}/chantiers/`, {
      data: { client: client.id, site_ville: 'Casablanca' },
    }), 'chantier')
    t.chantiers.push(inst.id)
    const releve = { installation: inst.id, date: isoDansJours(-1), period_days: 1, energy_kwh: '18.50' }
    const r1 = await lireJson(await page.request.post(`${API_DJANGO}/monitoring/readings/`, { data: releve }), '1er relevé')
    const r2 = await page.request.post(`${API_DJANGO}/monitoring/readings/`, { data: releve })
    await page.request.delete(`${API_DJANGO}/monitoring/readings/${r1.id}/`).catch(() => null)
    if (r2.ok()) await page.request.delete(`${API_DJANGO}/monitoring/readings/${(await r2.json()).id}/`).catch(() => null)
    expect([400, 409], 'second relevé identique refusé').toContain(r2.status())
    await page.goto('/production')
    await expect(page.getByRole('heading').first()).toBeVisible({ timeout: 30_000 })
  })
})

etape('P99.9', ['ASAV99'], async ({ page }) => {
  // (9) Paramètres SAV : SLA par priorité et auto-clôture enregistrés puis relus.
  await avecReglagesSla(page.request, {
    sla_par_priorite: { urgente: { response: 0, resolution: 2 } }, auto_cloture_jours: 9,
  }, async () => {
    await page.goto('/sav/parametres')
    await page.getByRole('tab', { name: 'SLA / Automatisation' }).click()
    await page.reload()
    await page.getByRole('tab', { name: 'SLA / Automatisation' }).click()
    await expect(page.getByRole('tabpanel')).toBeVisible()
    const relu = await lireJson(await page.request.get(`${SAV}/sla-settings/`), 'réglages relus')
    expect(relu.auto_cloture_jours).toBe(9)
    expect(relu.sla_par_priorite?.urgente?.resolution).toBe(2)
    await expect(page.getByRole('tabpanel').locator('input[value="9"]').first()).toBeVisible()
  })
})
