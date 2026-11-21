// Acceptation en direct — groupe ACAL, septième lot (runner GitHub) : ACAL490, moitié ÉCRAN du complément L5 du
// calepinage. Une étape par preuve « à l'écran » des tâches ACAL382-489 livrées (code sur dev-all-acal-l5) : rail guidé
// et mode expert, glossaire, guide, redirections, barre d'enregistrement et brouillon serveur, fiche, Détection du toit,
// palette ⌘K et raccourcis, gestes du constructeur (état vide, toit par cotes, formes, hypothèses, aide de pente,
// annuler/rétablir, filet des effacements), Production (héros, mensuel, journée type), Pertes (lignes, panneau unifié),
// « ce qui manque », simulation automatique, Économie, Optimiser, rapport d'étude, Démarrage rapide.
// Les preuves « API seulement » (ACAL426, 445, 451, 452, 455, 456, 461-463, 465, 467, 468, 474, 477) sont jouées par
// l'autre lane. Montage carte : celui d'acal6 (ACAL377) — `design-context` relu puis sa `carte` surchargée d'une clé
// factice, `https://api.maptiler.com/**` répond 403 (déclaré) : l'atelier boote sur son fond de repli local. Tout le
// reste est réel. Données propres à chaque étape (lead + calepinage au shell Django), nettoyées.
// Le runner n'a AUCUN worker Celery : un travail mis en file par l'écran (simulation automatique, balayage) est exécuté
// par la VRAIE tâche (`apps.calepinage.tasks`) appelée au shell avec la charge utile que l'écran a envoyée ; l'écran le
// suit par son propre sondage. Une simulation « de préparation » passe par le VRAI service `simuler_calepinage`.
// Viewport 1440 × 900 (ACAL490) ; 390 × 844 pour les lignes de pertes (ACAL444).
import { readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { RACINE } from './_enregistrement.js'
import { API_DJANGO, assurerSessionPage, lireJson } from '../helpers.js'

const etape = groupe('ACAL', [
  'ACAL392', 'ACAL393', 'ACAL394', 'ACAL395', 'ACAL396', 'ACAL397', 'ACAL398', 'ACAL399', 'ACAL400', 'ACAL403',
  'ACAL405', 'ACAL406', 'ACAL407', 'ACAL408', 'ACAL409', 'ACAL410', 'ACAL412', 'ACAL413', 'ACAL414', 'ACAL415',
  'ACAL416', 'ACAL417', 'ACAL419', 'ACAL420', 'ACAL422', 'ACAL443', 'ACAL444', 'ACAL446', 'ACAL448', 'ACAL453',
  'ACAL469', 'ACAL475', 'ACAL488',
])
fermerDjangoApresTout()
test.describe.configure({ timeout: 900_000 })
test.use({ viewport: { width: 1440, height: 900 }, actionTimeout: 60_000 })
const INIT = () => {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
}
test.beforeEach(async ({ page }) => {
  await page.addInitScript(INIT)
  await assurerSessionPage(page)
})

const CAL = `${API_DJANGO}/calepinage`
const T = { timeout: 120_000 }
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()
const chiffres = (s) => Number(String(s).replace(/[^\d]/g, '')) || 0
const pan = (doc, id) => (doc?.zones || []).find((z) => z.id === id)

const PIN = { lat: 33.5731, lng: -7.5898 }
const PAN_A = [[-7.5899, 33.5732], [-7.5897, 33.5732], [-7.5897, 33.5730], [-7.5899, 33.5730]]
const toitPlat = (extra = {}) => ({
  version: 2, pin: PIN, activeAreaId: 'z1',
  zones: [{ id: 'z1', label: 'Toit plat', vertices: PAN_A, roofType: 'flat', pitchDeg: 15, facingAzimuthDeg: 180, ...extra }],
})
const vierge = () => ({ version: 2, pin: PIN, zones: [] })
/** 24 valeurs kWh/h (CALX255 `consumption.courbe24`) : 12 kWh/jour, la courbe de charge de la preuve. */
const COURBE24 = Array.from({ length: 24 }, (_, h) => (h >= 8 && h < 20 ? 0.75 : 0.25))

/** Lead (facture 3 000) + calepinage portant `layout`, posés au shell Django (patron acal4/acal6). */
async function calepinageAvec(tag, layout) {
  const m = marque()
  return py(`import json
from decimal import Decimal as D
from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
from apps.ventes.domain.geometrie import layout_hash
co = U.objects.get(username='demo_admin').company
lead = Lead.objects.create(company=co, nom='ACC ${tag} ${m}', ville='Casablanca', type_installation='residentiel', facture_hiver=D('3000'))
lay = json.loads(${JSON.stringify(JSON.stringify(layout))})
c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC ${tag} ${m}', roof_layout=lay, layout_hash=layout_hash(lay))
sortie({'id': c.pk, 'lead': lead.pk, 'company': co.pk})`)
}

async function poserDocument(id, layout) {
  return py(`import json
from apps.calepinage.models import Calepinage
from apps.ventes.domain.geometrie import layout_hash
lay = json.loads(${JSON.stringify(JSON.stringify(layout))})
c = Calepinage.objects.get(pk=${Number(id)})
c.roof_layout = lay
c.layout_hash = layout_hash(lay)
c.save(update_fields=['roof_layout', 'layout_hash'])
sortie(1)`)
}

async function nettoyer(...cals) {
  const ids = cals.filter(Boolean)
  if (!ids.length) return
  await py(`from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
Calepinage.objects.filter(pk__in=${JSON.stringify(ids.map((c) => Number(c.id)))}).delete()
Lead.objects.filter(pk__in=${JSON.stringify(ids.map((c) => Number(c.lead)))}).delete()
sortie(1)`).catch(() => undefined)
}

const lireLayout = async (request, id) => lireJson(await request.get(`${CAL}/calepinages/${id}/layout/`, T), 'layout')
const lireParcours = async (request, id) => lireJson(await request.get(`${CAL}/calepinages/${id}/parcours/`, T), 'parcours')

/** Montage ACAL377 : clé carte factice servie par `design-context`, style d'imagerie refusé (403, déclaré). */
async function carteRefusee(context, suivi) {
  await context.route(/\/calepinage\/calepinages\/\d+\/design-context\//, async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice-acal7', mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  suivi.attendre(/api\.maptiler\.com/, 403)
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({
    status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}',
  }))
}

/** ACAL398 : chaque « Enregistrer le calepinage » relance la simulation (POST `simuler/`, jamais forcée). Sur un
 *  projet d'essai sans réglage météo ni matériel désigné, le serveur la REFUSE (4xx, motif nommé) : refus attendu de
 *  la pile d'essai, déclaré ici. L'étape ACAL398 ne le déclare pas : elle lit le refus à l'écran. */
const refusSimulationAutoAttendu = (suivi) => suivi.attendre(/\/calepinage\/calepinages\/\d+\/simuler\/$/)

/** Disposition « studio » (ACAL402) : la carte est COLLÉE en haut ; la rangée d'outils du tracé (Terminer, ↶ ↷,
 *  Effacer, + Ajouter une zone, formes, cotes) est au-dessus d'elle dans le flux et passe SOUS la carte dès que la page
 *  défile. On revient en haut de la page avant de toucher un outil, comme le ferait l'utilisateur (clic réel). */
const enHaut = (page) => page.evaluate(() => window.scrollTo(0, 0))

const boutonEnregistrer = (page) => page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ })

/** Ouvre l'atelier (fond de repli) et attend la scène HYDRATÉE (+ la production chiffrée du pan actif). */
async function ouvrirAtelier(page, id, onglet = null, { production = true, hydrate = true } = {}) {
  await page.goto(`/calepinage/${id}${onglet ? `?onglet=${onglet}` : ''}`)
  const bouton = boutonEnregistrer(page)
  if (hydrate) {
    try {
      await expect(bouton, '« Enregistrer le calepinage » actif (scène hydratée)').toBeEnabled({ timeout: 240_000 })
    } catch (e) {
      console.log(`[atelier] scène non hydratée ; #rp9-status : « ${await page.locator('#rp9-status').innerText().catch(() => '?')} »`)
      throw e
    }
  }
  await expect(page.locator('#rp9-status'), '`#rp9-status` n’est plus « Chargement… »').not.toHaveText(/^Chargement/, { timeout: 240_000 })
  await expect(page.getByRole('alert').filter({ hasText: 'clé MapTiler' }), 'jamais « Carte indisponible »').toHaveCount(0)
  if (production) await expect(page.locator('#rp9-reco-prod'), 'carte Production chiffrée').toHaveText(/\d/, T)
  return bouton
}

