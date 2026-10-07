"""ACAL314 (C-ACAL-019 / C-ACAL-107) — l'affiche de toiture du devis est
servie par un proxy Django MÊME ORIGINE, plus par une URL pré-signée portant
l'hôte interne du magasin (``MINIO_ENDPOINT`` = ``minio:9000``).

* les trois lecteurs navigateur — conception du lead
  (``conception_pour_lead``, fiche), charge publique de la proposition
  (``roof_image_url``) et API publique (``liens.apercu`` d'un calepinage) —
  servent un CHEMIN RELATIF ``/api/django/…``, jamais ``MINIO_ENDPOINT`` ;
* ``GET devis/<id>/roof-image/fichier/`` et
  ``GET proposal/<token>/roof-image/`` rendent 200 image/* avec les octets
  RÉELLEMENT stockés (magasin de la pile de test, aucun mock du stockage) ;
* un devis d'une autre société répond le MÊME 404 qu'un devis sans affiche ;
* un jeton inconnu répond 404.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_roof_image_proxy"
"""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.publicapi.public_serializers import _url_apercu_calepinage
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from apps.stock.models import Produit
from apps.ventes import services as ventes_services
from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.selectors import conception_pour_lead
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
WATT = 710
PNG = b'\x89PNG\r\n\x1a\n' + b'R' * 64


def _layout(panneaux=12):
    return {
        'scenario': 'reseau',
        'panelWatt': WATT,
        'result': {'panels': panneaux,
                   'kwc': round(panneaux * WATT / 1000, 2),
                   'annualKwh': 14000, 'savings': 12000},
    }


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RoofImageProxy(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ACAL314 Co',
                                              slug='acal314-co')
        self.autre = Company.objects.create(nom='ACAL314 Autre',
                                            slug='acal314-autre')
        self.user = self._user(self.company, 'acal314')
        self.user_autre = self._user(self.autre, 'acal314-autre')
        self.api = _api(self.user)
        self.client_obj = Client.objects.create(company=self.company,
                                                nom='Client ACAL314')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='ACAL314',
            telephone='+212600000314', ville='Casablanca',
            facture_hiver=1800, ete_differente=False)
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='A314-PAN', prix_vente=Decimal('1166.67'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 10kW Monophasé',
            sku='A314-OND', prix_vente=Decimal('14000'),
            prix_achat=Decimal('9000'), quantite_stock=100)
        self.devis = self._devis('01', avec_affiche=True)

    def _user(self, company, username):
        role = Role.objects.create(company=company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        return User.objects.create_user(
            username=username, password='x', company=company, role=role,
            role_legacy='responsable')

    def _devis(self, suffixe, *, avec_affiche):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-314{suffixe}',
            client=self.client_obj, lead=self.lead, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params={}, created_by=self.user,
            roof_layout=_layout(), layout_hash=layout_hash(_layout()))
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation=self.panneau.nom,
            quantite=Decimal('12'), prix_unitaire=Decimal('1166.67'),
            remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=self.onduleur,
            designation=self.onduleur.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('14000'), remise=Decimal('0'), ordre=1)
        if avec_affiche:
            cle = f'roofs/{self.company.pk}/{devis.reference}.png'
            ventes_services.stocker_image_toiture(PNG, cle,
                                                  content_type='image/png')
            devis.roof_image = cle
            devis.save(update_fields=['roof_image'])
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        return devis

    def _assert_relatif(self, url, attendu):
        self.assertIsInstance(url, str)
        if settings.MINIO_ENDPOINT:
            self.assertNotIn(settings.MINIO_ENDPOINT, url)
        self.assertFalse(url.startswith('http'), url)
        self.assertEqual(url, attendu)

    def test_url_servie_est_un_chemin_relatif(self):
        # 1. Conception du lead (fiche ERP) — chemin authentifié.
        conception = conception_pour_lead(self.lead, self.company)
        self._assert_relatif(
            conception['image_url'],
            f'/api/django/ventes/devis/{self.devis.pk}/roof-image/fichier/')

        # 2. Charge publique de la proposition — chemin borné par le jeton.
        lien = ShareLink.for_devis(self.devis)
        pub = APIClient().get(f'/api/django/ventes/proposal/{lien.token}/')
        self.assertEqual(pub.status_code, 200, pub.content)
        self._assert_relatif(
            pub.data['roof_image_url'],
            f'/api/django/ventes/proposal/{lien.token}/roof-image/')

        # 3. API publique : l'aperçu d'un calepinage passe par son proxy.
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL314',
            roof_image=f'roofs/{self.company.pk}/calepinage-x.png')
        self._assert_relatif(
            _url_apercu_calepinage(calepinage),
            f'/api/django/calepinage/calepinages/{calepinage.pk}'
            '/roof-image/fichier/')

    def test_fichier_rend_les_octets(self):
        r = self.api.get(
            f'/api/django/ventes/devis/{self.devis.pk}/roof-image/fichier/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r['Content-Type'], 'image/png')
        self.assertEqual(r.content, PNG)

        lien = ShareLink.for_devis(self.devis)
        pub = APIClient().get(
            f'/api/django/ventes/proposal/{lien.token}/roof-image/')
        self.assertEqual(pub.status_code, 200, pub.content)
        self.assertEqual(pub['Content-Type'], 'image/png')
        self.assertEqual(pub.content, PNG)

    def test_devis_autre_societe_404_identique_a_absent(self):
        sans_affiche = self._devis('02', avec_affiche=False)
        absent = self.api.get(
            f'/api/django/ventes/devis/{sans_affiche.pk}/roof-image/fichier/')
        etranger = _api(self.user_autre).get(
            f'/api/django/ventes/devis/{self.devis.pk}/roof-image/fichier/')
        self.assertEqual(absent.status_code, 404)
        self.assertEqual(etranger.status_code, 404)
        self.assertEqual(etranger.content, absent.content)

    def test_jeton_invalide_404(self):
        r = APIClient().get(
            '/api/django/ventes/proposal/jeton-inexistant-acal314/roof-image/')
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(b'\x89PNG', r.content)
