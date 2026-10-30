// CEC6 — spec d'acceptation en direct du groupe CEC (économie et retour C&I) :
// devis automatiques boulangerie BT, bureaux BT et usine MT, chacun « sans » ET
// « avec batterie » (lead `batterie_souhaitee: les_deux`), jouée par
// l'ORCHESTRATEUR sur la pile locale (CLAUDE.md 3-bis, METHODE §C.4, `_format.md`).
//
// Pour chaque devis : l'économie an 1 et le retour sont comparés sur QUATRE
// surfaces + un recalcul à la main écrit dans la trace :
//   (a) le PDF client `GET ventes/devis/<id>/proposal/` (règle #4, texte pdfjs) ;
//   (b) le bloc interne `GET ventes/devis/<id>/economie-ci/` (`economie_ci`) ;
//   (c) la charge publique `GET ventes/proposal/<jeton interne>/` — la page
//       `/proposition` (Astro) N'EST PAS lancée sur cette pile : on lit la charge
//       qu'elle rend et on applique la règle de `syntheseCi.ts::lireArgentCi`
//       (CE2E2 : `mode_kpis.payback`, sinon `argent.indicateurs.retour_ans`) ;
//       un brouillon n'est servi qu'au jeton d'aperçu interne (ADEV11) ;
//   (d) la bannière « Devis créé : … » de l'écran lead (P1.1-P1.3 cliquent le
//       vrai bouton « Devis automatique ») et la réponse `devis/auto` (CE2E3).
// Recalcul à la main : économie = Σ kWh évités × tarif du poste ; retour =
// cumul refait depuis l'investissement HT (année 0) + flux annuels servis,
// interpolé dans l'année du passage à zéro (au dixième) ; l'entier
// `indicateurs.retour_ans` = année de ce passage. Option batterie (BT, un seul
// poste tarifaire) : couverture × consommation annuelle × tarif moyen (± 1 %).
//
// Société : `taqinor-anon` (anon_admin) — la seule de cette pile qui porte les
// forfaits C&I et les rôles de composition ; demo_admin (société 1) n'a ni l'un
// ni l'autre (devis auto C&I impossible). Le mot de passe est LU dans
// `qa_import_anonymise.py` (ANON_PASSWORD), jamais écrit ici ni imprimé.
// Prix du catalogue = valeurs d'essai : la recette juge la cohérence, jamais le
// niveau des prix.
import { test, expect } from '@playwright/test'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { groupe } from './_oracles.js'
import { RACINE, aujourdHui } from './_enregistrement.js'
import { uniq, lireJson, textePdf, telephoneMobileUnique, connexionApi } from '../helpers.js'

const etape = groupe('CEC', ['CEC6'])
// Pile partagée avec un autre rejeu : la mise en place du contexte (trace 'on') peut dépasser
// les 60 s par défaut AVANT le corps — le délai couvre donc aussi les fixtures.
test.describe.configure({ timeout: 600_000 })
const API = '/api/django'
const T = { timeout: 180_000 }
const n = (s) => Number(String(s).replace(/[\s]/g, '').replace(',', '.'))
const plat = (s) => String(s).replace(/[\s]+/g, ' ')
const r1 = (v) => Math.round(v * 10) / 10

function motDePasseAnon() {
  const src = readFileSync(join(RACINE, 'backend/django_core/authentication/management/commands/qa_import_anonymise.py'), 'utf8')
  const m = src.match(/ANON_PASSWORD\s*=\s*['"]([^'"]+)['"]/)
  if (!m) throw new Error('ANON_PASSWORD introuvable dans qa_import_anonymise.py')
  return m[1]
}

async function connexionAnon(page, context) {
  await context.clearCookies()
  await connexionApi(page.request, { username: 'anon_admin', password: motDePasseAnon() })
}

const COMMUN = { ville: 'Casablanca', raccordement: 'triphase', type_toiture: 'bac_acier', batterie_souhaitee: 'les_deux' }
const PROFILS = {
  boulangerie: { type_installation: 'commercial', categorie_commerciale: 'boulangerie', tension_raccordement: 'bt', contrat_electricite: 'bt_patente', facture_hiver: '12000' },
  bureaux: { type_installation: 'commercial', categorie_commerciale: 'bureau', tension_raccordement: 'bt', contrat_electricite: 'bt_patente', facture_hiver: '15000' },
  usine: {
    type_installation: 'industriel', tension_raccordement: 'mt', contrat_electricite: 'mt_general', conso_mensuelle_kwh: '40000',
    secteur_industriel: 'textile', regime_equipes: '1x8', jours_ouverture: [1, 2, 3, 4, 5, 6], heure_debut: 8, heure_fin: 18,
  },
}

