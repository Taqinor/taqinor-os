"""CAD148 — « les questions à poser sur CET appel » (panneau d'appel guidé).

Contrat servi : ``apps/crm/contract_samples/panneau_appel.json`` (CAD147).

Les trois choses que ce module PROUVE, et qui sont le Done de la tâche :
  1. l'assembleur ne renvoie JAMAIS une question déjà répondue — la valeur
     connue part dans ``prefill``, elle ne se repose pas au téléphone ;
  2. il ne renvoie JAMAIS une valeur par défaut — ``prefill`` ne contient que
     ce que la fiche porte réellement ;
  3. le drapeau « compté dans l'étude » est FAUX pour un équipement déclaré
     dont la grandeur manque, et le champ manquant est NOMMÉ.

Les classes ``SimpleTestCase`` ci-dessous travaillent sur un ``Lead`` NON
ENREGISTRÉ : l'assemblage des questions, du pré-remplissage et des drapeaux ne
lit que des attributs et deux fonctions pures — aucune base n'est nécessaire,
et ces tests s'exécutent donc partout. Seule la classe finale (touche +
endpoint HTTP) a besoin de l'ORM.
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm import panneau_appel as panneau
from apps.crm import questionnaire
from apps.crm.models import Lead, RelanceEtape


def _lead(**kwargs):
    """Un lead EN MÉMOIRE : aucune écriture, aucune base."""
    return Lead(nom='Prospect', **kwargs)


def _champs(questions):
    return [q['champ'] for q in questions]


class OnNeReposeJamaisUneQuestionDejaRepondue(SimpleTestCase):
    def test_une_reponse_connue_sort_des_questions_et_entre_en_prefill(self):
        vierge = _lead()
        self.assertIn('occupation_jour',
                      _champs(panneau.questions_a_poser(vierge)))

        repondu = _lead(occupation_jour=Lead.OccupationJour.PRESENT)
        self.assertNotIn('occupation_jour',
                         _champs(panneau.questions_a_poser(repondu)))
        self.assertEqual(panneau.prefill_du_panneau(repondu)['occupation_jour'],
                         'present')

    def test_un_faux_est_une_REPONSE_pas_un_silence(self):
        """« Non, pas de piscine » est une réponse : on ne la repose pas."""
        lead = _lead(equip_piscine=False)
        self.assertNotIn('equip_piscine',
                         _champs(panneau.questions_a_poser(lead)))
        self.assertIs(panneau.prefill_du_panneau(lead)['equip_piscine'], False)

    def test_un_zero_est_une_REPONSE_pas_un_silence(self):
        lead = _lead(equip_clim_pieces=0)
        self.assertNotIn('equip_clim_pieces',
                         _champs(panneau.questions_a_poser(lead)))
        self.assertEqual(panneau.prefill_du_panneau(lead)['equip_clim_pieces'],
                         0)

    def test_aucune_question_en_double(self):
        questions = panneau.questions_a_poser(_lead())
        champs = _champs(questions)
        self.assertEqual(len(champs), len(set(champs)))

    def test_la_tranche_onee_n_est_JAMAIS_demandee(self):
        """Texte libre qu'aucun calcul ne lit : elle se DÉRIVE du barème."""
        lead = _lead()
        self.assertNotIn('tranche_onee', _champs(panneau.questions_a_poser(lead)))
        self.assertNotIn('tranche_onee', panneau.prefill_du_panneau(lead))
        renseigne = _lead(tranche_onee='Tranche 3')
        self.assertNotIn('tranche_onee',
                         panneau.prefill_du_panneau(renseigne))


class AucuneValeurParDefaut(SimpleTestCase):
    def test_un_lead_sans_aucune_reponse_a_un_prefill_VIDE(self):
        self.assertEqual(panneau.prefill_du_panneau(_lead()), {})

    def test_le_defaut_d_une_colonne_NOT_NULL_n_est_pas_publie(self):
        """`ete_differente` vaut False dès la création : ce n'est pas une
        réponse du client. Elle reste une question, et le pré-remplissage se
        tait — sinon le panneau servirait un DÉFAUT."""
        vierge = _lead()
        self.assertNotIn('ete_differente', panneau.prefill_du_panneau(vierge))
        self.assertIn('ete_differente', _champs(
            panneau.questions_a_poser(vierge)))
        repondu = _lead(ete_differente=True)
        self.assertIs(
            panneau.prefill_du_panneau(repondu)['ete_differente'], True)
        self.assertNotIn('ete_differente', _champs(
            panneau.questions_a_poser(repondu)))

    def test_le_prefill_ne_porte_que_des_valeurs_reelles(self):
        lead = _lead(facture_hiver=Decimal('1200.00'), ville='Bouskoura')
        prefill = panneau.prefill_du_panneau(lead)
        self.assertEqual(prefill['facture_hiver'], 1200.0)
        self.assertEqual(prefill['ville'], 'Bouskoura')
        # Rien d'autre n'a été renseigné : rien d'autre n'est servi.
        self.assertEqual(set(prefill), {'facture_hiver', 'ville'})

    def test_une_chaine_blanche_n_est_pas_une_reponse(self):
        lead = _lead(ville='   ')
        self.assertNotIn('ville', panneau.prefill_du_panneau(lead))
        self.assertIn('ville', _champs(panneau.questions_a_poser(lead)))


