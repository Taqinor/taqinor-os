// PVOND — tests de la logique PURE du mini-formulaire « fiche technique »
// (frontend/src/pages/stock/pvondFicheTechnique.js). Module sans dépendance :
// s'exécute directement, sans node_modules.
// Run : node --test src/pages/stock/pvondFicheTechnique.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  MARQUEUR_PLAGE_BATTERIE,
  lirePlageBatterieDescription, ecrirePlageBatterieDescription,
  plageBatterieDeclaree, plageBatterieAbsenteLocale,
  plageBatterieDeclareeChamps, plageBatterieAbsenteChamps,
  CONTRAT_ONDULEUR_FR, manquantesOnduleurLocal,
  typeFicheBackend, ficheFieldsVides, champsFicheDepuisServeur,
  champsFichePourType,
  LIBELLES_FICHE, VALEUR_ABSENTE, valeurFicheAffichee, groupeFicheAffichage,
  // CALX355
  CHOIX_CHIMIE_BATTERIE, COURBES_FICHE, ligneCourbeVide, lignesCourbeDepuisServeur,
  validerCourbe, erreursCourbesPourType, estOptimiseurNom, typeFicheFormulaire,
  messageRefusFiche,
} from './pvondFicheTechnique.js'

// ── Plage de tension batterie — lecture (miroir de plage_batterie_onduleur,
//    apps/stock/selectors.py) ────────────────────────────────────────────────
test('lit une fenêtre déclarée « 40-60 V »', () => {
  assert.deepEqual(
    lirePlageBatterieDescription('Onduleur hybride de test\nPlage batterie : 40-60 V'),
    { aucune: false, min: '40', max: '60' })
})

test('« aucune » est une valeur pleine — jamais une absence', () => {
  assert.deepEqual(
    lirePlageBatterieDescription('Plage batterie : aucune (onduleur réseau)'),
    { aucune: true, min: '', max: '' })
})

test('tiret demi-cadratin et virgule décimale tolérés, ordre bas/haut indifférent', () => {
  assert.deepEqual(
    lirePlageBatterieDescription('Plage batterie : 700,5 – 160'),
    { aucune: false, min: '160', max: '700.5' })
})

test('rien de déclaré → non renseigné', () => {
  assert.deepEqual(
    lirePlageBatterieDescription('Une description sans rien de spécial.'),
    { aucune: false, min: '', max: '' })
  assert.deepEqual(lirePlageBatterieDescription(''), { aucune: false, min: '', max: '' })
  assert.deepEqual(lirePlageBatterieDescription(null), { aucune: false, min: '', max: '' })
})

// ── Écriture — round-trip et préservation des autres lignes ────────────────
test('écrit une plage numérique dans une description vide', () => {
  const d = ecrirePlageBatterieDescription('', { aucune: false, min: '40', max: '60' })
  assert.equal(d, 'Plage batterie : 40-60 V')
  assert.deepEqual(lirePlageBatterieDescription(d), { aucune: false, min: '40', max: '60' })
})

test('écrit « aucune » quand le toggle réseau est actif', () => {
  const d = ecrirePlageBatterieDescription('', { aucune: true, min: '', max: '' })
  assert.equal(d, 'Plage batterie : aucune (onduleur réseau)')
})

test('remplace la ligne existante SANS toucher aux autres lignes', () => {
  const avant = 'Onduleur hybride robuste.\nPlage batterie : 40-60 V\nGarantie 10 ans.'
  const apres = ecrirePlageBatterieDescription(avant, { aucune: false, min: '160', max: '700' })
  assert.equal(apres, 'Onduleur hybride robuste.\nGarantie 10 ans.\nPlage batterie : 160-700 V')
})

test('min/max invalides ou incomplets → aucune ligne écrite (retire une ligne existante)', () => {
  const avant = 'Description.\nPlage batterie : 40-60 V'
  assert.equal(
    ecrirePlageBatterieDescription(avant, { aucune: false, min: '40', max: '' }),
    'Description.')
  assert.equal(
    ecrirePlageBatterieDescription(avant, { aucune: false, min: '', max: '' }),
    'Description.')
})

test('min > max est réordonné à l\'écriture', () => {
  const d = ecrirePlageBatterieDescription('', { aucune: false, min: '60', max: '40' })
  assert.equal(d, 'Plage batterie : 40-60 V')
})

test('le marqueur exporté correspond au format écrit', () => {
  assert.ok(ecrirePlageBatterieDescription('', { aucune: true }).startsWith(MARQUEUR_PLAGE_BATTERIE))
})

test('plageBatterieDeclaree : vraie pour une fenêtre ou « aucune », fausse sinon', () => {
  assert.equal(plageBatterieDeclaree('Plage batterie : 40-60 V'), true)
  assert.equal(plageBatterieDeclaree('Plage batterie : aucune (onduleur réseau)'), true)
  assert.equal(plageBatterieDeclaree('Rien ici.'), false)
  assert.equal(plageBatterieDeclaree(''), false)
})