function ecrireTrace(id, lignes) {
  const chemin = `docs/audits/acceptation/CEC/traces/${aujourdHui()}/${id}.txt`
  mkdirSync(dirname(join(RACINE, chemin)), { recursive: true })
  writeFileSync(join(RACINE, chemin), `${lignes.join('\n')}\n`, 'utf8')
  return chemin
}

/** Les deux blocs « Sans batterie » / « Avec batterie » de la synthèse du PDF. */
function blocsPdf(texte) {
  const t = plat(texte)
  const sans = t.match(/Sans batterie Puissance ([\d ,]+) kWc Investissement TTC ([\d ]+,\d{2}) MAD Économie annuelle ([\d ]+) MAD HT( Retour sur investissement ([\d]+,\d) ans)?/)
  const avec = t.match(/Avec batterie Puissance ([\d ,]+) kWc Investissement TTC ([\d ]+,\d{2}) MAD Économie annuelle ([\d ]+) MAD HT( Retour sur investissement ([\d]+,\d) ans)?/)
  const lire = (m) => (m ? { kwc: n(m[1]), ttc: n(m[2]), eco: n(m[3]), retour: m[5] ? n(m[5]) : null, retourImprime: !!m[4] } : null)
  return { sans: lire(sans), avec: lire(avec) }
}

/** Recalcul à la main du retour : cumul refait depuis l'investissement HT. */
function retourMain(flux, investissement) {
  let cumul = -investissement
  let precedent = null
  const lignes = []
  for (const f of flux) {
    if (f.annee === 0) { cumul = Number(f.flux_mad); continue }
    precedent = cumul
    cumul += Number(f.flux_mad)
    lignes.push([f.annee, Math.round(cumul * 100) / 100, Number(f.cumul_mad)])
    if (cumul >= 0) return { dixieme: r1(f.annee - 1 + (-precedent) / Number(f.flux_mad)), annee: f.annee, precedent, gain: Number(f.flux_mad), lignes }
  }
  return { dixieme: null, annee: null, lignes }
}

/** Joue un profil de bout en bout ; renvoie tout ce qu'il a lu. */
async function jouer(page, nom, { ecran }) {
  const lead = await lireJson(await page.request.post(`${API}/crm/leads/`, {
    ...T, data: { nom: uniq(`CEC6 ${nom}`), telephone: telephoneMobileUnique(), ...COMMUN, ...PROFILS[nom] },
  }), `lead ${nom}`)
  let auto
  let banniere = null
  if (ecran) {
    await page.goto(`/crm/leads/${lead.id}`)
    const appel = page.waitForResponse((r) => r.request().method() === 'POST'
      && /\/ventes\/devis\/auto\/$/.test(new URL(r.url()).pathname), { timeout: 180_000 })
    const bouton = page.getByRole('button', { name: /Devis automatique/ }).first()
    await expect(bouton).toBeEnabled({ timeout: 120_000 })
    await bouton.click()
    const rep = await appel
    expect(rep.status(), `devis/auto ${nom} → ${(await rep.text()).slice(0, 300)}`).toBe(201)
    auto = await rep.json()
    const zone = page.getByTestId('ldp-succes-auto')
    await expect(zone).toBeVisible({ timeout: 120_000 })
    banniere = plat(await zone.innerText())
  } else {
    auto = await lireJson(await page.request.post(`${API}/ventes/devis/auto/`, { ...T, data: { lead: lead.id } }), `devis/auto ${nom}`)
  }
  const eco = await lireJson(await page.request.get(`${API}/ventes/devis/${auto.id}/economie-ci/`, T), 'economie-ci')
  const lien = await lireJson(await page.request.post(`${API}/ventes/devis/${auto.id}/share-link/`, { ...T, data: {} }), 'share-link')
  const pub = await lireJson(await page.request.get(`${API}/ventes/proposal/${lien.token_interne}/`, T), 'charge publique')
  const repPdf = await page.request.get(`${API}/ventes/devis/${auto.id}/proposal/`, T)
  expect(repPdf.status(), 'PDF /proposal').toBe(200)
  expect(repPdf.headers()['content-type'] || '').toContain('application/pdf')
  const texte = await textePdf(await repPdf.body())
  return { lead, auto, banniere, eco, pub, texte }
}

async function nettoyer(page, d) {
  if (d?.auto?.id) await page.request.delete(`${API}/ventes/devis/${d.auto.id}/`).catch(() => undefined)
  if (d?.lead?.id) await page.request.delete(`${API}/crm/leads/${d.lead.id}/`).catch(() => undefined)
}

