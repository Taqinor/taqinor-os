"""ACAL116 (D-ACAL-24, C-ACAL-094) — « Approbation exigée » active : générer /
resynchroniser le devis et les pièces d'exécution exigent une approbation À
JOUR ; les livrables d'étude impriment « Conception non approuvée ».

Le réglage société est ÉCRIT EN BASE ; routes HTTP réelles ; la mention est
lue dans le TEXTE imprimé (pied de planche SVG, corps de la note), jamais
dans les octets d'un PDF.

Run :
    python manage.py test apps.calepinage.tests.test_acal_portee_approbation -v2
"""
import copy

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, tag

from apps.calepinage.models import Calepinage
from apps.calepinage.services.approbation import decider
from apps.calepinage.services.feu_vert import PIECES_EXECUTION
from apps.calepinage.services.layout import (
    empreinte_document, enregistrer_layout,
)
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
from apps.ventes.models import Devis

from .acal_livrables_helpers import LAYOUT_PLANCHE_SIMULABLE
from .test_api_liste import BaseApiCalepinage, url_detail
from .test_cal173_empreinte import MOMENT

User = get_user_model()

#: Chaque pièce d'exécution → sa porte HTTP réelle.
ROUTES = {
    'plan_pose': ('get', 'plan-pose.pdf/'),
    'plan_cablage': ('get', 'plan-cablage.pdf/'),
    'plan_cablage_dxf': ('get', 'plan-cablage.dxf/'),
    'export_dxf': ('get', 'export.dxf/'),
    'export_xlsx': ('get', 'export.xlsx/'),
    'export_csv': ('get', 'export.csv/'),
    'pack_technique': ('post', 'pack-technique/'),
    'dossier_fin_chantier': ('post', 'dossier-fin-chantier/'),
    'dossier_reglementaire': ('post', 'generer-dossier/'),  # ACON44
}

