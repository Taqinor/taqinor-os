# -*- coding: utf-8 -*-
"""ATOT10 — le pro-forma choisit son option par ``option_effective`` (la même
règle que le BC, la liste et le PDF /proposal) : son TTC == ``Devis.total_ttc``.

Constat C-ATOT-015 : ``utils/pdf._proforma_option`` rendait l'option AVEC dès
qu'un devis avait deux options. Un devis commercial/industriel non accepté
met pourtant en avant l'offre RÉSEAU (SANS, CIQ302), et un scénario mono
« Sans batterie » restreint le document à SANS (QJR400) : le pro-forma
imprimait 72 500 là où la liste et le PDF client disaient 53 500 (sonde V2
TSORT-2).

Source réelle : ``apps.ventes.utils.options.option_effective``, rendu
WeasyPrint réel, texte lu par PyMuPDF (dépendance déjà dans
requirements.txt), endpoint POST ``/api/django/ventes/devis/<id>/proforma-pdf/``
réel — aucun mock.

Test-du-test : réintroduire ``AVEC_BATTERIE if has_two_options(devis)`` dans
le pro-forma ⇒ les cas industriel et scénario mono échouent.
"""
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.options import (
    AVEC_BATTERIE, SANS_BATTERIE, option_effective, option_totaux,
)
from authentication.models import Company

User = get_user_model()

_RE_TTC = re.compile(r'Total TTC \(indicatif\)\s*([0-9]+\.[0-9]{2}) MAD')


def _texte_pdf(octets):
    import fitz  # PyMuPDF
    with fitz.open(stream=octets, filetype='pdf') as doc:
        texte = '\n'.join(page.get_text() for page in doc)
    return re.sub(r'\s+', ' ', texte)


class ProformaOptionTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='atot10-co', defaults={'nom': 'ATOT10 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Proforma', prenom='ATOT10',
            email='atot10@example.com', telephone='+212600000010',
            adresse='Casablanca')
        self.admin = User.objects.create_user(
            username='atot10_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self._n = 0

    def _ligne(self, devis, designation, *, quantite=1, prix=0, variante=''):
        produit = Produit.objects.create(
            company=self.company, nom=designation,
            prix_vente=Decimal(str(prix)), quantite_stock=100,
            tva=Decimal('20.00'))
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=designation,
            quantite=Decimal(str(quantite)), prix_unitaire=Decimal(str(prix)),
            remise=Decimal('0'), taux_tva=Decimal('20.00'), variante=variante)

    def _devis(self, *, mode='residentiel', option_acceptee='',
               statut=Devis.Statut.ENVOYE, scenario=None):
        self._n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ATOT10-{self._n:04d}',
            client=self.client_obj, statut=statut,
            taux_tva=Decimal('20.00'), mode_installation=mode,
            option_acceptee=option_acceptee,
            etude_params={'scenario': scenario} if scenario else {})
        # Option SANS : 8 panneaux + onduleur réseau.
        self._ligne(devis, 'Panneau Jinko 550W (sans)', quantite=8,
                    prix=1000, variante='sans')
        self._ligne(devis, 'Onduleur réseau Huawei 5kW Monophasé',
                    prix=5000, variante='sans')
        # Option AVEC : 10 panneaux + hybride + batterie.
        self._ligne(devis, 'Panneau Jinko 550W (avec)', quantite=10,
                    prix=1000, variante='avec')
        self._ligne(devis, 'Onduleur hybride Deye 5kW Monophasé', prix=7000,
                    variante='avec')
        self._ligne(devis, 'Batterie Dyness 10 kWh', prix=12000,
                    variante='avec')
        # Ligne commune.
        self._ligne(devis, 'Transport et mise en service', prix=1000)
        return Devis.objects.get(pk=devis.pk)

    def _ttc_imprime(self, devis):
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/proforma-pdf/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', ''))
        texte = _texte_pdf(resp.content)
        trouve = _RE_TTC.search(texte)
        self.assertIsNotNone(trouve, texte[-800:])
        return Decimal(trouve.group(1))

    def _verifier(self, devis, option_attendue):
        self.assertEqual(option_effective(devis), option_attendue)
        attendu = option_totaux(devis, option_attendue)['ttc']
        autre = option_totaux(
            devis, AVEC_BATTERIE if option_attendue == SANS_BATTERIE
            else SANS_BATTERIE)['ttc']
        self.assertNotEqual(attendu, autre)  # le cas discrimine bien
        imprime = self._ttc_imprime(devis)
        self.assertEqual(imprime, attendu)
        self.assertEqual(
            imprime, Decimal(str(devis.total_ttc)).quantize(Decimal('0.01')))

    def test_industriel_non_accepte_imprime_l_offre_reseau(self):
        """LE rouge (sonde V2 TSORT-2) : aujourd'hui le pro-forma sert AVEC."""
        self._verifier(self._devis(mode='industriel'), SANS_BATTERIE)

    def test_residentiel_non_accepte_imprime_avec(self):
        self._verifier(self._devis(mode='residentiel'), AVEC_BATTERIE)

    def test_ci_accepte_avec_imprime_avec(self):
        self._verifier(
            self._devis(mode='commercial', option_acceptee=AVEC_BATTERIE,
                        statut=Devis.Statut.ACCEPTE),
            AVEC_BATTERIE)

    def test_scenario_mono_sans_batterie_imprime_sans(self):
        self._verifier(
            self._devis(mode='residentiel', scenario='Sans batterie'),
            SANS_BATTERIE)
