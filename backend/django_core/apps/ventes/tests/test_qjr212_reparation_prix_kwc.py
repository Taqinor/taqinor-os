"""QJR212 — la réparation ``prix_par_kwc`` couvre les devis à deux options
SANS remise globale.

TEST ROUGE D'ABORD : un devis à deux options sans remise garde un
``prix_par_kwc`` figé sur la SOMME DES DEUX PANIERS (l'état d'avant QJR51, que
``0106_qjr52_prix_par_kwc_net`` ne répare pas — son prédicat exige
``remise_globale > 0``). Après la migration : la valeur de l'option effective.

La migration est appelée par ses deux fonctions, avec un ``apps`` minimal —
c'est une migration de DONNÉES pure (aucun changement de schéma), donc le
modèle historique et le modèle courant sont identiques.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr212_reparation_prix_kwc -v 2
"""
from decimal import Decimal, ROUND_HALF_UP
from importlib import import_module

from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)
from apps.ventes.utils.options import AVEC_BATTERIE, option_totaux

MIGRATION = import_module(
    'apps.ventes.migrations.0109_qjr212_prix_par_kwc_option_effective')

KWC = Decimal('7.7')

#: Deux options réelles : réseau Huawei d'un côté, hybride Deye + batterie de
#: l'autre. Aucune remise globale — le trou que QJR212 referme.
LIGNES = [
    ('Onduleur réseau Huawei 10kW', '1', '11700'),
    ('Onduleur hybride Deye 10kW', '1', '24000'),
    ('Panneau mono 550W', '14', '1100'),
    ('Batterie 5 kWh', '1', '14000'),
    ('Installation', '1', '4000'),
]


class _AppsShim:
    """``apps`` minimal : la migration ne demande qu'un modèle."""

    def get_model(self, app_label, model_name):
        assert (app_label, model_name) == ('ventes', 'Devis')
        return Devis


def _q(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class TestQJR212(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.compteur = 0

    def _devis(self, lignes=LIGNES, deux_options=True, remise='0', kwc=KWC):
        self.compteur += 1
        params = {'puissance_kwc': str(kwc)} if kwc else {}
        if deux_options:
            params['scenario'] = 'Les deux (Sans + Avec)'
        devis = make_devis(
            self.company, self.user, self.client_obj, lignes,
            remise_globale=remise,
            reference=f'DEV-QJR212-{self.compteur:04d}',
            etude_params=params)
        return devis

    def _somme_des_deux_paniers(self, devis):
        """L'ancienne valeur : le TTC de TOUTES les lignes, sans filtre."""
        lignes = list(devis.lignes.select_related('produit').all())
        return MIGRATION._ttc(devis, lignes)

    def _geler(self, devis, ttc):
        """Fige ``prix_par_kwc`` comme l'ancien ``Devis.save`` le faisait."""
        valeur = _q(ttc / KWC)
        Devis.objects.filter(pk=devis.pk).update(prix_par_kwc=valeur)
        return valeur

    def _lu(self, devis):
        return Devis.objects.get(pk=devis.pk).prix_par_kwc

    def _panier_effectif_ttc(self, devis, option=AVEC_BATTERIE):
        """Le TTC de l'option, par la chaîne RECOPIÉE de la migration."""
        lignes = list(devis.lignes.select_related('produit').all())
        return MIGRATION._ttc(devis, MIGRATION._panier(lignes, option))

    def test_la_chaine_recopiee_colle_au_noyau(self):
        """La recopie SELF-CONTAINED doit rendre le MÊME nombre que le noyau —
        sinon la réparation écrirait une troisième vérité."""
        devis = self._devis()
        self.assertLessEqual(
            abs(self._panier_effectif_ttc(devis)
                - Decimal(str(option_totaux(devis, AVEC_BATTERIE)['ttc']))),
            Decimal('0.01'))

    # ── LE ROUGE ────────────────────────────────────────────────────────────
    def test_devis_deux_options_sans_remise_est_repare(self):
        devis = self._devis()
        ancien = self._geler(devis, self._somme_des_deux_paniers(devis))
        attendu = _q(self._panier_effectif_ttc(devis) / KWC)
        # ROUGE AVANT : la valeur figée est celle de la SOMME des deux paniers.
        self.assertNotEqual(ancien, attendu)
        self.assertEqual(self._lu(devis), ancien)

        MIGRATION.corriger_sur_loption_effective(_AppsShim(), None)
        self.assertEqual(self._lu(devis), attendu)

    def test_migration_reversible_aller_retour(self):
        devis = self._devis()
        ancien = self._geler(devis, self._somme_des_deux_paniers(devis))
        MIGRATION.corriger_sur_loption_effective(_AppsShim(), None)
        self.assertNotEqual(self._lu(devis), ancien)
        MIGRATION.revenir_a_la_somme_des_deux(_AppsShim(), None)
        self.assertEqual(self._lu(devis), ancien)

    def test_option_acceptee_prime_sur_le_defaut(self):
        devis = self._devis()
        devis.option_acceptee = 'sans_batterie'
        devis.save(update_fields=['option_acceptee'])
        self._geler(devis, self._somme_des_deux_paniers(devis))
        MIGRATION.corriger_sur_loption_effective(_AppsShim(), None)
        attendu = _q(
            self._panier_effectif_ttc(devis, 'sans_batterie') / KWC)
        self.assertEqual(self._lu(devis), attendu)

    # ── PÉRIMÈTRE : ce que la migration NE touche PAS ───────────────────────
    def test_devis_remise_est_hors_perimetre(self):
        """Les devis remisés sont ceux de 0106 — jamais réparés deux fois."""
        devis = self._devis(remise='10')
        fige = self._geler(devis, Decimal('99999.00'))
        MIGRATION.corriger_sur_loption_effective(_AppsShim(), None)
        self.assertEqual(self._lu(devis), fige)

    def test_devis_mono_option_intact(self):
        devis = self._devis(lignes=[
            ('Onduleur réseau Huawei 10kW', '1', '11700'),
            ('Panneau mono 550W', '14', '1100'),
        ], deux_options=False)
        fige = self._geler(devis, Decimal('88888.00'))
        MIGRATION.corriger_sur_loption_effective(_AppsShim(), None)
        self.assertEqual(self._lu(devis), fige)

    def test_devis_sans_kwc_laisse_tel_quel_et_compte(self):
        """Aucune valeur inventée : sans kWc, la valeur est LAISSÉE."""
        devis = self._devis(kwc=None)
        Devis.objects.filter(pk=devis.pk).update(
            prix_par_kwc=Decimal('12345.00'))
        repares, laisses = MIGRATION._recalculer(
            _AppsShim(), filtrer_loption=True)
        self.assertEqual(self._lu(devis), Decimal('12345.00'))
        self.assertEqual(repares, 0)
        self.assertEqual(laisses, 1)

    def test_devis_jamais_gele_reste_null(self):
        devis = self._devis()
        Devis.objects.filter(pk=devis.pk).update(prix_par_kwc=None)
        MIGRATION.corriger_sur_loption_effective(_AppsShim(), None)
        self.assertIsNone(self._lu(devis))
