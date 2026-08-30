"""QJR104 — un optimum du moteur ne se publie pas sans sa configuration.

CE QUE CE MODULE TIENT. Le moteur de dimensionnement rend des blocs d'OPTIMUM
— ``meilleure_falaise``, ``recommandation_avec``, chaque LIGNE de balayage —
qui décrivent une configuration que le balayage a seulement TROUVÉE. Chaque
consommateur la DÉPOUILLAIT pour publier le nombre nu comme celui du client :
c'est le patron qui a produit les deux pires défauts client-facing de l'audit
L3 (le résiduel de falaise imprimé dans le PDF, QJR13 ; le taux de remplissage
batterie servi à la page publique, QJR14) — deux corrections du MÊME défaut,
écrites deux fois, dans deux vocabulaires.

QJR104 pose le TYPE qui manquait :
:class:`~apps.ventes.dimensionnement.Optimum` (une valeur INSÉPARABLE de sa
:class:`~apps.ventes.dimensionnement.ConfigInstallation`) et
:func:`~apps.ventes.dimensionnement.publier_si_decrit`, la seule porte par
laquelle ce nombre devient publiable.

LES QUATRE SURFACES, ET OÙ CHACUNE EST PROUVÉE.

* **charge utile publique** — ici (:class:`ChargeUtilePubliqueTests`) : la clé
  est ABSENTE, jamais à zéro ;
* **page publique** — la page Astro lit CETTE charge utile
  (``apps/web/src/lib/proposition.ts``) : une clé absente n'y rend rien. Il n'y
  a pas de seconde source à garder ;
* **PDF 3 pages et PDF une page** — les deux formats lisent le MÊME
  ``generate_devis_premium._falaise_context`` (sa docstring le dit, et
  ``test_quote_engine_formats`` le RE-PROUVE sur des documents rendus par
  WeasyPrint : ``test_qjr13_falaise_dune_autre_batterie_disparait_des_deux_
  formats``). Ici on prouve la SOURCE COMMUNE sans payer un rendu natif
  (:class:`SourceDuPdfTests`), et surtout que le jumeau vendoré et la règle
  canonique rendent le MÊME verdict sur toute la table de cas
  (:class:`JumeauVendoreTests`) — c'est cette dernière assertion qui empêche
  les deux écritures de re-diverger.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_optimum_publie -v 2
"""
import itertools
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes import dimensionnement as D
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()

_seq = itertools.count(1)


# ═══════════════════════════════════════════════════════════════════════════
# LA TABLE DE CAS — partagée par la règle canonique ET le jumeau vendoré
# ═══════════════════════════════════════════════════════════════════════════

#: ``(nom, panneaux_optimum, batterie_optimum, panneaux_vendus,
#:   batterie_vendue, verdict attendu)``. Elle couvre les trois familles de
#: refus (panneaux différents, capacité différente, côté illisible) et les
#: DEUX bornes de la tolérance.
CAS = (
    ('concordance exacte', 14, 5.0, 14, 5.0, True),
    ('écart de capacité sous la tolérance', 14, 5.02, 14, 5.0, True),
    ('écart de capacité À la tolérance', 14, 5.05, 14, 5.0, True),
    ('écart de capacité au-dessus', 14, 5.5, 14, 5.0, False),
    ('autre capacité (le défaut QJR13)', 14, 10.0, 14, 5.0, False),
    ('autres panneaux', 20, 5.0, 14, 5.0, False),
    ('devis sans batterie', 14, 5.0, 14, None, False),
    ('optimum sans capacité', 14, None, 14, 5.0, False),
    ('panneaux du devis inconnus', 14, 5.0, None, 5.0, False),
    ('panneaux de l\'optimum illisibles', None, 5.0, 14, 5.0, False),
    ('booléen déguisé en panneaux', True, 5.0, 14, 5.0, False),
    ('capacité en texte', 14, '5', 14, 5.0, False),
)


# ═══════════════════════════════════════════════════════════════════════════
# (1) LE TYPE — gelé, et honnête sur ce qu'il ne sait pas
# ═══════════════════════════════════════════════════════════════════════════

