// Acceptation en direct — groupe ACON (conception / calepinage, run 99392c) : preuve due d'ACON85.
// (a) « Générer le devis » sur un calepinage simulé OMBRÉ range un bloc horaire AVEC `ombrage`, et le PDF `/proposal`
//     dit la même production que la page publique : la sonde commitée `C-ACON-020-L2.py` (section F, chemin
//     POST calepinage/calepinages/<id>/generer-devis/, envoi, PDF, page publique) est REJOUÉE sur l'arbre, dans le shell
//     Django du runner, transaction annulée (même programme que `scripts/sonde.py`, sans docker). Le BOUTON de l'écran
//     n'est pas jouable ici : « Générer le devis » enregistre d'abord la conception du constructeur 3D, qui ne démarre
//     pas sans clé de fond de carte (précédent acal.spec.js P6.3-devis) — la route qu'il appelle est la même.
// (b) Verrou : `simuler {forcer:true}` sur le calepinage d'un devis ACCEPTÉ ⇒ 409 nommé, aucun job ; le recalcul de
//     masse ne le soumet pas ; le calepinage d'un devis ENVOYÉ reste simulable (202). Données propres dans la société
//     de demo_admin, gestes par les vraies routes HTTP.
import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, API_DJANGO as API } from '../helpers.js'

