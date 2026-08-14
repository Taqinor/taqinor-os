"""NTMKT20 — Modèles d'attribution configurables sur PointContact (FG204).

Couvre les 4 modèles de répartition (dernier/premier-touche, linéaire,
pondéré temporel) d'un devis signé, et les cas limites (pas de lead, pas
accepté, pas de point de contact).
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Lead, PointContact
from apps.crm.selectors import attribution_comparaison_devis

from testkit.factories import DevisFactory, LigneDevisFactory


class AttributionComparaisonDevisTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt20', nom='NTMKT20')
        self.lead = Lead.objects.create(company=self.co, nom='Lead A')
        self.devis = DevisFactory(
            company=self.co, lead=self.lead, statut='accepte')
        LigneDevisFactory(
            devis=self.devis, quantite=Decimal('1'),
            prix_unitaire=Decimal('1000.00'), remise=Decimal('0'))
        now = timezone.now()
        self.p1 = PointContact.objects.create(
            company=self.co, lead=self.lead, canal='meta_ads',
            date_contact=now - timezone.timedelta(days=10), ordre=1)
        self.p2 = PointContact.objects.create(
            company=self.co, lead=self.lead, canal='site_web',
            date_contact=now, ordre=2)

    def test_devis_non_accepte_renvoie_none(self):
        self.devis.statut = 'envoye'
        self.devis.save(update_fields=['statut'])
        self.assertIsNone(attribution_comparaison_devis(self.devis))

    def test_devis_sans_lead_renvoie_none(self):
        self.devis.lead = None
        self.devis.save(update_fields=['lead'])
        self.assertIsNone(attribution_comparaison_devis(self.devis))

    def test_dernier_touche_donne_tout_au_dernier_point(self):
        resultat = attribution_comparaison_devis(self.devis)
        total = Decimal(resultat['total_revenu'])
        self.assertGreater(total, 0)
        modele = resultat['modeles']['dernier_touche']
        self.assertEqual(Decimal(modele[0]['revenu_attribue']), Decimal('0'))
        self.assertEqual(Decimal(modele[1]['revenu_attribue']), total)

    def test_premier_touche_donne_tout_au_premier_point(self):
        resultat = attribution_comparaison_devis(self.devis)
        total = Decimal(resultat['total_revenu'])
        modele = resultat['modeles']['premier_touche']
        self.assertEqual(Decimal(modele[0]['revenu_attribue']), total)
        self.assertEqual(Decimal(modele[1]['revenu_attribue']), Decimal('0'))

    def test_lineaire_partage_egalement_et_somme_exacte(self):
        resultat = attribution_comparaison_devis(self.devis)
        total = Decimal(resultat['total_revenu'])
        modele = resultat['modeles']['lineaire']
        somme = sum(Decimal(m['revenu_attribue']) for m in modele)
        self.assertEqual(somme, total)
        self.assertLess(
            abs(Decimal(modele[0]['revenu_attribue']) - total / 2),
            Decimal('0.02'))

    def test_pondere_temporel_favorise_le_point_le_plus_recent(self):
        resultat = attribution_comparaison_devis(self.devis)
        modele = resultat['modeles']['pondere_temporel']
        self.assertGreater(
            Decimal(modele[1]['revenu_attribue']),
            Decimal(modele[0]['revenu_attribue']))
        total = Decimal(resultat['total_revenu'])
        somme = sum(Decimal(m['revenu_attribue']) for m in modele)
        self.assertEqual(somme, total)

    def test_sans_point_contact_aucune_repartition(self):
        PointContact.objects.filter(lead=self.lead).delete()
        resultat = attribution_comparaison_devis(self.devis)
        self.assertEqual(resultat['nb_points_contact'], 0)
        for modele in resultat['modeles'].values():
            self.assertEqual(modele, [])
