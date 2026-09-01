# -*- coding: utf-8 -*-
"""QJR80 — l'APERÇU et la CRÉATION composent par LA MÊME étape `composer`.

CE QUE CES TESTS VERROUILLENT, ET POURQUOI.

L'audit L3 du 29/08/2026 (constat QB80) a mesuré ceci : ``composer_devis_
residentiel`` — le dry-run que le vendeur APPROUVE à l'écran — et
``build_devis_from_layout`` — ce qui est RÉELLEMENT créé — enrobaient tous deux
``composition_residentielle``, mais lui passaient des jeux de paramètres
DIFFÉRENTS. La création n'ACCEPTAIT même pas ``mppt_paires`` ni
``structure_type`` : elle ne pouvait donc pas les transmettre. Résultat
mesurable sur la facture du client :

  · ``mppt_paires`` — le câble solaire DC est chiffré AU MÈTRE, 60 m par paire
    de MPPT (``metre_cable_dc_par_paires``). Un aperçu à 3 paires montrait
    180 m ; le devis créé en facturait 60. Trois fois moins de câble que
    l'aperçu approuvé.
  · ``structure_type`` — un aperçu en ALUMINIUM devenait un devis en ACIER,
    deux produits différents, deux prix différents.

Depuis QJR80 il n'y a plus qu'UN jeu de paramètres, nommé une seule fois
(``domain/pipeline.IntentionComposition``), et UNE fonction qui compose
(``domain/pipeline.composer``). Les deux chemins la remplissent. Un paramètre
ne peut plus être transmis d'un côté et oublié de l'autre — et un paramètre
AJOUTÉ demain le sera pour les deux.

Le test qui compte est ``test_apercu_et_creation_a_l_octet`` : mêmes entrées,
MÊMES lignes (désignation, quantité, prix unitaire HT), avec ``mppt_paires``
ET ``structure_type`` NON par défaut — les deux paramètres qui tombaient.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_pipeline_composer -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.domain import creation as _creation
from apps.ventes.domain import pipeline

User = get_user_model()

#: Catalogue minimal mais SUFFISANT pour que les deux paramètres tombés
#: laissent une trace : les DEUX structures (acier / aluminium) et le câble DC
#: AU MÈTRE (le seul conditionnement que la composition sait quantifier en
#: mètres).
CATALOGUE = [
    ('Panneau Canadien Solar 710W', 'PAN710', '1450'),
    ('Onduleur réseau Huawei 5kW Monophasé', 'ONDR5', '14000'),
    ('Onduleur hybride Deye 5kW Monophasé', 'ONDH5', '17000'),
    ('Batterie Dyness 5 kWh', 'BAT5', '16000'),
    ('Batterie Dyness 10 kWh', 'BAT10', '30000'),
    ('Structures acier', 'STR-ACIER', '500'),
    ('Structures aluminium', 'STR-ALU', '850'),
    ('Socles', 'SOC', '80'),
    ('Câble solaire Nexans 6 mm² (au mètre)', 'CAB-DC-M', '14.40'),
    ('Câble de terre Nexans 6 mm² (au mètre)', 'CAB-TER-M', '14.40'),
    ('Accessoires', 'ACC', '2000'),
    ('Tableau De Protection AC/DC', 'TAB', '2000'),
    ('Installation', 'INST', '4800'),
    ('Transport', 'TRANS', '1000'),
]

#: Le champ PV du scénario de test, écrit UNE fois : 9 panneaux de 710 Wc.
#: Le kWc est DÉRIVÉ (jamais un chiffre posé à la main) — c'est exactement ce
#: que les deux chemins calculent chacun de leur côté.
NB_PANNEAUX = 9
PANEL_WATT = 710
KWC = NB_PANNEAUX * PANEL_WATT / 1000.0

#: Les deux valeurs NON PAR DÉFAUT : c'est tout l'objet du test. Par défaut la
#: composition compose 1 paire de MPPT et de l'acier — deux chemins d'accord
#: par accident ne prouveraient rien.
MPPT_PAIRES = 3
STRUCTURE = 'aluminium'


class _Base(TestCase):
    slug = 'qjr80-composer'

    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.user = User.objects.create_user(
            username='qjr80-%s' % self.slug, password='x',
            company=self.company, role_legacy='admin')
        for nom, sku, prix in CATALOGUE:
            Produit.objects.create(
                company=self.company, nom=nom,
                sku='%s-%s' % (sku, self.company.pk),
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=1000)
        self.lead = Lead.objects.create(
            company=self.company, nom='Composer', prenom='QJR80',
            email='qjr80@example.com')

    # ── Les deux empreintes comparées ────────────────────────────────────────
    @staticmethod
    def _sou(valeur):
        """Prix au centime. Les deux chemins doivent tomber sur la MÊME
        VALEUR ; rien n'oblige leurs représentations à porter le même nombre
        de décimales."""
        return Decimal(str(valeur)).quantize(Decimal('0.01'))

    @classmethod
    def _empreinte_devis(cls, devis):
        return [(li.designation, int(li.quantite), cls._sou(li.prix_unitaire))
                for li in devis.lignes.order_by('ordre', 'id')]

    @classmethod
    def _empreinte_apercu(cls, charge):
        return [(li['designation'], int(li['quantite']),
                 cls._sou(li['prix_unitaire_ht']))
                for li in charge['lignes']]

    def _layout(self):
        return {'result': {'panels': NB_PANNEAUX, 'kwc': KWC},
                'panelWatt': PANEL_WATT, 'scenario': 'reseau'}


class LApercuEtLaCreationNeDiverguentPlus(_Base):
    """QB80 — mêmes entrées, MÊME composition, paramètres tombés compris."""

    slug = 'qjr80-non-divergence'

    def test_apercu_et_creation_a_l_octet(self):
        apercu = _creation.composer_devis_residentiel(
            company=self.company, nb_panneaux=NB_PANNEAUX,
            panel_watt=PANEL_WATT, scenario='sans',
            mppt_paires=MPPT_PAIRES, structure_type=STRUCTURE)
        devis = _creation.build_devis_from_layout(
            layout=self._layout(), user=self.user, company=self.company,
            lead=self.lead,
            mppt_paires=MPPT_PAIRES, structure_type=STRUCTURE)

        self.assertEqual(
            self._empreinte_apercu(apercu), self._empreinte_devis(devis),
            "l'aperçu approuvé par le vendeur et le devis réellement créé ne "
            "composent plus la même chose : le jeu de paramètres a re-divergé")
        # Garde-fou du garde-fou : deux listes vides seraient « égales ».
        self.assertGreater(len(apercu['lignes']), 5)

    def test_les_deux_parametres_tombes_arrivent_vraiment_au_devis(self):
        """Sans cette assertion, l'égalité ci-dessus passerait aussi si les
        DEUX chemins ignoraient ``mppt_paires`` et ``structure_type``."""
        devis = _creation.build_devis_from_layout(
            layout=self._layout(), user=self.user, company=self.company,
            lead=self.lead,
            mppt_paires=MPPT_PAIRES, structure_type=STRUCTURE)
        lignes = list(devis.lignes.all())

        cable = [li for li in lignes if 'Câble solaire' in li.designation]
        self.assertEqual(len(cable), 1, [li.designation for li in lignes])
        from apps.ventes.domain.catalogue import metre_cable_dc_par_paires
        self.assertEqual(int(cable[0].quantite),
                         metre_cable_dc_par_paires(MPPT_PAIRES),
                         'le devis créé ne chiffre pas le câble DC sur les '
                         'paires de MPPT de l’aperçu')

        structures = [li.designation for li in lignes
                      if 'Structures' in li.designation]
        self.assertEqual(structures, ['Structures aluminium'], structures)

    def test_les_defauts_de_la_creation_nont_pas_bouge(self):
        """Un appelant qui ne renseigne NI ``mppt_paires`` NI
        ``structure_type`` compose exactement ce que ce dépôt composait avant
        QJR80 : 1 paire (60 m) et de l'ACIER."""
        devis = _creation.build_devis_from_layout(
            layout=self._layout(), user=self.user, company=self.company,
            lead=self.lead)
        lignes = list(devis.lignes.all())
        cable = [li for li in lignes if 'Câble solaire' in li.designation]
        from apps.ventes.domain.catalogue import metre_cable_dc_par_paires
        self.assertEqual(int(cable[0].quantite), metre_cable_dc_par_paires(1))
        self.assertIn('Structures acier',
                      [li.designation for li in lignes])


