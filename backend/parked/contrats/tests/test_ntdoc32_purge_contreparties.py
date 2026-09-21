"""Tests NTDOC32 — Beat de purge des dépôts contrepartie ARCHIVÉS.

Critère d'acceptation :
- une contrepartie archivée depuis PLUS longtemps que la politique de rétention
  configurée est purgée au run suivant ;
- une contrepartie archivée RÉCEMMENT est conservée ;
- la durée n'est JAMAIS codée en dur : sans politique de rétention, rien n'est
  purgé ;
- best-effort par société : une société en échec n'empêche jamais les suivantes.
"""
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats import scheduled, services
from apps.contrats.models import Contrat, DocumentContrepartie
from apps.ged.models import PolitiqueRetention


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class PurgeContrepartiesTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc32', 'Purge')
        self.contrat = Contrat.objects.create(company=self.co, objet='C')

    def _depot(self, *, archive=False, jours_depuis_archivage=0):
        depot = DocumentContrepartie.objects.create(
            company=self.co, contrat=self.contrat,
            fichier_key='k/1.pdf', nom_fichier='x.pdf')
        if archive:
            DocumentContrepartie.objects.filter(id=depot.id).update(
                archive=True,
                date_archivage=timezone.now() - timedelta(
                    days=jours_depuis_archivage))
            depot.refresh_from_db()
        return depot

    def _politique(self, jours, *, type_document='contrat'):
        return PolitiqueRetention.objects.create(
            company=self.co, nom=f'Contrats {jours} j',
            type_document=type_document, duree_conservation_jours=jours,
            actif=True)

    def test_archive_au_dela_de_la_retention_est_purge(self):
        self._politique(30)
        self._depot(archive=True, jours_depuis_archivage=45)
        res = services.purger_contreparties_archivees(self.co)
        self.assertEqual(res['purges'], 1)
        self.assertEqual(res['duree_jours'], 30)
        self.assertEqual(DocumentContrepartie.objects.count(), 0)

    def test_archive_recemment_est_conserve(self):
        self._politique(30)
        self._depot(archive=True, jours_depuis_archivage=5)
        res = services.purger_contreparties_archivees(self.co)
        self.assertEqual(res['purges'], 0)
        self.assertEqual(DocumentContrepartie.objects.count(), 1)

    def test_non_archive_jamais_touche(self):
        self._politique(1)
        self._depot(archive=False)
        res = services.purger_contreparties_archivees(self.co)
        self.assertEqual(res['purges'], 0)
        self.assertEqual(DocumentContrepartie.objects.count(), 1)

    def test_sans_politique_rien_n_est_purge(self):
        """Aucune durée codée en dur : sans politique, on ne purge RIEN."""
        self._depot(archive=True, jours_depuis_archivage=3650)
        res = services.purger_contreparties_archivees(self.co)
        self.assertEqual(res['purges'], 0)
        self.assertIsNone(res['duree_jours'])
        self.assertEqual(DocumentContrepartie.objects.count(), 1)

    def test_politique_inactive_ignoree(self):
        pol = self._politique(1)
        pol.actif = False
        pol.save(update_fields=['actif'])
        self._depot(archive=True, jours_depuis_archivage=100)
        res = services.purger_contreparties_archivees(self.co)
        self.assertEqual(res['purges'], 0)

    def test_politique_globale_utilisee_a_defaut_de_categorie(self):
        PolitiqueRetention.objects.create(
            company=self.co, nom='Globale', duree_conservation_jours=10,
            actif=True)
        self._depot(archive=True, jours_depuis_archivage=20)
        res = services.purger_contreparties_archivees(self.co)
        self.assertEqual(res['duree_jours'], 10)
        self.assertEqual(res['purges'], 1)

    def test_politique_typee_prime_sur_la_globale(self):
        PolitiqueRetention.objects.create(
            company=self.co, nom='Globale', duree_conservation_jours=365,
            actif=True)
        self._politique(30)
        self._depot(archive=True, jours_depuis_archivage=45)
        res = services.purger_contreparties_archivees(self.co)
        self.assertEqual(res['duree_jours'], 30)
        self.assertEqual(res['purges'], 1)

    def test_isolation_multi_societe(self):
        autre = make_company('ntdoc32-b', 'B')
        contrat_b = Contrat.objects.create(company=autre, objet='B')
        DocumentContrepartie.objects.create(
            company=autre, contrat=contrat_b, fichier_key='k/b.pdf',
            nom_fichier='b.pdf', archive=True,
            date_archivage=timezone.now() - timedelta(days=999))
        self._politique(30)
        self._depot(archive=True, jours_depuis_archivage=45)
        services.purger_contreparties_archivees(self.co)
        # Le dépôt de l'autre société est intact (aucune politique chez elle).
        self.assertEqual(
            DocumentContrepartie.objects.filter(company=autre).count(), 1)


class PurgeContrepartiesBeatTests(TestCase):
    def test_beat_agrege_et_isole_les_societes(self):
        co_a = make_company('ntdoc32-beat-a', 'A')
        co_b = make_company('ntdoc32-beat-b', 'B')
        contrat = Contrat.objects.create(company=co_b, objet='B')
        PolitiqueRetention.objects.create(
            company=co_b, nom='Globale', duree_conservation_jours=10,
            actif=True)
        DocumentContrepartie.objects.create(
            company=co_b, contrat=contrat, fichier_key='k/b.pdf',
            nom_fichier='b.pdf', archive=True,
            date_archivage=timezone.now() - timedelta(days=30))

        reel = services.purger_contreparties_archivees

        def _boom(company, **kwargs):
            if company.pk == co_a.pk:
                raise RuntimeError('société en échec')
            return reel(company, **kwargs)

        with mock.patch.object(
                services, 'purger_contreparties_archivees', side_effect=_boom):
            total = scheduled.purger_contreparties_archivees()

        self.assertEqual(total['purges'], 1)
        self.assertGreaterEqual(total['societes_en_echec'], 1)
        self.assertEqual(DocumentContrepartie.objects.count(), 0)

    def test_tache_celery_enregistree_sous_son_nom(self):
        self.assertEqual(
            scheduled.purger_contreparties_archivees.name,
            'contrats.purger_contreparties_archivees')