/** Les comparaisons d'un devis ; renvoie la trace. Toute assertion échouée = FAIL. */
function comparer(nom, d) {
  const { auto, banniere, eco, pub, texte } = d
  const trace = [`# CEC6 — ${nom} : devis ${auto.reference} (id ${auto.id}), lead ${d.lead.id}`]
  const sc = pub.synthese_ci || {}
  const argent = sc.argent || {}
  const mk = pub.mode_kpis || {}
  const pdf = blocsPdf(texte)
  expect(pdf.sans, `PDF ${nom} : bloc « Sans batterie » lisible`).not.toBeNull()
  const e1 = eco.economie_annee1 || {}

  // ── Économie an 1 HT ──
  const parPoste = (e1.par_poste || []).map((p) => ({ ...p, main: p.kwh_evites * p.tarif_kwh }))
  const ecoMain = parPoste.reduce((s, p) => s + p.main, 0)
  trace.push(`Économie an 1 HT — recalcul : ${parPoste.map((p) => `${p.poste} ${p.kwh_evites} kWh × ${p.tarif_kwh} = ${p.main.toFixed(2)}`).join(' + ')} = ${ecoMain.toFixed(2)} MAD`)
  trace.push(`  economie_ci.economie_annee1.total_mad = ${e1.total_mad} ; PDF = ${pdf.sans.eco} ; mode_kpis.economies_annuelles = ${mk.economies_annuelles} ; synthese_ci.argent.economie_annee1.total_mad = ${argent.economie_annee1?.total_mad} ; devis/auto.economie_an_1_ht = ${auto.economie_an_1_ht}`)
  expect(Math.abs(ecoMain - e1.total_mad), `${nom} : recalcul ${ecoMain.toFixed(2)} vs economie_ci ${e1.total_mad}`).toBeLessThanOrEqual(Math.max(3, 0.0002 * e1.total_mad))
  expect(pdf.sans.eco, `${nom} : PDF économie = economie_ci arrondi`).toBe(Math.round(e1.total_mad))
  expect(mk.economies_annuelles, `${nom} : mode_kpis`).toBe(e1.total_mad)
  expect(argent.economie_annee1?.total_mad, `${nom} : charge publique`).toBe(e1.total_mad)
  expect(auto.economie_an_1_ht, `${nom} : devis/auto`).toBe(e1.total_mad)

  // ── Investissement ──
  const totSans = pub.option_totals?.sans_batterie || {}
  trace.push(`Investissement sans batterie : PDF ${pdf.sans.ttc} TTC ; option_totals ${totSans.ttc} TTC / ${totSans.ht_net} HT ; devis/auto.total_ttc ${auto.total_ttc}`)
  expect(pdf.sans.ttc, `${nom} : PDF TTC = option_totals`).toBe(totSans.ttc)
  expect(auto.total_ttc, `${nom} : devis/auto TTC`).toBe(totSans.ttc)

  // ── Retour ──
  const base = eco.base === 'ttc' ? eco.flux_ttc : eco.flux_ht
  const inv = eco.base === 'ttc' ? totSans.ttc : totSans.ht_net
  const rm = retourMain(base?.flux || [], inv)
  trace.push(`Retour — recalcul (base ${eco.base}, investissement ${inv}) : cumul refait ${rm.lignes.map(([a, c, s]) => `an ${a} ${c} (servi ${s})`).join(' ; ')}`)
  trace.push(`  passage à zéro an ${rm.annee} : ${rm.annee} − 1 + ${(-rm.precedent).toFixed(2)} / ${rm.gain} = ${rm.dixieme} ans ; simple ${inv} / ${e1.total_mad} = ${(inv / e1.total_mad).toFixed(2)} ans`)
  const retourPage = mk.payback ?? argent.indicateurs?.retour_ans ?? null // syntheseCi.ts::lireArgentCi (CE2E2)
  const retourBanniere = banniere ? (banniere.match(/retour ≈ ([\d,.]+) ans/) || [])[1] : null
  trace.push(`  PDF ${pdf.sans.retour} ; mode_kpis.payback ${mk.payback} → page /proposition « Rentabilisé en » ${retourPage} ; devis/auto.retour_ans ${auto.retour_ans} ; bannière ${retourBanniere ?? 'non jouée (API)'} ; economie_ci.indicateurs.retour_ans (entier) ${eco.indicateurs?.retour_ans}`)
  expect(rm.lignes.every(([, c, s]) => Math.abs(c - s) < 1), `${nom} : cumul refait = cumul servi`).toBeTruthy()
  expect(rm.dixieme, `${nom} : passage à zéro trouvé`).not.toBeNull()
  expect(pdf.sans.retour, `${nom} : PDF retour = recalcul`).toBe(rm.dixieme)
  expect(mk.payback, `${nom} : mode_kpis.payback`).toBe(rm.dixieme)
  expect(retourPage, `${nom} : page /proposition`).toBe(rm.dixieme)
  expect(auto.retour_ans, `${nom} : devis/auto (bannière)`).toBe(rm.dixieme)
  expect(eco.indicateurs?.retour_ans, `${nom} : entier = année du passage`).toBe(rm.annee)

  // ── Bannière écran ──
  if (banniere) {
    trace.push(`Bannière écran : « ${banniere} »`)
    expect(n(retourBanniere), `${nom} : bannière retour`).toBe(rm.dixieme)
    const ecoBan = (banniere.match(/économie ≈ ([\d\s]+)/) || [])[1]
    expect(n(ecoBan), `${nom} : bannière économie (arrondie à la centaine)`).toBe(Math.round(e1.total_mad / 100) * 100)
    expect(banniere).toContain(auto.reference)
  }

  // ── Option avec batterie ──
  const ob = sc.option_batterie
  if (ob?.totaux) {
    const vc = ob.valeur_chiffree || {}
    const totAvec = pub.option_totals?.avec_batterie || {}
    const t = plat(texte)
    const mOpt = t.match(/Total TTC ([\d ]+,\d{2}) MAD Économie annuelle HT ([\d ]+,\d{2}) MAD/)
    trace.push(`Avec batterie : PDF synthèse ${JSON.stringify(pdf.avec)} ; page d'option « Total TTC ${mOpt?.[1]} — Économie annuelle HT ${mOpt?.[2]} » ; option_batterie.valeur_chiffree.economie_annuelle_mad ${vc.economie_annuelle_mad} ; option_totals.avec_batterie.ttc ${totAvec.ttc} ; retour_simple_ans ${vc.retour_simple_ans}`)
    expect(pdf.avec, `${nom} : bloc « Avec batterie » du PDF`).not.toBeNull()
    expect(pdf.avec.eco, `${nom} : PDF économie avec`).toBe(Math.round(vc.economie_annuelle_mad))
    expect(n(mOpt?.[2]), `${nom} : page d'option économie HT`).toBe(vc.economie_annuelle_mad)
    expect(pdf.avec.ttc, `${nom} : PDF TTC avec`).toBe(totAvec.ttc)
    expect(ob.totaux.ttc).toBe(totAvec.ttc)
    // Aucun retour « avec » servi ⇒ aucun imprimé (rien d'incomparable sur le document).
    expect(pdf.avec.retourImprime, `${nom} : retour avec imprimé sans être servi`).toBe(vc.retour_simple_ans != null)
    const conso = (sc.energie?.par_mois || []).reduce((s, m) => s + Number(m.consommation_kwh || 0), 0)
    if ((e1.par_poste || []).length === 1 && vc.taux_couverture_pct != null) {
      const tarif = e1.par_poste[0].tarif_kwh
      const main = (vc.taux_couverture_pct / 100) * conso * tarif
      trace.push(`  recalcul avec : couverture ${vc.taux_couverture_pct} % × ${conso} kWh/an × ${tarif} = ${main.toFixed(0)} MAD (servi ${vc.economie_annuelle_mad}, écart ${((main / vc.economie_annuelle_mad - 1) * 100).toFixed(2)} %) ; retour simple main ${totAvec.ht_net} / ${vc.economie_annuelle_mad} = ${(totAvec.ht_net / vc.economie_annuelle_mad).toFixed(1)} ans (non servi, non imprimé)`)
      expect(Math.abs(main / vc.economie_annuelle_mad - 1), `${nom} : recalcul avec ± 1 %`).toBeLessThanOrEqual(0.01)
    } else {
      trace.push(`  recalcul avec : ${(e1.par_poste || []).length} postes tarifaires (pointe/pleines/creuses) — la batterie déplace l'énergie vers d'autres postes, recalcul au tarif moyen non probant, non fait ; retour simple main ${totAvec.ht_net} / ${vc.economie_annuelle_mad} = ${(totAvec.ht_net / vc.economie_annuelle_mad).toFixed(1)} ans (non servi, non imprimé)`)
    }
  } else {
    trace.push(`Avec batterie : aucune option servie (${ob?.motif || 'motif absent'}) ; PDF ${JSON.stringify(pdf.avec)}`)
    expect(pdf.avec, `${nom} : pas de bloc « Avec » sans option servie`).toBeNull()
  }
  return trace
}

