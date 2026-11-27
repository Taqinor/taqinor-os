"""STKCAT21 — `Produit.role_devis`, la résolution à trois rangs et son exposition.

CE QUE CE FICHIER PROTÈGE
-------------------------
Le rôle d'un produit dans un devis n'était nulle part une DONNÉE : il était
re-deviné à partir des mots-clés du nom, à chaque lecture. STKCAT21 ajoute la
donnée (`Produit.role_devis`) et l'ORDRE DE LECTURE
(`core.product_roles.role_effectif`) :

    déclaré → famille de la catégorie (si sans ambiguïté) → mots-clés du nom

LE POINT LE PLUS IMPORTANT DE CE FICHIER EST LA NON-RÉGRESSION : sur le
catalogue RÉELLEMENT semé (les 96 désignations de `seed_catalogue`), aucun
produit n'ayant de rôle déclaré ni de catégorie, la résolution doit rendre
EXACTEMENT ce que `classer_produit` rendait hier, avec `source='nom'`. Les
mots-clés ne sont pas remplacés : ils deviennent un REPLI PERMANENT.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.test_stkcat21_role_devis -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from apps.stock import selectors_panneau_defaut as spd
from apps.stock.management.commands import seed_catalogue as seed
from apps.stock.models import Categorie, FicheTechnique, Produit
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
    """LES 96 DÉSIGNATIONS SEMÉES RENDENT LE MÊME RÔLE QU'HIER (R3 : + 3 Smart Meter Huawei)."""

    def test_le_catalogue_seme_est_bien_celui_qu_on_croit(self):
        noms = _noms_semes()
        self.assertEqual(len(noms), 96)
        self.assertEqual(len(set(noms)), 96, 'un nom semé en double')

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
            GET = {}  # `_target_locale` lit `request.GET` sans query_params (YHARD4)

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


# ═══════════════════════════════════════════════════════════════════════════
# D-ACAL-169 — LE panneau par défaut de la société (contrat
# ``contract_samples/panneau_par_defaut.json``). Ici parce que la règle « est un
# panneau » est celle de ce fichier : rôle déclaré, puis fiche MODULE, puis
# catégorie et mots-clés (``role_effectif``).
# ═══════════════════════════════════════════════════════════════════════════

_CONTRAT_PANNEAU = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples' / 'panneau_par_defaut.json')
    .read_text(encoding='utf-8'))


def _panneau_memoire(nom='Panneau Canadian Solar 715 Wc', prix='1200', pmax=None, **kwargs):
    """Un produit NON enregistré (aucune base) ; fiche MODULE si ``pmax`` est donné."""
    produit = Produit(nom=nom, prix_vente=Decimal(prix), **kwargs)
    if pmax is not None:
        produit.fiche_technique = FicheTechnique(type_fiche='module', pmax_wc=Decimal(str(pmax)))
    return produit


