"""AUD614 — les avis dépassés expirent enfin tout seuls.

``services.expirer_avis_depasses`` était écrit, testé… et appelé par AUCUN
chemin de production (ni ``tasks.py``, ni le beat). Un avis dont la remise est
passée restait donc « nouveau » indéfiniment dans le sas, et le tri humain se
faisait sur une liste polluée par des marchés déjà clos.

RÈGLE #5 — cette tâche n'a RIEN à voir avec la collecte : elle ne lit aucun
portail et n'ouvre aucune connexion ; elle compare une date déjà en base à
l'horloge. Elle n'est donc pas gardée par ``VEILLE_AO_COLLECTE_ACTIVE``, qui
arme l'ACQUISITION de données — et ce module le PROUVE, plutôt que de
l'affirmer.

Run :
    python manage.py test apps.veille_ao.tests.test_aud614_expiration_beat -v2
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.veille_ao.models import (
    AvisMarche, SourceVeille, StatutAvis, TypeSource,
)
from apps.veille_ao.tasks import expirer_avis_depasses
from authentication.models import Company


class BaseSas(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD614 Veille',
                                              slug='aud614-veille')
        self.source = SourceVeille.objects.create(
            company=self.company, code='tuyau', libelle='Tuyau partenaire',
            type_source=TypeSource.TUYAU_PARTENAIRE, actif=True)

    def _avis(self, jours, **extra):
        params = {
            'company': self.company, 'source': self.source,
            'objet': 'Centrale photovoltaïque',
            'date_limite_remise': timezone.now() + timedelta(days=jours),
        }
        params.update(extra)
        return AvisMarche.objects.create(**params)


class TestExpirationAutomatique(BaseSas):
    def test_un_avis_depasse_bascule_en_expire(self):
        avis = self._avis(-3)
        resultat = expirer_avis_depasses()
        self.assertEqual(resultat['expires'], 1)
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.EXPIRE)

    def test_un_avis_encore_ouvert_ne_bouge_pas(self):
        avis = self._avis(10)
        expirer_avis_depasses()
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.NOUVEAU)

    def test_un_avis_sans_date_limite_n_expire_jamais_seul(self):
        """On ne devine pas une échéance qu'on n'a pas lue."""
        avis = self._avis(0, date_limite_remise=None)
        expirer_avis_depasses()
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.NOUVEAU)

    def test_rejouer_le_beat_n_expire_pas_deux_fois(self):
        self._avis(-3)
        self.assertEqual(expirer_avis_depasses()['expires'], 1)
        self.assertEqual(expirer_avis_depasses()['expires'], 0)

    def test_chaque_societe_est_traitee(self):
        voisine = Company.objects.create(nom='AUD614 Veille voisine',
                                         slug='aud614-veille-voisine')
        source_voisine = SourceVeille.objects.create(
            company=voisine, code='tuyau', libelle='Tuyau',
            type_source=TypeSource.TUYAU_PARTENAIRE, actif=True)
        AvisMarche.objects.create(
            company=voisine, source=source_voisine, objet='Autre',
            date_limite_remise=timezone.now() - timedelta(days=1))
        self._avis(-1)
        self.assertEqual(expirer_avis_depasses()['expires'], 2)


class TestRegle5(BaseSas):
    """L'entretien du sas n'est PAS l'acquisition : aucun désarmement ici."""

    @override_settings(VEILLE_AO_COLLECTE_ACTIVE=False)
    def test_la_tache_agit_meme_collecte_desarmee(self):
        avis = self._avis(-3)
        self.assertEqual(expirer_avis_depasses()['expires'], 1)
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.EXPIRE)
