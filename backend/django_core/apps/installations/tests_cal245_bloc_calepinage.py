"""CAL245 — le bloc « calepinage retenu » sur le détail chantier (endpoint).

Couvre :
  * ``InstallationSerializer.calepinage`` sert le bloc
    ``{calepinage_id, kwc, nb_modules, planche_url, plan_pose_url}`` pour un
    chantier issu d'un calepinage RETENU, ``None`` sinon (contrat
    ``apps/installations/contract_samples/calepinage_retenu.json``, PACT10) ;
  * aucune migration n'accompagne cette lane : ``Installation`` ne gagne
    aucun champ calepinage (règle fondateur 12/09/2026).

Run :
    python manage.py test apps.installations.tests_cal245_bloc_calepinage -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.variantes import bascule_autorisee
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.installations.models import Installation
from apps.installations.serializers import InstallationSerializer
from apps.ventes.models import Devis
from authentication.models import Company

_seq = itertools.count(1)


def make_company():
    n = next(_seq)
    return Company.objects.create(nom=f'CAL245 Co {n}', slug=f'cal245-co-{n}')


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='CAL245',
        email=f'cal245-{company.id}-{n}@example.invalid')


def make_devis(company, client):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-CAL245-{n}', client=client,
        taux_tva=Decimal('20'))


def make_installation(company, client, devis=None):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CHT-CAL245-{n}', client=client,
        devis=devis)


class TestBlocCalepinageSerializer(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)

    def test_chantier_sans_devis_rend_null(self):
        chantier = make_installation(self.company, self.client_obj)
        data = InstallationSerializer(chantier).data
        self.assertIsNone(data['calepinage'])

    def test_chantier_avec_devis_sans_calepinage_rend_null(self):
        chantier = make_installation(self.company, self.client_obj, self.devis)
        data = InstallationSerializer(chantier).data
        self.assertIsNone(data['calepinage'])

    def test_chantier_issu_d_un_calepinage_rend_le_bloc(self):
        # ACAL107 — le kWc / les modules se lisent sur la CONCEPTION du
        # calepinage (retenir une variante l'y écrit), plus sur la variante.
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=self.devis,
            resultat={'pose': {'kwc': 8.64, 'total_modules': 12}})
        with bascule_autorisee():
            CalepinageVariante.objects.create(
                company=self.company, calepinage=calepinage, nom='V1',
                retenue=True)
        chantier = make_installation(self.company, self.client_obj, self.devis)

        data = InstallationSerializer(chantier).data
        bloc = data['calepinage']
        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['calepinage_id'], calepinage.id)
        self.assertEqual(bloc['kwc'], 8.64)
        self.assertEqual(bloc['nb_modules'], 12)
        self.assertEqual(bloc['planche_url'], f'/calepinage/{calepinage.id}')
        self.assertEqual(
            bloc['plan_pose_url'], f'/ventes/devis/{self.devis.id}/3d')

    def test_installation_ne_gagne_aucun_champ_calepinage(self):
        """Aucune migration chantier n'accompagne CAL245 : le bloc est un
        SerializerMethodField calculé, jamais une colonne persistée."""
        noms_champs = {f.name for f in Installation._meta.get_fields()}
        for interdit in ('calepinage', 'calepinage_id', 'calepinage_retenu'):
            self.assertNotIn(interdit, noms_champs)


class TestBlocChantierKwcVendu(TestCase):
    """ACAL274 (C-ACAL-118) — le bloc du chantier affiche le kWc et les
    modules VENDUS (lignes du devis) et le dessin comme tel, avec l'écart.

    Test rouge d'abord : avant ACAL274 le bloc lisait le ``pose`` du
    calepinage (8,52 kWc dessinés) au lieu des 12 × 550 W vendus (6,6 kWc).
    Hébergé ici (module du bloc chantier existant, CAL245) plutôt que dans un
    fichier ``test_acal_chantier_kwc_vendu.py`` par tâche (garde de placement).
    """

    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)

    def _vendre_12_panneaux_550(self):
        produit = Produit.objects.create(
            company=self.company, nom='Panneau Solar 550W',
            sku=f'ACAL274-PAN-{self.devis.pk}', prix_vente=Decimal('1000'),
            prix_achat=Decimal('1'), quantite_stock=500)
        self.devis.lignes.create(
            produit=produit, designation='Panneau Solar 550W',
            quantite=Decimal('12'), prix_unitaire=Decimal('1000'))

    def _retenir_dessin_8_52(self):
        document = {
            'areas': [{'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
                       'obstacles': [], 'roofType': 'flat', 'pitch': 10,
                       'azimuth': 180}],
            'scenario': 'reseau',
            'result': {'panels': 12, 'kwc': 8.52,
                       'annualKwh': 10800, 'savings': 9200},
        }
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=self.devis,
            roof_layout=document,
            resultat={'pose': {'kwc': 8.52, 'total_modules': 12}})
        with bascule_autorisee():
            CalepinageVariante.objects.create(
                company=self.company, calepinage=calepinage, nom='V1',
                retenue=True)
        return calepinage

    def test_bloc_chantier_kwc_vendu(self):
        self._vendre_12_panneaux_550()
        self._retenir_dessin_8_52()
        chantier = make_installation(self.company, self.client_obj, self.devis)

        bloc = InstallationSerializer(chantier).data['calepinage']
        self.assertEqual(bloc['kwc'], 6.6)
        self.assertEqual(bloc['nb_modules'], 12)
        self.assertEqual(bloc['kwc_source'], 'devis')
        self.assertEqual(bloc['dessin_kwc'], 8.52)
        self.assertEqual(bloc['ecart_kwc'], 1.92)

    def test_sans_ligne_vendue_le_bloc_garde_la_conception(self):
        self._retenir_dessin_8_52()
        chantier = make_installation(self.company, self.client_obj, self.devis)

        bloc = InstallationSerializer(chantier).data['calepinage']
        self.assertEqual(bloc['kwc_source'], 'calepinage')
        self.assertEqual(bloc['kwc'], 8.52)
        self.assertIsNone(bloc['ecart_kwc'])
