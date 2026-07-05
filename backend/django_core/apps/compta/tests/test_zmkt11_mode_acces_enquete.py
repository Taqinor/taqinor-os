"""ZMKT11 — Mode d'accès, connexion requise et nombre de tentatives
d'enquête + entrée de test.

Couvre : une enquête invités-seulement refuse un token non émis, la
limite de tentatives bloque au-delà de N pour un même email, le test ne
crée aucune participation réelle, défauts = ouvert/illimité (comportement
actuel), migration additive.
"""
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Enquete, ReponseEnquete


QUESTIONS = [{'id': 'q1', 'type': 'texte', 'libelle': 'Q1'}]


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ModeAccesEnqueteTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt11', 'ZMKT11')

    def test_defaut_lien_public_toujours_autorise(self):
        enquete = services.creer_enquete(self.co, titre='E', questions=QUESTIONS)
        self.assertTrue(services.acces_enquete_autorise(enquete))

    def test_invites_seulement_refuse_sans_jeton(self):
        enquete = services.creer_enquete(self.co, titre='E2', questions=QUESTIONS)
        enquete.mode_acces = Enquete.ModeAcces.INVITES_SEULEMENT
        enquete.save(update_fields=['mode_acces'])
        self.assertFalse(services.acces_enquete_autorise(enquete))

    def test_invites_seulement_refuse_jeton_non_emis(self):
        enquete = services.creer_enquete(self.co, titre='E3', questions=QUESTIONS)
        enquete.mode_acces = Enquete.ModeAcces.INVITES_SEULEMENT
        enquete.save(update_fields=['mode_acces'])
        self.assertFalse(
            services.acces_enquete_autorise(enquete, jeton_invite='invente'))

    def test_invites_seulement_accepte_jeton_emis(self):
        enquete = services.creer_enquete(self.co, titre='E4', questions=QUESTIONS)
        enquete.mode_acces = Enquete.ModeAcces.INVITES_SEULEMENT
        enquete.save(update_fields=['mode_acces'])
        jeton = services.emettre_jeton_invite(enquete)
        self.assertTrue(
            services.acces_enquete_autorise(enquete, jeton_invite=jeton))

    def test_tentatives_max_bloque_au_dela(self):
        enquete = services.creer_enquete(self.co, titre='E5', questions=QUESTIONS)
        enquete.tentatives_max = 2
        enquete.save(update_fields=['tentatives_max'])
        services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'x'}, contact_ref='a@x.ma')
        services.soumettre_reponse_enquete(
            enquete, reponses={'q1': 'y'}, contact_ref='a@x.ma')
        with self.assertRaises(ValueError):
            services.soumettre_reponse_enquete(
                enquete, reponses={'q1': 'z'}, contact_ref='a@x.ma')

    def test_tentatives_illimitees_par_defaut(self):
        enquete = services.creer_enquete(self.co, titre='E6', questions=QUESTIONS)
        for i in range(5):
            services.soumettre_reponse_enquete(
                enquete, reponses={'q1': str(i)}, contact_ref='b@x.ma')
        self.assertEqual(
            ReponseEnquete.objects.filter(
                enquete=enquete, contact_ref='b@x.ma').count(), 5)

    def test_tester_ne_cree_pas_de_reponse(self):
        enquete = services.creer_enquete(self.co, titre='E7', questions=QUESTIONS)
        services.tester_enquete(enquete)
        self.assertEqual(
            ReponseEnquete.objects.filter(enquete=enquete).count(), 0)

    def test_endpoint_publique_refuse_invites_sans_jeton(self):
        enquete = services.creer_enquete(self.co, titre='E8', questions=QUESTIONS)
        enquete.mode_acces = Enquete.ModeAcces.INVITES_SEULEMENT
        enquete.save(update_fields=['mode_acces'])
        resp = self.client.get(
            f'/api/django/compta/enquetes-publiques/{enquete.token}/')
        self.assertEqual(resp.status_code, 404)