class TypeOptimumTests(SimpleTestCase):

    def test_la_configuration_est_gelee(self):
        config = D.ConfigInstallation(panneaux=14, batterie_kwh=5.0, kwc=7.7)
        with self.assertRaises(AttributeError):
            config.panneaux = 20
        self.assertEqual(config.panneaux, 14)

    def test_l_optimum_est_gele(self):
        optimum = D.Optimum(420.0, D.ConfigInstallation(14, 5.0, 7.7))
        with self.assertRaises(AttributeError):
            optimum.valeur = 1.0
        self.assertEqual(optimum.valeur, 420.0)

    def test_deux_configurations_identiques_sont_egales(self):
        self.assertEqual(D.ConfigInstallation(14, 5.0, 7.7),
                         D.ConfigInstallation(14, 5.0, 7.7))
        self.assertNotEqual(D.ConfigInstallation(14, 5.0, 7.7),
                            D.ConfigInstallation(14, 10.0, 7.7))

    def test_un_bloc_malforme_rend_une_config_non_identifiable(self):
        for bloc in (None, {}, 'oops', [], {'panneaux': 'quatorze'},
                     {'panneaux': 14}, {'batterie_kwh': 5.0}):
            with self.subTest(bloc=bloc):
                self.assertFalse(D.config_du_bloc(bloc).identifiable)

    def test_un_booleen_n_est_jamais_un_compte_de_panneaux(self):
        """``int(True) == 1`` — le refus doit être EXPLICITE."""
        config = D.config_du_bloc({'panneaux': True, 'batterie_kwh': 5.0})
        self.assertIsNone(config.panneaux)
        self.assertFalse(config.identifiable)

    def test_optimum_du_bloc_suit_un_chemin_pointe(self):
        bloc = {'panneaux': 14, 'kwc': 7.7, 'batterie_kwh': 5.0,
                'remplissage': {'moyen': 0.62}}
        optimum = D.optimum_du_bloc(bloc, 'remplissage.moyen')
        self.assertEqual(optimum.valeur, 0.62)
        self.assertEqual(optimum.config,
                         D.ConfigInstallation(14, 5.0, 7.7))

    def test_un_chemin_absent_rend_une_valeur_nulle_pas_une_erreur(self):
        optimum = D.optimum_du_bloc({'panneaux': 14, 'batterie_kwh': 5.0},
                                    'remplissage.moyen')
        self.assertIsNone(optimum.valeur)
        self.assertEqual(optimum.config.panneaux, 14)

    def test_optima_publiables_rend_les_trois_nombres_client_facing(self):
        dim = {
            'meilleure_falaise': {
                'panneaux': 14, 'kwc': 7.7, 'batterie_kwh': 5.0,
                'residuel_kwh_mois': 420.0,
                'tranche_apres': {'libelle': 'Tranche 5 (401-500 kWh)'},
            },
            'recommandation_avec': {
                'panneaux': 14, 'kwc': 7.7, 'batterie_kwh': 5.0,
                'remplissage': {'moyen': 0.62},
            },
        }
        optima = D.optima_publiables(dim)
        self.assertEqual(set(optima), {'residuel_falaise',
                                       'tranche_apres_falaise',
                                       'remplissage_recommandation'})
        self.assertEqual(optima['residuel_falaise'].valeur, 420.0)
        self.assertEqual(optima['tranche_apres_falaise'].valeur,
                         'Tranche 5 (401-500 kWh)')
        self.assertEqual(optima['remplissage_recommandation'].valeur, 0.62)
        for optimum in optima.values():
            self.assertEqual(optimum.config,
                             D.ConfigInstallation(14, 5.0, 7.7))

    def test_optima_publiables_ne_leve_jamais_sur_un_bloc_absent(self):
        for dim in (None, {}, 'oops', {'meilleure_falaise': 'oops'}):
            with self.subTest(dim=dim):
                optima = D.optima_publiables(dim)
                self.assertEqual(len(optima), 3)
                for optimum in optima.values():
                    self.assertIsNone(optimum.valeur)
                    self.assertFalse(optimum.config.identifiable)

    def test_optimum_de_ligne_porte_la_config_AVEC_batterie_de_la_ligne(self):
        """Le piège nommé par QJR104 : ``residuel_kwh_mois`` d'une ligne décrit
        son meilleur palier AVEC batterie, pas la variante SANS."""
        ligne = {'panneaux': 18, 'kwc': 9.9, 'batterie_kwh': 10.0,
                 'residuel_kwh_mois': 300.0, 'residuel_sans_kwh_mois': 700.0}
        optimum = D.optimum_de_ligne(ligne)
        self.assertEqual(optimum.valeur, 300.0)
        self.assertEqual(optimum.config.batterie_kwh, 10.0)


# ═══════════════════════════════════════════════════════════════════════════
# (2) LA RÈGLE — écrite une fois, vérifiée sur toute la table
# ═══════════════════════════════════════════════════════════════════════════