// ── plageBatterieAbsenteLocale — règle CORRIGÉE (commit ed34ced9, ordre
//    fondateur 18/08) : la plage n'est exigée QUE d'un onduleur HYBRIDE.
//    MIROIR de `plage_batterie_onduleur` (apps/stock/selectors.py). ──────────
test('HYBRIDE sans ligne déclarée → absente (comportement inchangé)', () => {
  assert.equal(plageBatterieAbsenteLocale({
    estHybride: true, estReseau: false, description: '',
  }), true)
})

test('HYBRIDE avec une plage déclarée → non absente', () => {
  assert.equal(plageBatterieAbsenteLocale({
    estHybride: true, estReseau: false, description: 'Plage batterie : 40-60 V',
  }), false)
})

test('HYBRIDE avec « aucune » déclarée → non absente (valeur pleine)', () => {
  assert.equal(plageBatterieAbsenteLocale({
    estHybride: true, estReseau: false, description: 'Plage batterie : aucune (onduleur réseau)',
  }), false)
})

test('RÉSEAU sans AUCUNE ligne déclarée → JAMAIS absente (la famille vaut « aucune »)', () => {
  assert.equal(plageBatterieAbsenteLocale({
    estHybride: false, estReseau: true, description: '',
  }), false)
})

test('RÉSEAU même sur un produit tout juste en cours de création (pas de fallback serveur nécessaire)', () => {
  // Reproduit exactement le bug corrigé : `produit` est `null` (création),
  // donc `plageBatterieServeurAbsente` vaudrait `true` par défaut — un
  // onduleur réseau doit rester « non absente » MALGRÉ ce défaut, la
  // famille suffit à elle seule.
  assert.equal(plageBatterieAbsenteLocale({
    estHybride: false, estReseau: true, description: '',
    plageBatterieServeurAbsente: true,
  }), false)
})

test('RÉSEAU avec une ligne déclarée reste non absente (la ligne prime, cohérent)', () => {
  assert.equal(plageBatterieAbsenteLocale({
    estHybride: false, estReseau: true, description: 'Plage batterie : aucune (onduleur réseau)',
  }), false)
})

test('ni hybride ni réseau (famille indéterminée / hors périmètre) → repli sur l\'état SERVEUR', () => {
  assert.equal(plageBatterieAbsenteLocale({
    estHybride: false, estReseau: false, description: '',
    plageBatterieServeurAbsente: true,
  }), true)
  assert.equal(plageBatterieAbsenteLocale({
    estHybride: false, estReseau: false, description: '',
    plageBatterieServeurAbsente: false,
  }), false)
})

// ── PVOND-H — même contrat, lu sur le CHAMP DÉDIÉ plutôt que la description ─
test('plageBatterieDeclareeChamps : vraie pour aucune=true ou une plage min/max, fausse sinon', () => {
  assert.equal(plageBatterieDeclareeChamps({ ond_bat_aucune: true }), true)
  assert.equal(plageBatterieDeclareeChamps({ ond_bat_v_min: '40', ond_bat_v_max: '60' }), true)
  assert.equal(plageBatterieDeclareeChamps({ ond_bat_v_min: '40', ond_bat_v_max: '' }), false)
  assert.equal(plageBatterieDeclareeChamps({}), false)
  assert.equal(plageBatterieDeclareeChamps(undefined), false)
})

test('plageBatterieAbsenteChamps : HYBRIDE exigé, RÉSEAU jamais absente, sinon repli SERVEUR', () => {
  assert.equal(plageBatterieAbsenteChamps({ estHybride: true, estReseau: false, ficheFields: {} }), true)
  assert.equal(plageBatterieAbsenteChamps({
    estHybride: true, estReseau: false, ficheFields: { ond_bat_v_min: '40', ond_bat_v_max: '60' },
  }), false)
  assert.equal(plageBatterieAbsenteChamps({
    estHybride: true, estReseau: false, ficheFields: { ond_bat_aucune: true },
  }), false)
  assert.equal(plageBatterieAbsenteChamps({ estHybride: false, estReseau: true, ficheFields: {} }), false)
  assert.equal(plageBatterieAbsenteChamps({
    estHybride: false, estReseau: false, ficheFields: {}, plageBatterieServeurAbsente: true,
  }), true)
  assert.equal(plageBatterieAbsenteChamps({
    estHybride: false, estReseau: false, ficheFields: {}, plageBatterieServeurAbsente: false,
  }), false)
})

