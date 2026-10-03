"""AGR201-AGR205 — le moteur PUR ``economie_pompage`` (économie DÉCLARÉE).

Tous les cas sont des ``SimpleTestCase`` : le module est PUR (une requête en
base lèverait ici), et chaque valeur attendue est recalculée À LA MAIN dans le
test, jamais recopiée d'une sortie du moteur.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_agr_economie_pompage -v 2
"""
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes import economie_pompage as E
from apps.ventes.economie import EconomieInvalide


def _saisie(valeur, date='2026-09-12'):
    return {'valeur': valeur, 'saisi_le': date}


def _energie(valeur, date='2026-09-12'):
    return {'valeur': valeur,
            'provenance': {'origine': 'saisie', 'detail': None, 'date': date}}


def _mois(mois, origine='saisie', detail=None):
    return {'mois': list(mois),
            'provenance': {'origine': origine, 'detail': detail,
                           'date': '2026-09-12'}}


def saisies_carburant(*, energie='butane', quantite=2, unite='bouteille_12kg',
                      periode='jour_irrigation', jours=3, prix=50.0,
                      mois=(6, 7), entretien=None):
    s = {
        'energie_actuelle': _energie(energie),
        'consommation': {'quantite': quantite, 'unite': unite,
                         'periode': periode,
                         'jours_irrigation_par_semaine': jours,
                         'saisi_le': '2026-09-12'},
        'depense_unitaire_payee': (None if prix is None else _saisie(prix)),
        'mois_irrigation': _mois(mois),
        'coherence_confirmee': False,
    }
    if entretien is not None:
        s['entretien_paye_mad_an'] = _saisie(entretien)
    return s