const etape = groupe('ACON', ['ACON85'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const T = { timeout: 120_000 }
const J = JSON.stringify
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()

/** Rejoue une sonde commitée dans le shell Django (transaction ANNULÉE, Celery neutralisé) ; rend
 *  `{ret, stdout}`. `complet` : la sortie JSON imprimée par la sonde n'est pas tronquée à 14 000 car. */
function sondeEnLigne(groupeSonde, constat, { complet = false } = {}) {
  const src = readFileSync(join(RACINE, 'docs', 'audits', 'sondes', groupeSonde, `${constat}.py`), 'utf8')
  return py(`import io, contextlib
import json as _json
from django.conf import settings
from django.db import transaction
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver', 'localhost']
class _Entier(str):
    def __getitem__(self, k):
        return str(self) if isinstance(k, slice) else str.__getitem__(self, k)
_vrai_dumps = _json.dumps
def _dumps(*a, **k):
    return _Entier(_vrai_dumps(*a, **k))
def _noop(self, *a, **k):
    return type('R', (), {'id': 'noop'})()
ns = {'__name__': '__sonde__'}
exec(compile(${J(src)}, 'sonde', 'exec'), ns)
tampon = io.StringIO()
ret, err = None, None
with mock.patch('celery.app.task.Task.apply_async', new=_noop), mock.patch('celery.app.task.Task.delay', new=_noop), \\
        mock.patch.object(_json, 'dumps', new=_dumps if ${complet ? 'True' : 'False'} else _vrai_dumps):
    try:
        with transaction.atomic():
            try:
                with contextlib.redirect_stdout(tampon):
                    ret = ns['sonde']({'celery': [], 'racine': '.', 'args': None})
            finally:
                transaction.set_rollback(True)
    except BaseException:
        import traceback
        err = traceback.format_exc()[-2500:]
sortie({'ret': ret, 'stdout': str(tampon.getvalue())[-200000:], 'err': err})`)
}

etape('PA2.generer_devis_ombre_pdf_egal_page', ['ACON85'], async () => {
  const s = await sondeEnLigne('ACON', 'C-ACON-020-L2', { complet: true })
  expect(s.err, `sonde rejouée sans erreur : ${s.err}`).toBeNull()
  const ligne = s.stdout.split('\n').map((l) => l.trim()).filter((l) => l.startsWith('{')).pop()
  expect(ligne, `observation imprimée par la sonde (${s.stdout.slice(-400)})`).toBeTruthy()
  const obs = JSON.parse(ligne)
  expect(obs.F_generer_http, `generer-devis : 201 (${obs.F_generer_corps || ''})`).toBe(201)
  expect(obs.F_lien, 'le devis né est lié au calepinage').toBe(true)
  // Le bloc horaire RANGÉ du devis né porte l'ombrage du calepinage (perte non nulle).
  const ombrage = obs.F1_ne_bloc_ombrage
  expect(ombrage && typeof ombrage === 'object', `bloc rangé AVEC ombrage (${J(ombrage)})`).toBeTruthy()
  expect(Number(ombrage.perte_pct), 'perte d’ombrage rangée > 0').toBeGreaterThan(0)
  expect(Number(obs.F1_ne_perte), 'perte lue sur le devis = perte rangée').toBeCloseTo(Number(ombrage.perte_pct), 1)
  // PDF /proposal = bloc rangé = page publique (dimensionnement_options.sans), au kWh près.
  const prodRange = Number(obs.F1_ne_bloc_production_kwh)
  expect(obs.F2_pdf?.http, 'GET /proposal 200').toBe(200)
  const prodPdf = Number(obs.F2_pdf?.prod_kwh)
  const prodPage = Number(obs.F2_public_production_options?.sans)
  expect(obs.F2_public_http, 'page publique 200').toBe(200)
  expect(Math.abs(prodPdf - prodRange), `PDF ${prodPdf} = bloc rangé ${prodRange}`).toBeLessThan(1)
  expect(Math.abs(prodPdf - prodPage), `PDF ${prodPdf} = page ${prodPage}`).toBeLessThan(1)
})

etape('PA2.simuler_calepinage_fige_409', ['ACON85'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const x = await py(`a = U.objects.get(username='demo_admin'); co = a.company
from decimal import Decimal as D
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.calepinage.models import Calepinage
SIMULE = {'simulation': {'hash_entree': 'a' * 64, 'calcule_le': '2026-10-01T10:00:00Z'}}
cl = Client.objects.create(company=co, nom='ACC ACON85', prenom='${m}', email='acc-acon85-${m.toLowerCase()}@example.invalid')
lead = Lead.objects.create(company=co, nom='ACC ACON85 ${m}')
out = {}
for cle, statut in (('accepte', Devis.Statut.ACCEPTE), ('envoye', Devis.Statut.ENVOYE)):
    d = Devis.objects.create(company=co, reference='DEV-ACC-ACON85-%s-${m}' % cle.upper(), client=cl, lead=lead, taux_tva=D('20'))
    Devis.objects.filter(pk=d.pk).update(statut=statut)
    c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC ACON85 %s ${m}' % cle, resultat=SIMULE)
    Calepinage.objects.filter(pk=c.pk).update(devis=d)
    out[cle] = c.id
sortie(out)`)
  const jobs = () => py(`from core.models import BackgroundJob
sortie(BackgroundJob.objects.filter(company=U.objects.get(username='demo_admin').company).count())`)
  const avant = await jobs()
  const refus = await r.post(`${API}/calepinage/calepinages/${x.accepte}/simuler/`, { ...T, data: { forcer: true } })
  const corps = await refus.json().catch(() => ({}))
  expect(refus.status(), `simuler {forcer:true} sur un calepinage de devis accepté : 409 (${J(corps)})`).toBe(409)
  expect(J(corps.simulation), 'motif de ventes nommé sous `simulation`').toContain('Devis accepté : révisez-le')
  expect(await jobs(), 'aucun job créé par le refus').toBe(avant)
  // Le calepinage d'un devis ENVOYÉ reste corrigeable : le verrou ne le refuse pas (202 quand il est simulable ;
  // sans réglage météo de la société démo, le refus éventuel nomme un réglage de simulation, jamais le devis).
  const ok = await r.post(`${API}/calepinage/calepinages/${x.envoye}/simuler/`, { ...T, data: { forcer: true } })
  const corpsOk = await ok.text()
  expect([202, 409], `devis envoyé : simuler (${corpsOk.slice(0, 300)})`).toContain(ok.status())
  expect(corpsOk, 'devis envoyé : jamais le motif du verrou').not.toContain('Devis accepté')
  // Recalcul de masse : le calepinage figé n'est jamais soumis.
  const rec = await lireJson(await r.post(`${API}/calepinage/parametres/recalculer-simulations/`, { ...T, data: {} }), 'recalcul de masse')
  const soumis = (rec.jobs || []).map((j) => j.calepinage)
  expect(soumis, `recalcul : le calepinage du devis accepté n'est pas soumis (${J(rec).slice(0, 300)})`).not.toContain(x.accepte)
  expect(Number(rec.soumis), '`soumis` = nombre de jobs rendus').toBe(soumis.length)
  // Persistance : relire le calepinage figé ⇒ son résultat est intact (aucune simulation réécrite).
  const relu = await py(`from apps.calepinage.models import Calepinage
sortie((Calepinage.objects.get(pk=${x.accepte}).resultat or {}).get('simulation', {}).get('hash_entree'))`)
  expect(relu, 'résultat du calepinage figé inchangé').toBe('a'.repeat(64))
})
