"""CAL207 — verrouiller le calepinage après envoi du devis lié.

Ce qui est prouvé ici :

* sans devis lié, ou devis ``brouillon`` ou ``envoyé`` (ACAL42, D-QJR5-5 :
  un envoyé se corrige), écrire une conception marche ;
* devis ``accepté`` : écrire une conception refuse, 409, champ nommé, motif
  de ventes mot pour mot ;
* plus AUCUN déverrouillage (ACAL42 : le seul geste est « Réviser ») ;
* la restauration de version (CAL20) hérite du MÊME refus (même chemin
  d'écriture, CAL203) ;
* le statut du devis n'est JAMAIS touché par ces gestes (règle #4).

Run :
    python manage.py test apps.calepinage.tests.test_cal207_verrou -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import APIException

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services import verrou as module_verrou
from apps.calepinage.services.verrou import VerrouilleRefuse, est_verrouille
from apps.calepinage.services.versions import restaurer_version
from apps.crm.models import Client
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


class VerrouTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Verrou Co',
                                              slug='verrou-co-207')
        self.role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='verrou_207', password='x', company=self.company,
            role=self.role)
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Client Verrou')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-CAL207-1', statut=Devis.Statut.BROUILLON)
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=self.devis)

    def test_sans_devis_ecrire_marche(self):
        libre = Calepinage.objects.create(company=self.company,
                                          client=self.client_a)
        self.assertFalse(est_verrouille(libre))
        enregistrer_layout(libre, {'panels': 3}, user=self.user)

    def test_devis_brouillon_ecrire_marche(self):
        self.assertFalse(est_verrouille(self.calepinage))
        enregistrer_layout(self.calepinage, {'panels': 3}, user=self.user)

    def test_devis_envoye_ecrire_marche(self):
        self.devis.statut = Devis.Statut.ENVOYE
        self.devis.save(update_fields=['statut'])
        self.assertFalse(est_verrouille(self.calepinage))
        enregistrer_layout(self.calepinage, {'panels': 3}, user=self.user)

    def test_devis_accepte_ecrire_refuse_409(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        self.assertTrue(est_verrouille(self.calepinage))
        with self.assertRaises(APIException) as ctx:
            enregistrer_layout(self.calepinage, {'panels': 3}, user=self.user)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn('roof_layout', ctx.exception.detail)
        self.assertIn('Devis accepté : révisez-le',
                      str(ctx.exception.detail['roof_layout'][0]))

    def test_aucune_porte_de_deverrouillage(self):
        self.assertFalse(hasattr(module_verrou, 'deverrouiller'))
        self.assertFalse(hasattr(module_verrou, 'reverrouiller'))

    def test_devis_statut_jamais_touche(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        with self.assertRaises(VerrouilleRefuse):
            enregistrer_layout(self.calepinage, {'panels': 3}, user=self.user)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)

    def test_restauration_de_version_herite_du_refus(self):
        enregistrer_layout(self.calepinage, {'panels': 3}, user=self.user)
        version = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).order_by('-created_at').first()
        self.assertIsNotNone(version)

        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        with self.assertRaises(VerrouilleRefuse):
            restaurer_version(version, user=self.user)