class DepenseActuelleTests(SimpleTestCase):
    """AGR201 — la dépense ACTUELLE vient des chiffres déclarés, jamais × 12."""

    def test_bouteilles_par_jour_d_irrigation_au_centime(self):
        dep = E.depense_actuelle(saisies_carburant())
        attendu = (2 * 3 * 30 / 7 + 2 * 3 * 31 / 7) * 50
        self.assertEqual(dep['statut'], 'calcule')
        self.assertEqual(dep['cas'], E.CAS_CARBURANT)
        self.assertEqual(dep['depense_actuelle']['annuelle_mad'],
                         round(attendu, 2))
        par_mois = dep['depense_actuelle']['par_mois']
        self.assertEqual(par_mois[5], round(2 * 3 * 30 / 7 * 50, 2))
        self.assertEqual(par_mois[6], round(2 * 3 * 31 / 7 * 50, 2))
        self.assertEqual(sum(1 for v in par_mois if v), 2)

    def test_par_mois_sur_quatre_mois_vaut_8000_jamais_24000(self):
        # 40 L/mois × 50 MAD = 2 000 MAD par mois coché.
        dep = E.depense_actuelle(saisies_carburant(
            energie='diesel', quantite=40, unite='litre', periode='mois',
            jours=None, prix=50.0, mois=(5, 6, 7, 8)))
        self.assertEqual(dep['depense_actuelle']['annuelle_mad'], 8000.0)
        self.assertNotEqual(dep['depense_actuelle']['annuelle_mad'], 24000.0)

    def test_par_semaine(self):
        dep = E.depense_actuelle(saisies_carburant(
            energie='diesel', quantite=70, unite='litre', periode='semaine',
            jours=None, prix=10.0, mois=(2,)))
        self.assertEqual(dep['depense_actuelle']['annuelle_mad'],
                         round(70 * 28 / 7 * 10, 2))

    def test_facture_bimestrielle_moins_part_fixe(self):
        dep = E.depense_actuelle({
            'energie_actuelle': _energie('electrique'),
            'facture_reseau': {'montant_mad': 1200,
                               'periodicite': 'bimestrielle',
                               'part_fixe_mad_mois': 50,
                               'saisi_le': '2026-09-12'},
            'mois_irrigation': _mois((6, 7, 8)),
        })
        self.assertEqual(dep['cas'], E.CAS_RESEAU)
        self.assertEqual(dep['depense_actuelle']['annuelle_mad'],
                         (600 - 50) * 3)

    def test_facture_sans_part_fixe_est_omise_et_nommee(self):
        dep = E.depense_actuelle({
            'energie_actuelle': _energie('electrique'),
            'facture_reseau': {'montant_mad': 1200,
                               'periodicite': 'mensuelle',
                               'saisi_le': '2026-09-12'},
            'mois_irrigation': _mois((6,)),
        })
        self.assertEqual(dep['statut'], 'omis')
        self.assertTrue(any('part fixe' in m for m in dep['motifs']))

    def test_entretien_paye_declare_s_ajoute(self):
        dep = E.depense_actuelle(saisies_carburant(entretien=1500))
        attendu = (2 * 3 * 30 / 7 + 2 * 3 * 31 / 7) * 50 + 1500
        self.assertEqual(dep['depense_actuelle']['annuelle_mad'],
                         round(attendu, 2))
        self.assertEqual(dep['depense_actuelle']['entretien_mad_an'], 1500)

    def test_aucune_energie_est_un_nouveau_forage_sans_depense(self):
        dep = E.depense_actuelle({'energie_actuelle': _energie('aucune')})
        self.assertEqual(dep['cas'], E.CAS_NOUVEAU_FORAGE)
        self.assertIsNone(dep['depense_actuelle'])

    def test_prix_absent_omis_avec_motif_nomme(self):
        dep = E.depense_actuelle(saisies_carburant(prix=None))
        self.assertEqual(dep['statut'], 'omis')
        self.assertIn('prix payé non déclaré', dep['motifs'])
        self.assertIsNone(dep['depense_actuelle'])

    def test_jours_d_irrigation_manquants_pour_une_periode_journaliere(self):
        dep = E.depense_actuelle(saisies_carburant(jours=None))
        self.assertEqual(dep['statut'], 'omis')
        self.assertIn("jours d'irrigation par semaine non déclarés",
                      dep['motifs'])

    def test_rien_declare_nomme_les_quatre_saisies(self):
        bloc = E.economie_pompage({})
        self.assertEqual(bloc['statut'], 'omis')
        self.assertFalse(bloc['publiable_client'])
        self.assertIsNone(bloc['cas'])
        self.assertEqual(bloc['motifs_non_publiable'], [
            'énergie actuelle non déclarée', 'consommation non déclarée',
            'prix payé non déclaré', "mois d'irrigation non déclarés"])

    def test_aucun_prix_n_est_pre_rempli(self):
        """Q17 : une énergie sans prix ne reçoit JAMAIS de prix de repli."""
        dep = E.depense_actuelle(saisies_carburant(prix=None))
        self.assertIsNone(dep['valeur_unitaire'])

    def test_une_saisie_invalide_est_refusee_en_nommant_le_champ(self):
        with self.assertRaises(EconomieInvalide) as ctx:
            E.depense_actuelle(saisies_carburant(quantite=-1))
        self.assertEqual(ctx.exception.champ, 'consommation.quantite')

    def test_entrees_declarees_et_mention(self):
        dep = E.depense_actuelle(saisies_carburant())
        cles = [e['cle'] for e in dep['entrees_declarees']]
        self.assertEqual(cles, [
            'energie_actuelle', 'consommation', 'jours_irrigation_par_semaine',
            'depense_unitaire_payee', 'mois_irrigation'])
        self.assertEqual(E.mention_declaration(dep['entrees_declarees'][1]),
                         'déclaré par le client le 12/09')

    def test_mois_du_calendrier_de_culture_publies_comme_tels(self):
        s = saisies_carburant()
        s['mois_irrigation'] = _mois((6, 7), origine='calculee',
                                     detail='calendrier_culture')
        dep = E.depense_actuelle(s)
        entree = [e for e in dep['entrees_declarees']
                  if e['cle'] == 'mois_irrigation'][0]
        self.assertEqual(entree['provenance']['detail'], 'calendrier_culture')
        self.assertEqual(E.mention_declaration(entree),
                         'pré-cochés selon le calendrier de culture')

    def test_l_ancienne_cle_fuel_spend_current_n_est_jamais_lue(self):
        source = Path(E.__file__).read_text(encoding='utf-8')
        for interdit in ("'fuel_spend_current'", 'force_motrice'):
            self.assertFalse(interdit in source, interdit)

    def test_module_pur_sans_modele(self):
        source = Path(E.__file__).read_text(encoding='utf-8')
        for interdit in ('.objects', 'import models', 'prix_achat'):
            self.assertFalse(interdit in source, interdit)


# ── AGR202 ──────────────────────────────────────────────────────────────────

CHARGES = {'charges_pompage_solaire': [
    {'libelle': 'Nettoyage des panneaux et visite annuelle',
     'montant_mad_an': 600.0, 'source': 'barème société'}]}
REGLE_FDA = {'regle_fda_pompage': {
    'taux_pct': 30, 'plafond_mad_par_ha': 3000, 'plafond_mad_par_kwc': 3000,
    'plafond_mad_par_projet': 30000, 'base': 'ttc',
    'source': 'Guide FDA édition 2024, p.20-23', 'releve_le': '2026-10-02'}}


