// ADCG — second lot de preuves en direct (vague 6, runner GitHub) : ADCG2, ADCG3, ADCG4, ADCG19 (séquence de deploy
// rejouée au BANC de `scripts/tests/test_auto_deploy.py` : faux git/docker/flock/systemctl/curl, vrai `auto-deploy.sh`),
// ADCG15, ADCG16, ADCG21 (scripts de poste rejoués sur données de test, pwsh du runner) et ADCG55 (en-têtes du Worker
// `apps/web/worker/headers.mjs` : VRAIE fonction + enforcement par un VRAI Chromium dans une iframe tierce).
// Chaque étape rejoue la clause « fini quand / Given-When-Then » de la tâche et AFFIRME ses valeurs exactes.
// NON JOUÉES ici (voir rapport) : ADCG14 (docker compose ps/pause), ADCG22 (passe nocturne claude + docker).
// Les parties « prod / poste de Reda / journal du serveur » des clauses « Preuve en direct » ne sont pas jouables sur un
// runner ; elles ne sont pas revendiquées.
import { test, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, cpSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'

const etape = groupe('ADCG', ['ADCG2', 'ADCG3', 'ADCG4', 'ADCG15', 'ADCG16', 'ADCG19', 'ADCG21', 'ADCG55'])
test.describe.configure({ timeout: 300_000 })

/** Python (stdlib) lancé à la racine du dépôt : charge le banc du test de deploy et rend la dernière ligne JSON. */
function banc(corps) {
  const code = `import importlib.util, json, re, tempfile
from pathlib import Path
sp = importlib.util.spec_from_file_location('t_deploy', 'scripts/tests/test_auto_deploy.py')
t = importlib.util.module_from_spec(sp); sp.loader.exec_module(t)
A, B, C = t.A, t.B, t.C
${corps}
`
  const sortie = execFileSync('python', ['-c', code], { cwd: RACINE, encoding: 'utf8', timeout: 240_000 })
  const ligne = sortie.split('\n').map((l) => l.trim()).filter((l) => l.startsWith('{')).pop()
  if (!ligne) throw new Error(`banc sans sortie JSON : ${sortie.slice(-500)}`)
  return JSON.parse(ligne)
}

// ── ADCG2 — migrate (image + code neufs) AVANT tout `up -d` / redémarrage ──────────────────────────────────────
etape('PF3.deploy.ADCG2-migrate-avant-redemarrage', ['ADCG2'], async () => {
  const o = banc(`
lot = "backend/django_core/apps/crm/models.py\\nbackend/django_core/apps/crm/migrations/0999_x.py\\n"
with tempfile.TemporaryDirectory() as d:
    b = t.Banc(d, changes=lot)
    rc, sortie = b.jouer()
    cycle1 = dict(rc=rc,
        migrate=b.index(r"run --rm --no-deps django_core python manage\\.py migrate --noinput"),
        up=b.index(r"prod\\.yml up -d"), restart=b.index(r" restart django_core "),
        init_roles=b.index("init_roles"))
with tempfile.TemporaryDirectory() as d:
    b = t.Banc(d, changes=lot)
    rc, sortie = b.jouer(FAIL="manage.py migrate --noinput")
    i_reset = b.index("^git reset --hard " + A + "$")
    avant = b.appels[:i_reset] if i_reset is not None else b.appels
    cycle2 = dict(rc=rc, ups=len([a for a in avant if re.search(r"prod\\.yml up -d", a)]),
        restarts=len([a for a in avant if re.search(r" restart ", a)]), echec="ECHEC" in b.journal,
        last=b.lire("last_deployed_commit"))
print(json.dumps(dict(cycle1=cycle1, cycle2=cycle2)))
`)
  const c1 = o.cycle1
  expect(c1.rc, 'cycle 1 : deploy réussi').toBe(0)
  expect(c1.migrate, `cycle 1 : \`run --rm --no-deps django_core python manage.py migrate --noinput\` joué (${JSON.stringify(c1)})`).not.toBeNull()
  expect(c1.migrate, 'cycle 1 : migrate AVANT `up -d`').toBeLessThan(c1.up)
  expect(c1.migrate, 'cycle 1 : migrate AVANT `restart django_core`').toBeLessThan(c1.restart)
  expect(c1.init_roles, 'init_roles reste APRÈS `up -d`').toBeGreaterThan(c1.up)
  const c2 = o.cycle2
  expect(c2.rc, 'cycle 2 : migrate en échec ⇒ deploy en échec').not.toBe(0)
  expect(c2.ups, 'cycle 2 : 0 `up -d` avant le retour arrière').toBe(0)
  expect(c2.restarts, 'cycle 2 : 0 `restart` avant le retour arrière').toBe(0)
  expect(c2.echec, 'cycle 2 : journal ECHEC').toBe(true)
  expect(c2.last, 'cycle 2 : last_deployed_commit inchangé (A)').toBe('a'.repeat(40))
})

// ── ADCG3 — un deploy échoué n'est plus rejoué chaque minute sur le même commit ─────────────────────────────
etape('PF3.deploy.ADCG3-echec-pas-rejoue', ['ADCG3'], async () => {
  const o = banc(`
with tempfile.TemporaryDirectory() as d:
    b = t.Banc(d, changes="backend/django_core/apps/crm/views.py\\n")
    for _ in range(2):
        b.jouer(FAIL="manage.py migrate")
    r = dict(migrates_apres_2_cycles=b.compte("manage.py migrate --noinput"), commit_en_echec=b.lire("commit_en_echec"),
             lignes_echec=b.journal.count("ECHEC"))
    b.jouer(t._remote())
    r["etat_apres_manuel"] = b.lire("commit_en_echec")
    b.jouer(FAIL="manage.py migrate")
    r["migrates_apres_retentative_manuelle"] = b.compte("manage.py migrate --noinput")
    Path(b.d, "origin").write_text(C)
    rc, sortie = b.jouer()
    r.update(rc_C=rc, migrates_apres_C=b.compte("manage.py migrate --noinput"), etat_apres_C=b.lire("commit_en_echec"),
             last=b.lire("last_deployed_commit"))
print(json.dumps(r))
`)
  expect(o.migrates_apres_2_cycles, 'deux cycles sur B en échec : UN seul migrate').toBe(1)
  expect(o.commit_en_echec, '`commit_en_echec` = B').toBe('b'.repeat(40))
  expect(o.lignes_echec, 'UNE seule ligne ECHEC au journal').toBe(1)
  expect(o.etat_apres_manuel, 'le chemin manuel efface l\u2019état').toBeNull()
  expect(o.migrates_apres_retentative_manuelle, 'le manuel retente B (2e migrate)').toBe(2)
  expect(o.rc_C, 'nouveau commit C : deploy réussi').toBe(0)
  expect(o.migrates_apres_C, 'C est tenté (3e migrate)').toBe(3)
  expect(o.etat_apres_C, 'un succès efface l\u2019état d\u2019échec').toBeNull()
  expect(o.last, 'last_deployed_commit = C').toBe('c'.repeat(40))
})

// ── ADCG4 — contrôle de santé rouge quand il ne s'exécute pas ───────────────────────────────────────────────
etape('PF3.deploy.ADCG4-sante-rouge', ['ADCG4'], async () => {
  const o = banc(`
lot = "backend/django_core/apps/crm/views.py\\n"
cas = {"sonde_vide": {"HEALTH": ""}, "showmigrations_en_echec": {"FAIL": "showmigrations"}, "http_502": {"HTTP_CODE": "502"}}
res = {}
with tempfile.TemporaryDirectory() as d:
    for nom, env in cas.items():
        b = t.Banc(Path(d) / nom, changes=lot)
        rc, sortie = b.jouer(**env)
        res[nom] = dict(rc=rc, echec="ECHEC" in b.journal, last=b.lire("last_deployed_commit"))
        if nom == "http_502":
            res["curl_essais"] = b.compte(r"^curl .*--resolve api\\.taqinor\\.ma:443:127\\.0\\.0\\.1 https://api\\.taqinor\\.ma/api/django/core/health/ready/")
    b = t.Banc(Path(d) / "vert", changes=lot)
    rc, sortie = b.jouer(HEALTH="degraded")
    res["vert"] = dict(rc=rc, last=b.lire("last_deployed_commit"))
print(json.dumps(res))
`)
  for (const nom of ['sonde_vide', 'showmigrations_en_echec', 'http_502']) {
    expect(o[nom].rc, `${nom} : le deploy sort en ECHEC`).not.toBe(0)
    expect(o[nom].echec, `${nom} : ligne ECHEC au journal`).toBe(true)
    expect(o[nom].last, `${nom} : last_deployed_commit inchangé (A)`).toBe('a'.repeat(40))
  }
  expect(o.curl_essais, 'health/ready à travers Caddy : 5 essais avant l\u2019échec').toBe(5)
  expect(o.vert.rc, 'sonde `degraded` + 0 migration en attente + 200 : OK').toBe(0)
  expect(o.vert.last, 'deploy OK ⇒ last_deployed_commit = B').toBe('b'.repeat(40))
})

// ── ADCG19 — DEPLOYED_SHA posé au deploy ────────────────────────────────────────────────────────────────────
etape('PF3.deploy.ADCG19-deployed-sha', ['ADCG19'], async () => {
  const o = banc(`
with tempfile.TemporaryDirectory() as d:
    b = t.Banc(d, changes="backend/django_core/apps/crm/views.py\\n")
    rc, sortie = b.jouer()
    i_up = b.index(r"prod\\.yml up -d --remove-orphans$")
    env_apres_up = b.appels[i_up + 1] if i_up is not None else None
    compose = (t.ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    services = {}
    for s in ("django_core", "celery_worker", "celery_worker_interactive", "celery_beat"):
        m = re.search(r"(?ms)^  " + s + r":\\n(.*?)(?=^  \\S)", compose)
        services[s] = bool(m and "DEPLOYED_SHA: \${DEPLOYED_SHA:-}" in m.group(1))
with tempfile.TemporaryDirectory() as d:
    b2 = t.Banc(d, changes="docs/CODEMAP.md\\n")
    b2.jouer()
    docs = b2.index("DEPLOYED_SHA")
print(json.dumps(dict(rc=rc, env_apres_up=env_apres_up, services=services, docs_seul=docs)))
`)
  expect(o.rc, 'deploy de code réussi').toBe(0)
  expect(o.env_apres_up, '`up -d` reçoit DEPLOYED_SHA = B (40 caractères)').toBe(`env DEPLOYED_SHA=${'b'.repeat(40)}`)
  for (const [service, ok] of Object.entries(o.services)) expect(ok, `docker-compose.prod.yml : DEPLOYED_SHA pour ${service}`).toBe(true)
  expect(o.docs_seul, 'un deploy docs seul ne touche pas DEPLOYED_SHA').toBeNull()
})

// ── ADCG16 — contrôle « dernier passage » de la QA nocturne ─────────────────────────────────────────────────
etape('PF3.nightly.ADCG16-dernier-passage', ['ADCG16'], async () => {
  const dossier = mkdtempSync(join(tmpdir(), 'adcg16-'))
  const p = (n) => String(n).padStart(2, '0')
  const horo = (heuresAvant) => {
    const d = new Date(Date.now() - heuresAvant * 3600_000)
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  }
  const jouer = (journal) => {
    try {
      return { code: 0, sortie: execFileSync('python', ['scripts/nightly_qa_dernier_passage.py', '--journal', journal],
        { cwd: RACINE, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } }) }
    } catch (e) { return { code: e.status, sortie: String(e.stdout || '') } }
  }
  // Cas 1 : « fin code 0 » vieille de 40 h puis un « ECHEC lancement » d'hier.
  const j1 = join(dossier, 'cas1.log')
  writeFileSync(j1, `${horo(40)}  fin code 0\n${horo(10)}  ECHEC lancement : scripts\\nightly-qa.ps1 absent de X (git status : propre)\n`, 'utf8')
  const c1 = jouer(j1)
  expect(c1.code, 'cas 1 : code 1 (au-delà de 36 h)').toBe(1)
  expect(c1.sortie).toMatch(/dernier passage réussi : \d{4}-\d\d-\d\d \d\d:\d\d \(il y a 40 h\)/)
  expect(c1.sortie).toMatch(/dernière tentative : \d{4}-\d\d-\d\d \d\d:\d\d ECHEC lancement/)
  // Cas 2 : un « fin code 0 » de cette nuit.
  const j2 = join(dossier, 'cas2.log')
  writeFileSync(j2, `${horo(30)}  fin code 1\n${horo(8)}  lancement skill qa-explorer\n${horo(6)}  fin code 0\n`, 'utf8')
  const c2 = jouer(j2)
  expect(c2.code, 'cas 2 : code 0 (passage de cette nuit)').toBe(0)
  expect(c2.sortie).toMatch(/dernier passage réussi : .*\(il y a 6 h\)/)
  // Cas 3 : aucun fichier, puis un journal sans aucune « fin code 0 ».
  const c3 = jouer(join(dossier, 'absent.log'))
  expect(c3.code, 'cas 3 : code 1 (aucun fichier)').toBe(1)
  expect(c3.sortie).toContain('aucun passage consigné')
  const j4 = join(dossier, 'cas4.log')
  writeFileSync(j4, `${horo(2)}  fin code 1\n`, 'utf8')
  const c4 = jouer(j4)
  expect(c4.code, 'journal sans « fin code 0 » : code 1').toBe(1)
  expect(c4.sortie).toContain('aucun passage consigné')
})

