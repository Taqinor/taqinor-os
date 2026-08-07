"""VAO26 — rétention et purge des avis non retenus.

Le « Done = » :
  * purge idempotente et testée sur les DEUX catégories ;
  * AUCUN avis converti supprimé (test explicite — c'est la garantie qui
    protège la mesure d'attribution de VAO31) ;
  * politique de rétention DÉCLARÉE dans le registre partagé.
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from core.retention import list_retention_policies

from apps.veille_ao.models import (
    AvisMarche, SourceVeille, StatutAvis, TypeSource,
)
from apps.veille_ao.retention import (
    DEFAUT_RETENTION_MOIS, avis_purgeables, purger_avis,
)


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME Rétention')
        self.source = SourceVeille.objects.create(
            company=self.company, code='pmmp', libelle='Portail',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test/', actif=True)

    def _avis(self, statut, *, mois_depuis_limite=18, appel_offre_id=None):
        return AvisMarche.objects.create(
            company=self.company, source=self.source,
            objet=f'Avis {statut}', statut=statut,
            appel_offre_id=appel_offre_id,
            date_limite_remise=(
                timezone.now() - timedelta(days=mois_depuis_limite * 30)))


class RegistreTests(TestCase):
    def test_la_politique_est_declaree_dans_le_registre_partage(self):
        self.assertIn('veille_ao_avis_perimes', list_retention_policies())


class CeQuiEstPurgeTests(_Base):
    def test_un_avis_nouveau_perime_est_purge(self):
        self._avis(StatutAvis.NOUVEAU)
        self.assertEqual(purger_avis(apply_=True), 1)
        self.assertEqual(AvisMarche.objects.count(), 0)

    def test_un_avis_ignore_perime_est_purge(self):
        self._avis(StatutAvis.IGNORE)
        self.assertEqual(purger_avis(apply_=True), 1)
        self.assertEqual(AvisMarche.objects.count(), 0)

    def test_un_avis_encore_dans_la_fenetre_n_est_pas_touche(self):
        self._avis(StatutAvis.NOUVEAU, mois_depuis_limite=3)
        self.assertEqual(purger_avis(apply_=True), 0)
        self.assertEqual(AvisMarche.objects.count(), 1)

    def test_un_avis_SANS_date_limite_n_est_jamais_purge(self):
        """On ne devine pas une échéance qu'on n'a pas lue."""
        AvisMarche.objects.create(
            company=self.company, source=self.source, objet='Sans échéance',
            statut=StatutAvis.NOUVEAU)
        self.assertEqual(purger_avis(apply_=True), 0)
        self.assertEqual(AvisMarche.objects.count(), 1)


class CeQuiNEstJamaisPurgeTests(_Base):
    """La garantie centrale : l'historique commercial est INTOUCHABLE."""

    def test_un_avis_RETENU_n_est_JAMAIS_purge(self):
        self._avis(StatutAvis.RETENU, mois_depuis_limite=120)
        self.assertEqual(purger_avis(apply_=True), 0)
        self.assertEqual(AvisMarche.objects.count(), 1)

    def test_un_avis_CONVERTI_n_est_JAMAIS_purge(self):
        self._avis(StatutAvis.CONVERTI, mois_depuis_limite=120,
                   appel_offre_id=42)
        self.assertEqual(purger_avis(apply_=True), 0)
        self.assertEqual(AvisMarche.objects.count(), 1)

    def test_un_avis_lie_a_une_affaire_survit_meme_avec_un_statut_derive(self):
        """Ceinture ET bretelles : le lien vers l'affaire suffit à protéger."""
        self._avis(StatutAvis.IGNORE, mois_depuis_limite=120,
                   appel_offre_id=7)
        self.assertEqual(purger_avis(apply_=True), 0)
        self.assertEqual(AvisMarche.objects.count(), 1)


class DryRunEtIdempotenceTests(_Base):
    def test_le_dry_run_COMPTE_sans_rien_supprimer(self):
        self._avis(StatutAvis.NOUVEAU)
        self.assertEqual(purger_avis(apply_=False), 1)
        self.assertEqual(AvisMarche.objects.count(), 1)

    def test_la_purge_est_idempotente(self):
        self._avis(StatutAvis.NOUVEAU)
        self.assertEqual(purger_avis(apply_=True), 1)
        self.assertEqual(purger_avis(apply_=True), 0)

    def test_le_compte_du_dry_run_est_celui_de_la_purge(self):
        for _ in range(3):
            self._avis(StatutAvis.NOUVEAU)
        self._avis(StatutAvis.CONVERTI, appel_offre_id=1)
        self.assertEqual(purger_avis(apply_=False), 3)
        self.assertEqual(purger_avis(apply_=True), 3)


class ReglageTests(_Base):
    def test_zero_mois_DESACTIVE_la_purge(self):
        self._avis(StatutAvis.NOUVEAU, mois_depuis_limite=999)
        self.assertEqual(purger_avis(apply_=True, mois=0), 0)
        self.assertEqual(AvisMarche.objects.count(), 1)

    @override_settings(VEILLE_AO_RETENTION_MOIS=24)
    def test_la_fenetre_est_founder_configurable(self):
        self._avis(StatutAvis.NOUVEAU, mois_depuis_limite=18)
        self.assertEqual(purger_avis(apply_=True), 0)
        self._avis(StatutAvis.NOUVEAU, mois_depuis_limite=30)
        self.assertEqual(purger_avis(apply_=True), 1)

    def test_le_defaut_du_depot_est_douze_mois(self):
        self.assertEqual(DEFAUT_RETENTION_MOIS, 12)

    def test_avis_purgeables_ne_touche_rien(self):
        self._avis(StatutAvis.NOUVEAU)
        self.assertEqual(avis_purgeables().count(), 1)
        self.assertEqual(AvisMarche.objects.count(), 1)


class MultiTenantTests(_Base):
    def test_la_purge_est_transverse_mais_chaque_avis_reste_scope(self):
        """Le balayage est SYSTÈME : il traite toutes les sociétés, et ne
        confond jamais leurs avis (le compte le prouve société par société).
        """
        autre = Company.objects.create(nom='Autre société')
        source_autre = SourceVeille.objects.create(
            company=autre, code='pmmp', libelle='Portail',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test/', actif=True)
        AvisMarche.objects.create(
            company=autre, source=source_autre, objet='Retenu ailleurs',
            statut=StatutAvis.RETENU,
            date_limite_remise=timezone.now() - timedelta(days=3000))
        self._avis(StatutAvis.NOUVEAU)

        self.assertEqual(purger_avis(apply_=True), 1)
        self.assertEqual(AvisMarche.objects.filter(company=autre).count(), 1)
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 0)
