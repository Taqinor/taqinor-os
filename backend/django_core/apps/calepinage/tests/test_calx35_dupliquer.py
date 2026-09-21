"""CALX35 — la duplication EXISTANTE, enfin joignable par HTTP.

CE QUE CE FICHIER PROUVE
------------------------
``services/variantes.py::dupliquer`` (CAL14) recopiait déjà layout et
variantes vers un NOUVEAU calepinage, sans devis ni appel d'offres — et
``grep dupliquer`` sur ``views/`` et ``urls.py`` ne rendait rien : la
capacité était construite, testée, et injoignable.

Deux étages, deux coûts :

1. :class:`RoutageDupliquerTest` et :class:`ContratDupliquerTest`
   (``SimpleTestCase``, ni base ni réseau) — l'action est RÉELLEMENT
   enregistrée sur le viewset pivot (piège CALX7 : un ``__name__`` divergent
   fait disparaître la route en silence), et l'exemple COMMITTÉ du contrat
   est affirmé clé par clé : c'est lui que la moitié frontend importe.
2. :class:`DupliquerServiceTest` (``TestCase``) — la copie porte une
   référence NEUVE, ``devis`` à ``null``, le MÊME ``layout_hash``, l'original
   n'est pas modifié, et ``avec_variantes=False`` ne duplique aucune
   variante.

Run :
    python manage.py test apps.calepinage.tests.test_calx35_dupliquer -v2
"""
import json
import pathlib

from django.test import SimpleTestCase, TestCase

RACINE = pathlib.Path(__file__).resolve().parent.parent
ECHANTILLON = RACINE / 'contract_samples' / 'calepinage_dupliquer.json'


def _contrat():
    return json.loads(ECHANTILLON.read_text(encoding='utf-8'))


def _actions():
    """Les ``@action`` que le routeur DRF enregistrera, par nom de méthode."""
    from apps.calepinage import urls  # noqa: F401
    from apps.calepinage.views.calepinages import CalepinageViewSet

    return CalepinageViewSet, {methode.__name__: methode
                               for methode
                               in CalepinageViewSet.get_extra_actions()}


class RoutageDupliquerTest(SimpleTestCase):
    """Sans route, le bouton de la fiche appellerait dans le vide."""

    def test_l_action_est_enregistree_sur_le_pivot(self):
        _viewset, actions = _actions()
        self.assertIn(
            'dupliquer', actions,
            "L'action « dupliquer » n'est pas rattachée au CalepinageViewSet "
            "— vérifier la ligne ajoutée en fin de views/rattachements.py "
            '(CALX35).')
        self.assertEqual(actions['dupliquer'].url_path, 'dupliquer')
        self.assertTrue(actions['dupliquer'].detail)
        self.assertEqual(set(actions['dupliquer'].mapping), {'post'})

    def test_le_nom_de_la_fonction_egale_le_nom_de_l_attribut(self):
        """DRF mappe par ``__name__`` — un alias serait ignoré (CALX7)."""
        viewset, _actions_ = _actions()
        self.assertEqual(getattr(viewset, 'dupliquer').__name__, 'dupliquer')

    def test_dupliquer_exige_le_droit_de_gerer(self):
        _viewset, actions = _actions()
        self.assertEqual(
            [garde.__name__
             for garde in actions['dupliquer'].kwargs['permission_classes']],
            ['PeutGererCalepinage'])

    def test_le_module_est_declare_dans_MODULES_RATTACHES(self):
        from apps.calepinage.views.rattachements import MODULES_RATTACHES

        self.assertIn('cycle', MODULES_RATTACHES)