class RegleDeConcordanceTests(SimpleTestCase):

    def test_la_table_de_cas_est_tranchee_comme_annonce(self):
        for (nom, pan_o, bat_o, pan_v, bat_v, attendu) in CAS:
            with self.subTest(cas=nom):
                self.assertEqual(
                    D.decrit(D.config_du_bloc({'panneaux': pan_o,
                                               'batterie_kwh': bat_o}),
                             D.ConfigInstallation(panneaux=pan_v,
                                                  batterie_kwh=bat_v)),
                    attendu, nom)

    def test_la_regle_de_capacite_ignore_les_panneaux(self):
        """``decrit_la_capacite`` est la moitié STOCKAGE : QJR14 s'en contente
        pour le taux de remplissage, qui décrit le régime de la batterie."""
        optimum = D.config_du_bloc({'panneaux': 20, 'batterie_kwh': 5.0})
        vendue = D.ConfigInstallation(panneaux=14, batterie_kwh=5.0)
        self.assertTrue(D.decrit_la_capacite(optimum, vendue))
        self.assertFalse(D.decrit(optimum, vendue))

    def test_une_config_absente_des_deux_cotes_ne_publie_rien(self):
        for gauche in (None, 'oops', D.ConfigInstallation()):
            for droite in (None, 'oops', D.ConfigInstallation()):
                with self.subTest(gauche=gauche, droite=droite):
                    self.assertFalse(D.decrit(gauche, droite))
                    self.assertFalse(D.decrit_la_capacite(gauche, droite))


# ═══════════════════════════════════════════════════════════════════════════
# (3) LE JUMEAU VENDORÉ — il ne peut pas diverger en silence
# ═══════════════════════════════════════════════════════════════════════════

class JumeauVendoreTests(SimpleTestCase):
    """``generate_devis_premium`` n'importe RIEN de ``apps`` (moteur vendoré,
    exécutable en ``__main__``) : il porte donc un jumeau de la règle. Ce test
    est ce qui empêche les deux écritures de re-diverger — la MÊME table, le
    MÊME verdict."""

    def test_le_moteur_vendore_tranche_comme_la_regle_canonique(self):
        from apps.ventes.quote_engine import generate_devis_premium as G

        for (nom, pan_o, bat_o, pan_v, bat_v, attendu) in CAS:
            with self.subTest(cas=nom):
                verdict = G._decrit(G._config_identifiante(pan_o, bat_o),
                                    G._config_identifiante(pan_v, bat_v))
                self.assertEqual(verdict, attendu, nom)

    def test_la_tolerance_est_le_meme_nombre_des_deux_cotes(self):
        from apps.ventes.quote_engine import generate_devis_premium as G

        self.assertEqual(G.TOLERANCE_CAPACITE_KWH, D.TOLERANCE_CAPACITE_KWH)


# ═══════════════════════════════════════════════════════════════════════════
# Fixture — un devis résidentiel qui vend 14 panneaux et 5 kWh
# ═══════════════════════════════════════════════════════════════════════════

LIGNES = (
    ('Onduleur hybride Deye 10kW Triphasé', '1', '24000'),
    ('Panneau Canadian Solar 550W', '14', '1100'),
    ('Batterie Dyness 5 kWh', '1', '14000'),
    ('Installation', '1', '4000'),
)

#: La configuration que la fixture VEND — jamais un nombre inventé : elle est
#: relue sur les lignes par ``config_vendue_du_devis`` dans le premier test.
PANNEAUX_VENDUS = 14
CAPACITE_VENDUE = 5.0


class _DevisBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from authentication.models import Company
        cls.company = Company.objects.create(slug='qjr104-co',
                                             nom='QJR104 Co')
        cls.user = User.objects.create_user(
            username='qjr104', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Tazi', prenom='Nadia',
            email='n@example.com', telephone='+212600000105')
        cls.produits = {
            designation: Produit.objects.create(
                company=cls.company, nom=designation, sku=f'QJR104-{index}',
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)
            for index, (designation, _q, prix) in enumerate(LIGNES)
        }

    def _devis(self, dimensionnement=None):
        n = next(_seq)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-QJR104-{n:04d}',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user, mode_installation='residentiel',
            etude_params=({'dimensionnement': dimensionnement}
                          if dimensionnement is not None else {}))
        for designation, qte, prix in LIGNES:
            LigneDevis.objects.create(
                devis=devis, produit=self.produits[designation],
                designation=designation, quantite=Decimal(qte),
                prix_unitaire=Decimal(prix), remise=Decimal('0'))
        return devis

    def _devis_sans_batterie(self, dimensionnement):
        n = next(_seq)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-QJR104-{n:04d}',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user, mode_installation='residentiel',
            etude_params={'dimensionnement': dimensionnement})
        for designation, qte, prix in LIGNES:
            if 'Batterie' in designation:
                continue
            LigneDevis.objects.create(
                devis=devis, produit=self.produits[designation],
                designation=designation, quantite=Decimal(qte),
                prix_unitaire=Decimal(prix), remise=Decimal('0'))
        return devis


