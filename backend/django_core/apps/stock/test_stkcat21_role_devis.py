"""STKCAT21 — `Produit.role_devis`, la résolution à trois rangs et son exposition.

CE QUE CE FICHIER PROTÈGE
-------------------------
Le rôle d'un produit dans un devis n'était nulle part une DONNÉE : il était
re-deviné à partir des mots-clés du nom, à chaque lecture. STKCAT21 ajoute la
donnée (`Produit.role_devis`) et l'ORDRE DE LECTURE
(`core.product_roles.role_effectif`) :

    déclaré → famille de la catégorie (si sans ambiguïté) → mots-clés du nom

LE POINT LE PLUS IMPORTANT DE CE FICHIER EST LA NON-RÉGRESSION : sur le
catalogue RÉELLEMENT semé (les 92 désignations de `seed_catalogue`), aucun
produit n'ayant de rôle déclaré ni de catégorie, la résolution doit rendre
EXACTEMENT ce que `classer_produit` rendait hier, avec `source='nom'`. Les
mots-clés ne sont pas remplacés : ils deviennent un REPLI PERMANENT.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.test_stkcat21_role_devis -v 2
"""
from django.test import SimpleTestCase, TestCase

from apps.stock.management.commands import seed_catalogue as seed
from apps.stock.models import Categorie, Produit
from apps.stock.serializers import ProduitSerializer
from apps.ventes.selectors import classer_produit_nom
from core.product_roles import (
    FAMILLE_VERS_ROLE,
    ROLES_DEVIS,
    contradiction_role_nom,
    role_declare,
    role_effectif,
)


