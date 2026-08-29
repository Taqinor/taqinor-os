"""Course ``get_or_create(company, nom)`` sur ``stock.Produit`` — fermeture.

Ordre fondateur 29/08/2026. ``apps.ventes.services._produit_frais_refactures``
créait le produit de service « Frais refacturés » par son seul NOM, sans
contrainte d'unicité derrière : deux appels concurrents créaient deux fiches.

Couvre les trois moitiés du correctif :
  1. la CONTRAINTE (``stock.0135``) et surtout son PÉRIMÈTRE — produits ACTIFS
     SANS SKU seulement : un produit archivé homonyme et deux SKU homonymes
     restent LÉGITIMES (le seeder en dépend) ;
  2. la migration de DÉ-DOUBLONNAGE (``stock.0134``) : renomme, ne supprime
     jamais, laisse la plus ancienne fiche intacte, et se réverse ;
  3. le SITE D'APPEL : idempotent, et la course perdue relit la fiche gagnante
     au lieu de lever.

Run :
    python manage.py test apps.stock.test_produit_nom_unique -v 2
"""
import importlib
from decimal import Decimal
from unittest import mock

from django.apps import apps as registre_django
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase

from apps.stock.models import Produit
from core.test_utils import WideTeardownTimeoutMixin

MIGRATION_DEDOUBLONNAGE = 'apps.stock.migrations.0134_dedoublonnage_produit_nom_sans_sku'
CONTRAINTE = 'stock_produit_company_nom_sans_sku_uniq'