def _dim(panneaux=PANNEAUX_VENDUS, batterie=CAPACITE_VENDUE):
    """Un bloc ``etude_params['dimensionnement']`` complet, paramétrable."""
    combinaison = {
        'panneaux': panneaux, 'kwc': 7.7, 'batterie_kwh': batterie,
        'residuel_kwh_mois': 420.0,
        'tranche_apres': {'rang': 5, 'libelle': 'Tranche 5 (401-500 kWh)'},
        'remplissage': {'moyen': 0.62},
    }
    return {
        'falaise': {
            'tranche_actuelle': {'rang': 6, 'libelle': 'Tranche 6 (>500)'},
            'tranche_visee': {'rang': 5, 'libelle': 'Tranche 5 (401-500)'},
            'cible_kwh_mois': 500.0,
        },
        'meilleure_falaise': dict(combinaison),
        'recommandation_avec': dict(combinaison),
    }


# ═══════════════════════════════════════════════════════════════════════════
# (4) publier_si_decrit sur un VRAI devis
# ═══════════════════════════════════════════════════════════════════════════

class PublierSiDecritTests(_DevisBase):

    def test_la_config_vendue_est_relue_sur_les_lignes(self):
        config = D.config_vendue_du_devis(self._devis())
        self.assertEqual(config.panneaux, PANNEAUX_VENDUS)
        self.assertAlmostEqual(config.batterie_kwh, CAPACITE_VENDUE, places=2)

    def test_un_optimum_concordant_publie_sa_valeur(self):
        devis = self._devis(_dim())
        optima = D.optima_publiables(devis.etude_params['dimensionnement'])
        self.assertEqual(
            D.publier_si_decrit(optima['residuel_falaise'], devis), 420.0)
        self.assertEqual(
            D.publier_si_decrit(optima['tranche_apres_falaise'], devis),
            'Tranche 5 (401-500 kWh)')

    def test_un_optimum_d_une_autre_batterie_est_OMIS(self):
        devis = self._devis(_dim(batterie=10.0))
        optima = D.optima_publiables(devis.etude_params['dimensionnement'])
        for nom, optimum in optima.items():
            with self.subTest(optimum=nom):
                self.assertIsNone(D.publier_si_decrit(optimum, devis))

    def test_un_optimum_d_une_autre_taille_est_OMIS(self):
        devis = self._devis(_dim(panneaux=20))
        optima = D.optima_publiables(devis.etude_params['dimensionnement'])
        self.assertIsNone(
            D.publier_si_decrit(optima['residuel_falaise'], devis))

    def test_un_devis_sans_batterie_ne_publie_aucun_optimum(self):
        devis = self._devis_sans_batterie(_dim())
        optima = D.optima_publiables(devis.etude_params['dimensionnement'])
        for nom, optimum in optima.items():
            with self.subTest(optimum=nom):
                self.assertIsNone(D.publier_si_decrit(optimum, devis))

    def test_publier_si_decrit_refuse_tout_ce_qui_n_est_pas_un_optimum(self):
        devis = self._devis(_dim())
        for entree in (None, 420.0, {'valeur': 420.0}, 'oops'):
            with self.subTest(entree=entree):
                self.assertIsNone(D.publier_si_decrit(entree, devis))


# ═══════════════════════════════════════════════════════════════════════════
# (5) LA CHARGE UTILE PUBLIQUE — la clé est ABSENTE, jamais à zéro
# ═══════════════════════════════════════════════════════════════════════════

