"""ADEV19 (C-ADEV-012) — l'activation d'une option par le CLIENT (page
publique, ``activate_optional_line``) est un geste de ligne standard :
``debut_de_geste_devis`` / ``fin_de_geste_devis(objet='option client')``,
rafraîchissement (MODE_RAFRAICHIR : kWc, marge), instantané et avance du
jeton d'édition.

Given un devis résidentiel ENVOYÉ (10 panneaux 710 W = 7,1 kWc) + une ligne
optionnelle de 4 panneaux 710 W, et un écran interne ouvert avant (jeton t0) ;
When le client POST ``/public/proposal/<token>/activer-option/`` puis l'écran
interne enregistre avec t0 ;
Then kWc = 9,94, un instantané de plus, une trace « corrigé après envoi —
option client », et l'enregistrement interne répond 409 ``devis_modifie`` —
la ligne reste NON optionnelle (choix du client préservé).

Test-du-test : retirer ``fin_de_geste_devis``/l'avance du jeton ⇒
``test_jeton_avance_409`` échoue ; retirer le rafraîchissement ⇒
``test_kwc_rafraichi`` échoue.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev19_option_client_geste -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    ConfigurationDevisSnapshot, Devis, DevisActivity, LigneDevis, ShareLink,
)
from authentication.models import Company

User = get_user_model()


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class OptionClientGesteTests(TestCase):

    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='ADEV19 Co', slug='adev19-co')
        self.user = User.objects.create_user(
            username='adev19_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='adev19@example.com')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Canadian Solar 710W',
            sku='ADEV19-PV', prix_vente=Decimal('1450'),
            prix_achat=Decimal('900'), quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 8kW',
            sku='ADEV19-OND', prix_vente=Decimal('14000'),
            prix_achat=Decimal('9000'), quantite_stock=10)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ADEV19-0001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), remise_globale=Decimal('0'),
            created_by=self.user)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.panneau,
            designation=self.panneau.nom, quantite=Decimal('10'),
            prix_unitaire=Decimal('1450'), remise=Decimal('0'), ordre=0)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.onduleur,
            designation=self.onduleur.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('14000'), remise=Decimal('0'), ordre=1)
        self.option = LigneDevis.objects.create(
            devis=self.devis, produit=self.panneau,
            designation=self.panneau.nom, quantite=Decimal('4'),
            prix_unitaire=Decimal('1450'), remise=Decimal('0'), ordre=2,
            optionnelle=True)
        self.lien = ShareLink.for_devis(self.devis)
        self.interne = APIClient()
        self.interne.force_authenticate(user=self.user)

    def _jeton(self):
        reponse = self.interne.get(f'/api/django/ventes/devis/{self.devis.id}/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        return reponse.data['updated_at']

    def _activer(self):
        reponse = APIClient().post(
            f'/api/django/public/proposal/{self.lien.token}/activer-option/',
            {'ligne_id': self.option.id}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        return reponse

    def _kwc(self):
        devis = Devis.objects.get(pk=self.devis.pk)
        return (devis.etude_params or {}).get('puissance_kwc')

    def test_kwc_rafraichi(self):
        self._activer()
        self.assertAlmostEqual(float(self._kwc()), 9.94, places=2)

    def test_instantane_cree(self):
        avant = ConfigurationDevisSnapshot.objects.filter(
            devis=self.devis).count()
        self._activer()
        apres = ConfigurationDevisSnapshot.objects.filter(
            devis=self.devis).count()
        self.assertGreater(apres, avant)

    def test_trace_chatter(self):
        self._activer()
        traces = DevisActivity.objects.filter(
            devis=self.devis, field='correction_apres_envoi')
        self.assertEqual(traces.count(), 1)
        self.assertIn('option client', traces.get().body)
        # Le statut n'a pas bougé (règle #4).
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)

    def test_jeton_avance_409(self):
        t0 = self._jeton()
        self._activer()
        lignes = [
            {'produit': self.panneau.id, 'designation': self.panneau.nom,
             'quantite': '10', 'prix_unitaire': '1450.00', 'remise': '0',
             'taux_tva': '20.00', 'type_ligne': 'produit', 'ordre': 0},
            {'produit': self.onduleur.id, 'designation': self.onduleur.nom,
             'quantite': '1', 'prix_unitaire': '14000.00', 'remise': '0',
             'taux_tva': '20.00', 'type_ligne': 'produit', 'ordre': 1},
            {'produit': self.panneau.id, 'designation': self.panneau.nom,
             'quantite': '4', 'prix_unitaire': '1450.00', 'remise': '0',
             'taux_tva': '20.00', 'type_ligne': 'produit', 'ordre': 2,
             'optionnelle': True},
        ]
        reponse = self.interne.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': lignes, 'expected_updated_at': t0}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.content)
        self.assertEqual(reponse.json()['code'], 'devis_modifie')
        # CLAUSE PERSISTANCE : le choix du client reste en base.
        self.option.refresh_from_db()
        self.assertFalse(self.option.optionnelle)