// ── Verrou de complétude onduleur — miroir de CONTRAT_ONDULEUR ─────────────
test('CONTRAT_ONDULEUR_FR a bien les 10 variables du contrat backend, dans le même ordre', () => {
  assert.deepEqual(CONTRAT_ONDULEUR_FR.map(([cle]) => cle), [
    'ond_ac_kw', 'ond_phases', 'ond_n_mppt', 'ond_mppt_v_min', 'ond_mppt_v_max',
    'ond_v_max_abs', 'ond_i_max_mppt_a', 'ond_rendement_euro_pct',
    '__plage_batterie_v', '__garantie',
  ])
  assert.deepEqual(CONTRAT_ONDULEUR_FR.map(([, libelle]) => libelle), [
    'puissance AC (kW)', 'monophasé / triphasé', "nombre d'entrées MPPT",
    'plage MPPT — tension mini (V)', 'plage MPPT — tension maxi (V)',
    'tension DC maximale (V)', 'courant maxi par MPPT (A)',
    'rendement européen (%)', 'plage de tension batterie (V)',
    'garantie constructeur',
  ])
})

test('fiche complète (tout renseigné) → aucune variable manquante', () => {
  const ficheFields = {
    ond_ac_kw: '10', ond_phases: '3', ond_n_mppt: '2',
    ond_mppt_v_min: '200', ond_mppt_v_max: '650', ond_v_max_abs: '800',
    ond_i_max_mppt_a: '26', ond_rendement_euro_pct: '97',
  }
  const manquantes = manquantesOnduleurLocal({
    ficheFields, garantieTexte: 'Garantie constructeur 10 ans',
    plageBatterieAbsente: false,
  })
  assert.deepEqual(manquantes, [])
})

test('mirroir exact du test backend synthétique (une seule variable manquante : courant maxi MPPT)', () => {
  // Même fixture que test_le_verrou_refuse_encore_un_incomplet_non_declare
  // (apps/ventes/tests/test_pvond_contrat_onduleur.py) : tout est renseigné
  // SAUF ond_i_max_mppt_a.
  const ficheFields = {
    ond_ac_kw: '8', ond_phases: '1', ond_n_mppt: '2',
    ond_mppt_v_min: '200', ond_mppt_v_max: '650', ond_v_max_abs: '800',
    ond_i_max_mppt_a: '', ond_rendement_euro_pct: '97',
  }
  const manquantes = manquantesOnduleurLocal({
    ficheFields, garantieTexte: 'Garantie constructeur 10 ans',
    plageBatterieAbsente: false,
  })
  assert.deepEqual(manquantes, ['courant maxi par MPPT (A)'])
})

test('rien de renseigné → les 10 variables manquent, dans l\'ordre du contrat', () => {
  const manquantes = manquantesOnduleurLocal({
    ficheFields: {}, garantieTexte: '', plageBatterieAbsente: true,
  })
  assert.deepEqual(manquantes, CONTRAT_ONDULEUR_FR.map(([, libelle]) => libelle))
})

test('la garantie et la plage batterie sont vérifiées hors FicheTechnique', () => {
  const complet = {
    ond_ac_kw: '10', ond_phases: '3', ond_n_mppt: '2',
    ond_mppt_v_min: '200', ond_mppt_v_max: '650', ond_v_max_abs: '800',
    ond_i_max_mppt_a: '26', ond_rendement_euro_pct: '97',
  }
  assert.deepEqual(
    manquantesOnduleurLocal({ ficheFields: complet, garantieTexte: '', plageBatterieAbsente: false }),
    ['garantie constructeur'])
  assert.deepEqual(
    manquantesOnduleurLocal({ ficheFields: complet, garantieTexte: 'Garantie 10 ans', plageBatterieAbsente: true }),
    ['plage de tension batterie (V)'])
})

// ── Mapping type client → type_fiche backend + conversion payload ──────────
test('typeFicheBackend mappe hybride/réseau → onduleur, panneau → module', () => {
  assert.equal(typeFicheBackend('onduleur_hybride'), 'onduleur')
  assert.equal(typeFicheBackend('onduleur_reseau'), 'onduleur')
  assert.equal(typeFicheBackend('panneau'), 'module')
  assert.equal(typeFicheBackend('batterie'), 'batterie')
  assert.equal(typeFicheBackend(null), null)
  assert.equal(typeFicheBackend('structure'), null)
})

test('ficheFieldsVides part de chaînes vides pour tous les champs connus', () => {
  const vide = ficheFieldsVides()
  assert.equal(vide.ond_ac_kw, '')
  assert.equal(vide.pmax_wc, '')
  assert.equal(vide.bat_kwh_nominal, '')
  // PVOND-H — nouveaux champs onduleur/panneau, mêmes garanties.
  assert.equal(vide.ond_v_demarrage_v, '')
  assert.equal(vide.ond_isc_max_mppt_a, '')
  assert.equal(vide.ond_bat_v_min, '')
  assert.equal(vide.ond_bat_v_max, '')
  assert.equal(vide.voc_v, '')
  assert.equal(vide.isc_a, '')
  assert.equal(vide.vmp_v, '')
  assert.equal(vide.imp_a, '')
  assert.equal(vide.temp_coeff_voc_pct_c, '')
  assert.equal(vide.temp_coeff_pmax_pct_c, '')
  // Le seul champ booléen part à `false`, jamais une chaîne vide.
  assert.equal(vide.ond_bat_aucune, false)
})

