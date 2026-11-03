// CADV — spec d'acceptation en direct du parcours PA1 « Contact -> visite », volet cadence v4
// (gabarits contact / après-devis / réveil, message d'identité, guide), jouée par l'ORCHESTRATEUR sur
// la pile locale (CLAUDE.md 3-bis, METHODE §C.4, `_format.md`). Aucun envoi réel : on lit le texte du
// « Message prêt » (GET …/message/), jamais d'envoi ; EMAIL_BACKEND console.
//
// Données : chaque étape crée ses leads/devis par l'API réelle. Le rejeu de la migration (CADV23)
// passe par le shell Django de la pile (E2E_DJANGO_EXEC) : `migrate parametres 0132` (marche arrière
// réelle) puis `migrate parametres` (marche avant réelle) sur les lignes de la société de démo.
import { test, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import {
  uniq, lireJson, telephoneMobileUnique, executerDansDjango, assurerSessionPage,
} from '../helpers.js'

const etape = groupe('CADV', ['CADV23', 'CADV24', 'CADV85', 'CADV34', 'CADV79', 'CADV25', 'CADV86', 'CADV87', 'CADV81', 'CADV72', 'CADV80', 'CADV9', 'CADV11'])
const API = '/api/django'
const T = { timeout: 120_000 }
test.beforeEach(async ({ page }) => {
  // L'habitué : bienvenue et bannière PWA déjà fermées (comme auth.setup.js, mais pour CETTE origine).
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

function shellJson(code) {
  const sortie = executerDansDjango(code)
  const ligne = sortie.split('\n').reverse().find((l) => l.startsWith('@@'))
  expect(ligne, `sortie du shell : ${sortie.slice(-400)}`).toBeTruthy()
  return JSON.parse(ligne.slice(2))
}

const email = () => `${uniq('cadv').toLowerCase().replace(/[^a-z0-9]/g, '')}@example.invalid`

async function nouveauLead(request, nom = 'CADV Lead') {
  return lireJson(await request.post(`${API}/crm/leads/`, {
    ...T, data: { nom: uniq(nom), ville: 'Casablanca', telephone: telephoneMobileUnique(), email: email() },
  }), 'lead')
}

async function ouvrirCadences(page) {
  await page.goto('/parametres?onglet=referentiels')
  await expect(page.getByTestId('cadence-relance-editor')).toBeVisible({ timeout: 60_000 })
}

const ONGLET = { contact: 'Contact', apres_devis: 'Après devis', reveil: 'Réveil' }

/** Lit l'éditeur : [{ordre, actif, texte}] de la cadence demandée. */
async function lireTable(page, cadence) {
  await page.getByTestId('cadence-relance-editor').getByRole('tab', { name: ONGLET[cadence], exact: true }).click()
  const table = page.getByTestId(`cadence-table-${cadence}`)
  await expect(table).toBeVisible()
  return table.evaluate((el) => [...el.querySelectorAll('[role="switch"][aria-label^="Active"]')].map((sw) => {
    const m = /étape (\d+)/.exec(sw.getAttribute('aria-label') || '')
    const ligne = sw.closest('div.border')
    return { ordre: Number(m?.[1]), actif: sw.getAttribute('aria-checked') === 'true', texte: ligne?.textContent || '' }
  }))
}

const instantane = (cad) => `
from apps.parametres.models_relance import CadenceRelanceEtape as C
import json
rows = list(C.objects.filter(company_id=1, cadence='${cad}').order_by('ordre').values_list(
    'ordre', 'canal', 'delai_jours', 'actif', 'template_cle', 'libelle'))
print('@@' + json.dumps(rows))
`
const migrer = (cible) => `from django.core.management import call_command
call_command('migrate', 'parametres', ${cible ? `'${cible}', ` : ''}verbosity=0)
${instantane('contact')}`

etape('PA1.contact_appel', ['CADV23'], async ({ page, suivi }) => {
  // 1. Rejeu de la migration sur les vraies lignes : marche arrière (v3), marche avant (v4), relecture.
  const v4 = shellJson(instantane('contact'))
  try {
    const v3 = shellJson(migrer('0132'))
    expect(v3.filter((r) => r[3]).length, 'marche arrière : le protocole v3 a plus de 8 barreaux actifs').toBeGreaterThanOrEqual(9)
    expect(v3.find((r) => r[0] === 9)?.[3], 'v3 : le barreau 9 est actif').toBeTruthy()
  } finally {
    shellJson(migrer(null))
  }
  // Django reste muet un moment après un `migrate` : attendre qu'il réponde avant d'ouvrir l'écran.
  await expect.poll(async () => (await page.request.get(`${API}/auth/me/`, { timeout: 20_000 }).catch(() => ({ status: () => 0 }))).status(),
    { timeout: 180_000, intervals: [2_000, 5_000] }).toBe(200)
  const apres = shellJson(instantane('contact'))
  expect(apres, 'marche avant : mêmes lignes que le v4 d\'origine (idempotence)').toEqual(v4)
  expect(apres.filter((r) => r[3]).map((r) => r[0]), 'ordres actifs').toEqual([1, 2, 3, 4, 5, 6, 7, 8])
  expect(apres.filter((r) => !r[3]).map((r) => r[0]), 'ordres 9-11 désactivés').toEqual([9, 10, 11])
  const canaux = apres.filter((r) => r[3]).map((r) => r[1])
  expect(canaux.filter((c) => c === 'appel').length, '5 appels').toBe(5)
  expect(canaux.filter((c) => c === 'whatsapp').length, '3 WhatsApp').toBe(3)
  expect(Math.max(...apres.filter((r) => r[3]).map((r) => r[2])), 'sur 7 jours').toBe(7)
  // 2. L'écran Paramètres → Cadences de relance → Contact liste 8 lignes actives.
  await ouvrirCadences(page)
  const lignes = await lireTable(page, 'contact')
  expect(lignes.length, 'onze barreaux affichés (les 3 derniers désactivés)').toBe(11)
  expect(lignes.filter((l) => l.actif).map((l) => l.ordre)).toEqual([1, 2, 3, 4, 5, 6, 7, 8])
  // 3. Persistance : recharger, relire.
  await page.reload()
  await expect(page.getByTestId('cadence-relance-editor')).toBeVisible({ timeout: 60_000 })
  expect((await lireTable(page, 'contact')).filter((l) => l.actif).length).toBe(8)
  suivi.verifie(5)
})

etape('PA1.suivi_appel', ['CADV24', 'CADV81'], async ({ page, suivi }) => {
  const lead = await nouveauLead(page.request, 'CADV24')
  const produit = await lireJson(await page.request.post(`${API}/stock/produits/`, {
    ...T, data: { nom: uniq('Onduleur CADV24'), prix_vente: '10000.00', prix_achat: '4321.09' },
  }), 'produit')
  const devis = await lireJson(await page.request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: lead.id,
      lignes: [{ produit: produit.id, designation: 'Onduleur', quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
    },
  }), 'devis')
  await lireJson(await page.request.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  const gab = shellJson(instantane('apres_devis'))
  expect(gab.filter((r) => r[3]).map((r) => r[2]), 'jours actifs').toEqual([1, 2, 3, 7, 10, 14, 28, 60, 90])
  expect(gab.filter((r) => !r[3]).map((r) => r[2]), 'J4 et J6 désactivés').toEqual([4, 6])
  // Le moteur pose la touche suivante à chaque geste : on avance sur la frise par le geste « sauter »
  // et on relit les dates posées. J3 (dimanche_famille) est conditionnelle par conception (MRY4).
  const jours = []
  for (let i = 0; i < 12; i += 1) {
    const liste = (await lireJson(await page.request.get(`${API}/crm/relance-etapes/?lead=${lead.id}`, T), 'étapes')).results
    const ouverte = liste.find((e) => e.cadence === 'apres_devis' && e.statut === 'a_faire')
    if (!ouverte || ouverte.template_cle === '') break
    jours.push([ouverte.ordre, ouverte.canal, ouverte.due_date])
    const r = await page.request.post(`${API}/crm/relance-etapes/${ouverte.id}/sauter/`, { ...T, data: { note: 'rejeu CADV24' } })
    expect(r.ok(), `sauter l'étape ${ouverte.ordre} (${r.status()})`).toBeTruthy()
  }
  const ordres = jours.map((j) => j[0])
  for (const attendu of [1, 2, 6, 7, 8, 9, 10, 11]) expect(ordres, `la frise pose l'ordre ${attendu}`).toContain(attendu)
  expect(ordres, 'J4 (4) et J6 (5) ne sont jamais posés').not.toContain(4)
  expect(ordres).not.toContain(5)
  const relu = await lireJson(await page.request.get(`${API}/ventes/devis/${devis.id}/`, T), 'devis relu')
  const envoi = new Date(relu.date_envoi)
  const ecart = Math.round((new Date(`${relu.date_validite}T12:00:00Z`) - envoi) / 86_400_000)
  expect(ecart, 'validité 30 jours depuis l\'envoi (pas 90)').toBeGreaterThanOrEqual(29)
  expect(ecart).toBeLessThanOrEqual(31)
  const j90 = jours.find((j) => j[0] === 11)
  const joursJ90 = Math.round((new Date(`${j90[2]}T12:00:00Z`) - envoi) / 86_400_000)
  expect(joursJ90, 'dernier appel à J90').toBeGreaterThanOrEqual(89)
  expect(joursJ90).toBeLessThanOrEqual(91)
  // Écran : la frise du lead montre les touches posées.
  await page.goto(`/crm/leads/${lead.id}`)
  await expect(page.getByTestId('cadence-frise')).toBeVisible({ timeout: 60_000 })
  expect(await page.getByTestId('cadence-frise-etape').count(), 'la frise affiche les touches').toBeGreaterThanOrEqual(8)
  suivi.verifie(5)
})

etape('PA1.reveil_appel', ['CADV85'], async ({ page, suivi }) => {
  const reveil = shellJson(instantane('reveil'))
  expect(reveil[0].slice(0, 3), 'ordre 1 : appel à J30').toEqual([1, 'appel', 30])
  expect(reveil[1].slice(0, 3), 'ordre 2 : WhatsApp à J60 inchangé').toEqual([2, 'whatsapp', 60])
  await ouvrirCadences(page)
  await page.getByTestId('cadence-relance-editor').getByRole('tab', { name: 'Réveil', exact: true }).click()
  const premier = page.getByTestId('cadence-table-reveil').locator('div.border').first()
  await expect(premier).toContainText('Appel')
  await page.reload()
  await page.getByTestId('cadence-relance-editor').getByRole('tab', { name: 'Réveil', exact: true }).click()
  await expect(page.getByTestId('cadence-table-reveil').locator('div.border').first()).toContainText('Appel')
  suivi.verifie(5)
})

etape('PA1.contact_message', ['CADV34'], async ({ page, suivi }) => {
  const STOP = 'Répondez STOP et je n\'insiste plus.'
  const lead = await nouveauLead(page.request, 'CADV34')
  const liste = (await lireJson(await page.request.get(`${API}/crm/relance-etapes/?lead=${lead.id}`, T), 'étapes')).results
  const identite = liste.find((e) => e.template_cle === 'identite')
  expect(identite, 'la touche d\'identité est posée à l\'arrivée du lead').toBeTruthy()
  const fr = await lireJson(await page.request.get(`${API}/crm/relance-etapes/${identite.id}/message/`, T), 'message FR')
  expect(fr.message.trim().endsWith(STOP), `le message prêt finit par la ligne STOP : « ${fr.message.slice(-80)} »`).toBeTruthy()
  const rl = await page.request.post(`${API}/crm/relance-etapes/${identite.id}/langue/`, { ...T, data: { langue: 'darija' } })
  expect(rl.ok(), `changer la langue (${rl.status()})`).toBeTruthy()
  const darija = await lireJson(await page.request.get(`${API}/crm/relance-etapes/${identite.id}/message/`, T), 'message darija')
  expect(darija.message, 'le texte darija est un autre texte').not.toBe(fr.message)
  expect(/STOP/.test(darija.message), `le message darija porte STOP : « ${darija.message.slice(-100)} »`).toBeTruthy()
  await page.goto(`/crm/leads/${lead.id}`)
  await expect(page.getByTestId('cadence-frise')).toBeVisible({ timeout: 60_000 })
  suivi.verifie(5)
})

etape('PA1.guide_ged', ['CADV79'], async ({ suivi }) => {
  // Le PDF committé du guide « Le suivi commercial » (celui que la GED publie via publier_documents_meryem).
  const texte = execFileSync('python', ['-I', '-c',
    'import sys,pypdf,re;sys.stdout.reconfigure(encoding="utf-8");r=pypdf.PdfReader(sys.argv[1]);t=" ".join(p.extract_text() or "" for p in r.pages);print(re.sub(r"\\s+"," ",t))',
    `${RACINE}docs/meryem/Suivi_commercial_etapes_et_reponses.pdf`], { encoding: 'utf8', maxBuffer: 20_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  expect(texte, 'le guide annonce 8 touches de contact').toMatch(/8 touches\W+5 appels et 3 messages\W+sur 7 jours/)
  expect(texte, 'le guide annonce 9 touches après devis jusqu\'à J90').toMatch(/9 touches\W+5 appels et 4 messages\W+sur 90 jours/)
  expect(texte, 'plus de protocole à 11 touches').not.toMatch(/11 touches/)
  suivi.verifie(5)
})

const nomUnique = (base) => `${base} ${Date.now().toString().slice(-6)}`

async function leadAvecFacture(request, base, facture, extra = {}) {
  return lireJson(await request.post(`${API}/crm/leads/`, {
    ...T, data: { nom: nomUnique(base), ville: 'Casablanca', telephone: telephoneMobileUnique(), email: email(), facture_hiver: facture, ...extra },
  }), 'lead')
}

const touches = async (request, lid) => (await lireJson(await request.get(`${API}/crm/relance-etapes/?lead=${lid}`, T), 'touches')).results

/** Traite chaque touche ouverte : appel → « Non joint » tracé, message → sauté ; renvoie les touches posées. */
async function derouler(request, lid, max = 40) {
  for (let i = 0; i < max; i += 1) {
    const ouverte = (await touches(request, lid)).find((e) => e.statut === 'a_faire')
    if (!ouverte) break
    const r = ouverte.canal === 'appel'
      ? await request.post(`${API}/crm/relance-etapes/${ouverte.id}/fait/`, { ...T, data: { outcome: 'non_joint', note: 'rejeu CADV' } })
      : await request.post(`${API}/crm/relance-etapes/${ouverte.id}/sauter/`, { ...T, data: { note: 'rejeu CADV' } })
    expect(r.ok(), `traiter la touche ${ouverte.ordre} (${r.status()})`).toBeTruthy()
  }
  return touches(request, lid)
}

async function devisEnvoye(request, lid, base) {
  const produit = await lireJson(await request.post(`${API}/stock/produits/`, {
    ...T, data: { nom: nomUnique(`Onduleur ${base}`), prix_vente: '10000.00', prix_achat: '4321.09' },
  }), 'produit')
  const devis = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: lid,
      lignes: [{ produit: produit.id, designation: 'Onduleur', quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
    },
  }), 'devis')
  await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  return devis
}

etape('PA1.reveil_appel_filtre', ['CADV25', 'CADV86', 'CADV72', 'CADV80'], async ({ page, suivi }) => {
  const reveils = (liste) => liste.filter((e) => e.cadence === 'reveil')
  // (a) jamais joint, jamais chiffré, facture 800 < 2 000 : aucun réveil, le lead finit au Froid.
  const seuil = await leadAvecFacture(page.request, 'Reveil Seuil', 800)
  expect(reveils(await derouler(page.request, seuil.id)), 'sous le seuil : aucun appel de réveil').toHaveLength(0)
  const froid = await lireJson(await page.request.get(`${API}/crm/leads/${seuil.id}/`, T), 'lead')
  expect(froid.stage, 'le lead est au Froid').toBe('COLD')
  expect([froid.parc_etat, froid.parc_raison], 'CADV72 : fin de gabarit parquée par parquer_lead').toEqual(['nurture', 'injoignable'])
  expect(froid.tags, 'CADV80 : 5 appels au gabarit v4').toContain('Injoignable 5 appels')
  // (b) pilote CADV86 : facture 2 300 MAD, jamais joint ni chiffré : UN seul appel de réveil, le J30.
  const pilote = await leadAvecFacture(page.request, 'Reveil Pilote', 2300)
  const lp = await derouler(page.request, pilote.id)
  expect(reveils(lp).map((e) => [e.ordre, e.canal]), 'le pilote garde le seul appel J30').toEqual([[1, 'appel']])
  // (c) chiffré (devis envoyé, plan après-devis déroulé) : les deux réveils du gabarit (J30 appel, J60 message).
  const chiffre = await leadAvecFacture(page.request, 'Reveil Chiffre', 800)
  await devisEnvoye(page.request, chiffre.id, 'RV')
  const lc = await derouler(page.request, chiffre.id)
  expect(reveils(lc).map((e) => [e.ordre, e.canal]), 'le lead chiffré garde ses deux réveils').toEqual([[1, 'appel'], [2, 'whatsapp']])
  expect((await lireJson(await page.request.get(`${API}/crm/leads/${chiffre.id}/`, T), 'lead')).parc_raison,
    "CADV72 : fin d'après-devis = pas_maintenant_sans_date").toBe('pas_maintenant_sans_date')
  // Écran : la frise du lead pilote montre le réveil ; celle du lead sous le seuil n'en montre pas. Persistance : rechargé.
  await page.goto(`/crm/leads/${pilote.id}`)
  await expect(page.getByTestId('cadence-frise')).toContainText('Réveil', { timeout: 60_000 })
  await page.reload()
  await expect(page.getByTestId('cadence-frise')).toContainText('Réveil', { timeout: 60_000 })
  await page.goto(`/crm/leads/${seuil.id}`)
  await expect(page.getByTestId('cadence-frise')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByTestId('cadence-frise')).not.toContainText('Réveil')
  suivi.verifie(5)
})

etape('PA1.suivi_message', ['CADV87'], async ({ page, suivi }) => {
  // Une réalisation à montrer existe (repli « dernière installation de la société ») : on la pose si la société n'en a pas.
  const reals = await lireJson(await page.request.get(`${API}/parametres/realisations/`, T), 'réalisations')
  if (!(reals.results ?? reals).some((r) => r.actif)) {
    await lireJson(await page.request.post(`${API}/parametres/realisations/`, {
      ...T, data: { titre: 'Villa Ain Sebaa 6 kWc', ville: 'Casablanca', puissance_kwc: '6.0', mise_en_service: '2026-05-01', url_page: 'https://taqinor.ma/realisations/villa-ain-sebaa', actif: true },
    }), 'réalisation')
  }
  const j10 = async (frein) => {
    const lead = await leadAvecFacture(page.request, `Frein ${frein}`, 800, { frein_principal: frein })
    await devisEnvoye(page.request, lead.id, frein)
    for (let i = 0; i < 8; i += 1) {
      const ouverte = (await touches(page.request, lead.id)).find((e) => e.statut === 'a_faire' && e.cadence === 'apres_devis')
      expect(ouverte, 'une touche après-devis est ouverte').toBeTruthy()
      if (ouverte.ordre >= 7) return { cle: ouverte.template_cle, id: ouverte.id, lead }
      const r = ouverte.canal === 'appel'
        ? await page.request.post(`${API}/crm/relance-etapes/${ouverte.id}/fait/`, { ...T, data: { outcome: 'non_joint', note: 'rejeu CADV87' } })
        : await page.request.post(`${API}/crm/relance-etapes/${ouverte.id}/sauter/`, { ...T, data: { note: 'rejeu CADV87' } })
      expect(r.ok(), `traiter ${ouverte.ordre} (${r.status()})`).toBeTruthy()
    }
    throw new Error("le J10 n'a pas été posé")
  }
  const confiance = await j10('confiance')
  const prix = await j10('prix')
  expect(confiance.cle, 'frein « confiance » : le J10 montre un chantier comparable').toBe('j4_preuve')
  expect(prix.cle, 'frein « prix » : le J10 garde les garanties').toBe('j6_garanties')
  const texte = async (id) => (await lireJson(await page.request.get(`${API}/crm/relance-etapes/${id}/message/`, T), 'message')).message
  const [a, b] = [await texte(confiance.id), await texte(prix.id)]
  expect(a, 'deux textes J10 différents').not.toBe(b)
  expect(a, 'le texte « confiance » nomme la réalisation').toMatch(/Ain Sebaa|Casablanca/i)
  expect(b, 'le texte « prix » ne nomme pas la réalisation').not.toMatch(/Ain Sebaa/i)
  await page.goto(`/crm/leads/${confiance.lead.id}`)
  await expect(page.getByTestId('cadence-frise')).toBeVisible({ timeout: 60_000 })
  suivi.verifie(5)
})

etape('PA1.cadence_gestes', ['CADV9', 'CADV11'], async ({ page, suivi }) => {
  // CADV9 : message WhatsApp ouvert puis « Fait » (joint) : une seule ligne WhatsApp, une note d'issue.
  const lead = await nouveauLead(page.request, 'CADV9 Whatsapp')
  const t1 = (await touches(page.request, lead.id)).find((e) => e.canal === 'whatsapp' && e.statut === 'a_faire')
  expect(t1, 'touche WhatsApp ouverte').toBeTruthy()
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${t1.id}/whatsapp/`, T), 'ouverture du message')
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${t1.id}/fait/`, { ...T, data: { outcome: 'joint', note: 'rejeu CADV9' } }), 'fait joint')
  const histo = await lireJson(await page.request.get(`${API}/crm/leads/${lead.id}/historique/`, T), 'historique')
  expect(histo.filter((h) => h.kind === 'whatsapp'), 'une seule ligne WhatsApp (le clic)').toHaveLength(1)
  expect(histo.filter((h) => h.outcome === 'joint'), "une note d'issue joint").toHaveLength(1)
  const relu = await lireJson(await page.request.get(`${API}/crm/leads/${lead.id}/`, T), 'lead')
  expect(relu.nb_tentatives).toBe(1)
  expect(relu.first_contacted_at, 'premier contact posé').toBeTruthy()
  const apres = await touches(page.request, lead.id)
  expect(apres.filter((e) => e.cadence === 'contact' && e.statut === 'a_faire' && e.ordre >= 2 && e.ordre <= 8), 'la cadence contact est arrêtée').toHaveLength(0)
  // CADV11 : « Reporter » au 20/11 : la date convenue est servie, comptée une fois ; rechargé, identique.
  const l2 = await nouveauLead(page.request, 'CADV11 Rappel')
  const t2 = (await touches(page.request, l2.id)).find((e) => e.statut === 'a_faire')
  await lireJson(await page.request.post(`${API}/crm/relance-etapes/${t2.id}/reporter/`, { ...T, data: { rappel_le: '2026-11-20', rappel_heure: '10:00' } }), 'reporter')
  const lu = (await touches(page.request, l2.id)).find((e) => e.id === t2.id)
  expect(lu.rappel_convenu_le).toBe('2026-11-20')
  expect(lu.nb_reports).toBe(1)
  await page.goto(`/crm/leads/${l2.id}`)
  await expect(page.getByTestId('cadence-frise')).toBeVisible({ timeout: 60_000 })
  expect((await touches(page.request, l2.id)).find((e) => e.id === t2.id).rappel_convenu_le, 'persistance').toBe('2026-11-20')
  suivi.verifie(5)
})
