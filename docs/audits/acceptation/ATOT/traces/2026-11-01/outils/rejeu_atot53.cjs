// ATOT53 — rejeu en direct des écarts de la contre-visite ATOT du 01/11/2026.
// Usage : node rejeu_atot53.cjs <head|old> <baseURL> <outDir> [frontURL]
//  head : connexion UI demo_admin sur le front (vite), API via page.request (cookies),
//         oracles observés sur chaque page ouverte + chaque appel API (statut attendu déclaré).
//  old  : API seule (contre-épreuve) sur Django direct, jeton Bearer.
// Données : créées par l'API sous la société démo, préfixe « ATOT53 <run> » ; aucune
// donnée existante n'est modifiée ni supprimée (factures émises : PROTECT, gardées).
const { chromium, request: pwRequest } = require('playwright')
const fs = require('fs')
const path = require('path')

const [mode, BASE, OUT, FRONT] = process.argv.slice(2)
const RUN = `${mode}-${Date.now().toString(36)}`
const API = '/api/django'
fs.mkdirSync(OUT, { recursive: true })
const journal = []
const log = (...a) => { const s = a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' '); journal.push(s); console.log(s) }
const today = new Date().toISOString().slice(0, 10)

let page = null
let ctx = null
let req = null
const incidents = { '1': [], '2': [], '3': [], '4': [], '8': [] }

function surveiller(p) {
  p.on('console', (m) => { if (m.type() === 'error') incidents['3'].push(`console.error ${m.text().slice(0, 200)}`) })
  p.on('pageerror', (e) => incidents['3'].push(`pageerror ${String(e).slice(0, 200)}`))
  p.on('dialog', async (d) => { incidents['4'].push(`dialog ${d.type()} ${d.message().slice(0, 120)}`); await d.dismiss().catch(() => {}) })
  p.on('response', (r) => {
    const u = r.url()
    if (!u.startsWith(FRONT || BASE)) return
    if (r.status() >= 500) incidents['1'].push(`${r.status()} ${u}`)
    else if (r.status() >= 400) incidents['2'].push(`${r.status()} ${u}`)
  })
}

async function call(method, p, data, attendu) {
  const opts = { timeout: 120000 }
  if (data !== undefined) opts.data = data
  const r = await req[method.toLowerCase()](`${API}${p}`, opts)
  const st = r.status()
  let body = null
  const ct = r.headers()['content-type'] || ''
  const buf = await r.body()
  if (ct.includes('json')) { try { body = JSON.parse(buf.toString('utf8')) } catch { body = buf.toString('utf8') } } else body = buf
  const okAttendu = attendu === undefined ? st < 400 : (Array.isArray(attendu) ? attendu.includes(st) : st === attendu)
  if (!okAttendu && st >= 500) incidents['1'].push(`API ${method} ${p} -> ${st}`)
  else if (!okAttendu && st >= 400) incidents['2'].push(`API ${method} ${p} -> ${st} ${typeof body === 'object' && !Buffer.isBuffer(body) ? JSON.stringify(body).slice(0, 200) : ''}`)
  log(`${method} ${p} ${data !== undefined ? JSON.stringify(data).slice(0, 160) : ''} -> ${st}${Buffer.isBuffer(body) ? ` [${body.length} o, ${ct}]` : ` ${JSON.stringify(body).slice(0, 260)}`}`)
  return { st, body, ct }
}
const must = async (method, p, data, attendu) => {
  const r = await call(method, p, data, attendu)
  const ok = attendu === undefined ? r.st < 400 : (Array.isArray(attendu) ? attendu.includes(r.st) : r.st === attendu)
  if (!ok) throw new Error(`${method} ${p} -> ${r.st} ${JSON.stringify(r.body).slice(0, 400)}`)
  return r.body
}