def ligne(designation, pu, *, tva=0, quantite=1, type_equipement=None,
          role=None, garantie=None, optionnelle=False):
    return {'designation': designation, 'quantite': quantite,
            'prix_unitaire': pu, 'remise': 0, 'taux_tva': tva,
            'optionnelle': optionnelle, 'type_ligne': 'produit',
            'type_equipement': type_equipement, 'role_pompage': role,
            'garantie_mois': garantie}


def lignes_reference(*, garantie_variateur=None, tva_panneaux=20):
    """Investissement 50 000 TTC : pompe 8 000 TTC + 42 000 TTC autres."""
    lignes = [
        ligne('Pompe immergée', 8000, type_equipement='pompe'),
        ligne('Panneaux', 35000, tva=tva_panneaux),
    ]
    if garantie_variateur is not None:
        lignes[1] = ligne('Panneaux', 30000, tva=tva_panneaux)
        lignes.append(ligne('Variateur', 6000, role='variateur_pompage',
                            garantie=garantie_variateur))
    return lignes


def saisies_12000():
    """Diesel : 100 L par mois × 10 MAD × 12 mois = 12 000 MAD/an."""
    return saisies_carburant(energie='diesel', quantite=100, unite='litre',
                             periode='mois', jours=None, prix=10.0,
                             mois=range(1, 13))


ETUDE_COUVERTE = {'couverture_pct_mois': [120] * 12,
                  'pompe': {'mode': 'neuve'}}