class TestPanneauParDefautSelecteurs(SimpleTestCase):
    """Les replis des sélecteurs, sans base : source, watt, forme du résumé."""

    def test_aucun_designe(self):
        self.assertEqual(spd.source_du_produit(None), spd.AUCUN)
        self.assertEqual(spd.resume_du_produit(None), _CONTRAT_PANNEAU['exemple_aucun'])

    def test_designe_utilisable_forme_du_contrat(self):
        produit = _panneau_memoire(pmax=715)
        produit.pk = 42
        self.assertEqual(spd.source_du_produit(produit), spd.DESIGNE)
        resume = spd.resume_du_produit(produit)
        self.assertEqual(set(resume), set(_CONTRAT_PANNEAU['exemple']))
        self.assertEqual(resume['produit_id'], 42)
        self.assertEqual(resume['pmax_wc'], 715)
        self.assertIsInstance(resume['pmax_wc'], int)
        self.assertIsNone(resume['motif'])

    def test_archive_sans_prix_pas_un_panneau(self):
        nom = 'Panneau Canadian Solar 715 Wc bifacial'
        cas = (
            (_panneau_memoire(nom=nom, is_archived=True), spd.ARCHIVE, 'exemple_archive'),
            (_panneau_memoire(nom=nom, prix='0'), spd.SANS_PRIX, 'exemple_sans_prix'),
            (_panneau_memoire(nom=nom, role_devis='batterie'), spd.PAS_UN_PANNEAU, 'exemple_pas_un_panneau'),
        )
        for produit, source, variante in cas:
            with self.subTest(source=source):
                self.assertEqual(spd.source_du_produit(produit), source)
                self.assertEqual(spd.resume_du_produit(produit), _CONTRAT_PANNEAU[variante])

    def test_les_sources_du_contrat_sont_celles_du_code(self):
        self.assertEqual(list(spd.SOURCES), _CONTRAT_PANNEAU['sources'])

    def test_est_un_panneau_ordre_de_la_maison(self):
        # Rôle déclaré d'abord : une « Batterie » déclarée panneau en est un, un « Panneau » déclaré batterie non.
        self.assertTrue(spd.est_un_panneau(Produit(nom='Batterie X', role_devis='panneau')))
        self.assertFalse(spd.est_un_panneau(Produit(nom='Panneau 715 Wc', role_devis='batterie')))
        # Puis la fiche technique MODULE, même sous un nom muet.
        self.assertTrue(spd.est_un_panneau(_panneau_memoire(nom='Réf. XK-9', pmax=715)))
        # Puis les mots-clés du nom (repli du moteur).
        self.assertTrue(spd.est_un_panneau(Produit(nom='Panneau Jinko 710W')))
        self.assertFalse(spd.est_un_panneau(Produit(nom='Onduleur Deye 10 kW')))

    def test_watt_fiche_puis_nom_puis_rien(self):
        self.assertEqual(spd.watt_du_panneau(_panneau_memoire(nom='Panneau 710 W', pmax=715)), 715)
        self.assertEqual(spd.watt_du_panneau(_panneau_memoire(nom='Panneau 710 W', pmax='712.5')), 712.5)
        self.assertEqual(spd.watt_du_panneau(_panneau_memoire(nom='Panneau 710 W')), 710)
        self.assertIsNone(spd.watt_du_panneau(_panneau_memoire(nom='Panneau bifacial')))

    def test_un_watt_par_panneau_nom_et_fiche_en_desaccord(self):
        """Nom « 710 W » + fiche 715 Wc : deux moteurs liraient deux puissances — pas utilisable, phrase du contrat."""
        produit = _panneau_memoire(nom='Panneau Jinko 710 W', pmax=715)
        self.assertEqual(spd.desaccord_watt(produit), (710, 715))
        self.assertEqual(spd.source_du_produit(produit), spd.WATT_CONTRADICTOIRE)
        self.assertEqual(spd.resume_du_produit(produit), _CONTRAT_PANNEAU['exemple_watt_contradictoire'])
        # D-ACAL-169 (rejeu) — le motif du résumé NOMME le produit désigné (jamais « ce produit ») et les deux watts.
        motif = spd.resume_du_produit(produit)['motif']
        self.assertIn('« Panneau Jinko 710 W »', motif)
        self.assertNotIn('ce produit', motif)
        self.assertIn('710 W', motif)
        self.assertIn('715 Wc', motif)
        self.assertEqual(spd.phrase_desaccord_watt(710, 712.5),
                         "Le nom de ce produit dit 710 W et sa fiche technique 712,5 Wc : corrigez l'un des deux, "
                         "puis désignez-le.")
        # Accord, ou une seule des deux sources : aucun désaccord, et la même valeur dans les deux ordres.
        for accord in (_panneau_memoire(nom='Panneau 715 Wc', pmax=715), _panneau_memoire(nom='Panneau 715 Wc'),
                       _panneau_memoire(nom='Réf. XK-9', pmax=715)):
            with self.subTest(nom=accord.nom):
                self.assertIsNone(spd.desaccord_watt(accord))
                self.assertEqual(spd.watt_du_panneau(accord), 715)
                self.assertEqual(spd.watt_au_nom(accord) or spd.watt_de_fiche(accord), 715)

    def test_sans_societe_rien(self):
        self.assertIsNone(spd.panneau_par_defaut(None))
        self.assertIsNone(spd.watt_panneau_par_defaut(None))
        self.assertEqual(spd.resume_panneau_par_defaut(None), _CONTRAT_PANNEAU['exemple_aucun'])


