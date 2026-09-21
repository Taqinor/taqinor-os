"""AUD601 — aucune FK cross-app d'un sérialiseur AO ne peut pointer une AUTRE
société.

Ce qui est prouvé ici :

* **les deux surfaces CRITIQUES par l'API réelle** — une ligne de bordereau et
  un équipement d'AO postés avec le ``produit`` d'une société voisine sont
  refusés en 400 sur le champ ``produit``. Ces deux valeurs sont RENDUES dans
  des pièces remises à l'ACHETEUR (bordereau des prix, onglet Équipements) :
  la fuite se lirait chez le client final, jamais dans un log ;
* les cinq autres FK cross-app AO (pièces du DCE, caution, pièce
  administrative, kit, variante) refusent la même écriture par le chemin PATCH ;
* le mixin ne gêne PAS le cas normal : une FK de la MÊME société passe.

Run :
    python manage.py test apps.ao.tests.test_aud601_fk_meme_societe -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import (
    AppelOffre, BatimentAO, BordereauPrix, EquipementAO, KitCalepinage,
    ToitureAO, VarianteCalepinage,
)
from apps.ao.permissions import AO_GERER, AO_VOIR
from apps.ao.serializers import (
    CautionSoumissionSerializer, KitCalepinageSerializer,
    PieceAdministrativeSerializer, PieceConsultationSerializer,
    VarianteCalepinageSerializer,
)
from apps.records.models import Attachment
from apps.roles.models import Role
from apps.stock.models import Produit
from authentication.models import Company
from core.models import BackgroundJob

User = get_user_model()

BASE = '/api/django/ao/'


class BaseDeuxSocietes(TestCase):
    """Deux sociétés voisines, chacune avec son catalogue et ses pièces."""

    def setUp(self):
        self.nous = Company.objects.create(nom='AUD601 Nous',
                                           slug='aud601-nous')
        self.eux = Company.objects.create(nom='AUD601 Eux', slug='aud601-eux')

        self.ao = AppelOffre.objects.create(
            company=self.nous, reference='AO-601-1', objet='FK scoping')
        self.bordereau = BordereauPrix.objects.create(
            company=self.nous, appel_offre=self.ao)

        self.produit_nous = Produit.objects.create(
            company=self.nous, nom='Module 625 W (nous)',
            prix_vente=Decimal('1000.00'))
        self.produit_eux = Produit.objects.create(
            company=self.eux, nom='Module 625 W (eux)',
            prix_vente=Decimal('1000.00'))

        role = Role.objects.create(company=self.nous, nom='AUD601 gestion',
                                   permissions=[AO_VOIR, AO_GERER])
        self.user = User.objects.create_user(
            username='aud601', password='x', company=self.nous, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    # ── outils ────────────────────────────────────────────────────────────
    def _contexte(self):
        """Contexte de sérialiseur portant la société courante."""
        class _Req:
            user = self.user
        return {'request': _Req()}

    def _attachment(self, company):
        return Attachment.objects.create(
            company=company,
            content_type=ContentType.objects.get_for_model(AppelOffre),
            object_id=self.ao.pk, file_key='k', filename='f.pdf')

    def _refuse(self, serializer_cls, champ, valeur_etrangere,
                valeur_locale):
        """PATCH partiel : la valeur étrangère est refusée, la locale passe."""
        etranger = serializer_cls(
            data={champ: valeur_etrangere}, partial=True,
            context=self._contexte())
        self.assertFalse(
            etranger.is_valid(),
            f'{serializer_cls.__name__}.{champ} accepte une ligne voisine')
        self.assertIn(champ, etranger.errors)

        local = serializer_cls(
            data={champ: valeur_locale}, partial=True,
            context=self._contexte())
        local.is_valid()
        self.assertNotIn(
            champ, local.errors,
            f'{serializer_cls.__name__}.{champ} refuse sa PROPRE société')


class TestSurfacesCritiques(BaseDeuxSocietes):
    """Les deux FK qui atteignent un document remis à l'ACHETEUR."""

    def test_ligne_de_bordereau_refuse_un_produit_voisin(self):
        reponse = self.api.post(f'{BASE}lignes-bordereau/', {
            'bordereau': self.bordereau.pk,
            'designation': 'Fourniture et pose modules',
            'quantite': '10.000',
            'prix_unitaire': '1000.00',
            'produit': self.produit_eux.pk,
        }, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('produit', reponse.data)

    def test_ligne_de_bordereau_accepte_son_propre_produit(self):
        reponse = self.api.post(f'{BASE}lignes-bordereau/', {
            'bordereau': self.bordereau.pk,
            'designation': 'Fourniture et pose modules',
            'quantite': '10.000',
            'prix_unitaire': '1000.00',
            'produit': self.produit_nous.pk,
        }, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)

    def test_equipement_ao_refuse_un_produit_voisin(self):
        reponse = self.api.post(f'{BASE}equipements/', {
            'appel_offre': self.ao.pk,
            'role': EquipementAO.Role.MODULE,
            'designation': 'Module 625 W',
            'produit': self.produit_eux.pk,
        }, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('produit', reponse.data)

    def test_equipement_ao_accepte_son_propre_produit(self):
        reponse = self.api.post(f'{BASE}equipements/', {
            'appel_offre': self.ao.pk,
            'role': EquipementAO.Role.MODULE,
            'designation': 'Module 625 W',
            'produit': self.produit_nous.pk,
        }, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)


class TestAutresFkAo(BaseDeuxSocietes):
    """Une FK cross-app par sérialiseur AO restant."""

    def test_piece_consultation_attachment(self):
        self._refuse(PieceConsultationSerializer, 'attachment',
                     self._attachment(self.eux).pk,
                     self._attachment(self.nous).pk)

    def test_caution_soumission_attachment(self):
        self._refuse(CautionSoumissionSerializer, 'attachment',
                     self._attachment(self.eux).pk,
                     self._attachment(self.nous).pk)

    def test_piece_administrative_attachment(self):
        self._refuse(PieceAdministrativeSerializer, 'attachment',
                     self._attachment(self.eux).pk,
                     self._attachment(self.nous).pk)

    def test_kit_calepinage_produit(self):
        self._refuse(KitCalepinageSerializer, 'produit',
                     self.produit_eux.pk, self.produit_nous.pk)

    def test_variante_calepinage_job(self):
        job_eux = BackgroundJob.objects.create(
            company=self.eux, user=self.user, kind='calepinage')
        job_nous = BackgroundJob.objects.create(
            company=self.nous, user=self.user, kind='calepinage')
        self._refuse(VarianteCalepinageSerializer, 'job',
                     job_eux.pk, job_nous.pk)


class TestKitEtVarianteParLOrm(BaseDeuxSocietes):
    """Le garde vit au SÉRIALISEUR : l'ORM interne reste libre.

    Les services internes (calepinage, engagement) écrivent sans requête HTTP ;
    les casser aurait été un dommage collatéral, pas une sécurité.
    """

    def test_l_orm_direct_n_est_pas_garde(self):
        kit = KitCalepinage.objects.create(
            company=self.nous, code='K601', libelle='Kit',
            pas_rangee_m=Decimal('1.000'),
            longueur_pente_m=Decimal('2.000'), produit=self.produit_nous)
        self.assertEqual(kit.produit_id, self.produit_nous.pk)

    def test_une_variante_sans_job_reste_valide(self):
        batiment = BatimentAO.objects.create(
            company=self.nous, appel_offre=self.ao, code='A',
            designation='Bâtiment A')
        toiture = ToitureAO.objects.create(
            company=self.nous, batiment=batiment, forme='rectangle')
        variante = VarianteCalepinage.objects.create(
            company=self.nous, appel_offre=self.ao, toiture=toiture,
            nom='V1')
        self.assertIsNone(variante.job_id)
