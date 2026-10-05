"""CAD175 — seconde livraison du panneau d'appel : agricole et industriel.

Ce que le SERVEUR doit servir pour que l'écran rende le bon jeu de questions
(``frontend/src/features/crm/relances/appelGuidance.js``, ``ORDRE_AGRICOLE`` /
``ORDRE_PRO``) : chaque question est une colonne ``crm.Lead`` EXISTANTE, et
une réponse déjà sur la fiche n'est jamais reposée.

AGR407 — l'appel agricole devient CINQ étapes qui collectent ce qui
dimensionne (énergie actuelle → eau → besoin → heures/distance →
irrigation/électricité) ; ``pompe_actuelle_cv`` sort de l'appel (plaque, en
visite) ; ``mois_irrigation`` est servi en ``choix_multiple`` ; un lead
agricole ne reçoit aucune section résidentielle ; aucune clé d'économie.

Aucune base : un ``Lead`` NON ENREGISTRÉ suffit.
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from apps.crm import panneau_appel as panneau
from apps.crm.models import Lead

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'panneau_appel.json').read_text(encoding='utf-8'))

#: Les colonnes que l'écran pose, par famille (miroir des étapes de
#: `appelGuidance.js` ; le test écran prouve l'ordre, celui-ci la présence).
COLONNES_AGRICOLES = (
    'pompe_alim_actuelle', 'butane_bouteilles_jour', 'carburant_litres_mois',
    'carburant_prix_unitaire_mad', 'depense_carburant_mad_mois',
    'source_eau', 'niveau_statique_m', 'debit_forage_m3h',
    'besoin_eau_m3j', 'surface_irriguee_ha', 'culture',
    'pompage_heures_jour', 'distance_forage_champ_m',
    'irrigation_methode', 'mois_irrigation', 'electricite_sur_place',
)
#: CIQ410 — colonnes posées à TOUT lead pro (la facture se pose en kWh OU en
#: dirhams selon le lead : voir les tests dédiés).
COLONNES_PRO = ('tension_raccordement', 'compteur_puissance_kva',
                'jours_ouverture', 'heure_debut', 'heure_fin',
                'fermeture_mois', 'type_surface', 'type_toiture',
                'surface_toiture_m2', 'decideur')

#: CAD175 — garde : aucune clé d'économie dans le panneau.
FRAGMENTS_ECONOMIE = ('econom', 'payback', 'retour', 'gain')


def _champs(lead):
    return [q['champ'] for q in panneau.questions_a_poser(lead)]


def _cles(objet):
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            yield cle
            yield from _cles(valeur)
    elif isinstance(objet, list):
        for valeur in objet:
            yield from _cles(valeur)


def _panneau(lead, exemple):
    with mock.patch.object(panneau, '_touche_en_cours', return_value=None), \
            mock.patch.object(panneau, '_couches_composables',
                              return_value=set()), \
            mock.patch.object(panneau, 'fenetre_du_jour_servie',
                              return_value=exemple['fenetre_du_jour']), \
            mock.patch.object(panneau, 'profil_suppose_servi',
                              return_value=exemple['profil_suppose']):
        return panneau.panneau_appel(lead)


class LeServeurSertLesQuestionsDuSegment(SimpleTestCase):
    def test_un_lead_agricole_se_voit_poser_ses_cinq_etapes(self):
        champs = _champs(Lead(nom='P', type_installation='agricole'))
        for colonne in COLONNES_AGRICOLES:
            self.assertIn(colonne, champs, colonne)
        self.assertEqual(champs[:len(COLONNES_AGRICOLES)],
                         list(COLONNES_AGRICOLES))

    def test_la_cv_de_la_pompe_actuelle_sort_de_l_appel(self):
        champs = _champs(Lead(nom='P', type_installation='agricole'))
        self.assertNotIn('pompe_actuelle_cv', champs)
        self.assertNotIn('pompe_actuelle_cv', panneau.CHAMPS_ORAUX_AGRICOLE)

    def test_un_lead_agricole_ne_recoit_aucune_section_residentielle(self):
        questions = panneau.questions_a_poser(
            Lead(nom='P', type_installation='agricole'))
        for question in questions:
            self.assertIsNone(question['section'], question['champ'])
        champs = [q['champ'] for q in questions]
        for colonne in ('occupation_jour', 'facture_hiver', 'type_toiture',
                        'equip_clim'):
            self.assertNotIn(colonne, champs)

    def test_industriel_et_commercial_se_voient_poser_le_jeu_pro(self):
        for segment in ('industriel', 'commercial'):
            champs = _champs(Lead(nom='P', type_installation=segment))
            for colonne in COLONNES_PRO:
                self.assertIn(colonne, champs, f'{segment}:{colonne}')

    def test_le_residentiel_ne_recoit_ni_la_pompe_ni_la_puissance_souscrite(self):
        """En résidentiel, la puissance souscrite se lit sur la PHOTO du
        compteur (dernier recours à l'oral, CAD154) : pas une question."""
        champs = _champs(Lead(nom='P', type_installation='residentiel'))
        for colonne in ('pompe_alim_actuelle', 'source_eau',
                        'compteur_puissance_kva'):
            self.assertNotIn(colonne, champs, colonne)

    def test_chaque_colonne_de_segment_existe_sur_le_lead(self):
        for colonne in (*COLONNES_AGRICOLES, *COLONNES_PRO):
            self.assertIsNotNone(Lead._meta.get_field(colonne), colonne)

    def test_une_reponse_de_segment_deja_sur_la_fiche_n_est_pas_reposee(self):
        lead = Lead(nom='P', type_installation='agricole',
                    niveau_statique_m=Decimal('32.00'))
        self.assertNotIn('niveau_statique_m', _champs(lead))
        self.assertEqual(
            panneau.prefill_du_panneau(lead)['niveau_statique_m'], 32.0)
        pro = Lead(nom='P', type_installation='industriel',
                   compteur_puissance_kva=Decimal('60.00'))
        self.assertNotIn('compteur_puissance_kva', _champs(pro))
        self.assertEqual(
            panneau.prefill_du_panneau(pro)['compteur_puissance_kva'], 60.0)

    def test_les_grandeurs_d_eau_sont_servies_comme_des_nombres(self):
        questions = {q['champ']: q for q in panneau.questions_a_poser(
            Lead(nom='P', type_installation='agricole'))}
        for colonne in ('niveau_statique_m', 'debit_forage_m3h',
                        'besoin_eau_m3j'):
            self.assertEqual(questions[colonne]['nature'], 'nombre', colonne)
            self.assertIsNone(questions[colonne]['choix'], colonne)

    def test_mois_irrigation_en_choix_multiple_douze_mois(self):
        questions = {q['champ']: q for q in panneau.questions_a_poser(
            Lead(nom='P', type_installation='agricole'))}
        mois = questions['mois_irrigation']
        self.assertEqual(mois['nature'], 'choix_multiple')
        self.assertEqual([c['valeur'] for c in mois['choix']],
                         list(range(1, 13)))


class AGR407ChaqueChampAgricoleASaQuestion(SimpleTestCase):
    def test_garde_parametree_help_text_question_a_l_appel(self):
        for colonne in panneau.CHAMPS_ORAUX_AGRICOLE:
            with self.subTest(colonne=colonne):
                texte = str(Lead._meta.get_field(colonne).help_text or '')
                self.assertTrue(texte.startswith("Question à l'appel : « "),
                                texte)
                self.assertIn(' »', texte)

    def test_le_site_a_rempli_source_niveau_besoin_on_ne_pose_que_le_reste(self):
        lead = Lead(nom='P', type_installation='agricole', source_eau='forage',
                    niveau_statique_m=Decimal('32.00'),
                    besoin_eau_m3j=Decimal('135.00'))
        champs = _champs(lead)
        for deja in ('source_eau', 'niveau_statique_m', 'besoin_eau_m3j'):
            self.assertNotIn(deja, champs)
        reste = [c for c in COLONNES_AGRICOLES
                 if c not in ('source_eau', 'niveau_statique_m',
                              'besoin_eau_m3j')]
        self.assertEqual(champs[:len(reste)], reste)

    def test_aucune_cle_d_economie(self):
        exemple = CONTRAT['exemple_agricole']
        data = _panneau(Lead(nom='P', type_installation='agricole'), exemple)
        for cle in _cles(data):
            for fragment in FRAGMENTS_ECONOMIE:
                self.assertNotIn(fragment, cle.lower(), cle)

    def test_l_exemple_agricole_du_contrat_egale_la_sortie_reelle(self):
        exemple = CONTRAT['exemple_agricole']
        prefill = exemple['prefill']
        lead = Lead(pk=exemple['lead_id'], nom='P',
                    type_installation='agricole',
                    pompe_alim_actuelle=prefill['pompe_alim_actuelle'],
                    source_eau=prefill['source_eau'],
                    niveau_statique_m=Decimal(str(prefill['niveau_statique_m'])),
                    besoin_eau_m3j=Decimal(str(prefill['besoin_eau_m3j'])))
        data = _panneau(lead, exemple)
        self.assertEqual(data, exemple)


class CIQ410PanneauPro(SimpleTestCase):
    """CIQ410 (D-CIQ-7) — les cinq étapes du premier appel pro."""

    def test_garde_parametree_toute_colonne_pro_a_une_question_pro(self):
        for colonne in panneau.CHAMPS_ORAUX_PRO:
            for segment in ('commercial', 'industriel'):
                with self.subTest(colonne=colonne, segment=segment):
                    lead = Lead(nom='P', type_installation=segment,
                                categorie_commerciale='hotel')
                    question = panneau._question(lead, colonne, None)
                    texte = question['question']
                    self.assertTrue(texte.startswith(
                        panneau.PREFIXE_QUESTION), texte)
                    self.assertTrue(texte[len(panneau.PREFIXE_QUESTION):]
                                    .strip(), colonne)
                    self.assertNotIn('photo du compteur', texte.lower())

    def test_les_questions_viennent_du_contrat_ciq1(self):
        contrat_pro = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'lead_pro.json').read_text(encoding='utf-8'))
        par_colonne = {c['nom']: c['question']
                       for c in contrat_pro['colonnes_pro']}
        etapes = contrat_pro['questions_pro']
        for colonne in ('raccordement', 'categorie_commerciale',
                        'secteur_industriel', 'regime_equipes',
                        'jours_ouverture', 'heure_debut', 'heure_fin',
                        'fermeture_mois', 'type_surface', 'type_toiture'):
            self.assertEqual(panneau.QUESTIONS_PRO[colonne],
                             par_colonne[colonne], colonne)
        for segment in ('commercial', 'industriel'):
            self.assertEqual(
                panneau.QUESTIONS_PRO['conso_mensuelle_kwh'][segment],
                etapes['etape_1'][segment][0])
            self.assertEqual(
                panneau.QUESTIONS_PRO['tension_raccordement'][segment],
                etapes['etape_2'][segment][0])
            self.assertEqual(panneau.QUESTIONS_PRO['compteur_puissance_kva'],
                             etapes['etape_2'][segment][1])
            self.assertEqual(panneau.QUESTIONS_PRO['decideur'][segment],
                             etapes['etape_5'][segment][0])

    def test_un_lead_commercial_n_a_aucun_champ_residentiel(self):
        lead = Lead(nom='P', type_installation='commercial')
        champs = _champs(lead)
        residentiels = set()
        for section in ('occupation', 'equipements'):
            residentiels.update(
                panneau.questionnaire.CHAMPS_PAR_SECTION[section])
        residentiels.update(('roof_age', 'ownership', 'type_bien',
                             'objectif_projet', 'ete_differente'))
        for champ in champs:
            self.assertNotIn(champ, residentiels, champ)
        data = _panneau(lead, CONTRAT['exemple_commercial'])
        self.assertEqual(data['equipements'], [])

    def test_facture_en_dirhams_commerce_bt_en_kwh_industriel_ou_mt(self):
        self.assertIn('facture_hiver', _champs(Lead(
            nom='P', type_installation='commercial')))
        self.assertIn('conso_mensuelle_kwh', _champs(Lead(
            nom='P', type_installation='industriel')))
        mt = _champs(Lead(nom='P', type_installation='commercial',
                          tension_raccordement='mt'))
        self.assertIn('conso_mensuelle_kwh', mt)
        self.assertNotIn('raccordement', mt)

    def test_une_facture_connue_ferme_l_etape(self):
        champs = _champs(Lead(nom='P', type_installation='industriel',
                              facture_hiver=Decimal('9000')))
        self.assertNotIn('conso_mensuelle_kwh', champs)
        self.assertNotIn('facture_hiver', champs)

    def test_decideur_seulement_les_choix_pro(self):
        questions = {q['champ']: q for q in panneau.questions_a_poser(
            Lead(nom='P', type_installation='industriel'))}
        self.assertEqual([c['valeur'] for c in questions['decideur']['choix']],
                         list(panneau.DECIDEUR_PRO))

    def test_tension_et_categorie_remplies_on_ne_pose_que_le_reste(self):
        lead = Lead(nom='P', type_installation='commercial',
                    tension_raccordement='bt', categorie_commerciale='hotel')
        champs = _champs(lead)
        self.assertNotIn('tension_raccordement', champs)
        self.assertNotIn('categorie_commerciale', champs)
        prefill = panneau.prefill_du_panneau(lead)
        self.assertEqual(prefill['tension_raccordement'], 'bt')
        self.assertEqual(prefill['categorie_commerciale'], 'hotel')

    def test_jours_et_mois_en_choix_multiple(self):
        questions = {q['champ']: q for q in panneau.questions_a_poser(
            Lead(nom='P', type_installation='industriel'))}
        self.assertEqual(questions['jours_ouverture']['nature'],
                         'choix_multiple')
        self.assertEqual([c['valeur'] for c in
                          questions['jours_ouverture']['choix']],
                         list(range(1, 8)))
        self.assertEqual([c['valeur'] for c in
                          questions['fermeture_mois']['choix']],
                         list(range(1, 13)))

    def test_aucune_cle_d_economie(self):
        for nom in ('exemple_commercial', 'exemple_industriel'):
            exemple = CONTRAT[nom]
            lead = Lead(nom='P', type_installation=exemple['segment'])
            for cle in _cles(_panneau(lead, exemple)):
                for fragment in FRAGMENTS_ECONOMIE:
                    self.assertNotIn(fragment, cle.lower(), cle)

    def test_les_exemples_pro_du_contrat_egalent_la_sortie_reelle(self):
        for nom in ('exemple_commercial', 'exemple_industriel'):
            exemple = CONTRAT[nom]
            lead = Lead(pk=exemple['lead_id'], nom='P',
                        type_installation=exemple['segment'],
                        **exemple['prefill'])
            self.assertEqual(_panneau(lead, exemple), exemple, nom)