class FluxPompageTests(SimpleTestCase):
    """AGR202 — charges, remplacements au TTC réel, flux 10 ans, retour sans
    aide, par ``economie.flux_de_tresorerie``."""

    def bloc(self, **kw):
        kw.setdefault('sortie_etude', ETUDE_COUVERTE)
        kw.setdefault('lignes', lignes_reference())
        kw.setdefault('reglages', CHARGES)
        return E.economie_pompage(kw.pop('saisies', saisies_12000()), **kw)

    def test_cas_de_reference_recalcule_a_la_main(self):
        bloc = self.bloc()
        eco = bloc['economie']
        flux = [-50000.0] + [12000.0 - 600.0] * 10
        flux[7] -= 8000.0
        cumul, cumuls = 0.0, []
        for f in flux:
            cumul += f
            cumuls.append(cumul)
        retour = next(a for a, c in enumerate(cumuls) if c >= 0)
        self.assertEqual(eco['horizon_ans'], 10)
        self.assertEqual([lg['flux_mad'] for lg in eco['flux']],
                         [round(f, 2) for f in flux])
        self.assertEqual([lg['cumul_mad'] for lg in eco['flux']],
                         [round(c, 2) for c in cumuls])
        self.assertEqual(eco['retour_ans'], retour)
        self.assertEqual(retour, 5)
        self.assertIsNone(eco['van_mad'])
        self.assertTrue(bloc['publiable_client'])
        self.assertEqual(bloc['statut'], 'calcule')
        self.assertEqual(bloc['remplacements'][0], {
            'composant': 'pompe', 'annee': 7, 'montant_ttc_mad': 8000.0,
            'source': E.SOURCE_POMPE, 'motif': None})

    def test_hypotheses_horizon_indexation_degradation_sourcees(self):
        hyp = {h['cle']: h for h in self.bloc()['economie']['hypotheses']}
        self.assertEqual(hyp['horizon_ans']['source'], E.SOURCE_HORIZON)
        self.assertEqual(hyp['indexation_pct']['valeur'], 0.0)
        self.assertIn('il peut monter ou baisser',
                      hyp['indexation_pct']['source'])
        self.assertEqual(hyp['degradation_pct']['valeur'], 0.0)
        self.assertIn('sans objet', hyp['degradation_pct']['source'])

    def test_variateur_garantie_24_mois_remplace_en_annee_2(self):
        bloc = self.bloc(lignes=lignes_reference(garantie_variateur=24))
        var = [r for r in bloc['remplacements']
               if r['composant'] == 'variateur'][0]
        self.assertEqual(var['annee'], 2)
        self.assertEqual(var['montant_ttc_mad'], 6000.0)
        flux = bloc['economie']['flux']
        self.assertEqual(flux[2]['flux_mad'], round(12000 - 600 - 6000, 2))

    def test_variateur_garantie_vide_omission_nommee(self):
        bloc = self.bloc(lignes=lignes_reference(garantie_variateur=0))
        var = [r for r in bloc['remplacements']
               if r['composant'] == 'variateur'][0]
        self.assertIsNone(var['annee'])
        self.assertIn('garantie constructeur', var['motif'])
        self.assertIn('remplacement_variateur',
                      [o['cle'] for o in bloc['economie']['omissions']])

    def test_variateur_garantie_au_dela_de_10_ans_omise(self):
        bloc = self.bloc(lignes=lignes_reference(garantie_variateur=132))
        var = [r for r in bloc['remplacements']
               if r['composant'] == 'variateur'][0]
        self.assertIsNone(var['annee'])

    def test_pompe_existante_aucune_provision(self):
        bloc = self.bloc(sortie_etude={'couverture_pct_mois': [120] * 12,
                                       'pompe': {'mode': 'existante'}})
        pompe = bloc['remplacements'][0]
        self.assertIsNone(pompe['montant_ttc_mad'])
        self.assertEqual(pompe['motif'], 'pompe conservée dans les deux '
                                         'scénarios : aucune provision de '
                                         'remplacement')
        self.assertEqual(bloc['economie']['flux'][7]['flux_mad'], 11400.0)

    def test_bareme_vide_non_publiable(self):
        bloc = self.bloc(reglages={})
        self.assertFalse(bloc['publiable_client'])
        self.assertIn('barème des charges solaires non saisi',
                      bloc['motifs_non_publiable'])
        self.assertIsNone(bloc['charges_solaires'])

    def test_la_tva_d_une_ligne_ne_change_que_l_investissement(self):
        a = self.bloc(lignes=lignes_reference(tva_panneaux=20))
        b = self.bloc(lignes=lignes_reference(tva_panneaux=10))
        fa, fb = a['economie']['flux'], b['economie']['flux']
        self.assertEqual(fa[0]['flux_mad'], -50000.0)
        self.assertEqual(fb[0]['flux_mad'], -(8000.0 + 35000 * 1.1))
        self.assertEqual([lg['flux_mad'] for lg in fa[1:]],
                         [lg['flux_mad'] for lg in fb[1:]])
        self.assertEqual(a['remplacements'], b['remplacements'])

    def test_une_regle_fda_ne_change_pas_le_retour(self):
        sans = self.bloc()
        avec = self.bloc(reglages=dict(CHARGES, **REGLE_FDA))
        self.assertEqual(sans['economie']['retour_ans'],
                         avec['economie']['retour_ans'])
        self.assertEqual(sans['economie']['flux'], avec['economie']['flux'])

    def test_part_evitee_plafonnee_et_couverture_sans_courbe(self):
        etude = {'couverture_pct_mois': [50] * 12, 'pompe': {'mode': 'neuve'}}
        bloc = self.bloc(sortie_etude=etude)
        self.assertEqual(bloc['economie']['flux'][1]['economie_mad'], 6000.0)
        sans = self.bloc(sortie_etude={'pompe': {'mode': 'neuve'}})
        self.assertFalse(sans['couverture']['verifiee'])
        self.assertEqual(sans['couverture']['motif'],
                         'couverture non vérifiable : pompe sans courbe')
        self.assertEqual(sans['couverture']['part_evitee_par_mois'],
                         [1] * 12)

    def test_ligne_optionnelle_hors_investissement(self):
        lignes = lignes_reference() + [ligne('Sonde', 999, optionnelle=True)]
        self.assertEqual(self.bloc(lignes=lignes)['economie']['flux'][0]
                         ['flux_mad'], -50000.0)

    def test_passe_par_flux_de_tresorerie(self):
        from unittest import mock
        with mock.patch.object(E, 'flux_de_tresorerie',
                               wraps=E.flux_de_tresorerie) as espion:
            self.bloc()
        # Le flux principal ET chaque ligne de sensibilité : un seul moteur.
        self.assertGreaterEqual(espion.call_count, 1)

    def test_aucune_logique_d_injection_en_agricole(self):
        import json
        bloc = self.bloc()
        texte = json.dumps(bloc, ensure_ascii=False).lower()
        self.assertNotIn('injection', texte)
        self.assertNotIn('autoconsomm', texte)
        # Aucune ligne « moins subvention » dans le flux (retour SANS aide).
        self.assertNotIn('subvention',
                         json.dumps(bloc['economie'], ensure_ascii=False))


# ── AGR203 ──────────────────────────────────────────────────────────────────

def etude_declaree(volume=100.0, production=150.0, couverture=120):
    return {'besoin': {'nature': 'declare', 'm3_jour_mois': [volume] * 12},
            'production': (None if production is None
                           else {'m3_jour_mois': [production] * 12}),
            'couverture_pct_mois': ([couverture] * 12
                                    if couverture is not None else None),
            'pompe': {'mode': 'neuve'}}


