"""CTX3D — la cible 3D décrit UNE option, et le devis « Les deux » les DÉCRIT
toutes les deux.

DEUX DÉFAUTS, UN SEUL SUJET (l'écran de conception 3D, PV17) :

1. ``cible_depuis_lignes`` filtrait ``panneaux``/``kwc`` par variante (L-2OPT)
   mais lisait ``scenario``/``batterie`` sur TOUTES les lignes. Un devis « Les
   deux » rendait donc le compte de panneaux de l'option SANS surmonté de
   ``scenario='avec_batterie'`` : une cible qu'AUCUNE installation ne décrit,
   envoyée telle quelle à l'écran 3D.
2. Le contexte PV17 ne pouvait décrire qu'UNE option — l'écran n'avait aucun
   moyen de savoir que le devis en servait une seconde.

Ce module tient les deux : cohérence des quatre grandeurs de ``cible``, et la
clé sœur OPTIONNELLE ``cible_avec``, présente si et seulement si les lignes
peuvent réellement livrer l'option « Avec batterie » (onduleur hybride ET
batterie — le MÊME critère ``avec_ok`` que le moteur PDF).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_ctx3d_cible_avec -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import cible_depuis_lignes, option_avec_servable

User = get_user_model()

#: Les six clés PV16 — contrat GELÉ, que ``cible_avec`` reprend à l'identique.
CLES_PV16 = {'panneaux', 'kwc', 'panel_watt', 'scenario', 'batterie',
             'avertissements'}
#: Les clés de la racine du contexte PV17, hors clé optionnelle.
CLES_RACINE = {'devis', 'geometrie', 'cible', 'carte', 'modifiable',
               'raison_lecture_seule', 'avertissements'}


class _Base(TestCase):
    def setUp(self):
        from authentication.models import Company

        self.company, _ = Company.objects.get_or_create(
            slug='ctx3d-co', defaults={'nom': 'CTX3D'})
        self.user = User.objects.create_user(
            username='ctx3d_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client CTX3D')
        self.produits = {}
        for cle, nom in (
                ('PAN', 'Panneau Jinko 550W'),
                ('ONDR', 'Onduleur réseau Huawei 5kW Monophasé'),
                ('ONDH', 'Onduleur hybride Deye 5kW Monophasé'),
                ('BAT', 'Batterie Dyness 10 kWh')):
            self.produits[cle] = Produit.objects.create(
                company=self.company, nom=nom, sku='CTX3D-%s' % cle,
                prix_vente=Decimal('1100'), quantite_stock=50)
        self.compteur = 0

    def _devis(self, lignes, **extra):
        """``lignes`` = itérable de ``(clé produit, quantité, variante)``."""
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, reference='DEV-CTX3D-%d' % self.compteur,
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            mode_installation=Devis.ModeInstallation.RESIDENTIEL,
            created_by=self.user, **extra)
        for cle, quantite, variante in lignes:
            produit = self.produits[cle]
            devis.lignes.create(
                produit=produit, designation=produit.nom,
                quantite=Decimal(str(quantite)),
                prix_unitaire=Decimal('1100'), variante=variante)
        return devis

    def _devis_les_deux(self, *, sans=8, avec=10):
        """Le devis « Les deux » : deux comptes de panneaux, un onduleur réseau
        d'un côté, hybride + batterie de l'autre."""
        return self._devis(
            [('PAN', sans, 'sans'), ('PAN', avec, 'avec'),
             ('ONDR', 1, 'sans'), ('ONDH', 1, 'avec'), ('BAT', 1, 'avec')],
            etude_params={'scenario': 'Les deux (Sans + Avec)'})

    def _get(self, devis):
        return self.api.get(
            f'/api/django/ventes/devis/{devis.id}/design-context/')


class LaCibleDecritUneSeuleOption(_Base):
    """Volet 1 — les quatre grandeurs viennent du MÊME sous-ensemble."""

    def test_la_cible_dun_devis_les_deux_est_coherente(self):
        """C'ÉTAIT LE DÉFAUT : 8 panneaux (option SANS) annoncés avec le
        scénario « avec_batterie » (lu sur tout le devis, batterie de l'option
        AVEC comprise). La cible décrivait une installation inexistante."""
        cible = cible_depuis_lignes(self._devis_les_deux(sans=8, avec=10))

        self.assertEqual(cible['panneaux'], 8)
        self.assertEqual(cible['scenario'], 'reseau')
        self.assertFalse(cible['batterie'])

    def test_la_vue_avec_decrit_lautre_option(self):
        cible = cible_depuis_lignes(self._devis_les_deux(sans=8, avec=10),
                                    variante='avec')

        self.assertEqual(cible['panneaux'], 10)
        self.assertEqual(cible['scenario'], 'avec_batterie')
        self.assertTrue(cible['batterie'])

    def test_la_forme_ne_bouge_pas(self):
        """Contrat GELÉ : six clés, quelle que soit la variante demandée."""
        devis = self._devis_les_deux()
        self.assertEqual(set(cible_depuis_lignes(devis)), CLES_PV16)
        self.assertEqual(set(cible_depuis_lignes(devis, variante='avec')),
                         CLES_PV16)

    def test_un_devis_non_variante_est_inchange(self):
        """Non-régression : sans variante, TOUTES les lignes sont communes —
        les deux vues sont identiques et valent le comportement d'hier."""
        devis = self._devis([('PAN', 12, ''), ('ONDH', 1, ''), ('BAT', 1, '')])

        cible = cible_depuis_lignes(devis)
        self.assertEqual(cible['panneaux'], 12)
        self.assertEqual(cible['scenario'], 'avec_batterie')
        self.assertTrue(cible['batterie'])
        self.assertEqual(cible_depuis_lignes(devis, variante='avec'), cible)

    def test_un_devis_reseau_reste_reseau(self):
        cible = cible_depuis_lignes(
            self._devis([('PAN', 14, ''), ('ONDR', 1, '')]))

        self.assertEqual(cible['panneaux'], 14)
        self.assertEqual(cible['scenario'], 'reseau')
        self.assertFalse(cible['batterie'])