/** « Enregistrer le calepinage » (écriture COMPLÈTE) puis relecture du document stocké. */
async function enregistrer(page, id, bouton = boutonEnregistrer(page)) {
  const ecrit = page.waitForResponse((x) => x.request().method() !== 'GET'
    && new URL(x.url()).pathname.endsWith(`/calepinages/${id}/layout/`), T)
  await bouton.click()
  const r = await ecrit
  expect(r.status(), `Enregistrer le calepinage → ${(await r.text()).slice(0, 300)}`).toBeLessThan(300)
  await expect(bouton).toBeEnabled({ timeout: 60_000 })
  await expect(page.getByTestId('cal-erreur-enregistrement')).toHaveCount(0)
  return (await lireLayout(page.request, id)).roof_layout
}

/** Réglage météo de la pile d'essai (pas un défaut produit — patron acal6) : `pluriannuel` 2020. Rend l'état d'avant
 *  de TOUTES les colonnes JSON de la ligne de réglages. */
async function sauverReglages() {
  return py(`from apps.calepinage.models import ParametresCalepinage
co = U.objects.get(username='demo_admin').company
p = ParametresCalepinage.objects.filter(company=co).order_by('id').first()
if p is None:
    sortie({'cree': True, 'avant': {}})
else:
    sortie({'cree': False, 'avant': {f.name: getattr(p, f.name) for f in p._meta.fields if f.get_internal_type() == 'JSONField'}})`)
}

async function restaurerReglages(etat) {
  if (!etat) return
  await py(`import json
from apps.calepinage.models import ParametresCalepinage
co = U.objects.get(username='demo_admin').company
p = ParametresCalepinage.objects.filter(company=co).order_by('id').first()
if p is not None:
    if ${etat.cree ? 'True' : 'False'}:
        p.delete()
    else:
        for k, v in json.loads(${JSON.stringify(JSON.stringify(etat.avant || {}))}).items():
            setattr(p, k, v)
        p.save()
sortie(1)`)
}

async function poserMeteo() {
  return py(`from apps.calepinage.models import ParametresCalepinage
co = U.objects.get(username='demo_admin').company
p = ParametresCalepinage.objects.filter(company=co).order_by('id').first()
if p is None:
    p = ParametresCalepinage.objects.create(company=co)
sim = dict(p.simulation or {})
sim['mode_meteo'] = {'valeur': 'pluriannuel', 'source': 'societe', 'reference': 'acceptation ACAL7'}
sim['fenetre_annees'] = {'valeur': '2020-2020', 'source': 'societe', 'reference': 'acceptation ACAL7'}
p.simulation = sim
p.save(update_fields=['simulation'])
sortie(1)`)
}

/** Retire `mode_meteo` (la simulation doit refuser en le NOMMANT). */
async function retirerMeteo() {
  return py(`from apps.calepinage.models import ParametresCalepinage
co = U.objects.get(username='demo_admin').company
p = ParametresCalepinage.objects.filter(company=co).order_by('id').first()
if p is not None:
    sim = dict(p.simulation or {})
    sim.pop('mode_meteo', None)
    p.simulation = sim
    p.save(update_fields=['simulation'])
sortie(1)`)
}

/** Module + onduleur RÉELS du catalogue désignés (patron acal6 `designerMateriel`). */
async function designerMateriel(id) {
  const r = await py(`from apps.calepinage.models import Calepinage
from apps.calepinage.services.chaines import CHAMPS_MODULE, CHAMPS_ONDULEUR
from apps.calepinage.services.electrique import enregistrer_entree
from apps.stock.selectors import produits_par_type_fiche_qs
from apps.stock.selectors_fiche_technique import produits_modules_qs, specs_for_produit
c = Calepinage.objects.get(pk=${Number(id)})
def premier(qs, champs):
    for p in qs:
        s = specs_for_produit(p) or {}
        if all(s.get(cle) not in (None, '') for cle, _ in champs):
            return {'id': p.pk, 'nom': p.nom}
    return None
module = premier(produits_modules_qs(c.company), CHAMPS_MODULE)
onduleur = premier(produits_par_type_fiche_qs(c.company, 'onduleur'), CHAMPS_ONDULEUR)
if module and onduleur:
    enregistrer_entree(c, {'module_produit': module['id'], 'onduleur_produit': onduleur['id']},
                       user=U.objects.get(username='demo_admin'))
sortie({'module': module, 'onduleur': onduleur})`)
  if (!r?.module || !r?.onduleur) throw new Error(`NON JOUABLE — catalogue sans fiche complète (${JSON.stringify(r)})`)
  return r
}

/** Le VRAI service de simulation, résultat ÉCRIT (forcé). PVGIS injoignable ⇒ NON JOUABLE, jamais un faux vert. */
async function simulerServeur(id) {
  let r
  try {
    r = await py(`from apps.calepinage.models import Calepinage
from apps.calepinage.services.simulation import simuler_calepinage, SimulationRefusee
c = Calepinage.objects.get(pk=${Number(id)})
try:
    simuler_calepinage(c, forcer=True)
    sortie({'ok': True})
except SimulationRefusee as refus:
    sortie({'refus': str(refus), 'champ': getattr(refus, 'champ', '')})`)
  } catch (e) {
    const m = String(e.message)
    if (/pvgis|ConnectionError|Timeout|Max retries|NameResolution|unreachable|injoignable/i.test(m)) {
      throw new Error(`NON JOUABLE sur ce runner — PVGIS injoignable : ${m.slice(-400)}`)
    }
    throw new Error(`simulation serveur en erreur : ${m.slice(-700)}`)
  }
  if (r?.refus) throw new Error(`simulation serveur REFUSÉE (${r.champ}) : ${r.refus}`)
}

/** Calepinage « simulé » de référence : toit plat pavé par l'atelier, matériel réel, courbe de charge déclarée
 *  (`consumption.courbe24`), simulation serveur écrite. Créé une fois par worker, RE-simulé à chaque étape. */
let SIMULE = null
async function calepinageSimule(page) {
  await poserMeteo()
  if (!SIMULE) {
    const cal = await calepinageAvec('ACAL7 simule', toitPlat())
    await designerMateriel(cal.id)
    const bouton = await ouvrirAtelier(page, cal.id)
    const doc = await enregistrer(page, cal.id, bouton)
    expect(pan(doc, 'z1')?.geometry?.panels?.length, 'toit pavé par l’atelier').toBeGreaterThan(0)
    await poserDocument(cal.id, { ...doc, consumption: { courbe24: COURBE24 } })
    SIMULE = cal
  }
  await simulerServeur(SIMULE.id)
  return SIMULE
}