class LesDeuxCheminsRemplissentLaMemeIntention(_Base):
    """Le contrôle STRUCTUREL, en amont des lignes : les deux appelants
    construisent la MÊME ``IntentionComposition``. Une future divergence de
    paramètre est rouge ici avant même d'être visible sur une ligne."""

    slug = 'qjr80-meme-intention'

    #: Les champs de composition qui doivent concorder. ``avertissements`` est
    #: un CANAL (une liste que l'appelant fournit pour être enrichi), pas un
    #: paramètre de composition : il est légitimement différent.
    CHAMPS = ('kwc', 'nb_panneaux', 'panel_watt', 'scenario',
              'structure_type', 'taux_tva', 'mppt_paires', 'phase',
              'gamme_nom_devis', 'dimensionnement_avec')

    def _capturer(self, appel):
        """Capture L'UNIQUE ``IntentionComposition`` que l'appel construit.

        QJR95 — L'ESPION EST POSÉ SUR LES DEUX NOMS, et c'est nécessaire depuis
        la bascule 3/5. Le dry-run appelle ``composer`` par le nom global de
        ``domain/creation`` ; la CRÉATION, elle, ne l'appelle plus elle-même :
        elle délègue à ``pipeline.appliquer``, qui résout ``composer`` dans les
        globales de ``domain/pipeline``. Ce sont deux NOMS pour la même
        fonction — n'en patcher qu'un rendrait ce test aveugle au chemin qu'il
        est justement censé comparer (il verrait zéro appel côté création).
        Ce que le test vérifie n'a pas changé d'un mot : les deux appelants
        remplissent la MÊME intention.
        """
        vues = []
        vrai = _creation.composer

        def espion(intention):
            vues.append(intention)
            return vrai(intention)

        _creation.composer = espion
        pipeline.composer = espion
        try:
            appel()
        finally:
            _creation.composer = vrai
            pipeline.composer = vrai
        self.assertEqual(len(vues), 1)
        return vues[0]

    def test_meme_intention_des_deux_cotes(self):
        intention_apercu = self._capturer(
            lambda: _creation.composer_devis_residentiel(
                company=self.company, nb_panneaux=NB_PANNEAUX,
                panel_watt=PANEL_WATT, scenario='sans',
                mppt_paires=MPPT_PAIRES, structure_type=STRUCTURE))
        intention_devis = self._capturer(
            lambda: _creation.build_devis_from_layout(
                layout=self._layout(), user=self.user, company=self.company,
                lead=self.lead,
                mppt_paires=MPPT_PAIRES, structure_type=STRUCTURE))

        for champ in self.CHAMPS:
            self.assertEqual(
                getattr(intention_apercu, champ),
                getattr(intention_devis, champ),
                'le champ « %s » de l’intention diverge entre l’aperçu et la '
                'création' % champ)
        self.assertEqual(intention_apercu.company, intention_devis.company)


