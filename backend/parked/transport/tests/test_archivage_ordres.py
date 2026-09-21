"""NTLOG39 — tâche Celery beat mensuelle `transport.
archiver_ordres_transport_anciens` : archive (jamais supprime) les
`OrdreTransport` livrés depuis plus de `ParametresTransport.
archive_ordres_apres_mois` mois (défaut 24). Un ordre archivé disparaît de
`ordres-transport/` par défaut mais reste accessible via
`?inclure_archives=1`."""
from django.test import TestCase
from django.utils import timezone

from apps.transport.models import OrdreTransport, ParametresTransport
from apps.transport.tasks import archiver_ordres_transport_anciens

from ._helpers import auth, make_company, make_user

BASE = '/api/django/transport/ordres-transport/'


def _ordre_livre_il_y_a(company, jours):
    ordre = OrdreTransport.objects.create(
        company=company, statut=OrdreTransport.Statut.LIVRE)
    OrdreTransport.objects.filter(pk=ordre.pk).update(
        updated_at=timezone.now() - timezone.timedelta(days=jours))
    return ordre


class ArchivageOrdresAnciensTests(TestCase):
    def setUp(self):
        self.company = make_company('transport-arch-a', 'A')
        self.user = make_user(self.company, 'transport-arch-a')

    def test_ordre_livre_depuis_25_mois_avec_seuil_24_est_archive(self):
        ancien = _ordre_livre_il_y_a(self.company, jours=25 * 30)
        archiver_ordres_transport_anciens()
        ancien.refresh_from_db()
        self.assertTrue(ancien.archive)

    def test_ordre_livre_depuis_20_mois_avec_seuil_24_reste_visible(self):
        recent = _ordre_livre_il_y_a(self.company, jours=20 * 30)
        archiver_ordres_transport_anciens()
        recent.refresh_from_db()
        self.assertFalse(recent.archive)

    def test_ordre_non_livre_jamais_archive(self):
        ordre = OrdreTransport.objects.create(
            company=self.company, statut=OrdreTransport.Statut.BROUILLON)
        OrdreTransport.objects.filter(pk=ordre.pk).update(
            updated_at=timezone.now() - timezone.timedelta(days=25 * 30))
        archiver_ordres_transport_anciens()
        ordre.refresh_from_db()
        self.assertFalse(ordre.archive)

    def test_seuil_configurable_par_societe(self):
        ParametresTransport.objects.create(
            company=self.company, archive_ordres_apres_mois=6)
        ordre = _ordre_livre_il_y_a(self.company, jours=7 * 30)
        archiver_ordres_transport_anciens()
        ordre.refresh_from_db()
        self.assertTrue(ordre.archive)

    def test_ordre_archive_disparait_de_la_liste_par_defaut(self):
        ancien = _ordre_livre_il_y_a(self.company, jours=25 * 30)
        archiver_ordres_transport_anciens()
        ancien.refresh_from_db()
        self.assertTrue(ancien.archive)

        resp = auth(self.user).get(BASE)
        ids = [o['id'] for o in resp.data['results']] if isinstance(resp.data, dict) else [o['id'] for o in resp.data]
        self.assertNotIn(ancien.id, ids)

    def test_ordre_archive_reste_accessible_via_filtre(self):
        ancien = _ordre_livre_il_y_a(self.company, jours=25 * 30)
        archiver_ordres_transport_anciens()

        resp = auth(self.user).get(BASE, {'inclure_archives': '1'})
        ids = [o['id'] for o in resp.data['results']] if isinstance(resp.data, dict) else [o['id'] for o in resp.data]
        self.assertIn(ancien.id, ids)