// ════════════════════════════════════════════════════════════════════════════
// ACAL393 + ACAL394 + ACAL419 + ACAL408 — PA2.5 : un calepinage s'ouvre sur 5 étapes ; `?onglet=releve` ouvre « Relevé
// terrain » sous Toit ; le « ? » de Séries ouvre sa bulle et les flèches ne s'y arrêtent pas ; Mode expert coché,
// rechargé : tous les onglets du registre rangés sous les 5 étapes, puis décoché ; le guide se déroule étape par étape.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL393-ACAL394-ACAL419-ACAL408-rail-guide', ['ACAL393', 'ACAL394', 'ACAL419', 'ACAL408'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL393', toitPlat())
  try {
    await ouvrirAtelier(page, cal.id)
    const etapes = page.getByTestId('cal-rail-etapes')
    const LIBELLES = { toit: 'Toit', panneaux: 'Panneaux', electrique: 'Électrique', resultats: 'Résultats', documents: 'Documents' }
    await expect(etapes.getByRole('button'), 'cinq boutons d’étape').toHaveCount(5)
    for (const [cle, libelle] of Object.entries(LIBELLES)) {
      await expect(page.getByTestId(`cal-etape-${cle}`), `étape ${libelle}`).toContainText(libelle)
    }
    const expert = page.getByTestId('cal-mode-expert')
    await expect(expert, 'guidé par défaut').not.toBeChecked()
    const onglets = page.getByTestId('cal-rail-onglets').getByRole('tab')

    // Le registre `onglets.js` (lu dans le dépôt) : le nombre total d'onglets.
    const registre = readFileSync(join(RACINE, 'frontend/src/features/calepinage/atelier/onglets.js'), 'utf8')
    const total = (registre.match(/^\s*\{ cle: '/gm) || []).length
    expect(total, 'registre lu').toBeGreaterThanOrEqual(36)

    const compter = async () => {
      const parEtape = {}
      for (const cle of Object.keys(LIBELLES)) {
        await page.getByTestId(`cal-etape-${cle}`).click()
        await expect(page.getByTestId(`cal-etape-${cle}`)).toHaveAttribute('aria-current', 'step')
        parEtape[cle] = (await onglets.allInnerTexts()).map((t) => t.trim())
      }
      return parEtape
    }
    const guide = await compter()
    const nGuide = Object.values(guide).reduce((s, l) => s + l.length, 0)
    console.log(`[ACAL393] guidé : ${JSON.stringify(guide)} (${nGuide} onglets sur ${total})`)
    expect(nGuide, 'mode guidé : les seuls essentiels').toBeLessThan(total)

    // `?onglet=releve` (panneau expert) : ouvert quand même, sous Toit.
    await page.goto(`/calepinage/${cal.id}?onglet=releve`)
    await expect(page.getByTestId('cal-etape-toit'), 'Relevé terrain rangé sous Toit').toHaveAttribute('aria-current', 'step')
    await expect(page.getByTestId('cal-onglet-releve')).toHaveText('Relevé terrain')
    await expect(page.getByTestId('cal-onglet-releve')).toHaveAttribute('aria-selected', 'true')

    // ACAL419 — le « ? » de Séries : bulle ouverte ; les flèches passent d'onglet en onglet sans s'y arrêter.
    await page.goto(`/calepinage/${cal.id}?onglet=series`)
    const aideSeries = page.getByRole('button', { name: 'À quoi sert « Séries »' })
    await expect(aideSeries).toBeVisible(T)
    await aideSeries.click()
    await expect(page.getByText('Comparer la production mois par mois ou heure par heure.'), 'bulle de Séries').toBeVisible()
    await page.keyboard.press('Escape')
    await page.getByTestId('cal-onglet-series').focus()
    for (const touche of ['ArrowRight', 'ArrowRight', 'ArrowLeft', 'ArrowLeft', 'ArrowLeft']) {
      await page.keyboard.press(touche)
      const role = await page.evaluate(() => document.activeElement?.getAttribute('role'))
      expect(role, `${touche} : le focus reste sur un onglet (jamais sur une bulle)`).toBe('tab')
    }

    // ACAL394 — cocher, recharger : tous les onglets du registre sous les 5 étapes ; décocher.
    await expect(expert).toBeVisible()
    await expert.check()
    await page.reload()
    await expect(page.getByTestId('cal-mode-expert'), 'mémorisé après rechargement').toBeChecked(T)
    const tous = await compter()
    const nExpert = Object.values(tous).reduce((s, l) => s + l.length, 0)
    console.log(`[ACAL394] expert : ${nExpert} onglets (registre ${total})`)
    expect(nExpert, 'mode expert : chaque onglet du registre une fois').toBe(total)
    expect(new Set(Object.values(tous).flat()).size, 'aucun onglet en double').toBe(total)

    // ACAL408 — le guide (section Calepinage) déroulé une étape à la fois : ses listes = les onglets à l'écran.
    const doc = readFileSync(join(RACINE, 'docs/GUIDE_UTILISATEUR_ERP.md'), 'utf8')
    const section = doc.slice(doc.indexOf('### Calepinage'), doc.indexOf('\n### ', doc.indexOf('### Calepinage') + 5))
    for (const [n, cle] of [[1, 'toit'], [2, 'panneaux'], [3, 'electrique'], [4, 'resultats'], [5, 'documents']]) {
      const ligne = section.split('\n').find((l) => l.startsWith(`- **${n} ${LIBELLES[cle]}**`))
      expect(ligne, `guide : ligne de l’étape ${n} ${LIBELLES[cle]}`).toBeTruthy()
      const liste = ligne.split(' : ')[1].split('.')[0].split(',').map((s) => s.trim())
      expect(new Set(liste), `guide étape ${n} = onglets à l’écran (expert)`).toEqual(new Set(tous[cle]))
    }
    expect(section, 'le guide dit la simulation automatique et le brouillon d’un autre poste')
      .toMatch(/Brouillon d'un autre poste/)

    await page.getByTestId('cal-mode-expert').uncheck()
    await page.reload()
    await expect(page.getByTestId('cal-mode-expert'), 'décoché et mémorisé').not.toBeChecked(T)
    await page.waitForLoadState('networkidle').catch(() => undefined) // aucun appel en vol vers le calepinage nettoyé
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL407 + ACAL409 — PA2.5 : `/calepinage/<id>/horizon` ⇒ `?onglet=horizon`, panneau Horizon ; « Comparer les
// variantes » et « Photos du site » ouvrent un onglet DANS l'atelier (plus de page à part).
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL407-ACAL409-adresses-onglets', ['ACAL407', 'ACAL409'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL407', toitPlat())
  try {
    await page.goto(`/calepinage/${cal.id}/horizon`)
    await expect(page, 'redirigé vers ?onglet=horizon').toHaveURL(new RegExp(`/calepinage/${cal.id}\\?onglet=horizon$`), T)
    await expect(page.getByTestId('cal-onglet-panneau').getByTestId('cal-horizon'), 'panneau Horizon').toBeVisible(T)
    await page.goto(`/calepinage/${cal.id}/variantes`)
    await expect(page).toHaveURL(new RegExp(`/calepinage/${cal.id}\\?onglet=variantes$`), T)

    await ouvrirAtelier(page, cal.id)
    await page.getByTestId('cal-lien-variantes').click()
    await expect(page).toHaveURL(new RegExp(`/calepinage/${cal.id}\\?onglet=variantes$`))
    await expect(page.getByTestId('cal-onglet-variantes'), 'onglet « Comparer les variantes » ouvert dans le rail').toHaveAttribute('aria-selected', 'true')
    await expect(page.getByTestId('cal-onglet-panneau'), 'contenu dans le panneau de l’atelier').toContainText('Comparer les variantes', T)
    await expect(page.getByTestId('cal-rail-etapes'), 'toujours dans l’atelier').toBeVisible()
    await page.getByTestId('cal-lien-photos-calage').click()
    await expect(page).toHaveURL(new RegExp(`/calepinage/${cal.id}\\?onglet=photos$`))
    await expect(page.getByTestId('cal-onglet-photos')).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByTestId('cal-onglet-panneau').getByTestId('cal-photo-calage'), 'Photos du site dans l’atelier').toBeVisible(T)
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL399 + ACAL400 — PA2.5 : en haut de la page, le bouton d'enregistrement se voit ; une modification ⇒
// « Modifications non enregistrées » et un brouillon SERVEUR ; un AUTRE navigateur (même compte, stockage vide) voit
// le bandeau « Brouillon d'un autre poste » ; enregistrer ⇒ « Enregistré à HH:MM ».
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL399-ACAL400-barre-brouillon', ['ACAL399', 'ACAL400'], async ({ page, context, suivi, testInfo }) => {
  refusSimulationAutoAttendu(suivi)
  const etatPropre = await context.storageState()
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL399', toitPlat())
  let autre = null
  try {
    const bouton = await ouvrirAtelier(page, cal.id)
    await page.evaluate(() => window.scrollTo(0, 0))
    await expect(bouton, 'défilé tout en haut : le bouton se voit').toBeInViewport()

    const brouillon = page.waitForResponse((x) => x.request().method() === 'PUT'
      && new URL(x.url()).pathname.endsWith(`/calepinages/${cal.id}/brouillon/`), { timeout: 90_000 })
    await enHaut(page)
    await page.locator('#rp9-add-area').click()
    await expect(page.getByTestId('cal-etat-enregistrement')).toHaveText('Modifications non enregistrées', T)
    const rb = await brouillon
    expect(rb.status(), `PUT brouillon/ → ${(await rb.text()).slice(0, 200)}`).toBeLessThan(300)

    // Un autre navigateur, même compte, sans le stockage local de celui-ci.
    autre = await context.browser().newContext({
      storageState: etatPropre, baseURL: testInfo.project.use.baseURL, viewport: { width: 1440, height: 900 }, serviceWorkers: 'block',
    })
    await autre.addInitScript(INIT)
    await carteRefusee(autre, suivi)
    const p2 = suivi.surveiller(await autre.newPage())
    await p2.goto(`/calepinage/${cal.id}`)
    const bandeau = p2.getByTestId('cal-brouillon-bandeau')
    await expect(bandeau, 'bandeau de reprise dans l’autre navigateur').toBeVisible({ timeout: 240_000 })
    await expect(bandeau).toContainText('Brouillon d’un autre poste')
    await expect(p2.getByTestId('cal-brouillon-reprendre')).toBeVisible()
    await autre.close()
    autre = null

    await enregistrer(page, cal.id, bouton)
    const etat = page.getByTestId('cal-etat-enregistrement')
    await expect(etat).toHaveText(/^Enregistré à \d{1,2}[:h]\d{2}$/, T)
    console.log(`[ACAL399] ${await etat.innerText()}`)
    await page.evaluate(() => window.scrollTo(0, 0))
    await expect(bouton, 'après enregistrement, toujours visible en haut').toBeInViewport()
  } finally {
    if (autre) await autre.close().catch(() => undefined)
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL406 — PA2.5 : fiche d'un calepinage portant un champ personnalisé : libellé lisible, jamais le code ni du JSON.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL406-fiche-champ-personnalise', ['ACAL406'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL406', toitPlat())
  const code = `acc_toit_${marque().toLowerCase()}`.slice(0, 40)
  await py(`from apps.customfields.models import CustomFieldDef
from apps.calepinage.models import Calepinage
co = U.objects.get(username='demo_admin').company
CustomFieldDef.objects.create(company=co, module='calepinage', code='${code}', libelle='Toit vu sur place', type='boolean')
c = Calepinage.objects.get(pk=${cal.id})
c.custom_data = {'${code}': True}
c.save(update_fields=['custom_data'])
sortie(1)`)
  try {
    await ouvrirAtelier(page, cal.id)
    const champ = page.getByTestId('cal-fiche-custom_data')
    await expect(champ, 'libellé lisible + Oui').toContainText('Toit vu sur place : Oui', T)
    await expect(champ, 'jamais le code interne').not.toContainText(code)
    await expect(champ, 'jamais de JSON brut').not.toContainText('{')
  } finally {
    await py(`from apps.customfields.models import CustomFieldDef
CustomFieldDef.objects.filter(code='${code}').delete()
sortie(1)`).catch(() => undefined)
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL488 — PA2 : sans clé, l'onglet « Détection du toit » dit l'indisponibilité et n'offre AUCUN bouton.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL488-detection-toit-sans-cle', ['ACAL488'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL488', toitPlat())
  try {
    const dispo = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/detection-toit/`, T), 'detection-toit')
    console.log(`[ACAL488] GET detection-toit/ → ${JSON.stringify(dispo).slice(0, 300)}`)
    expect(dispo?.disponible ?? dispo?.available, 'serveur : détection indisponible sans clé').toBeFalsy()
    await ouvrirAtelier(page, cal.id, 'detection-toit')
    await expect(page.getByTestId('cal-onglet-detection-toit')).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByTestId('cal-detection-indisponible'), 'indisponibilité dite').toBeVisible(T)
    await expect(page.getByTestId('cal-detection-carte'), 'aucun bouton « Détecter le toit »').toHaveCount(0)
    await expect(page.getByTestId('cal-detection-choisir'), 'aucun bouton d’image').toHaveCount(0)
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL415 — atelier, ⌘K : « obstacle » propose « Ajouter un obstacle » ; « horizon » ouvre l'onglet Horizon.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL415-palette-commandes', ['ACAL415'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL415', toitPlat())
  try {
    await ouvrirAtelier(page, cal.id)
    await page.keyboard.press('Control+k')
    const champ = page.getByPlaceholder('Rechercher ou lancer une action…')
    await expect(champ, 'palette ⌘K ouverte').toBeVisible()
    await champ.fill('obstacle')
    await expect(page.getByText('Ajouter un obstacle', { exact: true }), '« Ajouter un obstacle » proposé').toBeVisible()
    await champ.fill('horizon')
    const ouvrir = page.getByText('Ouvrir Horizon lointain', { exact: true })
    await expect(ouvrir, '« Ouvrir Horizon lointain » proposé').toBeVisible()
    await ouvrir.click()
    await expect(page).toHaveURL(/[?&]onglet=horizon/)
    await expect(page.getByTestId('cal-onglet-panneau').getByTestId('cal-horizon'), 'onglet Horizon ouvert').toBeVisible(T)
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL414 — atelier, « ? » : la fenêtre d'aide liste les touches du TRACÉ et de la DISPOSITION (une seule table).
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL414-aide-raccourcis', ['ACAL414'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL414', toitPlat())
  try {
    await ouvrirAtelier(page, cal.id)
    await expect(page.getByTestId('cal-raccourcis-bouton'), 'aide de l’atelier montée').toBeVisible()
    await enHaut(page)
    await page.locator('#rp9-status').click()
    await page.keyboard.press('?')
    // La fenêtre que « ? » ouvre réellement (quelle qu'elle soit) : elle doit lister les touches de l'atelier.
    const aide = page.locator('[role="dialog"]').filter({ hasText: /raccourci/i }).last()
    await expect(aide, 'une fenêtre d’aide ouverte par « ? »').toBeVisible()
    console.log(`[ACAL414] « ? » ouvre : ${(await aide.innerText()).replace(/\s+/g, ' ').slice(0, 1500)}`)
    console.log(`[ACAL414] #rp9-status : ${await page.locator('#rp9-status').innerText()}`)
    console.log(`[ACAL414] fenêtre de l'atelier (cal-raccourcis-aide) ouverte : ${await page.getByTestId('cal-raccourcis-aide').count()}`)
    await expect(page.getByTestId('cal-raccourcis-aide'), '« ? » ouvre la fenêtre de l’atelier').toBeVisible()
    await expect(aide, 'touche d’outil de l’atelier (T)').toContainText('Outil tracé de toit')
    await expect(aide, 'touches du TRACÉ (table unique)').toContainText('Poser un sommet du contour')
    await expect(aide, 'touches de la DISPOSITION (table unique)').toContainText('Annuler la dernière modification de la disposition')
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL420 + ACAL422 + ACAL410 — atelier vierge : carte « Localisez le toit », un clic ⇒ « Un clic par coin » ;
// 12 × 8 « Créer le toit » ⇒ rectangle fermé et pavé ; puces « Forme du toit » : « 2 pans » puis « 4 pans ».
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL420-ACAL422-ACAL410-trace-vierge', ['ACAL420', 'ACAL422', 'ACAL410'], async ({ page, context, suivi }) => {
  refusSimulationAutoAttendu(suivi)
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL420', vierge())
  let cal4 = null
  try {
    await ouvrirAtelier(page, cal.id, null, { production: false, hydrate: false })
    const aide = page.locator('#rp9-etat-vide')
    await expect(aide, 'atelier vierge : « Localisez le toit »').toHaveText(/^1 · Localisez le toit/, T)
    const carte = page.locator('#rp9-map')
    const boite = await carte.boundingBox()
    await carte.click({ position: { x: boite.width / 2, y: boite.height / 2 + 60 } })
    await expect(aide, 'un clic : « Un clic par coin »').toHaveText(/^2 · Un clic par coin/)
    await enHaut(page)
    await page.locator('#rp9-undo-point').click()

    const cotes = page.locator('#rp9-toit-cotes')
    await expect(cotes, 'toit par cotes offert tant qu’aucun contour').toBeVisible(T)
    await cotes.getByLabel('Longueur (m)').fill('12')
    await cotes.getByLabel('Largeur (m)').fill('8')
    await cotes.getByLabel('Orientation (°)').fill('0')
    await enHaut(page)
    await cotes.getByRole('button', { name: 'Créer le toit' }).click()
    await expect(page.locator('#rp9-status')).toContainText('Toit créé : 12 × 8 m', T)
    await expect(aide, 'contour fermé : la carte d’aide disparaît').toBeHidden()
    await expect(page.locator('#rp9-area-value'), 'surface ≈ 96 m²').toContainText('96', T)
    await expect(page.locator('#rp9-reco-prod'), 'rectangle pavé : production chiffrée').toHaveText(/\d/, T)

    const formes = page.locator('#rp9-formes-toit')
    await expect(formes, 'puces « Forme du toit » sur contour fermé').toBeVisible()
    const zones = page.locator('#rp9-areas-list > li')
    await enHaut(page)
    await formes.getByRole('button', { name: '2 pans', exact: true }).click()
    await expect(page.locator('#rp9-status')).toContainText('Toit découpé en 2 pans', T)
    await expect(zones, 'liste des zones : 2 pans').toHaveCount(2)
    const doc2 = await enregistrer(page, cal.id)
    console.log(`[ACAL410] « 2 pans » enregistré : ${(doc2.zones || []).map((z) => `${z.id}:${z.roofType}:${z.pitchDeg}:${z.facingAzimuthDeg}`).join(' ')}`)
    expect(doc2.zones, 'deux pans enregistrés').toHaveLength(2)
    expect(doc2.zones.every((z) => z.roofType === 'pitched'), 'pans en pente').toBe(true)

    // « 4 pans » sur un second rectangle 12 × 8 tracé de même.
    cal4 = await calepinageAvec('ACAL410 4p', vierge())
    await ouvrirAtelier(page, cal4.id, null, { production: false, hydrate: false })
    await expect(cotes).toBeVisible(T)
    await cotes.getByLabel('Longueur (m)').fill('12')
    await cotes.getByLabel('Largeur (m)').fill('8')
    await cotes.getByLabel('Orientation (°)').fill('0')
    await enHaut(page)
    await cotes.getByRole('button', { name: 'Créer le toit' }).click()
    await expect(page.locator('#rp9-status')).toContainText('Toit créé : 12 × 8 m', T)
    await enHaut(page)
    await formes.getByRole('button', { name: '4 pans', exact: true }).click()
    await expect(page.locator('#rp9-status')).toContainText('Toit découpé en 4 pans', T)
    const doc4 = await enregistrer(page, cal4.id)
    console.log(`[ACAL410] « 4 pans » : liste ${await zones.count()} ligne(s) ${JSON.stringify(await zones.allInnerTexts())} ; enregistré : ${(doc4.zones || []).map((z) => `${z.id}:${z.roofType}:${z.pitchDeg}:${z.facingAzimuthDeg}`).join(' ')}`)
    expect(doc4.zones, 'quatre pans enregistrés').toHaveLength(4)
    await expect(zones, 'liste des zones à jour : 4 pans').toHaveCount(4)
  } finally {
    await nettoyer(cal, cal4)
  }
})

/** Atelier vierge → toit 12 × 8 par cotes → « Toit en pente / tuiles » : un NOUVEAU pan en pente. */
async function nouveauPanEnPente(page) {
  const cotes = page.locator('#rp9-toit-cotes')
  await expect(cotes).toBeVisible(T)
  await cotes.getByLabel('Longueur (m)').fill('12')
  await cotes.getByLabel('Largeur (m)').fill('8')
  await cotes.getByLabel('Orientation (°)').fill('0')
  await enHaut(page)
  await cotes.getByRole('button', { name: 'Créer le toit' }).click()
  await expect(page.locator('#rp9-status')).toContainText('Toit créé', T)
  await enHaut(page)
  await page.locator('[data-rooftype="pitched"]').click()
  await expect(page.locator('#rp9-pitched-controls')).toBeVisible()
}

// ════════════════════════════════════════════════════════════════════════════
// ACAL417 — atelier, nouveau pan : « 22° par défaut — à confirmer » et face « à confirmer », puces non pressées ;
// clic ~30° ⇒ pressée, mention levée ; enregistrer, rouvrir ⇒ confirmée.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL417-hypotheses-a-confirmer', ['ACAL417'], async ({ page, context, suivi }) => {
  refusSimulationAutoAttendu(suivi)
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL417', vierge())
  try {
    await ouvrirAtelier(page, cal.id, null, { production: false, hydrate: false })
    await nouveauPanEnPente(page)
    await expect(page.locator('#rp9-pitch-note'), 'pente de départ dite « à confirmer »').toHaveText('Pente : 22° par défaut — à confirmer')
    await expect(page.locator('#rp9-facing-note'), 'face de départ dite « à confirmer »').toContainText('à confirmer')
    await expect(page.locator('[data-pitch="22"]'), 'puce 22° NON pressée').toHaveAttribute('aria-pressed', 'false')
    await expect(page.locator('[data-facing="180"]'), 'puce Sud NON pressée').toHaveAttribute('aria-pressed', 'false')
    await enHaut(page)
    await page.locator('[data-pitch="30"]').click()
    await expect(page.locator('[data-pitch="30"]'), '~30° pressée').toHaveAttribute('aria-pressed', 'true')
    await expect(page.locator('#rp9-pitch-note'), 'mention de pente levée').toHaveText('')
    const doc = await enregistrer(page, cal.id)
    const z = (doc.zones || []).find((x) => x.id === doc.activeAreaId) || doc.zones?.[0]
    console.log(`[ACAL417] pan enregistré : pitchDeg ${z?.pitchDeg} pitchSource ${JSON.stringify(z?.pitchSource)}`)
    expect(z?.pitchDeg, 'pente 30° enregistrée').toBe(30)
    expect(z?.pitchSource, 'pente CONFIRMÉE (source écrite)').toBeTruthy()
    await ouvrirAtelier(page, cal.id, null, { production: false })
    await expect(page.locator('#rp9-pitch-note'), 'rouvert : aucune mention de pente').toHaveText('')
    expect((await lireLayout(page.request, cal.id)).roof_layout.zones.find((x) => x.id === z.id)?.pitchSource).toEqual(z.pitchSource)
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL416 — atelier, aide « Je ne connais pas la pente » : 50 % ⇒ 27° ; enregistrer ; onglet Pente :
// « En pourcentage » 50.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL416-aide-pente-pourcentage', ['ACAL416'], async ({ page, context, suivi }) => {
  refusSimulationAutoAttendu(suivi)
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL416', vierge())
  try {
    await ouvrirAtelier(page, cal.id, null, { production: false, hydrate: false })
    await nouveauPanEnPente(page)
    const pct = page.locator('#rp9-pente-aide-pourcentage')
    await expect(pct, 'aide de pente sur la carte').toBeVisible()
    await pct.fill('50')
    await pct.dispatchEvent('change')
    await expect(page.locator('#rp9-pitch-value'), '50 % ⇒ 27°').toHaveText('27°')
    const doc = await enregistrer(page, cal.id)
    const z = (doc.zones || []).find((x) => x.id === doc.activeAreaId) || doc.zones?.[0]
    console.log(`[ACAL416] pan enregistré : pitchDeg ${z?.pitchDeg} pitchSource ${JSON.stringify(z?.pitchSource)}`)
    expect(z?.pitchSource?.mode, 'source de pente gardée : pourcentage').toBe('pourcentage')
    expect(Number(z?.pitchSource?.pourcentage)).toBe(50)
    await page.goto(`/calepinage/${cal.id}?onglet=pente`)
    await expect(page.getByTestId('cal-pente')).toBeVisible(T)
    await expect(page.locator('#cal-pente-pourcentage'), 'onglet Pente : « En pourcentage » 50').toHaveValue('50', T)
    await expect(page.getByTestId('cal-pente-source')).toContainText('pourcentage')
  } finally {
    await nettoyer(cal)
  }
})

const OBSTACLES = [
  { id: 'obs-1', centerLng: -7.58985, centerLat: 33.57312, lengthM: 0.8, widthM: 0.8, type: 'cheminee', heightM: 1.2 },
  { id: 'obs-2', centerLng: -7.58978, centerLat: 33.57310, lengthM: 0.8, widthM: 0.8, type: 'cheminee', heightM: 1.2 },
  { id: 'obs-3', centerLng: -7.58975, centerLat: 33.57306, lengthM: 0.8, widthM: 0.8, type: 'cheminee', heightM: 1.2 },
]
const nObstacles = (doc) => (pan(doc, 'z1')?.obstacles || []).length

async function toutEffacerObstacles(page) {
  const effacer = page.locator('#rp9-obstacle-clear')
  if (!(await effacer.isVisible())) await page.locator('#rp9-obstacle').click()
  await expect(effacer, '« Tout effacer » (obstacles)').toBeVisible()
  await effacer.click()
}

// ════════════════════════════════════════════════════════════════════════════
// ACAL413 + ACAL412 — atelier, 3 obstacles, « Tout effacer », « Annuler » du bandeau ⇒ rendus ; Annuler/Rétablir
// joignables hors de la disposition : Ctrl+Z, ↷, ↶. (ACAL412 : le geste annulé est l'effacement des obstacles — le
// glissé d'un sommet n'est pas automatisable sur le fond de repli ; même pile d'historique de l'atelier.)
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL413-ACAL412-annuler-effacements', ['ACAL413', 'ACAL412'], async ({ page, context, suivi }) => {
  refusSimulationAutoAttendu(suivi)
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL413', toitPlat({ obstacles: OBSTACLES }))
  try {
    let bouton = await ouvrirAtelier(page, cal.id)
    expect(nObstacles(await enregistrer(page, cal.id, bouton)), 'trois obstacles relus').toBe(3)
    bouton = await ouvrirAtelier(page, cal.id)
    await toutEffacerObstacles(page)
    const bandeau = page.locator('#rp9-bandeau-annuler')
    await expect(bandeau, 'bandeau d’annulation').toBeVisible()
    await enHaut(page)
    await bandeau.getByRole('button', { name: 'Annuler', exact: true }).click()
    await expect(bandeau).toHaveCount(0)
    expect(nObstacles(await enregistrer(page, cal.id, bouton)), '« Annuler » du bandeau : les 3 obstacles rendus').toBe(3)

    // ACAL412 — Ctrl+Z hors de la disposition, puis ↷ et ↶ (boutons de la barre du toit).
    bouton = await ouvrirAtelier(page, cal.id)
    await toutEffacerObstacles(page)
    await enHaut(page)
    await page.locator('#rp9-status').click()
    await page.keyboard.press('Control+z')
    await expect(page.locator('#rp9-status'), 'Ctrl+Z').toContainText('Action annulée.')
    await enHaut(page)
    await page.locator('button', { hasText: /^↷$/ }).click()
    await expect(page.locator('#rp9-status'), '↷').toContainText('Action rétablie.')
    expect(nObstacles(await enregistrer(page, cal.id, bouton)), '↷ : effacement rétabli').toBe(0)
    await enHaut(page)
    await page.locator('button', { hasText: /^↶$/ }).click()
    await expect(page.locator('#rp9-status'), '↶').toContainText('Action annulée.')
    expect(nObstacles(await enregistrer(page, cal.id, bouton)), '↶ : obstacles rendus').toBe(3)
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL413 — atelier, « Effacer » avec un contour et 3 obstacles : la question NOMME ce qui sera perdu ; refusée,
// rien n'est effacé (« Garder ») ; « Effacer » efface. Jamais un dialogue natif (oracle 4).
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL413-effacer-question-nommee', ['ACAL413'], async ({ page, context, suivi }) => {
  refusSimulationAutoAttendu(suivi)
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL413 q', toitPlat({ obstacles: OBSTACLES }))
  try {
    const bouton = await ouvrirAtelier(page, cal.id)
    const natives = []
    page.on('dialog', (d) => natives.push(d.message()))
    await enHaut(page)
    await page.locator('#rp9-clear').click()
    const question = page.locator('#rp9-question-effacer')
    await expect(question, 'question posée DANS l’atelier').toBeVisible()
    await expect(question).toHaveAttribute('role', 'alertdialog')
    await expect(page.locator('#rp9-question-effacer-texte'), 'la question nomme le pan et les obstacles').toHaveText('Effacer 1 pan et 3 obstacles ?')
    console.log(`[ACAL413] question : « ${await page.locator('#rp9-question-effacer-texte').innerText()} »`)
    expect(natives, 'aucun dialogue natif').toEqual([])
    // « Garder » : rien n'est effacé.
    await enHaut(page)
    await question.getByRole('button', { name: 'Garder', exact: true }).click()
    await expect(question).toHaveCount(0)
    const doc = await enregistrer(page, cal.id, bouton)
    expect(doc.zones, '« Garder » : rien n’est effacé').toHaveLength(1)
    expect(nObstacles(doc)).toBe(3)
    // « Effacer » : le tracé part, l'atelier redevient vierge.
    await enHaut(page)
    await page.locator('#rp9-clear').click()
    await expect(question).toBeVisible()
    await enHaut(page)
    await question.getByRole('button', { name: 'Effacer', exact: true }).click()
    await expect(question).toHaveCount(0)
    await expect(page.locator('#rp9-etat-vide'), '« Effacer » : contour effacé, atelier vierge').toHaveText(/^1 · Localisez le toit/, T)
    expect(natives, 'aucun dialogue natif').toEqual([])
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL392 + ACAL395 + ACAL443 + ACAL453 + ACAL446 + ACAL444 — PA2.5 sur un calepinage SIMULÉ avec courbe de charge :
// une seule ligne « norme électrique » ; Électrique « n points à régler » = lignes `electrique` ; Production : un
// héros puis le détail replié ; graphique mensuel ; journée type de juin à deux lignes ; Pertes en lignes, sans
// défilement horizontal à 1440 puis 390 px, étapes omises lisibles.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL392-ACAL395-ACAL443-ACAL453-ACAL446-ACAL444-resultats', ['ACAL392', 'ACAL395', 'ACAL443', 'ACAL453', 'ACAL446', 'ACAL444'], async ({ page, context, suivi }) => {
  const reglages = await sauverReglages()
  try {
    await carteRefusee(context, suivi)
    const cal = await calepinageSimule(page)
    const parcours = await lireParcours(page.request, cal.id)
    console.log(`[ACAL392] parcours : ${JSON.stringify(parcours)}`)
    const normes = parcours.manque.filter((m) => m.code === 'norme_absente')
    expect(normes, 'une seule ligne « norme électrique » (regroupée)').toHaveLength(1)
    expect(normes[0].cible, 'cible : réglages, champ norme').toEqual({ onglet: 'reglages', champ: 'norme' })

    // ACAL395 — Électrique en un écran : synthèse = lignes `electrique` de « ce qui manque ».
    await page.goto(`/calepinage/${cal.id}?onglet=verdict-electrique`)
    await expect(page.getByTestId('cal-etape-electrique-ecran')).toBeVisible(T)
    const etatElec = parcours.etapes.find((e) => e.cle === 'electrique')?.etat
    const n = parcours.manque.filter((m) => m.etape === 'electrique').length
    const attendu = etatElec === 'fait' ? 'Conforme' : (n > 0 ? `${n} point${n > 1 ? 's' : ''} à régler` : 'Aucun point à régler pour l’instant')
    await expect(page.getByTestId('cal-electrique-synthese'), `synthèse (état ${etatElec}, ${n} lignes)`).toHaveText(attendu, T)
    await expect(page.locator('[data-testid^="cal-electrique-section-"]'), 'sept sections repliables').toHaveCount(7)

    // ACAL443 / ACAL453 / ACAL446 — Production.
    await page.goto(`/calepinage/${cal.id}?onglet=production`)
    const heros = page.getByTestId('acal443-heros')
    await expect(heros, 'un chiffre héros').toBeVisible(T)
    await expect(heros).toContainText('Production annuelle (P50)')
    await expect(heros).toHaveText(/\d/)
    await expect(page.getByTestId('acal443-non-calcule'), 'jamais simulé ET « non calculé »').toHaveCount(0)
    const details = page.getByTestId('acal443-details')
    await expect(details, 'détail statistique présent').toBeVisible()
    expect(await details.evaluate((e) => e.open), 'P75/P90/P95 repliés').toBe(false)
    for (const l of ['Puissance installée', 'Productible', 'Pertes totales']) await expect(page.getByTestId('cal236-total')).toContainText(l)
    const mensuel = page.getByTestId('acal453-graphique')
    await expect(mensuel, 'graphique mensuel Production / Consommation / Autoconsommée').toBeVisible(T)
    await expect(mensuel.locator('.recharts-bar-rectangle').first()).toBeVisible()
    const journee = page.getByTestId('cal-tapis-journee-type')
    await expect(journee, 'journée type').toBeVisible(T)
    await page.getByTestId('cal-tapis-mois-6').click()
    await expect(journee.locator('.recharts-line'), 'juin : production ET consommation').toHaveCount(2, T)
    await expect(journee).toContainText('Consommation (kWh)')
    await expect(page.getByTestId('acal446-sans-charge')).toHaveCount(0)

    // ACAL444 — Pertes en lignes, sans défilement horizontal.
    await page.goto(`/calepinage/${cal.id}?onglet=pertes`)
    const lignes = page.getByTestId('acal444-lignes')
    await expect(lignes, 'diagramme de pertes en lignes').toBeVisible(T)
    const nLignes = await lignes.locator(':scope > li').count()
    const omises = lignes.locator(':scope > li[data-omise="true"]')
    console.log(`[ACAL444] ${nLignes} lignes, ${await omises.count()} omises`)
    expect(nLignes, 'une ligne par étape de la chaîne').toBeGreaterThan(3)
    const sansDefilement = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
    expect(await sansDefilement(), '1440 px : aucun défilement horizontal').toBe(true)
    if (await omises.count()) await expect(omises.first(), 'étape omise lisible').toBeVisible()
    await page.setViewportSize({ width: 390, height: 844 })
    await page.reload()
    await expect(lignes).toBeVisible(T)
    await expect.poll(sansDefilement, { message: '390 px : aucun défilement horizontal' }).toBe(true)
    if (await omises.count()) {
      await omises.first().scrollIntoViewIfNeeded()
      await expect(omises.first(), '390 px : étape omise lisible').toBeVisible()
    }
    await page.setViewportSize({ width: 1440, height: 900 })
  } finally {
    await restaurerReglages(reglages)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL397 — PA2.5 : onglet Production : cliquer la ligne de la norme ouvre les réglages À LA NORME.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL397-manque-ouvre-le-champ', ['ACAL397'], async ({ page, context, suivi }) => {
  const reglages = await sauverReglages()
  try {
    await carteRefusee(context, suivi)
    const cal = await calepinageSimule(page)
    await page.goto(`/calepinage/${cal.id}?onglet=production`)
    const ligne = page.getByTestId('calx48-manque-ligne').filter({ hasText: /norme/i })
    await expect(ligne, 'ligne « norme électrique » dans « ce qui manque »').toHaveCount(1, T)
    await ligne.click()
    await expect(page, 'réglages, ancre de la norme').toHaveURL(/\/calepinage\/reglages#norme$/)
    const champ = page.locator('#norme')
    await expect(champ, 'le champ de la norme existe et est montré').toBeVisible(T)
    await expect(champ, 'focalisé').toBeFocused()
  } finally {
    await restaurerReglages(reglages)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL396 — PA2.5 : panneau Pertes unifié : enregistrer un poste ⇒ « simulation périmée » dans le diagramme, sans
// changer d'onglet.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL396-pertes-unifie', ['ACAL396'], async ({ page, context, suivi }) => {
  const reglages = await sauverReglages()
  try {
    await carteRefusee(context, suivi)
    const cal = await calepinageSimule(page)
    await page.goto(`/calepinage/${cal.id}?onglet=pertes`)
    const unifie = page.getByTestId('cal-pertes-unifie')
    await expect(unifie.getByTestId('cal143-panneau'), 'diagramme').toBeVisible(T)
    await expect(unifie.getByTestId('cal-pertes-panel'), 'édition des postes, même panneau').toBeVisible(T)
    await expect(unifie.getByTestId('calx48-perime'), 'simulation à jour au départ').toHaveCount(0)
    const poste = unifie.locator('[data-testid^="cal-pertes-poste-"]').filter({ has: page.locator('input[type="number"]') }).first()
    const cle = (await poste.getAttribute('data-testid')).replace('cal-pertes-poste-', '')
    const champ = poste.locator(`#cal-pertes-${cle}`)
    const valeur = Number(await champ.inputValue()) || 0
    await champ.fill(String(valeur + 1.5))
    const source = poste.locator(`#cal-pertes-source-select-${cle}`)
    if (await source.count()) {
      const options = await source.locator('option').evaluateAll((os) => os.map((o) => o.value).filter(Boolean))
      if (!(await source.inputValue())) await source.selectOption(options[0])
    }
    const url = page.url()
    const ecrit = page.waitForResponse((x) => x.request().method() !== 'GET' && /\/calepinages\/\d+\/(enregistrer-)?pertes\//.test(new URL(x.url()).pathname), T)
    await unifie.getByTestId('cal-pertes-enregistrer').click()
    const r = await ecrit
    console.log(`[ACAL396] poste ${cle} → ${valeur + 1.5} : ${r.request().method()} ${new URL(r.url()).pathname} → ${r.status()}`)
    expect(r.status(), `enregistrement du poste → ${(await r.text()).slice(0, 300)}`).toBeLessThan(300)
    await expect(unifie.getByTestId('calx48-perime'), '« simulation périmée » dans le diagramme').toBeVisible(T)
    expect(page.url(), 'sans changer d’onglet').toBe(url)
  } finally {
    await restaurerReglages(reglages)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL398 — PA2.5 : enregistrer ⇒ la simulation part seule ; Production : calcul en cours puis P50 frais SANS clic ;
// sans mode météo : la phrase de refus.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL398-simulation-auto', ['ACAL398'], async ({ page, context, suivi }) => {
  const reglages = await sauverReglages()
  let cal = null
  let sans = null
  try {
    await carteRefusee(context, suivi)
    await poserMeteo()
    cal = await calepinageAvec('ACAL398', toitPlat())
    await designerMateriel(cal.id)
    let bouton = await ouvrirAtelier(page, cal.id)
    const simuler = page.waitForResponse((x) => x.request().method() === 'POST'
      && new URL(x.url()).pathname.endsWith(`/calepinages/${cal.id}/simuler/`), T)
    await enHaut(page)
    await page.locator('[data-tilt="10"]').click()
    await expect(page.getByTestId('cal-etat-enregistrement')).toHaveText('Modifications non enregistrées', T)
    await enregistrer(page, cal.id, bouton)
    const rs = await simuler
    const accuse = await rs.json()
    console.log(`[ACAL398] POST simuler/ (seul, après l’enregistrement) → ${rs.status()} ${JSON.stringify(accuse).slice(0, 300)}`)
    expect(rs.status(), 'simulation partie toute seule (202)').toBe(202)
    expect(rs.request().postDataJSON()?.forcer ?? false, 'jamais forcée').toBeFalsy()
    // Onglet Production (navigation dans l'atelier, sans clic de calcul) : calcul en cours…
    await page.getByTestId('cal-etape-resultats').click()
    await expect(page.getByTestId('cal-onglet-production')).toHaveAttribute('aria-selected', 'true', T)
    await expect(page.getByTestId('calx48-avancement'), 'calcul en cours').toBeVisible(T)
    await expect(page.getByTestId('acal443-heros')).toHaveCount(0)
    // … le travail mis en file par l'écran est exécuté par la VRAIE tâche (aucun worker sur le runner).
    const issue = await py(`from apps.calepinage.tasks import simuler_calepinage as tache
r = tache(job_id=${Number(accuse.job_id)}, company_id=${cal.company}, calepinage_id=${cal.id}, forcer=False)
sortie(r)`)
    console.log(`[ACAL398] tâche exécutée : ${JSON.stringify(issue).slice(0, 300)}`)
    await expect(page.getByTestId('acal443-heros'), 'P50 frais, sans clic').toHaveText(/\d/, { timeout: 180_000 })

    // Le tapis horaire du calepinage simulé est chargé (export horaire) AVANT que les réglages ne changent.
    await expect(page.getByTestId('cal-tapis-journee-type'), 'tapis horaire du résultat frais').toBeVisible(T)
    await page.waitForLoadState('networkidle').catch(() => undefined)
    await page.goto('/calepinage')
    // Sans mode météo : la simulation automatique est refusée, la phrase dite dans Production.
    await retirerMeteo()
    sans = await calepinageAvec('ACAL398 sans meteo', toitPlat())
    await designerMateriel(sans.id)
    bouton = await ouvrirAtelier(page, sans.id)
    suivi.attendre(new RegExp(`/calepinages/${sans.id}/simuler/$`))
    const refus = page.waitForResponse((x) => x.request().method() === 'POST'
      && new URL(x.url()).pathname.endsWith(`/calepinages/${sans.id}/simuler/`), T)
    await enregistrer(page, sans.id, bouton)
    const rr = await refus
    console.log(`[ACAL398] sans météo : POST simuler/ → ${rr.status()} ${(await rr.text()).slice(0, 300)}`)
    expect(rr.status(), 'refus serveur').toBeGreaterThanOrEqual(400)
    await page.waitForTimeout(1500)
    const toasts = page.locator('[data-sonner-toast]').filter({ hasText: /mode m[ée]t[ée]o/i })
    const nToasts = await toasts.count()
    console.log(`[ACAL398] toasts du refus : ${nToasts} ${JSON.stringify(await toasts.allInnerTexts().catch(() => []))}`)
    await page.getByTestId('cal-etape-resultats').click()
    const phrase = page.getByTestId('calx48-refus')
    await expect(phrase, 'la phrase de refus').toBeVisible(T)
    await expect(phrase).toContainText('La simulation automatique n’a pas démarré : ')
    console.log(`[ACAL398] refus affiché : « ${await phrase.innerText()} »`)
    expect(nToasts, 'refus nommé → AUCUN toast (Then d’ACAL398)').toBe(0)
  } finally {
    await restaurerReglages(reglages)
    await nettoyer(cal, sans)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL448 — PA2.5 : calepinage lié à un devis : onglet Économie, flux année par année (barres + cumul).
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL448-economie-flux', ['ACAL448'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL448', toitPlat())
  try {
    const candidats = await py(`from apps.ventes.models import Devis
co = U.objects.get(username='demo_admin').company
sortie(list(Devis.objects.filter(company=co, calepinages__isnull=True).order_by('-id').values_list('id', flat=True)[:25]))`)
    let devis = null
    let economie = null
    for (const id of candidats || []) {
      const r = await page.request.get(`${API_DJANGO}/ventes/devis/${id}/economie/`, T)
      if (!r.ok()) continue
      const e = await r.json()
      if (Array.isArray(e?.flux) && e.flux.length > 0) { devis = id; economie = e; break }
    }
    expect(devis, `un devis de démo à flux servi parmi ${JSON.stringify(candidats)}`).toBeTruthy()
    await py(`from apps.calepinage.models import Calepinage
c = Calepinage.objects.get(pk=${cal.id})
c.devis_id = ${devis}
c.save(update_fields=['devis'])
sortie(1)`)
    await page.goto(`/calepinage/${cal.id}?onglet=economie`)
    await expect(page.getByTestId('calx289-panneau')).toBeVisible(T)
    const graphique = page.getByTestId('acal448-graphique')
    await expect(graphique, 'flux de trésorerie tracé').toBeVisible(T)
    const avecFlux = economie.flux.filter((l) => l.flux_mad !== null && l.flux_mad !== undefined).length
    console.log(`[ACAL448] devis ${devis} : ${economie.flux.length} années, ${avecFlux} flux, retour ${economie.retour_ans}`)
    await expect(graphique.locator('.recharts-bar-rectangle'), 'une barre par flux servi').toHaveCount(avecFlux, T)
    await expect(graphique.locator('.recharts-line'), 'courbe du cumul').toHaveCount(1)
    if (typeof economie.retour_ans === 'number' && economie.flux.some((l) => l.annee === economie.retour_ans)) {
      await expect(graphique.locator('.recharts-reference-line'), 'repère du retour').toHaveCount(1)
    }
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL469 — PA2.5 : onglet Optimiser d'un pan LIBRE (toit plat ; un champ au sol se balaie par le même chemin) :
// Lancer, carte des résultats, Appliquer, enregistrer, rouvrir : inclinaison conservée.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL469-optimiser', ['ACAL469'], async ({ page, context, suivi }) => {
  const reglages = await sauverReglages()
  let cal = null
  try {
    await carteRefusee(context, suivi)
    await poserMeteo()
    cal = await calepinageAvec('ACAL469', toitPlat())
    await designerMateriel(cal.id)
    let bouton = await ouvrirAtelier(page, cal.id)
    await enregistrer(page, cal.id, bouton)
    bouton = await ouvrirAtelier(page, cal.id, 'optimiser')
    await expect(page.getByTestId('acal469-panneau')).toBeVisible(T)
    for (const [k, v] of [['inclinaison_deg-min', '10'], ['inclinaison_deg-max', '30'], ['inclinaison_deg-pas', '10'],
      ['azimut_deg-min', '180'], ['azimut_deg-max', '180'], ['azimut_deg-pas', '30']]) await page.locator(`#acal469-${k}`).fill(v)
    const balayer = page.waitForResponse((x) => x.request().method() === 'POST'
      && new URL(x.url()).pathname.endsWith(`/calepinages/${cal.id}/balayage/`), T)
    await page.getByTestId('acal469-lancer').click()
    const rb = await balayer
    const accuse = await rb.json()
    const corps = rb.request().postDataJSON()
    console.log(`[ACAL469] POST balayage/ ${JSON.stringify(corps)} → ${rb.status()} ${JSON.stringify(accuse).slice(0, 200)}`)
    expect(rb.status()).toBe(202)
    const issue = await py(`import json
from apps.calepinage.tasks import balayer_calepinage as tache
r = tache(job_id=${Number(accuse.job_id)}, company_id=${cal.company}, calepinage_id=${cal.id}, corps=json.loads(${JSON.stringify(JSON.stringify({ pan: corps.pan, axes: corps.axes }))}))
sortie(r)`)
    console.log(`[ACAL469] tâche : ${JSON.stringify(issue).slice(0, 300)}`)
    const grille = page.getByTestId('acal469-grille')
    await expect(grille, 'carte des résultats').toBeVisible({ timeout: 180_000 })
    await expect(page.getByTestId('acal469-case'), 'trois inclinaisons balayées').toHaveCount(3)
    await expect(page.getByTestId('acal469-optimum')).toBeVisible()
    const job = await lireJson(await page.request.get(`${CAL}/moteur/resultat/${accuse.job_id}/`, T), 'résultat du balayage')
    const optimum = (job?.resultat || job)?.optimum
    console.log(`[ACAL469] optimum : ${JSON.stringify(optimum)}`)
    expect(optimum?.inclinaison_deg, 'optimum nommé').toBeDefined()
    await page.getByTestId('acal469-appliquer').click()
    await expect(page.getByTestId('acal469-message')).toContainText('Optimum appliqué')
    const doc = await enregistrer(page, cal.id, bouton)
    console.log(`[ACAL469] choixConception enregistré : ${JSON.stringify(doc.choixConception)}`)
    expect(doc.choixConception?.tilt, 'inclinaison optimale enregistrée').toBe(optimum.inclinaison_deg)
    bouton = await ouvrirAtelier(page, cal.id, 'optimiser')
    const relu = await enregistrer(page, cal.id, bouton)
    expect(relu.choixConception?.tilt, 'rouvert puis enregistré : inclinaison conservée').toBe(optimum.inclinaison_deg)
  } finally {
    await restaurerReglages(reglages)
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL475 — PA2.5 : onglet Documents : rapport d'étude PDF d'un calepinage simulé : la « Note de validation » y est.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL475-rapport-note-validation', ['ACAL475'], async ({ page, context, suivi }) => {
  const reglages = await sauverReglages()
  try {
    await carteRefusee(context, suivi)
    const cal = await calepinageSimule(page)
    await page.goto(`/calepinage/${cal.id}?onglet=documents`)
    const carte = page.locator('[data-testid^="cal-doc-sortie-"]').filter({ hasText: /rapport d.étude/i }).first()
    await expect(carte, 'sortie « Rapport d’étude »').toBeVisible(T)
    const code = (await carte.getAttribute('data-testid')).replace('cal-doc-sortie-', '')
    const pdf = page.waitForResponse((x) => /rapport-etude\.pdf/.test(new URL(x.url()).pathname), { timeout: 240_000 })
    await carte.getByTestId(`cal-doc-bouton-${code}`).click()
    const r = await pdf
    expect(r.status(), `rapport-etude.pdf → ${r.status()}`).toBe(200)
    const chemin = join(tmpdir(), `acal7-rapport-${cal.id}.pdf`)
    writeFileSync(chemin, await r.body())
    const texte = await py(`import fitz
d = fitz.open(${JSON.stringify(chemin)})
sortie({'pages': d.page_count, 'texte': '\\n'.join(p.get_text() for p in d)})`)
    const i = texte.texte.indexOf('Note de validation')
    console.log(`[ACAL475] ${texte.pages} pages ; « Note de validation » à ${i} : ${texte.texte.slice(Math.max(0, i), i + 300).replace(/\s+/g, ' ')}`)
    expect(i, 'la section « Note de validation » est dans le PDF').toBeGreaterThanOrEqual(0)
  } finally {
    await restaurerReglages(reglages)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL405 + ACAL403 — PA2.5 : société aux réglages vides : « Démarrage rapide » > Appliquer, simuler, « Réglages
// utilisés » porte la mention « valeur publiée » ; puis Retirer le profil.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL405-ACAL403-demarrage-rapide', ['ACAL405', 'ACAL403'], async ({ page, context, suivi }) => {
  const reglages = await sauverReglages()
  try {
    await carteRefusee(context, suivi)
    const cal = await calepinageSimule(page)
    // Société « neuve » : réglages de simulation vides.
    await py(`from apps.calepinage.models import ParametresCalepinage
co = U.objects.get(username='demo_admin').company
for p in ParametresCalepinage.objects.filter(company=co):
    for f in p._meta.fields:
        if f.get_internal_type() == 'JSONField' and f.name != 'norme_electrique' and isinstance(getattr(p, f.name), dict):
            setattr(p, f.name, {})
    p.save()
sortie(1)`)
    await page.goto('/calepinage/reglages')
    const carte = page.getByTestId('acal405-demarrage')
    await expect(carte, 'Démarrage rapide').toBeVisible(T)
    await carte.getByTestId('acal405-appliquer').click()
    await expect(carte.getByTestId('acal405-message')).toHaveText(/^\d+ valeurs appliquées$/, T)
    const nAppliquees = chiffres(await carte.getByTestId('acal405-message').innerText())
    console.log(`[ACAL403/405] ${nAppliquees} valeurs appliquées`)
    expect(nAppliquees, 'des clés vides remplies').toBeGreaterThan(0)
    await poserMeteo()
    await simulerServeur(cal.id)
    await page.goto(`/calepinage/${cal.id}?onglet=pertes`)
    const utilises = page.getByTestId('acal52-reglages-utilises').first()
    await expect(utilises, '« Réglages utilisés »').toBeVisible(T)
    await utilises.locator('summary').click()
    await expect(utilises.getByTestId('acal405-publiee').first(), 'la mention « valeur publiée »').toBeVisible()
    console.log(`[ACAL405] mention : « ${await utilises.getByTestId('acal405-publiee').first().innerText()} » × ${await utilises.getByTestId('acal405-publiee').count()}`)
    await page.goto('/calepinage/reglages')
    await page.getByTestId('acal405-retirer').click()
    await expect(page.getByTestId('acal405-message')).toHaveText(/^\d+ valeurs retirées$/, T)
    expect(chiffres(await page.getByTestId('acal405-message').innerText()), 'profil retiré').toBeGreaterThan(0)
  } finally {
    await restaurerReglages(reglages)
    if (SIMULE) await nettoyer(SIMULE)
    SIMULE = null
  }
})
