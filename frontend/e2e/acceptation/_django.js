// Shell Django PERSISTANT des specs d'acceptation (démarrage ~1 min une seule fois, puis < 1 s par appel) :
// code en base64 par ligne, réponse `@@R<json>`. Même patron que `acrm.spec.js` ; s'arrête avec le worker.
import { spawn } from 'node:child_process'
import { test } from '@playwright/test'

const SERVEUR = [
  'import sys, json, base64, io, contextlib, traceback',
  'ns = {}',
  "print('@@PRET', flush=True)",
  'for ligne in sys.stdin:',
  '    ligne = ligne.strip()',
  '    if not ligne: continue',
  '    buf = io.StringIO()',
  '    try:',
  '        with contextlib.redirect_stdout(buf):',
  '            exec(base64.b64decode(ligne).decode(), ns)',
  "        sortie = {'ok': True, 'out': buf.getvalue()}",
  '    except BaseException:',
  "        sortie = {'ok': False, 'out': buf.getvalue(), 'err': traceback.format_exc()[-1800:]}",
  "    print('@@R' + json.dumps(sortie), flush=True)",
].join('\n')

let serveur = null
const attentes = []
let tampon = ''

function demarrer() {
  if (serveur) return serveur.pret
  const [cmd, ...args] = (process.env.E2E_DJANGO_EXEC || 'docker compose exec -T django_core').split(' ')
  const proc = spawn(cmd, [...args, 'python', 'manage.py', 'shell', '-c', SERVEUR], { stdio: ['pipe', 'pipe', 'ignore'] })
  let pretOk
  const pret = new Promise((r) => { pretOk = r })
  proc.stdout.on('data', (d) => {
    tampon += d.toString()
    let i
    while ((i = tampon.indexOf('\n')) >= 0) {
      const l = tampon.slice(0, i).trim()
      tampon = tampon.slice(i + 1)
      if (l === '@@PRET') pretOk()
      else if (l.startsWith('@@R')) attentes.shift()?.(JSON.parse(l.slice(3)))
    }
  })
  serveur = { proc, pret }
  return pret
}

const PRELUDE = `
import datetime, json
from unittest import mock
from django.contrib.auth import get_user_model
from django.utils import timezone
U = get_user_model()
def sortie(o): print('@@' + json.dumps(o, default=str))
def compte(nom, role=4, societe=1, mdp='Accept@2026!'):
    """Compte d'essai idempotent (role = pk du rôle de la société)."""
    u, _ = U.objects.get_or_create(username=nom, defaults=dict(company_id=societe, role_id=role))
    u.company_id = societe; u.role_id = role; u.is_active = True; u.email = nom + '@accept.test'
    u.must_change_password = False; u.failed_login_count = 0; u.locked_until = None; u.set_password(mdp); u.save()
    return u
def a_l_heure(iso, methode, url, data=None, username='demo_admin'):
    """Appel de la VRAIE route (client DRF) sous horloge gelée : seule voie pour jouer un samedi un mardi."""
    from rest_framework.test import APIClient
    from django.utils.dateparse import parse_datetime
    c = APIClient(); c.force_authenticate(U.objects.get(username=username))
    with mock.patch('django.utils.timezone.now', return_value=parse_datetime(iso)):
        r = getattr(c, methode)(url, data=data, format='json', HTTP_HOST='localhost')
    return r.status_code, (r.json() if r.get('Content-Type', '').startswith('application/json') else None)
`

/** Exécute `code` dans le shell (prélude : U, timezone, datetime, json, mock, compte, a_l_heure, sortie). */
export async function py(code) {
  await demarrer()
  const rep = await new Promise((resolve) => {
    attentes.push(resolve)
    serveur.proc.stdin.write(`${Buffer.from(`${PRELUDE}\n${code}`).toString('base64')}\n`)
  })
  if (!rep.ok) throw new Error(`shell Django : ${rep.err}`)
  const l = rep.out.split('\n').filter((x) => x.startsWith('@@')).pop()
  return l ? JSON.parse(l.slice(2)) : null
}

export const MDP_ESSAI = 'Accept@2026!'

/** À appeler une fois au niveau module : ferme le shell à la fin du fichier. */
export function fermerDjangoApresTout() {
  test.afterAll(() => { try { serveur?.proc.stdin.end() } catch { /* déjà fermé */ } serveur = null })
}
