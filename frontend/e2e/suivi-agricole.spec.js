// AGR545 — ALLER-RETOUR EN DIRECT du suivi d'un lead AGRICOLE (clôture de la
// vague AGR5, leçon QJR5 : des tests unitaires verts ne prouvent pas que
// l'écran, le serveur et le guide disent la même chose).
//
// Pile locale `seed_demo` (aucun lead agricole, aucun playbook semé) : le
// spec crée SES leads et, si absent, le playbook de segment FDA (forme exacte
// de `crm.services.PLAYBOOKS_SEGMENT_CAD125`), puis joue le parcours :
//   1. lead agricole au butane en darija → `valeur_j1` darija sans « فاتورة »
//      ni « السطح » (variante agricole AGR511) ;
//   2. appel abouti sans niveau ni débit → la suite est la visite de relevé
//      du point d'eau (« Planifier la visite — relevé du point d'eau ») ;
//   3. tâche FDA du playbook → « Proposer le texte » ouvre la modale ;
//   4. devis agricole envoyé → suivi de proposition SANS touche J4 tant
//      qu'aucune réalisation agricole n'existe (AGR514) ;
//   5. réponse « En attente d'un accord (DPA / banque) » datée → étiquette
//      posée, dossier en veille (AGR520) ;
//   6. cockpit filtré « Agricole » → le lead en veille y est listé (AGR543).
// Nettoyage best-effort en afterAll (la base est partagée, workers:1).
import { test, expect } from '@playwright/test'

const API = '/api/django'
const NOM_FDA = 'Segment — dossier de subvention agricole (FDA)'
const TACHE_FDA = 'Demander où en est le dossier de subvention agricole FDA '
  + '(texte « dossier_fda » au catalogue des messages)'
const TAG_ATTENTE_ACCORD = 'Attend un accord (DPA / banque)'

const leadIds = []
const devisIds = []
let playbookCree = null

// Numéro marocain E.164 UNIQUE (la cadence ne démarre pas sur un doublon).
const telephoneUnique = () => `+2126${String(Date.now()).slice(-8)}`

