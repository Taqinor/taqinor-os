"""
NTP2P31 — Réglages Procure-to-Pay par société : troisième interrupteur.

CRITÈRE D'ACCEPTATION (illustré par le réglage existant `budget_departement_
actif`, même patron pour les trois) : désactiver un interrupteur fait
repasser instantanément le comportement associé en mode historique
inchangé. Ce fichier couvre le NOUVEAU réglage additif
``plafond_notes_frais_actif`` : défaut ``False``, exposé par
``AchatsParametresSerializer``, lu cross-app via
``apps.stock.selectors.plafond_notes_frais_actif``.

Run :
    python manage.py test apps.stock.test_ntp2p31_reglages_p2p -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock import selectors as stock_selectors
from apps.stock.models import AchatsParametres
from apps.stock.serializers import AchatsParametresSerializer

User = get_user_model()
_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p31-co-{n}', defaults={'nom': f'NTP2P31 Co {n}'})
    return company


class PlafondNotesFraisActifSelectorTests(TestCase):
    def test_defaut_false_sans_parametres(self):
        company = make_company()
        # Aucun AchatsParametres encore créé pour cette société.
        self.assertFalse(
            stock_selectors.plafond_notes_frais_actif(company))

    def test_defaut_false_avec_parametres_existant(self):
        company = make_company()
        AchatsParametres.for_company(company)
        self.assertFalse(
            stock_selectors.plafond_notes_frais_actif(company))

    def test_true_apres_activation(self):
        company = make_company()
        params = AchatsParametres.for_company(company)
        params.plafond_notes_frais_actif = True
        params.save(update_fields=['plafond_notes_frais_actif'])
        self.assertTrue(
            stock_selectors.plafond_notes_frais_actif(company))

    def test_none_company_renvoie_false(self):
        self.assertFalse(stock_selectors.plafond_notes_frais_actif(None))

    def test_champ_expose_par_le_serializer(self):
        company = make_company()
        params = AchatsParametres.for_company(company)
        data = AchatsParametresSerializer(params).data
        self.assertIn('plafond_notes_frais_actif', data)
        self.assertFalse(data['plafond_notes_frais_actif'])
