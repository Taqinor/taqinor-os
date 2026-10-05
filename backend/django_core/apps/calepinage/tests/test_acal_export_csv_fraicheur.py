"""ACAL217 — l'export CSV et la provenance lisent UNE composition fraîche.

Constat C-ACAL-124 (C10, S2). ``GET export-csv/`` servait la série du STOCKÉ
(``Calepinage.resultat``) sans interroger la fraîcheur : après trois modules
retirés SANS relancer la simulation, le bureau d'études recevait le CSV de
l'ancien toit sous l'empreinte courante. Désormais l'export lit le résultat
SERVI (``selectors.resultat_servi``) : simulation périmée ⇒ 400 sous
``production`` avec le motif servi par ``GET resultat/`` ; frais ⇒ le même CSV
qu'avant, avec un en-tête à DEUX empreintes (document de pose + entrées de la
simulation) ; les en-têtes XLSX/DXF/JSON lisent production et pertes du servi
(« non publiée » quand périmé).

Le calepinage est fabriqué par les VRAIS écrivains
(``tests/acal_livrables_helpers.calepinage_simule_reel``), puis enregistré en
base ; le client HTTP est le vrai (``APIClient``). Aucun mock de la source.

Run :
    python manage.py test apps.calepinage.tests.test_acal_export_csv_fraicheur -v2
"""
import copy

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.calepinage.services.export_csv import (
    LIBELLE_EMPREINTE_LAYOUT, LIBELLE_EMPREINTE_SIMULATION, NON_CALCULEE,
)
from apps.calepinage.services.provenance_document import (
    NON_PUBLIEE, lignes_de_provenance,
)
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

from .acal_livrables_helpers import calepinage_simule_reel, patch_materiel

User = get_user_model()

BASE = '/api/django/calepinage/calepinages/'


class ExportFraicheurTest(TestCase):
    def setUp(self):
        societe = Company.objects.create(nom='ACAL217', slug='acal217')
        role = Role.objects.create(company=societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = User.objects.create_user(username='acal217', password='x',
                                        company=societe, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        lead = Lead.objects.create(company=societe, nom='Toiture 217')
        pivot = calepinage_simule_reel()
        self.calepinage = Calepinage.objects.create(
            company=societe, lead_id=lead.pk, titre='Export 217',
            roof_layout=copy.deepcopy(pivot.roof_layout),
            resultat=copy.deepcopy(pivot.resultat),
            layout_hash=pivot.layout_hash or '',
            version_moteur=pivot.version_moteur or '')

    def _url(self):
        return f'{BASE}{self.calepinage.pk}/export-csv/'

    def _lire(self, **parametres):
        with patch_materiel():
            return self.api.get(self._url(), parametres)

    def _retirer_trois_modules(self):
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] -= 3
        self.calepinage.roof_layout = layout
        self.calepinage.save()

    def test_le_depart_est_frais(self):
        with patch_materiel():
            servi = self.api.get(f'{BASE}{self.calepinage.pk}/resultat/')
        self.assertEqual(servi.status_code, 200, servi.content[:300])
        self.assertFalse(servi.data['simulation_perimee'])

    def test_export_csv_refuse_apres_edition_du_toit(self):
        self._retirer_trois_modules()
        with patch_materiel():
            servi = self.api.get(f'{BASE}{self.calepinage.pk}/resultat/').data
        self.assertTrue(servi['simulation_perimee'])
        for quoi in ('horaire', 'mensuel'):
            with self.subTest(quoi=quoi):
                reponse = self._lire(quoi=quoi)
                self.assertEqual(reponse.status_code, 400,
                                 getattr(reponse, 'data', reponse.content[:200]))
                # Le MÊME motif que GET resultat/, sous la clé ``production``.
                self.assertEqual(reponse.data['production'], [servi['motif']])

    def test_export_csv_frais_porte_les_deux_empreintes(self):
        reponse = self._lire(quoi='horaire')
        self.assertEqual(reponse.status_code, 200,
                         getattr(reponse, 'data', reponse.content[:200]))
        texte = reponse.content.decode('utf-8-sig')
        entete = [ligne.split(';') for ligne in texte.splitlines()
                  if ligne and not ligne[0].isdigit()]
        lignes = {ligne[0]: ligne[1] for ligne in entete if len(ligne) > 1}
        self.assertIn(LIBELLE_EMPREINTE_LAYOUT, lignes)
        self.assertIn(LIBELLE_EMPREINTE_SIMULATION, lignes)
        self.assertEqual(
            lignes[LIBELLE_EMPREINTE_SIMULATION],
            self.calepinage.resultat['simulation']['hash_entree'])
        self.assertNotEqual(lignes[LIBELLE_EMPREINTE_SIMULATION],
                            NON_CALCULEE)

    def test_deux_exports_successifs_memes_octets(self):
        premier = self._lire(quoi='horaire').content
        second = self._lire(quoi='horaire').content
        self.assertEqual(premier, second)

    def test_provenance_xlsx_non_publiee_quand_perimee(self):
        self._retirer_trois_modules()
        with patch_materiel():
            lignes = dict(lignes_de_provenance(self.calepinage))
        self.assertEqual(lignes['Base de rayonnement'], NON_PUBLIEE)
        self.assertEqual(lignes['Pertes passées à PVGIS (%)'], NON_PUBLIEE)
        self.assertEqual(lignes['Détail des pertes'], 'aucun poste publié')
        # Les empreintes restent : celle de la simulation périmée, et celle
        # du document d'aujourd'hui.
        self.assertIn(LIBELLE_EMPREINTE_LAYOUT, lignes)
        self.assertIn(LIBELLE_EMPREINTE_SIMULATION, lignes)
