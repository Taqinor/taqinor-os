"""ACAL98 (C-ACAL-107) — le devis né ou resynchronisé depuis le module
calepinage reçoit l'affiche 3D du calepinage : une COPIE des octets sous la
clé du devis (``roofs/<company>/<reference>.<ext>``), jamais une clé partagée.

* « Générer le devis » (POST calepinages/<id>/generer-devis/) pose
  ``Devis.roof_image`` et ``quote_engine.builder._roof_render_data_uri(devis)``
  n'est plus vide ;
* « Resynchroniser le devis » (POST calepinages/<id>/sync-devis/) après une
  modification remplace l'affiche du devis par le rendu courant ;
* réécrire ensuite l'image du calepinage ne change PAS les octets du devis.

Magasin RÉEL de la pile de test (MinIO, même client que
``upload_roof_image``) : aucun mock du stockage sous test. Seuls la
composition et son pré-vol sont simulés pour « Générer » (ils ont leurs
propres tests) ; la resynchro est réelle.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_affiche_depuis_calepinage"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from apps.stock.models import Produit
from apps.ventes import services as ventes_services
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.quote_engine.builder import _roof_render_data_uri
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
WATT = 710

PNG_A = b'\x89PNG\r\n\x1a\n' + b'A' * 48
PNG_B = b'\x89PNG\r\n\x1a\n' + b'B' * 48


def _layout(panneaux):
    return {
        'scenario': 'reseau',
        'panelWatt': WATT,
        'result': {'panels': panneaux,
                   'kwc': round(panneaux * WATT / 1000, 2),
                   'annualKwh': 14000, 'savings': 12000},
    }


class AfficheDepuisCalepinage(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ACAL98 Co',
                                              slug='acal98-co')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='acal98', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(company=self.company,
                                                nom='Client ACAL98')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='ACAL98',
            telephone='+212600000098', ville='Casablanca')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='A98-PAN', prix_vente=Decimal('1166.67'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 10kW Monophasé',
            sku='A98-OND', prix_vente=Decimal('14000'),
            prix_achat=Decimal('9000'), quantite_stock=100)

    # ── fixtures ────────────────────────────────────────────────────────
    def _calepinage(self, panneaux=12, devis=None):
        layout = _layout(panneaux)
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, devis=devis,
            titre='ACAL98', roof_layout=layout,
            layout_hash=layout_hash(layout))
        self._poser_image_calepinage(calepinage, PNG_A)
        return calepinage

    def _poser_image_calepinage(self, calepinage, octets):
        # La clé que POST calepinages/<id>/roof-image/ dérive (CAL19).
        cle = f'roofs/{self.company.pk}/calepinage-{calepinage.pk}.png'
        ventes_services.stocker_image_toiture(octets, cle,
                                              content_type='image/png')
        calepinage.roof_image = cle
        calepinage.save(update_fields=['roof_image'])
        return cle

    def _devis(self, reference_suffixe, panneaux=12):
        devis = Devis.objects.create(
            company=self.company,
            reference=f'DEV-{MONTH}-98{reference_suffixe}',
            client=self.client_obj, lead=self.lead, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params={}, created_by=self.user,
            roof_layout=_layout(panneaux),
            layout_hash=layout_hash(_layout(panneaux)))
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation=self.panneau.nom,
            quantite=Decimal(panneaux), prix_unitaire=Decimal('1166.67'),
            remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=self.onduleur,
            designation=self.onduleur.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('14000'), remise=Decimal('0'), ordre=1)
        return devis

    def _generer(self, calepinage, devis_construit):
        with mock.patch('apps.ventes.services.validate_composition_for_layout',
                        return_value=[]), \
                mock.patch('apps.ventes.services.build_devis_from_layout',
                           return_value=devis_construit):
            return self.api.post(
                f'/api/django/calepinage/calepinages/{calepinage.pk}'
                '/generer-devis/', {}, format='json')

    def _cle_attendue(self, devis):
        return f'roofs/{self.company.pk}/{devis.reference}.png'

    # ── tests ───────────────────────────────────────────────────────────
    def test_generer_devis_pose_affiche(self):
        calepinage = self._calepinage()
        devis = self._devis('01')
        self.assertEqual(_roof_render_data_uri(devis), '')

        r = self._generer(calepinage, devis)
        self.assertEqual(r.status_code, 201, r.data)

        devis.refresh_from_db()
        self.assertEqual(devis.roof_image, self._cle_attendue(devis))
        # Une COPIE sous la clé du devis, jamais la clé du calepinage.
        self.assertNotEqual(devis.roof_image, calepinage.roof_image)
        self.assertEqual(
            ventes_services.lire_fichier_toiture(devis.roof_image), PNG_A)
        self.assertTrue(
            _roof_render_data_uri(devis).startswith('data:image/png;base64,'))

    def test_resync_module_remplace_affiche(self):
        devis = self._devis('02')
        calepinage = self._calepinage(panneaux=12, devis=devis)
        # Le devis porte une ANCIENNE affiche.
        ventes_services.stocker_image_toiture(
            PNG_B, self._cle_attendue(devis), content_type='image/png')
        devis.roof_image = self._cle_attendue(devis)
        devis.save(update_fields=['roof_image'])

        # Modification de la conception (12 → 14) puis resynchro module.
        nouveau = _layout(14)
        calepinage.roof_layout = nouveau
        calepinage.layout_hash = layout_hash(nouveau)
        calepinage.save(update_fields=['roof_layout', 'layout_hash'])
        r = self.api.post(
            f'/api/django/calepinage/calepinages/{calepinage.pk}/sync-devis/',
            {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['inchange'])

        devis.refresh_from_db()
        self.assertEqual(devis.roof_image, self._cle_attendue(devis))
        self.assertEqual(
            ventes_services.lire_fichier_toiture(devis.roof_image), PNG_A)

    def test_affiche_devis_independante_du_calepinage(self):
        calepinage = self._calepinage()
        devis = self._devis('03')
        r = self._generer(calepinage, devis)
        self.assertEqual(r.status_code, 201, r.data)
        devis.refresh_from_db()
        cle_devis = devis.roof_image
        self.assertTrue(cle_devis)

        # Le calepinage est redessiné : son rendu change…
        self._poser_image_calepinage(calepinage, PNG_B)

        # … l'affiche du devis, elle, ne change que par un geste explicite.
        devis.refresh_from_db()
        self.assertEqual(devis.roof_image, cle_devis)
        self.assertEqual(
            ventes_services.lire_fichier_toiture(cle_devis), PNG_A)
