// Acceptation en direct — revue du module chantiers (groupe ACHT), parcours
// fondateur de bout en bout : l'admin prépare le matériel et les interventions,
// le technicien exécute sa journée (prépa, trajet, photos, séries, signature,
// retour dépôt), l'admin relit le résultat. Format : `_format.md`.
//
// Données PROPRES à chaque étape (jamais le chantier de démonstration, jamais
// une dépendance à une autre étape) : un fournisseur, un produit SANS stock
// rattaché à ce fournisseur, un lead, un devis d'UNE ligne de ce produit accepté,
// le chantier qui en découle (nomenclature gelée = manque certain) et une
// intervention « Pose » du jour assignée à demo_tech — tout posé par l'API
// (`page.request`, patron `adep.spec.js` / `installations.spec.js`) et nettoyé
// dans un `finally`.
//
// « Non couvert » : une étape dont la donnée ne peut pas être montée lève
// `nonCouvert(...)` : FAIL avec la raison en notes, elle ne couvre RIEN (jamais
// un PASS creux).
import { expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { aujourdHui } from './_enregistrement.js'
import {
  API_DJANGO, connexionApi, lireJson, listeDe, uniq, telephoneMobileUnique,
} from '../helpers.js'

const etape = groupe('ACHT', [
  'ACHT104', 'ACHT105', 'ACHT106', 'ACHT107', 'ACHT108', 'ACHT109', 'ACHT110',
])
const API = `${API_DJANGO}/installations`
const TECH = { username: 'demo_tech', password: 'Demo@2026!' }

// Un pixel JPEG valide (1×1, blanc).
const JPEG_1X1 = Buffer.from(
  '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////'
  + 'wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=',
  'base64')
const photo = (nom) => ({ name: nom, mimeType: 'image/jpeg', buffer: JPEG_1X1 })

const nonCouvert = (raison) => { throw new Error(`non couvert : ${raison}`) }

// Lecture best-effort (nettoyage) : jamais d'exception, `null` si la lecture échoue.
async function lireOuNull(request, url) {
  try {
    const r = await request.get(url)
    return r.ok() ? await r.json() : null
  } catch { return null }
}

// Id de demo_tech, lu par un contexte API dédié connecté en tant que lui (le
// projet s'exécute en demo_admin : la Pose doit être assignée au technicien).
async function idTechnicien(baseURL) {
  const api = await pwRequest.newContext({ baseURL })
  try {
    await connexionApi(api, TECH)
    return (await lireJson(await api.get(`${API_DJANGO}/auth/me/`), 'profil technicien')).id
  } finally { await api.dispose() }
}

// Monte les données de l'étape. `techId` (optionnel) = demo_tech : une
// intervention « Pose » du jour lui est assignée.
async function monterChantier(request, t, techId) {
  const fournisseur = await lireJson(await request.post(`${API_DJANGO}/stock/fournisseurs/`, {
    data: { nom: uniq('ACC Fournisseur') },
  }), 'fournisseur')
  t.fournisseur = fournisseur.id
  // Produit SANS mouvement de stock (stock 0) => manque certain ; sans catégorie =>
  // de nature à porter un n° de série (`serie_attendue`).
  const produit = await lireJson(await request.post(`${API_DJANGO}/stock/produits/`, {
    data: { nom: uniq('ACC Panneau'), prix_vente: '1000.00', fournisseur: fournisseur.id },
  }), 'produit sans stock')
  t.produit = produit.id
  t.produitNom = produit.nom
  const lead = await lireJson(await request.post(`${API_DJANGO}/crm/leads/`, {
    data: {
      nom: uniq('ACC Chantier'), ville: 'Casablanca', telephone: telephoneMobileUnique(),
      type_installation: 'residentiel', facture_hiver: '800',
    },
  }), 'lead')
  t.lead = lead.id
  const devis = await lireJson(await request.post(`${API_DJANGO}/ventes/devis/`, {
    data: { lead: lead.id, taux_tva: '20.00', mode_installation: 'residentiel' },
  }), 'devis')
  t.devis = devis.id
  await lireJson(await request.post(`${API_DJANGO}/ventes/devis/${devis.id}/replace-lines/`, {
    data: {
      lignes: [{
        produit: produit.id, designation: produit.nom, quantite: '4.00',
        prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00',
        type_ligne: 'produit', ordre: 0,
      }],
    },
  }), 'lignes du devis')
  await lireJson(await request.post(`${API_DJANGO}/ventes/devis/${devis.id}/accepter/`, {
    data: { nom: 'Client ACC Chantier' },
  }), 'acceptation du devis')
  // Idempotent : retourne le chantier créé à l'acceptation s'il existe déjà.
  const chantier = await lireJson(await request.post(`${API}/chantiers/creer-depuis-devis/`, {
    data: { devis: devis.id },
  }), 'chantier du devis')
  t.chantier = chantier.id
  if (techId) {
    const iv = await lireJson(await request.post(`${API}/interventions/`, {
      data: {
        installation: chantier.id, type_intervention: 'pose', technicien: techId,
        date_prevue: aujourdHui(),
      },
    }), 'intervention Pose')
    t.pose = iv.id
  }
}

// Nettoyage best-effort : chaque suppression est indépendante.
async function nettoyer(request, t) {
  const sup = (url) => request.delete(url).catch(() => null)
  if (t.chantier) {
    const appro = await lireOuNull(request, `${API}/chantiers/${t.chantier}/approvisionnement/`)
    for (const b of appro?.bons_commande ?? []) {
      await sup(`${API_DJANGO}/stock/bons-commande-fournisseur/${b.id}/`)
    }
    const ivs = await lireOuNull(request, `${API}/interventions/?installation=${t.chantier}&page_size=100`)
    for (const iv of listeDe(ivs)) await sup(`${API}/interventions/${iv.id}/`)
    await sup(`${API}/chantiers/${t.chantier}/`)
  }
  if (t.devis) await sup(`${API_DJANGO}/ventes/devis/${t.devis}/`)
  if (t.lead) await sup(`${API_DJANGO}/crm/leads/${t.lead}/`)
  if (t.produit) await sup(`${API_DJANGO}/stock/produits/${t.produit}/`)
  if (t.fournisseur) await sup(`${API_DJANGO}/stock/fournisseurs/${t.fournisseur}/`)
}

// Monte les données, joue le corps, nettoie TOUJOURS (même si le montage échoue à mi-chemin).
async function avecChantier(request, techId, corps) {
  const t = {}
  try {
    await monterChantier(request, t, techId)
    await corps(t)
  } finally {
    await nettoyer(request, t)
  }
}

async function ouvrirChantier(page, id, onglet) {
  await page.goto(`/chantiers?id=${id}`)
  await expect(page.getByRole('dialog')).toBeVisible()
  if (onglet) await page.getByRole('tab', { name: onglet }).click()
}

// Contexte NEUF connecté en demo_tech ; la fiche de la Pose de CETTE étape s'ouvre
// au chargement de « Ma journée » (restauration VX105, patron `adep.spec.js`).
// Les données sont montées par l'admin (`page.request`) puis nettoyées.
async function avecTechnicien({ page, suivi, testInfo, context }, corps, onglet = 'prep') {
  const ctx = await context.browser().newContext({
    baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block',
  })
  try {
    const p = suivi.surveiller(await ctx.newPage())
    await connexionApi(p.request, TECH)
    const techId = (await lireJson(await p.request.get(`${API_DJANGO}/auth/me/`), 'profil technicien')).id
    await avecChantier(page.request, techId, async (t) => {
      await p.context().addInitScript(([ident, tab]) => {
        try {
          localStorage.setItem('taqinor.onboardingTerrain.anonyme', '1')
          sessionStorage.setItem('mj.activeId', String(ident))
          sessionStorage.setItem('mj.tab', tab)
        } catch { /* stockage indisponible */ }
      }, [t.pose, onglet])
      await corps({ p, t })
    })
  } finally { await ctx.close() }
}

async function ouvrirMaJournee(p) {
  await p.goto('/ma-journee')
  await expect(p.getByRole('dialog')).toBeVisible()
}

const statutIntervention = async (p, id) => (await lireJson(
  await p.request.get(`${API}/interventions/${id}/`), 'intervention')).statut

// Départ dépôt + check-in (l'intervention passe « sur site »).
async function jusquAuSite(p, id) {
  await p.getByRole('tab', { name: /Prépa/ }).click()
  await p.getByRole('button', { name: /Tout est chargé/ }).click()
  await p.getByRole('tab', { name: /Trajet/ }).click()
  await p.getByRole('button', { name: /Départ dépôt/ }).click()
  await p.getByRole('button', { name: /Check-in/ }).click()
  await expect.poll(() => statutIntervention(p, id), { timeout: 20_000 }).toBe('sur_site')
}

etape('P1.1', ['ACHT104', 'ACHT105'], async ({ page }) => {
  // Approvisionnement visible SANS clic « Calculer » : le manque est calculé par le
  // serveur (une réponse), le chantier n'est pas « Prêt à poser ».
  await avecChantier(page.request, null, async (t) => {
    const appro = await lireJson(
      await page.request.get(`${API}/chantiers/${t.chantier}/approvisionnement/`), 'approvisionnement')
    const ligne = (appro.lignes ?? []).find((l) => l.produit_id === t.produit)
    expect(ligne, 'ligne du produit sans stock dans la nomenclature gelée').toBeTruthy()
    expect(ligne.manque, 'manque net > 0').toBeGreaterThan(0)
    expect(appro.resume.pret_a_poser).toBe(false)

    await ouvrirChantier(page, t.chantier, /Matériel/)
    await expect(page.getByRole('button', { name: /^Calculer$/ })).toHaveCount(0)
    await expect(page.getByRole('table').first()).toBeVisible()
    await expect(page.getByText(t.produitNom).first()).toBeVisible()
    await expect(page.getByText(/Prêt à poser/i).first()).toBeVisible()
    await page.reload() // persistance : rechargé, l'état est relu du serveur
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.getByRole('tab', { name: /Matériel/ }).click()
    await expect(page.getByText(t.produitNom).first()).toBeVisible()
  })
})

etape('P1.2', ['ACHT104', 'ACHT105', 'ACHT106'], async ({ page }) => {
  // « Commander les manques » crée le BCF du fournisseur (chantier d'origine posé) et
  // le chantier passe « Matériel commandé ».
  await avecChantier(page.request, null, async (t) => {
    await ouvrirChantier(page, t.chantier, /Matériel/)
    const bouton = page.getByRole('button', { name: /Commander les manques/ })
    await expect(bouton).toBeVisible()
    await bouton.click()
    await expect(page.getByText(/bon de commande créé/i).first()).toBeVisible()
    await page.reload()
    await expect(page.getByText(/Matériel commandé/).first()).toBeVisible()
    const relu = await lireJson(await page.request.get(`${API}/chantiers/${t.chantier}/`), 'chantier relu')
    expect(relu.statut).toBe('materiel_commande')
    const appro = await lireJson(
      await page.request.get(`${API}/chantiers/${t.chantier}/approvisionnement/`), 'approvisionnement relu')
    expect((appro.bons_commande ?? []).length, 'un BCF lié au chantier').toBeGreaterThanOrEqual(1)
    const bcf = await lireJson(await page.request.get(
      `${API_DJANGO}/stock/bons-commande-fournisseur/${appro.bons_commande[0].id}/`), 'BCF du chantier')
    expect(bcf.chantier_origine_reference, 'chantier d’origine lisible sur le BCF').toBeTruthy()
  })
})

etape('P1.3', ['ACHT105', 'ACHT110'], async ({ page, testInfo }) => {
  // Onglet Interventions : la Pose assignée à demo_tech existe ; « Créer les
  // interventions standard » est idempotent (toujours UNE Pose).
  const techId = await idTechnicien(testInfo.project.use.baseURL)
  await avecChantier(page.request, techId, async (t) => {
    await ouvrirChantier(page, t.chantier, /Interventions/)
    await expect(page.getByText(/Pose/).first()).toBeVisible()
    const creer = page.getByRole('button', { name: 'Créer les interventions standard' })
    if (await creer.isEnabled().catch(() => false)) await creer.click()
    await expect(page.getByText(/Pose/).first()).toBeVisible()
    const liste = listeDe(await lireJson(
      await page.request.get(`${API}/interventions/?installation=${t.chantier}&page_size=100`), 'interventions'))
    const poses = liste.filter((x) => x.type_intervention === 'pose')
    expect(poses.length, 'une seule Pose (idempotent)').toBe(1)
    expect(poses[0].technicien, 'Pose assignée à demo_tech').toBe(techId)
    await page.reload() // persistance
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.getByRole('tab', { name: /Interventions/ }).click()
    await expect(page.getByText(/Pose/).first()).toBeVisible()
  })
})

etape('P1.4', ['ACHT107', 'ACHT110'], async (ctx) => {
  // demo_tech : sa Pose (données de l'étape) s'ouvre dans « Ma journée » ; Prépa « Tout est chargé »,
  // Trajet « Départ dépôt » puis « Check-in » => l'intervention passe « sur site ».
  await avecTechnicien(ctx, async ({ p, t }) => {
    await ouvrirMaJournee(p)
    await jusquAuSite(p, t.pose)
    await p.reload() // persistance
    await expect.poll(() => statutIntervention(p, t.pose), { timeout: 20_000 }).toBe('sur_site')
  })
})

etape('P1.5', ['ACHT108'], async (ctx) => {
  // Photos : une image dans chaque emplacement obligatoire, géolocalisation best-effort.
  await avecTechnicien(ctx, async ({ p, t }) => {
    await ouvrirMaJournee(p)
    await p.getByRole('tab', { name: 'Photos' }).click()
    const champs = p.locator('input[type="file"]')
    const n = await champs.count()
    if (n === 0) nonCouvert('aucun emplacement photo obligatoire affiché')
    for (let i = 0; i < n; i += 1) await champs.nth(i).setInputFiles(photo(`acceptation-${i}.jpg`))
    await expect.poll(async () => listeDe(await lireJson(
      await p.request.get(`${API}/interventions/${t.pose}/photos/`), 'photos')).length,
    { timeout: 30_000 }).toBeGreaterThanOrEqual(n)
  })
})

etape('P1.6', ['ACHT108'], async (ctx) => {
  // N° série : séries attendues par produit, jauge « x/N », « Scanner », ajout d'une série
  // pour le produit depuis la liste fermée.
  await avecTechnicien(ctx, async ({ p, t }) => {
    const attendus = await lireJson(
      await p.request.get(`${API}/interventions/${t.pose}/serials-attendus/`), 'séries attendues')
    expect(JSON.stringify(attendus), 'le produit sans catégorie porte une série attendue')
      .toContain(String(t.produit))
    await ouvrirMaJournee(p)
    await p.getByRole('tab', { name: /N° série|Séries/ }).click()
    await expect(p.getByText(/\d+\s*\/\s*\d+/).first()).toBeVisible()
    await expect(p.getByRole('button', { name: /Scanner/ })).toBeVisible()
    await p.getByRole('combobox').first().selectOption({ index: 1 })
    const sn = `ACC-SN-${Date.now().toString(36)}`
    await p.getByPlaceholder(/N° de série/).fill(sn)
    await p.getByRole('button', { name: /Ajouter/ }).click()
    await expect(p.getByText(sn)).toBeVisible()
    await p.reload() // persistance
    await p.getByRole('tab', { name: /N° série|Séries/ }).click()
    await expect(p.getByText(sn)).toBeVisible()
    const series = listeDe(await lireJson(
      await p.request.get(`${API}/interventions/${t.pose}/serials/`), 'séries'))
    expect(series.some((s) => s.numero_serie === sn)).toBeTruthy()
  })
})

etape('P1.7', ['ACHT107', 'ACHT108'], async (ctx) => {
  // Signature client puis « Retour dépôt » : l'intervention passe « Terminée ».
  await avecTechnicien(ctx, async ({ p, t }) => {
    await ouvrirMaJournee(p)
    await jusquAuSite(p, t.pose)
    await p.getByRole('tab', { name: /Signature/ }).click()
    const zone = p.locator('canvas').first()
    await expect(zone).toBeVisible()
    const box = await zone.boundingBox()
    await p.mouse.move(box.x + 20, box.y + 20)
    await p.mouse.down()
    await p.mouse.move(box.x + box.width - 20, box.y + box.height - 20, { steps: 8 })
    await p.mouse.up()
    const accord = p.getByLabel(/J'ai lu et j'accepte/)
    if (await accord.count()) await accord.check()
    await p.getByRole('button', { name: /Enregistrer la signature|Valider/ }).first().click()
    await p.getByRole('tab', { name: /Trajet/ }).click()
    await p.getByRole('button', { name: /Retour dépôt/ }).click()
    await expect.poll(() => statutIntervention(p, t.pose), { timeout: 20_000 }).toBe('terminee')
  })
})

etape('P1.8', ['ACHT107', 'ACHT109'], async ({ page, testInfo }) => {
  // Retour admin : avertissements de clôture consultatifs une fois « Réceptionné » (liste,
  // jamais un blocage) et page Suivi GPS avec la liste des consentements.
  const techId = await idTechnicien(testInfo.project.use.baseURL)
  await avecChantier(page.request, techId, async (t) => {
    for (const statut of ['materiel_commande', 'planifie', 'en_cours', 'installe', 'receptionne']) {
      const pas = await page.request.patch(`${API}/chantiers/${t.chantier}/`, { data: { statut } })
      if (!pas.ok()) nonCouvert(`passage « ${statut} » refusé (${pas.status()} ${await pas.text()})`)
    }
    const recu = await lireJson(await page.request.get(`${API}/chantiers/${t.chantier}/`), 'chantier réceptionné')
    expect(Array.isArray(recu.avertissements_cloture), 'avertissements_cloture est une liste').toBeTruthy()
    await page.goto('/planification/suivi-gps')
    await expect(page.getByText(/Position partagée/).first()).toBeVisible()
    await page.reload() // persistance
    await expect(page.getByText(/Position partagée/).first()).toBeVisible()
  })
})
