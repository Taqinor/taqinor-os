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
    'depense_electricite_pompe_mad_mois', 'source_eau', 'niveau_statique_m', 'debit_forage_m3h', 'pompe_hmt_m',
    'besoin_eau_m3j', 'surface_irriguee_ha', 'culture',
    'pompe_actuelle_debit_m3h', 'pompage_heures_jour',
    'distance_forage_champ_m', 'irrigation_methode', 'mois_irrigation', 'electricite_sur_place',
    'raccordement',
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
        """CSV2 — l'étape facture sert LES DEUX colonnes ; la principale est
        celle que le client connaît (dirhams d'abord pour un commerce BT, kWh
        d'abord pour un industriel ou un site MT)."""
        commerce = _champs(Lead(nom='P', type_installation='commercial'))
        self.assertEqual(commerce[:2], ['facture_hiver',
                                        'conso_mensuelle_kwh'])
        industriel = _champs(Lead(nom='P', type_installation='industriel'))
        self.assertEqual(industriel[:2], ['conso_mensuelle_kwh',
                                          'facture_hiver'])
        mt = _champs(Lead(nom='P', type_installation='commercial',
                          tension_raccordement='mt'))
        self.assertEqual(mt[:2], ['conso_mensuelle_kwh', 'facture_hiver'])
        self.assertIn('raccordement', mt)

    def test_une_facture_qui_ne_compte_pas_ne_ferme_pas_l_etape(self):
        """CSV2 — une facture en dirhams ne ferme l'étape que si la tension ET
        le contrat BT déclaré la laissent compter (règle de ``devis_auto``)."""
        # Industriel sans basse tension déclarée : les dirhams ne comptent pas.
        champs = _champs(Lead(nom='P', type_installation='industriel',
                              facture_hiver=Decimal('9000')))
        self.assertIn('conso_mensuelle_kwh', champs)
        self.assertNotIn('facture_hiver', champs)  # déjà remplie
        # Commerce BT, dirhams, contrat pas encore posé : étape ouverte.
        champs = _champs(Lead(nom='P', type_installation='commercial',
                              tension_raccordement='bt',
                              facture_hiver=Decimal('5000')))
        self.assertIn('conso_mensuelle_kwh', champs)
        # Commerce BT, dirhams, contrat BT déclaré : l'étape est fermée.
        champs = _champs(Lead(nom='P', type_installation='commercial',
                              tension_raccordement='bt',
                              contrat_electricite='bt_patente',
                              facture_hiver=Decimal('5000')))
        self.assertNotIn('conso_mensuelle_kwh', champs)
        self.assertNotIn('facture_hiver', champs)
        # Les kWh ferment toujours l'étape.
        champs = _champs(Lead(nom='P', type_installation='industriel',
                              conso_mensuelle_kwh=Decimal('42000')))
        self.assertNotIn('conso_mensuelle_kwh', champs)
        self.assertNotIn('facture_hiver', champs)

    def test_site_mt_facture_dirhams_redemande_les_kwh(self):
        """CSV2 — impasse du rejeu : facture en dirhams PUIS tension MT. Les
        kWh sont redemandés (premier choix), les dirhams jamais reposés."""
        lead = Lead(nom='P', type_installation='commercial',
                    facture_hiver=Decimal('5000'), tension_raccordement='mt')
        champs = _champs(lead)
        self.assertEqual(champs[0], 'conso_mensuelle_kwh')
        self.assertNotIn('facture_hiver', champs)
        self.assertEqual(panneau.prefill_du_panneau(lead)['facture_hiver'],
                         5000.0)
        # Contrat « ne sait pas » en BT : les dirhams ne comptent pas non plus.
        lead = Lead(nom='P', type_installation='commercial',
                    tension_raccordement='bt',
                    contrat_electricite='ne_sait_pas',
                    facture_hiver=Decimal('5000'))
        self.assertEqual(_champs(lead)[0], 'conso_mensuelle_kwh')

    def test_contrat_pose_en_bt_jamais_en_mt_option_si_force_motrice(self):
        """CSV3 — le contrat se lit sur la facture : posé juste après la
        tension à tout site non déclaré en MT, l'option bi-horaire seulement
        en force motrice, la question reprise mot pour mot du contrat CIQ1."""
        for segment in ('commercial', 'industriel'):
            champs = _champs(Lead(nom='P', type_installation=segment,
                                  tension_raccordement='bt'))
            self.assertIn('contrat_electricite', champs, segment)
            self.assertNotIn('option_tarifaire_bt', champs, segment)
            self.assertLess(champs.index('contrat_electricite'),
                            champs.index('compteur_puissance_kva'))
            # Tension inconnue : le contrat est posé aussi.
            self.assertIn('contrat_electricite', _champs(
                Lead(nom='P', type_installation=segment)))
            # MT déclarée : jamais de contrat, jamais d'option.
            mt = _champs(Lead(nom='P', type_installation=segment,
                              tension_raccordement='mt',
                              contrat_electricite='bt_force_motrice'))
            self.assertNotIn('contrat_electricite', mt, segment)
            self.assertNotIn('option_tarifaire_bt', mt, segment)
        force = Lead(nom='P', type_installation='commercial',
                     tension_raccordement='bt',
                     contrat_electricite='bt_force_motrice')
        self.assertIn('option_tarifaire_bt', _champs(force))
        for autre in ('bt_patente', 'bt_domestique', 'ne_sait_pas'):
            lead = Lead(nom='P', type_installation='commercial',
                        tension_raccordement='bt', contrat_electricite=autre)
            self.assertNotIn('option_tarifaire_bt', _champs(lead), autre)
            # « Ne sait pas » (comme tout contrat posé) clôt la question.
            self.assertNotIn('contrat_electricite', _champs(lead), autre)

    def test_contrat_et_option_reprennent_le_contrat_ciq1_mot_pour_mot(self):
        contrat_pro = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'lead_pro.json').read_text(encoding='utf-8'))
        par_colonne = {c['nom']: c['question']
                       for c in contrat_pro['colonnes_pro']}
        for colonne in ('contrat_electricite', 'option_tarifaire_bt'):
            self.assertIn(panneau.QUESTIONS_PRO[colonne],
                          par_colonne[colonne], colonne)

    def test_site_bt_ne_propose_pas_le_contrat_moyenne_tension(self):
        def valeurs(lead):
            questions = {q['champ']: q
                         for q in panneau.questions_a_poser(lead)}
            return [c['valeur']
                    for c in questions['contrat_electricite']['choix']]

        bt = valeurs(Lead(nom='P', type_installation='commercial',
                          tension_raccordement='bt'))
        self.assertNotIn('mt_general', bt)
        self.assertEqual(bt, ['bt_domestique', 'bt_patente',
                              'bt_force_motrice', 'ne_sait_pas'])
        inconnue = valeurs(Lead(nom='P', type_installation='commercial'))
        self.assertIn('mt_general', inconnue)
        # BT pré-cochée par le site (pas déclarée) : le client peut être en
        # MT, le choix reste offert (critique Fable pré-merge, 27/10).
        site = valeurs(Lead(nom='P', type_installation='commercial',
                            tension_raccordement='bt',
                            tension_source='site_defaut_visible'))
        self.assertIn('mt_general', site)

    def test_phase_posee_a_tout_pro_deux_choix(self):
        """CSV4 — la phase (mono/tri) se pose à tout pro, MT et industriel
        compris, avec deux choix ; en MT un seul (triphasé, un clic)."""
        def phase(lead):
            return {q['champ']: q for q in panneau.questions_a_poser(lead)}[
                'raccordement']

        for segment in ('commercial', 'industriel'):
            question = phase(Lead(nom='P', type_installation=segment,
                                  tension_raccordement='bt'))
            self.assertEqual([c['valeur'] for c in question['choix']],
                             ['monophase', 'triphase'], segment)
            self.assertIn('monophasé ou triphasé', question['question'])
            mt = phase(Lead(nom='P', type_installation=segment,
                            tension_raccordement='mt'))
            self.assertEqual([c['valeur'] for c in mt['choix']],
                             ['triphase'], segment)
            self.assertIn('Site en moyenne tension : alimentation triphasée',
                          mt['question'])

    def test_phase_inconnue_ou_aucune_est_reposee(self):
        for valeur in ('inconnu', 'aucun'):
            lead = Lead(nom='P', type_installation='commercial',
                        raccordement=valeur)
            self.assertIn('raccordement', _champs(lead), valeur)
            self.assertNotIn('raccordement', panneau.prefill_du_panneau(lead))
        lead = Lead(nom='P', type_installation='industriel',
                    raccordement='triphase')
        self.assertNotIn('raccordement', _champs(lead))
        self.assertEqual(panneau.prefill_du_panneau(lead)['raccordement'],
                         'triphase')

    def test_talon_pose_dans_l_etape_activite(self):
        """CSV12 — le talon (équipements qui tournent hors horaires) se pose
        au téléphone à tout lead pro, après les heures ; répondu, jamais
        reposé ; la réponse se relit dans le pré-remplissage."""
        for segment in ('commercial', 'industriel'):
            lead = Lead(nom='P', type_installation=segment)
            champs = _champs(lead)
            self.assertIn('equipements_hors_horaires', champs, segment)
            self.assertGreater(champs.index('equipements_hors_horaires'),
                               champs.index('heure_fin'), segment)
            question = {q['champ']: q for q in panneau.questions_a_poser(
                lead)}['equipements_hors_horaires']
            self.assertEqual(question['nature'], 'choix')
            self.assertEqual([c['valeur'] for c in question['choix']],
                             ['aucun', 'un_peu', 'beaucoup'])
            self.assertIn('des appareils continuent-ils de tourner',
                          question['question'])
            repondu = Lead(nom='P', type_installation=segment,
                           equipements_hors_horaires='un_peu')
            self.assertNotIn('equipements_hors_horaires', _champs(repondu))
            self.assertEqual(
                panneau.prefill_du_panneau(repondu)[
                    'equipements_hors_horaires'], 'un_peu')

    def test_heures_cuisson_ecrivable_et_servie(self):
        """CSV13 — les clés d'heures que le moteur C&I lit sont écrivables
        (clés fermées du sérialiseur) et servies seulement quand la réponse
        qui les rend utiles est donnée ; celles qui changent la courbe passent
        avant les autres."""
        from apps.crm.serializers import LeadSerializer
        from core.conflit_etat import ConflitEtat

        for categorie, cle in (('boulangerie', 'heures_cuisson'),
                               ('restaurant', 'heures'),
                               ('sante', 'heures_garde'),
                               ('ecole', 'fermeture_du'),
                               ('ecole', 'fermeture_au')):
            self.assertIn(cle, Lead.REPONSES_CATEGORIE_CLES[categorie])
            lead = Lead(nom='P', type_installation='commercial',
                        categorie_commerciale=categorie)
            LeadSerializer(instance=lead)._valider_colonnes_pro(
                {'reponses_categorie': {cle: [[2, 6]]}})
        # Une clé hors de la catégorie reste refusée.
        with self.assertRaises(ConflitEtat):
            LeadSerializer(instance=Lead(
                nom='P', type_installation='commercial',
                categorie_commerciale='bureau'))._valider_colonnes_pro(
                    {'reponses_categorie': {'heures_cuisson': [[2, 6]]}})

        def cles(categorie, **reponses):
            return panneau._cles_categorie_a_poser(Lead(
                nom='P', type_installation='commercial',
                categorie_commerciale=categorie, reponses_categorie=reponses))

        # Boulangerie : les heures ne sont posées que pour une cuisson de nuit
        # au four ÉLECTRIQUE (au gaz, le moteur n'ajoute aucune plage).
        self.assertEqual(cles('boulangerie'), ('four', 'cuisson_nocturne'))
        self.assertEqual(cles('boulangerie', four='electrique',
                              cuisson_nocturne=True), ('heures_cuisson',))
        self.assertEqual(cles('boulangerie', four='gaz',
                              cuisson_nocturne=True), ())
        self.assertEqual(cles('boulangerie', four='electrique',
                              cuisson_nocturne=False), ())
        # « oui » du tunnel lu comme le moteur (``moteur_ci.categories._vrai``).
        self.assertEqual(cles('boulangerie', four='electrique',
                              cuisson_nocturne='oui'), ('heures_cuisson',))
        self.assertEqual(cles('boulangerie', four='electrique',
                              cuisson_nocturne=True,
                              heures_cuisson=[[2, 6]]), ())
        # Restaurant : les heures passent AVANT le reste, après les horaires.
        self.assertNotIn('heures', cles('restaurant'))
        self.assertEqual(cles('restaurant', horaires='soir')[0], 'heures')
        self.assertEqual(cles('restaurant', horaires='soir',
                              heures=[[18, 23]]),
                         ('chambres_froides', 'cuisson'))
        # Santé et école : seulement quand garde de nuit / fermeture d'été.
        self.assertEqual(cles('sante'), ('lits', 'garde_nuit'))
        self.assertEqual(cles('sante', garde_nuit=True)[0], 'heures_garde')
        self.assertEqual(cles('ecole', fermeture_estivale=True)[:2],
                         ('fermeture_du', 'fermeture_au'))
        self.assertNotIn('fermeture_du', cles('ecole'))
        # Au plus trois questions, jamais plus.
        self.assertLessEqual(len(cles('ecole', fermeture_estivale=True)), 3)

    def test_la_question_heures_est_servie_au_panneau_avec_son_libelle(self):
        lead = Lead(nom='P', type_installation='commercial',
                    categorie_commerciale='boulangerie',
                    reponses_categorie={'four': 'electrique',
                                        'cuisson_nocturne': True})
        objet = {q['champ']: q for q in panneau.questions_a_poser(lead)}[
            'reponses_categorie']
        self.assertEqual(
            [(s['cle'], s['libelle']) for s in objet['sous_questions']],
            [('heures_cuisson', '« De quelle heure à quelle heure le four '
                                'électrique tourne-t-il la nuit ? »')])

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
        for nom in ('exemple_commercial', 'exemple_industriel',
                    'exemple_commercial_force_motrice'):
            exemple = CONTRAT[nom]
            lead = Lead(pk=exemple['lead_id'], nom='P',
                        type_installation=exemple['segment'],
                        **exemple['prefill'])
            self.assertEqual(_panneau(lead, exemple), exemple, nom)