class ChaqueQuestionVientDuChampLuiMeme(SimpleTestCase):
    def test_le_texte_de_la_question_est_le_help_text_du_champ(self):
        """« Chaque champ EST le script d'appel » : aucune variante ailleurs."""
        questions = {q['champ']: q for q in panneau.questions_a_poser(_lead())}
        for champ, question in questions.items():
            attendu = str(Lead._meta.get_field(champ).help_text or '')
            self.assertEqual(question['question'], attendu, champ)

    def test_un_champ_a_vocabulaire_ferme_sert_ses_choix_dans_l_ordre(self):
        questions = {q['champ']: q for q in panneau.questions_a_poser(_lead())}
        occupation = questions['occupation_jour']
        self.assertEqual([c['valeur'] for c in occupation['choix']],
                         ['present', 'absent', 'partiel'])

    def test_un_champ_a_saisie_libre_n_a_aucun_choix(self):
        questions = {q['champ']: q for q in panneau.questions_a_poser(_lead())}
        self.assertIsNone(questions['facture_hiver']['choix'])


class LesQuestionsORALES(SimpleTestCase):
    """Décision fondateur du 21/09/2026 : budget, délai, décideur et
    concurrents ne se posent qu'à l'oral — donc hors du questionnaire envoyé
    au client, mais BIEN dans le panneau d'appel."""

    def test_decideur_et_concurrents_sont_proposes_a_l_appel(self):
        champs = _champs(panneau.questions_a_poser(_lead()))
        self.assertIn('decideur', champs)
        self.assertIn('devis_concurrents', champs)

    def test_ils_restent_hors_du_questionnaire_envoye_au_client(self):
        toutes = set()
        for colonnes in questionnaire.CHAMPS_PAR_SECTION.values():
            toutes.update(colonnes)
        self.assertNotIn('decideur', toutes)
        self.assertNotIn('devis_concurrents', toutes)

    def test_une_question_orale_n_a_pas_de_section(self):
        questions = {q['champ']: q for q in panneau.questions_a_poser(_lead())}
        self.assertIsNone(questions['decideur']['section'])
        self.assertEqual(questions['occupation_jour']['section'], 'occupation')

    def test_les_questions_de_pompage_ne_sortent_QUE_en_agricole(self):
        resid = _champs(panneau.questions_a_poser(
            _lead(type_installation=Lead.TypeInstallation.RESIDENTIEL)))
        self.assertNotIn('pompage_heures_jour', resid)
        agri = _champs(panneau.questions_a_poser(
            _lead(type_installation=Lead.TypeInstallation.AGRICOLE)))
        for champ in ('pompage_heures_jour', 'pompe_alim_actuelle',
                      'carburant_litres_mois'):
            self.assertIn(champ, agri)


class LeDrapeauCompteDansLEtude(SimpleTestCase):
    """Le cœur de la tâche : « déclaré » n'est pas « compté ». Un équipement
    déclaré sans sa grandeur ne compose AUCUNE couche — le chiffre montré au
    client ne le contient pas, et il faut le dire."""

    @staticmethod
    def _par_cle(lead):
        return {e['cle']: e for e in panneau.drapeaux_equipements(lead)}

    def test_une_clim_declaree_SANS_kW_ni_pieces_n_est_PAS_comptee(self):
        clim = self._par_cle(_lead(equip_clim=True))['clim']
        self.assertTrue(clim['declare'])
        self.assertFalse(clim['compte_dans_etude'])
        self.assertEqual(clim['champs_manquants'],
                         ['equip_clim_kw', 'equip_clim_pieces'])

    def test_la_meme_clim_AVEC_sa_puissance_est_comptee(self):
        clim = self._par_cle(
            _lead(equip_clim=True, equip_clim_kw=Decimal('2.80')))['clim']
        self.assertTrue(clim['compte_dans_etude'])
        self.assertEqual(clim['champs_manquants'], [])

    def test_une_piscine_declaree_sans_pompe_nomme_le_champ_qui_manque(self):
        piscine = self._par_cle(_lead(equip_piscine=True))['piscine']
        self.assertFalse(piscine['compte_dans_etude'])
        self.assertEqual(piscine['champs_manquants'],
                         ['equip_piscine_pompe_kw'])

    def test_un_equipement_NON_declare_ne_reclame_rien(self):
        ve = self._par_cle(_lead(equip_voiture_electrique=False))['ve']
        self.assertFalse(ve['declare'])
        self.assertFalse(ve['compte_dans_etude'])
        self.assertEqual(ve['champs_manquants'], [])

    def test_les_quatre_couches_sont_toujours_servies_dans_l_ordre(self):
        cles = [e['cle'] for e in panneau.drapeaux_equipements(_lead())]
        self.assertEqual(cles, ['piscine', 'clim', 've', 'chauffe_eau'])


