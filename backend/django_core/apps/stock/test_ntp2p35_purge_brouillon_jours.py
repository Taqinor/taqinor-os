"""NTP2P35 (complément stock) — seuil de purge des brouillons de demande
d'achat, configurable par société.

Le point de ce module est UNE chose : verrouiller le sens de ``0``. Le champ
naît à ``0``, donc TOUTE société existante lit ``0`` — si un appelant
l'interprétait comme « zéro jour », la première purge effacerait les brouillons
du jour même. ``0`` veut dire « utiliser le défaut (90 jours) », et
``selectors.purge_brouillon_jours`` est le seul endroit qui le décide.

Run :
    python manage.py test apps.stock.test_ntp2p35_purge_brouillon_jours -v2
"""
import itertools

from django.test import TestCase

from apps.stock.models import AchatsParametres
from apps.stock.selectors import (
    PURGE_BROUILLON_JOURS_DEFAUT, purge_brouillon_jours,
)
from apps.stock.serializers import AchatsParametresSerializer
from authentication.models import Company

_seq = itertools.count(1)


def make_company():
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p35-co-{n}', defaults={'nom': f'NTP2P35 Co {n}'})
    return company


class PurgeBrouillonJoursTests(TestCase):
    def test_le_champ_nait_a_zero(self):
        params = AchatsParametres.for_company(make_company())
        self.assertEqual(params.purge_brouillon_jours, 0)

    def test_zero_veut_dire_le_defaut_pas_zero_jour(self):
        company = make_company()
        AchatsParametres.for_company(company)
        self.assertEqual(
            purge_brouillon_jours(company), PURGE_BROUILLON_JOURS_DEFAUT)
        self.assertEqual(PURGE_BROUILLON_JOURS_DEFAUT, 90)

    def test_aucun_parametre_enregistre_rend_aussi_le_defaut(self):
        self.assertEqual(
            purge_brouillon_jours(make_company()),
            PURGE_BROUILLON_JOURS_DEFAUT)

    def test_une_valeur_configuree_est_respectee(self):
        company = make_company()
        params = AchatsParametres.for_company(company)
        params.purge_brouillon_jours = 30
        params.save(update_fields=['purge_brouillon_jours'])
        self.assertEqual(purge_brouillon_jours(company), 30)

    def test_une_valeur_plus_longue_que_le_defaut_est_respectee(self):
        company = make_company()
        params = AchatsParametres.for_company(company)
        params.purge_brouillon_jours = 365
        params.save(update_fields=['purge_brouillon_jours'])
        self.assertEqual(purge_brouillon_jours(company), 365)

    def test_sans_societe_le_defaut_s_applique(self):
        self.assertEqual(
            purge_brouillon_jours(None), PURGE_BROUILLON_JOURS_DEFAUT)

    def test_chaque_societe_a_son_propre_seuil(self):
        courte = make_company()
        longue = make_company()
        for company, jours in ((courte, 15), (longue, 200)):
            params = AchatsParametres.for_company(company)
            params.purge_brouillon_jours = jours
            params.save(update_fields=['purge_brouillon_jours'])

        self.assertEqual(purge_brouillon_jours(courte), 15)
        self.assertEqual(purge_brouillon_jours(longue), 200)

    def test_champ_expose_et_editable_par_le_serializer(self):
        params = AchatsParametres.for_company(make_company())
        data = AchatsParametresSerializer(params).data
        self.assertIn('purge_brouillon_jours', data)
        self.assertEqual(data['purge_brouillon_jours'], 0)

        serializer = AchatsParametresSerializer(
            params, data={'purge_brouillon_jours': 45}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        params.refresh_from_db()
        self.assertEqual(params.purge_brouillon_jours, 45)

    def test_une_valeur_negative_est_refusee(self):
        params = AchatsParametres.for_company(make_company())
        serializer = AchatsParametresSerializer(
            params, data={'purge_brouillon_jours': -5}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('purge_brouillon_jours', serializer.errors)