test('champsFicheDepuisServeur convertit nombres/absences en chaînes', () => {
  const out = champsFicheDepuisServeur({
    ond_ac_kw: '10.00', ond_phases: 3, ond_n_mppt: null,
  })
  assert.equal(out.ond_ac_kw, '10.00')
  assert.equal(out.ond_phases, '3')
  assert.equal(out.ond_n_mppt, '')
  // Un champ jamais mentionné par la fiche reste vide, pas `undefined`.
  assert.equal(out.pmax_wc, '')
})

test('champsFicheDepuisServeur(null) renvoie l\'état vide (nouveau produit)', () => {
  assert.deepEqual(champsFicheDepuisServeur(null), ficheFieldsVides())
})

test('champsFicheDepuisServeur convertit ond_bat_aucune en booléen (jamais une chaîne)', () => {
  assert.equal(champsFicheDepuisServeur({ ond_bat_aucune: true }).ond_bat_aucune, true)
  assert.equal(champsFicheDepuisServeur({ ond_bat_aucune: false }).ond_bat_aucune, false)
  // Fiche jamais enregistrée pour ce champ → repli `false`, jamais `null`/`undefined`.
  assert.equal(champsFicheDepuisServeur({ ond_ac_kw: '10' }).ond_bat_aucune, false)
})

test('champsFichePourType ne garde que les champs du type, en nombres', () => {
  const payload = champsFichePourType('onduleur_hybride', {
    ond_ac_kw: '10', ond_phases: '3', ond_n_mppt: '', pmax_wc: '710',
  })
  assert.deepEqual(payload, {
    ond_ac_kw: 10, ond_phases: 3, ond_n_mppt: null,
    ond_mppt_v_min: null, ond_mppt_v_max: null, ond_v_max_abs: null,
    ond_i_max_mppt_a: null, ond_rendement_euro_pct: null,
    // PVOND-H — nouveaux champs numériques du bloc onduleur.
    ond_v_demarrage_v: null, ond_isc_max_mppt_a: null,
    ond_bat_v_min: null, ond_bat_v_max: null,
    // CALX355 — bloc « rendement onduleur » : vides → null, courbe → null.
    ond_rendement_max_pct: null, ond_rendement_cec_pct: null,
    // Champ booléen du bloc onduleur : converti en `false`, jamais `null`.
    ond_bat_aucune: false,
    ond_courbe_rendement: null,
  })
  // pmax_wc n'appartient pas au bloc onduleur : jamais dans ce payload.
  assert.ok(!('pmax_wc' in payload))
})

// PVOND-H — la plage de tension batterie déclarée « aucune » (onduleur
// réseau) doit ressortir à `true`, pas à un nombre ou `null`.
test('champsFichePourType(onduleur) convertit ond_bat_aucune en booléen, jamais en nombre', () => {
  const payload = champsFichePourType('onduleur_reseau', { ond_bat_aucune: true })
  assert.equal(payload.ond_bat_aucune, true)
  assert.equal(champsFichePourType('onduleur_reseau', { ond_bat_aucune: false }).ond_bat_aucune, false)
  assert.equal(champsFichePourType('onduleur_reseau', {}).ond_bat_aucune, false)
})

test('champsFichePourType(panneau) garde puissance, électrique complet et dimensions', () => {
  assert.deepEqual(champsFichePourType('panneau', {
    pmax_wc: '710', voc_v: '48.3', isc_a: '18.59', vmp_v: '40.4', imp_a: '17.59',
    temp_coeff_voc_pct_c: '-0.25', temp_coeff_pmax_pct_c: '-0.29',
    longueur_mm: '2384', largeur_mm: '1303',
  }), {
    pmax_wc: 710, voc_v: 48.3, isc_a: 18.59, vmp_v: 40.4, imp_a: 17.59,
    temp_coeff_voc_pct_c: -0.25, temp_coeff_pmax_pct_c: -0.29,
    longueur_mm: 2384, largeur_mm: 1303,
    // CALX355 — non saisis : `null`, jamais 0 ; courbe absente : `null`.
    noct_c: null, bifacialite_pct: null,
    tolerance_pmax_min_pct: null, tolerance_pmax_max_pct: null,
    rendement_par_irradiance: null,
  })
})

test('champsFichePourType(batterie) garde capacité/tension/DoD/max-modules', () => {
  assert.deepEqual(
    champsFichePourType('batterie', {
      bat_kwh_nominal: '5.12', bat_kwh_usable: '4.6', bat_v_nominal: '51.2', bat_dod_pct: '90',
      bat_max_modules_par_banc: '200',
    }),
    { bat_kwh_nominal: 5.12, bat_kwh_usable: 4.6, bat_v_nominal: 51.2, bat_dod_pct: 90,
      bat_max_modules_par_banc: 200,
      // CALX355 — non saisis : `null` ; la chimie (CharField) part à ''.
      bat_c_rate_charge: null, bat_c_rate_decharge: null,
      bat_temp_min_c: null, bat_temp_max_c: null, bat_chimie: '' })
})