class LOptionAvecEstServableOuAbsente(_Base):
    """Volet 2 — le critère ``avec_ok`` : hybride ET batterie, jamais l'un
    sans l'autre."""

    def test_servable_quand_hybride_et_batterie(self):
        self.assertTrue(option_avec_servable(self._devis_les_deux()))
        self.assertTrue(option_avec_servable(
            self._devis([('PAN', 12, ''), ('ONDH', 1, ''), ('BAT', 1, '')])))

    def test_non_servable_sans_batterie(self):
        """Onduleur hybride SEUL : aucune batterie n'est inventée (règle Z1) —
        l'option « avec » n'existe pas."""
        self.assertFalse(option_avec_servable(
            self._devis([('PAN', 12, ''), ('ONDH', 1, '')])))

    def test_non_servable_sans_hybride(self):
        """Une batterie derrière un onduleur RÉSEAU ne fait pas une option
        « avec » : le moteur PDF exige l'hybride (``avec_ok``)."""
        self.assertFalse(option_avec_servable(
            self._devis([('PAN', 12, ''), ('ONDR', 1, ''), ('BAT', 1, '')])))

    def test_la_batterie_de_lautre_option_ne_compte_pas(self):
        """Une batterie déclarée « sans » n'appartient pas au panier « avec »
        (contradiction de saisie) : l'option n'est pas servable pour autant."""
        self.assertFalse(option_avec_servable(
            self._devis([('PAN', 12, ''), ('ONDH', 1, 'avec'),
                         ('BAT', 1, 'sans')])))


class LeContexte3DPorteLesDeuxCibles(_Base):
    """Volet 2 — la clé sœur, dans la réponse HTTP réelle."""

    def test_cible_avec_presente_sur_un_devis_les_deux(self):
        data = self._get(self._devis_les_deux(sans=8, avec=10)).data

        self.assertEqual(set(data), CLES_RACINE | {'cible_avec'})
        # L'option 1 reste la cible principale, cohérente avec elle-même.
        self.assertEqual(data['cible']['panneaux'], 8)
        self.assertEqual(data['cible']['scenario'], 'reseau')
        # L'option 2, même forme, SANS bill_kwh (la conso du client est unique
        # et vit dans `cible`).
        self.assertEqual(set(data['cible_avec']), CLES_PV16)
        self.assertEqual(data['cible_avec']['panneaux'], 10)
        self.assertEqual(data['cible_avec']['scenario'], 'avec_batterie')
        self.assertTrue(data['cible_avec']['batterie'])

    def test_cible_avec_absente_sur_un_devis_reseau(self):
        """ABSENTE, pas ``None`` : l'écran teste la présence, jamais une
        option que ce devis ne peut pas livrer."""
        data = self._get(self._devis([('PAN', 14, ''), ('ONDR', 1, '')])).data

        self.assertEqual(set(data), CLES_RACINE)
        self.assertNotIn('cible_avec', data)

    def test_cible_avec_absente_sur_un_hybride_sans_batterie(self):
        data = self._get(self._devis([('PAN', 12, ''), ('ONDH', 1, '')])).data

        self.assertNotIn('cible_avec', data)