// ── ADCG15 — lanceur de la QA nocturne installé hors du dépôt (pwsh du runner) ──────────────────────────────
function pwsh(args, env) {
  try {
    return { code: 0, sortie: execFileSync('pwsh', ['-NoProfile', '-NonInteractive', ...args], { cwd: RACINE, encoding: 'utf8', env: { ...process.env, ...env }, timeout: 120_000 }) }
  } catch (e) { return { code: e.status, sortie: `${e.stdout || ''}${e.stderr || ''}`, erreur: e.code } }
}
etape('PF3.nightly.ADCG15-lanceur-trace', ['ADCG15'], async () => {
  const tmp = mkdtempSync(join(tmpdir(), 'adcg15-'))
  const appdata = join(tmp, 'appdata')
  const lanceur = join(RACINE, 'scripts', 'nightly-qa-lanceur.ps1')
  const journal = join(appdata, 'taqinor', 'nightly-qa.log')
  const lire = () => readFileSync(journal, 'utf8').replace(/^\uFEFF/, '').split('\n').filter(Boolean)
  // Cas 1 : faux dépôt SANS scripts/nightly-qa.ps1.
  const depot1 = join(tmp, 'depot1'); mkdirSync(join(depot1, 'scripts'), { recursive: true })
  const r1 = pwsh(['-File', lanceur, '-Depot', depot1], { LOCALAPPDATA: appdata })
  expect(r1.erreur, `pwsh disponible (${r1.sortie.slice(0, 200)})`).not.toBe('ENOENT')
  expect(r1.code, 'cas 1 : code de sortie 3').toBe(3)
  const l1 = lire()
  expect(l1, `cas 1 : deux lignes (${JSON.stringify(l1)})`).toHaveLength(2)
  expect(l1[0]).toContain('lancement')
  expect(l1[1]).toContain('ECHEC lancement : scripts\\nightly-qa.ps1 absent')
  expect(l1[1]).toContain('(git status : ')
  expect(l1[1]).toMatch(/^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d {2}/)
  // Cas 2 : faux dépôt dont le script fait `exit 0`.
  const tmp2 = mkdtempSync(join(tmpdir(), 'adcg15b-'))
  const appdata2 = join(tmp2, 'appdata')
  const depot2 = join(tmp2, 'depot'); mkdirSync(join(depot2, 'scripts'), { recursive: true })
  writeFileSync(join(depot2, 'scripts', 'nightly-qa.ps1'), 'param([string]$Skill)\nexit 0\n', 'ascii')
  const r2 = pwsh(['-File', lanceur, '-Depot', depot2], { LOCALAPPDATA: appdata2 })
  expect(r2.code, 'cas 2 : code 0').toBe(0)
  const j2 = readFileSync(join(appdata2, 'taqinor', 'nightly-qa.log'), 'utf8').replace(/^\uFEFF/, '').split('\n').filter(Boolean)
  expect(j2[0]).toContain('lancement')
  expect(j2[j2.length - 1].endsWith('fin code 0'), `cas 2 : dernière ligne « fin code 0 » (${JSON.stringify(j2)})`).toBe(true)
  // Persistance : relancer ⇒ les lignes horodatées sont conservées (4 lignes).
  pwsh(['-File', lanceur, '-Depot', depot2], { LOCALAPPDATA: appdata2 })
  const j3 = readFileSync(join(appdata2, 'taqinor', 'nightly-qa.log'), 'utf8').replace(/^\uFEFF/, '').split('\n').filter(Boolean)
  expect(j3, 'journal conservé entre deux lancements').toHaveLength(4)
})