class TestPanneauParDefautContrainte(TestCase):
    """Base : un seul panneau par défaut par société, jamais sur un produit global."""

    def setUp(self):
        self.company = _make_company('dacal169-co', 'D-ACAL-169 Co')
        self.autre = _make_company('dacal169-autre', 'D-ACAL-169 Autre')

    def _panneau(self, company, nom, **kwargs):
        return Produit.objects.create(company=company, nom=nom, prix_vente=Decimal('1200'), **kwargs)

    def test_defaut_faux_pour_tout_produit_cree(self):
        self.assertFalse(self._panneau(self.company, 'Panneau 715 Wc').panneau_par_defaut)

    def test_deux_defauts_dans_une_societe_refuses(self):
        self._panneau(self.company, 'Panneau A 715 Wc', panneau_par_defaut=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._panneau(self.company, 'Panneau B 715 Wc', panneau_par_defaut=True)

    def test_un_defaut_par_societe_independants(self):
        self._panneau(self.company, 'Panneau A 715 Wc', panneau_par_defaut=True)
        self._panneau(self.autre, 'Panneau A 715 Wc', panneau_par_defaut=True)
        self.assertEqual(Produit.objects.filter(
            panneau_par_defaut=True, company__in=[self.company, self.autre]).count(), 2)

    def test_produit_global_ne_peut_pas_le_porter(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._panneau(None, 'Panneau global 715 Wc', panneau_par_defaut=True)


class TestPanneauParDefautApi(TestCase):
    """Lecture, désignation, remplacement, retrait, refus, droits et portée société."""

    URL_LECTURE = '/api/django/stock/panneau-par-defaut/'

    def setUp(self):
        from django.contrib.auth import get_user_model

        from apps.roles.models import Role
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES

        user_model = get_user_model()
        perms = dict(CANONICAL_SYSTEM_ROLES)
        self.company = _make_company('dacal169-api', 'D-ACAL-169 API')
        self.autre = _make_company('dacal169-api-autre', 'D-ACAL-169 API Autre')
        self.users = {}
        for company, nom in ((self.company, 'Directeur'), (self.company, 'Technicien'),
                             (self.company, 'Commercial responsable'), (self.autre, 'Directeur')):
            role = Role.objects.create(company=company, nom=nom, permissions=list(perms[nom]), est_systeme=True)
            cle = nom if company == self.company else f'{nom} autre'
            self.users[cle] = user_model.objects.create_user(
                username=f'dacal169-{company.slug}-{nom.lower().replace(" ", "-")}', password='x',
                company=company, role=role)
        self.p715 = Produit.objects.create(company=self.company, nom='Panneau Canadian Solar 715 Wc',
                                           prix_vente=Decimal('1200'))
        FicheTechnique.objects.create(company=self.company, produit=self.p715, type_fiche='module',
                                      pmax_wc=Decimal('715'))
        self.p710 = Produit.objects.create(company=self.company, nom='Panneau Jinko 710W', prix_vente=Decimal('1100'))
        self.onduleur = Produit.objects.create(company=self.company, nom='Onduleur Deye 10 kW',
                                               prix_vente=Decimal('9000'))

    def _api(self, cle):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.users[cle])}')
        return api

    def _definir(self, produit, cle='Directeur'):
        return self._api(cle).post(f'/api/django/stock/produits/{produit.pk}/definir-panneau-par-defaut/',
                                   {}, format='json')

    def _retirer(self, produit, cle='Directeur'):
        return self._api(cle).post(f'/api/django/stock/produits/{produit.pk}/retirer-panneau-par-defaut/',
                                   {}, format='json')

    def _drapeaux(self):
        return set(Produit.objects.filter(
            panneau_par_defaut=True, company__in=[self.company, self.autre]).values_list('pk', flat=True))

    def test_lecture_sans_designe_forme_aucun(self):
        rep = self._api('Technicien').get(self.URL_LECTURE)
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(rep.json(), _CONTRAT_PANNEAU['exemple_aucun'])

    def test_definir_puis_remplacer(self):
        rep = self._definir(self.p715)
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(rep.json(), {'produit_id': self.p715.pk, 'nom': self.p715.nom, 'pmax_wc': 715,
                                      'source': 'designe', 'motif': None})
        self.assertEqual(self._drapeaux(), {self.p715.pk})
        rep = self._definir(self.p710)
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(rep.json()['pmax_wc'], 710)  # lu au nom : aucune fiche
        self.assertEqual(self._drapeaux(), {self.p710.pk})

    def test_retirer_est_idempotent(self):
        self._definir(self.p715)
        rep = self._retirer(self.p710)  # pas le défaut : rien ne change
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(self._drapeaux(), {self.p715.pk})
        rep = self._retirer(self.p715)
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(rep.json(), _CONTRAT_PANNEAU['exemple_aucun'])
        self.assertEqual(self._drapeaux(), set())

    def test_refus_non_panneau_archive_sans_prix_sous_le_champ(self):
        archive = Produit.objects.create(company=self.company, nom='Panneau 700 Wc', prix_vente=Decimal('900'),
                                         is_archived=True)
        sans_prix = Produit.objects.create(company=self.company, nom='Panneau 690 Wc', prix_vente=Decimal('0'))
        for produit, extrait in ((self.onduleur, "n'est pas un panneau"), (archive, 'est archivé'),
                                 (sans_prix, "n'a pas de prix de vente")):
            with self.subTest(produit=produit.nom):
                rep = self._definir(produit)
                self.assertEqual(rep.status_code, 400, rep.content)
                self.assertIn(extrait, rep.json()['panneau_par_defaut'][0])
        self.assertEqual(self._drapeaux(), set())

    def test_droit_responsable_catalogue(self):
        for cle in ('Technicien', 'Commercial responsable'):
            with self.subTest(role=cle):
                self.assertEqual(self._definir(self.p715, cle).status_code, 403)
                self.assertEqual(self._retirer(self.p715, cle).status_code, 403)
        self.assertEqual(self._drapeaux(), set())

    def test_technicien_voit_le_panneau_sans_aucun_prix(self):
        self._definir(self.p715)
        rep = self._api('Technicien').get(self.URL_LECTURE)
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(rep.json()['produit_id'], self.p715.pk)
        self.assertNotIn('prix', json.dumps(rep.json()))
        detail = self._api('Technicien').get(f'/api/django/stock/produits/{self.p715.pk}/')
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertIs(detail.json()['panneau_par_defaut'], True)
        self.assertNotIn('prix_vente', detail.json())

    def test_portee_societe(self):
        self._definir(self.p715)
        # La société B ne voit pas le défaut de A et ne peut pas toucher un produit de A.
        rep = self._api('Directeur autre').get(self.URL_LECTURE)
        self.assertEqual(rep.json(), _CONTRAT_PANNEAU['exemple_aucun'])
        self.assertEqual(self._definir(self.p710, 'Directeur autre').status_code, 404)
        self.assertEqual(self._retirer(self.p715, 'Directeur autre').status_code, 404)
        self.assertEqual(self._drapeaux(), {self.p715.pk})
        self.assertIsNone(spd.panneau_par_defaut(self.autre))
        self.assertEqual(spd.panneau_par_defaut(self.company), self.p715)
        self.assertEqual(spd.watt_panneau_par_defaut(self.company), 715)
        self.assertIsNone(spd.watt_panneau_par_defaut(self.autre))

    def test_corps_patch_ignore(self):
        avant = self._api('Directeur').get(f'/api/django/stock/produits/{self.p715.pk}/').json()
        self.assertIs(avant['panneau_par_defaut'], False)
        rep = self._api('Directeur').patch(f'/api/django/stock/produits/{self.p715.pk}/',
                                           {'panneau_par_defaut': True}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(self._drapeaux(), set())

    def _journal(self, produit):
        from django.contrib.contenttypes.models import ContentType

        from apps.audit.models import AuditLog

        return list(AuditLog.objects.filter(
            content_type=ContentType.objects.get_for_model(Produit), object_id=str(produit.pk),
            action='update', detail__icontains='panneau par défaut').order_by('pk'))

    def test_journal_d_audit_qui_et_quel_produit(self):
        """« Historique » du produit : définir, remplacer, retirer laissent chacun leur ligne (qui, quel produit)."""
        directeur = self.users['Directeur']
        self._definir(self.p710)
        self._definir(self.p715)  # remplace p710
        self._definir(self.p715)  # déjà le défaut : aucune ligne de plus
        self._retirer(self.p715)
        lignes_715, lignes_710 = self._journal(self.p715), self._journal(self.p710)
        self.assertEqual([ligne.detail for ligne in lignes_715], [
            f'Panneau par défaut : « {self.p715.nom} » (remplace « {self.p710.nom} »).',
            f"N'est plus le panneau par défaut : « {self.p715.nom} » retiré (aucun panneau par défaut).",
        ])
        self.assertEqual([ligne.detail for ligne in lignes_710], [
            f'Panneau par défaut : « {self.p710.nom} ».',
            f"N'est plus le panneau par défaut : remplacé par « {self.p715.nom} ».",
        ])
        for ligne in lignes_715 + lignes_710:
            self.assertEqual(ligne.user_id, directeur.pk)
            self.assertEqual(ligne.company_id, self.company.pk)
        self.assertEqual(lignes_715[0].changes, [{'field': 'panneau_par_defaut', 'old': False, 'new': True}])

    def test_refus_nom_et_fiche_en_desaccord(self):
        contradictoire = Produit.objects.create(company=self.company, nom='Panneau Jinko 710 W',
                                                prix_vente=Decimal('1100'))
        FicheTechnique.objects.create(company=self.company, produit=contradictoire, type_fiche='module',
                                      pmax_wc=Decimal('715'))
        rep = self._definir(contradictoire)
        self.assertEqual(rep.status_code, 400, rep.content)
        self.assertEqual(rep.json()['panneau_par_defaut'],
                         [_CONTRAT_PANNEAU['exemple_watt_contradictoire']['motif']])
        self.assertEqual(self._drapeaux(), set())

    def test_nom_modifie_apres_designation_rend_none(self):
        self._definir(self.p715)
        Produit.objects.filter(pk=self.p715.pk).update(nom='Panneau Canadian Solar 710 W')
        self.assertIsNone(spd.panneau_par_defaut(self.company))
        self.assertIsNone(spd.watt_panneau_par_defaut(self.company))
        rep = self._api('Technicien').get(self.URL_LECTURE)
        self.assertEqual(rep.json(), _CONTRAT_PANNEAU['exemple_watt_contradictoire'])

    def test_selecteur_archive_apres_designation_rend_none(self):
        self._definir(self.p715)
        Produit.objects.filter(pk=self.p715.pk).update(is_archived=True)
        self.assertIsNone(spd.panneau_par_defaut(self.company))
        self.assertIsNone(spd.watt_panneau_par_defaut(self.company))
        self.assertEqual(spd.resume_panneau_par_defaut(self.company)['source'], spd.ARCHIVE)
