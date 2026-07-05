"""ZMKT12 — Partage d'enquête par lien / email / QR + descriptif d'accueil
et message de fin.

Couvre : le QR se télécharge, l'invitation email cible un segment/liste et
respecte consentement+suppression (XMKT3/XMKT4), l'accueil et le message
de fin s'affichent au bon moment, no-op sans clé, tests.
"""
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    AbonnementListe, ListeDiffusion, SegmentMarketing, SuppressionMarketing,
)
from apps.crm.models import Lead


QUESTIONS = [{'id': 'q1', 'type': 'texte', 'libelle': 'Q1'}]


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class PartageEnqueteTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt12', 'ZMKT12')

    def test_qr_svg_telechargeable(self):
        enquete = services.creer_enquete(self.co, titre='E', questions=QUESTIONS)
        svg = services.qr_svg_enquete(enquete)
        self.assertTrue(svg.startswith('<svg'))

    def test_accueil_et_fin_dans_rendu(self):
        enquete = services.creer_enquete(self.co, titre='E2', questions=QUESTIONS)
        enquete.description_accueil = 'Bienvenue !'
        enquete.message_fin = 'Merci !'
        enquete.save(update_fields=['description_accueil', 'message_fin'])
        rendu = services.rendre_enquete_publique(enquete, {})
        self.assertEqual(rendu['description_accueil'], 'Bienvenue !')
        self.assertEqual(rendu['message_fin'], 'Merci !')

    def test_invitation_liste_respecte_suppression(self):
        enquete = services.creer_enquete(self.co, titre='E3', questions=QUESTIONS)
        liste = ListeDiffusion.objects.create(company=self.co, nom='L')
        AbonnementListe.objects.create(
            company=self.co, liste=liste, destinataire='ok@x.ma',
            statut=AbonnementListe.Statut.INSCRIT)
        AbonnementListe.objects.create(
            company=self.co, liste=liste, destinataire='supprime@x.ma',
            statut=AbonnementListe.Statut.INSCRIT)
        SuppressionMarketing.objects.create(
            company=self.co, destinataire='supprime@x.ma')
        resultat = services.inviter_enquete(enquete, liste=liste)
        self.assertEqual(resultat['destinataires_cibles'], 1)

    def test_invitation_segment_cible_leads(self):
        enquete = services.creer_enquete(self.co, titre='E4', questions=QUESTIONS)
        Lead.objects.create(
            company=self.co, nom='Lead1', ville='Casablanca',
            email='lead1@x.ma')
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='Casa', regles={'ville': 'Casablanca'})
        resultat = services.inviter_enquete(enquete, segment=segment)
        self.assertEqual(resultat['destinataires_cibles'], 1)

    def test_no_op_sans_cle_brevo(self):
        enquete = services.creer_enquete(self.co, titre='E5', questions=QUESTIONS)
        liste = ListeDiffusion.objects.create(company=self.co, nom='L2')
        resultat = services.inviter_enquete(enquete, liste=liste)
        self.assertFalse(resultat['envoye_reel'])

    def test_isolation_multi_tenant(self):
        other = make_company('zmkt12-b', 'ZMKT12-B')
        enquete = services.creer_enquete(self.co, titre='E6', questions=QUESTIONS)
        liste = ListeDiffusion.objects.create(company=other, nom='AutreListe')
        resultat = services.inviter_enquete(enquete, liste=liste)
        # La liste d'une autre société n'a aucun abonnement lié (isolation).
        self.assertEqual(resultat['destinataires_cibles'], 0)
