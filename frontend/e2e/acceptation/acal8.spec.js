// Acceptation en direct — groupe ACAL, huitième lot (runner GitHub) : ACAL490, MOITIÉ SERVEUR du complément L5.
// Les clauses « Preuve en direct » qui se jouent par l'API (aucun geste d'écran : l'autre lane les joue) :
//   ACAL392 (parcours guidé `GET parcours/`), ACAL400 (brouillon serveur PUT/GET/DELETE, autre poste, autre compte),
//   ACAL403 (profil de départ appliqué puis retiré), ACAL426 (avertissements de « Générer le devis »),
//   ACAL445 (autoconsommation par mois), ACAL451 (irradiation mensuelle du plan), ACAL452 (colonne du rapport),
//   ACAL455 (transposition d'un CSV horizontal déposé), ACAL456 (décomposition d'un CSV au global seul),
//   ACAL461 (ombrage du diffus), ACAL462 (ombrage électrique au rapport), ACAL463 (neige), ACAL467 (table d'ombrage
//   direct), ACAL468 (balayage inclinaison × azimut), ACAL475 (note de validation au rapport), ACAL477 (axe ratio
//   DC/AC), ACAL485 (détection du toit : indisponible sans clé).
// Montage : la pile du runner n'a PAS de worker Celery. Chaque travail de fond est LANCÉ par sa vraie route
// (`POST simuler/`, `POST balayage/` → 202 + job), puis la VRAIE tâche Celery (`apps.calepinage.tasks.*`) est
// exécutée telle quelle au shell Django avec ce job (le rôle du worker), et son issue est RELUE par la vraie route
// `GET moteur/resultat/<job>/` puis `GET resultat/`. PVGIS est appelé EN DIRECT : « PVGIS injoignable » = NON JOUABLE
// (rejouer le run), jamais un faux vert. Réglages société posés par la vraie route `PUT parametres/`, état d'avant
// rendu à la fin de chaque étape. Données propres à chaque étape (lead + calepinage), nettoyées.
// Non couvert ici (motif dit au rapport) : ACAL465 (bifacial : aucune fiche bifaciale au catalogue de démo).
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { RACINE } from './_enregistrement.js'
import { API_DJANGO, PNG_1PX, assurerSessionPage, connexionApi, lireJson, textePdf } from '../helpers.js'