// BATHOMO (fondateur 26/08/2026) — « add it as parameter... for now keep it
// very high for 5kwh — maybe 200 ». Vide = illimité (jamais 0, jamais un
// défaut inventé) : ce test épingle le repli ``null`` que
// ``composition_residentielle`` lit comme « aucun plafond ».
test('champsFichePourType(batterie) : max-modules vide → null (illimité)', () => {
  assert.equal(
    champsFichePourType('batterie', { bat_max_modules_par_banc: '' })
      .bat_max_modules_par_banc,
    null)
})

test('champsFichePourType(structure) : type sans bloc FicheTechnique → objet vide', () => {
  assert.deepEqual(champsFichePourType('structure', { ond_ac_kw: '10' }), {})
})

test('une valeur non numérique devient null plutôt que NaN', () => {
  const payload = champsFichePourType('onduleur_hybride', { ond_ac_kw: 'abc' })
  assert.equal(payload.ond_ac_kw, null)
})

// ── PVFCH (fondateur 20/08/2026) — AFFICHAGE de la fiche structurée ─────────
// « i am expecting a fiche produit that includes all the data separately,
// that I can change — number of MPPT, range of each MPPT, battery voltage… »
// Le visualiseur produit (ProduitDetail) lit ces fonctions ; elles garantissent
// qu'un champ VIDE se voit comme un trou, jamais comme une valeur.

test('groupeFicheAffichage(onduleur) : les 15 variables, dans l’ordre du formulaire', () => {
  const groupe = groupeFicheAffichage({ type_fiche: 'onduleur', ond_n_mppt: 2 })
  assert.equal(groupe.type, 'onduleur')
  assert.equal(groupe.titre, 'Onduleur')
  assert.deepEqual(groupe.lignes.map((l) => l.cle), [
    'ond_ac_kw', 'ond_phases', 'ond_n_mppt', 'ond_mppt_v_min',
    'ond_mppt_v_max', 'ond_v_max_abs', 'ond_i_max_mppt_a',
    'ond_rendement_euro_pct', 'ond_v_demarrage_v', 'ond_isc_max_mppt_a',
    'ond_bat_v_min', 'ond_bat_v_max',
    // CALX355 — bloc « rendement onduleur ».
    'ond_rendement_max_pct', 'ond_rendement_cec_pct', 'ond_courbe_rendement',
  ])
  // Les trois variables que le fondateur a nommées sont bien SÉPARÉES.
  const parCle = Object.fromEntries(groupe.lignes.map((l) => [l.cle, l]))
  assert.equal(parCle.ond_n_mppt.valeur, '2')
  assert.equal(parCle.ond_n_mppt.libelle, "Nombre d'entrées MPPT")
  assert.equal(parCle.ond_mppt_v_min.libelle, 'Plage MPPT — tension mini (V)')
  assert.equal(parCle.ond_bat_v_min.libelle, 'Plage batterie — tension mini (V)')
})

test('un champ non renseigné affiche « à renseigner », JAMAIS un défaut ni un zéro', () => {
  const groupe = groupeFicheAffichage({ type_fiche: 'onduleur', ond_n_mppt: 2 })
  const vides = groupe.lignes.filter((l) => l.absente)
  assert.equal(vides.length, 14)
  for (const ligne of vides) assert.equal(ligne.valeur, VALEUR_ABSENTE)
  // La règle « never invent numbers » à l'écran : aucune valeur de repli.
  assert.equal(valeurFicheAffichee('ond_v_max_abs', { type_fiche: 'onduleur' }),
               VALEUR_ABSENTE)
  assert.equal(valeurFicheAffichee('ond_mppt_v_min', null), VALEUR_ABSENTE)
})

test('un zéro RÉEL reste affiché (0 est une valeur, pas une absence)', () => {
  assert.equal(valeurFicheAffichee('ond_v_demarrage_v',
    { type_fiche: 'onduleur', ond_v_demarrage_v: 0 }), '0')
})

test('les phases se lisent en toutes lettres — un nombre nu ne se lit pas', () => {
  assert.equal(valeurFicheAffichee('ond_phases', { ond_phases: 1 }), 'Monophasé')
  assert.equal(valeurFicheAffichee('ond_phases', { ond_phases: 3 }), 'Triphasé')
  assert.equal(valeurFicheAffichee('ond_phases', {}), VALEUR_ABSENTE)
})

test('« aucune batterie » se DIT, au lieu de laisser croire à un oubli', () => {
  const fiche = { type_fiche: 'onduleur', ond_bat_aucune: true }
  assert.equal(valeurFicheAffichee('ond_bat_v_min', fiche),
               'Aucune batterie compatible')
  assert.equal(valeurFicheAffichee('ond_bat_v_max', fiche),
               'Aucune batterie compatible')
  // …et une plage réellement déclarée s'affiche telle quelle.
  assert.equal(valeurFicheAffichee('ond_bat_v_min',
    { type_fiche: 'onduleur', ond_bat_v_min: 40 }), '40')
})

