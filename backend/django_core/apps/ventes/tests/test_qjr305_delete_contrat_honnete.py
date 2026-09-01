"""QJR305 — LE DELETE D'UNE SURCHARGE REND UN CONTRAT HONNÊTE.

LE ROUGE QUE CES TESTS REPRODUISENT. ``CHEMINS_AVEC_AUTO`` ne déclarait que
QUATRE chemins dérivables (``taille.nb_panneaux``, ``taille.panel_watt``,
``taille.kwc``, ``mode_installation``) alors que le contrat PACT10
``contract_samples/devis_overrides.json`` en autorise DIX-NEUF : sur **15
chemins sur 19**, la réponse du DELETE portait ``auto: null`` ET un effectif
nul — deux états indistinguables (« le moteur n'a pas de valeur » vs « la
valeur est vide »), et l'écran affichait un champ vide dans les deux cas.

CE QUI EST PROUVÉ ICI :

1. pour CHACUN des 19 chemins autorisés, la réponse du DELETE porte soit une
   valeur ``auto`` non nulle, soit ``non_derivable: true`` — jamais un
   ``auto: null`` seul ;
2. le CODE et le CONTRAT disent la même chose (PACT10) — la partition
   dérivable / non dérivable est épinglée contre le fichier committé, comme
   l'est déjà la liste blanche (``test_qjr_overrides_registre``) ;
3. un devis ILLISIBLE rend toujours une carte partielle, sans jamais lever.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr305_delete_contrat_honnete -v 2
"""
import itertools
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain import overrides as R
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

_seq = itertools.count(1)

CONTRAT = (Path(R.__file__).resolve().parent.parent
           / 'contract_samples' / 'devis_overrides.json')

#: Réseau + hybride + batterie + panneaux : le seul montage où TOUS les
#: dérivateurs du moteur ont quelque chose à lire.
LIGNES = (
    ('Onduleur réseau Huawei 10kW Triphasé', 1, '11700'),
    ('Onduleur hybride Deye 10kW Triphasé', 1, '24000'),
    ('Panneau Canadian Solar 710W', 14, '1100'),
    ('Batterie Dyness 10 kWh', 2, '14000'),
)

#: La clef d'équipement RÉELLE utilisée pour l'unique motif dynamique.
CLEF_EQUIPEMENT = R.PREFIXE_EQUIPEMENT + 'piscine'

#: Une valeur MANUELLE plausible par chemin — elle n'a qu'à être posable :
#: ce qui est testé, c'est la réponse du DELETE, pas la valeur.
VALEURS = {
    'taille.nb_panneaux': 21,
    'taille.panel_watt': 545,
    'taille.kwc': 9.99,
    'taille.batterie_nb_modules': 3,
    'taille.batterie_module_kwh': 5.12,
    'scenario': 'Sans batterie',
    'recommended_option': 'Sans batterie',
    'profil.occupation': 'jour',
    'profil.factures_mensuelles_reelles': [1200] * 12,
    'profil.conso_annuelle': 9600,
    CLEF_EQUIPEMENT: {'presente': True},
    'tarif.distributeur': 'ONEE',
    'tarif.tranches': [{'jusqu_a': 100, 'prix': 0.9}],
    'tarif.charges_fixes_mad': 42.5,
    'etude.jour_reference': '2026-03-15',
    'mode_installation': 'residentiel',
    'structure': 'beton',
    'tension': 'triphase',
    'pompe_alim': 'solaire',
}


def chemins_testables():
    """Les 19 chemins de la liste blanche, le motif dynamique CONCRÉTISÉ."""
    return [CLEF_EQUIPEMENT if c.endswith('<clef>') else c
            for c in R.CHAMPS_OVERRIDABLES]


class ContratEtCodeDisentLaMemeChose(SimpleTestCase):
    """PACT10 — la partition vit dans le contrat committé, pas dans une tête."""

    def setUp(self):
        self.contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))

    def test_la_partition_couvre_exactement_les_19_chemins(self):
        derivables = self.contrat['notes']['chemins_derivables']
        non_derivables = list(self.contrat['notes']['chemins_non_derivables'])
        self.assertEqual(
            sorted(derivables + non_derivables),
            sorted(self.contrat['notes']['chemins_autorises']),
            'La partition dérivable / non dérivable doit couvrir la liste '
            'blanche D12 exactement une fois.')

    def test_le_code_recopie_la_partition_du_contrat(self):
        self.assertEqual(sorted(R.CHEMINS_AVEC_AUTO),
                         sorted(self.contrat['notes']['chemins_derivables']))
        self.assertEqual(
            sorted(R.CHEMINS_SANS_AUTO),
            sorted(self.contrat['notes']['chemins_non_derivables']))

    def test_chaque_chemin_non_derivable_dit_POURQUOI(self):
        for chemin, raison in R.CHEMINS_SANS_AUTO.items():
            with self.subTest(chemin=chemin):
                self.assertTrue(raison and len(raison) > 20, chemin)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        from authentication.models import Company

        cls.company = Company.objects.create(slug='qjr305-co',
                                             nom='QJR305 Co')
        cls.user = User.objects.create_user(
            username='qjr305', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Bennani', prenom='Salma',
            email='qjr305@example.com', telephone='+212600000305')
        cls.produits = {
            designation: Produit.objects.create(
                company=cls.company, nom=designation, sku=f'QJR305-{index}',
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)
            for index, (designation, _qte, prix) in enumerate(LIGNES)
        }

    def setUp(self):
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def devis_neuf(self, *, avec_lignes=True):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-QJR305-{next(_seq):04d}',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user, mode_installation='residentiel',
            # Un profil de consommation EXPLOITABLE : sans lui, la lecture
            # unique des entrées (QJR42) s'arrête avant occupation/barème.
            etude_params={'factures_mensuelles_reelles': [900] * 12})
        if avec_lignes:
            for designation, qte, prix in LIGNES:
                LigneDevis.objects.create(
                    devis=devis, produit=self.produits[designation],
                    designation=designation, quantite=Decimal(qte),
                    prix_unitaire=Decimal(prix), remise=Decimal('0'))
        return devis

    def url(self, devis):
        return f'/api/django/ventes/devis/{devis.id}/overrides/'


