"""ALEA19 — les champs que la fiche écrit sont tracés au chatter.

Rejoue la sonde V3 LFICHE-3 : PATCH ``note``, contact secondaire,
``contact_preference``, ``structure_produit`` → 0 entrée (contrôle ``ville``
→ 2). Valeurs VALIDES de ``contact_preference`` (V3 a eu des 400 avec des
valeurs hors choix). Source réelle : ``log_changes`` via ``perform_update``.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import activity
from apps.crm.models import Lead, LeadActivity
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()


class ChatterChampsFicheTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ALEA19', slug='alea19')
        self.user = User.objects.create_user(
            username='alea19_user', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='ALEA19')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _patch(self, **body):
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.id}/', body, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def _modifs(self, field):
        return LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION,
            field=field).order_by('id')

    def test_note_tracee(self):
        self._patch(note='AAA')
        self._patch(note='BBB')
        modifs = list(self._modifs('note'))
        self.assertEqual(len(modifs), 2)
        self.assertEqual((modifs[1].old_value, modifs[1].new_value),
                         ('AAA', 'BBB'))
        self.assertEqual(modifs[1].field_label, 'Note')
        self.assertEqual(modifs[1].user_id, self.user.id)
        # Un second PATCH identique n'ajoute rien.
        self._patch(note='BBB')
        self.assertEqual(self._modifs('note').count(), 2)
        # Le chatter servi montre l'ancien texte.
        historique = self.api.get(
            f'/api/django/crm/leads/{self.lead.id}/historique/')
        self.assertEqual(historique.status_code, 200)
        self.assertIn('AAA', str(historique.data))

    def test_contact_secondaire_trace(self):
        self._patch(contact_secondaire_nom='Youssef')
        self._patch(contact_secondaire_telephone='0600000000')
        self.assertEqual(
            self._modifs('contact_secondaire_nom').get().new_value, 'Youssef')
        self.assertEqual(
            self._modifs('contact_secondaire_telephone').get().new_value,
            '0600000000')

    def test_contact_preference_tracee(self):
        choix = dict(Lead._meta.get_field('contact_preference').choices)
        cle = next(iter(choix))
        self._patch(contact_preference=cle)
        modif = self._modifs('contact_preference').get()
        self.assertEqual(modif.new_value, str(choix[cle]))
        self.assertEqual(modif.field_label, 'Préférence de contact')

    def test_structure_produit_tracee(self):
        produit = Produit.objects.create(
            company=self.company, nom='Structure alu ALEA19',
            sku='ALEA19-STR', prix_vente=Decimal('100'),
            prix_achat=Decimal('50'), quantite_stock=1, tva=Decimal('20.00'))
        self._patch(structure_produit=produit.id)
        modif = self._modifs('structure_produit').get()
        self.assertEqual(modif.old_value, '—')
        self.assertEqual(modif.new_value, str(produit))

    def test_lien_maps_trace(self):
        self._patch(lien_maps='https://maps.google.com/?q=33.5,-7.6')
        self.assertEqual(self._modifs('lien_maps').count(), 1)

    def test_exclusions_declarees_avec_raison(self):
        for champ in ('custom_data', 'utm_source', 'utm_medium',
                      'utm_campaign', 'utm_content', 'utm_term',
                      'meta_ad_id', 'meta_adset_id'):
            with self.subTest(champ=champ):
                self.assertNotIn(champ, activity.TRACKED_FIELDS)
                self.assertTrue(activity.CHAMPS_NON_SUIVIS[champ].strip())
        self.assertFalse(
            set(activity.TRACKED_FIELDS) & set(activity.CHAMPS_NON_SUIVIS))
