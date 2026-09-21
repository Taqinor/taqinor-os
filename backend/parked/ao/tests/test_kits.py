"""AOF26 — ``KitCalepinage`` : catalogue des kits + seed idempotent.

Le moteur est PARTAGÉ avec les villas : une villa est simplement un kit à un
module. Modéliser le kit — plutôt que coder deux moteurs — est ce qui rend
cette parité possible.

Deux invariants tenus ici :
  1. **AUCUN prix dans le kit** — il vient du produit lié, sinon deux vérités
     divergeraient au premier réapprovisionnement ;
  2. les emprises se DÉRIVENT de la géométrie, une valeur mesurée peut être
     FIGÉE (elle prime alors) et l'écart avec la dérivation reste TRACÉ.

Run :
    python manage.py test apps.ao.tests.test_kits -v2
"""
from decimal import Decimal

from django.db import models as dj_models
from django.test import SimpleTestCase, TestCase

from apps.ao.management.commands.seed_ao_kits import (
    KITS_REFERENCE, seeder_kits,
)
from apps.ao.models import KitCalepinage
from authentication.models import Company

FRAGMENTS_PRIX = ('prix', 'tarif', 'montant', 'cout', 'coût')


class TestModeleKit(SimpleTestCase):
    def test_aucun_champ_de_prix_dans_le_kit(self):
        fautifs = [
            champ.name for champ in KitCalepinage._meta.local_fields
            if any(f in champ.name.lower() for f in FRAGMENTS_PRIX)
        ]
        self.assertEqual(
            fautifs, [],
            'Le prix vient du produit lié — jamais figé dans le kit : '
            f'{fautifs}')

    def test_le_produit_est_une_string_fk_vers_stock(self):
        champ = KitCalepinage._meta.get_field('produit')
        self.assertIsInstance(champ, dj_models.ForeignKey)
        self.assertEqual(
            champ.remote_field.model._meta.label_lower, 'stock.produit')

    def test_les_modeles_ao_n_importent_pas_stock(self):
        """La FK est une string-FK : aucune INSTRUCTION d'import n'existe."""
        import inspect

        from apps.ao import models as ao_models

        source = inspect.getsource(ao_models)
        for interdit in ('from apps.stock', 'import apps.stock'):
            self.assertNotIn(interdit, source, interdit)


