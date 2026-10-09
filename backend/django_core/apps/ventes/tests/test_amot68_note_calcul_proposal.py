"""AMOT68 (C-AMOT-058) — la note de calcul FDA (AGR319) est demandable.

``GET …/proposal/?include_note_calcul=1`` transmet l'option au moteur
(sonde VC agr5 : elle arrivait ``False``) ; sans le paramètre (ou ``=0``),
elle reste ``False``. Garde de classe : chaque clé de ``DEFAULT_PDF_OPTIONS``
est soit lue par ``/proposal``, soit dans une liste d'exceptions MOTIVÉE ;
idem pour les options envoyées par le dialogue (``useDevisPdf.js``).

Le moteur n'est PAS modifié (règle #4) : seul le rendu est simulé pour
capturer les options transmises.

Test-du-test : retirer la lecture de ``include_note_calcul`` dans
``proposal`` ⇒ ``test_parametre_transmis`` et la garde de classe échouent.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_amot68_note_calcul_proposal -v 2
"""
from pathlib import Path
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.quote_engine.builder import DEFAULT_PDF_OPTIONS
from apps.ventes.tests.test_l_niv_niveau import (
    make_client, make_company, make_devis, make_user,
)

RACINE = Path(__file__).resolve().parents[5]
VUE_PDF = (Path(__file__).resolve().parents[1] / 'views' / 'devis_pdf.py')
HOOK_PDF = (RACINE / 'frontend' / 'src' / 'pages' / 'ventes' / 'devisList'
            / 'useDevisPdf.js')

#: Clés de DEFAULT_PDF_OPTIONS que ``/proposal`` (interne) ne lit PAS, et
#: pourquoi.
EXCEPTIONS_PROPOSAL = {
    'include_annexe_technique': 'AUTO (PV46) : suit la conception électrique, '
                                'aucun geste interne ne la tranche',
    'kit_agrege': 'posé côté SERVEUR par les vues publiques (L-NIV)',
    'variante_option': 'choix de lecture du CLIENT sur sa page publique',
    'share_token': 'jeton du lien public, posé par les vues publiques',
}
#: Clés que le dialogue PDF de la liste n'envoie PAS, et pourquoi.
EXCEPTIONS_DIALOGUE = dict(EXCEPTIONS_PROPOSAL, **{
    'langue_sortie': 'résolue serveur (client > société > FR), NTI18N4',
})


class NoteCalculProposalTests(TestCase):

    def setUp(self):
        self.company = make_company('amot68')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj,
                                'DEV-AMOT68-0001')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _options_transmises(self, query=''):
        with mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf',
                        return_value='cle.pdf') as rendu, \
                mock.patch('apps.ventes.utils.pdf.download_pdf',
                           return_value=b'%PDF-1.4'):
            r = self.api.get(
                f'/api/django/ventes/devis/{self.devis.pk}/proposal/{query}')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r.content))
        return rendu.call_args[0][1]

    def test_parametre_transmis(self):
        self.assertIs(self._options_transmises(
            '?include_note_calcul=1')['include_note_calcul'], True)
        self.assertIs(self._options_transmises(
            '?include_note_calcul=true')['include_note_calcul'], True)

    def test_absent_ou_zero_reste_faux(self):
        self.assertIs(self._options_transmises()['include_note_calcul'], False)
        self.assertIs(self._options_transmises(
            '?include_note_calcul=0')['include_note_calcul'], False)

    def test_chaque_option_a_un_point_d_entree(self):
        vue = VUE_PDF.read_text(encoding='utf-8')
        sans_entree = [
            cle for cle in DEFAULT_PDF_OPTIONS
            if f"'{cle}'" not in vue and cle not in EXCEPTIONS_PROPOSAL]
        self.assertEqual(sans_entree, [],
                         'option de rendu sans point d\'entrée /proposal')
        if HOOK_PDF.exists():  # image backend seule : le frontend est absent
            hook = HOOK_PDF.read_text(encoding='utf-8')
            sans_geste = [
                cle for cle in DEFAULT_PDF_OPTIONS
                if cle not in hook and cle not in EXCEPTIONS_DIALOGUE]
            self.assertEqual(sans_geste, [],
                             'option de rendu sans geste dans le dialogue PDF')
