// Acceptation en direct — groupe ACAL, neuvième lot (runner GitHub) : la détection du toit par IA AVEC LA VRAIE CLÉ
// Claude (D-ACAL-33 ; clé autorisée par Reda le 21/11, secret de dépôt `CLAUDE_API_KEY` passé par le workflow en
// `VISION_TOIT_CLE_API`, jamais écrite ni affichée).
//   ACAL489 (noyau IA, plan sécurité) : capacité `vision_toit` + fournisseur Claude — un appel RÉEL rend une
//     proposition validée, jetons non nuls, seuls les octets et le type de l'image partent.
//   ACAL485 (plan calepinage) : `GET/POST calepinages/<pk>/detection-toit/` — disponibilité, proposition à confirmer
//     en lng/lat, rien écrit sur le calepinage, chaque appel journalisé.
// IMAGE : orthophoto RÉELLE de l'USGS (The National Map, « USGS Imagery Only », domaine public, œuvre du gouvernement
// fédéral américain), demandée au moment de la spec par l'export ArcGIS avec une emprise EPSG:4326 : l'emprise RENDUE
// par le service (`extent`) est celle envoyée à la route. Aucune vue aérienne réelle n'est dans le dépôt (les
// `VUE_TOITURE_*.png` de docs/ao-frdisi sont des plans dessinés, les photos du site sont en webp, refusé par la route).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { API_DJANGO, assurerSessionPage, lireJson } from '../helpers.js'

