# -*- coding: utf-8 -*-
"""U3 — UNE SEULE SOURCE DE VÉRITÉ pour la composition résidentielle.

Ce que ces tests verrouillent, et pourquoi :

Le 20/08/2026 le fondateur constate en production « il y a encore DEUX sortes
de devis ». C'était vrai : l'écran composait le kit en JavaScript
(``solar.js::autoFillLines``) pendant que le serveur le composait en Python
(``services.composition_residentielle``). Deux implémentations de la même
règle métier dérivent toujours — et elles avaient dérivé sur QUATRE points
mesurables : le câble au mètre (l'écran en posait deux lignes, le serveur
aucune), les marques épinglées, l'ordre des lignes, et l'arrondi du nombre de
panneaux.

Depuis U3, la composition vit UNIQUEMENT côté serveur et deux chemins la
lisent :

* ``POST /ventes/devis/composition/`` — le DRY-RUN : il compose et rend les
  lignes sans RIEN créer (l'écran générateur préremplit avec) ;
* ``POST /ventes/devis/auto/`` — il compose ET crée (la fiche lead).

**Le test de non-divergence** ci-dessous est celui qui compte : pour la même
entrée, les DEUX chemins doivent produire EXACTEMENT les mêmes lignes. Tant
qu'il est vert, il ne peut pas exister deux sortes de devis — c'est
littéralement la même composition qu'on lit deux fois.

Run :
    python manage.py test apps.ventes.tests.test_composition_source_unique -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes import services

User = get_user_model()

AUTO_URL = '/api/django/ventes/devis/auto/'
COMPO_URL = '/api/django/ventes/devis/composition/'

#: Catalogue riche : il porte de quoi éprouver CHAQUE règle migrée — deux
#: onduleurs (forme deux options), deux capacités de batterie, les deux
#: structures, et surtout les DEUX conditionnements de câble (au mètre ET
#: rouleau) pour prouver que seul le mètre est coté.
CATALOGUE = [
    ('Panneau Canadien Solar 710W', 'PAN710', '1450'),
    ('Panneau Jinko 550W', 'PAN550', '1100'),
    ('Onduleur réseau Huawei 5kW Monophasé', 'ONDR5', '14000'),
    ('Onduleur hybride Deye 5kW Monophasé', 'ONDH5', '17000'),
    ('Batterie Dyness 5 kWh', 'BAT5', '16000'),
    ('Batterie Dyness 10 kWh', 'BAT10', '30000'),
    ('Structures acier', 'STR-ACIER', '500'),
    ('Structures aluminium', 'STR-ALU', '850'),
    ('Socles', 'SOC', '80'),
    ('Smart Meter', 'SMART', '1800'),
    ('Wifi Dongle', 'WIFI', '1200'),
    ('Câble solaire Nexans 6 mm² (au mètre)', 'CAB-DC-M', '14.40'),
    ('Câble de terre Nexans 6 mm² (au mètre)', 'CAB-TER-M', '14.40'),
    # Le PIÈGE de l'incident fondateur du 19/08 : un rouleau de 100 m, chiffré,
    # que personne ne doit jamais quantifier EN MÈTRES (60 « unités » de
    # rouleau = 71 400 MAD de câble).
    ('Câble solaire 6mm² (100m)', 'CAB-DC-ROLL', '1190'),
    ('Accessoires', 'ACC', '2000'),
    ('Tableau De Protection AC/DC', 'TAB', '2000'),
    ('Installation', 'INST', '4800'),
    ('Transport', 'TRANS', '1000'),
]


def make_company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def seed(company):
    for nom, sku, prix in CATALOGUE:
        Produit.objects.create(
            company=company, nom=nom, sku='%s-%s' % (sku, company.pk),
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=1000)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(user))
    return api


class _Base(TestCase):
    slug = 'u3-source-unique'

    def setUp(self):
        self.company = make_company(self.slug)
        self.user = User.objects.create_user(
            username='u3-%s' % self.slug, password='x',
            company=self.company, role='admin')
        seed(self.company)
        self.api = auth_client(self.user)

    def lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Source', prenom='Unique',
            email='u3@example.com', **extra)

    @staticmethod
    def _sou(valeur):
        """Prix au centime — les deux chemins doivent tomber sur le MÊME, mais
        rien n'oblige leurs représentations à porter le même nombre de
        décimales : c'est la VALEUR qui est le contrat, pas sa chaîne."""
        return Decimal(str(valeur)).quantize(Decimal('0.01'))

    @classmethod
    def _empreinte_devis(cls, devis):
        """Ce qui doit concorder entre les deux chemins, dans l'ORDRE."""
        return [
            (li.designation, int(li.quantite), cls._sou(li.prix_unitaire))
            for li in devis.lignes.order_by('ordre', 'id')
        ]

    @classmethod
    def _empreinte_dry_run(cls, charge):
        return [
            (li['designation'], li['quantite'], cls._sou(li['prix_unitaire_ht']))
            for li in charge['lignes']
        ]