class LIntentionEstGeleeEtLeScenarioValide(SimpleTestCase):
    """Les garanties du jeu de paramètres lui-même — aucune base requise."""

    def test_intention_gelee(self):
        intention = pipeline.IntentionComposition(company=None)
        with self.assertRaises(Exception):
            intention.mppt_paires = 4

    def test_defauts_alignes_sur_la_composition(self):
        """Les défauts de l'intention SONT ceux de
        ``composition_residentielle`` : sans quoi le simple passage par le
        pipeline changerait ce que ce dépôt compose."""
        import inspect
        from apps.ventes.domain.composition import composition_residentielle
        signature = inspect.signature(composition_residentielle)
        intention = pipeline.IntentionComposition(company=None)
        for champ in ('structure_type', 'taux_tva', 'mppt_paires', 'phase'):
            self.assertEqual(signature.parameters[champ].default,
                             getattr(intention, champ), champ)

    def test_scenario_inconnu_refuse_en_francais(self):
        with self.assertRaises(ValueError) as leve:
            pipeline.composer(
                pipeline.IntentionComposition(company=None,
                                              scenario='peut-etre'))
        self.assertIn('Scénario de composition inconnu', str(leve.exception))

    def test_les_trois_scenarios_composables(self):
        self.assertEqual(pipeline.SCENARIOS_COMPOSABLES,
                         ('sans', 'avec', 'les_deux'))