const etape = groupe('ACAL', ['ACAL485', 'ACAL489'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const CAL = `${API_DJANGO}/calepinage`
const T = { timeout: 150_000 }
const USGS = 'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/export'
// Résidence de la Maison-Blanche (Washington) : toit net, bien dégagé ; 768 × 512 px pour 0,0015° × 0,0010°.
const BBOX = { ouest: -77.0375, sud: 38.8971, est: -77.0360, nord: 38.8981 }
const NOM_LEAD = `ACC9 Vision ${Date.now().toString(36).toUpperCase()}`
const ADRESSE = '12 rue des Essais Vision'

const etat = {}
const LAYOUT = {
  version: 2, pin: { lat: 38.8976, lng: -77.0367 }, activeAreaId: 'z1',
  zones: [{ id: 'z1', label: 'Pan tracé à la main', roofType: 'flat', pitchDeg: 10, facingAzimuthDeg: 180,
    vertices: [[-77.0372, 38.8978], [-77.0362, 38.8978], [-77.0362, 38.8975], [-77.0372, 38.8975]] }],
}

/** Image réelle + emprise RENDUE par le service (domaine public USGS). */
async function image(request) {
  if (etat.image) return etat.image
  const q = new URLSearchParams({
    bbox: `${BBOX.ouest},${BBOX.sud},${BBOX.est},${BBOX.nord}`, bboxSR: '4326', imageSR: '4326',
    size: '768,512', format: 'jpg', f: 'json',
  })
  const meta = await lireJson(await request.get(`${USGS}?${q}`, T), 'export USGS (métadonnées)')
  const r = await request.get(meta.href, T)
  expect(r.ok(), `image USGS → HTTP ${r.status()}`).toBeTruthy()
  const buffer = await r.body()
  expect(buffer.subarray(0, 3).toString('hex'), 'JPEG (octets magiques)').toBe('ffd8ff')
  const e = meta.extent
  etat.image = { buffer, emprise: { ouest: e.xmin, sud: e.ymin, est: e.xmax, nord: e.ymax }, w: meta.width, h: meta.height }
  console.log(`[acal9] image USGS ${buffer.length} o, ${meta.width}×${meta.height}, emprise ${JSON.stringify(etat.image.emprise)}`)
  return etat.image
}

/** Lead (nom + adresse de contrôle) + calepinage vide de la société demo, posés au shell. */
async function calepinage() {
  if (etat.cal) return etat.cal
  // Conception NON vide (un pan déjà tracé, empreinte calculée) : E4 prouve que la proposition ne l'écrase pas.
  etat.cal = await py(`import json
from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
from apps.ventes.domain.geometrie import layout_hash
co = U.objects.get(username='demo_admin').company
lead = Lead.objects.create(company=co, nom=${JSON.stringify(NOM_LEAD)}, adresse=${JSON.stringify(ADRESSE)}, ville='Casablanca', type_installation='residentiel')
lay = json.loads(${JSON.stringify(JSON.stringify(LAYOUT))})
c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre=${JSON.stringify(NOM_LEAD)}, roof_layout=lay, layout_hash=layout_hash(lay))
c.refresh_from_db()
sortie({'id': c.pk, 'lead': lead.pk, 'company': co.pk, 'layout_hash': c.layout_hash, 'roof_layout': c.roof_layout})`)
  return etat.cal
}

const dansEmprise = (p, e) => p[0] >= e.ouest - 1e-9 && p[0] <= e.est + 1e-9 && p[1] >= e.sud - 1e-9 && p[1] <= e.nord + 1e-9

etape('E1.disponible_avec_cle', ['ACAL485', 'ACAL489'], async ({ page }) => {
  const cal = await calepinage()
  const reglages = await py(`from django.conf import settings
from core.ai.registry import get_provider, is_capability_configured
p = get_provider('vision_toit')
sortie({'cle_posee': bool(settings.VISION_TOIT_CLE_API), 'modele': settings.VISION_TOIT_MODELE,
        'ai_providers': settings.AI_PROVIDERS, 'carte': settings.DETECTION_TOIT_CAPTURE_CARTE,
        'fournisseur': p.key, 'configure': is_capability_configured('vision_toit')})`)
  console.log(`[acal9] E1 réglages : ${JSON.stringify(reglages)}`)
  expect(reglages.cle_posee, 'VISION_TOIT_CLE_API posée').toBe(true)
  expect(reglages.fournisseur).toBe('claude')
  const dispo = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/detection-toit/`, T), 'GET detection-toit')
  console.log(`[acal9] E1 GET : ${JSON.stringify(dispo)}`)
  expect(dispo.disponible).toBe(true)
  expect(dispo.motif).toBe('')
  expect(dispo.origines_acceptees).toEqual(reglages.carte ? ['importee', 'carte'] : ['importee'])
})

etape('E2.proposition_reelle', ['ACAL485', 'ACAL489'], async ({ page }) => {
  const cal = await calepinage()
  const img = await image(page.request)
  etat.usageAvant = (await py(`from apps.agent.models import UsageIA
d = UsageIA.objects.order_by('-pk').first()
sortie({'pk': d.pk if d else 0})`)).pk
  const debut = Date.now()
  const r = await page.request.post(`${CAL}/calepinages/${cal.id}/detection-toit/`, {
    ...T,
    multipart: {
      image: { name: 'toit-usgs.jpg', mimeType: 'image/jpeg', buffer: img.buffer },
      emprise: JSON.stringify(img.emprise),
      origine: 'importee',
    },
  })
  const texte = await r.text()
  console.log(`[acal9] E2 POST → HTTP ${r.status()} en ${Date.now() - debut} ms : ${texte}`)
  expect(r.status(), `POST detection-toit : ${texte}`).toBe(200)
  const corps = JSON.parse(texte)
  expect(corps.provenance).toBe('ia')
  expect(corps.a_confirmer).toBe(true)
  const { contour_lnglat: contour, pans } = corps.propositions
  expect(pans.length, 'au moins un pan proposé').toBeGreaterThan(0)
  expect(contour.length, 'contour d’ensemble ≥ 3 sommets').toBeGreaterThanOrEqual(3)
  for (const p of [...contour, ...pans.flatMap((x) => x.contour_lnglat)]) {
    expect(dansEmprise(p, img.emprise), `sommet ${p} dans l’emprise`).toBe(true)
  }
  for (const pan of pans) {
    expect(pan.contour_lnglat.length).toBeGreaterThanOrEqual(3)
    expect(pan.confiance === null || (pan.confiance >= 0 && pan.confiance <= 1)).toBe(true)
  }
  etat.proposition = corps
  console.log(`[acal9] E2 proposition : ${pans.length} pan(s), confiances ${JSON.stringify(pans.map((x) => x.confiance))}, contour ${contour.length} sommets`)
  // Capture : l'image réelle + la proposition reprojetée en pixels (ce que l'écran d'ACAL488 montrera).
  const e = img.emprise
  const px = (p) => `${((p[0] - e.ouest) / (e.est - e.ouest)) * img.w},${((e.nord - p[1]) / (e.nord - e.sud)) * img.h}`
  const poly = (pts, c) => `<polygon points="${pts.map(px).join(' ')}" fill="${c}33" stroke="${c}" stroke-width="3"/>`
  await page.setContent(`<body style="margin:0;font:14px sans-serif"><svg width="${img.w}" height="${img.h}">
    <image href="data:image/jpeg;base64,${img.buffer.toString('base64')}" width="${img.w}" height="${img.h}"/>
    ${pans.map((x) => poly(x.contour_lnglat, '#ff8800')).join('')}${poly(contour, '#00aaff')}</svg>
    <div style="padding:6px">ACAL485/489 — proposition IA (à confirmer) : ${pans.length} pan(s) orange, contour bleu ;
    orthophoto USGS (domaine public).</div></body>`)
})

// Juste après E2 et AVANT l'appel au shell d'E4 : la SEULE ligne nouvelle est celle de l'appel de la VRAIE route.
etape('E3.journal_usage_persiste', ['ACAL485', 'ACAL489'], async () => {
  const cal = await calepinage()
  expect(etat.proposition, 'E2 a rendu une proposition').toBeTruthy()
  const j = await py(`from django.forms.models import model_to_dict
from apps.agent.models import UsageIA
from core.ai.usage import usage_sinks
rows = list(UsageIA.objects.filter(pk__gt=${etat.usageAvant}).order_by('pk'))
champs = sorted(f.name for f in UsageIA._meta.concrete_fields)
texte = ' '.join(str(v) for r in rows for v in model_to_dict(r).values())
sortie({'puits': [getattr(s, '__qualname__', str(s)) for s in usage_sinks()], 'champs': champs,
        'lignes': [{k: str(v) for k, v in model_to_dict(r).items()} | {'created_at': str(r.created_at)} for r in rows],
        'pii': [x for x in (${JSON.stringify(NOM_LEAD)}, ${JSON.stringify(ADRESSE)}, 'Casablanca') if x in texte]})`)
  console.log(`[acal9] E3 journal : ${JSON.stringify(j)}`)
  expect(j.lignes.length, 'exactement UNE ligne UsageIA nouvelle pour l’appel de la route').toBe(1)
  const l = j.lignes[0]
  expect(Number(l.company)).toBe(cal.company)
  expect(l.capability).toBe('vision_toit')
  expect(l.provider).toBe('claude')
  expect(l.feature_key).toBe('calepinage.detection_toit')
  expect(Number(l.input_tokens), 'jetons d’entrée').toBeGreaterThan(0)
  expect(Number(l.output_tokens), 'jetons de sortie').toBeGreaterThan(0)
  expect(l.success).toBe('True')
  expect(Number(l.duration_ms)).toBeGreaterThan(0)
  // Aucun contenu stocké : métriques seulement (aucun champ texte libre, aucune donnée du lead).
  expect(j.champs).toEqual(['capability', 'company', 'cout', 'created_at', 'duration_ms', 'feature_key', 'id',
    'input_tokens', 'output_tokens', 'provider', 'success', 'updated_at'])
  expect(j.pii, 'aucune donnée du lead dans la ligne').toEqual([])
})

etape('E4.appel_reel_jetons', ['ACAL489'], async ({ page }) => {
  const cal = await calepinage()
  const img = await image(page.request)
  // Second appel RÉEL, au shell, par le service (même chemin que la route) : un puits en mémoire relit la ligne
  // d'usage écrite par l'enveloppe du noyau, un transport-témoin relit la REQUÊTE partie (corps seulement, jamais
  // les en-têtes : la clé y est) puis la transmet au vrai réseau.
  const r = await py(`import base64, json as _j, httpx
from core.ai.usage import register_usage_sink, unregister_usage_sink
from core.ai.fournisseurs_claude import ClaudeVisionToitProvider
from apps.calepinage.services import detection_toit as svc
lignes, vu = [], {}
def puits(**m): lignes.append(m)
class Temoin(httpx.BaseTransport):
    def __init__(self): self.reel = httpx.HTTPTransport()
    def handle_request(self, req):
        corps = _j.loads(req.content.decode())
        brut = req.content.decode()
        vu['cles'] = sorted(corps)
        vu['modele'] = corps.get('model')
        vu['blocs'] = [b.get('type') for m in corps['messages'] for b in m['content']]
        vu['source'] = sorted(corps['messages'][0]['content'][0]['source'])
        vu['nom_lead'] = ${JSON.stringify(NOM_LEAD)} in brut
        vu['adresse'] = ${JSON.stringify(ADRESSE)} in brut
        vu['casablanca'] = 'Casablanca' in brut
        vu['lead_id'] = ('"lead"' in brut) or ('lead_id' in brut)
        rep = self.reel.handle_request(req); rep.read()
        vu['statut'] = rep.status_code
        try:
            d = _j.loads(rep.content)
            vu['erreur'] = (d.get('error') or {}) if rep.status_code >= 400 else None
            vu['usage_api'] = d.get('usage'); vu['modele_rendu'] = d.get('model'); vu['stop'] = d.get('stop_reason')
        except Exception as exc:
            vu['erreur'] = repr(exc)[:200]
        return rep
register_usage_sink(puits)
ClaudeVisionToitProvider.transport = Temoin()
try:
    try:
        prop = svc.detecter(${cal.company}, base64.b64decode(${JSON.stringify(img.buffer.toString('base64'))}), 'image/jpeg', ${JSON.stringify(img.emprise)})
        res = {'pans': len(prop['pans']), 'confiances': [p['confiance'] for p in prop['pans']]}
    except svc.DetectionIndisponible:
        res = {'indisponible': True}
finally:
    ClaudeVisionToitProvider.transport = None
    unregister_usage_sink(puits)
sortie({'resultat': res, 'lignes': [{k: str(v) for k, v in l.items()} for l in lignes], 'requete': vu})`)
  console.log(`[acal9] E4 : ${JSON.stringify(r)}`)
  etat.temoin = r.requete
  expect(r.requete.statut, `API Anthropic : ${JSON.stringify(r.requete.erreur)}`).toBe(200)
  expect(r.resultat.pans, 'proposition validée par le noyau').toBeGreaterThan(0)
  expect(r.lignes.length, 'une ligne d’usage par appel').toBe(1)
  const l = r.lignes[0]
  expect(l.capability).toBe('vision_toit')
  expect(l.provider).toBe('claude')
  expect(l.feature_key).toBe('calepinage.detection_toit')
  expect(l.success).toBe('True')
  expect(Number(l.prompt_tokens), 'jetons d’entrée').toBeGreaterThan(0)
  expect(Number(l.completion_tokens), 'jetons de sortie').toBeGreaterThan(0)
  expect(Number(l.company_id)).toBe(cal.company)
})

etape('E5.rien_ecrit_sur_le_calepinage', ['ACAL485'], async () => {
  const cal = await calepinage()
  expect(etat.proposition, 'E2 a rendu une proposition (sinon rien à vérifier)').toBeTruthy()
  const apres = await py(`from apps.calepinage.models import Calepinage
c = Calepinage.objects.get(pk=${cal.id})
sortie({'layout_hash': c.layout_hash, 'roof_layout': c.roof_layout})`)
  console.log(`[acal9] E5 avant ${cal.layout_hash} / après ${apres.layout_hash}`)
  expect(cal.layout_hash, 'empreinte de départ non vide').toMatch(/^[0-9a-f]{64}$/)
  expect(apres.layout_hash).toBe(cal.layout_hash)
  expect(apres.roof_layout).toEqual(cal.roof_layout)
})

etape('E6.aucune_donnee_personnelle_envoyee', ['ACAL485', 'ACAL489'], async () => {
  const t = etat.temoin
  expect(t, 'E4 a capturé la requête partie').toBeTruthy()
  console.log(`[acal9] E6 requête : ${JSON.stringify(t)}`)
  expect(t.cles).toEqual(['max_tokens', 'messages', 'model', 'system'])
  expect(t.blocs, 'un seul bloc : l’image').toEqual(['image'])
  expect(t.source).toEqual(['data', 'media_type', 'type'])
  expect(t.modele).toBe(process.env.VISION_TOIT_MODELE || t.modele)
  expect(t.nom_lead, 'nom du lead absent').toBe(false)
  expect(t.adresse, 'adresse absente').toBe(false)
  expect(t.casablanca, 'ville absente').toBe(false)
  expect(t.lead_id, 'aucun identifiant de lead').toBe(false)
})