function isoDansJours(n) {
  const d = new Date()
  d.setDate(d.getDate() + n)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const j = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${j}`
}

async function json(res, quoi) {
  expect(res.ok(), `${quoi} → HTTP ${res.status()} ${await res.text()}`).toBeTruthy()
  return res.json()
}

async function creerLeadAgricole(request, nom) {
  const lead = await json(await request.post(`${API}/crm/leads/`, {
    data: {
      nom, ville: 'Taroudant', telephone: telephoneUnique(),
      type_installation: 'agricole', pompe_alim_actuelle: 'butane',
      langue_preferee: 'darija',
    },
  }), `création du lead ${nom}`)
  leadIds.push(lead.id)
  return lead
}

async function touches(request, leadId) {
  const corps = await json(await request.get(
    `${API}/crm/relance-etapes/?lead=${leadId}&scope=lead`), 'touches du lead')
  return Array.isArray(corps) ? corps : (corps.results || [])
}

const ouvertes = (liste) => liste.filter((t) => t.statut === 'a_faire')

// Saute les touches ouvertes (la cadence est RÉACTIVE : chaque saut
// matérialise le barreau suivant) jusqu'à ce que `cible(touche)` soit vrai.
async function sauterJusqua(request, leadId, cible, filtre = () => true) {
  for (let i = 0; i < 12; i += 1) {
    const liste = ouvertes(await touches(request, leadId)).filter(filtre)
    const trouvee = liste.find(cible)
    if (trouvee) return trouvee
    expect(liste.length, 'une touche ouverte à sauter').toBeGreaterThan(0)
    await json(await request.post(
      `${API}/crm/relance-etapes/${liste[0].id}/sauter/`, { data: {} }), 'sauter')
  }
  throw new Error('touche cible jamais matérialisée')
}

async function assurerPlaybookFda(request) {
  const corps = await json(await request.get(`${API}/crm/playbooks/`), 'playbooks')
  const liste = Array.isArray(corps) ? corps : (corps.results || [])
  if (liste.some((p) => p.nom === NOM_FDA && p.actif !== false)) return
  const pb = await json(await request.post(`${API}/crm/playbooks/`, {
    data: {
      nom: NOM_FDA, actif: true,
      condition: {
        op: 'and',
        conditions: [
          { field: 'type_installation', operator: 'eq', value: 'agricole' },
          { field: 'pompe_alim_actuelle', operator: 'eq', value: 'butane' },
        ],
      },
    },
  }), 'création du playbook FDA')
  playbookCree = pb.id
  const etape = await json(await request.post(`${API}/crm/playbook-etapes/`, {
    data: { playbook: pb.id, stage: 'CONTACTED', ordre: 0 },
  }), 'étape du playbook FDA')
  await json(await request.post(`${API}/crm/playbook-taches/`, {
    data: { etape: etape.id, libelle: TACHE_FDA, obligatoire: false, ordre: 0 },
  }), 'tâche du playbook FDA')
}

test.describe.configure({ mode: 'serial' })

test.describe('AGR545 — suivi d’un lead agricole, en direct', () => {
  let leadA
  let leadB

  test.afterAll(async ({ request }) => {
    await Promise.all(devisIds.map((id) => (
      request.delete(`${API}/ventes/devis/${id}/`).catch(() => null))))
    await Promise.all(leadIds.map((id) => (
      request.delete(`${API}/crm/leads/${id}/`).catch(() => null))))
    if (playbookCree) {
      await request.delete(`${API}/crm/playbooks/${playbookCree}/`).catch(() => null)
    }
  })

  test('valeur_j1 en darija : variante agricole, ni « فاتورة » ni « السطح »', async ({ request }) => {
    await assurerPlaybookFda(request)
    leadA = await creerLeadAgricole(request, `Ferme AGR545 ${Date.now()}`)
    const valeur = await sauterJusqua(request, leadA.id,
      (t) => t.template_cle === 'valeur_j1')
    expect(valeur.lead_segment).toBe('agricole')
    const msg = await json(await request.get(
      `${API}/crm/relance-etapes/${valeur.id}/message/`), 'message valeur_j1')
    expect(msg.langue).toBe('darija')
    expect(msg.repli_langue).toBe(false)
    expect(msg.message.length).toBeGreaterThan(0)
    expect(msg.message).not.toContain('فاتورة')
    expect(msg.message).not.toContain('السطح')
  })

  test('appel abouti sans niveau ni débit → visite de relevé du point d’eau', async ({ request }) => {
    const appel = await sauterJusqua(request, leadA.id, (t) => t.canal === 'appel')
    const rep = await json(await request.post(
      `${API}/crm/relance-etapes/${appel.id}/fait/`, { data: { outcome: 'joint' } }),
    'appel abouti')
    expect(rep.prochaine_touche?.cle).toBe('planifier')
    const planifier = ouvertes(await touches(request, leadA.id))
      .find((t) => t.cle === 'planifier')
    expect(planifier, 'touche « planifier » ouverte').toBeTruthy()
    expect(planifier.note).toContain('Relevé du point d’eau')
    const lead = await json(await request.get(`${API}/crm/leads/${leadA.id}/`), 'lead A')
    expect(lead.stage).toBe('CONTACTED')
  })

  test('« Proposer le texte » de la tâche FDA ouvre la modale', async ({ page, request }, testInfo) => {
    // La tâche est générée à l'entrée en CONTACTED (appel abouti ci-dessus).
    const progres = await json(await request.get(
      `${API}/crm/leads/${leadA.id}/playbook/`), 'playbook du lead')
    const liste = Array.isArray(progres) ? progres : (progres.results || [])
    expect(liste.some((p) => p.cle_message === 'dossier_fda')).toBeTruthy()

    await page.goto(`/crm/leads/${leadA.id}`)
    await page.getByRole('tab', { name: 'Playbook' }).click()
    const panneau = page.getByTestId('playbook-checklist-panel')
    await expect(panneau).toBeVisible()
    await panneau.getByRole('button', { name: 'Proposer le texte' }).click()
    const modale = page.getByRole('dialog')
    await expect(modale).toBeVisible()
    await expect(modale.getByRole('button', { name: 'Copier' })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('agr545-fda-modale.png') })
    await modale.getByRole('button', { name: 'Fermer' }).first().click()
  })

  test('devis agricole envoyé → suivi de proposition SANS touche J4', async ({ request }) => {
    const devis = await json(await request.post(`${API}/ventes/devis/`, {
      data: { lead: leadA.id, taux_tva: '20.00', mode_installation: 'agricole' },
    }), 'création du devis')
    devisIds.push(devis.id)
    await json(await request.post(`${API}/crm/leads/${leadA.id}/whatsapp-devis/`, {
      data: { devis_ids: [devis.id], langue: 'fr' },
    }), 'envoi du devis')
    const relu = await json(await request.get(`${API}/ventes/devis/${devis.id}/`), 'devis')
    expect(relu.statut).toBe('envoye')

    const apresDevis = (t) => t.cadence === 'apres_devis'
    // Saute la proposition jusqu'au barreau QUI SUIT le trou de l'ordre 4
    // (aucune réalisation agricole : J4 retirée), puis parcourt TOUTE la
    // liste — sinon « pas de J4 » serait vrai par vacuité.
    const suite = await sauterJusqua(request, leadA.id,
      (t) => t.template_cle === 'j6_garanties', apresDevis)
    expect(suite).toBeTruthy()
    const cles = (await touches(request, leadA.id)).filter(apresDevis)
      .map((t) => t.template_cle)
    expect(cles).toContain('j1_pdf')
    expect(cles).not.toContain('j4_preuve')
  })

  test('« En attente d’un accord (DPA / banque) » daté → étiquette + veille', async ({ request }) => {
    leadB = await creerLeadAgricole(request, `Ferme AGR545 veille ${Date.now()}`)
    const [premiere] = ouvertes(await touches(request, leadB.id))
    expect(premiere, 'première touche du protocole').toBeTruthy()
    const date = isoDansJours(7)
    const rep = await json(await request.post(
      `${API}/crm/relance-etapes/${premiere.id}/fait/`,
      { data: { reponse: 'attente_accord', rappel_le: date } }), 'attente d’accord')
    expect(rep.statut).toBe('a_faire')
    const lead = await json(await request.get(`${API}/crm/leads/${leadB.id}/`), 'lead B')
    expect(String(lead.tags || '')).toContain(TAG_ATTENTE_ACCORD)
    const veille = (await touches(request, leadB.id)).find((t) => t.id === premiere.id)
    expect(veille.statut).toBe('a_faire')
    expect(veille.due_date).toBe(date)
    expect(veille.nb_reports).toBeGreaterThanOrEqual(1)
  })

  test('cockpit filtré « Agricole » : le lead en veille y est listé', async ({ page, request }, testInfo) => {
    const ctrl = await json(await request.get(
      `${API}/crm/relance-etapes/controle/?segment=agricole&jours=14`), 'contrôle agricole')
    expect(ctrl.segment).toBe('agricole')
    const reports = ctrl.exceptions?.reports?.lignes || []
    expect(reports.some((l) => l.lead === leadB.id)).toBeTruthy()
    const residentiel = await json(await request.get(
      `${API}/crm/relance-etapes/controle/?segment=residentiel&jours=14`), 'contrôle résidentiel')
    expect((residentiel.exceptions?.reports?.lignes || [])
      .some((l) => l.lead === leadB.id)).toBeFalsy()

    await page.goto('/crm/cockpit')
    const panneau = page.getByTestId('controle-suivi-panel')
    await expect(panneau).toBeVisible()
    await panneau.getByRole('button', { name: 'Voir le détail' }).click()
    await panneau.getByRole('combobox', { name: 'Segment' }).click()
    await page.getByRole('option', { name: 'Agricole' }).click()
    await expect(page.getByTestId('controle-segment-actif')).toContainText('Agricole')
    await expect(panneau.getByText(leadB.nom, { exact: false }).first()).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('agr545-cockpit-agricole.png'), fullPage: true })
  })
})