class LeDryRunEtLaCreationNeDiverguentPas(_Base):
    """LE test de U3 : une entrée, deux chemins, des lignes IDENTIQUES."""

    slug = 'u3-non-divergence'

    def test_meme_entree_memes_lignes_par_les_deux_chemins(self):
        lead = self.lead(taille_souhaitee_kwc=Decimal('5'))

        cree = self.api.post(AUTO_URL, {'lead': lead.id}, format='json')
        self.assertEqual(cree.status_code, 201, cree.data)
        from apps.ventes.models import Devis
        devis = Devis.objects.get(pk=cree.data['id'])

        # Le dry-run reçoit EXACTEMENT ce que le devis a réellement retenu :
        # sa puissance. Si les deux chemins composaient différemment, c'est
        # ici que ça se verrait — c'est tout l'objet du test.
        blanc = self.api.post(COMPO_URL, {
            'kwc': devis.etude_params['puissance_kwc'],
            'panel_watt': 710,
        }, format='json')
        self.assertEqual(blanc.status_code, 200, blanc.data)

        self.assertEqual(
            self._empreinte_devis(devis),
            self._empreinte_dry_run(blanc.data),
            'le dry-run et la création ne composent plus la même chose : '
            'il existe à nouveau DEUX sortes de devis')
        # Garde-fou du garde-fou : une empreinte vide passerait l'égalité
        # ci-dessus sans rien prouver.
        self.assertGreater(len(blanc.data['lignes']), 5)

    def test_le_dry_run_ne_cree_rien(self):
        """« À blanc » veut dire à blanc : aucun devis, aucune ligne."""
        from apps.ventes.models import Devis, LigneDevis
        avant = (Devis.objects.count(), LigneDevis.objects.count())
        reponse = self.api.post(
            COMPO_URL, {'kwc': 5, 'panel_watt': 710}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['lignes'])
        self.assertEqual(
            (Devis.objects.count(), LigneDevis.objects.count()), avant)

    def test_le_dry_run_est_company_scope(self):
        """Le catalogue d'une autre société ne fuite jamais dans la compo."""
        autre = make_company('u3-autre-societe')
        Produit.objects.create(
            company=autre, nom='Panneau Espion 999W', sku='SPY-999',
            prix_vente=Decimal('1'), prix_achat=Decimal('1'),
            quantite_stock=10)
        reponse = self.api.post(
            COMPO_URL, {'kwc': 5, 'panel_watt': 710}, format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertNotIn(
            'Espion',
            ' '.join(li['designation'] for li in reponse.data['lignes']))


class LesReglesMigreesViventCoteServeur(_Base):
    """Les trois règles qui n'existaient QUE dans solar.js y sont désormais."""

    slug = 'u3-regles-migrees'

    def _compo(self, **extra):
        charge = {'kwc': 5, 'panel_watt': 710}
        charge.update(extra)
        reponse = self.api.post(COMPO_URL, charge, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_c4_le_cable_est_compose_au_metre(self):
        """C4 — le serveur compose les DEUX câbles, et SEULEMENT au mètre.

        Avant U3 le serveur n'en composait aucun (son classifieur ignorait le
        mot « câble ») : le devis serveur partait sans câblage là où l'écran
        en posait deux lignes.
        """
        data = self._compo()
        par_role = {li['role']: li for li in data['lignes']}
        self.assertIn('cable_dc', par_role)
        self.assertIn('cable_terre', par_role)
        # 60 m par PAIRE de MPPT (repli fondateur explicite : 1 paire).
        self.assertEqual(par_role['cable_dc']['quantite'], 60)
        # 25 m de base + 15 m par palier de 5 kWc.
        self.assertEqual(par_role['cable_terre']['quantite'], 40)
        self.assertIn('au mètre', par_role['cable_dc']['designation'])

    def test_c4_le_rouleau_n_est_jamais_quantifie_en_metres(self):
        """Le piège du 19/08 : 60 « unités » d'un rouleau de 100 m."""
        data = self._compo()
        designations = [li['designation'] for li in data['lignes']]
        self.assertNotIn('Câble solaire 6mm² (100m)', designations)

    def test_c4_le_metrage_dc_suit_les_paires_de_mppt(self):
        data = self._compo(mppt_paires=3)
        par_role = {li['role']: li for li in data['lignes']}
        self.assertEqual(par_role['cable_dc']['quantite'], 180)
        # Le câble de TERRE, lui, suit les paliers de puissance, pas les paires.
        self.assertEqual(par_role['cable_terre']['quantite'], 40)

    def test_pvmrq_une_marque_epinglee_restreint_le_vivier(self):
        from apps.ventes.models import ParametresGammes
        ParametresGammes.objects.update_or_create(
            company=self.company,
            defaults={'marques': {
                ParametresGammes.SLOT_ESSENTIELLE: {'panneau': 'Jinko'}}})
        data = self._compo()
        panneau = next(li for li in data['lignes'] if li['role'] == 'panneau')
        self.assertIn('Jinko', panneau['designation'])
        self.assertEqual(data['marques_manquantes'], [])

    def test_pvmrq_une_marque_introuvable_est_DITE_jamais_remplacee(self):
        """Ordre fondateur #5 : jamais de substitution silencieuse."""
        from apps.ventes.models import ParametresGammes
        ParametresGammes.objects.update_or_create(
            company=self.company,
            defaults={'marques': {
                ParametresGammes.SLOT_ESSENTIELLE: {'panneau': 'Trina'}}})
        data = self._compo()
        self.assertEqual(
            [m['role'] for m in data['marques_manquantes']], ['panneau'])
        self.assertEqual(
            data['marques_manquantes'][0]['libelle_role'], 'Panneaux')
        # Le vivier est VIDE : aucune ligne panneau — surtout pas une autre marque.
        self.assertFalse(
            [li for li in data['lignes'] if li['role'] == 'panneau'])

    def test_pvmrq_la_creation_REFUSE_plutot_que_de_livrer_sans_panneaux(self):
        """La garde ne vivait que dans l'écran : le chemin serveur livrait un
        devis sans panneaux, à un prix effondré. Il refuse désormais."""
        from apps.ventes.models import Devis, ParametresGammes
        ParametresGammes.objects.update_or_create(
            company=self.company,
            defaults={'marques': {
                ParametresGammes.SLOT_ESSENTIELLE: {'panneau': 'Trina'}}})
        avant = Devis.objects.count()
        reponse = self.api.post(
            AUTO_URL, {'lead': self.lead(taille_souhaitee_kwc=Decimal('5')).id},
            format='json')
        self.assertEqual(reponse.status_code, 422, reponse.data)
        self.assertIn('Trina', reponse.data['detail'])
        self.assertIn('Panneaux', reponse.data['detail'])
        # Et surtout : AUCUN brouillon amputé ne reste derrière l'erreur.
        self.assertEqual(Devis.objects.count(), avant)

    def test_pvord_l_ordre_par_defaut_de_la_societe_est_applique(self):
        from apps.ventes.models import ParametresGammes
        ParametresGammes.objects.update_or_create(
            company=self.company,
            defaults={'ordre_lignes': ['panneau', 'transport']})
        data = self._compo()
        roles = [li['role'] for li in data['lignes']]
        self.assertEqual(roles[0], 'panneau')
        self.assertEqual(roles[1], 'transport')
        # Les rôles non préférés gardent leur rang canonique, DERRIÈRE.
        self.assertIn('onduleur_reseau', roles[2:])
        # L'ordre rendu est bien celui des index (le dry-run ne ment pas).
        self.assertEqual([li['ordre'] for li in data['lignes']],
                         list(range(len(data['lignes']))))

    def test_pvord_l_ordre_survit_a_la_creation(self):
        """PVORD ne vaut que si les lignes CRÉÉES le portent aussi."""
        from apps.ventes.models import Devis, ParametresGammes
        ParametresGammes.objects.update_or_create(
            company=self.company,
            defaults={'ordre_lignes': ['panneau', 'transport']})
        reponse = self.api.post(
            AUTO_URL, {'lead': self.lead(taille_souhaitee_kwc=Decimal('5')).id},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        devis = Devis.objects.get(pk=reponse.data['id'])
        lignes = list(devis.lignes.order_by('ordre', 'id'))
        self.assertIn('Panneau', lignes[0].designation)
        self.assertIn('Transport', lignes[1].designation)

    def test_u1_le_plafond_de_panneaux_est_celui_du_serveur(self):
        """U1 vu depuis la composition : 5 kWc en 710 Wc = 8 panneaux."""
        data = self._compo(kwc=5, panel_watt=710)
        panneau = next(li for li in data['lignes'] if li['role'] == 'panneau')
        self.assertEqual(panneau['quantite'], 8)
        self.assertEqual(data['nb_panneaux'], 8)
        # Structures = 1/panneau, socles = 2/panneau : les effets en cascade
        # suivent le plafond, ils ne restent pas sur l'ancien arrondi.
        par_role = {li['role']: li for li in data['lignes']}
        self.assertEqual(par_role['structure_acier']['quantite'], 8)
        self.assertEqual(par_role['socle']['quantite'], 16)

    def test_u2_le_dry_run_propose_les_deux_options_par_defaut(self):
        data = self._compo()
        roles = [li['role'] for li in data['lignes']]
        self.assertIn('onduleur_reseau', roles)
        self.assertIn('onduleur_hybride', roles)
        self.assertIn('batterie', roles)
        self.assertEqual(data['scenario'], 'Les deux (Sans + Avec)')

    def test_u2_un_scenario_explicite_reste_souverain(self):
        sans = self._compo(scenario='sans')
        self.assertNotIn('onduleur_hybride',
                         [li['role'] for li in sans['lignes']])
        self.assertNotIn('batterie', [li['role'] for li in sans['lignes']])
        avec = self._compo(scenario='avec')
        self.assertNotIn('onduleur_reseau',
                         [li['role'] for li in avec['lignes']])
        self.assertIn('batterie', [li['role'] for li in avec['lignes']])

    def test_le_ttc_rendu_est_derive_du_ht_stocke(self):
        """L'écran saisit en TTC mais la base fait foi en HT : le dry-run rend
        les deux, et le TTC doit être exactement le HT × (1 + TVA)."""
        data = self._compo(taux_tva=20)
        for ligne in data['lignes']:
            attendu = (Decimal(ligne['prix_unitaire_ht'])
                       * Decimal('1.20')).quantize(Decimal('0.01'))
            self.assertEqual(Decimal(ligne['prix_unitaire_ttc']), attendu,
                             ligne['designation'])


class LeDryRunRefuseCeQuIlNeSaitPasComposer(_Base):
    slug = 'u3-gardes-dry-run'

    def test_sans_puissance_ni_panneaux_c_est_400(self):
        reponse = self.api.post(COMPO_URL, {}, format='json')
        self.assertEqual(reponse.status_code, 400)

    def test_scenario_inconnu_c_est_422(self):
        reponse = self.api.post(
            COMPO_URL, {'kwc': 5, 'scenario': 'peut-etre'}, format='json')
        self.assertEqual(reponse.status_code, 422)

    def test_valeur_non_numerique_c_est_400(self):
        reponse = self.api.post(
            COMPO_URL, {'kwc': 'beaucoup'}, format='json')
        self.assertEqual(reponse.status_code, 400)

    def test_authentification_requise(self):
        self.assertEqual(
            APIClient().post(COMPO_URL, {'kwc': 5}, format='json').status_code,
            401)

    def test_nb_panneaux_seul_suffit(self):
        """kWc OU nombre de panneaux : l'un se déduit de l'autre."""
        reponse = self.api.post(
            COMPO_URL, {'nb_panneaux': 8, 'panel_watt': 710}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['nb_panneaux'], 8)


class LaFonctionPureResteApplelableSansReglage(_Base):
    """Sans réglage de gamme, la composition doit rester ce qu'elle était."""

    slug = 'u3-defauts'

    def test_sans_marque_ni_ordre_l_ordre_est_canonique(self):
        lignes = services.composition_residentielle(
            services.catalogue_de_la_societe(self.company),
            kwc=5, panel_watt=710, deux_options=True)
        roles = list(lignes.roles)
        self.assertEqual(roles[0], 'onduleur_reseau')
        self.assertEqual(roles[1], 'onduleur_hybride')
        self.assertEqual(list(lignes.marques_manquantes), [])
        # Le wattage RÉELLEMENT retenu est rendu (jamais un kWc théorique).
        self.assertEqual(lignes.panel_watt_reel, 710)
        self.assertEqual(lignes.kwc_reel, 5.68)

    def test_le_resultat_reste_une_liste_pour_les_appelants_historiques(self):
        lignes = services.composition_residentielle(
            services.catalogue_de_la_societe(self.company),
            kwc=5, panel_watt=710)
        self.assertIsInstance(lignes, list)
        self.assertTrue(all(hasattr(li, 'designation') for li in lignes))
