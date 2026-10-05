# -*- coding: utf-8 -*-
"""SPL130 — golden de ``DevisViewSet`` capturé AVANT la découpe de
``views/devis.py`` (piste SPL134-SPL142, déplacements purs).

Ce que le golden fige (``fixtures/golden_devis_viewset.json``, capturé sur le
code du 04/10/2026, avant tout déplacement) :

* ``routes`` — chaque route de ``DevisViewSet.get_extra_actions()`` (nom,
  ``url_path``, ``url_name``, ``detail``, méthodes triées) : 53 ``@action`` de
  la classe + ``economie`` greffée par ``views/economie.py`` = 54 ;
* ``noms_publics`` — ``sorted(n for n in dir(DevisViewSet)
  if not n.startswith('__'))`` : un mixin oublié dans les bases ou un nom
  renommé en route rougit ;
* (``corps`` — sha256 de ``ast.dump`` de chaque symbole déplacé : section
  ÉPHÉMÈRE, prouvée identique à chaque déplacement SPL134-SPL142 puis
  retirée par SPL142, dernière tâche de la piste, pour ne pas verrouiller
  les éditions futures de ces corps.)

``PLACE`` est rempli par chaque déplacement : ``groupe → fichier
de views/`` attendu. Tant qu'un groupe déclaré dans ``PLACE`` vit encore dans
``views/devis.py``, le test d'emplacement est ROUGE ; un symbole présent deux
fois (jumeau) l'est aussi. Le gel action × rôle vit déjà dans
``test_devis_matrice_permissions.py`` : il n'est pas dupliqué ici.

Le golden ne se régénère JAMAIS pour faire passer un déplacement : un golden
rouge est un bug du déplacement (NE PAS FAIRE du plan transverse).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_golden_devis_viewset"
"""
import ast
import inspect
import json
import re
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

VUES = Path(__file__).resolve().parent.parent / 'views'
FIXTURE = Path(__file__).resolve().parent / 'fixtures' / \
    'golden_devis_viewset.json'

#: 54 + ``facturer-complet`` (05/10/2026, ajout de route, pas un déplacement).
NB_ROUTES = 55
MIXIN = re.compile(r'^Devis\w*ActionsMixin$')

#: Les symboles que chaque tâche de la piste déplace (texte des tâches
#: SPL134-SPL142, se repérer par NOM).
GROUPES = {
    # SPL134 → views/devis_gardes.py
    'gardes': ['_refus_modifiabilite', '_reponse_non_modifiable',
               '_refus_verrou'],
    # SPL135 → views/devis_edition.py
    'edition': ['_garde_kwh_declare', '_valider_etude_ecran',
                '_gardes_mise_a_jour', '_DevisModifie', 'atomic',
                'replace_lines', 'perform_update'],
    # SPL136 → views/devis_cycle.py
    'cycle': ['_LotCreationSerializer', 'save_preset', '_reponse_derive',
              '_refus_derive_fige', 'reappliquer_lead', 'acquitter_derive',
              'dupliquer_variante', 'dupliquer_variante_gamme', 'variantes',
              'dupliquer', 'approuver_remise', 'reviser',
              'historique_configuration', 'lots', 'renouveler', 'accepter',
              'refuser', 'historique', 'noter'],
    # SPL137 → views/devis_etudes.py
    'etudes': ['_jeton', '_offres_tailles_reponse', '_overrides_reponse',
               'overrides', '_rafraichir_etudes_apres_surcharge',
               'etude_params', 'offres_tailles', 'offres_tailles_config',
               'offres_tailles_regenerer', 'offres_tailles_appliquer'],
    # SPL138 → views/devis_envoi.py
    'envoi': ['_gamme_envoi_payload', '_appliquer_gamme_envoi',
              '_RemiseEnvoiRefusee', '_exiger_remise_envoi', 'share_link',
              'envoyer_email', 'lecture_client', 'whatsapp_preview',
              'whatsapp', 'pdf_partage', 'contacter_superieur',
              'superior_contact_status'],
    # SPL139 → views/devis_pdf.py
    'pdf': ['generer_pdf', 'etat_pdf', 'proposal', 'telecharger_pdf'],
    # SPL140 → views/devis_calepinage.py
    'calepinage': ['_emettre_layout_finalise', 'from_layout',
                   'design_context', 'sync_layout', 'conception_electrique',
                   'simuler', 'simulation_status', 'ajouter_boq_electrique',
                   'layout', 'roof_image'],
    # SPL141 → views/devis_facturation.py
    'facturation': ['convertir_en_bc', 'generer_facture', 'proforma_pdf'],
    # SPL142 → views/devis_cadence.py
    'cadence': ['action_requise'],
}