class LeDeleteNeRendJamaisUnAutoNullMuet(_Base):
    """LE ROUGE : 15 chemins sur 19 rendaient ``auto: null`` sans marqueur."""

    def test_chaque_chemin_autorise_est_explicite(self):
        devis = self.devis_neuf()
        url = self.url(devis)
        for chemin in chemins_testables():
            with self.subTest(chemin=chemin):
                pose = self.api.patch(
                    url, {chemin: {'valeur': VALEURS[chemin]}}, format='json')
                self.assertEqual(pose.status_code, 200,
                                 f'pose de « {chemin} » refusée : {pose.data}')
                reponse = self.api.delete(f'{url}?chemin={chemin}')
                self.assertEqual(reponse.status_code, 200, reponse.data)

                self.assertIn(chemin, reponse.data['effectif'],
                              f'« {chemin} » a DISPARU de la réponse du '
                              f'DELETE au lieu de revenir à l\'automatique.')
                bloc = reponse.data['effectif'][chemin]
                self.assertNotIn(chemin, reponse.data['overrides'])
                self.assertTrue(
                    bloc['auto'] is not None
                    or bloc.get('non_derivable') is True,
                    f'« {chemin} » rend un « auto: null » MUET : ni valeur '
                    f'moteur, ni marqueur « non_derivable ». Bloc = {bloc}')

    def test_un_chemin_derivable_ne_porte_pas_le_marqueur(self):
        """Le marqueur ne doit jamais maquiller une valeur réellement lue."""
        devis = self.devis_neuf()
        url = self.url(devis)
        self.api.patch(url, {'taille.nb_panneaux': {'valeur': 21}},
                       format='json')
        bloc = self.api.delete(
            f'{url}?chemin=taille.nb_panneaux').data['effectif'][
                'taille.nb_panneaux']
        self.assertEqual(bloc['auto'], 14)
        self.assertNotIn('non_derivable', bloc)
        self.assertEqual(bloc['source'], 'auto')

    def test_les_chemins_sans_derivateur_sont_marques(self):
        """Les 6 chemins de ``CHEMINS_SANS_AUTO``, nommément."""
        devis = self.devis_neuf()
        url = self.url(devis)
        for chemin in R.CHEMINS_SANS_AUTO:
            with self.subTest(chemin=chemin):
                self.api.patch(url, {chemin: {'valeur': VALEURS[chemin]}},
                               format='json')
                bloc = self.api.delete(
                    f'{url}?chemin={chemin}').data['effectif'][chemin]
                self.assertIsNone(bloc['auto'])
                self.assertIs(bloc.get('non_derivable'), True)

    def test_le_moteur_derive_bien_les_nouveaux_chemins(self):
        """L'élargissement n'est pas cosmétique : les valeurs sont RÉELLES."""
        autos = R.autos_du_devis(self.devis_neuf())
        self.assertEqual(autos['taille.nb_panneaux'], 14)
        self.assertEqual(autos['taille.batterie_nb_modules'], 2)
        self.assertEqual(autos['taille.batterie_module_kwh'], 10.0)
        self.assertEqual(autos['scenario'], 'Les deux (Sans + Avec)')
        self.assertIn('etude.jour_reference', autos)
        self.assertIn('profil.conso_annuelle', autos)

    def test_la_carte_auto_ignore_toujours_le_registre(self):
        """``auto`` reste la valeur AUTOMATIQUE — y compris sur les chemins
        dont le dérivateur consulte lui-même le registre (jour de référence)."""
        devis = self.devis_neuf()
        self.api.patch(self.url(devis),
                       {'etude.jour_reference': {'valeur': '2026-03-15'}},
                       format='json')
        devis.refresh_from_db()
        self.assertNotEqual(
            R.autos_du_devis(devis).get('etude.jour_reference'), '2026-03-15')


class UnDevisIllisibleRendUneCartePartielle(_Base):
    """Ne lève JAMAIS — un bloc en échec retire SES clés, pas les autres."""

    def test_un_devis_sans_ligne_ne_leve_pas(self):
        autos = R.autos_du_devis(self.devis_neuf(avec_lignes=False))
        self.assertNotIn('taille.nb_panneaux', autos)
        self.assertNotIn('taille.batterie_nb_modules', autos)
        self.assertNotIn('scenario', autos)
        # Ce qui NE dépend pas des lignes reste rendu.
        self.assertEqual(autos['mode_installation'], 'residentiel')

    def test_un_devis_detache_ne_leve_pas(self):
        class _Muet:
            overrides = None
            mode_installation = ''

            @property
            def lignes(self):
                raise RuntimeError('illisible')

        self.assertEqual(R.autos_du_devis(_Muet()), {})

    def test_la_reponse_reste_servie_sur_un_devis_sans_ligne(self):
        devis = self.devis_neuf(avec_lignes=False)
        reponse = self.api.get(self.url(devis))
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('effectif', reponse.data)
