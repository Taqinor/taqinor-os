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
import { expect, test, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { aujourdHui } from './_enregistrement.js'
import {
  API_DJANGO, PNG_1PX, assurerSessionPage, connexionApi, lireJson, listeDe, textePdf, uniq, telephoneMobileUnique,
} from '../helpers.js'

const etape = groupe('ACHT', [
  'ACHT104', 'ACHT105', 'ACHT106', 'ACHT107', 'ACHT108', 'ACHT109', 'ACHT110', 'ACHT99',
])
const API = `${API_DJANGO}/installations`
const TECH = { username: 'demo_tech', password: 'Demo@2026!' }
// Pile locale partagée et chargée : budget large par étape (ACHT99).
test.describe.configure({ timeout: 300_000 })
// La session du storageState expire au fil d'une longue passe : rouverte par l'API.
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
// Pile chargée : une requête API peut dépasser 15 s.
test.use({ actionTimeout: 60_000 })

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
async function monterChantier(request, t, techId, { quantite = '4.00', prestation = false } = {}) {
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
  if (prestation) {
    // Une ligne de devis exige un produit : la prestation est un produit « Installation ».
    t.prestation = (await lireJson(await request.post(`${API_DJANGO}/stock/produits/`, {
      data: { nom: uniq('Installation'), prix_vente: '4000.00' },
    }), 'prestation Installation')).id
  }
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
        produit: produit.id, designation: produit.nom, quantite,
        prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00',
        type_ligne: 'produit', ordre: 0,
      }, ...(t.prestation ? [{
        // ACHT99 — une prestation « Installation » : jamais au parc SAV (ACHT94).
        produit: t.prestation, designation: 'Installation', quantite: '1.00', prix_unitaire: '4000.00',
        remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 1,
      }] : [])],
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
async function avecChantier(request, techId, corps, options = {}) {
  const t = {}
  try {
    await monterChantier(request, t, techId, options)
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
    // Fondateur 27/10/2026 — l'accord aux conditions d'utilisation (géolocalisation)
    // conditionne l'accès aux missions : demo_tech l'accorde (idempotent) avant sa journée.
    await lireJson(await p.request.get(`${API}/gps-consentements/mon-consentement/`), 'consentement GPS')
    await p.request.post(`${API}/gps-consentements/mon-consentement/accepter/`)
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

// ════════════════════════════════════════════════════════════════════════════
// ACHT99 — parcours J2 devis accepté → chantier → achats → atelier →
// intervention → réception → parc SAV → rapport → annulation (acceptation de
// groupe ACHT). Données propres par étape (montage ci-dessus + une prestation
// « Installation » et 12 panneaux) ; un compte Viewer de test créé par l'API
// (pile locale seule).
// ════════════════════════════════════════════════════════════════════════════
const J2 = { quantite: '12.00', prestation: true }
const VIEWER = { username: 'acc_viewer_acht99', password: 'Acc@Viewer2026!' }
const SIGNATURE = `data:image/png;base64,${PNG_1PX.toString('base64')}`

async function contexteApi(baseURL, identifiants) {
  const api = await pwRequest.newContext({ baseURL })
  await connexionApi(api, identifiants)
  return api
}

// Compte Viewer de test (rôle système « Viewer ») — créé une fois, réutilisé.
async function assurerViewer(request) {
  const roles = listeDe(await lireJson(await request.get(`${API_DJANGO}/roles/?page_size=200`), 'rôles'))
  const viewer = roles.find((r) => r.nom === 'Viewer')
  if (!viewer) nonCouvert('rôle système « Viewer » absent de la société démo')
  const r = await request.post(`${API_DJANGO}/users/`, {
    data: {
      username: VIEWER.username, email: `${VIEWER.username}@example.test`, password: VIEWER.password,
      first_name: 'Acceptation', last_name: 'Viewer', role: viewer.id,
    },
  })
  if (!r.ok()) {
    const corps = await r.text()
    if (!/existe|exists|unique|déjà/i.test(corps)) {
      nonCouvert(`création du compte Viewer refusée (${r.status()} ${corps.slice(0, 200)})`)
    }
  }
}

const chantierDe = async (request, id) => lireJson(await request.get(`${API}/chantiers/${id}/`), 'chantier')
const isoIlYa = (n) => {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

etape('P99.1', ['ACHT99'], async ({ page }) => {
  // (1) Devis accepté → UN seul chantier, aucune fausse bannière « Devis modifié ».
  await avecChantier(page.request, null, async (t) => {
    const encore = await lireJson(await page.request.post(`${API}/chantiers/creer-depuis-devis/`, {
      data: { devis: t.devis },
    }), 'chantier du devis (2e appel)')
    expect(encore.id, 'idempotent : même chantier').toBe(t.chantier)
    const liste = listeDe(await lireJson(
      await page.request.get(`${API}/chantiers/?devis=${t.devis}&page_size=50`), 'chantiers du devis'))
    expect(liste.filter((c) => c.devis === t.devis).length, 'un seul chantier').toBe(1)
    const ch = await chantierDe(page.request, t.chantier)
    expect(ch.divergence_devis?.diverge ?? false, 'aucune divergence devis').toBe(false)
    await ouvrirChantier(page, t.chantier)
    await expect(page.getByText(/Devis modifié/)).toHaveCount(0)
    await page.reload()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByText(/Devis modifié/)).toHaveCount(0)
  }, J2)
})

etape('P99.2', ['ACHT99'], async ({ page }) => {
  // (2) Une étape avancée, puis Notes modifiées + « Mettre à jour » : le statut
  // avancé est conservé (le formulaire n'écrase pas l'étape).
  await avecChantier(page.request, null, async (t) => {
    await lireJson(await page.request.patch(`${API}/chantiers/${t.chantier}/`, {
      data: { statut: 'materiel_commande' },
    }), 'étape suivante')
    await ouvrirChantier(page, t.chantier)
    const note = uniq('Note ACHT99')
    await page.locator('#ch-notes').fill(note)
    await page.getByRole('button', { name: 'Mettre à jour' }).click()
    await expect.poll(async () => (await chantierDe(page.request, t.chantier)).notes, { timeout: 30_000 }).toBe(note)
    expect((await chantierDe(page.request, t.chantier)).statut, 'statut avancé conservé').toBe('materiel_commande')
    await page.reload()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.locator('#ch-notes')).toHaveValue(note)
  }, J2)
})

etape('P99.3', ['ACHT99'], async ({ page, testInfo }) => {
  // (3) Demande d'achat du chantier : prix à 3 décimales refusé puis corrigé ;
  // BC généré par l'admin ; le technicien est refusé. Une seule DA.
  const tech = await contexteApi(testInfo.project.use.baseURL, TECH)
  try {
    await avecChantier(page.request, null, async (t) => {
      const da = await lireJson(await page.request.post(`${API}/demandes-achat/`, {
        data: { objet: uniq('DA ACHT99'), chantier: t.chantier, fournisseur_suggere: t.fournisseur },
      }), 'demande d’achat')
      const ligne = { demande: da.id, produit: t.produit, quantite: '2', prix_estime: '12.345' }
      const r3 = await page.request.post(`${API}/demandes-achat-lignes/`, { data: ligne })
      expect(r3.status(), 'prix à 3 décimales refusé').toBe(400)
      expect(JSON.stringify(await r3.json())).toContain('prix_estime')
      await lireJson(await page.request.post(`${API}/demandes-achat-lignes/`, {
        data: { ...ligne, prix_estime: '12.35' },
      }), 'ligne corrigée')
      await lireJson(await page.request.post(`${API}/demandes-achat/${da.id}/soumettre/`, { data: {} }), 'soumettre')
      await lireJson(await page.request.post(`${API}/demandes-achat/${da.id}/approuver/`, { data: {} }), 'approuver')
      const refus = await tech.post(`${API}/demandes-achat/${da.id}/generer-bcf/`, { data: {} })
      expect(refus.status(), 'BC refusé au technicien').toBe(403)
      await lireJson(await page.request.post(`${API}/demandes-achat/${da.id}/generer-bcf/`, { data: {} }), 'BC admin')
      const das = listeDe(await lireJson(
        await page.request.get(`${API}/demandes-achat/?chantier=${t.chantier}&page_size=50`), 'DA du chantier'))
      expect(das.filter((d) => d.chantier === t.chantier).length, 'une seule DA').toBe(1)
      const relu = await lireJson(await page.request.get(`${API}/demandes-achat/${da.id}/`), 'DA relue')
      expect(relu.chantier, 'chantier affiché sur la DA').toBe(t.chantier)
      await page.goto('/chantiers/demandes-achat')
      await expect(page.getByText(da.reference).first()).toBeVisible({ timeout: 30_000 })
    }, J2)
  } finally { await tech.dispose() }
})

etape('P99.4', ['ACHT99'], async ({ page }) => {
  // (4) Ateliers : ordre d'assemblage du kit depuis le devis du chantier.
  await avecChantier(page.request, null, async (t) => {
    const r = await page.request.post(`${API}/ordres-assemblage/depuis-devis/`, { data: { devis: t.devis } })
    if (!r.ok()) nonCouvert(`ordre d'assemblage depuis le devis refusé (${r.status()} ${(await r.text()).slice(0, 200)})`)
    const ordres = listeDe(await lireJson(
      await page.request.get(`${API}/ordres-assemblage/?page_size=200`), 'ordres d’assemblage'))
      .filter((o) => o.devis === t.devis)
    if (ordres.length === 0) nonCouvert('le devis ne porte aucun kit : aucun ordre d’assemblage créable')
    await page.goto('/atelier')
    await expect(page.getByText(ordres[0].reference || String(ordres[0].id)).first()).toBeVisible()
  }, J2)
})

etape('P99.5', ['ACHT99'], async (ctx) => {
  // (5) Intervention : check-in HORS LIGNE puis retour du réseau (arrivée « dans
  // la fenêtre ») ; doublon de série refusé sous le champ ; signature refusée au
  // Viewer ; compte-rendu PDF ; page publique du compte-rendu sans session.
  const { page, suivi, testInfo } = ctx
  await assurerViewer(page.request)
  await avecTechnicien(ctx, async ({ p, t }) => {
    await lireJson(await page.request.patch(`${API}/interventions/${t.pose}/`, {
      data: { fenetre_debut: '00:00', fenetre_fin: '23:59' },
    }), 'fenêtre promise')
    await ouvrirMaJournee(p)
    await p.getByRole('tab', { name: /Prépa/ }).click()
    await p.getByRole('button', { name: /Tout est chargé/ }).click()
    await p.getByRole('tab', { name: /Trajet/ }).click()
    await p.getByRole('button', { name: /Départ dépôt/ }).click()
    suivi.attendre(/\/api\/django\//, 'reseau')
    await p.context().setOffline(true)
    await p.getByRole('button', { name: /Check-in/ }).click()
    await p.context().setOffline(false)
    await expect.poll(() => statutIntervention(p, t.pose), { timeout: 60_000 }).toBe('sur_site')
    const iv = await lireJson(await page.request.get(`${API}/interventions/${t.pose}/`), 'intervention')
    expect(iv.arrivee_dans_fenetre, 'arrivée dans la fenêtre').toBe(true)

    // Séries : la même deux fois → la 2e refusée sous le champ.
    await p.getByRole('tab', { name: /N° série|Séries/ }).click()
    const sn = `ACC99-${Date.now().toString(36)}`
    suivi.attendre(/ajouter-serial/, 409)
    for (let i = 0; i < 2; i += 1) {
      await p.getByRole('combobox').first().selectOption({ index: 1 })
      await p.getByPlaceholder(/N° de série/).fill(sn)
      await p.getByRole('button', { name: /Ajouter/ }).click()
      if (i === 0) await expect(p.getByText(sn)).toBeVisible()
    }
    await expect(p.getByText(/déjà relevé|déjà au parc/).first()).toBeVisible()
    const series = listeDe(await lireJson(await p.request.get(`${API}/interventions/${t.pose}/serials/`), 'séries'))
    expect(series.filter((s) => s.numero_serie === sn).length, 'une série par relevé').toBe(1)

    // Viewer : signature client refusée.
    const viewer = await contexteApi(testInfo.project.use.baseURL, VIEWER)
    try {
      const r = await viewer.post(`${API}/interventions/${t.pose}/signer-client/`, {
        data: { signature_client: SIGNATURE, signataire_nom: 'Viewer' },
      })
      expect(r.status(), 'Viewer refusé').toBe(403)
    } finally { await viewer.dispose() }

    // Compte-rendu PDF + page publique du compte-rendu en navigation privée.
    const pdf = await page.request.get(`${API}/interventions/${t.pose}/compte-rendu/`)
    expect(pdf.status(), 'compte-rendu PDF').toBe(200)
    expect(pdf.headers()['content-type']).toContain('pdf')
    const lien = await lireJson(await page.request.get(`${API}/interventions/${t.pose}/lien-rapport/`), 'lien du compte-rendu')
    const prive = await page.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block' })
    try {
      const pub = suivi.surveiller(await prive.newPage())
      await pub.goto(lien.path || new URL(lien.url).pathname)
      await expect(pub.getByText(/Youssef/).first()).toBeVisible({ timeout: 30_000 })
    } finally { await prive.close() }
  })
})

etape('P99.6', ['ACHT99'], async ({ page, testInfo }) => {
  // (6)+(7) Réception : BL signé, réceptionné, date de réception CORRIGÉE ⇒ date de
  // pose du parc = date corrigée ; parc = matériel seul, une série par relevé.
  const tech = await contexteApi(testInfo.project.use.baseURL, TECH)
  try {
    const techId = (await lireJson(await tech.get(`${API_DJANGO}/auth/me/`), 'tech')).id
    await tech.post(`${API}/gps-consentements/mon-consentement/accepter/`)
    await avecChantier(page.request, techId, async (t) => {
      const sns = [`ACC99A-${Date.now().toString(36)}`, `ACC99B-${Date.now().toString(36)}`]
      for (const sn of sns) {
        await lireJson(await tech.post(`${API}/interventions/${t.pose}/ajouter-serial/`, {
          data: { produit: t.produit, numero_serie: sn },
        }), `série ${sn}`)
      }
      await lireJson(await page.request.post(`${API}/chantiers/${t.chantier}/signer-client/`, {
        data: { signature_client: SIGNATURE, signataire_nom: 'Client ACC Chantier' },
      }), 'BL signé')
      for (const statut of ['materiel_commande', 'planifie', 'en_cours', 'installe', 'receptionne']) {
        const pas = await page.request.patch(`${API}/chantiers/${t.chantier}/`, { data: { statut } })
        if (!pas.ok()) nonCouvert(`passage « ${statut} » refusé (${pas.status()} ${(await pas.text()).slice(0, 200)})`)
      }
      const corrigee = isoIlYa(3)
      await lireJson(await page.request.patch(`${API}/chantiers/${t.chantier}/`, {
        data: { date_reception: corrigee },
      }), 'date de réception corrigée')
      const ch = await chantierDe(page.request, t.chantier)
      expect(ch.date_reception).toBe(corrigee)
      const parc = listeDe(await lireJson(
        await page.request.get(`${API_DJANGO}/sav/equipements/?installation=${t.chantier}&page_size=100`), 'parc'))
      try {
        expect(parc.map((e) => e.numero_serie).sort(), 'une série par relevé, aucun fantôme').toEqual([...sns].sort())
        expect(parc.every((e) => e.produit === t.produit), 'parc = matériel seul').toBe(true)
        expect(parc.map((e) => e.date_pose), 'date de pose = réception corrigée').toEqual(parc.map(() => corrigee))
        await page.goto('/equipements')
        await expect(page.getByText(sns[0]).first()).toBeVisible({ timeout: 30_000 })
      } finally {
        for (const e of parc) await page.request.delete(`${API_DJANGO}/sav/equipements/${e.id}/`).catch(() => null)
      }
    }, J2)
  } finally { await tech.dispose() }
})

etape('P99.8', ['ACHT99'], async ({ page }) => {
  // (8) Rapport de production : PDF sans montant nul ni négatif, OU refus lisible
  // quand la puissance (kWc) manque.
  await avecChantier(page.request, null, async (t) => {
    const r = await page.request.get(`${API}/chantiers/${t.chantier}/rapport-energie/`)
    if (r.status() === 409) {
      expect((await r.json()).detail, 'refus lisible').toMatch(/kWc|puissance/i)
      return
    }
    expect(r.status()).toBe(200)
    const texte = await textePdf(await r.body())
    expect(texte, 'aucun montant négatif').not.toMatch(/-\s?\d[\d\s]*[,.]\d{2}\s*(MAD|DH)/)
    expect(texte, 'aucun montant nul').not.toMatch(/(^|\s)0[,.]00\s*(MAD|DH)/)
  }, J2)
})

etape('P99.9', ['ACHT99'], async ({ page, suivi, testInfo }) => {
  // (9) Un autre chantier annulé : le lien client de son intervention est expiré.
  const techId = await idTechnicien(testInfo.project.use.baseURL)
  await avecChantier(page.request, techId, async (t) => {
    const lien = await lireJson(await page.request.get(`${API}/interventions/${t.pose}/lien-client/`), 'lien client')
    await lireJson(await page.request.post(`${API}/chantiers/${t.chantier}/annuler/`, {
      data: { motif: 'Acceptation ACHT99' },
    }), 'annulation')
    const apres = await page.request.get(`${API}/interventions/${t.pose}/lien-client/`)
    expect(apres.status(), 'lien-client d’une intervention annulée').toBe(409)
    const prive = await page.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block' })
    try {
      const pub = suivi.surveiller(await prive.newPage())
      suivi.attendre(/\/public\/installations\/intervention\//, 404)
      await pub.goto(lien.path)
      await expect(pub.getByText(/introuvable ou a expiré/)).toBeVisible({ timeout: 30_000 })
    } finally { await prive.close() }
  })
})