def _retour_a_la_main(investissement, economie_nette, sorties):
    cumul = -investissement
    if cumul >= 0:
        return 0
    for annee in range(1, 11):
        cumul += economie_nette - sorties.get(annee, 0.0)
        if cumul >= 0:
            return annee
    return None


class CoutDuM3SensibiliteSeuilTests(SimpleTestCase):
    """AGR203 — coût du m³ actuel et solaire, sensibilité sans prévision,
    seuil de rentabilité du carburant."""

    def gasoil(self, **kw):
        # 10 L par jour d'irrigation × 6 j/semaine, 12 MAD/L, avril-sept.
        saisies = saisies_carburant(
            energie='diesel', quantite=10, unite='litre',
            periode='jour_irrigation', jours=6, prix=12.0, mois=range(4, 10))
        return E.economie_pompage(
            saisies, sortie_etude=kw.get('etude', etude_declaree()),
            lignes=lignes_reference(), reglages=CHARGES)

    def test_gasoil_calcule_a_la_main(self):
        bloc = self.gasoil()
        jours = sum((30, 31, 30, 31, 31, 30))     # avril → septembre
        litres = 10 * 6 * jours / 7
        volume = 100 * 6 * jours / 7               # déclaré = utile (100 < 150)
        self.assertEqual(bloc['mad_par_m3']['actuel'],
                         round(litres * 12 / volume, 2))
        self.assertEqual(bloc['mad_par_m3']['actuel'], 1.2)
        self.assertEqual(bloc['mad_par_m3']['solaire'],
                         round((50000 + 8000 + 600 * 10) / (volume * 10), 2))
        seuil = (50000 + 8000 + 10 * 600) / (10 * litres)
        self.assertEqual(bloc['seuil_rentabilite_carburant'],
                         {'valeur_unitaire_mad': round(seuil, 2),
                          'unite': 'MAD par litre',
                          'formule': 'valeur unitaire pour laquelle le cumul '
                                     'à 10 ans vaut 0 (indexation 0 %)'})
        sens = bloc['sensibilite_carburant']
        self.assertEqual([s['facteur'] for s in sens],
                         [0.8, 0.9, 1.1, 1.2, 1.5])
        for ligne_s in sens:
            prix = 12.0 * ligne_s['facteur']
            nette = litres * prix - 600
            self.assertEqual(ligne_s['valeur_unitaire_mad'], round(prix, 2))
            self.assertEqual(ligne_s['economie_nette_mad_an'],
                             round(nette, 2))
            self.assertEqual(ligne_s['retour_ans'],
                             _retour_a_la_main(50000, nette, {7: 8000.0}))
        self.assertEqual(sens[0]['libelle'],
                         'si le prix payé était 9,60 DH le litre')

    def test_butane_calcule_a_la_main(self):
        saisies = saisies_carburant(quantite=4, jours=6, prix=50.0,
                                    mois=range(4, 10))
        bloc = E.economie_pompage(
            saisies, sortie_etude=etude_declaree(volume=135.0),
            lignes=lignes_reference(), reglages=CHARGES)
        self.assertEqual(bloc['mad_par_m3']['actuel'],
                         round(4 * 50 / 135, 2))
        bouteilles = 4 * 6 * 183 / 7
        self.assertEqual(
            bloc['seuil_rentabilite_carburant']['valeur_unitaire_mad'],
            round((50000 + 8000 + 6000) / (10 * bouteilles), 2))
        self.assertEqual(bloc['seuil_rentabilite_carburant']['unite'],
                         'MAD par bouteille 12 kg')
        self.assertEqual(bloc['sensibilite_carburant'][2]['libelle'],
                         'si le prix payé était 55 DH la bouteille')

    def test_nouveau_forage_m3_solaire_seul_sans_economie(self):
        saisies = {'energie_actuelle': _energie('aucune'),
                   'consommation': {'jours_irrigation_par_semaine': 7},
                   'mois_irrigation': _mois(range(1, 13))}
        bloc = E.economie_pompage(
            saisies, sortie_etude=etude_declaree(volume=50.0,
                                                 production=40.0),
            lignes=lignes_reference(), reglages=CHARGES)
        self.assertEqual(bloc['cas'], E.CAS_NOUVEAU_FORAGE)
        self.assertIsNone(bloc['mad_par_m3']['actuel'])
        utile = 40.0 * 365                         # min(40 livrés, 50 voulus)
        self.assertEqual(bloc['mad_par_m3']['solaire'],
                         round((50000 + 8000 + 6000) / (utile * 10), 2))
        self.assertEqual(bloc['economie']['flux'], [])
        self.assertEqual(bloc['sensibilite_carburant'], [])
        self.assertIsNone(bloc['seuil_rentabilite_carburant'])

    def test_sans_serie_ni_volume_declare_omission_nommee(self):
        etude = {'besoin': {'nature': 'agronomique_plein',
                            'm3_jour_mois': [80.0] * 12},
                 'production': None, 'couverture_pct_mois': None,
                 'pompe': {'mode': 'neuve'}}
        bloc = self.gasoil(etude=etude)
        self.assertIsNone(bloc['mad_par_m3']['solaire'])
        self.assertIsNone(bloc['mad_par_m3']['actuel'])
        cles = {o['cle']: o['motif'] for o in bloc['omissions']}
        self.assertIn('pompe sans courbe et aucun volume déclaré',
                      cles['mad_par_m3.solaire'])
        self.assertIn('volume pompé déclaré absent', cles['mad_par_m3.actuel'])

    def test_la_sensibilite_ne_contient_aucune_ligne_indexee(self):
        import json
        for ligne_s in self.gasoil()['sensibilite_carburant']:
            self.assertEqual(set(ligne_s), {
                'facteur', 'libelle', 'valeur_unitaire_mad',
                'economie_nette_mad_an', 'retour_ans'})
            self.assertNotIn('index', json.dumps(ligne_s))

    def test_reseau_grille_sur_la_facture_sans_seuil_carburant(self):
        bloc = E.economie_pompage({
            'energie_actuelle': _energie('electrique'),
            'facture_reseau': {'montant_mad': 1000,
                               'periodicite': 'mensuelle',
                               'part_fixe_mad_mois': 100,
                               'saisi_le': '2026-09-12'},
            'mois_irrigation': _mois((6, 7, 8)),
        }, sortie_etude=etude_declaree(), lignes=lignes_reference(),
            reglages=CHARGES)
        sens = bloc['sensibilite_carburant']
        self.assertEqual(sens[0]['libelle'], 'si la facture était 800 DH')
        self.assertEqual(sens[0]['economie_nette_mad_an'],
                         round((800 - 100) * 3 - 600, 2))
        self.assertIsNone(bloc['seuil_rentabilite_carburant'])