class LePanneauServiParLEndpoint(TestCase):
    """Le chemin COMPLET : touche en cours, script rendu, réponse HTTP.

    Ces tests ont besoin de l'ORM (les touches de cadence sont des lignes) —
    ils sont ÉCRITS ici et exécutés par la CI."""

    def setUp(self):
        self.company = Company.objects.create(nom='CAD148 Co', slug='cad148-co')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect',
            type_installation=Lead.TypeInstallation.RESIDENTIEL,
            occupation_jour=Lead.OccupationJour.PRESENT)

    def test_sans_cadence_active_la_touche_et_le_script_sont_nuls(self):
        data = panneau.panneau_appel(self.lead)
        self.assertIsNone(data['touche'])
        self.assertIsNone(data['script'])
        # Le panneau reste utile : les questions, elles, se posent toujours.
        self.assertTrue(data['champs_a_poser'])

    def test_la_touche_servie_est_la_prochaine_A_FAIRE(self):
        faite = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=1,
            due_date='2026-09-20', canal=RelanceEtape.Canal.APPEL,
            statut=RelanceEtape.Statut.FAIT)
        a_faire = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=2,
            due_date='2026-09-23', canal=RelanceEtape.Canal.APPEL,
            template_cle='appel_j2', statut=RelanceEtape.Statut.A_FAIRE)
        data = panneau.panneau_appel(self.lead)
        self.assertEqual(data['touche']['id'], a_faire.pk)
        self.assertNotEqual(data['touche']['id'], faite.pk)
        self.assertEqual(data['touche']['rang'], 2)
        self.assertEqual(data['touche']['canal'], 'appel')

    def test_le_script_reprend_la_forme_relance_etape_message_sans_wa_url(self):
        RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=1,
            due_date='2026-09-23', canal=RelanceEtape.Canal.APPEL,
            template_cle='appel_j2', statut=RelanceEtape.Statut.A_FAIRE)
        script = panneau.panneau_appel(self.lead)['script']
        self.assertEqual(set(script),
                         {'message', 'langue', 'placeholders_manquants'})
        self.assertNotIn('wa_url', script)

    def test_le_segment_du_lead_est_servi_avec_son_libelle(self):
        data = panneau.panneau_appel(self.lead)
        self.assertEqual(data['segment'], 'residentiel')
        self.assertEqual(data['segment_libelle'], 'Résidentiel')

    def test_un_lead_d_une_AUTRE_societe_est_introuvable(self):
        """Multi-tenant : la portée vient de `get_object()`, jamais du corps."""
        autre = Company.objects.create(nom='Autre Co', slug='cad148-autre')
        lead_autre = Lead.objects.create(company=autre, nom='Ailleurs')
        user = self._utilisateur(self.company)
        client = APIClient()
        client.force_authenticate(user=user)
        res = client.get(f'/api/django/crm/leads/{lead_autre.pk}/panneau-appel/')
        self.assertEqual(res.status_code, 404, res.content)

    def test_l_endpoint_sert_le_panneau_de_son_propre_lead(self):
        user = self._utilisateur(self.company)
        client = APIClient()
        client.force_authenticate(user=user)
        res = client.get(f'/api/django/crm/leads/{self.lead.pk}/panneau-appel/')
        self.assertEqual(res.status_code, 200, res.content)
        corps = res.json()
        self.assertEqual(corps['lead_id'], self.lead.pk)
        # CAD155 — `fenetre_du_jour` rejoint la racine (même contrat).
        self.assertEqual(
            set(corps),
            {'lead_id', 'segment', 'segment_libelle', 'touche', 'script',
             'champs_a_poser', 'prefill', 'equipements', 'fenetre_du_jour'})
        # La réponse déjà donnée n'est pas reposée.
        self.assertNotIn('occupation_jour', _champs(corps['champs_a_poser']))
        self.assertEqual(corps['prefill']['occupation_jour'], 'present')

    @staticmethod
    def _utilisateur(company):
        from django.contrib.auth import get_user_model
        modele = get_user_model()
        return modele.objects.create_user(
            username=f'cad148-{company.slug}', password='x',
            company=company, is_staff=True, is_superuser=True)