def _make_company(slug='stkcat21-co', nom='STKCAT21 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def _noms_semes():
    """Les désignations que `seed_catalogue` pose réellement en base.

    Lues sur les TABLES du seeder (et pas recopiées) : une ligne ajoutée au
    catalogue demain entre automatiquement dans la garde de non-régression.
    """
    noms = [ligne[0] for ligne in seed.CATALOGUE]
    noms += [ligne[0] for ligne in seed.POMPAGE]
    noms += [ligne[0] for ligne in seed.VEICHI]
    noms += [ligne[0] for ligne in seed.OSP]
    noms += [ligne[0] for ligne in seed.CABLES_PROTECTIONS_VIDES]
    noms += [ligne[0] for ligne in seed.BATTERIE_DEYE_HV]
    return noms


class TestStkcat21Vocabulaire(SimpleTestCase):
    """Le tuple de rôles est UN, et la carte des familles est exhaustive."""

    def test_le_tuple_ventes_est_le_tuple_core(self):
        # Le nom historique reste le point de lecture de `apps.ventes` ; la
        # VALEUR vient de `core` (plus aucune copie à tenir à la main).
        from apps.ventes.models import ROLES_AUTO_COMPOSITION
        self.assertIs(ROLES_AUTO_COMPOSITION, ROLES_DEVIS)

    def test_la_carte_des_familles_couvre_toutes_les_familles(self):
        """Chaque valeur de `Categorie.TypeEquipement` a un arbitrage ÉCRIT.

        `None` est un arbitrage (famille ambiguë ou hors vocabulaire) — ce qui
        est interdit, c'est l'ABSENCE : une famille ajoutée demain et oubliée
        ici tomberait silencieusement sur le repli mots-clés sans que personne
        n'ait tranché.
        """
        familles = {valeur for valeur, _ in Categorie.TypeEquipement.choices}
        self.assertEqual(
            sorted(FAMILLE_VERS_ROLE), sorted(familles),
            'FAMILLE_VERS_ROLE (core/product_roles.py) et '
            'Categorie.TypeEquipement ont divergé.')

    def test_les_roles_de_la_carte_appartiennent_au_vocabulaire(self):
        for famille, role in FAMILLE_VERS_ROLE.items():
            if role is not None:
                self.assertIn(
                    role, ROLES_DEVIS,
                    'la famille « %s » pointe un rôle hors vocabulaire : %s'
                    % (famille, role))

    def test_les_familles_ambigues_ne_repondent_pas(self):
        """Les familles qui recouvrent PLUSIEURS rôles se taisent.

        `onduleur` (réseau/hybride/hors-réseau), `cable` (DC/terre) et
        `service` (installation/transport/suivi) : répondre l'un des trois
        composerait un devis sur une devinette.
        """
        for famille in ('onduleur', 'cable', 'service', 'protection',
                        'pompe', 'variateur', 'compteur'):
            self.assertIsNone(FAMILLE_VERS_ROLE[famille], famille)

    def test_un_role_hors_vocabulaire_est_ignore(self):
        self.assertIsNone(role_declare('role_invente'))
        self.assertIsNone(role_declare(''))
        self.assertIsNone(role_declare(None))
        self.assertEqual(role_declare('  panneau  '), 'panneau')


class TestStkcat21OrdreDeResolution(SimpleTestCase):
    """Déclaré → catégorie → nom, et la source le DIT."""

    def test_le_role_declare_passe_devant_tout(self):
        role, source = role_effectif(
            role_devis='structure', type_equipement='panneau',
            nom='Panneau Jinko 710W', classer_nom=classer_produit_nom)
        self.assertEqual((role, source), ('structure', 'declare'))

    def test_la_categorie_passe_devant_les_mots_cles(self):
        # « Pergola alu » : le nom réel du fondateur, qu'AUCUN mot-clé ne
        # reconnaît — c'est le défaut « Pergola introuvable » de l'audit.
        self.assertIsNone(classer_produit_nom('Pergola alu'))
        role, source = role_effectif(
            type_equipement='structure', nom='Pergola alu',
            classer_nom=classer_produit_nom)
        self.assertEqual((role, source), ('structure', 'categorie'))

    def test_les_mots_cles_restent_le_repli(self):
        role, source = role_effectif(
            nom='Panneau Jinko 710W', classer_nom=classer_produit_nom)
        self.assertEqual((role, source), ('panneau', 'nom'))

    def test_une_famille_ambigue_laisse_la_main_aux_mots_cles(self):
        role, source = role_effectif(
            type_equipement='onduleur', nom='Onduleur hybride Deye 5kW',
            classer_nom=classer_produit_nom)
        self.assertEqual((role, source), ('onduleur_hybride', 'nom'))

    def test_rien_de_lisible_ne_rend_rien(self):
        self.assertEqual(
            role_effectif(nom='Pergola alu', classer_nom=classer_produit_nom),
            (None, None))

    def test_sans_classifieur_injecte_le_rang_3_est_saute(self):
        # `core` ne peut pas importer `apps.ventes` : le classifieur est
        # TOUJOURS injecté. Sans lui, la fonction reste utilisable.
        self.assertEqual(role_effectif(nom='Panneau Jinko 710W'), (None, None))

    def test_une_contradiction_est_un_message_jamais_une_decision(self):
        self.assertIsNone(contradiction_role_nom('panneau', 'panneau'))
        self.assertIsNone(contradiction_role_nom('panneau', None))
        message = contradiction_role_nom('structure', 'panneau')
        self.assertIn('structure', message)
        self.assertIn('panneau', message)
        self.assertIn('conservé', message)


class TestStkcat21NonRegressionCatalogueSeme(SimpleTestCase):
    """LES 92 DÉSIGNATIONS SEMÉES RENDENT LE MÊME RÔLE QU'HIER."""

    def test_le_catalogue_seme_est_bien_celui_qu_on_croit(self):
        noms = _noms_semes()
        self.assertEqual(len(noms), 92)
        self.assertEqual(len(set(noms)), 92, 'un nom semé en double')

    def test_sans_role_ni_categorie_le_resultat_est_celui_des_mots_cles(self):
        for nom in _noms_semes():
            attendu = classer_produit_nom(nom)
            with self.subTest(nom=nom):
                role, source = role_effectif(
                    nom=nom, classer_nom=classer_produit_nom)
                self.assertEqual(
                    role, attendu,
                    'le rôle de « %s » a changé : %s au lieu de %s'
                    % (nom, role, attendu))
                self.assertEqual(source, 'nom' if attendu else None)


class TestStkcat21Serialiseur(TestCase):
    """Le sérialiseur produit expose le rôle DÉCLARÉ, le RÉSOLU et sa SOURCE."""

    def setUp(self):
        self.company = _make_company()

    def _produit(self, **kwargs):
        champs = dict(company=self.company, nom='Pergola alu', prix_vente=1000)
        champs.update(kwargs)
        return Produit.objects.create(**champs)

    def test_produit_sans_role_ni_categorie_source_nom(self):
        produit = self._produit(nom='Panneau Jinko 710W')
        data = ProduitSerializer(produit).data
        self.assertIsNone(data['role_devis'])
        self.assertEqual(data['role_devis_effectif'], 'panneau')
        self.assertEqual(data['role_devis_source'], 'nom')

    def test_produit_type_par_sa_categorie_source_categorie(self):
        categorie = Categorie.objects.create(
            company=self.company, nom='Structures & fixation',
            type_equipement=Categorie.TypeEquipement.STRUCTURE)
        produit = self._produit(categorie=categorie)
        data = ProduitSerializer(produit).data
        self.assertEqual(data['categorie_type'], 'structure')
        self.assertIsNone(data['role_devis'])
        self.assertEqual(data['role_devis_effectif'], 'structure')
        self.assertEqual(data['role_devis_source'], 'categorie')

    def test_role_declare_source_declare(self):
        produit = self._produit(role_devis='structure')
        data = ProduitSerializer(produit).data
        self.assertEqual(data['role_devis'], 'structure')
        self.assertEqual(data['role_devis_effectif'], 'structure')
        self.assertEqual(data['role_devis_source'], 'declare')

    def test_produit_sans_rien_de_lisible_rend_null(self):
        data = ProduitSerializer(self._produit()).data
        self.assertIsNone(data['role_devis_effectif'])
        self.assertIsNone(data['role_devis_source'])

    def test_role_hors_vocabulaire_refuse_en_ecriture(self):
        ser = ProduitSerializer(data={
            'nom': 'X', 'prix_vente': '10.00', 'role_devis': 'role_invente'})
        self.assertFalse(ser.is_valid())
        self.assertIn('role_devis', ser.errors)

    def test_chaine_vide_normalisee_en_null(self):
        """Effacer le rôle depuis l'écran écrit NULL, jamais ''.

        Deux façons d'écrire « non déclaré » rendraient `role_devis__isnull`
        aveugle à la moitié du catalogue.
        """
        produit = self._produit(role_devis='structure')
        ser = ProduitSerializer(produit, data={'role_devis': ''}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        produit.refresh_from_db()
        self.assertIsNone(produit.role_devis)

    def test_les_gardes_prix_achat_et_marge_sont_intactes(self):
        """STKCAT21 n'ouvre AUCUNE donnée sensible.

        Le rôle voyage à côté de `prix_achat`/`marge_pct` : ces deux-là restent
        retirés pour un rôle sans la permission, exactement comme avant.
        """
        class _User:
            can_view_buy_prices = False
            can_view_marge = False
            company_id = None
            is_superuser = False

        class _Request:
            user = _User()

        produit = self._produit(role_devis='structure')
        data = ProduitSerializer(produit, context={'request': _Request()}).data
        self.assertNotIn('prix_achat', data)
        self.assertNotIn('marge_pct', data)
        self.assertEqual(data['role_devis'], 'structure')


class TestStkcat21Champ(SimpleTestCase):
    """La colonne : nullable, indexée, vocabulaire partagé."""

    def test_colonne_nullable_indexee_et_au_vocabulaire(self):
        champ = Produit._meta.get_field('role_devis')
        self.assertTrue(champ.null)
        self.assertTrue(champ.blank)
        self.assertTrue(champ.db_index)
        self.assertEqual(champ.max_length, 32)
        self.assertEqual([cle for cle, _ in champ.choices], list(ROLES_DEVIS))
        # Le plus long rôle du vocabulaire doit tenir dans la colonne.
        self.assertLessEqual(max(len(r) for r in ROLES_DEVIS), champ.max_length)