# ── AGR204 ──────────────────────────────────────────────────────────────────

def etude_hmt(volume, hmt):
    etude = etude_declaree(volume=volume, production=volume * 2)
    etude['hmt'] = {'valeur_m': hmt, 'source': 'calculee'}
    return etude


def saisies_gasoil_jour(litres, *, confirmee=False):
    s = saisies_carburant(energie='diesel', quantite=litres, unite='litre',
                          periode='jour_irrigation', jours=7, prix=12.0,
                          mois=(6, 7, 8))
    s['coherence_confirmee'] = confirmee
    return s


class GardeDeCoherenceTests(SimpleTestCase):
    """AGR204 — litres ou bouteilles contre le volume pompé : avertir,
    jamais corriger."""

    def bloc(self, litres, volume, hmt, confirmee=False):
        return E.economie_pompage(
            saisies_gasoil_jour(litres, confirmee=confirmee),
            sortie_etude=etude_hmt(volume, hmt), lignes=lignes_reference(),
            reglages=CHARGES)

    def test_constante_hydraulique_physique(self):
        self.assertAlmostEqual(E.ENERGIE_HYDRAULIQUE_KWH_PAR_M3_M, 0.002725)

    def test_chaque_pci_porte_sa_source_url_et_date(self):
        for cle, pci in E.PCI_CARBURANTS.items():
            with self.subTest(cle=cle):
                self.assertIn('https://', pci['source'])
                self.assertIn('03/10/2026', pci['source'])

    def test_3_litres_pour_500_m3_a_60_m_avertit_sans_corriger(self):
        bloc = self.bloc(3, 500, 60)
        self.assertEqual(len(bloc['coherence']), 1)
        alerte = bloc['coherence'][0]
        self.assertEqual(alerte['niveau'], 'avertissement')
        self.assertEqual(alerte['champ'],
                         'saisies_economie_pompage.consommation')
        self.assertEqual(alerte['message'], E.MESSAGE_IMPOSSIBLE)
        self.assertFalse(bloc['publiable_client'])
        # Chiffres INCHANGÉS : la dépense reste celle déclarée.
        attendu = 3 * 7 * (30 + 31 + 31) / 7 * 12.0
        self.assertEqual(bloc['depense_actuelle']['annuelle_mad'],
                         round(attendu, 2))
        self.assertIsNone(
            bloc['vue_interne']['rendement_global_implicite_pct'])

    def test_meme_cas_confirme_devient_publiable(self):
        bloc = self.bloc(3, 500, 60, confirmee=True)
        self.assertEqual(len(bloc['coherence']), 1)
        self.assertTrue(bloc['publiable_client'])

    def test_pci_non_source_omission_nommee(self):
        from unittest import mock
        sans = {k: dict(v, source='') for k, v in E.PCI_CARBURANTS.items()}
        with mock.patch.object(E, 'PCI_CARBURANTS', sans):
            bloc = self.bloc(3, 500, 60)
        self.assertEqual(bloc['coherence'], [])
        self.assertIn('pouvoir calorifique non sourcé', [
            o['motif'].split(' :')[0]
            for o in bloc['vue_interne']['omissions']])

    def test_cas_realiste_aucun_avertissement_rendement_interne(self):
        bloc = self.bloc(10, 100, 60)
        self.assertEqual(bloc['coherence'], [])
        hydraulique = 0.002725 * 60 * 100
        carburant = 10 * 43.3 * 0.845 / 3.6
        self.assertAlmostEqual(
            bloc['vue_interne']['rendement_global_implicite_pct'],
            round(hydraulique / carburant * 100, 1), places=1)
        publique = {k: v for k, v in bloc.items() if k != 'vue_interne'}
        import json
        self.assertNotIn('rendement', json.dumps(publique))

    def test_retour_d_un_an_alerte_interne_sans_bloquer(self):
        # 200 L/jour × 12 MAD sur 3 mois : le retour tombe à 1 an.
        bloc = self.bloc(200, 3000, 20)
        self.assertLessEqual(bloc['economie']['retour_ans'], 1)
        self.assertEqual(bloc['vue_interne']['alertes'][0]['code'],
                         'retour_tres_court')
        self.assertTrue(bloc['publiable_client'])