// ── ADCG21 — gc-workspace liste les branches fusionnées `worktree-agent-*` ──────────────────────────────────
etape('PF3.nightly.ADCG21-gc-worktree-agent', ['ADCG21'], async () => {
  const depot = mkdtempSync(join(tmpdir(), 'adcg21-'))
  const git = (...a) => execFileSync('git', ['-c', 'user.email=a@b.c', '-c', 'user.name=acc', ...a], { cwd: depot, encoding: 'utf8' })
  git('init', '-q', '-b', 'main')
  writeFileSync(join(depot, 'a.txt'), 'a\n')
  git('add', 'a.txt'); git('commit', '-q', '-m', 'a')
  git('branch', 'worktree-agent-x')                       // fusionnée dans main
  git('checkout', '-q', '-b', 'worktree-agent-y')         // non fusionnée
  writeFileSync(join(depot, 'b.txt'), 'b\n')
  git('add', 'b.txt'); git('commit', '-q', '-m', 'b')
  git('checkout', '-q', 'main')
  mkdirSync(join(depot, 'scripts'))
  cpSync(join(RACINE, 'scripts', 'gc-workspace.ps1'), join(depot, 'scripts', 'gc-workspace.ps1'))
  const avant = git('branch', '--format=%(refname:short)').split('\n').filter(Boolean).sort()
  const r = pwsh(['-File', join(depot, 'scripts', 'gc-workspace.ps1'), '-WhatIf'], {})
  expect(r.erreur, 'pwsh disponible').not.toBe('ENOENT')
  expect(r.code, `gc-workspace -WhatIf : code 0 (${r.sortie.slice(-300)})`).toBe(0)
  expect(r.sortie, '« delete merged branch worktree-agent-x »').toContain('delete merged branch worktree-agent-x')
  expect(r.sortie, 'worktree-agent-y (non fusionnée) n\u2019est PAS à supprimer').not.toContain('delete merged branch worktree-agent-y')
  const garde = r.sortie.slice(r.sortie.indexOf('KEEP (non fusionn'))
  expect(r.sortie.includes('KEEP (non fusionn'), 'section « KEEP (non fusionnées) »').toBe(true)
  expect(garde, 'worktree-agent-y listée dans KEEP (non fusionnées)').toContain('- worktree-agent-y')
  const apres = git('branch', '--format=%(refname:short)').split('\n').filter(Boolean).sort()
  expect(apres, '`git branch` inchangé en -WhatIf').toEqual(avant)
  expect(apres).toEqual(['main', 'worktree-agent-x', 'worktree-agent-y'])
})