class ContratDupliquerTest(SimpleTestCase):
    """L'exemple COMMITTÉ est le seul point d'accord des deux moitiés."""

    def test_le_chemin_declare_est_celui_de_l_action(self):
        contrat = _contrat()
        self.assertEqual(
            contrat['endpoint'],
            'POST /api/django/calepinage/calepinages/<int:pk>/dupliquer/')

    def test_les_clefs_des_deux_etats_sont_les_memes(self):
        contrat = _contrat()
        self.assertEqual(sorted(contrat['exemple']),
                         sorted(contrat['exemple_sans_variantes']))

    def test_la_copie_ne_reprend_jamais_le_devis(self):
        for etat in ('exemple', 'exemple_sans_variantes'):
            self.assertIsNone(_contrat()[etat]['devis'],
                              f'{etat} : la copie ne réquisitionne pas le '
                              "devis de l'original (CAL14).")

    def test_l_etat_sans_variantes_n_en_compte_aucune(self):
        sans = _contrat()['exemple_sans_variantes']
        self.assertFalse(sans['avec_variantes'])
        self.assertEqual(sans['variantes_copiees'], 0)

    def test_les_deux_etats_portent_des_identifiants_distincts(self):
        contrat = _contrat()
        self.assertNotEqual(contrat['exemple']['calepinage'],
                            contrat['exemple']['source'])
        self.assertNotEqual(contrat['exemple']['reference'],
                            contrat['exemple_sans_variantes']['reference'])

    def test_le_layout_hash_est_celui_de_l_original(self):
        """La copie décrit la MÊME conception : même empreinte."""
        contrat = _contrat()
        self.assertEqual(contrat['exemple']['layout_hash'],
                         contrat['exemple_sans_variantes']['layout_hash'])


class DupliquerServiceTest(TestCase):
    """Le comportement métier du service que la vue expose."""

    def setUp(self):
        from apps.calepinage.models import Calepinage, CalepinageVariante
        from apps.crm.models import Client
        from authentication.models import Company

        self.company = Company.objects.create(nom='Dupli Co',
                                              slug='dupli-co-calx35')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Client Dupli')
        self.original = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Villa type',
            roof_layout={'zones': []}, layout_hash='c' * 64)
        for nom in ('A', 'B'):
            CalepinageVariante.objects.create(
                company=self.company, calepinage=self.original, nom=nom)

    def test_la_copie_porte_une_reference_neuve(self):
        from apps.calepinage.services.variantes import dupliquer
        from apps.calepinage.views.calepinages import _reference

        copie = dupliquer(self.original)
        self.assertNotEqual(copie.pk, self.original.pk)
        self.assertNotEqual(_reference(copie), _reference(self.original))

    def test_la_copie_ne_porte_aucun_devis(self):
        from apps.calepinage.services.variantes import dupliquer

        copie = dupliquer(self.original)
        self.assertIsNone(copie.devis_id)

    def test_le_layout_hash_est_identique(self):
        from apps.calepinage.services.variantes import dupliquer

        copie = dupliquer(self.original)
        self.assertEqual(copie.layout_hash, self.original.layout_hash)
        self.assertEqual(copie.roof_layout, self.original.roof_layout)

    def test_l_original_n_est_pas_modifie(self):
        from apps.calepinage.models import Calepinage, CalepinageVariante
        from apps.calepinage.services.variantes import dupliquer

        avant = Calepinage.objects.get(pk=self.original.pk)
        dupliquer(self.original)
        apres = Calepinage.objects.get(pk=self.original.pk)
        self.assertEqual(apres.titre, avant.titre)
        self.assertEqual(apres.layout_hash, avant.layout_hash)
        self.assertEqual(apres.devis_id, avant.devis_id)
        self.assertEqual(
            CalepinageVariante.objects.filter(
                calepinage=self.original).count(), 2)

    def test_avec_variantes_par_defaut_les_recopie(self):
        """D12 — le défaut EST le comportement d'aujourd'hui."""
        from apps.calepinage.models import CalepinageVariante
        from apps.calepinage.services.variantes import dupliquer

        copie = dupliquer(self.original)
        self.assertEqual(
            CalepinageVariante.objects.filter(calepinage=copie).count(), 2)

    def test_avec_variantes_false_n_en_duplique_aucune(self):
        from apps.calepinage.models import CalepinageVariante
        from apps.calepinage.services.variantes import dupliquer

        copie = dupliquer(self.original, avec_variantes=False)
        self.assertEqual(
            CalepinageVariante.objects.filter(calepinage=copie).count(), 0)
        # L'original garde les siennes : le drapeau ne déplace rien.
        self.assertEqual(
            CalepinageVariante.objects.filter(
                calepinage=self.original).count(), 2)

    def test_la_copie_garde_sa_societe_et_son_rattachement(self):
        from apps.calepinage.services.variantes import dupliquer

        copie = dupliquer(self.original)
        self.assertEqual(copie.company_id, self.company.pk)
        self.assertEqual(copie.client_id, self.client_a.pk)