# ── AGR205 ──────────────────────────────────────────────────────────────────

REPERES = {
    'butane_12kg_detail': {'valeur': 50, 'source': '', 'releve_le':
                           '2026-08-20'},
    'butane_12kg_non_subventionne': {
        'valeur': 128, 'source': 'relevé société (repère daté)',
        'releve_le': '2026-08-20'},
}


class VueInterneEtFinancementTests(SimpleTestCase):
    """AGR205 — VAN avec taux saisi, scénario butane non subventionné, aide
    FDA indicative, mensualité du prêt ; rien de tout cela ne sort de
    ``economie_pompage_publique``."""

    def bloc(self, saisies=None, **kw):
        kw.setdefault('sortie_etude', dict(ETUDE_COUVERTE,
                                           champ={'kwc': 5.0}))
        kw.setdefault('lignes', lignes_reference())
        kw.setdefault('reglages', dict(CHARGES, **REGLE_FDA))
        return E.economie_pompage(saisies or saisies_12000(), **kw)

    def test_sans_taux_van_nulle_avec_motif(self):
        interne = self.bloc()['vue_interne']
        self.assertIsNone(interne['van_mad'])
        self.assertIn({'cle': 'van_mad',
                       'motif': "taux d'actualisation non saisi"},
                      interne['omissions'])

    def test_taux_sans_source_refuse_en_nommant_le_champ(self):
        s = saisies_12000()
        s['taux_actualisation'] = {'valeur': 8, 'source': ''}
        with self.assertRaises(EconomieInvalide) as ctx:
            self.bloc(s)
        self.assertEqual(ctx.exception.champ, 'taux_actualisation.source')

    def test_taux_source_donne_la_van_du_meme_flux(self):
        s = saisies_12000()
        s['taux_actualisation'] = {'valeur': 8, 'source': 'saisie interne'}
        bloc = self.bloc(s)
        flux = [-50000.0] + [11400.0] * 10
        flux[7] -= 8000.0
        van = sum(f / 1.08 ** a for a, f in enumerate(flux))
        self.assertAlmostEqual(bloc['vue_interne']['van_mad'], van, places=1)
        # Le bloc PUBLIC reste sans VAN.
        self.assertIsNone(bloc['economie']['van_mad'])

    def test_aide_fda_le_plafond_le_plus_bas(self):
        s = saisies_carburant(quantite=4, jours=6, prix=50.0,
                              mois=range(4, 10))
        aide = self.bloc(s, surface_irriguee_ha=4)['vue_interne'][
            'aide_fda_indicative']
        self.assertEqual(aide['termes'], {
            'taux_x_base_mad': 15000.0,            # 30 % × 50 000 TTC
            'plafond_ha_x_surface_mad': 12000.0,   # 3 000 × 4 ha
            'plafond_kwc_x_kwc_mad': 15000.0,      # 3 000 × 5 kWc
            'plafond_projet_mad': 30000.0})
        self.assertEqual(aide['montant_mad'], 12000.0)
        self.assertEqual(aide['edition'], 'Guide FDA édition 2024, p.20-23')
        etats = {c['cle']: c['etat'] for c in aide['conditions']}
        self.assertEqual(etats, {
            'energie_actuelle_butane': 'remplie',
            'irrigation_localisee': 'a_verifier', 'compteur_eau': 'a_verifier',
            'un_seul_projet_par_exploitation': 'a_verifier'})

    def test_diesel_condition_butane_non_remplie_montant_non_calcule(self):
        aide = self.bloc(surface_irriguee_ha=4)['vue_interne'][
            'aide_fda_indicative']
        self.assertEqual(aide['conditions'][0],
                         {'cle': 'energie_actuelle_butane',
                          'etat': 'non_remplie'})
        self.assertIsNone(aide['montant_mad'])

    def test_regle_fda_absente_aide_omise(self):
        interne = self.bloc(reglages=CHARGES)['vue_interne']
        self.assertIsNone(interne['aide_fda_indicative'])
        self.assertIn('aide_fda_indicative',
                      [o['cle'] for o in interne['omissions']])

    def test_scenario_butane_non_subventionne_interne_seulement(self):
        s = saisies_carburant(quantite=4, jours=6, prix=50.0,
                              mois=range(4, 10))
        bloc = self.bloc(s, reperes=REPERES)
        scen = bloc['vue_interne']['scenario_butane_non_subventionne']
        bouteilles = 4 * 6 * 183 / 7
        self.assertEqual(scen['valeur_unitaire_mad'], 128)
        self.assertEqual(scen['economie_nette_mad_an'],
                         round(bouteilles * 128 - 600, 2))
        self.assertEqual(scen['libelle'], E.LIBELLE_SCENARIO_BUTANE)
        # Le retour principal reste au prix PAYÉ déclaré.
        principal = self.bloc(s)['economie']['retour_ans']
        self.assertEqual(bloc['economie']['retour_ans'], principal)
        # Le repère détail SANS source n'est pas affiché à côté du champ.
        self.assertEqual(bloc['reperes_affiches'], [])

    def test_scenario_omis_sans_source(self):
        s = saisies_carburant(quantite=4, jours=6, prix=50.0,
                              mois=range(4, 10))
        reperes = {'butane_12kg_non_subventionne': {'valeur': 128,
                                                    'source': ''}}
        interne = self.bloc(s, reperes=reperes)['vue_interne']
        self.assertIsNone(interne['scenario_butane_non_subventionne'])

    def test_pret_saisi_mensualite_de_tableau_pret(self):
        from apps.ventes.economie import tableau_pret
        s = saisies_12000()
        pret = {'principal_mad': 40000, 'taux_annuel_pct': 6,
                'duree_mois': 60, 'type_pret': 'annuite', 'differe_mois': 0,
                'source': 'offre bancaire saisie'}
        s['pret'] = pret
        fin = self.bloc(s)['financement']
        attendu = tableau_pret(principal_mad=40000, taux_annuel_pct=6,
                               duree_mois=60, type_pret='annuite',
                               differe_mois=0)
        self.assertEqual(fin['mensualite_mad'], attendu['mensualite_mad'])
        self.assertEqual(fin['carburant_evite_par_mois'], [1000.0] * 12)

    def test_pret_sans_taux_jamais_de_taux_par_defaut(self):
        s = saisies_12000()
        s['pret'] = {'principal_mad': 40000, 'duree_mois': 60,
                     'type_pret': 'annuite', 'source': 'offre'}
        bloc = self.bloc(s)
        self.assertIsNone(bloc['financement'])

    def test_rien_d_interne_ne_sort_de_la_version_publique(self):
        import json
        s = saisies_carburant(quantite=4, jours=6, prix=50.0,
                              mois=range(4, 10))
        s['taux_actualisation'] = {'valeur': 8, 'source': 'saisie interne'}
        bloc = self.bloc(s, reperes=REPERES, surface_irriguee_ha=4)
        publique = E.economie_pompage_publique(bloc)
        self.assertNotIn('vue_interne', publique)
        texte = json.dumps(publique, ensure_ascii=False)
        for interdit in ('aide_fda', 'non_subventionne', 'rendement_global',
                         'prix_achat'):
            self.assertNotIn(interdit, texte)
        self.assertIsNone(publique['economie']['van_mad'])
        self.assertIn('vue_interne', bloc)
