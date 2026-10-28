"""Tests recouvrement (workstream E) : impayés, balance âgée, relevé, relance.

Vue / consigne / impression uniquement — aucun envoi.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    Facture, LigneFacture, FollowupLevel, RelanceLog,
)

User = get_user_model()


def make_company(slug='rec-co', nom='Rec Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestRecouvrement(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='rec_resp', password='x', role_legacy='responsable',
            company=self.company)
        for ordre, nom, delai in [(1, 'Rappel', 7), (2, 'Relance', 15),
                                  (3, 'Ferme', 30)]:
            FollowupLevel.objects.create(
                company=self.company, ordre=ordre, nom=nom, delai_jours=delai)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Débiteur', telephone='+212600000002')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-R',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
        # Facture émise, échéance dépassée de 45 jours, due 6000 TTC.
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-REC-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'),
            date_echeance=date.today() - timedelta(days=45))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_is_overdue_relies_on_jours_retard(self):
        from apps.ventes.serializers_facturation import FactureSerializer
        data = FactureSerializer(self.facture).data
        self.assertTrue(data['is_overdue'])
        self.assertEqual(data['jours_retard'], 45)
        # Une facture sans échéance (donc jours_retard=0) n'est pas en retard.
        f2 = Facture.objects.create(
            company=self.company, reference='FAC-REC-0002',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=f2, produit=self.produit, designation='X',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        self.assertFalse(FactureSerializer(f2).data['is_overdue'])

    def test_overdue_in_relances_list_with_level(self):
        resp = self.api.get('/api/django/ventes/relances/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = next(r for r in resp.data if r['id'] == self.facture.id)
        self.assertEqual(row['jours_retard'], 45)
        # 45 jours → niveau le plus haut atteint (J+30).
        self.assertEqual(row['niveau']['delai_jours'], 30)
        # Le niveau courant porte sa clé message (pré-remplissage modale).
        self.assertIn('message', row['niveau'])
        # AFAC46 — `niveau_suivant` = LE prochain niveau de la cadence (journal
        # des relances), plus une estimation par jours : aucune relance encore
        # consignée → le premier niveau (celui que le beat enverrait).
        self.assertEqual(row['niveau_suivant']['ordre'], 1)

    def test_next_level_suggested_for_mid_overdue(self):
        # Configure un message sur le niveau courant et une facture à 10 j de
        # retard : niveau courant = J+7 (avec message), suivant = J+15.
        lvl7 = FollowupLevel.objects.get(company=self.company, delai_jours=7)
        lvl7.message = 'Cher client, merci de régulariser.'
        lvl7.save(update_fields=['message'])
        from datetime import date, timedelta
        f2 = Facture.objects.create(
            company=self.company, reference='FAC-REC-0002',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'),
            date_echeance=date.today() - timedelta(days=10))
        LigneFacture.objects.create(
            facture=f2, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))
        resp = self.api.get('/api/django/ventes/relances/')
        row = next(r for r in resp.data if r['id'] == f2.id)
        self.assertEqual(row['niveau']['delai_jours'], 7)
        self.assertEqual(row['niveau']['message'],
                         'Cher client, merci de régulariser.')
        # AFAC46 — aucune relance consignée → le premier niveau de la cadence.
        self.assertEqual(row['niveau_suivant']['delai_jours'], 7)

    def test_overdue_in_aged_balance_bucket(self):
        resp = self.api.get('/api/django/ventes/balance-agee/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = next(r for r in resp.data if r['client_id'] == self.client_obj.id)
        # 45 jours → bucket 31–60.
        self.assertEqual(row['b31_60'], '6000.00')
        self.assertEqual(row['b0_30'], '0.00')
        self.assertEqual(row['total'], '6000.00')

    def test_client_statement_lists_facture(self):
        resp = self.api.get(
            f'/api/django/ventes/clients/{self.client_obj.id}/releve/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['lignes']), 1)
        self.assertEqual(resp.data['lignes'][0]['du'], '6000.00')
        self.assertEqual(resp.data['totaux']['du'], '6000.00')

    def test_statement_details_payments_and_avoirs(self):
        from apps.ventes.models import Avoir, LigneAvoir, Paiement
        Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1000'), date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)
        avoir = Avoir.objects.create(
            company=self.company, reference='AVO-REC-1', facture=self.facture,
            client=self.client_obj, statut='emise', taux_tva=Decimal('20'))
        LigneAvoir.objects.create(
            avoir=avoir, designation='Geste', quantite=Decimal('1'),
            prix_unitaire=Decimal('500'), remise=Decimal('0'),
            taux_tva=Decimal('20'))
        resp = self.api.get(
            f'/api/django/ventes/clients/{self.client_obj.id}/releve/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['paiements']), 1)
        self.assertEqual(resp.data['paiements'][0]['montant'], '1000.00')
        self.assertEqual(resp.data['paiements'][0]['mode'], 'Virement')
        self.assertEqual(len(resp.data['avoirs']), 1)
        self.assertEqual(resp.data['avoirs'][0]['reference'], 'AVO-REC-1')
        self.assertEqual(resp.data['avoirs'][0]['total_ttc'], '600.00')

    def test_enf11_releve_pdf_nom_client_avec_caractere_de_controle(self):
        """Fuzz nocturne : un client dont le nom porte \\x03 donnait un
        Content-Disposition invalide (400 text/html chez gunicorn) -> le nom
        de fichier est un slug ASCII sans caractere de controle."""
        from unittest.mock import patch
        self.client_obj.nom = 'Dupont\x03G "x"\r\nInjected: 1 \u00e9'
        self.client_obj.save()
        with patch('apps.ventes.utils.pdf.generate_releve_pdf',
                   return_value=b'%PDF-1.4'):
            resp = self.api.get(
                f'/api/django/ventes/clients/{self.client_obj.id}/releve-pdf/')
        self.assertEqual(resp.status_code, 200)
        entete = resp['Content-Disposition']
        self.assertRegex(entete, r'^inline; filename="Releve_[A-Za-z0-9_-]+\.pdf"$')
        self.assertTrue(all(32 <= ord(c) < 127 for c in entete), entete)

    def test_relancer_logs_and_sets_next(self):
        nxt = (date.today() + timedelta(days=7)).isoformat()
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/relancer/',
            {'niveau': 3, 'note': 'Appel client', 'prochaine_relance': nxt},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(RelanceLog.objects.filter(
            facture=self.facture, note='Appel client').exists())
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.prochaine_relance.isoformat(), nxt)

    def test_exclude_removes_from_relances(self):
        self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/exclure-relance/',
            {'exclu': True}, format='json')
        resp = self.api.get('/api/django/ventes/relances/')
        ids = [r['id'] for r in resp.data]
        self.assertNotIn(self.facture.id, ids)

    def test_exclure_relance_booleen_strict(self):
        # ENF11 — `exclu` non booléen (objet, 0, texte) ou corps non objet :
        # 400 qui nomme le champ, la facture n'est pas touchée.
        url = f'/api/django/ventes/factures/{self.facture.id}/exclure-relance/'
        for mauvais in ({'exclu': {}}, {'exclu': 0}, {'exclu': 'oui'}):
            resp = self.api.post(url, mauvais, format='json')
            self.assertEqual(resp.status_code, 400, (mauvais, resp.data))
            self.assertIn('exclu', resp.data)
        # Corps non objet (liste, chaîne JSON) : 400, la facture n'est pas touchée
        # (api-fuzz-full 24/10 ; avant, lu comme {} → exclusion en 200).
        avant = self.facture.exclu_relances
        for corps in ([None], 'texte'):
            self.assertEqual(self.api.post(url, corps, format='json').status_code, 400, corps)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.exclu_relances, avant)

    def test_paid_facture_not_in_relances(self):
        # Une facture payée ne doit pas figurer dans les impayés.
        from apps.ventes.models import Paiement
        Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('6000'), date_paiement=date.today())
        resp = self.api.get('/api/django/ventes/relances/')
        ids = [r['id'] for r in resp.data]
        self.assertNotIn(self.facture.id, ids)


class TestSeedDefaultsNiveaux(TestCase):
    """L768 — création des niveaux de relance par défaut (J+7 / J+15 / J+30)."""

    def setUp(self):
        self.company = make_company(slug='seed-co', nom='Seed Co')
        self.admin = User.objects.create_user(
            username='seed_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_seed_creates_three_default_levels(self):
        self.assertEqual(
            FollowupLevel.objects.filter(company=self.company).count(), 0)
        resp = self.api.post(
            '/api/django/ventes/niveaux-relance/seed-defaults/')
        self.assertEqual(resp.status_code, 201, resp.data)
        delais = sorted(
            FollowupLevel.objects.filter(company=self.company)
            .values_list('delai_jours', flat=True))
        self.assertEqual(delais, [7, 15, 30])

    def test_seed_publie_201_sans_corps(self):
        # api-fuzz-full 27/10 (ENF11) : le 201 renvoyé est publié, aucun corps.
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        from apps.ventes import urls as ventes_urls
        schema = SchemaGenerator(patterns=[
            path('api/django/ventes/', include(ventes_urls)),
        ]).get_schema(request=None, public=True)
        op = schema['paths'][
            '/api/django/ventes/niveaux-relance/seed-defaults/']['post']
        self.assertIn('201', op['responses'])
        self.assertNotIn('requestBody', op)

    def test_niveau_decimaux_strictement_en_chaine(self):
        # ENF11 — taux/frais sont déclarés en chaîne : un nombre JSON est
        # refusé en 400 (plus converti en silence), la chaîne reste acceptée.
        url = '/api/django/ventes/niveaux-relance/'
        base = {'nom': 'N', 'delai_jours': 7, 'ordre': 1}
        for champ in ('frais_fixes', 'taux_interet_annuel'):
            resp = self.api.post(url, {**base, champ: 5}, format='json')
            self.assertEqual(resp.status_code, 400, (champ, resp.data))
            self.assertIn(champ, resp.data)
        resp = self.api.post(
            url, {**base, 'frais_fixes': '12.50', 'taux_interet_annuel': ''},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['frais_fixes'], '12.50')
        self.assertIsNone(resp.data['taux_interet_annuel'])

    def test_niveau_texte_strictement_en_chaine(self):
        # CI #997 — ``message: 0`` était converti en « 0 » (201) : 400.
        resp = self.api.post(
            '/api/django/ventes/niveaux-relance/',
            {'nom': 'N', 'delai_jours': 7, 'ordre': 1, 'message': 0},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('message', resp.data)

    def test_seed_idempotent_when_levels_exist(self):
        FollowupLevel.objects.create(
            company=self.company, ordre=0, nom='Existant', delai_jours=10)
        resp = self.api.post(
            '/api/django/ventes/niveaux-relance/seed-defaults/')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(
            FollowupLevel.objects.filter(company=self.company).count(), 1)
