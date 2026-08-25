"""CAPUTIL — la capacité UTILE des batteries est lue sur la FICHE, pas devinée.

``dimensionnement.capacite_utile_batterie`` documente depuis toujours une
chaîne de résolution en trois temps : ``kwh_usable`` de la fiche, sinon
``kwh_nominal × dod_pct``, sinon seulement le kWh lu dans le NOM du produit.
Les deux premiers étages étaient MORTS : l'appel lisait
``specs_for_produit(p).get('batterie')`` alors que ce sélecteur rend le bloc du
``type_fiche`` DÉJÀ PLAT (son propre docstring avertit que ``['batterie']``
rend toujours ``None``). Le moteur retombait donc systématiquement sur le
NOMINAL de l'étiquette — le seul cas « optimiste » que le docstring promet de
faire disparaître dès que la fiche porte la donnée.

Aucun test ne couvrait ce chemin : les montages existants créent soit des
produits SANS fiche, soit des doubles en mémoire. Ce module tient donc les
trois étages sur de VRAIES ``stock.FicheTechnique``, avec les valeurs
constructeur RÉELLES du catalogue seedé (``seed_catalogue`` : BAT-DEY-5,
BAT-DEY-10, BAT-DYN-HV-16).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_caputil_capacite_utile -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.ventes.dimensionnement import capacite_utile_batterie
from authentication.models import Company


class CapaciteUtileBatterieTest(TestCase):
    """Les trois étages de la chaîne, sur les batteries RÉELLES du catalogue."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Co CAPUTIL',
                                             slug='caputil')

    def _batterie(self, nom, **champs_fiche):
        """Un produit batterie AVEC sa vraie fiche technique stock (PV5)."""
        produit = Produit.objects.create(
            company=self.company, nom=nom, prix_vente=Decimal('20000'))
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche='batterie',
            **champs_fiche)
        # On relit : ``specs_for_produit`` passe par le related ``fiche_technique``
        # du produit, qui n'est pas peuplé sur l'instance qui vient de le créer.
        return Produit.objects.get(pk=produit.pk)

    # ── Étage 1 — ``kwh_usable`` fichée : c'est ELLE qui sort ────────────────
    def test_dyness_5_rend_l_utile_fichee_pas_le_nominal_du_nom(self):
        """Dyness DL5.0C : nominal 5,12 kWh, UTILE 4,60 kWh (constructeur).

        Le nom porte « 5 kWh » : avant CAPUTIL le moteur simulait donc 5,0 kWh
        d'énergie disponible sur un pack qui n'en rend que 4,6.
        """
        produit = self._batterie(
            'Batterie Dyness 5 kWh',
            bat_kwh_nominal=Decimal('5.12'),
            bat_kwh_usable=Decimal('4.60'),
            bat_dod_pct=Decimal('90.0'))

        self.assertAlmostEqual(
            capacite_utile_batterie(produit, 'Batterie Dyness 5 kWh'),
            4.60, places=3)

    def test_dyness_10_rend_l_utile_fichee(self):
        """Dyness Powerbox Pro : nominal 10,24 kWh, UTILE 9,22 kWh."""
        produit = self._batterie(
            'Batterie Dyness 10 kWh',
            bat_kwh_nominal=Decimal('10.24'),
            bat_kwh_usable=Decimal('9.22'),
            bat_dod_pct=Decimal('90.0'))

        self.assertAlmostEqual(
            capacite_utile_batterie(produit, 'Batterie Dyness 10 kWh'),
            9.22, places=3)

    # ── Étage 2 — pas d'utile fichée, mais un DoD : nominal × DoD ────────────
    def test_deye_bos_b_16_sans_utile_derive_du_dod(self):
        """Deye BOS-B-Pack16-A3 : Deye ne publie AUCUNE valeur utile par module
        (``bat_kwh_usable`` est délibérément absent du seeder), seulement un DoD
        recommandé de 90 %. La capacité utile est donc DÉRIVÉE — 16,08 × 90 %
        = 14,472 kWh — au lieu des 16 kWh de l'étiquette.
        """
        nom = 'Batterie Deye BOS-B-Pack16-A3 16 kWh'
        produit = self._batterie(
            nom,
            bat_kwh_nominal=Decimal('16.08'),
            bat_dod_pct=Decimal('90.0'))

        utile = capacite_utile_batterie(produit, nom)
        self.assertAlmostEqual(utile, 14.472, places=3)
        # Et surtout : ce n'est PAS le nominal lu dans le nom.
        self.assertNotAlmostEqual(utile, 16.0, places=2)

    # ── Étage 3 — rien d'exploitable sur la fiche : repli sur le NOM ─────────
    def test_fiche_batterie_muette_replie_sur_le_nom(self):
        """Une fiche batterie qui ne porte ni utile ni nominal ne fabrique
        rien : le moteur retombe sur le kWh du nom, exactement comme avant."""
        nom = 'Batterie générique 7,5 kWh'
        produit = self._batterie(nom, bat_v_nominal=Decimal('51.2'))

        self.assertAlmostEqual(capacite_utile_batterie(produit, nom),
                               7.5, places=3)

    def test_nominal_sans_dod_replie_sur_le_nom(self):
        """Un nominal SANS profondeur de décharge n'autorise aucune dérivation
        (multiplier par un DoD supposé serait un chiffre inventé)."""
        nom = 'Batterie sans DoD 12 kWh'
        produit = self._batterie(nom, bat_kwh_nominal=Decimal('12.80'))

        self.assertAlmostEqual(capacite_utile_batterie(produit, nom),
                               12.0, places=3)

    def test_produit_sans_fiche_replie_sur_le_nom(self):
        """Non-régression : le comportement historique (aucune fiche) est
        strictement conservé."""
        produit = Produit.objects.create(
            company=self.company, nom='Batterie nue 5 kWh',
            prix_vente=Decimal('20000'))

        self.assertAlmostEqual(
            capacite_utile_batterie(produit, 'Batterie nue 5 kWh'),
            5.0, places=3)

    def test_sans_produit_replie_sur_le_nom(self):
        """``produit=None`` (ligne libre saisie à la main) : le nom fait foi."""
        self.assertAlmostEqual(
            capacite_utile_batterie(None, 'Batterie 15 kWh'), 15.0, places=3)

    # ── La lecture est PLATE — le piège qui a rendu le moteur muet ───────────
    def test_le_bloc_batterie_est_plat_dans_le_selecteur(self):
        """Garde de régression DIRECTE : ``specs_for_produit`` rend les clés
        ``kwh_usable``/``kwh_nominal``/``dod_pct`` À LA RACINE. Re-introduire un
        ``.get('batterie')`` rendrait ``None`` et remettrait tout le moteur sur
        l'étiquette, sans qu'aucune exception ne le signale.
        """
        from apps.stock.selectors import specs_for_produit

        produit = self._batterie(
            'Batterie plate 5 kWh',
            bat_kwh_nominal=Decimal('5.12'),
            bat_kwh_usable=Decimal('4.60'),
            bat_dod_pct=Decimal('90.0'))

        specs = specs_for_produit(produit)
        self.assertIn('kwh_usable', specs)
        self.assertIsNone(specs.get('batterie'))