test('groupeFicheAffichage(module/batterie) : leurs propres blocs', () => {
  const mod = groupeFicheAffichage({ type_fiche: 'module', pmax_wc: '710.00' })
  assert.equal(mod.titre, 'Panneau photovoltaïque')
  assert.equal(mod.lignes[0].valeur, '710.00')
  assert.equal(mod.lignes[0].libelle, 'Puissance crête (Wc)')
  assert.deepEqual(mod.lignes.map((l) => l.cle), [
    'pmax_wc', 'voc_v', 'isc_a', 'vmp_v', 'imp_a',
    'temp_coeff_voc_pct_c', 'temp_coeff_pmax_pct_c',
    'longueur_mm', 'largeur_mm',
    // CALX355
    'noct_c', 'bifacialite_pct', 'tolerance_pmax_min_pct',
    'tolerance_pmax_max_pct', 'rendement_par_irradiance'])

  const bat = groupeFicheAffichage({ type_fiche: 'batterie', bat_v_nominal: '51.2' })
  assert.equal(bat.titre, 'Batterie')
  assert.equal(bat.lignes.find((l) => l.cle === 'bat_v_nominal').valeur, '51.2')
})

test('produit sans fiche (ou type inconnu) → rien à afficher, jamais un bloc vide', () => {
  assert.equal(groupeFicheAffichage(null), null)
  assert.equal(groupeFicheAffichage(undefined), null)
  assert.equal(groupeFicheAffichage({ type_fiche: '' }), null)
  assert.equal(groupeFicheAffichage({ type_fiche: 'autre' }), null)
})

test('tout champ éditable du formulaire porte un libellé d’affichage', () => {
  // Sans ça, le visualiseur montrerait une clé technique (`ond_v_max_abs`) là
  // où le formulaire montre « Tension DC maximale (V) ».
  for (const type of ['onduleur', 'module', 'batterie', 'optimiseur']) {
    for (const ligne of groupeFicheAffichage({ type_fiche: type }).lignes) {
      assert.equal(typeof LIBELLES_FICHE[ligne.cle], 'string',
                   `libellé manquant pour ${ligne.cle}`)
      assert.notEqual(ligne.libelle, ligne.cle)
    }
  }
})

// ── CALX355 — les nouveaux champs de fiche, saisissables ───────────────────
// Parité PV*SOL (dialogue de création par champ, modèle de charge partielle
// inclus). Règle absolue : un champ VIDE reste vide — jamais envoyé à 0.

test('CALX355 — un champ vide n’est JAMAIS envoyé à 0 (tous les blocs)', () => {
  const blocs = {
    onduleur_reseau: ['ond_rendement_max_pct', 'ond_rendement_cec_pct'],
    panneau: ['noct_c', 'bifacialite_pct', 'tolerance_pmax_min_pct', 'tolerance_pmax_max_pct'],
    batterie: ['bat_c_rate_charge', 'bat_c_rate_decharge', 'bat_temp_min_c', 'bat_temp_max_c'],
    optimiseur: ['opt_ac_kw', 'opt_ac_tension_v', 'opt_ac_i_max_a',
      'opt_ac_unites_max_par_branche', 'opt_v_out_nominal_v', 'opt_v_out_min',
      'opt_v_out_max', 'opt_i_out_max_a', 'opt_pmax_out_w', 'opt_modules_max_par_chaine'],
  }
  for (const [type, cles] of Object.entries(blocs)) {
    const vides = Object.fromEntries(cles.map((c) => [c, '']))
    const payload = champsFichePourType(type, vides)
    for (const cle of cles) {
      assert.equal(payload[cle], null, `${type}.${cle} vide doit partir à null`)
      assert.notEqual(payload[cle], 0)
    }
  }
})

test('CALX355 — les champs saisis partent en nombres (négatifs admis : tolérance, température)', () => {
  const mod = champsFichePourType('panneau', {
    noct_c: '43', bifacialite_pct: '80', tolerance_pmax_min_pct: '-3', tolerance_pmax_max_pct: '3',
  })
  assert.equal(mod.noct_c, 43)
  assert.equal(mod.bifacialite_pct, 80)
  assert.equal(mod.tolerance_pmax_min_pct, -3)
  assert.equal(mod.tolerance_pmax_max_pct, 3)
  const bat = champsFichePourType('batterie', {
    bat_c_rate_charge: '0.5', bat_c_rate_decharge: '1', bat_temp_min_c: '-10',
    bat_temp_max_c: '50', bat_chimie: 'lfp',
  })
  assert.deepEqual(
    [bat.bat_c_rate_charge, bat.bat_c_rate_decharge, bat.bat_temp_min_c, bat.bat_temp_max_c, bat.bat_chimie],
    [0.5, 1, -10, 50, 'lfp'])
  const ond = champsFichePourType('onduleur_hybride', {
    ond_rendement_max_pct: '98.4', ond_rendement_cec_pct: '97.5',
  })
  assert.equal(ond.ond_rendement_max_pct, 98.4)
  assert.equal(ond.ond_rendement_cec_pct, 97.5)
})

