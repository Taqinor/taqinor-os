// Relit facture émise + BC de l'étape 1 après le poste admin. Usage : node relire.cjs <base> <rejeu.json> <out.json>
const { request } = require('playwright'); const fs = require('fs')
const [BASE, RJ, OUTF] = process.argv.slice(2); const r = JSON.parse(fs.readFileSync(RJ, 'utf8')).e1
;(async () => {
  const a = await request.newContext({ baseURL: BASE })
  const t = await (await a.post('/api/django/token/', { data: { username: 'demo_admin', password: 'Demo@2026!' } })).json()
  const c = await request.newContext({ baseURL: BASE, extraHTTPHeaders: t.access ? { Authorization: `Bearer ${t.access}` } : {}, storageState: await a.storageState() })
  const f = await (await c.get(`/api/django/ventes/factures/${r.emise}/`)).json()
  const b = await (await c.get(`/api/django/ventes/bons-commande/${r.bc}/`)).json()
  const o = { facture: { id: f.id, statut: f.statut, ttc: f.total_ttc, lignes: f.lignes.map((l) => [l.id, l.quantite, l.prix_unitaire]), abandon_montant: f.abandon_montant }, bc: { id: b.id, statut: b.statut, devis: b.devis, client: b.client }, attendu: { D1: r.D1, D2: r.D2 } }
  fs.writeFileSync(OUTF, JSON.stringify(o, null, 2)); console.log(JSON.stringify(o))
})()