def make_company(slug, nom='Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def creer(company, nom, **kwargs):
    kwargs.setdefault('prix_vente', Decimal('0'))
    kwargs.setdefault('quantite_stock', 0)
    return Produit.objects.create(company=company, nom=nom, **kwargs)


def _contrainte():
    for c in Produit._meta.constraints:
        if c.name == CONTRAINTE:
            return c
    raise AssertionError(f'contrainte {CONTRAINTE} absente de Produit.Meta')


def _contrainte_presente():
    """L'unicité conditionnelle est matérialisée par un INDEX UNIQUE PARTIEL
    portant le nom de la contrainte : sa présence dans ``pg_class`` suffit."""
    with connection.cursor() as cur:
        cur.execute('SELECT 1 FROM pg_class WHERE relname = %s', [CONTRAINTE])
        return cur.fetchone() is not None


class _SansContrainteMixin:
    """Retire temporairement la contrainte pour pouvoir FABRIQUER l'état
    « base historique avec doublons » que la migration 0134 doit nettoyer.

    Pourquoi ``TransactionTestCase`` et non ``TestCase`` (idiome maison, cf.
    ``core/tests/test_rls.py`` et ``apps/ventes/tests/test_premium_security``) :
    sous ``TestCase`` tout le test vit dans UNE transaction, les INSERT y
    laissent des déclencheurs de clés étrangères EN ATTENTE, et le DDL de
    remise de la contrainte échoue alors avec « cannot CREATE INDEX … because
    it has pending trigger events ». En autocommit, les lignes sont commitées
    avant le DDL et le problème disparaît.

    Conséquence : le DDL est commité, lui aussi. La remise de la contrainte ne
    peut donc PAS se faire à la sortie du bloc ``with`` — certains tests y
    laissent volontairement des doublons (le sens inverse de 0134 les
    recrée), et PostgreSQL refuserait l'index. Elle est faite au NETTOYAGE,
    après avoir effacé les fiches fabriquées : une base ``--keepdb`` ne reste
    jamais sans sa contrainte entre deux tests.
    """

    def setUp(self):
        super().setUp()
        # Enregistré AVANT toute fabrication : même un test qui échoue en
        # cours de route rend la base à son état contraint.
        self.addCleanup(self._remettre_contrainte)

    def _sans_contrainte(self):
        contrainte = _contrainte()

        class _Ctx:
            def __enter__(_self):
                if _contrainte_presente():
                    with connection.schema_editor(atomic=False) as se:
                        se.remove_constraint(Produit, contrainte)

            def __exit__(_self, *exc):
                # Remise déléguée au nettoyage (cf. docstring de la classe).
                return False

        return _Ctx()

    def _remettre_contrainte(self):
        # Les fiches fabriquées violent DÉLIBÉRÉMENT l'unicité (c'est l'état
        # historique que 0134 nettoie) : les effacer d'abord, sinon l'index
        # partiel est refusé.
        Produit.objects.all().delete()
        if not _contrainte_presente():
            with connection.schema_editor(atomic=False) as se:
                se.add_constraint(Produit, _contrainte())


class TestContrainteNomSansSku(TestCase):
    """Le PÉRIMÈTRE de l'unicité — ce qu'elle interdit ET ce qu'elle autorise."""

    def setUp(self):
        self.company = make_company('uniq-nom-a', 'Uniq Nom A')

    def test_deux_produits_actifs_sans_sku_homonymes_sont_refuses(self):
        creer(self.company, 'Frais refacturés')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                creer(self.company, 'Frais refacturés')

    def test_sku_vide_compte_comme_sans_sku(self):
        creer(self.company, 'Frais refacturés', sku='')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                creer(self.company, 'Frais refacturés', sku=None)

    def test_deux_sku_distincts_peuvent_porter_le_meme_nom(self):
        """Cas RÉEL du catalogue (jumeaux câble 6 mm²) : l'unicité des produits
        SKUés est déjà assurée par unique_together (company, sku)."""
        creer(self.company, 'Câble solaire 6mm²', sku='CAB-A')
        creer(self.company, 'Câble solaire 6mm²', sku='CAB-B')
        self.assertEqual(Produit.objects.filter(
            company=self.company, nom='Câble solaire 6mm²').count(), 2)

    def test_un_produit_archive_peut_garder_le_nom_d_un_actif(self):
        """Règle explicite du seeder : « an archived demo product frees its
        name for the catalogue item » (les 6 coffrets placeholders archivés)."""
        creer(self.company, 'Variateur pompage solaire', is_archived=True)
        creer(self.company, 'Variateur pompage solaire')
        self.assertEqual(Produit.objects.filter(
            company=self.company, nom='Variateur pompage solaire').count(), 2)

    def test_l_unicite_est_scopee_par_societe(self):
        autre = make_company('uniq-nom-b', 'Uniq Nom B')
        creer(self.company, 'Frais refacturés')
        creer(autre, 'Frais refacturés')
        self.assertEqual(
            Produit.objects.filter(nom='Frais refacturés').count(), 2)


class TestMigrationDedoublonnage(_SansContrainteMixin,
                                 WideTeardownTimeoutMixin,
                                 TransactionTestCase):
    """``stock.0134`` — renomme, ne supprime JAMAIS."""

    def setUp(self):
        super().setUp()
        self.company = make_company('uniq-nom-mig', 'Uniq Nom Mig')
        self.migration = importlib.import_module(MIGRATION_DEDOUBLONNAGE)

    def test_les_doublons_sont_renommes_la_plus_ancienne_intacte(self):
        with self._sans_contrainte():
            p1 = creer(self.company, 'Frais refacturés',
                       prix_vente=Decimal('12.34'), quantite_stock=7)
            p2 = creer(self.company, 'Frais refacturés')
            p3 = creer(self.company, 'Frais refacturés')

            self.migration.dedoublonner(registre_django, None)

        for p in (p1, p2, p3):
            p.refresh_from_db()
        # Aucune suppression.
        self.assertEqual(Produit.objects.filter(company=self.company).count(), 3)
        # La plus ancienne (plus petit pk) est INTACTE — nom, prix, quantité.
        self.assertEqual(p1.nom, 'Frais refacturés')
        self.assertEqual(p1.prix_vente, Decimal('12.34'))
        self.assertEqual(p1.quantite_stock, 7)
        # Les suivantes sont désambiguïsées, de façon déterministe et distincte.
        self.assertEqual(p2.nom, 'Frais refacturés (doublon 2)')
        self.assertEqual(p3.nom, 'Frais refacturés (doublon 3)')

    def test_les_non_doublons_ne_sont_jamais_touches(self):
        with self._sans_contrainte():
            seul = creer(self.company, 'Main-d\'œuvre')
            skue_a = creer(self.company, 'Câble 6mm²', sku='CAB-A')
            skue_b = creer(self.company, 'Câble 6mm²', sku='CAB-B')
            archive = creer(self.company, 'Coffret', is_archived=True)
            actif = creer(self.company, 'Coffret')
            autre_societe = creer(
                make_company('uniq-nom-mig2', 'Mig 2'), 'Main-d\'œuvre')

            self.migration.dedoublonner(registre_django, None)

        for p in (seul, skue_a, skue_b, archive, actif, autre_societe):
            nom_avant = p.nom
            p.refresh_from_db()
            self.assertEqual(p.nom, nom_avant)

    def test_le_suffixe_evite_un_nom_deja_pris(self):
        with self._sans_contrainte():
            creer(self.company, 'Service')
            creer(self.company, 'Service (doublon 2)', sku='SRV-2')
            doublon = creer(self.company, 'Service')

            self.migration.dedoublonner(registre_django, None)

        doublon.refresh_from_db()
        self.assertEqual(doublon.nom, 'Service (doublon 3)')

    def test_le_dedoublonnage_est_idempotent(self):
        with self._sans_contrainte():
            creer(self.company, 'Frais refacturés')
            creer(self.company, 'Frais refacturés')
            self.migration.dedoublonner(registre_django, None)
            noms = set(Produit.objects.filter(
                company=self.company).values_list('nom', flat=True))
            self.migration.dedoublonner(registre_django, None)

        self.assertEqual(set(Produit.objects.filter(
            company=self.company).values_list('nom', flat=True)), noms)

    def test_le_sens_inverse_restaure_les_noms(self):
        with self._sans_contrainte():
            creer(self.company, 'Frais refacturés')
            doublon = creer(self.company, 'Frais refacturés')
            self.migration.dedoublonner(registre_django, None)
            self.migration.restaurer(registre_django, None)

        doublon.refresh_from_db()
        self.assertEqual(doublon.nom, 'Frais refacturés')

    def test_le_sens_inverse_ne_touche_pas_un_nom_fondateur_similaire(self):
        """« X (doublon 2) » SANS homonyme de base n'est pas une trace du
        dé-doublonnage : le sens inverse le laisse tel quel."""
        with self._sans_contrainte():
            p = creer(self.company, 'Service (doublon 2)')
            self.migration.restaurer(registre_django, None)

        p.refresh_from_db()
        self.assertEqual(p.nom, 'Service (doublon 2)')


class TestSiteAppelFraisRefactures(TestCase):
    """``_produit_frais_refactures`` — idempotent et course-safe."""

    def setUp(self):
        self.company = make_company('uniq-nom-frais', 'Uniq Nom Frais')
        from apps.ventes import services
        self.services = services

    def test_deux_appels_renvoient_la_meme_fiche(self):
        a = self.services._produit_frais_refactures(self.company)
        b = self.services._produit_frais_refactures(self.company)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(Produit.objects.filter(
            company=self.company, nom='Frais refacturés').count(), 1)

    def test_une_fiche_archivee_ne_bloque_pas(self):
        archive = creer(self.company, 'Frais refacturés', is_archived=True)
        produit = self.services._produit_frais_refactures(self.company)
        self.assertNotEqual(produit.pk, archive.pk)
        self.assertFalse(produit.is_archived)

    def test_la_course_perdue_relit_la_fiche_gagnante(self):
        """Simulation fidèle : la première lecture ne voit rien (la
        concurrente n'a pas encore commité), la création se heurte à la
        contrainte, la RELECTURE renvoie la fiche gagnante — jamais d'erreur
        remontée à l'appelant, jamais de seconde fiche."""
        gagnante = creer(self.company, 'Frais refacturés')

        vrai_filter = Produit.objects.filter
        etat = {'appels': 0}

        def filter_en_course(*args, **kwargs):
            etat['appels'] += 1
            if etat['appels'] == 1:
                return vrai_filter(pk__in=[])   # course : rien de visible
            return vrai_filter(*args, **kwargs)

        with mock.patch.object(Produit.objects, 'filter',
                               side_effect=filter_en_course), \
                mock.patch.object(
                    Produit.objects, 'create',
                    side_effect=IntegrityError('duplicate key')):
            produit = self.services._produit_frais_refactures(self.company)

        self.assertEqual(produit.pk, gagnante.pk)
        self.assertEqual(Produit.objects.filter(
            company=self.company, nom='Frais refacturés').count(), 1)

    def test_une_integrityerror_sans_fiche_gagnante_remonte(self):
        """Une IntegrityError qui n'est PAS la course (aucune fiche à relire)
        n'est jamais avalée en silence."""
        with mock.patch.object(
                Produit.objects, 'create',
                side_effect=IntegrityError('autre contrainte')):
            with self.assertRaises(IntegrityError):
                self.services._produit_frais_refactures(self.company)