const etape = groupe('ACAL', ['ACAL392', 'ACAL400', 'ACAL403', 'ACAL426', 'ACAL445', 'ACAL451', 'ACAL452', 'ACAL455',
  'ACAL456', 'ACAL461', 'ACAL462', 'ACAL463', 'ACAL467', 'ACAL468', 'ACAL475', 'ACAL477', 'ACAL485'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 900_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const CAL = `${API_DJANGO}/calepinage`
const T = { timeout: 180_000 }
const J = (x) => JSON.stringify(x)
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()
const somme = (xs) => xs.reduce((s, x) => s + (Number(x) || 0), 0)
const etapeDe = (resultat, nom) => ((resultat?.cascade?.etapes) || []).find((e) => e?.etape === nom)
const SOC = `U.objects.get(username='demo_admin').company`

const PIN = { lat: 33.5731, lng: -7.5898 }
const PAN_A = [[-7.5899, 33.5732], [-7.5897, 33.5732], [-7.5897, 33.5730], [-7.5899, 33.5730]]
/** Un pan sud 15° de `count` modules, lisible par le serveur (forme des goldens ACAL382). */
const zoneSud = (count, extra = {}) => ({
  id: 'z1', label: 'PAN-SUD', vertices: PAN_A, pitchDeg: 15, facingAzimuthDeg: 180,
  geometry: { count, azimuthDeg: 180.0, tiltDeg: 15.0, family: 'surimposition', ...extra },
})
const docSud = (count, extraGeo = {}, extraDoc = {}) => ({ version: 2, pin: PIN, zones: [zoneSud(count, extraGeo)], ...extraDoc })

// ── Préparation au shell Django (rien de public ne crée un calepinage à document donné) ─────────────────────────────
async function calepinageAvec(tag, layout) {
  const m = marque()
  return py(`import json
from decimal import Decimal as D
from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
from apps.ventes.domain.geometrie import layout_hash
co = ${SOC}
lead = Lead.objects.create(company=co, nom='ACC ${tag} ${m}', ville='Casablanca', type_installation='residentiel', facture_hiver=D('3000'))
lay = json.loads(${J(J(layout))})
c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC ${tag} ${m}', roof_layout=lay, layout_hash=layout_hash(lay))
sortie({'id': c.pk, 'lead': lead.pk})`)
}

async function poserDocument(id, layout) {
  return py(`import json
from apps.calepinage.models import Calepinage
from apps.ventes.domain.geometrie import layout_hash
lay = json.loads(${J(J(layout))})
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
from apps.ventes.models import Devis
cals = list(Calepinage.objects.filter(pk__in=${J(ids.map((c) => Number(c.id)))}))
devis = [c.devis_id for c in cals if c.devis_id]
for c in cals:
    try:
        c.delete()
    except Exception:
        pass
for pk in devis:
    try:
        Devis.objects.filter(pk=pk).delete()
    except Exception:
        pass
try:
    Lead.objects.filter(pk__in=${J(ids.map((c) => Number(c.lead)))}).delete()
except Exception:
    pass
sortie(1)`)
}

/** Désigne module + onduleur RÉELS du catalogue (patron acal6 `designerMateriel`). */
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
            return {'id': p.pk, 'nom': p.nom, 'pmax_wc': s.get('pmax_wc'), 'ac_kw': s.get('ac_kw')}
    return None
module = premier(produits_modules_qs(c.company), CHAMPS_MODULE)
onduleur = premier(produits_par_type_fiche_qs(c.company, 'onduleur'), CHAMPS_ONDULEUR)
if module and onduleur:
    enregistrer_entree(c, {'module_produit': module['id'], 'onduleur_produit': onduleur['id']},
                       user=U.objects.get(username='demo_admin'))
sortie({'module': module, 'onduleur': onduleur})`)
  if (!r?.module || !r?.onduleur) throw new Error(`NON JOUABLE — catalogue sans fiche module/onduleur complète : ${J(r)}`)
  return r
}

/** Réglages société : photo de TOUTES les sections (restaurée telle quelle à la fin de l'étape). */
async function photoReglages() {
  return py(`from apps.calepinage.models import ParametresCalepinage
p = ParametresCalepinage.objects.filter(company=${SOC}).order_by('id').first()
sortie(None if p is None else {s: getattr(p, s) for s in ParametresCalepinage.SECTIONS})`)
}
async function rendreReglages(photo) {
  await py(`import json
from apps.calepinage.models import ParametresCalepinage
photo = json.loads(${J(J(photo))})
p = ParametresCalepinage.objects.filter(company=${SOC}).order_by('id').first()
if photo is None:
    if p is not None:
        p.delete()
else:
    if p is None:
        p = ParametresCalepinage.objects.create(company=${SOC})
    for s, v in photo.items():
        setattr(p, s, v)
    p.save()
sortie(1)`)
}
/** Écrit des réglages par la VRAIE route de l'écran de réglages (`PUT parametres/`). */
async function regler(request, donnees) {
  const r = await request.put(`${CAL}/parametres/`, { ...T, data: donnees })
  expect(r.status(), `PUT parametres/ ${J(donnees).slice(0, 200)} → ${(await r.text()).slice(0, 400)}`).toBe(200)
  return r.json()
}
const S = (valeur, reference, source = 'societe') => ({ valeur, source, reference })
const METEO_2020 = {
  mode_meteo: S('pluriannuel', 'acceptation ACAL8 — réglage de la pile d’essai'),
  fenetre_annees: S('2020-2020', 'acceptation ACAL8 — base PVGIS 2020'),
}

/** Le rôle du worker absent : la VRAIE tâche Celery, exécutée telle quelle avec le job créé par la route. */
async function travailler(code) {
  try {
    return await py(code)
  } catch (e) {
    const m = String(e.message)
    if (/pvgis|ConnectionError|Timeout|Max retries|NameResolution|unreachable|injoignable/i.test(m)) {
      throw new Error(`NON JOUABLE sur ce runner — PVGIS injoignable : ${m.slice(-500)}`)
    }
    throw e
  }
}
async function lireJob(request, jobId) {
  const job = await lireJson(await request.get(`${CAL}/moteur/resultat/${jobId}/`, T), `moteur/resultat/${jobId}`)
  if (job.statut !== 'done') {
    const motif = J(job.elements?.[0] || job.message_erreur || job).slice(0, 700)
    if (/pvgis|injoignable|ConnectionError|Timeout|Max retries|NameResolution/i.test(motif)) {
      throw new Error(`NON JOUABLE sur ce runner — PVGIS injoignable : ${motif}`)
    }
    throw new Error(`job ${jobId} ${job.statut} : ${motif}`)
  }
  return job
}
/** `POST simuler/` (route réelle, 202) → tâche `calepinage.simuler` → `GET moteur/resultat/<job>/` → `GET resultat/`. */
async function simuler(request, id) {
  const r = await request.post(`${CAL}/calepinages/${id}/simuler/`, { ...T, data: { forcer: true } })
  const accuse = await r.json().catch(() => ({}))
  expect(r.status(), `POST simuler/ → ${J(accuse).slice(0, 500)}`).toBe(202)
  expect(accuse.nature).toBe('simulation')
  await travailler(`from apps.calepinage.tasks import simuler_calepinage as tache
sortie(tache(job_id=${accuse.job_id}, company_id=${SOC}.pk, calepinage_id=${Number(id)}, forcer=True))`)
  await lireJob(request, accuse.job_id)
  return lireJson(await request.get(`${CAL}/calepinages/${id}/resultat/`, T), `resultat/ de ${id}`)
}
/** `POST balayage/` (route réelle, 202) → tâche `calepinage.balayer` → `GET moteur/resultat/<job>/`. */
async function balayer(request, id, corps) {
  const r = await request.post(`${CAL}/calepinages/${id}/balayage/`, { ...T, data: corps })
  const accuse = await r.json().catch(() => ({}))
  expect(r.status(), `POST balayage/ → ${J(accuse).slice(0, 500)}`).toBe(202)
  expect(accuse.nature).toBe('balayage')
  await travailler(`from apps.calepinage.tasks import balayer_calepinage as tache
sortie(tache(job_id=${accuse.job_id}, company_id=${SOC}.pk, calepinage_id=${Number(id)}, corps=json.loads(${J(J(corps))})))`)
  return (await lireJob(request, accuse.job_id)).resultat
}
async function rapportEtude(request, id) {
  const r = await request.get(`${CAL}/calepinages/${id}/rapport-etude.pdf`, T)
  expect(r.status(), `rapport-etude.pdf → ${r.status() === 200 ? '' : (await r.text()).slice(0, 400)}`).toBe(200)
  expect(r.headers()['content-type']).toContain('application/pdf')
  return (await textePdf(await r.body())).replace(/\s+/g, ' ')
}
const lireLayout = async (request, id) => lireJson(await request.get(`${CAL}/calepinages/${id}/layout/`, T), 'layout')

/** Un second « poste » : contexte API neuf (aucun cookie partagé), connecté par la vraie route de jeton. */
async function poste(testInfo, identifiants) {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, identifiants)
  return ctx
}

// ════════════════════════════════════════════════════════════════════════════
// ACAL392 — PA2.5 : `GET parcours/` d'un calepinage « de la capture » (toit tracé, 10 panneaux, aucune norme choisie) :
// 5 étapes dans l'ordre, états des règles, UNE seule ligne « norme électrique » ; puis simulé (resultats fait) et
// périmé (resultats en_cours).
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL392-parcours-guide', ['ACAL392'], async ({ page }) => {
  const photo = await photoReglages()
  let cal = null
  try {
    await regler(page.request, { simulation: METEO_2020 })
    await py(`from apps.calepinage.models import ParametresCalepinage
p = ParametresCalepinage.objects.filter(company=${SOC}).order_by('id').first()
p.norme_electrique = {}
p.save(update_fields=['norme_electrique'])
sortie(1)`)
    cal = await calepinageAvec('ACAL392', docSud(10))
    await designerMateriel(cal.id)
    const lire = async (quand) => {
      const p = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/parcours/`, T), `parcours/ ${quand}`)
      console.log(`[ACAL392] ${quand} : ${J(p)}`)
      expect(p.etapes.map((e) => e.cle), `${quand} : 5 étapes dans l'ordre`).toEqual(['toit', 'panneaux', 'electrique', 'resultats', 'documents'])
      for (const e of p.etapes) expect(['a_faire', 'en_cours', 'fait', 'bloque'], `${quand} : état de ${e.cle}`).toContain(e.etat)
      const cles = p.manque.map((l) => `${l.code}|${l.cible?.onglet}|${l.cible?.champ}`)
      expect(new Set(cles).size, `${quand} : « ce qui manque » sans doublon (code, cible)`).toBe(cles.length)
      const norme = p.manque.filter((l) => l.code === 'norme_absente')
      expect(norme, `${quand} : UNE seule ligne « norme électrique »`).toHaveLength(1)
      expect(norme[0].etape).toBe('electrique')
      expect(norme[0].cible).toEqual({ onglet: 'reglages', champ: 'norme' })
      expect(norme[0].nombre, `${quand} : lignes fusionnées comptées`).toBeGreaterThanOrEqual(1)
      return Object.fromEntries(p.etapes.map((e) => [e.cle, e.etat]))
    }
    const avant = await lire('jamais simulé')
    expect(avant.toit, 'toit tracé ⇒ fait').toBe('fait')
    expect(avant.panneaux, '10 panneaux ⇒ fait').toBe('fait')
    expect(avant.resultats, 'jamais simulé ⇒ a_faire').toBe('a_faire')
    expect(avant.documents, 'sans devis, résultats non faits ⇒ a_faire').toBe('a_faire')

    const res = await simuler(page.request, cal.id)
    expect(res.simule, `simulation servie (${res.motif})`).toBe(true)
    const simule = await lire('simulé')
    expect(simule.resultats, 'simulation fraîche ⇒ fait').toBe('fait')
    expect(simule.documents, 'résultats faits, sans devis ⇒ en_cours').toBe('en_cours')

    await poserDocument(cal.id, docSud(12))
    const perime = await lire('périmé (12 panneaux après simulation)')
    expect(perime.resultats, 'simulation périmée ⇒ en_cours').toBe('en_cours')
  } finally {
    await nettoyer(cal)
    await rendreReglages(photo)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL400 — PA2.5 : brouillon serveur. Poste A range un brouillon ; poste B (autre contexte, MÊME compte) le reprend ;
// un AUTRE compte ne le voit pas ; aucune version, ni layout_hash, ni empreinte, ni updated_at touchés ; périmé dès que
// le document change ; DELETE l'efface.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL400-brouillon-serveur', ['ACAL400'], async ({ page, testInfo }) => {
  const cal = await calepinageAvec('ACAL400', docSud(10))
  const ouverts = []
  try {
    const etat = () => py(`from apps.calepinage.models import Calepinage
c = Calepinage.objects.get(pk=${Number(cal.id)})
sortie({'layout_hash': c.layout_hash, 'updated_at': c.updated_at.isoformat(), 'versions': c.versions.count()})`)
    const lu = await lireLayout(page.request, cal.id)
    const base = lu.empreinte_document
    expect(base, 'empreinte « document » servie').toBeTruthy()
    const avant = await etat()
    const brouillonA = { layout: docSud(11), horodatage: new Date().toISOString(), base_empreinte: base }
    const put = await page.request.put(`${CAL}/calepinages/${cal.id}/brouillon/`, { ...T, data: brouillonA })
    expect(put.status(), `PUT brouillon/ → ${(await put.text()).slice(0, 300)}`).toBe(200)
    expect(await put.json(), 'PUT rend le brouillon rangé').toEqual(brouillonA)
    const apres = await etat()
    const lu2 = await lireLayout(page.request, cal.id)
    console.log(`[ACAL400] avant ${J(avant)} après ${J(apres)} empreinte ${base} → ${lu2.empreinte_document}`)
    expect(apres, 'aucune version, layout_hash et updated_at inchangés').toEqual(avant)
    expect(lu2.empreinte_document, 'empreinte « document » inchangée').toBe(base)
    expect(lu2.roof_layout, 'document stocké inchangé').toEqual(lu.roof_layout)

    // Poste B, même compte : le brouillon est proposé.
    const posteB = await poste(testInfo)
    ouverts.push(posteB)
    const surB = await lireJson(await posteB.get(`${CAL}/calepinages/${cal.id}/brouillon/`, T), 'brouillon (poste B)')
    expect(surB, 'poste B, même compte : le brouillon serveur est repris').toEqual(brouillonA)

    // Un autre compte de la même société ne voit RIEN (privé à l'auteur), et range le sien sans toucher au premier.
    const nom = `acal8b_${marque().toLowerCase()}`
    await py(`from apps.roles.models import Role
compte(${J(nom)}, role=Role.objects.get(company=${SOC}, nom='Directeur', est_systeme=True).pk, societe=${SOC}.pk)
sortie(1)`)
    const autre = await poste(testInfo, { username: nom, password: MDP_ESSAI })
    ouverts.push(autre)
    const rAutre = await autre.get(`${CAL}/calepinages/${cal.id}/brouillon/`, T)
    expect(rAutre.status(), 'autre compte : le calepinage se lit').toBe(200)
    expect(await rAutre.json(), 'autre compte : aucun brouillon (null)').toBeNull()
    const brouillonAutre = { layout: docSud(9), horodatage: new Date().toISOString(), base_empreinte: base }
    const putAutre = await autre.put(`${CAL}/calepinages/${cal.id}/brouillon/`, { ...T, data: brouillonAutre })
    expect(putAutre.status(), `autre compte : PUT → ${(await putAutre.text()).slice(0, 200)}`).toBe(200)
    expect(await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/brouillon/`, T), 'brouillon A'),
      'le brouillon de l’auteur reste le sien').toEqual(brouillonA)

    // Périmé : le document change (section écrite par l'API) ⇒ GET rend null.
    const sec = await page.request.post(`${CAL}/calepinages/${cal.id}/layout/section/`, {
      ...T,
      data: { cle: 'horizonProfile', valeur: { source: 'saisie', points: [{ azimuthDeg: 90, heightDeg: 5 }], hauteurMaxDeg: 5 }, base_empreinte: base },
    })
    expect(sec.status(), `section horizon → ${(await sec.text()).slice(0, 200)}`).toBe(200)
    expect((await lireLayout(page.request, cal.id)).empreinte_document, 'le document a changé').not.toBe(base)
    expect(await lireJson(await posteB.get(`${CAL}/calepinages/${cal.id}/brouillon/`, T), 'brouillon périmé'),
      'document changé depuis : brouillon périmé ⇒ null').toBeNull()

    // Rangé de nouveau sur le document vivant, puis effacé (« Enregistrer » ou « Ignorer ») : null partout.
    const vivant = (await lireLayout(page.request, cal.id)).empreinte_document
    const put2 = await page.request.put(`${CAL}/calepinages/${cal.id}/brouillon/`, { ...T, data: { ...brouillonA, base_empreinte: vivant } })
    expect(put2.status()).toBe(200)
    expect((await lireJson(await posteB.get(`${CAL}/calepinages/${cal.id}/brouillon/`, T), 'brouillon vivant')).base_empreinte).toBe(vivant)
    const brouillonAutreVivant = { ...brouillonAutre, base_empreinte: vivant }
    expect((await autre.put(`${CAL}/calepinages/${cal.id}/brouillon/`, { ...T, data: brouillonAutreVivant })).status()).toBe(200)
    const del = await page.request.delete(`${CAL}/calepinages/${cal.id}/brouillon/`, T)
    expect(del.status(), 'DELETE brouillon/').toBe(200)
    expect(await del.json()).toBeNull()
    expect(await lireJson(await posteB.get(`${CAL}/calepinages/${cal.id}/brouillon/`, T), 'après DELETE'), 'effacé ⇒ null').toBeNull()
    expect(await lireJson(await autre.get(`${CAL}/calepinages/${cal.id}/brouillon/`, T), 'autre après DELETE de A'),
      'le DELETE de A n’efface pas celui de l’autre compte').toEqual(brouillonAutreVivant)
    await py(`U.objects.filter(username=${J(nom)}).update(is_active=False)
sortie(1)`)
  } finally {
    for (const c of ouverts) await c.dispose().catch(() => undefined)
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL403 — PA2.5 : profil de départ. Clés du profil vides ⇒ POST les remplit TOUTES (référence au préfixe du
// contrat) ; second POST ⇒ toutes « deja_saisie » ; une valeur retouchée ⇒ DELETE la garde et retire les autres.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL403-profil-depart', ['ACAL403'], async ({ page }) => {
  const contrat = JSON.parse(readFileSync(join(RACINE, 'backend/django_core/apps/calepinage/contract_samples/calepinage_profil_depart.json'), 'utf8'))
  const prefixe = contrat.prefixe_reference
  const photo = await photoReglages()
  try {
    const profil = await lireJson(await page.request.get(`${CAL}/calepinages/profil-depart/`, T), 'GET profil-depart/')
    const valeurs = profil.valeurs || []
    console.log(`[ACAL403] profil servi : ${valeurs.length} valeurs (${valeurs.map((v) => `${v.section}.${v.cle}`).join(', ')}), ${(profil.sans_source || []).length} sans source`)
    expect(valeurs.length, 'le profil propose des valeurs sourcées').toBeGreaterThan(1)
    for (const v of valeurs) {
      expect(v.source, `${v.cle} : source « texte »`).toBe('texte')
      expect(String(v.url), `${v.cle} : page lue citée`).toMatch(/^https?:\/\//)
    }
    const cles = valeurs.map((v) => `${v.section}.${v.cle}`).sort()
    // Given : toutes les clés du profil VIDES pour la société de démo.
    await py(`import json
from apps.calepinage.models import ParametresCalepinage
co = ${SOC}
p = ParametresCalepinage.objects.filter(company=co).order_by('id').first() or ParametresCalepinage.objects.create(company=co)
for sc in json.loads(${J(J(cles))}):
    s, c = sc.split('.', 1)
    d = dict(getattr(p, s) or {})
    d.pop(c, None)
    setattr(p, s, d)
p.save()
sortie(1)`)
    const poste1 = await page.request.post(`${CAL}/calepinages/profil-depart/`, T)
    const app1 = await poste1.json()
    expect(poste1.status(), `POST profil-depart/ → ${J(app1).slice(0, 300)}`).toBe(200)
    console.log(`[ACAL403] application 1 : ${app1.appliquees.length} appliquées, ${app1.ignorees.length} ignorées`)
    expect(app1.appliquees.map((l) => `${l.section}.${l.cle}`).sort(), 'clés vides : toutes appliquées').toEqual(cles)
    expect(app1.ignorees).toEqual([])
    const reglages = await lireJson(await page.request.get(`${CAL}/parametres/`, T), 'GET parametres/')
    for (const v of valeurs) {
      const s = reglages[v.section]?.[v.cle]
      expect(s?.source, `${v.section}.${v.cle} écrite source « texte »`).toBe('texte')
      expect(String(s?.reference), `${v.section}.${v.cle} : référence au préfixe du contrat`).toContain(prefixe)
      expect(String(s?.reference), `${v.section}.${v.cle} : « valeur publiée, non mesurée »`).toContain('valeur publiée, non mesurée')
      expect(s?.valeur, `${v.section}.${v.cle} : valeur du profil`).toEqual(v.valeur)
    }
    // Second POST : rien de vide ⇒ toutes ignorées « deja_saisie ».
    const app2 = await lireJson(await page.request.post(`${CAL}/calepinages/profil-depart/`, T), 'POST 2')
    expect(app2.appliquees, 'second POST : rien appliqué').toEqual([])
    expect(app2.ignorees.map((l) => `${l.section}.${l.cle}`).sort()).toEqual(cles)
    expect(new Set(app2.ignorees.map((l) => l.motif))).toEqual(new Set(['deja_saisie']))
    // Une valeur retouchée par la société (même source et référence) est GARDÉE par le retrait.
    const cible = valeurs.find((v) => typeof v.valeur === 'number')
    const saisie = reglages[cible.section][cible.cle]
    const retouchee = cible.valeur + 0.01
    await regler(page.request, { [cible.section]: { [cible.cle]: { ...saisie, valeur: retouchee } } })
    const retrait = await lireJson(await page.request.delete(`${CAL}/calepinages/profil-depart/`, T), 'DELETE profil-depart/')
    console.log(`[ACAL403] retrait : ${retrait.retirees.length} retirées, gardées ${J(retrait.gardees)}`)
    expect(retrait.gardees.map((l) => `${l.section}.${l.cle}`), 'la valeur retouchée est gardée').toEqual([`${cible.section}.${cible.cle}`])
    expect(retrait.retirees.map((l) => `${l.section}.${l.cle}`).sort(), 'les autres sont retirées')
      .toEqual(cles.filter((c) => c !== `${cible.section}.${cible.cle}`))
    const apres = await lireJson(await page.request.get(`${CAL}/parametres/`, T), 'GET parametres/ après retrait')
    expect(apres[cible.section][cible.cle].valeur, 'valeur retouchée intacte').toBe(retouchee)
    for (const v of valeurs.filter((x) => x !== cible)) {
      const s = apres[v.section]?.[v.cle]
      expect(s == null || s.valeur == null, `${v.section}.${v.cle} retirée (${J(s)})`).toBeTruthy()
    }
  } finally {
    await rendreReglages(photo)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL485 — sans capacité IA configurée : `GET detection-toit/` dit « indisponible », `POST` répond 503.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2-ACAL485-detection-toit-sans-cle', ['ACAL485'], async ({ page }) => {
  const cal = await calepinageAvec('ACAL485', docSud(10))
  try {
    const dispo = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/detection-toit/`, T), 'GET detection-toit/')
    console.log(`[ACAL485] GET : ${J(dispo)}`)
    expect(dispo.disponible, 'sans clé : indisponible').toBe(false)
    expect(String(dispo.motif || '').trim(), 'motif dit').not.toBe('')
    // « carte » n'est ouverte que par le réglage DETECTION_TOIT_CAPTURE_CARTE (conditions de l'imagerie lues par Reda).
    expect(dispo.origines_acceptees, 'origine « importee » acceptée').toContain('importee')
    const r = await page.request.post(`${CAL}/calepinages/${cal.id}/detection-toit/`, {
      ...T,
      multipart: {
        image: { name: 'toit.png', mimeType: 'image/png', buffer: PNG_1PX },
        emprise: J({ ouest: -7.5900, sud: 33.5729, est: -7.5896, nord: 33.5733 }),
        origine: 'importee',
      },
    })
    const corps = await r.text()
    console.log(`[ACAL485] POST : ${r.status()} ${corps.slice(0, 300)}`)
    expect(r.status(), 'sans clé : POST 503').toBe(503)
    expect(JSON.parse(corps).detail, 'motif 503 dit').toBeTruthy()
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL426 — « Générer le devis » d'un calepinage en pente sans source : 201 et les deux avertissements nommés ; pente
// et face confirmées : aucun ; jamais de blocage.
// ════════════════════════════════════════════════════════════════════════════
etape('API-ACAL426-generer-devis-hypotheses', ['ACAL426'], async ({ page }) => {
  const doc = (champs) => ({
    areas: [{ vertices: [[0, 0], [10, 0], [10, 6], [0, 6]], obstacles: [], roofType: 'flat', pitch: 10, azimuth: 180 }],
    scenario: 'reseau',
    result: { panels: 12, kwc: 6.6, annualKwh: 10800, savings: 9200 },
    zones: [{ id: 'A', label: 'A', roofType: 'pitched', vertices: [[0, 0], [10, 0], [10, 6], [0, 6]], pitchDeg: 22, facingAzimuthDeg: 180, ...champs }],
  })
  const creer = async (tag, champs) => {
    const c = await calepinageAvec(tag, {})
    await py(`import json
from apps.calepinage.models import Calepinage
from apps.calepinage.services.layout import enregistrer_layout
c = Calepinage.objects.get(pk=${Number(c.id)})
enregistrer_layout(c, json.loads(${J(J(doc(champs)))}), user=U.objects.get(username='demo_admin'))
sortie(1)`)
    return c
  }
  const sans = await creer('ACAL426 sans', {})
  const avec = await creer('ACAL426 avec', { pitchSource: { mode: 'degres' }, facingManual: true })
  try {
    const PENTE = "Pan « A » : la pente (22°) n'a jamais été confirmée — confirmez-la avant d'envoyer le devis."
    const FACE = "Pan « A » : la face (180°) n'a jamais été confirmée — confirmez-la avant d'envoyer le devis."
    const r1 = await page.request.post(`${CAL}/calepinages/${sans.id}/generer-devis/`, { ...T, data: {} })
    const c1 = await r1.json()
    console.log(`[ACAL426] sans source : ${r1.status()} devis ${c1.devis} avertissements ${J(c1.avertissements)}`)
    expect(r1.status(), `generer-devis (sans source) → ${J(c1).slice(0, 400)}`).toBe(201)
    expect(c1.devis, 'le devis est créé (aucun blocage)').toBeTruthy()
    expect(c1.avertissements).toEqual(expect.arrayContaining([PENTE, FACE]))
    const r2 = await page.request.post(`${CAL}/calepinages/${avec.id}/generer-devis/`, { ...T, data: {} })
    const c2 = await r2.json()
    console.log(`[ACAL426] pente et face confirmées : ${r2.status()} devis ${c2.devis} avertissements ${J(c2.avertissements)}`)
    expect(r2.status(), `generer-devis (confirmé) → ${J(c2).slice(0, 400)}`).toBe(201)
    expect(c2.avertissements.filter((m) => /n'a jamais été confirmée/.test(m)), 'confirmées : aucun message').toEqual([])
    const statut = await py(`from apps.ventes.models import Devis
sortie(list(Devis.objects.filter(pk__in=[${Number(c1.devis)}, ${Number(c2.devis)}]).values_list('statut', flat=True)))`)
    expect(statut, 'deux devis brouillon, aucun statut touché').toEqual(['brouillon', 'brouillon'])
  } finally {
    await nettoyer(sans, avec)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL445 + ACAL451 + ACAL461 + ACAL463 + ACAL467 + ACAL452 + ACAL475 — PA2.5 : un pan portant facteur de vue du ciel
// et table d'ombrage direct (format ACAL389, celui qu'écrit l'atelier), une courbe de charge, neige saisie par l'API de
// l'écran de réglages ; `simuler/` puis `GET resultat/` et le rapport d'étude PDF.
// ════════════════════════════════════════════════════════════════════════════
const NEIGE = [3, 2, 1, 0, 0, 0, 0, 0, 0, 0, 1, 2]
const COURBE24 = [0.4, 0.4, 0.4, 0.4, 0.4, 0.5, 0.8, 1.2, 1.0, 0.9, 0.9, 1.0, 1.1, 1.0, 0.9, 0.9, 1.0, 1.3, 1.8, 2.0, 1.7, 1.2, 0.8, 0.5]
const SKY = { facteur: 0.8, methode: { diffus: 'isotrope', horizon: false, resolution: 'centres_de_modules' } }
// Lignes = hauteurs, colonnes = azimuts (0 = nord, 90 = est) : soleil sous ~20° ⇒ direct coupé (0), au-dessus libre.
const TABLE = { azimutsDeg: [0, 90, 180, 270], hauteursDeg: [5, 35, 65], facteurs: [[0, 0, 0, 0], [1, 1, 1, 1], [1, 1, 1, 1]], methode: 'centres_de_modules' }

etape('PA2.5-ACAL451-445-461-463-467-452-475-simulation', ['ACAL445', 'ACAL451', 'ACAL452', 'ACAL461', 'ACAL463', 'ACAL467', 'ACAL475'], async ({ page }) => {
  const photo = await photoReglages()
  let cal = null
  try {
    await regler(page.request, {
      simulation: { ...METEO_2020, neige_mensuelle_pct: S(NEIGE, 'acceptation ACAL8 — relevé de neige du site (essai)', 'mesure') },
    })
    cal = await calepinageAvec('ACAL451', docSud(12, { skyViewFactor: SKY, shadeTable: TABLE }, {
      consumption: { methode: 'courbe', courbe24: COURBE24, source: { origine: 'saisie', saisi_le: '2026-11-21T08:00:00Z' } },
    }))
    await designerMateriel(cal.id)
    const res = await simuler(page.request, cal.id)
    expect(res.simule, `simulation servie (${res.motif})`).toBe(true)
    expect(res.simulation_perimee).toBe(false)
    const lignes = (res.cascade?.etapes || []).map((e) => `${e.etape}:${e.motif_omission ? 'omise' : `${e.perte_pct}%`}`)
    console.log(`[PA2.5] P50 ${res.production?.total?.p50_kwh} kWh ; cascade ${lignes.join(' ')}`)

    // ACAL451 — irradiation incidente mensuelle du plan : 12 mois, somme = irradiation de la cascade.
    const irr = res.production?.irradiation_mensuelle
    expect(irr, 'production.irradiation_mensuelle : 12 lignes').toHaveLength(12)
    expect(irr.map((l) => l.mois)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    const sIrr = somme(irr.map((l) => l.irradiation_plan_kwh_m2))
    const cIrr = res.cascade?.irradiation_incidente_kwh_m2
    console.log(`[ACAL451] Σ irradiation mensuelle ${sIrr.toFixed(3)} kWh/m² ; cascade ${cIrr} ; mois ${J(irr.map((l) => l.irradiation_plan_kwh_m2))}`)
    expect(irr.every((l) => typeof l.irradiation_plan_kwh_m2 === 'number' && l.irradiation_plan_kwh_m2 > 0), 'année pleine : 12 mois chiffrés').toBeTruthy()
    expect(Math.abs(sIrr - cIrr), `Σ ${sIrr} = irradiation incidente ${cIrr} (au millième × 12)`).toBeLessThanOrEqual(0.012)

    // ACAL445 — autoconsommation par mois : 12 lignes, Σ = annuel.
    const auto = res.autoconsommation
    const pm = auto?.par_mois
    console.log(`[ACAL445] energie ${J(auto?.energie)} ; motif_absence « ${auto?.motif_absence || ''} » ; par_mois ${J(pm)?.slice(0, 600)}`)
    expect(pm, 'autoconsommation.par_mois : 12 lignes').toHaveLength(12)
    expect(pm.map((l) => l.mois)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    for (const k of ['consommation_kwh', 'production_kwh', 'autoconsomme_kwh', 'import_reseau_kwh', 'export_reseau_kwh']) {
      expect(pm.every((l) => k in l), `chaque mois porte ${k}`).toBeTruthy()
    }
    const sConso = somme(pm.map((l) => l.consommation_kwh))
    const sAuto = somme(pm.map((l) => l.autoconsomme_kwh))
    console.log(`[ACAL445] Σ consommation ${sConso.toFixed(3)} / annuel ${auto.energie.consommation_kwh} ; Σ autoconsommée ${sAuto.toFixed(3)} / annuel ${auto.energie.autoconsomme_kwh}`)
    expect(Math.abs(sConso - auto.energie.consommation_kwh), 'Σ consommation mensuelle = annuelle').toBeLessThanOrEqual(0.012)
    expect(Math.abs(sAuto - auto.energie.autoconsomme_kwh), 'Σ autoconsommée mensuelle = annuelle').toBeLessThanOrEqual(0.012)
    expect(sAuto, 'autoconsommation chiffrée').toBeGreaterThan(0)

    // ACAL463 — neige saisie : étape « neige » appliquée, mode mensuel, perte > 0.
    const neige = etapeDe(res, 'neige')
    console.log(`[ACAL463] neige ${J(neige)?.slice(0, 500)}`)
    expect(neige?.motif_omission || '', 'neige appliquée (non omise)').toBe('')
    expect(neige.entree?.mode).toBe('mensuelle')
    expect(neige.perte_kwh, 'perte de neige chiffrée').toBeGreaterThan(0)

    // ACAL461 — ombrage du diffus : facteur de vue du ciel 0,8 appliqué au diffus.
    const diffus = etapeDe(res, 'ombrage_diffus')
    console.log(`[ACAL461] ombrage_diffus ${J(diffus)?.slice(0, 500)}`)
    expect(diffus?.motif_omission || '', 'ombrage du diffus appliqué').toBe('')
    expect(diffus.perte_kwh, 'perte du diffus chiffrée').toBeGreaterThan(0)

    // ACAL467 — ombrage proche lu dans la TABLE par direction du soleil.
    const proche = etapeDe(res, 'ombrage_proche')
    console.log(`[ACAL467] ombrage_proche ${J(proche)?.slice(0, 600)}`)
    expect(proche?.motif_omission || '', 'ombrage proche appliqué').toBe('')
    expect(proche.entree?.source_ombrage, 'la ligne « Ombrage proche » dit « table »').toBe('table')
    expect(proche.entree?.heures_ombrees, 'des heures au soleil bas ont leur direct coupé').toBeGreaterThan(0)
    expect(proche.perte_kwh).toBeGreaterThan(0)

    // ACAL452 + ACAL475 — rapport d'étude PDF du calepinage simulé.
    const texte = await rapportEtude(page.request, cal.id)
    const extrait = (motif) => { const i = texte.search(motif); return i < 0 ? '(absent)' : texte.slice(i, i + 260) }
    console.log(`[ACAL452] ${extrait(/Irradiation dans le plan/)}`)
    console.log(`[ACAL475] ${extrait(/Note de validation/)} … ${extrait(/Cette étude :/)}`)
    expect(texte, 'section Production : colonne « Irradiation dans le plan (kWh/m²) »').toMatch(/Irradiation dans le plan \(kWh\/m/)
    expect(texte, 'pas la note « irradiation mensuelle non publiée »').not.toMatch(/irradiation mensuelle non publiée/)
    expect(texte, 'section « Note de validation » imprimée').toMatch(/Note de validation/)
    expect(texte, 'méthode du banc').toMatch(/Méthode : la production de notre chaîne/)
    expect(texte, 'écarts informatifs').toMatch(/INFORMATIFS/)
    expect(texte, 'ligne de CETTE étude').toMatch(/Cette étude :/)
    expect(texte, 'aucune revendication « validé »').not.toMatch(/\bvalidée? par\b/i)
  } finally {
    await nettoyer(cal)
    await rendreReglages(photo)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL462 — PA2.5 : accès solaire par module (un module à 0,5) et seuil de dérivation saisi ⇒ étape
// `mismatch_ombrage` appliquée, rapport d'étude : « Ombrage électrique des chaînes » et ses deux bornes.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL462-ombrage-electrique-rapport', ['ACAL462'], async ({ page }) => {
  const photo = await photoReglages()
  let cal = null
  try {
    await regler(page.request, {
      simulation: { ...METEO_2020, seuil_derivation_acces: S(0.6, 'acceptation ACAL8 — seuil de dérivation (essai)', 'saisie') },
    })
    const acces = Array.from({ length: 12 }, (_, i) => (i === 2 ? 0.5 : 1.0))
    cal = await calepinageAvec('ACAL462', docSud(12, {
      solarAccess: { values: acces, method: 'centres_de_modules', computedAt: '2026-11-21T08:00:00Z' },
    }))
    await designerMateriel(cal.id)
    const res = await simuler(page.request, cal.id)
    expect(res.simule, `simulation servie (${res.motif})`).toBe(true)
    const mm = etapeDe(res, 'mismatch_ombrage')
    console.log(`[ACAL462] mismatch_ombrage ${J(mm)?.slice(0, 900)} ; affectation ${J(res.electrique?.affectation)?.slice(0, 300)}`)
    expect(mm?.motif_omission || '', 'mismatch d’ombrage calculé').toBe('')
    const bornes = mm.entree?.bornes
    expect(bornes?.basse?.perte_chaine_pct, 'borne basse publiée').toEqual(expect.any(Number))
    expect(bornes?.haute?.perte_chaine_pct, 'borne haute publiée').toEqual(expect.any(Number))
    expect(bornes.haute.perte_chaine_pct, 'borne haute ≥ borne basse').toBeGreaterThanOrEqual(bornes.basse.perte_chaine_pct)
    const texte = await rapportEtude(page.request, cal.id)
    const i = texte.search(/Ombrage électrique des chaînes/)
    console.log(`[ACAL462] rapport : ${i < 0 ? '(absent)' : texte.slice(i, i + 420)}`)
    expect(i, 'section ombrage : « Ombrage électrique des chaînes »').toBeGreaterThanOrEqual(0)
    const para = texte.slice(i, i + 600)
    expect(para, 'borne basse (retenue) imprimée').toMatch(/Borne basse \(retenue\)/)
    expect(para, 'borne haute imprimée').toMatch(/borne haute/)
    expect(para, 'seuil et sa source').toMatch(/Seuil de dérivation : 0[.,]6/)
    expect(para, 'jamais « non calculé »').not.toMatch(/non calculé/)
  } finally {
    await nettoyer(cal)
    await rendreReglages(photo)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL455 + ACAL456 — PA2.5 : CSV horizontal DÉPOSÉ (48 h réelles de la fixture PVGIS TMY de Casablanca), modèle et
// albédo saisis, `simuler/` ⇒ `meteo.transposition` ; CSV au global seul + modèle de décomposition ⇒
// `meteo.decomposition` et composantes « deduites ».
// ════════════════════════════════════════════════════════════════════════════
const TMY = JSON.parse(readFileSync(join(RACINE, 'backend/django_core/apps/calepinage/tests/fixtures_pvgis/tmy_casablanca.json'), 'utf8')).outputs.tmy_hourly
const HEURES48 = TMY.slice(0, 48).map((r, rang) => ({ jour: 15 + Math.floor(rang / 24), heure: rang % 24, r }))
const horo = (h) => `2020-01-${h.jour}T${String(h.heure).padStart(2, '0')}:00:00+00:00`
const CSV_HORIZONTAL = ['horodatage,ghi_w_m2,dni_w_m2,dhi_w_m2,t2m_c,ws10m',
  ...HEURES48.map((h) => `${horo(h)},${h.r['G(h)']},${h.r['Gb(n)']},${h.r['Gd(h)']},${h.r.T2m},${h.r.WS10m}`)].join('\n') + '\n'
const CSV_GLOBAL = ['horodatage,ghi_w_m2,t2m_c,ws10m',
  ...HEURES48.map((h) => `${horo(h)},${h.r['G(h)']},${h.r.T2m},${h.r.WS10m}`)].join('\n') + '\n'
const PAN_20_200 = { version: 2, pin: PIN, zones: [{ id: 'z1', label: 'PAN-SSO', vertices: PAN_A, pitchDeg: 20, facingAzimuthDeg: 200,
  geometry: { count: 12, azimuthDeg: 200.0, tiltDeg: 20.0, family: 'surimposition' } }] }

async function deposerMeteo(request, id, nom, csv) {
  const r = await request.post(`${CAL}/calepinages/${id}/meteo-fichier/`, {
    ...T, multipart: { fichier: { name: nom, mimeType: 'text/csv', buffer: Buffer.from(csv, 'utf8') }, fournisseur: 'PVGIS (TMY Casablanca, fixture enregistrée)' },
  })
  const corps = await r.text()
  expect(r.status(), `POST meteo-fichier/ ${nom} → ${corps.slice(0, 400)}`).toBe(201)
  return JSON.parse(corps)
}

const REGLAGES_METEO_FICHIER = {
  simulation: {
    ...METEO_2020,
    modele_transposition: S('isotropic', 'acceptation ACAL8 — modèle choisi par la société (essai)'),
    modele_decomposition: S('erbs', 'acceptation ACAL8 — modèle choisi par la société (essai)'),
    albedo_mensuel: S(0.2, 'acceptation ACAL8 — albédo mesuré (essai)', 'mesure'),
  },
}

etape('PA2.5-ACAL455-transposition-csv-horizontal', ['ACAL455'], async ({ page }) => {
  const photo = await photoReglages()
  let a = null
  try {
    await regler(page.request, REGLAGES_METEO_FICHIER)
    a = await calepinageAvec('ACAL455', PAN_20_200)
    await designerMateriel(a.id)
    const depot = await deposerMeteo(page.request, a.id, 'casablanca-horizontal.csv', CSV_HORIZONTAL)
    console.log(`[ACAL455] dépôt : ${J(depot).slice(0, 400)}`)
    const ra = await simuler(page.request, a.id)
    expect(ra.simule, `simulation servie (${ra.motif})`).toBe(true)
    console.log(`[ACAL455] meteo ${J(ra.meteo).slice(0, 1200)} ; P50 ${ra.production?.total?.p50_kwh}`)
    expect(ra.meteo?.service, 'la simulation a pris le fichier déposé').toBe('fichier')
    expect(ra.meteo?.fichier?.nom).toBe('casablanca-horizontal.csv')
    expect(ra.meteo?.transposition?.modele, 'meteo.transposition.modele = réglage').toBe('isotropic')
    expect(String(ra.meteo.transposition.reference || ''), 'référence du modèle nommée').toMatch(/isotrop/i)
    expect(ra.meteo.transposition.albedo, 'albédo et sa source').toEqual({ valeur: Array(12).fill(0.2), source: 'mesure' })
    expect(ra.meteo.decomposition, 'aucune décomposition pour un fichier aux composantes mesurées').toBeFalsy()
    expect(ra.production?.total?.p50_kwh, 'production chiffrée sur le fichier déposé').toBeGreaterThan(0)
  } finally {
    await nettoyer(a)
    await rendreReglages(photo)
  }
})

etape('PA2.5-ACAL456-decomposition-csv-global', ['ACAL456'], async ({ page }) => {
  const photo = await photoReglages()
  let b = null
  try {
    await regler(page.request, REGLAGES_METEO_FICHIER)
    b = await calepinageAvec('ACAL456', PAN_20_200)
    await designerMateriel(b.id)
    const depot = await deposerMeteo(page.request, b.id, 'casablanca-global-seul.csv', CSV_GLOBAL)
    console.log(`[ACAL456] dépôt : ${J(depot).slice(0, 600)}`)
    const rb = await simuler(page.request, b.id)
    expect(rb.simule, `simulation servie (${rb.motif})`).toBe(true)
    console.log(`[ACAL456] meteo ${J(rb.meteo).slice(0, 1200)} ; P50 ${rb.production?.total?.p50_kwh}`)
    expect(rb.meteo?.service, 'la simulation a pris le fichier déposé').toBe('fichier')
    expect(rb.meteo?.transposition?.modele, 'puis transposées').toBe('isotropic')
    expect(rb.production?.total?.p50_kwh, 'production chiffrée').toBeGreaterThan(0)
    // Diagnostic (avant l'assertion) : ce que la série DÉPOSÉE porte côté serveur, et les clés de `meteo` servies.
    const deposee = await py(`from apps.calepinage.models import Calepinage
from apps.calepinage.services.simulation import _serie_meteo_deposee
f = _serie_meteo_deposee(Calepinage.objects.get(pk=${Number(b.id)})) or {}
m = f.get('meteo') or {}
sortie({'a_decomposer': f.get('a_decomposer'), 'composantes_origine': m.get('composantes_origine'),
        'decomposition': m.get('decomposition'), 'plan_des_donnees': f.get('plan_des_donnees')})`)
    console.log(`[ACAL456] série déposée (serveur) : ${J(deposee)} ; dépôt.meteo.composantes_origine=${depot?.meteo?.composantes_origine} ; clés de meteo servies : ${Object.keys(rb.meteo || {}).sort().join(',')}`)
    expect(rb.meteo?.decomposition?.modele, '`GET resultat/` : meteo.decomposition.modele = réglage').toBe('erbs')
    expect(rb.meteo.decomposition.hypothese).toBe('composantes déduites du global, non mesurées')
    expect(String(rb.meteo.decomposition.reference || '')).not.toBe('')
    expect(rb.meteo.composantes_origine, 'composantes « deduites »').toBe('deduites')
  } finally {
    await nettoyer(b)
    await rendreReglages(photo)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL468 + ACAL477 — balayage d'un CHAMP AU SOL : grille 3 × 3 (inclinaison × azimut) et optimum nommé ; axe ratio
// DC/AC (trois ratios) ⇒ `ecretage_pct` strictement croissant, la série d'irradiance partagée ; refus nommés en 400.
// ════════════════════════════════════════════════════════════════════════════
etape('API-ACAL468-477-balayage', ['ACAL468', 'ACAL477'], async ({ page }) => {
  const photo = await photoReglages()
  let cal = null
  try {
    await regler(page.request, { simulation: METEO_2020 })
    cal = await calepinageAvec('ACAL468', {
      version: 2, pin: PIN, zones: [],
      poseSurfaces: [{ id: 'champ-1', kind: 'sol', label: 'CHAMP-SOL', moduleWc: 710, tiltDeg: 20.0, rowAzimuthDeg: 90.0, engine: { modules: 24 } }],
    })
    await designerMateriel(cal.id)
    // Refus nommés AVANT la file.
    const pas0 = await page.request.post(`${CAL}/calepinages/${cal.id}/balayage/`, {
      ...T, data: { pan: 1, axes: [{ nom: 'inclinaison_deg', min: 10, max: 30, pas: 0 }] },
    })
    const c0 = await pas0.json()
    expect(pas0.status(), `pas 0 → ${J(c0)}`).toBe(400)
    expect(Object.keys(c0), 'le champ fautif est nommé').toEqual(['axes[0].pas'])

    const grille = await balayer(page.request, cal.id, {
      pan: 1, axes: [{ nom: 'inclinaison_deg', min: 10, max: 30, pas: 10 }, { nom: 'azimut_deg', min: 160, max: 200, pas: 20 }],
    })
    console.log(`[ACAL468] grille ${J(grille.grille.map((l) => [l.inclinaison_deg, l.azimut_deg, l.rendement_specifique_kwh_kwc]))} ; optimum ${J(grille.optimum)} ; appels PVGIS ${grille.appels_pvgis} ; complete ${grille.complete}`)
    expect(grille.etat).toBe('done')
    expect(grille.grille, 'grille 3 × 3').toHaveLength(9)
    expect(grille.grille.every((l) => l.p50_kwh > 0 && l.rendement_specifique_kwh_kwc > 0), 'chaque point chiffré').toBeTruthy()
    const meilleur = Math.max(...grille.grille.map((l) => l.rendement_specifique_kwh_kwc))
    expect(grille.optimum?.rendement_specifique_kwh_kwc, 'optimum = meilleur rendement de la grille').toBe(meilleur)
    expect([10, 20, 30]).toContain(grille.optimum.inclinaison_deg)
    expect([160, 180, 200]).toContain(grille.optimum.azimut_deg)
    expect(grille.appels_pvgis, 'appels PVGIS comptés').toBeGreaterThanOrEqual(1)
    const stocke = (await lireLayout(page.request, cal.id)).roof_layout
    expect(stocke.poseSurfaces[0].tiltDeg, 'rien n’est écrit au calepinage').toBe(20)

    const ratios = await balayer(page.request, cal.id, { pan: 1, axes: [{ nom: 'ratio_dc_ac', min: 1.25, max: 1.75, pas: 0.25 }] })
    const ecr = ratios.grille.map((l) => l.ecretage_pct)
    console.log(`[ACAL477] ratios ${J(ratios.grille.map((l) => [l.ratio_dc_ac, l.p50_kwh, l.ecretage_pct, l.ratio_hors_bornes]))} ; appels PVGIS ${ratios.appels_pvgis} ; mention « ${ratios.grille[0]?.mention_ratio} »`)
    expect(ratios.grille, 'trois ratios').toHaveLength(3)
    expect(ecr.every((v) => typeof v === 'number'), 'ecretage_pct publié pour chaque ratio').toBeTruthy()
    expect(ecr[1] > ecr[0] && ecr[2] > ecr[1], `ecretage_pct strictement croissant ${J(ecr)}`).toBeTruthy()
    // « Sur la MÊME série » : le même balayage rejoué au shell avec un client PVGIS neuf (cache de processus partagé),
    // appels RÉELS triés : série d'irradiance (seriescalc sans pvcalculation) contre contrôle PVcalc (pvcalculation=1).
    const appels = await travailler(`from apps.calepinage.models import Calepinage
from apps.calepinage.services.balayage import balayer as balayer_service
from apps.calepinage.services.pvgis_serie import ClientPvgis
c = Calepinage.objects.get(pk=${Number(cal.id)})
cl = ClientPvgis()
r = balayer_service(c, json.loads(${J(J({ pan: 1, axes: [{ nom: 'ratio_dc_ac', min: 1.25, max: 1.75, pas: 0.25 }] }))}), client=cl)
reels = [u for u in cl.urls_appelees if u]
sortie({'reels': len(reels), 'servis_cache': len([u for u in cl.urls_appelees if u is None]),
        'serie': len([u for u in reels if '/seriescalc?' in u and 'pvcalculation=1' not in u]),
        'pvcalc': len([u for u in reels if 'pvcalculation=1' in u]),
        'ecretage': [l['ecretage_pct'] for l in r['grille']], 'appels_pvgis': r['appels_pvgis']})`)
    console.log(`[ACAL477] appels du balayage des ratios (route) : ${ratios.appels_pvgis} ; rejoué au shell : ${J(appels)}`)
    expect(appels.ecretage, 'rejoué : mêmes écrêtages').toEqual(ecr)
    expect(appels.serie, 'série d’irradiance partagée : aucun appel de série par ratio').toBeLessThanOrEqual(1)
    expect(String(ratios.grille[0].mention_ratio || ''), 'hypothèse « remis à l’échelle » dite').toMatch(/remis à l.échelle/)
  } finally {
    await nettoyer(cal)
    await rendreReglages(photo)
  }
})