#: groupe → fichier de ``views/`` où il DOIT vivre ; rempli par chaque
#: déplacement (ex. SPL134 : ``PLACE['gardes'] = 'devis_gardes.py'``).
PLACE = {
    'gardes': 'devis_gardes.py',  # SPL134
    'edition': 'devis_edition.py',  # SPL135
    'cycle': 'devis_cycle.py',  # SPL136
    'etudes': 'devis_etudes.py',  # SPL137
    'envoi': 'devis_envoi.py',  # SPL138
    'pdf': 'devis_pdf.py',  # SPL139
    'calepinage': 'devis_calepinage.py',  # SPL140
    'facturation': 'devis_facturation.py',  # SPL141
    'cadence': 'devis_cadence.py',  # SPL142
}

DEFAUT = 'devis.py'


def _fichiers_vues_devis():
    return [VUES / 'devis.py'] + sorted(VUES.glob('devis_*.py'))


def _symboles():
    """{nom: [(fichier, noeud)]} des symboles de ``views/devis*.py`` : niveau
    module + corps de ``DevisViewSet`` et de toute ``Devis*ActionsMixin``."""
    trouves = {}
    for chemin in _fichiers_vues_devis():
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        for noeud in arbre.body:
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                trouves.setdefault(noeud.name, []).append((chemin.name, noeud))
            if isinstance(noeud, ast.ClassDef) and (
                    noeud.name == 'DevisViewSet' or MIXIN.match(noeud.name)):
                for membre in noeud.body:
                    if isinstance(membre, (ast.FunctionDef,
                                           ast.AsyncFunctionDef,
                                           ast.ClassDef)):
                        trouves.setdefault(membre.name, []).append(
                            (chemin.name, membre))
    return trouves


def capturer_routes():
    from apps.ventes.views.devis import DevisViewSet
    routes = [{
        'nom': fn.__name__,
        'url_path': fn.url_path,
        'url_name': fn.url_name,
        'detail': fn.detail,
        'methodes': sorted(fn.mapping),
    } for fn in DevisViewSet.get_extra_actions()]
    return sorted(routes, key=lambda r: r['nom'])


#: Posés sur la CLASSE par ``ViewSetMixin.as_view()`` dès que l'URLconf est
#: chargée (DRF) : leur présence dépend de l'ordre des tests, pas du code.
POSES_PAR_AS_VIEW = {'basename', 'description', 'detail', 'name', 'suffix'}


def capturer_noms_publics():
    from apps.ventes.views.devis import DevisViewSet
    return sorted(n for n in dir(DevisViewSet)
                  if not n.startswith('__') and n not in POSES_PAR_AS_VIEW)


