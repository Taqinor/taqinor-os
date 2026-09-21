"""AUD621 — enquêtes publiques : jeton d'invitation consommé,
``tentatives_max`` incontournable, ``connexion_requise`` réellement appliqué.

Trois trous confirmés par l'audit :

1. aucun code ne retirait ni ne marquait un jeton après une soumission
   réussie — un lien ``?invite=`` partagé servait un nombre ILLIMITÉ de
   répondants ;
2. ``tentatives_max`` n'était appliqué QUE si ``contact_ref`` était fourni —
   or c'est un champ LIBRE du POST, jamais vérifié contre une identité
   réelle : l'omettre ou le changer contournait la limite ;
3. ``connexion_requise`` n'avait AUCUNE occurrence dans les services/vues —
   déclaré sur le modèle, jamais appliqué.

Tests ROUGES d'abord : ``test_jeton_invite_nest_pas_reutilisable``,
``test_tentatives_max_incontournable_sans_contact_ref`` et
``test_connexion_requise_refuse_une_soumission_anonyme`` réussissaient tous
les trois AVANT le correctif.
"""
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Enquete, ReponseEnquete

QUESTIONS = [{'id': 'q1', 'type': 'texte', 'libelle': 'Q1'}]


class JetonInviteConsommeTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud621', nom='AUD621')
        self.enquete = services.creer_enquete(
            self.co, titre='E', questions=QUESTIONS)
        self.enquete.mode_acces = Enquete.ModeAcces.INVITES_SEULEMENT
        self.enquete.save(update_fields=['mode_acces'])
        self.jeton = services.emettre_jeton_invite(self.enquete)

    def _soumettre(self, jeton=None, **kwargs):
        return services.soumettre_reponse_enquete(
            self.enquete, reponses={'q1': 'x'},
            jeton_invite=self.jeton if jeton is None else jeton, **kwargs)

    def test_jeton_invite_nest_pas_reutilisable(self):
        """ROUGE avant correctif : la 2e soumission passait."""
        self._soumettre()
        with self.assertRaises(ValueError):
            self._soumettre()
        self.assertEqual(
            ReponseEnquete.objects.filter(enquete=self.enquete).count(), 1)

    def test_jeton_epuise_nouvre_plus_la_lecture(self):
        """La consommation vaut aussi pour l'accès aux questions."""
        self.assertTrue(services.acces_enquete_autorise(
            self.enquete, jeton_invite=self.jeton))
        self._soumettre()
        self.assertFalse(services.acces_enquete_autorise(
            self.enquete, jeton_invite=self.jeton))

    def test_tentatives_max_sapplique_au_jeton(self):
        """``tentatives_max=2`` = deux usages DU JETON, pas deux
        ``contact_ref`` auto-déclarés."""
        self.enquete.tentatives_max = 2
        self.enquete.save(update_fields=['tentatives_max'])
        self._soumettre()
        self._soumettre()
        with self.assertRaises(ValueError):
            self._soumettre()

    def test_tentatives_max_incontournable_sans_contact_ref(self):
        """ROUGE avant correctif : sans ``contact_ref``, la limite ne
        s'appliquait pas du tout — répondre à l'infini."""
        self.enquete.tentatives_max = 1
        self.enquete.save(update_fields=['tentatives_max'])
        self._soumettre(contact_ref='')
        with self.assertRaises(ValueError):
            self._soumettre(contact_ref='')

    def test_changer_de_contact_ref_ne_reinitialise_plus_le_compteur(self):
        """ROUGE avant correctif : changer le champ libre repartait à zéro."""
        self._soumettre(contact_ref='a@x.ma')
        with self.assertRaises(ValueError):
            self._soumettre(contact_ref='b@x.ma')

    def test_un_autre_jeton_emis_reste_utilisable(self):
        """La consommation est PAR jeton : elle n'invalide pas les autres
        invitations de la même enquête."""
        autre = services.emettre_jeton_invite(self.enquete)
        self._soumettre()
        self._soumettre(jeton=autre)
        self.assertEqual(
            ReponseEnquete.objects.filter(enquete=self.enquete).count(), 2)

    def test_jeton_non_emis_refuse(self):
        with self.assertRaises(ValueError):
            self._soumettre(jeton='invente')

    def test_sans_jeton_refuse_en_mode_invites(self):
        with self.assertRaises(ValueError):
            self._soumettre(jeton='')

    def test_le_jeton_consomme_est_trace_sur_la_reponse(self):
        reponse = self._soumettre()
        self.assertEqual(reponse.jeton_invite, self.jeton)


class ConnexionRequiseTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud621c', nom='AUD621C')
        self.enquete = services.creer_enquete(
            self.co, titre='E', questions=QUESTIONS)
        self.enquete.connexion_requise = True
        self.enquete.save(update_fields=['connexion_requise'])

    def test_connexion_requise_refuse_une_soumission_anonyme(self):
        """ROUGE avant correctif : le drapeau n'était jamais lu."""
        with self.assertRaises(ValueError):
            services.soumettre_reponse_enquete(
                self.enquete, reponses={'q1': 'x'}, contact_ref='')

    def test_connexion_requise_refuse_un_contact_ref_blanc(self):
        with self.assertRaises(ValueError):
            services.soumettre_reponse_enquete(
                self.enquete, reponses={'q1': 'x'}, contact_ref='   ')

    def test_connexion_requise_accepte_un_repondant_identifie(self):
        reponse = services.soumettre_reponse_enquete(
            self.enquete, reponses={'q1': 'x'}, contact_ref='a@x.ma')
        self.assertEqual(reponse.contact_ref, 'a@x.ma')

    def test_sans_le_drapeau_lanonymat_reste_permis(self):
        ouverte = services.creer_enquete(
            self.co, titre='Ouverte', questions=QUESTIONS)
        reponse = services.soumettre_reponse_enquete(
            ouverte, reponses={'q1': 'x'}, contact_ref='')
        self.assertEqual(reponse.contact_ref, '')


class EndpointPublicEnqueteTests(TestCase):
    """Le trou le plus direct : l'endpoint de SOUMISSION ne vérifiait aucun
    accès (seule la lecture des questions le faisait)."""

    def setUp(self):
        self.co = Company.objects.create(slug='aud621e', nom='AUD621E')
        self.enquete = services.creer_enquete(
            self.co, titre='E', questions=QUESTIONS)
        self.enquete.mode_acces = Enquete.ModeAcces.INVITES_SEULEMENT
        self.enquete.save(update_fields=['mode_acces'])
        self.jeton = services.emettre_jeton_invite(self.enquete)
        self.url = (
            f'/api/django/compta/enquetes-publiques/{self.enquete.token}/'
            f'soumettre/')

    def _post(self, query=''):
        return self.client.post(
            self.url + query, {'reponses': {'q1': 'x'}},
            content_type='application/json')

    def test_soumission_sans_jeton_refusee(self):
        """ROUGE avant correctif : 201 sans le moindre jeton."""
        resp = self._post()
        self.assertEqual(resp.status_code, 404, resp.content)
        self.assertEqual(
            ReponseEnquete.objects.filter(enquete=self.enquete).count(), 0)

    def test_soumission_avec_jeton_valide_acceptee_une_seule_fois(self):
        premiere = self._post(f'?invite={self.jeton}')
        self.assertEqual(premiere.status_code, 201, premiere.content)
        seconde = self._post(f'?invite={self.jeton}')
        self.assertEqual(seconde.status_code, 404, seconde.content)
        self.assertEqual(
            ReponseEnquete.objects.filter(enquete=self.enquete).count(), 1)
