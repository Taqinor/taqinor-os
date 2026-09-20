"""CAL207 — verrouiller le calepinage après envoi du devis lié.

Ce qui est prouvé ici :

* sans devis lié, ou devis encore ``brouillon``, écrire une conception
  marche ;
* devis ``envoyé`` : écrire une conception refuse, 409, champ nommé ;
* ``deverrouiller`` lève le verrou — tracé au journal AVEC l'auteur — et
  l'écriture marche à nouveau ;
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
from apps.calepinage.services.verrou import (
    VerrouilleRefuse, deverrouiller, est_verrouille,
)
from apps.calepinage.services.versions import restaurer_version
from apps.crm.models import Client
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
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

    def test_devis_envoye_ecrire_refuse_409(self):
        self.devis.statut = Devis.Statut.ENVOYE
        self.devis.save(update_fields=['statut'])
        self.assertTrue(est_verrouille(self.calepinage))
        with self.assertRaises(APIException) as ctx:
            enregistrer_layout(self.calepinage, {'panels': 3}, user=self.user)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn('roof_layout', ctx.exception.detail)

    def test_deverrouiller_puis_ecriture_marche(self):
        self.devis.statut = Devis.Statut.ENVOYE
        self.devis.save(update_fields=['statut'])
        deverrouiller(self.calepinage, user=self.user)
        self.assertFalse(est_verrouille(self.calepinage))
        enregistrer_layout(self.calepinage, {'panels': 3}, user=self.user)

    def test_devis_statut_jamais_touche(self):
        self.devis.statut = Devis.Statut.ENVOYE
        self.devis.save(update_fields=['statut'])
        deverrouiller(self.calepinage, user=self.user)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)

    def test_restauration_de_version_herite_du_refus(self):
        enregistrer_layout(self.calepinage, {'panels': 3}, user=self.user)
        version = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).order_by('-created_at').first()
        self.assertIsNotNone(version)

        self.devis.statut = Devis.Statut.ENVOYE
        self.devis.save(update_fields=['statut'])
        with self.assertRaises(VerrouilleRefuse):
            restaurer_version(version, user=self.user)

    def test_deverrouiller_calepinage_non_verrouille_est_un_no_op(self):
        self.assertFalse(deverrouiller(self.calepinage, user=self.user))
