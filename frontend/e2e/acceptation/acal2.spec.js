// Acceptation en direct — groupe ACAL, second lot : ACAL374 (resynchronisation), ACAL375 (fichier météo retiré) et
// ACAL376 (provenance météo du rapport). Format : `_format.md`. ACAL366 / ACAL367 ne sont PAS jouées ici : elles
// exigent le constructeur 3D, qui ne démarre pas sans clé carte (PUBLIC_MAPTILER_KEY absente de la pile locale).
// ACAL375 est joué par l'API réelle ; ACAL374 et ACAL376 rejouent la sonde commitée du constat (`scripts/sonde.py`,
// transaction annulée) : la resynchronisation du devis et le rapport sont des services serveur.
import { spawnSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { groupe } from './_oracles.js'
import { RACINE, aujourdHui } from './_enregistrement.js'
import {
  API_DJANGO, assurerSessionPage, executerDansDjango, lireJson, listeDe, uniq, telephoneMobileUnique,
} from '../helpers.js'

test.describe.configure({ timeout: 900_000 })
test.use({ viewport: { width: 1600, height: 1000 }, actionTimeout: 60_000 })
const etape = groupe('ACAL', ['ACAL374', 'ACAL375', 'ACAL376'])
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const CAL = `${API_DJANGO}/calepinage`
const CONTENEUR = (process.env.E2E_DJANGO_EXEC || 'docker exec live2-django').split(' ').pop()

function py(code) {
  const m = String(executerDansDjango(code)).match(/@@JSON@@(.*)/)
  if (!m) throw new Error('sortie Django sans JSON')
  return JSON.parse(m[1])
}
function rejouerSonde(constat) {
  // `sonde.py` sort en 1 quand le verdict est ÉCART (le constat n'est plus reproduit) : la sortie est lue quel que soit le code.
  const r = spawnSync('python', ['scripts/sonde.py', `ACAL/${constat}`, '--conteneur', CONTENEUR],
    { cwd: RACINE, encoding: 'utf8', timeout: 600_000 })
  const sortie = `${r.stdout || ''}${r.stderr || ''}`
  const dossier = join(RACINE, 'docs/qa-explorer/captures', aujourdHui())
  mkdirSync(dossier, { recursive: true })
  writeFileSync(join(dossier, `ACCEPTATION-ACAL-sonde-${constat}.txt`), sortie, 'utf8')
  return sortie
}

const csvMeteo = () => {
  const lignes = ['horodatage;gi_w_m2;gb_i_w_m2;gd_i_w_m2;gr_i_w_m2;t2m_c;ws10m']
  for (let h = 0; h < 24; h += 1) {
    const arche = Math.max(0, Math.sin((Math.PI * (h - 6)) / 12))
    const g = Math.round(900 * arche * 100) / 100
    lignes.push([`2021-01-01T${String(h).padStart(2, '0')}:00:00+00:00`, g, Math.round(g * 75) / 100,
      Math.round(g * 20) / 100, Math.round(g * 5) / 100, Math.round((12 + 10 * arche) * 100) / 100, 2.5].join(';'))
  }
  return `${lignes.join('\r\n')}\r\n`
}

async function nouveauCalepinage(request) {
  const lead = await lireJson(await request.post(`${API_DJANGO}/crm/leads/`, {
    data: { nom: uniq('ACC CAL Meteo'), ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '800' },
  }), 'lead')
  return lireJson(await request.post(`${CAL}/calepinages/`, { data: { lead: lead.id, titre: uniq('ACC CAL Meteo') }, timeout: 120_000 }), 'calepinage')
}
const deposer = async (request, calId, nom = 'site.csv') => request.post(`${CAL}/calepinages/${calId}/meteo-fichier/`, {
  multipart: { fournisseur: 'Meteonorm', fichier: { name: nom, mimeType: 'text/csv', buffer: Buffer.from(csvMeteo()) } },
})
const retenu = async (request, calId) => (await request.get(`${CAL}/calepinages/${calId}/meteo-fichier/`)).json()

// ── ACAL375 : un fichier météo retiré reste retiré après la purge de la corbeille ───────────
etape('PA2.5', ['ACAL375'], async ({ page }) => {
  const cal = await nouveauCalepinage(page.request)
  const dep = await deposer(page.request, cal.id)
  expect(dep.status(), `dépôt (${(await dep.text()).slice(0, 300)})`).toBe(201)
  const avant = await retenu(page.request, cal.id)
  expect(avant?.nom).toBe('site.csv')
  expect(avant?.fournisseur).toBe('Meteonorm')
  const ret = await page.request.delete(`${CAL}/calepinages/${cal.id}/meteo-fichier/`)
  expect(ret.status(), 'Retirer le fichier météo').toBeLessThan(300)
  expect(await retenu(page.request, cal.id), 'retiré : null').toBeNull()
  // La corbeille passe 30 jours plus tard : entrée échue, puis la commande de purge réelle.
  const purge = py(`
import json
from datetime import timedelta
from django.core.management import call_command
from django.utils import timezone
from apps.calepinage.models import Calepinage
from apps.trash.models import ElementSupprime
cal = Calepinage.objects.get(pk=${cal.id})
n = ElementSupprime.objects.filter(company=cal.company, restaure_le__isnull=True).update(expire_le=timezone.now() - timedelta(days=1))
call_command('purger_corbeille_transverse', company=cal.company_id)
cal.refresh_from_db()
print('@@JSON@@' + json.dumps({'echues': n, 'retirees': cal.meteo_retirees}))
`)
  expect(purge.echues).toBeGreaterThan(0)
  expect(purge.retirees.length, 'marqueur « retiré » conservé après la purge').toBeGreaterThan(0)
  expect(await retenu(page.request, cal.id), 'après la purge : toujours null (jamais l’ancien fichier)').toBeNull()
  // Restaurer AVANT la purge rend la pièce retenue (ACAL148 inchangé) ; un remplacement retire l'ancien.
  const cal2 = await nouveauCalepinage(page.request)
  expect((await deposer(page.request, cal2.id, 'a.csv')).status()).toBe(201)
  expect((await page.request.delete(`${CAL}/calepinages/${cal2.id}/meteo-fichier/`)).status()).toBeLessThan(300)
  const corbeille = listeDe(await lireJson(await page.request.get(`${API_DJANGO}/trash/corbeille/?page_size=200`), 'corbeille'))
  const entree = corbeille.find((e) => /a\.csv/.test(JSON.stringify(e)) && !e.restaure_le)
  expect(entree, 'entrée de corbeille du fichier retiré').toBeTruthy()
  const rest = await page.request.post(`${API_DJANGO}/trash/corbeille/${entree.id}/restaurer/`)
  expect(rest.status(), `Restaurer (${(await rest.text()).slice(0, 200)})`).toBeLessThan(300)
  expect((await retenu(page.request, cal2.id))?.nom, 'restauré : de nouveau retenu').toBe('a.csv')
  expect((await deposer(page.request, cal2.id, 'b.csv')).status()).toBe(201)
  expect((await retenu(page.request, cal2.id))?.nom, 'remplacement : le nouveau est retenu').toBe('b.csv')
  const ancien = await retenu(page.request, cal2.id)
  expect(ancien?.nom).toBe('b.csv')
})

// ── ACAL374 : la resynchronisation porte chaque ligne panneau au compte de SON modèle ────────
etape('PA2.9', ['ACAL374'], async () => {
  const sortie = rejouerSonde('C-ACAL-VER2-61')
  expect(sortie).toMatch(/"repro": false/)
  expect(sortie, 'la ligne 550 W reste à 8, la ligne 450 W passe à 5').toMatch(/"apres": \[\[\d+, 8\], \[\d+, 5\]\]/)
  expect(sortie).toMatch(/"sync": 200/)
})

// ── ACAL376 : le rapport d'étude nomme la vraie base d'irradiance ───────────────────────────
etape('PA2.10', ['ACAL376'], async () => {
  const sortie = rejouerSonde('C-ACAL-VER2-72')
  expect(sortie).toMatch(/'source': 'fichier'/)
  expect(sortie, 'PVGIS n’apparaît plus pour l’irradiance').toMatch(/"pvgis_dans_rapport": false/)
  expect(sortie, 'le fournisseur est nommé').toMatch(/"meteonorm_dans_rapport": true/)
})
