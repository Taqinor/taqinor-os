"""AUD608 — créer une affaire depuis un avis est SÉRIALISÉ.

``creer_appel_offre_depuis_avis`` déduplique par ``reference_acheteur`` avec un
simple « je cherche, je ne trouve pas, je crée ». Deux imports du MÊME avis
lancés ensemble lisent tous les deux « aucune affaire » et en créent DEUX, avec
deux références AO consommées (``core.numbering``, jamais réattribuées) pour un
seul marché.

Aucune ligne d'affaire n'existe encore à verrouiller : le service sérialise donc
sur la ligne SOCIÉTÉ, et UNIQUEMENT sur le chemin de création — le ré-import
(cas courant) ne doit prendre aucun verrou.

Run :
    python manage.py test apps.ao.tests.test_aud608_verrou_creation_affaire -v2
"""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.ao import services
from apps.ao.models import AppelOffre
from authentication.models import Company

AVIS = {
    'reference_acheteur': 'AO 42/2026',
    'objet': 'Centrale photovoltaïque en toiture',
    'acheteur': 'Commune de Test',
}


def _verrous_societe(capture):
    return [q['sql'] for q in capture.captured_queries
            if 'FOR UPDATE' in q['sql'].upper()
            and 'company' in q['sql'].lower()]


class TestVerrouSurLeCheminDeCreation(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD608 AO',
                                              slug='aud608-ao')

    def test_la_creation_verrouille_la_societe(self):
        with CaptureQueriesContext(connection) as capture:
            _affaire, cree = services.creer_appel_offre_depuis_avis(
                self.company, dict(AVIS))
        self.assertTrue(cree)
        self.assertTrue(
            _verrous_societe(capture),
            "La création d'affaire ne prend AUCUN verrou : deux imports "
            'simultanés du même avis créeraient deux affaires.')

    def test_le_reimport_ne_verrouille_rien(self):
        """Le cas COURANT reste sans verrou : on ne sérialise pas pour rien."""
        services.creer_appel_offre_depuis_avis(self.company, dict(AVIS))
        with CaptureQueriesContext(connection) as capture:
            _affaire, cree = services.creer_appel_offre_depuis_avis(
                self.company, dict(AVIS))
        self.assertFalse(cree)
        self.assertEqual(_verrous_societe(capture), [])

    def test_l_idempotence_est_preservee(self):
        premiere, _ = services.creer_appel_offre_depuis_avis(
            self.company, dict(AVIS))
        seconde, cree = services.creer_appel_offre_depuis_avis(
            self.company, dict(AVIS))
        self.assertFalse(cree)
        self.assertEqual(seconde.pk, premiere.pk)
        self.assertEqual(
            AppelOffre.objects.filter(company=self.company).count(), 1)

    def test_le_report_des_champs_survit_au_verrou(self):
        """Le ré-import met toujours à jour les champs de l'avis rectifié."""
        services.creer_appel_offre_depuis_avis(self.company, dict(AVIS))
        rectifie = dict(AVIS, objet='Centrale PV — objet rectifié')
        affaire, _cree = services.creer_appel_offre_depuis_avis(
            self.company, rectifie)
        affaire.refresh_from_db()
        self.assertEqual(affaire.objet, 'Centrale PV — objet rectifié')

    def test_deux_societes_gardent_leur_propre_affaire(self):
        voisine = Company.objects.create(nom='AUD608 AO voisine',
                                         slug='aud608-ao-voisine')
        a, _ = services.creer_appel_offre_depuis_avis(self.company, dict(AVIS))
        b, cree = services.creer_appel_offre_depuis_avis(voisine, dict(AVIS))
        self.assertTrue(cree)
        self.assertNotEqual(a.pk, b.pk)
