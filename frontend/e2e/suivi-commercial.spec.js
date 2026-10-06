// CIQ521 — ALLER-RETOUR EN DIRECT du suivi d'un lead COMMERCIAL (clôture de la
// vague CIQ5, leçon QJR5 : des tests unitaires verts ne prouvent pas que
// l'écran, le serveur et le guide disent la même chose).
//
// Pile locale `seed_demo`, AUCUN mock réseau sur les écrans testés. Un lead
// commercial joignable SEULEMENT sur un fixe, doté d'une adresse e-mail, reçoit
// un devis commercial (créé au vrai générateur) envoyé :
//   1. devis envoyé → suivi de proposition démarré ;
//   2. sa première touche WhatsApp naît e-mail : objet, adresse, bouton
//      « Ouvrir dans la messagerie » (aucun envoi) ;
//   3. noter « Qui décide : avec un associé / la direction » sur le panneau
//      d'appel pose l'étiquette « Décision à plusieurs » ;
//   4. « En attente d'un accord » SANS raison est refusée (400 qui nomme
//      `raison_attente`), puis acceptée avec « La direction / le comité » à J+10 :
//      étiquette, veille de la même touche, accusé proposé ;
//   5. la validité prolongée est LA MÊME sur la page publique et sur le PDF ;
//   6. aucune tâche « dossier 82-21 » pour ce lead en basse tension ;
//   7. tout le suivi traversé : aucune touche WhatsApp, aucune touche J4 (aucune
//      réalisation professionnelle).
// Nettoyage best-effort en afterAll (base partagée, workers: 1).
import { test, expect } from '@playwright/test'
import {
  API_DJANGO as API, lireJson, listeDe, telephoneFixeUnique, isoDansJours, textePdf,
  creerDevisCommercialDepuisLead, uniq,
} from './helpers.js'

const jeton = String(Date.now()).slice(-9)
const societe = `Hôtel Atlas ${jeton}`
const email = `standard-${jeton}@hotel-atlas.example`
const TAG_DECISION = /décision à plusieurs/i
const TAG_DIRECTION = 'Attend la direction / le comité'

const leadIds = []
const devisIds = []
let lead = null
let devisId = null
let premiere = null
let validiteAvant = null

const apresDevis = (t) => t.cadence === 'apres_devis'
const ouvertes = (liste) => liste.filter((t) => t.statut === 'a_faire')

async function touches(request) {
  return listeDe(await lireJson(await request.get(
    `${API}/crm/relance-etapes/?lead=${lead.id}&scope=lead`), 'touches du lead'))
}
const leadDetail = async (request) => lireJson(
  await request.get(`${API}/crm/leads/${lead.id}/`), 'lead')

/** `AAAA-MM-JJ` → `JJ/MM/AAAA`, le format que le PDF imprime. */
const jjmmaaaa = (iso) => iso.split('-').reverse().join('/')

async function validitePublique(request) {
  const lien = await lireJson(await request.post(
    `${API}/ventes/devis/${devisId}/share-link/`, { data: {} }), 'lien de partage')
  expect(lien.token_interne, 'jeton interne de la proposition').toBeTruthy()
  const data = await lireJson(await request.get(
    `${API}/public/proposal/${lien.token_interne}/data/`), 'proposition publique')
  expect(data.date_validite, 'date de validité servie par la page publique').toBeTruthy()
  return data.date_validite
}

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  await Promise.all(devisIds.map((id) => request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
  await Promise.all(leadIds.map((id) => request.delete(`${API}/crm/leads/${id}/`).catch(() => null)))
})