class ChargeUtilePubliqueTests(_DevisBase):

    def _payload(self, devis):
        token = str(uuid.uuid4())
        ShareLink.objects.create(company=self.company, devis=devis,
                                 token=token,
                                 niveau=ShareLink.NIVEAU_CONFIANCE)
        reponse = DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(reponse.status_code, 200)
        return reponse.json()

    def test_un_optimum_concordant_est_servi(self):
        payload = self._payload(self._devis(_dim()))
        self.assertEqual(
            payload['tranche_tarifaire'].get('residuel_kwh_mois'), 420.0)
        self.assertEqual(
            payload['batterie_regime'].get('remplissage_moyen_pct'), 62.0)

    def test_une_autre_batterie_retire_les_deux_cles(self):
        payload = self._payload(self._devis(_dim(batterie=10.0)))
        self.assertNotIn('residuel_kwh_mois',
                         payload.get('tranche_tarifaire') or {})
        self.assertNotIn('remplissage_moyen_pct',
                         payload.get('batterie_regime') or {})
        # La tranche ACTUELLE décrit la FACTURE du client — elle reste vraie.
        self.assertEqual(
            (payload['tranche_tarifaire']['tranche_actuelle'] or {})
            .get('libelle'), 'Tranche 6 (>500)')

    def test_une_autre_taille_retire_le_residuel(self):
        payload = self._payload(self._devis(_dim(panneaux=20)))
        self.assertNotIn('residuel_kwh_mois',
                         payload.get('tranche_tarifaire') or {})

    def test_un_devis_sans_batterie_ne_recoit_aucun_des_deux(self):
        payload = self._payload(self._devis_sans_batterie(_dim()))
        self.assertNotIn('residuel_kwh_mois',
                         payload.get('tranche_tarifaire') or {})
        self.assertNotIn('remplissage_moyen_pct',
                         payload.get('batterie_regime') or {})

    def test_la_cle_est_absente_jamais_a_zero(self):
        """Un zéro serait un CHIFFRE — donc un chiffre inventé."""
        payload = self._payload(self._devis(_dim(batterie=10.0)))
        for bloc in ('tranche_tarifaire', 'batterie_regime'):
            for valeur in (payload.get(bloc) or {}).values():
                self.assertNotEqual(valeur, 0)


# ═══════════════════════════════════════════════════════════════════════════
# (6) LA SOURCE DES DEUX FORMATS PDF
# ═══════════════════════════════════════════════════════════════════════════

class SourceDuPdfTests(SimpleTestCase):
    """``_falaise_context`` est LA source des DEUX formats (3 pages et une
    page) : ce qu'elle omet n'est imprimable nulle part. Le rendu natif
    lui-même est exercé par ``test_quote_engine_formats`` (WeasyPrint)."""

    def setUp(self):
        from apps.ventes.quote_engine import generate_devis_premium as G
        self.G = G
        self._sauvegarde = {
            nom: getattr(G, nom, None)
            for nom in ('ETUDE', 'NB_PAN', 'BATTERIE_KWH_TOTAL',
                        'ONEPAGE_BRANCHE')
        }

    def tearDown(self):
        for nom, valeur in self._sauvegarde.items():
            setattr(self.G, nom, valeur)

    def _poser(self, dimensionnement, *, branche=None,
               batterie=CAPACITE_VENDUE):
        self.G.ETUDE = {'dimensionnement': dimensionnement}
        self.G.NB_PAN = PANNEAUX_VENDUS
        self.G.BATTERIE_KWH_TOTAL = batterie
        self.G.ONEPAGE_BRANCHE = branche

    def test_concordant_le_contexte_porte_les_trois_chiffres(self):
        self._poser(_dim())
        contexte = self.G._falaise_context()
        self.assertEqual(contexte['residuel_kwh_mois'], 420.0)
        self.assertEqual(contexte['tranche_apres'], 'Tranche 5 (401-500 kWh)')
        self.assertEqual(contexte['remplissage_pct'], 62)

    def test_divergent_les_trois_chiffres_disparaissent_du_contexte(self):
        for cas, dim in (('autre batterie', _dim(batterie=10.0)),
                         ('autre taille', _dim(panneaux=20))):
            with self.subTest(cas=cas):
                self._poser(dim)
                contexte = self.G._falaise_context()
                self.assertIsNone(contexte['residuel_kwh_mois'])
                self.assertIsNone(contexte['tranche_apres'])
                self.assertIsNone(contexte['remplissage_pct'])
                # La tranche ACTUELLE décrit la facture — elle reste.
                self.assertEqual(contexte['tranche_actuelle'],
                                 'Tranche 6 (>500)')

    def test_la_branche_une_page_sans_batterie_ne_publie_rien(self):
        """Format UNE PAGE, branche « sans » : la configuration facturée ne
        porte aucune batterie, donc aucun optimum batterie ne la décrit."""
        self._poser(_dim(), branche='sans')
        contexte = self.G._falaise_context()
        self.assertIsNone(contexte['residuel_kwh_mois'])
        self.assertIsNone(contexte['remplissage_pct'])

    def test_la_branche_une_page_avec_batterie_publie_comme_le_3_pages(self):
        """MÊME source, MÊME verdict : c'est ce qui garantit que le une-page
        ne survit pas à une correction faite pour le 3 pages."""
        self._poser(_dim(), branche='avec')
        self.assertEqual(self.G._falaise_context()['residuel_kwh_mois'], 420.0)