test('CALX355 — la chimie : vide → \'\' (jamais null), valeurs = miroir du backend', () => {
  assert.equal(champsFichePourType('batterie', { bat_chimie: '' }).bat_chimie, '')
  assert.equal(champsFichePourType('batterie', {}).bat_chimie, '')
  assert.deepEqual(CHOIX_CHIMIE_BATTERIE.map(([v]) => v), [
    'lfp', 'nmc', 'nca', 'lmo', 'lto', 'plomb_ouvert', 'plomb_agm', 'plomb_gel', 'autre'])
  assert.equal(valeurFicheAffichee('bat_chimie', { bat_chimie: 'lfp' }), 'LFP (lithium fer phosphate)')
  assert.equal(valeurFicheAffichee('bat_chimie', { bat_chimie: '' }), VALEUR_ABSENTE)
})

test('CALX355 — le bloc optimiseur n’appartient qu’au type optimiseur', () => {
  const payload = champsFichePourType('optimiseur', { opt_ac_kw: '0.365', ond_ac_kw: '10' })
  assert.equal(payload.opt_ac_kw, 0.365)
  assert.ok(!('ond_ac_kw' in payload))
  assert.equal(typeFicheBackend('optimiseur'), 'optimiseur')
  const groupe = groupeFicheAffichage({ type_fiche: 'optimiseur', opt_ac_kw: '0.365' })
  assert.equal(groupe.titre, 'Optimiseur / micro-onduleur')
  assert.equal(groupe.lignes[0].valeur, '0.365')
})

test('CALX355 — l’optimiseur se reconnaît quand classifyProduct ne dit rien, jamais par-dessus lui', () => {
  assert.equal(estOptimiseurNom('Optimiseur SolarEdge S440'), true)
  assert.equal(estOptimiseurNom('Micro-onduleur Hoymiles HMS-800'), true)
  assert.equal(estOptimiseurNom('Micro onduleur APsystems'), true)
  assert.equal(estOptimiseurNom('Tigo optimizer TS4'), true)
  assert.equal(estOptimiseurNom('Onduleur hybride Deye 8kW'), false)
  assert.equal(estOptimiseurNom(''), false)
  // Un produit déjà classé garde SA famille (source unique du générateur).
  assert.equal(typeFicheFormulaire({ typeClient: 'onduleur_reseau', nom: 'Micro-onduleur réseau X' }),
               'onduleur_reseau')
  assert.equal(typeFicheFormulaire({ typeClient: null, nom: 'Micro-onduleur Hoymiles' }), 'optimiseur')
  // Une fiche déjà typée « optimiseur » garde son bloc, quel que soit le nom.
  assert.equal(typeFicheFormulaire({ typeClient: null, nom: 'Article 42', typeFicheServeur: 'optimiseur' }),
               'optimiseur')
  assert.equal(typeFicheFormulaire({ typeClient: null, nom: 'Vis inox M8' }), null)
})

test('CALX355 — état vide : choix à \'\', courbes sans aucune ligne', () => {
  const vide = ficheFieldsVides()
  assert.equal(vide.bat_chimie, '')
  assert.deepEqual(vide.rendement_par_irradiance, [])
  assert.deepEqual(vide.ond_courbe_rendement, [])
  assert.equal(vide.noct_c, '')
  assert.equal(vide.opt_ac_kw, '')
})

test('CALX355 — courbe : aller-retour serveur → lignes → points identique', () => {
  const serveur = [
    { w_m2: 200, rendement_relatif_pct: 96.5 },
    { w_m2: 400, rendement_relatif_pct: 98.8 },
    { w_m2: 1000, rendement_relatif_pct: 100 },
  ]
  const etat = champsFicheDepuisServeur({ type_fiche: 'module', rendement_par_irradiance: serveur })
  assert.deepEqual(etat.rendement_par_irradiance[0], { w_m2: '200', rendement_relatif_pct: '96.5' })
  assert.deepEqual(champsFichePourType('panneau', etat).rendement_par_irradiance, serveur)
  assert.deepEqual(lignesCourbeDepuisServeur('rendement_par_irradiance', null), [])
})

test('CALX355 — courbe sans aucune ligne (ou lignes vierges) → null, jamais []', () => {
  assert.equal(validerCourbe('rendement_par_irradiance', []).points, null)
  const vierges = [ligneCourbeVide('rendement_par_irradiance'), ligneCourbeVide('rendement_par_irradiance')]
  const r = validerCourbe('rendement_par_irradiance', vierges)
  assert.equal(r.points, null)
  assert.deepEqual(r.erreurs, [null, null])
})

