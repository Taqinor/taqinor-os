// AMSG — preuve en direct d'AMSG6 avec le VRAI assistant (vague d'acceptation 6, lane « llm », 16/11/2026) :
// « assistant de démo « prépare le WhatsApp du devis <id> » : carte de résultat, devis toujours brouillon dans
// la liste ». Le service IA FastAPI RÉEL tourne dans le job (vraie clé de modèle, moteur et interrupteurs à leur
// défaut du merge) ; l'écran l'atteint sous `/api/fastapi/` comme derrière nginx (route Playwright → E2E_IA_URL,
// jeton de la session relayé en Bearer). Le modèle n'est pas déterministe : l'étape affirme les INVARIANTS de la
// clause (carte « wa_devis » rendue, devis brouillon sans date d'envoi en base ET dans la liste, lead à son étape,
// aucune touche après-devis, aucune note, l'aperçu servi par Django et jamais le commit), pas un texte.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { readFileSync, statSync } from 'node:fs'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('AMSG', ['AMSG6'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

// ── service IA réel (FastAPI du workflow), branché sous /api/fastapi comme nginx en prod ─────────────────────
const IA = process.env.E2E_IA_URL
const jetonDe = async (context) => (await context.cookies()).find((c) => c.name === 'access_token')?.value || ''
async function brancherIA(page) {
  expect(IA, 'service IA lancé par le workflow (E2E_IA_URL)').toBeTruthy()
  await page.route(/\/api\/fastapi\//, async (route) => {
    const req = route.request()
    const u = new URL(req.url())
    const headers = { ...req.headers() }
    delete headers.host; delete headers.cookie; delete headers['content-length']
    const jeton = await jetonDe(page.context())
    if (jeton) headers.authorization = `Bearer ${jeton}`
    try {
      const rep = await route.fetch({ url: `${IA}${u.pathname.replace(/^\/api\/fastapi/, '')}${u.search}`, headers, timeout: 300_000, maxRedirects: 0 })
      await route.fulfill({ response: rep })
    } catch {
      await route.abort().catch(() => undefined)
    }
  })
}
async function viderHistorique(context) {
  const ia = await pwRequest.newContext({ baseURL: IA, extraHTTPHeaders: { Authorization: `Bearer ${await jetonDe(context)}` } })
  try { await ia.delete('/sql-agent/history', T) } finally { await ia.dispose() }
}
/** Pose `question` dans le tiroir Copilote ; rend le corps JSON de `/sql-agent/query` (réponse du vrai modèle). */
async function demander(page, question) {
  const panneau = page.getByTestId('copilot-panel')
  if (!(await panneau.isVisible().catch(() => false))) {
    await page.getByTestId('copilot-toggle').click()
    await expect(panneau, 'tiroir Copilote ouvert').toBeVisible({ timeout: 30_000 })
  }
  const zone = panneau.getByPlaceholder('Posez votre question en français…')
  await expect(zone).toBeEnabled({ timeout: 60_000 })
  await zone.fill(question)
  const rep = page.waitForResponse((r) => r.request().method() === 'POST' && /\/api\/fastapi\/sql-agent\/query$/.test(new URL(r.url()).pathname), { timeout: 300_000 })
  await panneau.getByRole('button', { name: 'Envoyer' }).click()
  const r = await rep
  const corps = await r.json().catch(() => ({}))
  expect(r.status(), `réponse de l'assistant : ${J(corps).slice(0, 400)}`).toBe(200)
  await expect(zone, 'tour terminé').toBeEnabled({ timeout: 60_000 })
  console.log(`[AMSG6] « ${question} » → moteur=${corps.moteur} cartes=${J((corps.cartes || []).map((c) => c.carte))} réponse=${J((corps.answer || '').slice(0, 300))}`)
  return { panneau, corps }
}
const tailleDe = (f) => { try { return statSync(f).size } catch { return 0 } }
const lireDepuis = (f, debut) => { try { return readFileSync(f).subarray(debut).toString('utf8') } catch { return '' } }

// ── données (mêmes routes que amsg.spec.js) ──────────────────────────────────────────────────────────────────
async function devisBrouillon(request, leadId, m) {
  const p = await lireJson(await request.post(`${API}/stock/produits/`, {
    ...T, data: { nom: `Onduleur AMSG6 ${m}`, prix_vente: '10000.00', prix_achat: '4321.09' },
  }), 'produit')
  const d = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: leadId,
      lignes: [{ produit: p.id, designation: 'Onduleur', quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
    },
  }), 'devis')
  return { d, p }
}
const etat = (leadId, devisId) => py(`from apps.crm.models import Lead, LeadActivity
from apps.crm.models_cadence import RelanceEtape
from apps.ventes.models import Devis
l = Lead.objects.get(pk=${leadId}); dv = Devis.objects.get(pk=${devisId})
sortie(dict(stage=l.stage, statut=dv.statut, envoi=dv.date_envoi, apres=RelanceEtape.objects.filter(lead_id=${leadId}, cadence='apres_devis').count(),
            notes=LeadActivity.objects.filter(lead_id=${leadId}).count()))`)

/** Sonde hôte du constat (vrai code, bouchons, sans Django) : {ok, repro, observe | erreur}. */
function sonde(constat) {
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-X', 'utf8', `docs/audits/sondes/AMSG/${constat}.py`], { cwd: RACINE, encoding: 'utf8', timeout: 120_000, maxBuffer: 50_000_000 })
  try {
    const d = JSON.parse(r.stdout)
    return { ok: true, repro: d.repro, observe: d.observe }
  } catch {
    return { ok: false, erreur: ((r.stderr || r.stdout || '').trim().split('\n').pop() || `code ${r.status}`).slice(0, 300) }
  }
}

