"""CALX47 — ouvrir le module calepinage depuis la fiche d'un lead.

CE QUE CE FICHIER PROUVE
------------------------
Le CRM et la conception doivent être deux vues du MÊME dossier : avant cette
tâche, aucun lien de ``frontend/src/features/crm`` ne menait à
``/calepinage/…`` et aucune porte serveur ne partait d'un lead.

Deux étages, deux coûts :

1. :class:`RoutageDepuisLeadTest` (``SimpleTestCase``, ni base ni réseau) —
   l'action est RÉELLEMENT enregistrée sur le viewset pivot, en action de
   LISTE (elle ne vise aucun calepinage existant, elle en ouvre un), avec sa
   garde d'écriture. Piège CALX7 : un ``__name__`` divergent ferait
   disparaître la route en silence.
2. :class:`DepuisLeadIdempotentTest` (``TestCase``) — deux appels successifs
   rendent le MÊME identifiant, un lead d'une autre société est refusé en
   NOMMANT le champ, et un appelant sans société l'est aussi.

Run :
    python manage.py test apps.calepinage.tests.test_calx47_depuis_lead -v2
"""
from django.test import SimpleTestCase, TestCase


def _actions():
    """Les ``@action`` que le routeur DRF enregistrera, par nom de méthode."""
    from apps.calepinage import urls  # noqa: F401
    from apps.calepinage.views.calepinages import CalepinageViewSet

    return CalepinageViewSet, {methode.__name__: methode
                               for methode
                               in CalepinageViewSet.get_extra_actions()}


class RoutageDepuisLeadTest(SimpleTestCase):
    """Sans route, l'entrée neuve du rail CRM appellerait dans le vide."""

    def test_l_action_est_enregistree_sur_le_pivot(self):
        _viewset, actions = _actions()
        self.assertIn(
            'depuis_lead', actions,
            "L'action « depuis-lead » n'est pas rattachée au "
            'CalepinageViewSet — vérifier la ligne ajoutée en fin de '
            'views/rattachements.py (CALX47).')
        self.assertEqual(actions['depuis_lead'].url_path, 'depuis-lead')
        self.assertEqual(set(actions['depuis_lead'].mapping), {'post'})

    def test_c_est_une_action_de_LISTE(self):
        """Elle n'a aucun calepinage à viser : elle en ouvre un."""
        _viewset, actions = _actions()
        self.assertFalse(actions['depuis_lead'].detail)

    def test_le_nom_de_la_fonction_egale_le_nom_de_l_attribut(self):
        viewset, _actions_ = _actions()
        self.assertEqual(getattr(viewset, 'depuis_lead').__name__,
                         'depuis_lead')

    def test_elle_exige_le_droit_de_gerer(self):
        _viewset, actions = _actions()
        self.assertEqual(
            [garde.__name__
             for garde in actions['depuis_lead'].kwargs['permission_classes']],
            ['PeutGererCalepinage'])

    def test_le_module_est_declare_dans_MODULES_RATTACHES(self):
        from apps.calepinage.views.rattachements import MODULES_RATTACHES

        self.assertIn('depuis_lead', MODULES_RATTACHES)

    def test_le_module_ne_lit_le_crm_que_par_ses_selecteurs(self):
        """Contrats import-linter : jamais ``apps.crm.models`` ici."""
        import pathlib

        source = (pathlib.Path(__file__).resolve().parent.parent
                  / 'views' / 'depuis_lead.py').read_text(encoding='utf-8')
        self.assertNotIn('apps.crm.models', source)
        self.assertNotIn('from apps.crm import models', source)


class DepuisLeadIdempotentTest(TestCase):
    """Un lead qui a déjà un calepinage ouvert n'en reçoit jamais un second."""

    def setUp(self):
        from apps.crm.models import Lead
        from authentication.models import Company

        self.company = Company.objects.create(nom='Depuis Lead Co',
                                              slug='depuis-lead-calx47')
        self.autre_company = Company.objects.create(
            nom='Autre Co', slug='autre-co-calx47')
        self.lead = Lead.objects.create(company=self.company,
                                        nom='Lead Casablanca')

    def _porte(self, lead_id, company):
        """Le corps de l'action, isolé de HTTP (aucune requête à monter)."""
        from apps.calepinage.views.depuis_lead import _calepinage_ouvert

        from apps.calepinage.services.creation import creer_pour_lead

        existant = _calepinage_ouvert(lead_id, company)
        if existant is not None:
            return existant, False
        return creer_pour_lead(lead_id, company), True

    def test_deux_appels_successifs_rendent_le_MEME_identifiant(self):
        premier, cree_1 = self._porte(self.lead.pk, self.company)
        second, cree_2 = self._porte(self.lead.pk, self.company)

        self.assertTrue(cree_1)
        self.assertFalse(cree_2)
        self.assertEqual(premier.pk, second.pk)

    def test_un_calepinage_ARCHIVE_ne_bloque_pas_une_conception_neuve(self):
        """« Ouvert » = non archivé (CAL208) — ni ressuscité, ni bloquant."""
        from apps.calepinage.services.archivage import archiver

        premier, _ = self._porte(self.lead.pk, self.company)
        archiver(premier)
        second, cree = self._porte(self.lead.pk, self.company)

        self.assertTrue(cree)
        self.assertNotEqual(premier.pk, second.pk)

    def test_un_lead_d_une_AUTRE_societe_est_introuvable(self):
        from apps.calepinage.services.creation import CreationRefusee

        with self.assertRaises(CreationRefusee) as refus:
            self._porte(self.lead.pk, self.autre_company)
        self.assertEqual(refus.exception.champ, 'lead')

    def test_sans_societe_le_refus_NOMME_le_champ(self):
        from apps.calepinage.services.creation import CreationRefusee

        with self.assertRaises(CreationRefusee) as refus:
            self._porte(self.lead.pk, None)
        self.assertEqual(refus.exception.champ, 'company')

    def test_le_calepinage_ouvert_est_borne_societe(self):
        from apps.calepinage.views.depuis_lead import _calepinage_ouvert

        premier, _ = self._porte(self.lead.pk, self.company)
        self.assertIsNotNone(premier)
        # La MÊME clé de lead, lue depuis une AUTRE société : rien.
        self.assertIsNone(
            _calepinage_ouvert(self.lead.pk, self.autre_company))