test('CALX355 — chaque ligne nomme son erreur sous la cellule fautive', () => {
  const r = validerCourbe('rendement_par_irradiance', [
    { w_m2: '200', rendement_relatif_pct: '96' },
    { w_m2: '400', rendement_relatif_pct: '' },       // cellule requise vide
    { w_m2: 'abc', rendement_relatif_pct: '99' },     // pas un nombre
    { w_m2: '150', rendement_relatif_pct: '97' },     // abscisse qui recule
  ])
  assert.equal(r.erreurs[0], null)
  assert.deepEqual(Object.keys(r.erreurs[1]), ['rendement_relatif_pct'])
  assert.match(r.erreurs[1].rendement_relatif_pct, /Valeur requise/)
  assert.deepEqual(Object.keys(r.erreurs[2]), ['w_m2'])
  assert.match(r.erreurs[2].w_m2, /Nombre attendu/)
  assert.deepEqual(Object.keys(r.erreurs[3]), ['w_m2'])
  assert.match(r.erreurs[3].w_m2, /Doit dépasser 200 \(point 1\)/)
  // Seules les lignes correctes deviennent des points.
  assert.deepEqual(r.points, [{ w_m2: 200, rendement_relatif_pct: 96 }])
})

test('CALX355 — abscisse répétée refusée, virgule décimale normalisée', () => {
  const r = validerCourbe('rendement_par_irradiance', [
    { w_m2: '200', rendement_relatif_pct: '96,5' },
    { w_m2: '200', rendement_relatif_pct: '97' },
  ])
  assert.equal(r.erreurs[0], null)
  assert.match(r.erreurs[1].w_m2, /ne se répète pas/)
  assert.deepEqual(r.points, [{ w_m2: 200, rendement_relatif_pct: 96.5 }])
})

test('CALX355 — onduleur : une courbe PAR tension, croissance exigée dans chaque série', () => {
  const r = validerCourbe('ond_courbe_rendement', [
    { charge_pct: '10', rendement_pct: '95', tension_v: '360' },
    { charge_pct: '50', rendement_pct: '98', tension_v: '360' },
    { charge_pct: '10', rendement_pct: '94', tension_v: '600' },  // nouvelle série : OK
    { charge_pct: '30', rendement_pct: '97', tension_v: '' },     // tension facultative
  ])
  assert.deepEqual(r.erreurs, [null, null, null, null])
  assert.deepEqual(r.points[3], { charge_pct: 30, rendement_pct: 97 })
  assert.ok(!('tension_v' in r.points[3]))
  const recul = validerCourbe('ond_courbe_rendement', [
    { charge_pct: '50', rendement_pct: '98', tension_v: '360' },
    { charge_pct: '20', rendement_pct: '96', tension_v: '360' },
  ])
  assert.match(recul.erreurs[1].charge_pct, /Doit dépasser 50 \(point 1\)/)
})

test('CALX355 — le bandeau nomme la courbe, le point et la colonne fautifs', () => {
  const { parCourbe, bandeau } = erreursCourbesPourType('module', {
    rendement_par_irradiance: [
      { w_m2: '200', rendement_relatif_pct: '96' },
      { w_m2: '', rendement_relatif_pct: '97' },
    ],
  })
  assert.ok(parCourbe.rendement_par_irradiance)
  assert.match(bandeau, /Courbe rendement \/ irradiance/)
  assert.match(bandeau, /point 2/)
  assert.match(bandeau, /Irradiance \(W\/m²\)/)
  // Aucune erreur → rien à signaler.
  assert.deepEqual(erreursCourbesPourType('module', { rendement_par_irradiance: [] }),
                   { parCourbe: {}, bandeau: null })
  assert.deepEqual(erreursCourbesPourType('batterie', {}), { parCourbe: {}, bandeau: null })
})

test('CALX355 — une courbe s’affiche par son nombre de points', () => {
  assert.equal(valeurFicheAffichee('rendement_par_irradiance',
    { rendement_par_irradiance: [{ w_m2: 200, rendement_relatif_pct: 96 }] }), '1 point')
  assert.equal(valeurFicheAffichee('ond_courbe_rendement',
    { ond_courbe_rendement: [{}, {}] }), '2 points')
  assert.equal(valeurFicheAffichee('ond_courbe_rendement', { ond_courbe_rendement: [] }), VALEUR_ABSENTE)
  assert.equal(valeurFicheAffichee('ond_courbe_rendement', {}), VALEUR_ABSENTE)
  assert.equal(COURBES_FICHE.ond_courbe_rendement.colonnes.at(-1).requise, false)
})

test('CALX355 — le refus serveur nomme le champ par son libellé d’écran', () => {
  assert.equal(
    messageRefusFiche({ bat_c_rate_charge: ['Assurez-vous que cette valeur est supérieure ou égale à 0.01.'] }),
    '« C-rate de charge (C) » : Assurez-vous que cette valeur est supérieure ou égale à 0.01.')
  assert.equal(messageRefusFiche({ detail: 'Refusé.' }), 'Refusé.')
  assert.equal(messageRefusFiche(null), null)
  assert.equal(messageRefusFiche({}), null)
})
