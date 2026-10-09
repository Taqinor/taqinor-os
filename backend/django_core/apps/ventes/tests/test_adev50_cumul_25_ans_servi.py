"""ADEV50 (C-ADEV-017) — le cumul 25 ans de CHAQUE option est SERVI par
``proposal_data`` (``economies_cumul_25_ans``), lu sur le flux annuel que trace
le PDF ``/proposal`` (``cashflow_*`` du moteur) : la page ne recalcule plus
« économie × 25 » (sonde VA p7 : 400 350 pour les deux options, réel 342 314 /
346 653).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev50_cumul_25_ans_servi -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink

LIGNES_DEUX_OPTIONS = (
    ('Panneau Canadien Solar 710W', '14', '1166.67'),
    ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
    ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
    ('Batterie Dyness 10 kWh', '1', '25000.00'),
)


def devis_deux_options(slug, etude_params=None, statut='envoye'):
    """Devis résidentiel à DEUX options, ancré sur 12 factures réelles
    (patron ``test_pvcov_synthese_servie``)."""
    company = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})[0]
    user = get_user_model().objects.create_user(
        username=f'{slug}_u', password='x', company=company)
    client_obj = Client.objects.create(company=company, nom=f'Client {slug}')
    if etude_params is None:
        # Ancrage RÉEL (Z2) : le builder ne lit que ``factures_mensuelles_reelles``
        # (sans elle, tarif de repli ⇒ économies omises de la page publique).
        etude_params = {'factures_mensuelles_reelles': [1800] * 12,
                        'distributeur': 'onee', 'ville': 'casablanca'}
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{slug.upper()}-01',
        client=client_obj, taux_tva=Decimal('20'), statut=statut,
        created_by=user, etude_params=etude_params)
    for i, (nom, qte, pu) in enumerate(LIGNES_DEUX_OPTIONS):
        produit = Produit.objects.create(
            company=company, nom=nom, sku=f'{slug}-{i}',
            prix_vente=Decimal(pu), quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=nom,
            quantite=Decimal(qte), prix_unitaire=Decimal(pu),
            remise=Decimal('0'), ordre=i)
    return devis


def lire(token):
    with mock.patch('apps.ventes.public_views._notify_open'):
        return APIClient().get(f'/api/django/public/proposal/{token}/data/')


class Cumul25AnsServiTests(TestCase):

    def test_cle_par_option_egale_pdf(self):
        devis = devis_deux_options('adev50a')
        link = ShareLink.objects.create(company=devis.company, devis=devis)
        resp = lire(link.token)
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        cumul = resp.json().get('economies_cumul_25_ans')
        self.assertIsInstance(cumul, dict)

        # LE flux du PDF : la même sortie moteur que /proposal trace.
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis, {'pdf_mode': 'full',
                                        'share_token': link.token})
        attendu = {}
        for option, cle_flux, cle_total in (
                ('sans_batterie', 'cashflow_sans', 'total_sans'),
                ('avec_batterie', 'cashflow_avec', 'total_avec')):
            flux = data.get(cle_flux) or []
            if flux:
                # Somme des 25 flux annuels = cumul final + investissement.
                annuels = [flux[0] + float(data[cle_total])] + [
                    flux[i] - flux[i - 1] for i in range(1, len(flux))]
                attendu[option] = round(sum(annuels))
        self.assertEqual(set(cumul), {'sans_batterie', 'avec_batterie'})
        for option, valeur in cumul.items():
            self.assertAlmostEqual(valeur, attendu[option], delta=1)
        # Deux options, deux flux : jamais la même valeur servie deux fois.
        self.assertNotEqual(cumul['sans_batterie'], cumul['avec_batterie'])
        # …et jamais l'ancien « économie annuelle × 25 » de la page.
        eco_a = data.get('eco_a_ann') or 0
        self.assertNotEqual(cumul['avec_batterie'], round(eco_a * 25))

        # CLAUSE PERSISTANCE : relire → mêmes chiffres.
        self.assertEqual(lire(link.token).json()['economies_cumul_25_ans'],
                         cumul)

    def test_absente_sans_etude(self):
        # Aucun ancrage réel (ni factures, ni distributeur) : Z2 retire les
        # économies, le cumul part avec elles — clé ABSENTE, jamais null.
        devis = devis_deux_options('adev50b', etude_params={})
        link = ShareLink.objects.create(company=devis.company, devis=devis)
        resp = lire(link.token)
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.assertNotIn('economies_cumul_25_ans', resp.json())

    def test_absente_case_economies_decochee(self):
        devis = devis_deux_options('adev50c')
        link = ShareLink.objects.create(
            company=devis.company, devis=devis,
            sections={'economies': False})
        resp = lire(link.token)
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.assertNotIn('economies_cumul_25_ans', resp.json())
