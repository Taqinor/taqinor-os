"""QJR52 — ``prix_par_kwc`` gelé sur le NET, et les gels historiques corrigés.

CE QUI ÉTAIT FAUX. ``Devis.save`` gèle ``prix_par_kwc`` (Total TTC ÷ kWc) UNE
SEULE FOIS — write-once — et le lisait sur un total TTC qui ignorait
``remise_globale`` : tout devis remisé restait à jamais à un prix par kWc
gonflé, sans chemin de correction.

CE QUE CES TESTS TIENNENT :
1. le gel d'un devis remisé lit le NET (QJR51 en amont) ;
2. un devis SANS remise gèle exactement la même valeur qu'avant ;
3. le champ reste WRITE-ONCE (une valeur posée n'est jamais recalculée) ;
4. la data-migration corrige les SEULS devis remisés, et son ``reverse_code``
   restaure exactement l'état d'avant (les deux sens sont des dérivations pures
   des mêmes données).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_prix_par_kwc -v 2
"""
import importlib
from decimal import Decimal

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

MIGRATION = importlib.import_module(
    'apps.ventes.migrations.0106_qjr52_prix_par_kwc_net')


class _PrixParKwcBase(TestCase):
    def _company(self, slug):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        return company

    def _devis(self, slug, *, remise=Decimal('0'), kwc=6.0):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom=f'Client {slug}', defaults={})[0]
        return Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, statut='brouillon',
            taux_tva=Decimal('20'), remise_globale=remise,
            mode_installation='residentiel',
            etude_params={'puissance_kwc': kwc})

    def _ligne(self, devis, designation, quantite, prix, **extra):
        return LigneDevis.objects.create(
            devis=devis, designation=designation,
            quantite=Decimal(str(quantite)), prix_unitaire=Decimal(str(prix)),
            remise=Decimal('0'), **extra)


class GelSurLeNetTests(_PrixParKwcBase):

    def test_un_devis_remise_gele_sur_le_net(self):
        devis = self._devis('qjr52-net', remise=Decimal('10'), kwc=6.0)
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        devis = Devis.objects.get(pk=devis.pk)
        devis.save()
        devis.refresh_from_db()
        # HT brut 10 000 → net 9 000 → TTC 10 800 ÷ 6 kWc = 1 800,00
        self.assertEqual(devis.prix_par_kwc, Decimal('1800.00'))

    def test_un_devis_sans_remise_gele_la_valeur_d_avant(self):
        devis = self._devis('qjr52-sans', kwc=6.0)
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        devis = Devis.objects.get(pk=devis.pk)
        devis.save()
        devis.refresh_from_db()
        self.assertEqual(devis.prix_par_kwc, Decimal('2000.00'))

    def test_le_champ_reste_write_once(self):
        devis = self._devis('qjr52-once', remise=Decimal('10'), kwc=6.0)
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        devis = Devis.objects.get(pk=devis.pk)
        devis.save()
        devis.refresh_from_db()
        gele = devis.prix_par_kwc
        self._ligne(devis, 'Batterie 10 kWh', 1, 25000)
        devis = Devis.objects.get(pk=devis.pk)
        devis.save()
        devis.refresh_from_db()
        self.assertEqual(devis.prix_par_kwc, gele)

    def test_sans_kwc_le_champ_reste_null(self):
        devis = self._devis('qjr52-pompage', kwc=0)
        self._ligne(devis, 'Pompe 3 CV', 1, 30000)
        devis = Devis.objects.get(pk=devis.pk)
        devis.save()
        devis.refresh_from_db()
        self.assertIsNone(devis.prix_par_kwc)


class DataMigrationTests(_PrixParKwcBase):
    """La migration corrige les SEULS devis remisés, et se défait exactement."""

    def _figer(self, devis, valeur):
        """Pose un ``prix_par_kwc`` comme le faisait le code d'AVANT (brut)."""
        Devis.objects.filter(pk=devis.pk).update(
            prix_par_kwc=Decimal(str(valeur)))

    def test_un_devis_remise_est_corrige(self):
        devis = self._devis('qjr52-mig', remise=Decimal('10'), kwc=6.0)
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        # Gel historique BRUT : 12 000 TTC ÷ 6 = 2 000.
        self._figer(devis, '2000.00')

        MIGRATION.corriger_sur_le_net(django_apps, None)
        devis.refresh_from_db()
        self.assertEqual(devis.prix_par_kwc, Decimal('1800.00'))

    def test_la_migration_est_reversible_a_l_identique(self):
        devis = self._devis('qjr52-rev', remise=Decimal('10'), kwc=6.0)
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        self._figer(devis, '2000.00')

        MIGRATION.corriger_sur_le_net(django_apps, None)
        MIGRATION.revenir_au_brut(django_apps, None)
        devis.refresh_from_db()
        self.assertEqual(devis.prix_par_kwc, Decimal('2000.00'))

    def test_un_devis_sans_remise_n_est_pas_touche(self):
        devis = self._devis('qjr52-intact', kwc=6.0)
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        self._figer(devis, '1234.56')

        MIGRATION.corriger_sur_le_net(django_apps, None)
        devis.refresh_from_db()
        self.assertEqual(devis.prix_par_kwc, Decimal('1234.56'))

    def test_un_devis_non_gele_reste_null(self):
        devis = self._devis('qjr52-null', remise=Decimal('10'), kwc=6.0)
        self._ligne(devis, 'Panneau 550 W', 10, 1000)
        Devis.objects.filter(pk=devis.pk).update(prix_par_kwc=None)

        MIGRATION.corriger_sur_le_net(django_apps, None)
        devis.refresh_from_db()
        self.assertIsNone(devis.prix_par_kwc)

    def test_les_taux_mixtes_passent_par_la_meme_chaine(self):
        devis = self._devis('qjr52-mixte', remise=Decimal('10'), kwc=6.0)
        self._ligne(devis, 'Panneau 550 W', 10, 1000, taux_tva=Decimal('20'))
        self._ligne(devis, 'Pose', 1, 5000, taux_tva=Decimal('10'))
        self._figer(devis, '9999.99')

        MIGRATION.corriger_sur_le_net(django_apps, None)
        devis.refresh_from_db()
        # HT brut 15 000 → net 13 500 ; TVA = 9 000×20 % + 4 500×10 % = 2 250 ;
        # TTC 15 750 ÷ 6 = 2 625,00.
        self.assertEqual(devis.prix_par_kwc, Decimal('2625.00'))
