"""ASTK176 — ``seed_catalogue`` est ADDITIF sur les fiches commerciales.

Décision fondateur du 06/10/2026 (ASTK172, option a) : le run nu — donc chaque
déploiement (``scripts/deploy-prod.ps1``) — ne COMBLE que les champs VIDES
(marque / description / garantie / garantie_mois) ; l'écrasement est réservé à
``--reappliquer-fiches``. Même règle pour le renommage « pendent → pendant » et
la conversion TVA 10 % des panneaux. Le seeder réel tourne sur une société
réelle (aucun mock) ; la persistance est vérifiée en relisant la base.
"""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.stock.management.commands.seed_catalogue import FICHES
from apps.stock.models import Produit
from authentication.models import Company

SKU_HUAWEI = 'OND-R-HUA-10T'
CHAMPS = ('marque', 'description', 'garantie', 'garantie_mois')
SAISIE = {
    'marque': 'Marque saisie fondateur',
    'description': 'Saisie fondateur',
    'garantie': 'Garantie saisie fondateur',
    'garantie_mois': 999,
}


def _seed(company, **options):
    out = StringIO()
    call_command('seed_catalogue', company_slug=company.slug, stdout=out,
                 **options)
    return out.getvalue()


def _sku_avec(champ):
    for sku, fiche in FICHES.items():
        if champ in fiche:
            return sku
    raise AssertionError(f'aucune fiche ne déclare {champ}')


class SeedAdditifTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Seed ASTK176', slug='seed-astk176')
        _seed(self.company)

    def _produit(self, sku):
        return Produit.objects.get(company=self.company, sku=sku)

    def test_saisie_fondateur_survit_au_seed(self):
        """Un champ saisi n'est jamais réécrit par un run nu (un sous-test
        par champ écrit par le seeder)."""
        for champ in CHAMPS:
            with self.subTest(champ=champ):
                sku = _sku_avec(champ)
                Produit.objects.filter(
                    company=self.company, sku=sku).update(
                        **{champ: SAISIE[champ]})

                _seed(self.company)  # run nu = chaque déploiement

                self.assertEqual(
                    getattr(self._produit(sku), champ), SAISIE[champ])

    def test_champ_vide_est_comble(self):
        sku = _sku_avec('description')
        declare = FICHES[sku]['description']
        Produit.objects.filter(company=self.company, sku=sku).update(
            description='')

        _seed(self.company)

        self.assertEqual(self._produit(sku).description, declare)

    def test_garantie_mois_vide_est_comblee(self):
        sku = _sku_avec('garantie_mois')
        declare = FICHES[sku]['garantie_mois']
        Produit.objects.filter(company=self.company, sku=sku).update(
            garantie_mois=None)

        _seed(self.company)

        self.assertEqual(self._produit(sku).garantie_mois, declare)

    def test_reappliquer_fiches_reecrit(self):
        for champ in CHAMPS:
            sku = _sku_avec(champ)
            Produit.objects.filter(company=self.company, sku=sku).update(
                **{champ: SAISIE[champ]})

        _seed(self.company, reappliquer_fiches=True)

        for champ in CHAMPS:
            with self.subTest(champ=champ):
                sku = _sku_avec(champ)
                self.assertEqual(
                    getattr(self._produit(sku), champ), FICHES[sku][champ])

    def test_renommage_pendent_seulement_sous_reappliquer(self):
        produit = Produit.objects.get(company=self.company, sku='SUIVI-2A')
        Produit.objects.filter(pk=produit.pk).update(
            nom='Contrat maintenance pendent 2 ans')

        sortie = _seed(self.company)
        produit.refresh_from_db()
        self.assertIn('pendent 2 ans', produit.nom)
        self.assertIn('ASTK176', sortie)  # rapporté, jamais silencieux

        _seed(self.company, reappliquer_fiches=True)
        produit.refresh_from_db()
        self.assertIn('pendant 2 ans', produit.nom)

    def test_conversion_tva_panneau_seulement_sous_reappliquer(self):
        Produit.objects.filter(company=self.company, sku='PAN-CS-710').update(
            tva=Decimal('20.00'), prix_vente=Decimal('20000.00'),
            prix_achat=Decimal('18000.00'))

        _seed(self.company)
        panneau = self._produit('PAN-CS-710')
        self.assertEqual(panneau.tva, Decimal('20.00'))
        self.assertEqual(panneau.prix_vente, Decimal('20000.00'))

        _seed(self.company, reappliquer_fiches=True)
        panneau = self._produit('PAN-CS-710')
        self.assertEqual(panneau.tva, Decimal('10.00'))
        self.assertEqual(panneau.prix_vente, Decimal('21818.18'))


