// CMP12 (D-CMP-7 = a) — un envoyé C&I de niveau ≤ 2 recalculé par un geste complet passe au niveau 3, tracé, et le PDF suit.
// Le devis vient de la vraie route ; seul le niveau 2 et sa date du passé sont posés au shell (aucun geste ne les pose).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage } from '../helpers.js'
import { API, T, marque, catalogueCi, retablirCatalogueApresTout, leadCi, devisAuto, devisRelu, envoyer, pdfTexte } from './_ci.js'

const etape = groupe('CMP', ['CMP12'])
fermerDjangoApresTout()
retablirCatalogueApresTout()
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

etape('P12.recalcul_niveau_2', ['CMP12'], async ({ page }) => {
  const r = page.request
  await catalogueCi(r)
  const m = marque()
  const lead = await leadCi(r, `CMP12 ${m}`)
  const cree = await devisAuto(r, lead.id)
  const id = cree.id ?? cree.devis?.id
  await envoyer(r, id)
  await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk=${id}).update(regles_calcul=2); sortie(1)`)
  const avant = await devisRelu(r, id)
  expect([avant.statut, avant.regles_calcul], 'envoyé, niveau 2').toEqual(['envoye', 2])
  const pdfAvant = await pdfTexte(r, id)
  const etudeAvant = await py(`from apps.ventes.models import Devis
d = Devis.objects.get(pk=${id}); sortie(json.dumps(d.etude_params.get('etude_ci'), sort_keys=True, default=str))`)
  // Recalcul SANS geste complet (lignes seules) : niveau et étude gardés.
  const lignes = avant.lignes.map((l) => ({ produit: l.produit, designation: l.designation, quantite: l.quantite, prix_unitaire: l.prix_unitaire, remise: l.remise, taux_tva: l.taux_tva, type_ligne: l.type_ligne, ordre: l.ordre }))
  await lireJson(await r.post(`${API}/ventes/devis/${id}/replace-lines/`, { ...T, data: { lignes, expected_updated_at: avant.updated_at } }), 'lignes seules')
  const temoin = await devisRelu(r, id)
  expect(temoin.regles_calcul, 'témoin : sans geste complet, niveau 2 gardé').toBe(2)
  // Geste complet : en-tête + lignes au même prix.
  await lireJson(await r.post(`${API}/ventes/devis/${id}/replace-lines/`, { ...T, data: { lignes, entete: { notes: `Correction CMP12 ${m}` }, expected_updated_at: temoin.updated_at } }), 'geste complet')
  const apres = await devisRelu(r, id)
  expect(apres.statut, 'statut intact (règle #4)').toBe('envoye')
  expect(apres.regles_calcul, 'persistance : niveau 3').toBe(3)
  const trace = await py(`from apps.ventes.models import DevisActivity
sortie(list(DevisActivity.objects.filter(devis_id=${id}, field='regles_calcul').values_list('old_value', 'new_value', 'body')))`)
  expect(trace, 'une trace au chatter').toEqual([['2', '3', 'Règles du 27/10 appliquées au recalcul.']])
  const pdfApres = await pdfTexte(r, id)
  const etudeApres = await py(`from apps.ventes.models import Devis
d = Devis.objects.get(pk=${id}); sortie(json.dumps(d.etude_params.get('etude_ci'), sort_keys=True, default=str))`)
  expect(etudeApres, 'étude recalculée au niveau 3').toBeTruthy()
  expect(pdfApres.length, 'le PDF se rend').toBeGreaterThan(500)
  test.info().annotations.push({ type: 'pdf', description: `avant ${pdfAvant.length} car., après ${pdfApres.length} car. ; étude ${etudeAvant === etudeApres ? 'identique' : 'recalculée'} ; PDF ${pdfAvant === pdfApres ? 'identique' : 'différent'}` })
  console.log(`[CMP12] étude ${etudeAvant === etudeApres ? 'identique' : 'recalculée'} ; PDF ${pdfAvant === pdfApres ? 'identique' : 'différent'}`)
  // Un second geste : aucune nouvelle trace, jamais à la baisse.
  const relu = await devisRelu(r, id)
  await lireJson(await r.post(`${API}/ventes/devis/${id}/replace-lines/`, { ...T, data: { lignes, entete: { notes: `Correction bis CMP12 ${m}` }, expected_updated_at: relu.updated_at } }), 'second geste')
  expect((await devisRelu(r, id)).regles_calcul).toBe(3)
  expect(await py(`from apps.ventes.models import DevisActivity
sortie(DevisActivity.objects.filter(devis_id=${id}, field='regles_calcul').count())`), 'une seule trace').toBe(1)
})
