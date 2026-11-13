// AANA81 (preuve en direct, 13/11) — l'agent SQL réel (fournisseur LLM réel, clé du .env local) répond à
// « Quel est le montant du devis <REF> ? » sur un devis à DEUX options accepté « sans » : aucune requête ne somme
// `quantite * prix_unitaire` des lignes (motif de `tests/eval/runner.py::_SOMME_LIGNES`) et la réponse ne donne
// pas la somme des lignes comme montant. Appel EN PROCESSUS dans le conteneur fastapi_ia (même chemin que
// POST /sql-agent/query : ActionContext + resolve_caller_permissions + sql_agent_service.query), le SQL proposé
// par le LLM étant relu à `_validate_and_secure` et à `on_tool_start` (ERR84 : il n'est jamais renvoyé au client).
// 0 écran (clause : « Appelants … 0 écran »). Un seul appel à l'agent par rejeu (plusieurs tours LLM au plus).
import { spawnSync } from 'node:child_process'
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { ADMIN } from '../helpers.js'

const etape = groupe('AANA', ['AANA81'])
const FASTAPI = 'erp-agentique-fastapi_ia-1'
const DJANGO = 'erp-agentique-django_core-1'
test.describe.configure({ timeout: 600_000 })

// Programme joué dans le conteneur de l'agent (ses dépendances et ses clés n'existent que là).
export const PROGRAMME = String.raw`import asyncio, json, os, re
import httpx, jwt
from app.services import sql_agent_service as s
from app.services.action_tools import ActionContext, resolve_caller_permissions
from app.core.config import DJANGO_INTERNAL_URL, internal_headers
REF = os.environ['DEVIS_REF']
r = httpx.post(DJANGO_INTERNAL_URL.rstrip('/') + '/api/django/token/', headers=internal_headers(), json={'username': os.environ['DEMO_USER'], 'password': os.environ['DEMO_PW']}, timeout=180)
tok = r.cookies.get('access_token') or (r.json() or {}).get('access')
assert tok, f'login {r.status_code}'
p = jwt.decode(tok, os.environ['DJANGO_SECRET_KEY'], algorithms=['HS256'])
uid, co = int(p['user_id']), int(p['company_id'])
ctx = ActionContext(company_id=co, role=p.get('role', ''), permissions=[], token=tok, is_superuser=bool(p.get('is_superuser', False)))
resolve_caller_permissions(ctx)
s.sql_agent_service.clear_history(uid)
sqls, outils, llm = [], [], [0]
_v = s._validate_and_secure
def _spy(sql, *a, **k):
    sqls.append(sql)
    return _v(sql, *a, **k)
s._validate_and_secure = _spy
_e = s._SQLCapture.on_llm_end
def _n(self, *a, **k):
    llm[0] += 1
    return _e(self, *a, **k)
s._SQLCapture.on_llm_end = _n
_t = s._SQLCapture.on_tool_start
def _o(self, serialized, input_str, *a, **k):
    outils.append({'outil': (serialized or {}).get('name'), 'entree': str(input_str)[:2000]})
    return _t(self, serialized, input_str, *a, **k)
s._SQLCapture.on_tool_start = _o
q = f'Quel est le montant du devis {REF} ?'
out = asyncio.run(s.sql_agent_service.query(question=q, user_id=uid, company_id=co, action_ctx=ctx))
somme = re.compile(r"SUM\s*\([^)]*quantite\s*\*\s*(?:\w+\.)?prix_unitaire", re.I)
print('RESULTAT ' + json.dumps({'question': q, 'answer': out.get('answer'), 'sqls': sqls, 'outils': outils,
    'somme_lignes': [x for x in sqls + [o['entree'] for o in outils] if somme.search(x)],
    'modele': out.get('modele'), 'repli': out.get('repli'), 'erreur': out.get('erreur'), 'intention': out.get('intention'),
    'tokens': out.get('tokens'), 'appels_llm': llm[0], 'evenement_id': out.get('evenement_id'),
    'permissions_n': len(ctx.permissions or [])}, ensure_ascii=False, default=str))
`

// Le devis de référence : deux options (lignes « sans » ET « avec »), accepté, société de demo_admin ;
// somme des lignes et total_ht (domain.argent, option effective) lus par Django.
const LECTURE = String.raw`import json
from django.contrib.auth import get_user_model
from django.db.models import F, Sum
from apps.ventes.models import Devis, LigneDevis
co = get_user_model().objects.get(username='demo_admin').company_id
for d in Devis.objects.filter(company_id=co, statut='accepte').order_by('-id'):
    v = set(LigneDevis.objects.filter(devis=d).values_list('variante', flat=True))
    if {'sans', 'avec'} <= v:
        s = LigneDevis.objects.filter(devis=d).aggregate(s=Sum(F('quantite') * F('prix_unitaire')))['s']
        print('DEVIS ' + json.dumps({'ref': d.reference, 'option': d.option_acceptee, 'somme_lignes': str(s), 'total_ht': str(d.total_ht), 'total_ttc': str(d.total_ttc)}))
        break
`

/** « 46000.0000 » → motif tolérant aux séparateurs de milliers et décimales (46 000 / 46,000 / 46 000,00). */
export function motifMontant(valeur) {
  const entier = String(Math.round(Number(valeur)))
  const groupes = entier.replace(/\B(?=(\d{3})+(?!\d))/g, ' ').split(' ')
  return new RegExp(`(^|[^\\d])${groupes.join('[\\s\\u00a0\\u202f.,]?')}([.,]0+)?([^\\d]|$)`)
}

etape('P.montant_devis_sans_somme_des_lignes', ['AANA81'], async () => {
  const lu = spawnSync('docker', ['exec', '-i', DJANGO, 'python', 'manage.py', 'shell'], { input: LECTURE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligneDevis = (lu.stdout || '').split('\n').find((l) => l.startsWith('DEVIS '))
  expect(ligneDevis, `devis deux options accepté introuvable ${lu.stderr?.slice(-300)}`).toBeTruthy()
  const devis = JSON.parse(ligneDevis.slice(6))
  expect(Number(devis.somme_lignes), 'la somme des lignes diffère du total du devis (sinon la preuve ne discrimine rien)').not.toBe(Number(devis.total_ht))

  const r = spawnSync('docker', ['exec', '-i', '-e', `DEVIS_REF=${devis.ref}`, '-e', `DEMO_USER=${ADMIN.username}`, '-e', `DEMO_PW=${ADMIN.password}`,
    FASTAPI, 'python', '-'], { input: PROGRAMME, encoding: 'utf8', maxBuffer: 20_000_000, timeout: 540_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('RESULTAT '))
  expect(ligne, `agent sans résultat ${r.stderr?.slice(-600)}`).toBeTruthy()
  const res = JSON.parse(ligne.slice(9))
  console.log(`[AANA81] devis ${JSON.stringify(devis)} ; agent ${JSON.stringify(res)}`)
  // Le fournisseur a vraiment répondu (pas un repli d'erreur générique, pas un 401/429).
  expect(res.erreur, `erreur fournisseur/agent : ${JSON.stringify(res.erreur)}`).toBeFalsy()
  expect(res.appels_llm, 'au moins un tour LLM réel').toBeGreaterThan(0)
  // Clause : aucune somme des lignes, ni dans le SQL proposé, ni comme montant rendu.
  expect(res.somme_lignes, 'SQL qui somme quantite * prix_unitaire').toEqual([])
  expect(res.answer, `réponse = somme des lignes ${devis.somme_lignes}`).not.toMatch(motifMontant(devis.somme_lignes))
})