class GarantiesMarocTests(TestCase):
    """RPDF (fondateur 27/10/2026) — une garantie client est UNE durée, celle
    du Maroc : jamais « selon site », « variante régionale » ni « version ».
    Deye = 5 ans et Dyness DL5.0C V2 = 7 ans (durées de base, l'extension
    payante n'est pas achetée), texte ET ``garantie_mois`` (sinon la page 2
    et la tuile de la page 3 se contredisent) ; la migration 0174 corrige les
    bases déjà seedées sans toucher une saisie du fondateur."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Seed RPDF', slug='seed-rpdf-garanties')

    def test_aucune_garantie_semee_n_affiche_d_incertitude(self):
        for sku, fiche in FICHES.items():
            texte = fiche.get('garantie', '').lower()
            for mot in ('selon', 'variante', 'régionale', 'version', ' à 10'):
                self.assertNotIn(mot, texte, sku)

    def test_seed_deye_5_ans_dyness_7_ans(self):
        _seed(self.company)
        deye = Produit.objects.get(company=self.company, sku='OND-H-DEY-10T')
        self.assertEqual(deye.garantie, 'Garantie constructeur 5 ans')
        self.assertEqual(deye.garantie_mois, 60)
        dyness = Produit.objects.get(company=self.company, sku='BAT-DEY-5')
        self.assertTrue(dyness.garantie.startswith('Garantie constructeur 7 ans'))
        self.assertEqual(dyness.garantie_mois, 84)

    def test_migration_0174_corrige_l_ancienne_valeur_semee(self):
        from importlib import import_module

        from django.apps import apps as registre
        mig = import_module('apps.stock.migrations.0174_rpdf_garanties_maroc')
        _seed(self.company)
        Produit.objects.filter(company=self.company, sku='OND-H-DEY-10T').update(
            garantie=mig.ANCIEN_TEXTE_DEYE, garantie_mois=120)
        Produit.objects.filter(company=self.company, sku='BAT-DEY-5').update(
            garantie=mig.ANCIEN_TEXTE_DYNESS_V2, garantie_mois=120)
        Produit.objects.filter(company=self.company, sku='BAT-DEY-10').update(
            garantie=mig.ANCIEN_TEXTE_DYNESS)
        # Une saisie du fondateur n'est jamais réécrite.
        Produit.objects.filter(company=self.company, sku='OND-H-DEY-5M').update(
            garantie='Garantie 10 ans (extension achetée)', garantie_mois=99)

        mig.corriger(registre, None)

        def _p(sku):
            return Produit.objects.get(company=self.company, sku=sku)
        self.assertEqual(_p('OND-H-DEY-10T').garantie, mig.NOUVEAU_TEXTE_DEYE)
        self.assertEqual(_p('OND-H-DEY-10T').garantie_mois, 60)
        self.assertEqual(_p('BAT-DEY-5').garantie, mig.NOUVEAU_TEXTE_DYNESS_5)
        self.assertEqual(_p('BAT-DEY-5').garantie_mois, 84)
        self.assertEqual(_p('BAT-DEY-10').garantie, mig.NOUVEAU_TEXTE_DYNESS_10)
        self.assertEqual(_p('BAT-DEY-10').garantie_mois, 120)
        self.assertEqual(_p('OND-H-DEY-5M').garantie,
                         'Garantie 10 ans (extension achetée)')
        self.assertEqual(_p('OND-H-DEY-5M').garantie_mois, 99)


class DescriptionHybridesDeyeTests(TestCase):
    """CCAT15 (27/10/2026) — aucune fiche semée n'imprime « … » au client ;
    la migration 0175 corrige l'ancienne description semée des hybrides Deye
    sans toucher une saisie du fondateur."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Seed CCAT15', slug='seed-ccat15-deye')

    def test_aucune_description_semee_avec_points_de_suspension(self):
        for sku, fiche in FICHES.items():
            texte = fiche.get('description', '')
            self.assertNotIn('…', texte, sku)
            self.assertNotIn('...', texte, sku)

    def test_migration_0175_corrige_la_seule_valeur_semee(self):
        from importlib import import_module

        from django.apps import apps as registre
        mig = import_module(
            'apps.stock.migrations.0175_ccat15_description_hybrides_deye')
        _seed(self.company)
        self.assertEqual(
            Produit.objects.get(company=self.company, sku='OND-H-DEY-15T')
            .description, FICHES['OND-H-DEY-15T']['description'])
        Produit.objects.filter(company=self.company, sku='OND-H-DEY-15T').update(
            description=mig.ANCIENNE)
        Produit.objects.filter(company=self.company, sku='OND-H-DEY-5M').update(
            description='Saisie fondateur')

        mig.corriger(registre, None)

        def _p(sku):
            return Produit.objects.get(company=self.company, sku=sku)
        self.assertEqual(_p('OND-H-DEY-15T').description,
                         FICHES['OND-H-DEY-15T']['description'])
        self.assertTrue(_p('OND-H-DEY-15T').description.startswith(
            'Onduleur hybride Deye SUN-15K-SG05LP3-EU-SM2'))
        self.assertEqual(_p('OND-H-DEY-5M').description, 'Saisie fondateur')

    def test_migration_0175_couvre_les_deux_variantes_semees(self):
        from importlib import import_module

        from django.apps import apps as registre
        mig = import_module(
            'apps.stock.migrations.0175_ccat15_description_hybrides_deye')
        _seed(self.company)
        variante_1206 = (
            'Onduleur hybride Deye SUN-…SG, rendement max ≈ 97,6 %\n'
            'Compatible batteries lithium 48 V (BMS CAN/RS485)\n'
            'Bascule secours (EPS/UPS) < 4 ms en cas de coupure réseau\n'
            'Monitoring Wi-Fi via Solarman Smart / Deye Cloud')
        Produit.objects.filter(company=self.company, sku='OND-H-DEY-10T').update(
            description=variante_1206)
        Produit.objects.filter(company=self.company, sku='OND-H-DEY-20T').update(
            description=mig.ANCIENNE)

        def _p(sku):
            return Produit.objects.get(company=self.company, sku=sku).description

        mig.corriger(registre, None)
        # Seule la première ligne change ; la suite semée reste telle quelle.
        self.assertEqual(_p('OND-H-DEY-10T'), variante_1206.replace(
            'Onduleur hybride Deye SUN-…SG, rendement max ≈ 97,6 %',
            'Onduleur hybride Deye SUN-10K-SG05LP3-EU-SM2'))
        self.assertEqual(_p('OND-H-DEY-20T'),
                         FICHES['OND-H-DEY-20T']['description'])
        self.assertNotIn('…', _p('OND-H-DEY-10T'))

        # Retour arrière exact pour les deux variantes.
        mig.retablir(registre, None)
        self.assertEqual(_p('OND-H-DEY-10T'), variante_1206)
        self.assertEqual(_p('OND-H-DEY-20T'), mig.ANCIENNE)

    def test_migration_0176_fiches_client_sans_extension_ni_modele(self):
        from importlib import import_module

        from django.apps import apps as registre
        mig = import_module('apps.stock.migrations.0176_ccat_fiches_client')
        _seed(self.company)

        def _p(sku):
            return Produit.objects.get(company=self.company, sku=sku)
        # Le seeder porte déjà les nouveaux textes.
        self.assertEqual(_p('OND-R-HUA-100T').garantie, 'Garantie constructeur 5 ans')
        self.assertNotIn('SI22', _p('VEI-SI22-AFF').description)
        (garantie, skus, ancienne_g, nouvelle_g), (_c, _s, ancienne_d, nouvelle_d) = mig.CHANGEMENTS
        Produit.objects.filter(company=self.company, sku='OND-R-HUA-50T').update(garantie=ancienne_g)
        Produit.objects.filter(company=self.company, sku='VEI-SI22-AFF').update(description=ancienne_d)
        # Une saisie du fondateur n'est jamais réécrite.
        Produit.objects.filter(company=self.company, sku='OND-R-HUA-150T').update(
            garantie='Garantie 10 ans (extension achetée)')

        mig.corriger(registre, None)
        self.assertEqual(_p('OND-R-HUA-50T').garantie, nouvelle_g)
        self.assertEqual(_p('VEI-SI22-AFF').description, nouvelle_d)
        self.assertEqual(_p('OND-R-HUA-150T').garantie, 'Garantie 10 ans (extension achetée)')

        mig.retablir(registre, None)
        self.assertEqual(_p('OND-R-HUA-50T').garantie, ancienne_g)
        self.assertEqual(_p('VEI-SI22-AFF').description, ancienne_d)