const etapes = {}
function verif(etape, nom, ok, detail) {
  etapes[etape] = etapes[etape] || []
  etapes[etape].push({ nom, ok: !!ok, detail })
  log(`  [${ok ? 'OK' : 'KO'}] ${etape} ${nom} ${detail !== undefined ? JSON.stringify(detail).slice(0, 300) : ''}`)
}
async function capture(nom, url) {
  if (!page) return null
  const f = path.join(OUT, `ACCEPTATION-ATOT-${nom}.jpg`)
  if (url) {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 })
    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {})
  }
  const casse = await page.getByText('Une erreur est survenue').count().catch(() => 0)
  if (casse) incidents['8'].push(`écran cassé ${url}`)
  const texte = await page.locator('body').innerText().catch(() => '')
  await page.screenshot({ path: f, type: 'jpeg', quality: 60, fullPage: false })
  return { f, texte }
}

const num = (v) => Number(v)
const eq2 = (a, b) => Math.abs(num(a) - num(b)) < 0.005

async function client(nom) {
  return must('POST', '/crm/clients/', { nom: `ATOT53 ${nom}`, prenom: RUN, email: `atot53-${nom.toLowerCase()}-${RUN}@example.invalid` })
}
async function produit(nom, pu) {
  return must('POST', '/stock/produits/', { nom: `ATOT53 ${nom} ${RUN}`, prix_vente: pu, quantite_stock: 1000 })
}
async function factureLibre(cl, lignes, emettre) {
  const f = await must('POST', '/ventes/factures/', { client: cl.id, taux_tva: '20.00' })
  for (const l of lignes) {
    await must('POST', '/ventes/factures-lignes/', { facture: f.id, produit: l.produit, designation: l.designation, quantite: l.q || '1', prix_unitaire: l.pu, taux_tva: l.tva || '20.00' })
  }
  if (emettre) await must('POST', `/ventes/factures/${f.id}/emettre/`, {})
  return must('GET', `/ventes/factures/${f.id}/`)
}
async function devisAccepte(cl, pr, envoyer = true, accepter = true) {
  const d = await must('POST', '/ventes/devis/atomic/', {
    client: cl.id, taux_tva: '20.00', remise_globale: '0',
    lignes: [{ produit: pr.id, designation: 'Kit ATOT53', quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
  })
  if (envoyer) await must('POST', `/ventes/devis/${d.id}/share-link/`, { envoi: true })
  if (envoyer && accepter) await must('POST', `/ventes/devis/${d.id}/accepter/`, { nom: 'Client ATOT53' })
  return must('GET', `/ventes/devis/${d.id}/`)
}

// ── (1) PATCH latéraux — ATOT40, ATOT41, ATOT48 ──────────────────────────────
async function etape1() {
  const A = await client('A'); const B = await client('B')
  const p = await produit('Panneau', '1000')
  const emise = await factureLibre(A, [{ produit: p.id, designation: 'Panneau', pu: '1000' }], true)
  verif('P1.1', 'facture émise 1 200 TTC', emise.statut !== 'brouillon' && eq2(emise.total_ttc, 1200), { statut: emise.statut, ttc: emise.total_ttc, ref: emise.reference })
  const br = await factureLibre(A, [{ produit: p.id, designation: 'Ajout', pu: '500' }], false)
  const br2 = await factureLibre(A, [{ produit: p.id, designation: 'Autre', pu: '300' }], false)
  const li = br.lignes[0].id
  // ATOT40
  const r1 = await call('PATCH', `/ventes/factures-lignes/${li}/`, { facture: emise.id }, 409)
  verif('P1.1', 'ligne brouillon -> facture émise : 409', r1.st === 409, { st: r1.st, body: r1.body })
  const r2 = await call('PATCH', `/ventes/factures-lignes/${li}/`, { facture: br2.id }, 409)
  verif('P1.1', 'ligne brouillon -> autre brouillon : 409', r2.st === 409, { st: r2.st, body: r2.body })
  const r3 = await call('PATCH', `/ventes/factures-lignes/${li}/`, { facture: br.id, quantite: '2' }, 200)
  verif('P1.1', 'PATCH {facture: sa facture, quantite: 2} : 200', r3.st === 200, { st: r3.st })
  const e2 = await must('GET', `/ventes/factures/${emise.id}/`)
  const b2 = await must('GET', `/ventes/factures/${br.id}/`)
  verif('P1.1', 'persistance : émise 1 ligne 1 200,00 TTC ; brouillon garde sa ligne', e2.lignes.length === 1 && eq2(e2.total_ttc, 1200) && b2.lignes.length === 1 && b2.lignes[0].id === li, { emise: [e2.lignes.length, e2.total_ttc], brouillon: [b2.lignes.length, b2.total_ttc] })
  // ATOT41
  for (const [champ, val] of [['client', B.id], ['retenue_garantie_mad', '500'], ['devise', 'EUR']]) {
    const r = await call('PATCH', `/ventes/factures/${emise.id}/`, { [champ]: val }, 409)
    const refuses = (r.body && r.body.champs_refuses) || []
    verif('P1.2', `PATCH {${champ}} sur émise : 409 champs_refuses ∋ ${champ}`, r.st === 409 && refuses.includes(champ), { st: r.st, body: r.body })
  }
  const rIn = await call('PATCH', `/ventes/factures/${emise.id}/`, { client: A.id, devise: e2.devise }, 200)
  verif('P1.2', 'PATCH à valeurs inchangées (client A, devise) : 200', rIn.st === 200, { st: rIn.st })
  const rNote = await call('PATCH', `/ventes/factures/${emise.id}/`, { notes: `note ATOT53 ${RUN}` }, 200)
  verif('P1.2', 'PATCH {notes} : 200', rNote.st === 200, { st: rNote.st })
  const e3 = await must('GET', `/ventes/factures/${emise.id}/`)
  verif('P1.2', 'persistance : client A, retenue 0, devise et TTC 1 200 inchangés', e3.client === A.id && eq2(e3.retenue_garantie_mad || 0, 0) && e3.devise === e2.devise && eq2(e3.total_ttc, 1200), { client: e3.client, retenue: e3.retenue_garantie_mad, devise: e3.devise, ttc: e3.total_ttc })
  const rBr = await call('PATCH', `/ventes/factures/${br.id}/`, { client: B.id }, 200)
  verif('P1.2', 'brouillon : PATCH {client: B} 200', rBr.st === 200, { st: rBr.st })
  // ATOT48
  const D1 = await devisAccepte(A, p)
  const D2 = await devisAccepte(A, p, false, false)
  const bc0 = await must('POST', `/ventes/devis/${D1.id}/convertir-bc/`, {})
  const bcId = bc0.id || (bc0.bon_commande && bc0.bon_commande.id) || bc0.bc_id
  await must('POST', `/ventes/bons-commande/${bcId}/confirmer/`, {})
  const liv = await call('POST', `/ventes/bons-commande/${bcId}/marquer-livre/`, { signataire: 'ATOT53' })
  const bc = await must('GET', `/ventes/bons-commande/${bcId}/`)
  verif('P1.3', 'BC livré du devis D1 / client A', bc.statut === 'livre' && bc.devis === D1.id, { statut: bc.statut, devis: bc.devis, client: bc.client, livrer: liv.st })
  const q1 = await call('PATCH', `/ventes/bons-commande/${bcId}/`, { devis: D2.id }, 409)
  verif('P1.3', 'PATCH BC {devis: D2} : 409', q1.st === 409, { st: q1.st, body: q1.body })
  const q2 = await call('PATCH', `/ventes/bons-commande/${bcId}/`, { client: B.id }, 409)
  verif('P1.3', 'PATCH BC {client: B} : 409', q2.st === 409, { st: q2.st, body: q2.body })
  const q3 = await call('PATCH', `/ventes/bons-commande/${bcId}/`, { note: 'x' }, 200)
  verif('P1.3', 'PATCH BC {note} : 200', q3.st === 200, { st: q3.st })
  const q4 = await call('PATCH', `/ventes/bons-commande/${bcId}/`, { devis: D1.id }, 200)
  verif('P1.3', 'PATCH BC {devis: D1 (sa valeur)} : 200', q4.st === 200, { st: q4.st })
  const bcR = await must('GET', `/ventes/bons-commande/${bcId}/`)
  verif('P1.3', 'persistance : devis D1, client A', bcR.devis === D1.id && bcR.client === bc.client, { devis: bcR.devis, client: bcR.client })
  const caps = []
  if (page) {
    const c1 = await capture('P1.1', `${FRONT}/ventes/factures`)
    caps.push(c1.f)
    await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {})
    const c3 = await capture('P1.3', `${FRONT}/ventes/bons-commande`)
    caps.push(c3.f)
  }
  return { emise: emise.id, emiseRef: emise.reference, bc: bcId, A: A.id, B: B.id, D1: D1.id, D2: D2.id, p: p.id, caps }
}

// ── (6) note de débit puis grand livre, journal, IIF, export comptable — ATOT46, ATOT47 ──
function parseCsv(txt) {
  const lignes = txt.replace(/^﻿/, '').split(/\r?\n/).filter((l) => l.trim())
  const sep = (lignes[0].match(/;/g) || []).length > (lignes[0].match(/,/g) || []).length ? ';' : ','
  const split = (l) => { const out = []; let cur = ''; let q = false; for (const ch of l) { if (ch === '"') q = !q; else if (ch === sep && !q) { out.push(cur); cur = '' } else cur += ch } out.push(cur); return out }
  const head = split(lignes[0])
  return { head, rows: lignes.slice(1).map(split) }
}
const n = (s) => Number(String(s || '0').replace(/\s/g, '').replace(',', '.'))

async function etape6() {
  const C = await client('C6')
  const p10 = await produit('Panneau10', '400'); const p20 = await produit('Onduleur20', '600')
  const f = await factureLibre(C, [{ produit: p10.id, designation: 'Panneau', pu: '400', tva: '10.00' }, { produit: p20.id, designation: 'Onduleur', pu: '600', tva: '20.00' }], true)
  verif('P6', 'facture émise 1 000 HT (400 @10 + 600 @20) = 1 160 TTC', eq2(f.total_ht, 1000) && eq2(f.total_ttc, 1160), { ref: f.reference, ht: f.total_ht, tva: f.total_tva, ttc: f.total_ttc })
  const av = await must('POST', `/ventes/factures/${f.id}/creer-avoir/`, { motif: 'ATOT53 avoir', lignes: [{ produit: p20.id, designation: 'Onduleur', quantite: '1', prix_unitaire: '200', taux_tva: '20.00' }] })
  const jv0 = await call('GET', `/ventes/journal-ventes/?start=${today}&end=${today}`, undefined, [200, 202])
  if (Buffer.isBuffer(jv0.body)) fs.writeFileSync(path.join(OUT, `journal-ventes-${mode}-avant-note.xlsx`), jv0.body)
  const nd = await must('POST', `/ventes/factures/${f.id}/creer-note-debit/`, { motif: 'ATOT53 pénalité', lignes: [{ produit: p20.id, designation: 'Pénalité', quantite: '1', prix_unitaire: '100', taux_tva: '20' }] })
  const avRef = av.reference || (av.avoir && av.avoir.reference); const ndRef = nd.reference || (nd.note_debit && nd.note_debit.reference)
  log('avoir', JSON.stringify(av).slice(0, 300)); log('note', JSON.stringify(nd).slice(0, 300))
  verif('P6', 'avoir émis 200 HT @20 et note de débit émise 100 HT @20', !!avRef && !!ndRef, { avoir: [avRef, av.statut, av.total_ttc], note: [ndRef, nd.statut, nd.total_ttc] })
  const refs = [f.reference, avRef, ndRef]
  const Q = `start=${today}&end=${today}`
  // export comptable csv (ATOT47)
  const ec = await must('GET', `/ventes/export-comptable/?${Q}&fmt=csv`)
  const ecTxt = Buffer.isBuffer(ec) ? ec.toString('utf8') : String(ec)
  fs.writeFileSync(path.join(OUT, `export-comptable-${mode}.csv`), ecTxt.split(/\r?\n/).filter((l, i) => i === 0 || refs.some((r) => r && l.includes(r))).join('\n') + '\n')
  const { head, rows } = parseCsv(ecTxt)
  log('entêtes export comptable', head.join(' | '))
  const mine = rows.filter((r) => r.some((c) => refs.includes(c.trim())))
  const iHT = head.findIndex((h) => /^Total HT/i.test(h)); const iTVA = head.findIndex((h) => /^TVA$|montant.?tva|TVA \(/i.test(h)); const iTTC = head.findIndex((h) => /TTC/i.test(h))
  const sum = (i) => mine.reduce((s, r) => s + n(r[i]), 0)
  const tot = { ht: sum(iHT), tva: sum(iTVA), ttc: sum(iTTC), lignes: mine.length, cols: [head[iHT], head[iTVA], head[iTTC]] }
  verif('P6.3', 'export comptable (csv) : 900 HT / 140 TVA / 1 040 TTC sur nos pièces', eq2(tot.ht, 900) && eq2(tot.tva, 140) && eq2(tot.ttc, 1040), tot)
  const ligneAv = mine.find((r) => r.includes(avRef)); const ligneNd = mine.find((r) => r.includes(ndRef))
  verif('P6.3', 'avoir en ligne négative, note en ligne positive', !!ligneAv && n(ligneAv[iTTC]) < 0 && !!ligneNd && n(ligneNd[iTTC]) > 0, { avoir: ligneAv, note: ligneNd })
  const ex = await call('GET', `/ventes/export-comptable/?${Q}`, undefined, [200, 202])
  if (Buffer.isBuffer(ex.body)) fs.writeFileSync(path.join(OUT, `export-comptable-${mode}.xlsx`), ex.body)
  verif('P6.3', 'export comptable xlsx servi', ex.st === 200 && Buffer.isBuffer(ex.body) && ex.body.length > 0, { st: ex.st, ct: ex.ct })
  // grand livre csv (ATOT46)
  const gl = await must('GET', `/ventes/export-comptable/?${Q}&layout=grand-livre&fmt=csv`)
  const glTxt = Buffer.isBuffer(gl) ? gl.toString('utf8') : String(gl)
  const g = parseCsv(glTxt)
  const glNd = g.rows.filter((r) => r.some((c) => c.trim() === ndRef))
  fs.writeFileSync(path.join(OUT, `grand-livre-${mode}.csv`), [g.head.join(';'), ...g.rows.filter((r) => r.some((c) => refs.includes(c.trim()))).map((r) => r.join(';'))].join('\n') + '\n')
  log('entêtes grand livre', g.head.join(' | '))
  const iD = g.head.findIndex((h) => /d[ée]bit/i.test(h)); const iC = g.head.findIndex((h) => /cr[ée]dit/i.test(h)); const iCpt = g.head.findIndex((h) => /compte/i.test(h))
  const deb = glNd.reduce((s, r) => s + n(r[iD]), 0); const cre = glNd.reduce((s, r) => s + n(r[iC]), 0)
  const comptes = glNd.map((r) => `${r[iCpt]}:${r[iD]}/${r[iC]}`)
  const has = (cpt, d, c) => glNd.some((r) => String(r[iCpt]).startsWith(cpt) && eq2(n(r[iD]), d) && eq2(n(r[iC]), c))
  verif('P6.1', 'grand livre : note de débit D 3421 120 / C 7111 100 / C 4455 20, équilibrée', glNd.length >= 3 && eq2(deb, cre) && has('3421', 120, 0) && has('7111', 0, 100) && has('4455', 0, 20), { lignes: glNd.length, deb, cre, comptes })
  // IIF
  const iif = await must('GET', `/ventes/export-comptable/?${Q}&layout=quickbooks`)
  const iifTxt = Buffer.isBuffer(iif) ? iif.toString('utf8') : String(iif)
  const blocs = iifTxt.split(/\r?\n/).filter((l) => l.includes(ndRef))
  fs.writeFileSync(path.join(OUT, `quickbooks-${mode}.iif`), iifTxt.split(/\r?\n/).filter((l, i) => i < 3 || refs.some((r) => r && l.includes(r))).join('\n') + '\n')
  verif('P6.1', 'IIF : la note de débit y figure', blocs.length > 0, { lignes: blocs.length })
  // journal des ventes (xlsx) — lu par openpyxl côté orchestrateur
  const jv = await call('GET', `/ventes/journal-ventes/?${Q}`, undefined, [200, 202])
  if (Buffer.isBuffer(jv.body)) fs.writeFileSync(path.join(OUT, `journal-ventes-${mode}.xlsx`), jv.body)
  verif('P6.2', 'journal des ventes xlsx servi (contenu relu par openpyxl)', jv.st === 200 && Buffer.isBuffer(jv.body), { st: jv.st })
  let cap = null
  if (page) cap = (await capture('P6', `${FRONT}/ventes/factures`)).f
  return { facture: f.id, factureRef: f.reference, avoirRef: avRef, noteRef: ndRef, cap }
}

;(async () => {
  let browser = null
  try {
    if (mode === 'head') {
      browser = await chromium.launch()
      ctx = await browser.newContext({ baseURL: FRONT, serviceWorkers: 'block', viewport: { width: 1440, height: 900 } })
      page = await ctx.newPage()
      surveiller(page)
      await page.goto('/login')
      await page.getByPlaceholder('Entrez votre identifiant').fill('demo_admin')
      await page.locator('input[type="password"]').fill('Demo@2026!')
      await page.getByRole('button', { name: 'Se connecter →' }).click()
      await page.waitForURL(/\/apps/, { timeout: 60000 })
      req = page.request
    } else {
      const anon = await pwRequest.newContext({ baseURL: BASE })
      const t = await anon.post(`${API}/token/`, { data: { username: 'demo_admin', password: 'Demo@2026!' } })
      const tb = await t.json().catch(() => ({}))
      log('token', t.status())
      const headers = tb.access ? { Authorization: `Bearer ${tb.access}` } : {}
      req = await pwRequest.newContext({ baseURL: BASE, extraHTTPHeaders: headers, storageState: await anon.storageState() })
    }
    const res = { mode, base: BASE, run: RUN }
    const quoi = (process.env.ETAPES || '1,6').split(',')
    if (quoi.includes('1')) { try { res.e1 = await etape1() } catch (e) { log('ETAPE1 ERREUR', String(e)); verif('P1.x', 'étape 1 exécutée sans erreur', false, String(e)) } }
    if (quoi.includes('6')) { try { res.e6 = await etape6() } catch (e) { log('ETAPE6 ERREUR', String(e)); verif('P6.x', 'étape 6 exécutée sans erreur', false, String(e)) } }
    res.etapes = etapes
    res.incidents = incidents
    fs.writeFileSync(path.join(OUT, `rejeu-${mode}.json`), JSON.stringify(res, null, 2))
    fs.writeFileSync(path.join(OUT, `rejeu-${mode}.log`), journal.join('\n') + '\n')
    log('INCIDENTS', incidents)
  } finally {
    if (browser) await browser.close()
  }
})()