test.describe('CIQ521 — suivi d’un lead commercial, en direct', () => {
  test('1. lead sur fixe + e-mail : devis commercial envoyé, suivi de proposition démarré', async ({ page, request }) => {
    test.setTimeout(240_000)
    lead = await lireJson(await request.post(`${API}/crm/leads/`, {
      data: {
        nom: uniq('Direction E2E'), societe, ville: 'Casablanca',
        telephone: telephoneFixeUnique(), email, type_installation: 'commercial',
        facture_hiver: '9000', tension_raccordement: 'bt', langue_preferee: 'fr',
      },
    }), 'création du lead commercial')
    leadIds.push(lead.id)
    expect(lead.whatsapp || '', 'joignable seulement sur un fixe').toBe('')

    devisId = await creerDevisCommercialDepuisLead(page, lead.id)
    devisIds.push(devisId)
    const envoi = await lireJson(await request.post(
      `${API}/ventes/devis/${devisId}/envoyer-email/`, { data: { to_email: email } }), 'envoi du devis')
    expect(envoi.devis_statut).toBe('envoye')
    validiteAvant = await validitePublique(request)

    await expect.poll(async () => ouvertes((await touches(request)).filter(apresDevis)).length,
      { message: 'le suivi de proposition démarre à l’envoi du devis' }).toBeGreaterThan(0)
    premiere = ouvertes((await touches(request)).filter(apresDevis))
      .sort((a, b) => a.ordre - b.ordre)[0]
  })

  test('2. la touche WhatsApp naît e-mail : objet, adresse, « Ouvrir dans la messagerie »', async ({ page, request }, testInfo) => {
    expect(premiere.template_cle).toBe('j1_pdf')
    expect(premiere.canal, 'touche WhatsApp devenue e-mail').toBe('email')
    expect(premiere.canal_adapte).toContain('fixe')
    const message = await lireJson(await request.get(
      `${API}/crm/relance-etapes/${premiere.id}/message/`), 'texte de la touche')
    expect(message.objet, 'objet de l’e-mail').toBeTruthy()
    expect(message.mailto_url).toContain(email)

    await page.goto(`/crm/leads/${lead.id}`)
    await page.getByTestId('texte-touche').first()
      .getByRole('button', { name: 'Texte de l’e-mail' }).click()
    await expect(page.getByTestId('texte-touche-objet').first()).toContainText(message.objet)
    const ouvrir = page.getByTestId('ouvrir-messagerie').first()
    await expect(ouvrir).toBeVisible()
    await expect(ouvrir).toHaveAttribute('href', /^mailto:/)
    await testInfo.attach('ciq521-touche-email', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })
    // Rien n'est parti : la touche reste à faire jusqu'à « Fait ».
    const relue = (await touches(request)).find((t) => t.id === premiere.id)
    expect(relue.statut).toBe('a_faire')
  })

  test('3. « Qui décide : avec la direction » noté au panneau d’appel → « Décision à plusieurs »', async ({ page, request }, testInfo) => {
    await page.goto(`/crm/leads/${lead.id}`)
    await page.locator('a.lw-rail-contact-link', { hasText: '☎' }).click()
    await expect(page.getByRole('dialog', { name: /Appel —/ })).toBeVisible()
    const question = page.getByTestId('question-appel-decideur').first()
    await expect(question).toBeVisible({ timeout: 30_000 })
    await question.getByRole('button', { name: 'Avec un associé / la direction' }).click()
    await expect.poll(async () => (await leadDetail(request)).decideur,
      { message: 'la réponse est écrite sur la fiche' }).toBe('associe_direction')
    expect(String((await leadDetail(request)).tags || '')).toMatch(TAG_DECISION)
    await testInfo.attach('ciq521-decideur', { body: await page.screenshot(), contentType: 'image/png' })
  })

  test('4. « En attente d’un accord » : refusée sans raison, acceptée avec « Direction / comité » à J+10', async ({ request }) => {
    const date = isoDansJours(10)
    const url = `${API}/crm/relance-etapes/${premiere.id}/fait/`
    const refus = await request.post(url, {
      data: { reponse: 'attente_accord', rappel_le: date, rappel_heure: '11:00' },
    })
    expect(refus.status(), 'sans raison : refus').toBe(400)
    const erreurs = (await refus.json()).erreurs || {}
    expect(Object.keys(erreurs), 'le refus nomme le champ').toContain('raison_attente')
    expect(String((await leadDetail(request)).tags || '')).not.toContain(TAG_DIRECTION)

    await lireJson(await request.post(url, {
      data: {
        reponse: 'attente_accord', rappel_le: date, rappel_heure: '11:00', raison_attente: 'direction',
      },
    }), 'attente d’un accord')
    expect(String((await leadDetail(request)).tags || '')).toContain(TAG_DIRECTION)
    const veille = (await touches(request)).find((t) => t.id === premiere.id)
    expect(veille.statut, 'la même touche veille').toBe('a_faire')
    expect(veille.due_date).toBe(date)
    expect(veille.nb_reports).toBeGreaterThanOrEqual(1)
    // L'accusé est PROPOSÉ (jamais envoyé) : un texte prêt à relire.
    const accuse = await lireJson(await request.get(
      `${API}/crm/relance-etapes/${premiere.id}/message/?cle=attente_accord_accuse`), 'accusé proposé')
    expect(String(accuse.message || '').length, 'accusé proposé').toBeGreaterThan(0)
  })

  test('5. date de validité prolongée : la même sur la page publique et sur le PDF', async ({ request }) => {
    const apres = await validitePublique(request)
    expect(apres >= validiteAvant, `jamais raccourcie (${validiteAvant} → ${apres})`).toBe(true)
    const pdf = await request.get(`${API}/ventes/devis/${devisId}/proposal/?pdf_mode=full`)
    expect(pdf.status(), '/proposal').toBe(200)
    const texte = (await textePdf(await pdf.body())).replaceAll(String.fromCharCode(160), ' ')
    expect(texte, `le PDF imprime la validité de la page publique (${apres})`)
      .toContain(jjmmaaaa(apres))
  })

  test('6. aucune tâche « dossier 82-21 » pour ce lead en basse tension', async ({ request }) => {
    const liste = await touches(request)
    expect(liste.filter((t) => /82-21/.test(`${t.libelle} ${t.note || ''}`) || t.template_cle === 'dossier_8221'))
      .toEqual([])
    const playbook = listeDe(await lireJson(await request.get(
      `${API}/crm/leads/${lead.id}/playbook/`), 'playbook du lead'))
    expect(playbook.filter((p) => p.cle_message === 'dossier_8221')).toEqual([])
    expect((await leadDetail(request)).tension_raccordement).toBe('bt')
  })

  test('7. tout le suivi traversé : aucune touche WhatsApp, aucune touche J4', async ({ request }) => {
    const vues = new Map()
    let atteinte = false
    for (let i = 0; i < 14 && !atteinte; i += 1) {
      const liste = (await touches(request)).filter(apresDevis)
      for (const t of liste) vues.set(t.template_cle, t.canal)
      const ouverte = ouvertes(liste).sort((a, b) => a.ordre - b.ordre)
      if (ouverte.some((t) => t.template_cle === 'j6_garanties')) { atteinte = true; break }
      expect(ouverte.length, 'une touche ouverte à sauter').toBeGreaterThan(0)
      await lireJson(await request.post(
        `${API}/crm/relance-etapes/${ouverte[0].id}/sauter/`, { data: {} }), 'sauter')
    }
    expect(atteinte, 'la touche « garanties » (J6) finit par exister').toBe(true)
    expect(vues.get('j1_pdf')).toBe('email')
    expect([...vues.values()], 'canaux du suivi de proposition').not.toContain('whatsapp')
    expect([...vues.keys()], 'pas de preuve J4 sans réalisation professionnelle')
      .not.toContain('j4_preuve')
  })
})