def _golden():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class GoldenDevisViewSet(SimpleTestCase):

    def test_routes_identiques(self):
        routes = capturer_routes()
        self.assertEqual(len(routes), NB_ROUTES)
        self.assertEqual(routes, _golden()['routes'])

    def test_noms_publics_identiques(self):
        self.assertEqual(capturer_noms_publics(), _golden()['noms_publics'])

    def test_chaque_groupe_vit_a_sa_place(self):
        from apps.ventes.views.devis import DevisViewSet
        trouves = _symboles()
        for groupe, noms in GROUPES.items():
            attendu = PLACE.get(groupe, DEFAUT)
            for nom in noms:
                with self.subTest(groupe=groupe, symbole=nom):
                    occurrences = trouves.get(nom, [])
                    self.assertEqual(
                        [f for f, _n in occurrences], [attendu],
                        'aucun jumeau : %s doit vivre UNE fois, dans '
                        'views/%s' % (nom, attendu))
                    membre = None
                    for base in DevisViewSet.__mro__:
                        if nom in base.__dict__:
                            membre = base.__dict__[nom]
                            break
                    if membre is None:
                        continue  # niveau module : l'AST fait foi
                    fn = inspect.unwrap(getattr(membre, '__func__', membre))
                    if not callable(fn) or isinstance(fn, type):
                        continue
                    self.assertEqual(Path(inspect.getsourcefile(fn)).name,
                                     attendu)

    def test_perform_update_vient_du_mixin_d_edition(self):
        """SPL135 — la surcharge de ``perform_update`` est conservée dans le
        MRO : elle vient de ``DevisEditionActionsMixin``, placé AVANT
        ``CompanyScopedModelViewSet`` dans les bases."""
        from apps.ventes.views.devis import DevisViewSet
        self.assertEqual(DevisViewSet.perform_update.__qualname__,
                         'DevisEditionActionsMixin.perform_update')


#: SPL139 — octets que le moteur « rend » pendant la capture : le rendu réel
#: (WeasyPrint + MinIO) n'est ni déterministe ni disponible hors pile ; ce
#: qui est figé ici est la VUE ``/proposal`` (routage, garde, paramètres
#: transmis au moteur, en-têtes, octets streamés tels quels). Le symbole
#: déplacé (``proposal``) n'est JAMAIS mocké : seuls le moteur et le
#: téléchargement MinIO le sont, à leur chemin de définition (les imports
#: restent function-locaux dans le corps).
_OCTETS_CAPTURE = b'%PDF-1.4 golden SPL139 /proposal'


class GoldenProposalReponse(TestCase):
    """SPL139 — capture GET ``/api/django/ventes/devis/<id>/proposal/``,
    identique avant et après le déplacement vers ``views/devis_pdf.py``
    (règle #4 : rendu seul, aucun statut écrit)."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='spl139-golden', defaults={'nom': 'SPL139 Golden'})[0]
        self.user = get_user_model().objects.create_user(
            username='spl139-resp', password='motdepasse-test-1234',
            company=self.company, role_legacy='responsable')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Golden', prenom='SPL139',
            email='spl139@example.invalid')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-SPL139-1',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    @patch('apps.ventes.utils.pdf.download_pdf',
           return_value=_OCTETS_CAPTURE)
    @patch('apps.ventes.quote_engine.generate_premium_devis_pdf',
           return_value='devis/spl139/DEV-SPL139-1.pdf')
    def test_proposal_reponse_identique(self, m_gen, m_dl):
        from apps.ventes.utils.filenames import document_filename
        statut_avant = self.devis.statut
        resp = self.api.get(
            '/api/django/ventes/devis/%d/proposal/'
            '?pdf_mode=onepage&devis_final=1' % self.devis.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertEqual(resp.content, _OCTETS_CAPTURE)
        nom = document_filename(
            'Proposition', self.devis.reference, client=self.client_obj,
            company=self.company)
        self.assertEqual(resp['Content-Disposition'],
                         'inline; filename="%s"' % nom)
        # Le moteur reçoit le devis, les options nettoyées, persist=False
        # (ERR74 : un GET ne persiste jamais fichier_pdf).
        self.assertEqual(m_gen.call_count, 1)
        args, kwargs = m_gen.call_args
        self.assertEqual(args[0], self.devis.id)
        self.assertEqual(kwargs, {'persist': False})
        self.assertEqual(args[1].get('pdf_mode'), 'onepage')
        self.assertIs(args[1].get('devis_final'), True)
        m_dl.assert_called_once_with('devis/spl139/DEV-SPL139-1.pdf')
        # Règle #4 : le rendu n'écrit aucun statut.
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, statut_avant)