for (const [id, nom] of [['P1.1', 'boulangerie'], ['P1.2', 'bureaux'], ['P1.3', 'usine']]) {
  etape(id, ['CEC6'], async ({ page, context, suivi, testInfo }) => {
    testInfo.setTimeout(600_000)
    await connexionAnon(page, context)
    let d = null
    try {
      d = await jouer(page, nom, { ecran: true })
      let trace = [`(pile 127.0.0.1:5191 → :8010, anon_admin / taqinor-anon ; page /proposition non lancée : charge publique lue)`]
      try {
        trace = trace.concat(comparer(nom, d))
      } finally {
        ecrireTrace(id, trace.concat([`PDF (texte, extrait) : ${plat(d.texte).match(/Sans batterie Puissance.{0,420}/)?.[0] || '—'}`]))
      }
      suivi.verifie(6)
    } finally {
      await nettoyer(page, d)
    }
  })
}

// ── P1.4 — sensibilités industrielles imprimées (page 3 du PDF usine) vs economie_ci et le bon sens ──
etape('P1.4', ['CEC6'], async ({ page, context, suivi, testInfo }) => {
  testInfo.setTimeout(600_000)
  await connexionAnon(page, context)
  let d = null
  const trace = ['# CEC6 — sensibilités du PDF industriel (usine MT, devis par l’API)']
  try {
    d = await jouer(page, 'usine', { ecran: false })
    trace.push(`devis ${d.auto.reference} (id ${d.auto.id})`)
    const t = plat(d.texte)
    const m = t.match(/Scénario central ([\d,]+) ans ([\d,]+) % ([\d ]+,\d{2}) MAD Production (-?[\d,]+) % ([\d,]+) ans ([\d,]+) % ([\d ]+,\d{2}) MAD/)
    expect(m, 'tableau des sensibilités lisible dans le PDF').not.toBeNull()
    const pdf = { central: { retour: n(m[1]), tri: n(m[2]), cumul: n(m[3]) }, prod: { variation: n(m[4]), retour: n(m[5]), tri: n(m[6]), cumul: n(m[7]) } }
    const s = (d.eco.sensibilites || []).find((x) => x.cle === 'production')
    const flux = d.eco.flux_ht?.flux || []
    const cumulCentral = Number(flux[flux.length - 1]?.cumul_mad)
    const ecoCentral = d.eco.economie_annee1?.total_mad
    trace.push(`PDF : central ${JSON.stringify(pdf.central)} ; production ${JSON.stringify(pdf.prod)}`)
    trace.push(`economie_ci.sensibilites[production] : ${JSON.stringify(s)}`)
    trace.push(`economie_ci central : économie an 1 ${ecoCentral} ; cumul 25 ans ${cumulCentral} ; TRI ${d.eco.indicateurs?.tri_pct}`)
    trace.push(`Recalcul à la main : la production baisse de ${-pdf.prod.variation} % (P90) et RIEN d'autre ne change ⇒ autoconsommé ≤ central, donc économie an 1 ≤ ${ecoCentral}, cumul ≤ ${cumulCentral}, TRI ≤ ${d.eco.indicateurs?.tri_pct}`)
    // PDF = economie_ci (le document imprime le bloc servi).
    expect(pdf.prod.cumul, 'PDF cumul production = economie_ci').toBe(s.cumul_25_ans_mad)
    expect(pdf.central.cumul, 'PDF cumul central = economie_ci').toBe(cumulCentral)
    // Le bon sens économique (recalcul) : moins de production ⇒ jamais plus d'économie.
    const ecarts = []
    if (s.economie_annee1_mad > ecoCentral) ecarts.push(`économie an 1 P90 ${s.economie_annee1_mad} > centrale ${ecoCentral}`)
    if (s.cumul_25_ans_mad > cumulCentral) ecarts.push(`cumul 25 ans P90 ${s.cumul_25_ans_mad} > central ${cumulCentral}`)
    if (s.tri_pct > d.eco.indicateurs?.tri_pct) ecarts.push(`TRI P90 ${s.tri_pct} > central ${d.eco.indicateurs?.tri_pct}`)
    trace.push(ecarts.length ? `ÉCART : ${ecarts.join(' ; ')} — responsable : backend/django_core/apps/ventes/economie_ci.py::_apercu_production (autoconsommé recalculé min(production, charge) cellule par cellule, base différente du scénario central)` : 'Aucun écart')
    expect(ecarts, 'sensibilité production : moins de production ⇒ jamais plus d’économie').toEqual([])
    suivi.verifie(6)
  } finally {
    ecrireTrace('P1.4', trace)
    await nettoyer(page, d)
  }
})