// ── ADCG55 — `/embed/estimation` affichable dans une iframe tierce, le reste du site fermé ────────────────────
const HTML_SITE = 'https://taqinor-test.invalid'
async function reponsesWorker() {
  const mod = await import(pathToFileURL(join(RACINE, 'apps', 'web', 'worker', 'headers.mjs')).href)
  const rendre = (chemin) => mod.applySecurityHeaders(
    new Request(`${HTML_SITE}${chemin}`, { method: 'GET' }),
    new Response('<!doctype html><title>t</title>', { status: 200, headers: { 'content-type': 'text/html; charset=utf-8' } }))
  return { mod, rendre }
}
etape('PF3.web.ADCG55-embed-iframe', ['ADCG55'], async ({ page, context }) => {
  const { rendre } = await reponsesWorker()
  // (1) La VRAIE fonction du Worker, sur les quatre chemins de la clause.
  const embed = rendre('/embed/estimation')
  const csp = embed.headers.get('content-security-policy') || ''
  expect(csp, 'embed : `frame-ancestors https:`').toContain('frame-ancestors https:')
  expect(csp, 'embed : plus de `frame-ancestors \'none\'`').not.toContain("frame-ancestors 'none'")
  expect(embed.headers.get('x-frame-options'), 'embed : aucun X-Frame-Options').toBeNull()
  const fermees = {}
  for (const chemin of ['/', '/devis/mon-toit', '/embedded']) {
    const r = rendre(chemin)
    fermees[chemin] = r
    expect(r.headers.get('content-security-policy'), `${chemin} : frame-ancestors 'none' gardé`).toContain("frame-ancestors 'none'")
    expect(r.headers.get('x-frame-options'), `${chemin} : X-Frame-Options DENY gardé`).toBe('DENY')
  }
  const sansFrame = (c) => c.split('; ').filter((d) => !d.startsWith('frame-ancestors ')).join('; ')
  expect(sansFrame(csp), 'les autres directives sont identiques à celles du reste du site')
    .toBe(sansFrame(fermees['/'].headers.get('content-security-policy')))
  // (2) Un VRAI navigateur : une page partenaire HTTPS embarque l'iframe, servie avec EXACTEMENT ces en-têtes.
  const servir = async (route, chemin, corps) => {
    const r = rendre(chemin)
    const headers = Object.fromEntries(r.headers.entries())
    await route.fulfill({ status: 200, headers, body: corps })
  }
  await context.route(`${HTML_SITE}/embed/estimation`, (route) => servir(route, '/embed/estimation',
    '<!doctype html><title>Widget</title><h1 id="widget">Widget estimation partenaire</h1>'))
  await context.route(`${HTML_SITE}/devis/mon-toit`, (route) => servir(route, '/devis/mon-toit',
    '<!doctype html><title>Devis</title><h1 id="devis">Devis mon toit</h1>'))
  await context.route('https://partenaire.invalid/', (route) => route.fulfill({
    status: 200, headers: { 'content-type': 'text/html; charset=utf-8' },
    body: `<!doctype html><title>Partenaire</title><h1>Site partenaire</h1>
<iframe id="embed" title="embed" src="${HTML_SITE}/embed/estimation" width="500" height="300"></iframe>`,
  }))
  await page.goto('https://partenaire.invalid/')
  const cadre = page.frameLocator('#embed')
  await expect(cadre.locator('#widget'), 'le widget /embed/estimation s\u2019affiche dans l\u2019iframe tierce').toHaveText('Widget estimation partenaire')
  // Témoin : une AUTRE page du site, dans la même iframe tierce, reste bloquée (page non surveillée : l'erreur console
  // « Refused to display… » y est ATTENDUE).
  const temoin = await context.newPage()
  const refus = []
  temoin.on('console', (m) => refus.push(m.text()))
  await context.route('https://partenaire-2.invalid/', (route) => route.fulfill({
    status: 200, headers: { 'content-type': 'text/html; charset=utf-8' },
    body: `<!doctype html><title>P2</title><iframe id="autre" title="autre" src="${HTML_SITE}/devis/mon-toit" width="500" height="300"></iframe>`,
  }))
  await temoin.goto('https://partenaire-2.invalid/')
  await temoin.waitForTimeout(2500)
  const frameAutre = temoin.frames().find((f) => f.url().includes('/devis/mon-toit') || f.url().startsWith('chrome-error'))
  const contenuAutre = frameAutre ? await frameAutre.locator('#devis').count().catch(() => 0) : 0
  expect(contenuAutre, `/devis/mon-toit reste interdit d\u2019iframe (console : ${refus.join(' | ').slice(0, 300)})`).toBe(0)
  console.log(`[ADCG55] témoin /devis/mon-toit : frame=${frameAutre ? frameAutre.url() : 'aucune'} ; console=${refus.join(' | ').slice(0, 300)}`)
  await temoin.close()
  // Console de la page partenaire (surveillée par les oracles) : aucune erreur `frame-ancestors` côté widget.
})
