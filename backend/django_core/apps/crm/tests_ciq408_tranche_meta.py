"""CIQ408 — reprise des leads Meta dont « plus de 4 000 DH » a été écrit
4 000 dans ``facture_hiver`` (migration de données 0126, D-CIQ-19).

Fixtures à la forme EXACTE de la note posée par ``_ensure_meta_form_note``
avant CIQ407 (« • question → réponse », underscores → espaces).

Run :
    python manage.py test apps.crm.tests_ciq408_tranche_meta -v 2
"""
import importlib
from decimal import Decimal

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity

User = get_user_model()

Q_FACTURE = "quelle est votre facture moyenne d'électricité par mois ?"


def _migration():
    return importlib.import_module(
        'apps.crm.migrations.0126_ciq408_tranche_meta_ouverte')


class RepriseTrancheMetaOuverte(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='CIQ408 Co', slug='ciq408-co')
        self.user = User.objects.create_user(
            username='ciq408_user', password='x', role_legacy='responsable',
            company=self.company)

    def _lead_meta(self, nom, reponse, facture):
        lead = Lead.objects.create(
            company=self.company, nom=nom, type_installation='commercial',
            facture_hiver=facture, source='meta_lead_ads')
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body='[Formulaire Meta] Réponses du prospect (formulaire 1) :\n'
                 f'• où souhaitez-vous installer ? → pour mon entreprise\n'
                 f'• {Q_FACTURE} → {reponse}\n'
                 f'(facture hiver pré-remplie à {int(facture)} MAD depuis '
                 f'la tranche déclarée « {reponse} » — à préciser au '
                 'premier appel)')
        return lead

    def test_reprise_cible_seulement_la_borne_ouverte_non_touchee(self):
        ouverte = self._lead_meta('Ouverte', 'plus de 4000dh',
                                  Decimal('4000'))
        touchee = self._lead_meta('Touchée', 'plus de 4000dh',
                                  Decimal('4000'))
        LeadActivity.objects.create(
            company=self.company, lead=touchee, user=self.user,
            kind=LeadActivity.Kind.MODIFICATION, field='facture_hiver',
            field_label='Facture hiver', old_value='5000.00',
            new_value='4000.00')
        fermee = self._lead_meta('Fermée', 'entre 1000 et 2000 dh',
                                 Decimal('1500'))
        autre_montant = self._lead_meta('Autre', 'plus de 4000dh',
                                        Decimal('6000'))
        migration = _migration()
        migration.retirer_les_bornes(django_apps, None)
        for lead in (ouverte, touchee, fermee, autre_montant):
            lead.refresh_from_db()
        self.assertIsNone(ouverte.facture_hiver)
        self.assertEqual(ouverte.facture_tranche_declaree, {
            'min_mad': 4000, 'max_mad': None, 'libelle': 'plus de 4000dh',
            'source': 'meta'})
        self.assertTrue(LeadActivity.objects.filter(
            lead=ouverte, body=migration.NOTE).exists())
        self.assertEqual(touchee.facture_hiver, Decimal('4000'))
        self.assertIsNone(touchee.facture_tranche_declaree)
        self.assertEqual(fermee.facture_hiver, Decimal('1500'))
        self.assertEqual(autre_montant.facture_hiver, Decimal('6000'))

    def test_rejouee_deux_fois_meme_etat_et_retour_arriere(self):
        lead = self._lead_meta('Ouverte', 'plus de 4 000 DH',
                               Decimal('4000'))
        migration = _migration()
        migration.retirer_les_bornes(django_apps, None)
        etat = list(Lead.objects.filter(pk=lead.pk).values())
        notes = LeadActivity.objects.filter(lead=lead).count()
        migration.retirer_les_bornes(django_apps, None)
        self.assertEqual(list(Lead.objects.filter(pk=lead.pk).values()),
                         etat)
        self.assertEqual(LeadActivity.objects.filter(lead=lead).count(),
                         notes)
        migration.remettre_les_bornes(django_apps, None)
        lead.refresh_from_db()
        self.assertEqual(lead.facture_hiver, Decimal('4000'))
        self.assertIsNone(lead.facture_tranche_declaree)
        self.assertFalse(LeadActivity.objects.filter(
            lead=lead, body=migration.NOTE).exists())

    def test_aucun_devis_touche(self):
        from apps.ventes.models import Devis
        lead = self._lead_meta('Ouverte', 'plus de 4000dh', Decimal('4000'))
        avant = Devis.objects.count()
        _migration().retirer_les_bornes(django_apps, None)
        self.assertEqual(Devis.objects.count(), avant)
        lead.refresh_from_db()
        self.assertIsNone(lead.facture_hiver)
