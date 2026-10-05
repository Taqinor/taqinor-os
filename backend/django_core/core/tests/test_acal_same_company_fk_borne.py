"""ACAL298 — ``SameCompanyFKSerializerMixin`` BORNE le queryset de ses champs.

Constat C-ACAL-015 : un id d'une autre société recevait « Cette référence
n'appartient pas à votre société. » quand un id absent recevait « objet
inexistant » — deux réponses différentes, donc un oracle d'existence
inter-sociétés. Le mixin borne désormais, dans ``get_fields()``, le queryset de
chaque champ de ``same_company_fields`` à la société de la requête : les deux
cas rendent l'erreur ``does_not_exist`` standard de DRF, octet-identique hors
l'id cité.

Run :
    python manage.py test core.tests.test_acal_same_company_fk_borne -v2
"""
from decimal import Decimal

from django.apps import apps as django_apps
from django.test import TestCase
from django.utils.module_loading import import_string
from rest_framework import serializers
from rest_framework.test import APIRequestFactory

from authentication.models import Company, CustomUser
from core.mixins import SameCompanyFKSerializerMixin


class _JouetSerializer(SameCompanyFKSerializerMixin, serializers.Serializer):
    """Sérialiseur jouet : une FK NUE vers un modèle scopé société."""

    utilisateur = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all())
    same_company_fields = ('utilisateur',)


ABSENT = 999999


def _sans_id(erreurs, pk):
    """Les erreurs rendues comparables : l'id cité remplacé par « N »."""
    return [(str(e).replace(str(pk), 'N'), getattr(e, 'code', None))
            for e in erreurs]


class SameCompanyFkBorneTest(TestCase):
    def setUp(self):
        self.societe = Company.objects.create(nom='ACAL298 A',
                                              slug='acal298-a')
        self.voisine = Company.objects.create(nom='ACAL298 B',
                                              slug='acal298-b')
        self.moi = CustomUser.objects.create_user(
            username='acal298_moi', password='x', company=self.societe)
        self.collegue = CustomUser.objects.create_user(
            username='acal298_collegue', password='x', company=self.societe)
        self.voisin = CustomUser.objects.create_user(
            username='acal298_voisin', password='x', company=self.voisine)
        requete = APIRequestFactory().post('/')
        requete.user = self.moi
        self.contexte = {'request': requete}

    def _erreurs(self, classe, champ, pk, **kwargs):
        s = classe(data={champ: pk}, context=self.contexte, **kwargs)
        self.assertFalse(s.is_valid())
        self.assertEqual(list(s.errors), [champ])
        return _sans_id(s.errors[champ], pk)

    def test_le_mixin_borne_le_queryset_du_champ(self):
        s = _JouetSerializer(context=self.contexte)
        qs = s.fields['utilisateur'].get_queryset()
        self.assertIn(self.collegue, qs)
        self.assertNotIn(self.voisin, qs)

        etranger = self._erreurs(_JouetSerializer, 'utilisateur',
                                 self.voisin.pk)
        absent = self._erreurs(_JouetSerializer, 'utilisateur', ABSENT)
        self.assertEqual(etranger, absent)
        self.assertEqual(etranger[0][1], 'does_not_exist')
        self.assertNotIn('appartient', etranger[0][0])

        # Un id de SA société passe.
        ok = _JouetSerializer(data={'utilisateur': self.collegue.pk},
                              context=self.contexte)
        self.assertTrue(ok.is_valid(), ok.errors)

    def test_hors_requete_inchange(self):
        """Sans requête (service, seed) : aucun bornage, comme avant."""
        s = _JouetSerializer(data={'utilisateur': self.voisin.pk})
        self.assertTrue(s.is_valid(), s.errors)

    def test_structure_produit_du_lead_meme_reponse(self):
        # Chargement dynamique : ``core`` n'importe aucune app métier
        # statiquement (contrat import-linter core-foundation).
        lead_serializer = import_string('apps.crm.serializers.LeadSerializer')
        produit = django_apps.get_model('stock', 'Produit')
        etranger = produit.objects.create(
            company=self.voisine, nom='Structure voisine', sku='ACAL298-STR',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=1)
        e1 = self._erreurs(lead_serializer, 'structure_produit',
                           etranger.pk, partial=True)
        e2 = self._erreurs(lead_serializer, 'structure_produit', ABSENT,
                           partial=True)
        self.assertEqual(e1, e2)
        self.assertEqual(e1[0][1], 'does_not_exist')