class TestPuissanceEtEmprise(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF26 Co', slug='aof26-co')

    def _kit(self, **kwargs):
        base = {
            'code': 'K1', 'libelle': 'Kit test',
            'mode': KitCalepinage.Mode.TABLE_DOS_A_DOS,
            'modules_par_kit': 2, 'pas_rangee_m': Decimal('1.134'),
            'longueur_pente_m': Decimal('2.382'),
            'faitage_m': Decimal('0.098'), 'puissance_module_w': 625,
            'inclinaison_deg': Decimal('15.00'),
        }
        base.update(kwargs)
        kit = KitCalepinage(company=self.company, **base)
        kit.appliquer_emprise()
        kit.save()
        return kit

    def test_kwc_egal_modules_fois_puissance(self):
        self.assertEqual(self._kit().puissance_kwc, Decimal('1.250'))
        self.assertEqual(
            self._kit(code='K2', modules_par_kit=1,
                      puissance_module_w=720).puissance_kwc,
            Decimal('0.720'))

    def test_emprise_derivee_portrait(self):
        """2 × 2,382 × cos 15° + faîtage ≈ 4,70 m."""
        self.assertEqual(self._kit().emprise_transversale_m,
                         Decimal('4.700'))

    def test_emprise_derivee_paysage(self):
        kit = self._kit(
            code='K3', pas_rangee_m=Decimal('2.382'),
            longueur_pente_m=Decimal('1.134'), faitage_m=Decimal('0.059'),
            orientation_modules=KitCalepinage.Orientation.PAYSAGE)
        self.assertEqual(kit.emprise_transversale_m, Decimal('2.250'))

    def test_panneau_simple_n_a_qu_un_versant(self):
        kit = self._kit(
            code='K4', mode=KitCalepinage.Mode.PANNEAU_SIMPLE,
            modules_par_kit=1, longueur_pente_m=Decimal('2.384'),
            faitage_m=Decimal('0.000'), inclinaison_deg=Decimal('13.00'))
        self.assertEqual(kit.emprise_transversale_m, Decimal('2.323'))

    def test_emprise_mesuree_figee_prime_et_l_ecart_est_trace(self):
        kit = self._kit(
            code='K5', emprise_mesuree_m=Decimal('4.750'),
            emprise_figee=True)
        self.assertEqual(kit.emprise_transversale_m, Decimal('4.750'))
        self.assertEqual(kit.ecart_emprise_m, Decimal('0.050'))

    def test_mesure_non_figee_laisse_la_derivation_gagner(self):
        kit = self._kit(code='K6', emprise_mesuree_m=Decimal('4.750'))
        self.assertEqual(kit.emprise_transversale_m, Decimal('4.700'))
        self.assertEqual(kit.ecart_emprise_m, Decimal('0.050'))


class TestSeedIdempotent(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF26 Sd', slug='aof26-sd')

    def test_seed_cree_les_trois_kits(self):
        crees, existants = seeder_kits(self.company)
        self.assertEqual(crees, len(KITS_REFERENCE))
        self.assertEqual(existants, 0)
        codes = set(KitCalepinage.objects.filter(
            company=self.company).values_list('code', flat=True))
        self.assertEqual(codes, {'AO-TABLE-PORTRAIT', 'AO-TABLE-PAYSAGE',
                                 'VILLA-PANNEAU'})

    def test_seed_rejouable_sans_doublon(self):
        seeder_kits(self.company)
        crees, existants = seeder_kits(self.company)
        self.assertEqual(crees, 0)
        self.assertEqual(existants, len(KITS_REFERENCE))
        self.assertEqual(
            KitCalepinage.objects.filter(company=self.company).count(),
            len(KITS_REFERENCE))

    def test_seed_additif_ne_touche_pas_un_kit_existant(self):
        kit = KitCalepinage(
            company=self.company, code='AO-TABLE-PORTRAIT',
            libelle='Réglé à la main', pas_rangee_m=Decimal('1.200'),
            longueur_pente_m=Decimal('2.000'),
            emprise_mesuree_m=Decimal('9.999'), emprise_figee=True)
        kit.appliquer_emprise()
        kit.save()
        seeder_kits(self.company)
        kit.refresh_from_db()
        self.assertEqual(kit.libelle, 'Réglé à la main')
        self.assertEqual(kit.emprise_transversale_m, Decimal('9.999'))

    def test_les_deux_kits_ao_sont_a_deux_modules_de_625(self):
        seeder_kits(self.company)
        for code in ('AO-TABLE-PORTRAIT', 'AO-TABLE-PAYSAGE'):
            kit = KitCalepinage.objects.get(company=self.company, code=code)
            self.assertEqual(kit.modules_par_kit, 2)
            self.assertEqual(kit.puissance_module_w, 625)
            self.assertEqual(kit.puissance_kwc, Decimal('1.250'))

    def test_le_kit_villa_est_un_module_de_720(self):
        seeder_kits(self.company)
        villa = KitCalepinage.objects.get(
            company=self.company, code='VILLA-PANNEAU')
        self.assertEqual(villa.modules_par_kit, 1)
        self.assertEqual(villa.puissance_module_w, 720)
        self.assertEqual(villa.inclinaison_deg, Decimal('13.00'))

    def test_seed_scope_societe(self):
        autre = Company.objects.create(nom='AOF26 X', slug='aof26-x')
        seeder_kits(self.company)
        self.assertEqual(
            KitCalepinage.objects.filter(company=autre).count(), 0)