// ═══ PF8.1 — AMSG6 : « prépare le WhatsApp du devis <id> » au VRAI assistant de démo ⇒ carte, devis brouillon ═══
etape('PF8.1-AMSG6-assistant-reel', ['AMSG6'], async ({ page, testInfo }) => {
  // Sonde du constat rejouée : si elle s'exécute, repro False ; si son bouchon ne tourne plus sur l'arbre, elle est
  // PÉRIMÉE (consigné) et la route réelle ci-dessous fait la preuve.
  const s = sonde('C-AMSG-007')
  testInfo.annotations.push({ type: 'sonde C-AMSG-007', description: s.ok ? `repro=${s.repro}` : `périmée — ne s'exécute plus : ${s.erreur}` })
  console.log(`[AMSG6] sonde C-AMSG-007 : ${s.ok ? `repro=${s.repro}` : `PÉRIMÉE (${s.erreur})`}`)
  if (s.ok) expect(s.repro, 'sonde C-AMSG-007 rejouée : repro False').toBe(false)

  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, {
    ...T, data: { nom: `AMSG6 ${m}`, prenom: 'Nadia', ville: 'Casablanca', telephone: telephoneMobileUnique(), whatsapp: telephoneMobileUnique(), email: `amsg6-${m}@example.invalid` },
  }), 'lead')
  const { d } = await devisBrouillon(r, lead.id, m)
  try {
    const avant = await etat(lead.id, d.id)
    expect(avant.statut, 'devis de départ brouillon').toBe('brouillon')
    const accesAvant = tailleDe(process.env.E2E_DJANGO_ACCESS_LOG || '/tmp/gunicorn-access.log')

    await brancherIA(page)
    await viderHistorique(page.context())
    await page.goto('/apps')
    const { panneau, corps } = await demander(page, `Prépare le WhatsApp du devis ${d.id} (référence ${d.reference}) du lead ${lead.id}.`)

    // Carte de résultat : la carte « wa_devis » du serveur (jamais le texte du modèle), rendue dans le tiroir.
    const cartes = (corps.cartes || []).filter((c) => c.carte === 'wa_devis')
    expect(cartes.length, `carte wa_devis servie par le tour (cartes : ${J((corps.cartes || []).map((c) => c.carte))})`).toBeGreaterThan(0)
    const donnees = cartes[cartes.length - 1].donnees || {}
    expect(donnees.wa_url, 'wa_url du résultat').toMatch(/^https:\/\/wa\.me\//)
    expect(donnees.message, 'message du résultat').toBeTruthy()
    expect((donnees.links || []).map((l) => l.devis_id), 'links du résultat : le devis demandé').toContain(d.id)
    const carte = panneau.getByTestId('carte-wa_devis').last()
    await expect(carte, 'carte de résultat affichée dans le tiroir').toBeVisible({ timeout: 30_000 })
    await expect(carte.getByTestId('wa-texte'), 'texte du message affiché').toBeVisible()
    await expect(carte.getByRole('button', { name: /Ouvrir WhatsApp/ }), 'bouton Ouvrir WhatsApp (non pressé)').toBeVisible()
    await expect(carte.getByTestId('wa-devis-envoye'), 'aucun envoi enregistré par l\'assistant').toHaveCount(0)

    // Django a servi l'APERÇU de l'assistant, jamais le commit `whatsapp-devis` (journal d'accès du gunicorn du job).
    const acces = lireDepuis(process.env.E2E_DJANGO_ACCESS_LOG || '/tmp/gunicorn-access.log', accesAvant)
    const apercu = acces.split('\n').filter((l) => l.includes(`/crm/assistant/leads/${lead.id}/whatsapp-devis-apercu/`))
    const commit = acces.split('\n').filter((l) => new RegExp(`/crm/leads/${lead.id}/whatsapp-devis/`).test(l))
    console.log(`[AMSG6] journal d'accès : aperçu=${J(apercu)} commit=${J(commit)}`)
    expect(apercu.length, 'l\'action exécutée est l\'aperçu sans effet').toBeGreaterThan(0)
    expect(commit, 'aucun appel du commit whatsapp-devis').toEqual([])

    // Persistance : devis brouillon sans date d'envoi, lead à son étape, aucune touche après-devis, aucune note.
    const apres = await etat(lead.id, d.id)
    expect(apres, 'devis et lead inchangés').toEqual(avant)
    expect(apres.envoi, 'aucune date d\'envoi').toBeNull()
    expect(apres.apres, 'aucune touche après-devis').toBe(0)

    // Écran nommé par la clause : la LISTE des devis lit toujours un brouillon.
    await page.goto('/ventes/devis')
    await page.getByPlaceholder('Rechercher (référence ou client)…').fill(d.reference, { timeout: 60_000 })
    const ligne = page.locator(`#devis-row-${d.id}`)
    await expect(ligne, 'le devis est dans la liste').toBeVisible({ timeout: 60_000 })
    await expect(ligne, 'statut « Brouillon » dans la liste').toContainText(/Brouillon/i)
    await expect(ligne, 'jamais le statut « Envoyé »').not.toContainText('Envoyé')
  } finally {
    await r.delete(`${API}/ventes/devis/${d.id}/`, T).catch(() => null)
    await r.delete(`${API}/crm/leads/${lead.id}/`, T).catch(() => null)
  }
}, {
  ecart: {
    base: 'FAIL',
    raison: "sonde C-AMSG-007 périmée : NameError _valider_valeur, fonction ajoutée par COP-A2 830794c10 (13/11), "
      + "postérieure à AMSG6 et hors Files ; repro False déjà asserté dans docs/audits/acceptation/AMSG/2026-11-13-f409ca823 "
      + "(PF8.1.assistant_apercu_whatsapp) ; ce rejeu ajoute l'assistant réel",
  },
})
