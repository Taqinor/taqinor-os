# -*- coding: utf-8 -*-
"""QJR-OFFGRID (fondateur 01/09/2026) — le raccordement « aucun » (site isolé).

Le lead d'un site ISOLÉ ne déclarait rien de vrai : la taxonomie n'offrait que
monophasé / triphasé / « je ne sais pas ». Or « je ne sais pas » et « il n'y a
pas de raccordement » n'appellent pas le même devis — le second impose un
onduleur AUTONOME et une batterie, là où le premier laisse simplement le
filtre de phase inerte.

Ce que ce module verrouille :
  * le choix additif existe, avec son libellé français ;
  * les trois valeurs historiques sont INTACTES ;
  * un lead l'accepte par le sérialiseur (donc par l'API).

Ce que « aucun » VEUT DIRE pour la composition (inerte pour le filtre mono/tri,
reconnu comme site isolé) est verrouillé côté ventes —
``apps.ventes.tests.test_offgrid_hors_reseau`` — pour que ce module-ci reste
une lecture PUREMENT crm.

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_offgrid_raccordement -v 2
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from .models import Lead
from .serializers import LeadSerializer


class TestRaccordementAucunChoix(SimpleTestCase):
    def test_le_choix_existe_avec_son_libelle(self):
        self.assertIn('aucun', Lead.Raccordement.values)
        self.assertEqual(Lead.Raccordement.AUCUN.label,
                         'Non raccordé (site isolé)')

    def test_les_choix_historiques_sont_intacts(self):
        for valeur in ('monophase', 'triphase', 'inconnu'):
            self.assertIn(valeur, Lead.Raccordement.values)


class TestLeadAccepteRaccordementAucun(TestCase):
    def test_le_serialiseur_accepte_aucun(self):
        serializer = LeadSerializer(
            data={'nom': 'Site isolé', 'raccordement': 'aucun'})
        serializer.is_valid()
        self.assertNotIn('raccordement', serializer.errors)

    def test_le_serialiseur_refuse_toujours_une_valeur_inconnue(self):
        """Le contrôle : la liste reste FERMÉE, elle s'est seulement allongée."""
        serializer = LeadSerializer(
            data={'nom': 'Site isolé', 'raccordement': 'hors-sol'})
        serializer.is_valid()
        self.assertIn('raccordement', serializer.errors)

    def test_le_lead_le_stocke(self):
        company = Company.objects.create(nom='Offgrid Co', slug='offgrid-co')
        lead = Lead.objects.create(
            company=company, nom='Ferme isolée', raccordement='aucun')
        lead.refresh_from_db()
        self.assertEqual(lead.raccordement, 'aucun')