TOIT = {
    'areas': [{'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
               'obstacles': [], 'roofType': 'flat', 'pitch': 10,
               'azimuth': 180}],
    'zones': [{'id': 'z1', 'label': 'Pan Sud',
               'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]]}],
    'scenario': 'reseau',
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
}


class PorteeApprobationTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue
        seed_catalogue(self.company)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL116')
        # ACAL303 — la conception est d'un AUTRE compte que le relecteur
        # (``self.user`` approuve : séparation des tâches).
        enregistrer_layout(self.calepinage, copy.deepcopy(TOIT),
                           user=self.user_sans)
        self.base = url_detail(self.calepinage.pk)

    def _exiger(self, valeur=True):
        enregistrer_parametres(self.company,
                               {'presets': {'approbation_exigee': valeur}})

    def _generer(self):
        return self.api.post(f'{self.base}generer-devis/', {}, format='json')

    def test_from_layout_lead_d_un_collegue_404(self):
        # ADVS44 — A ne reçoit ni le brouillon de B ni son jeton.
        role = Role.objects.create(
            company=self.company, nom='Commercial ADVS44',
            permissions=list(COMMERCIAL_PERMISSIONS))
        a, b = (User.objects.create_user(
            username=nom, password='x', company=self.company, role=role)
            for nom in ('advs44_a', 'advs44_b'))
        lead_b = Lead.objects.create(
            company=self.company, nom='Collegue', prenom='LeadB', owner=b,
            email='advs44@example.com', telephone='+212600004044')
        corps = {'layout': copy.deepcopy(TOIT), 'lead': lead_b.pk}
        url = '/api/django/ventes/devis/from-layout/'
        api_a, api_b = self._client(a), self._client(b)
        cree = api_b.post(url, corps, format='json')
        self.assertEqual(cree.status_code, 201, cree.data)
        refus = api_a.post(url, corps, format='json')
        self.assertEqual(refus.status_code, 404, refus.data)
        self.assertEqual(refus.data, {'detail': 'Lead inconnu.'})
        self.assertEqual(Devis.objects.filter(lead_id=lead_b.pk).count(), 1)
        rejoue = api_b.post(url, corps, format='json')
        self.assertEqual(rejoue.status_code, 200, rejoue.data)
        self.assertEqual(rejoue.data['id'], cree.data['id'])
        self.assertTrue(rejoue.data['deduplicated'])

    def test_generer_refuse_sans_approbation_a_jour(self):
        self._exiger()
        avant = Devis.objects.filter(company=self.company).count()
        reponse = self._generer()
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('Approbation à jour exigée', str(reponse.data))
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)

    def test_sync_refuse_approbation_perimee(self):
        self._exiger()
        self.calepinage.refresh_from_db()
        decider(self.calepinage, decision='approuve', user=self.user,
                empreinte=self.calepinage.layout_hash or '')  # ACON23
        reponse = self._generer()
        self.assertEqual(reponse.status_code, 201, reponse.data)
        # La conception change : l'approbation est périmée.
        self.calepinage.refresh_from_db()
        autre = copy.deepcopy(TOIT)
        autre['result']['panels'] = 14
        autre['zones'][0]['vertices'] = [[0, 0], [14, 0], [14, 6], [0, 6]]
        jeton = empreinte_document(self.calepinage.roof_layout)
        reponse = self.api.post(f'{self.base}layout/', autre, format='json',
                                HTTP_IF_MATCH=f'"{jeton}"')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        reponse = self.api.post(f'{self.base}sync-devis/', {},
                                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('approbation', str(reponse.data))

    def test_pieces_execution_refusees(self):
        self._exiger()
        self.assertEqual(set(ROUTES), set(PIECES_EXECUTION))
        for piece in PIECES_EXECUTION:
            with self.subTest(piece=piece):
                methode, chemin = ROUTES[piece]
                appel = getattr(self.api, methode)
                reponse = (appel(f'{self.base}{chemin}', {}, format='json')
                           if methode == 'post'
                           else appel(f'{self.base}{chemin}'))
                self.assertEqual(reponse.status_code, 409,
                                 (piece, reponse.status_code))
                self.assertIn('approbation', str(reponse.data))

    def test_livrables_etude_portent_non_approuvee(self):
        from apps.calepinage.services.documents.gabarit_document import (
            MENTION_NON_APPROUVEE, etat_de_conception, mentions_d_etat,
        )
        from apps.calepinage.services.planche import rendre_planche_svg

        self._exiger()
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=copy.deepcopy(LAYOUT_PLANCHE_SIMULABLE))
        cal = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertIn(MENTION_NON_APPROUVEE,
                      mentions_d_etat(etat_de_conception(cal)))
        planche = rendre_planche_svg(cal, moment=MOMENT)
        self.assertIn(MENTION_NON_APPROUVEE, planche)

    @tag('pdf')
    def test_livrables_etude_pdf_texte_extrait(self):
        """Lot 2 critique #34 — la mention est lue dans le TEXTE EXTRAIT des
        PDF servis (planche, rapport d'étude), jamais dans leurs octets."""
        from apps.calepinage.services.documents.gabarit_document import (
            MENTION_NON_APPROUVEE,
        )

        from .acal_livrables_helpers import (
            calepinage_simule_reel, exiger_bibliotheques_pdf, patch_materiel,
        )

        exiger_bibliotheques_pdf()
        import fitz

        pivot = calepinage_simule_reel(LAYOUT_PLANCHE_SIMULABLE)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=copy.deepcopy(pivot.roof_layout),
            resultat=copy.deepcopy(pivot.resultat),
            layout_hash=pivot.layout_hash or '',
            version_moteur=pivot.version_moteur or '')
        self._exiger()
        for route in ('planche.pdf/', 'rapport-etude.pdf/'):
            with self.subTest(route=route):
                with patch_materiel():
                    reponse = self.api.get(f'{self.base}{route}')
                self.assertEqual(reponse.status_code, 200,
                                 getattr(reponse, 'data', None))
                octets = (b''.join(reponse.streaming_content)
                          if getattr(reponse, 'streaming', False)
                          else reponse.content)
                document = fitz.open(stream=octets, filetype='pdf')
                try:
                    texte = ' '.join(page.get_text() for page in document)
                finally:
                    document.close()
                self.assertIn(MENTION_NON_APPROUVEE, ' '.join(texte.split()))

    def test_reglages_inactifs_rien_ne_change(self):
        from apps.calepinage.services.documents.gabarit_document import (
            etat_de_conception, mentions_d_etat,
        )

        reponse = self._generer()
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.calepinage.refresh_from_db()
        self.assertEqual(mentions_d_etat(etat_de_conception(self.calepinage)),
                         [])


class PorteEtSchemaTest(SimpleTestCase):
    """Lot 2 critique #20 — la porte d'exécution lève une VRAIE exception
    pour une pièce inconnue (jamais un ``assert``), et chaque méthode du
    sérialiseur porte SON type de schéma."""

    def test_piece_inconnue_leve(self):
        from apps.calepinage.views.sorties import porte_execution

        with self.assertRaises(ValueError):
            porte_execution(object(), 'piece_inconnue')

    def test_types_de_schema_a_leur_methode(self):
        from rest_framework import serializers

        from apps.calepinage.serializers import CalepinageSerializer

        def champ(methode):
            return getattr(CalepinageSerializer, methode) \
                ._spectacular_annotation['field']

        self.assertIsInstance(champ('get_layout_stale'),
                              serializers.BooleanField)
        self.assertIsInstance(champ('get_statut'), serializers.CharField)
        self.assertIsInstance(champ('get_statut_libelle'),
                              serializers.CharField)
