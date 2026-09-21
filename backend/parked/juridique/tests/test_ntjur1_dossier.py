"""NTJUR1 — ``DossierJuridique`` : isolation société, référence, confidentialité.

Critère d'acceptation : « un directeur crée un dossier contentieux et il
n'apparaît que dans sa société ».
"""
from datetime import date

from django.test import TestCase

from apps.juridique.models import DossierJuridique

from ._base import auth, make_admin, make_company, make_responsable

URL = '/api/django/juridique/dossiers/'


class DossierJuridiqueApiTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-d1-co', 'Juridique D1')
        self.autre = make_company('jur-d1-autre', 'Juridique D1 Autre')
        self.admin = make_admin(self.company, 'jur-d1-admin')
        self.admin_autre = make_admin(self.autre, 'jur-d1-admin-autre')
        self.api = auth(self.admin)

    def _payload(self, **extra):
        data = {
            'titre': 'SARL Alpha c/ nous',
            'nature': DossierJuridique.Nature.CONTENTIEUX,
            'type_procedure': DossierJuridique.TypeProcedure.COMMERCIAL,
            'date_ouverture': '2026-03-02',
            'montant_en_jeu': '150000.00',
            'partie_adverse_nom': 'SARL Alpha',
        }
        data.update(extra)
        return data

    def test_creation_pose_societe_et_reference_annuelle(self):
        resp = self.api.post(URL, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        dossier = DossierJuridique.objects.get(pk=resp.data['id'])
        self.assertEqual(dossier.company_id, self.company.id)
        self.assertEqual(dossier.created_by_id, self.admin.id)
        annee = date.today().year
        self.assertEqual(dossier.reference, f'JUR-{annee}-0001')
        self.assertEqual(dossier.statut, DossierJuridique.Statut.OUVERT)

    def test_reference_ne_recule_jamais_apres_suppression(self):
        """Anti-``count() + 1`` : supprimer le 2e dossier ne recycle pas son
        numéro (collision déjà vécue en production)."""
        self.api.post(URL, self._payload(), format='json')
        second = self.api.post(URL, self._payload(titre='Deuxième'),
                               format='json')
        DossierJuridique.objects.filter(pk=second.data['id']).delete()
        troisieme = self.api.post(URL, self._payload(titre='Troisième'),
                                  format='json')
        annee = date.today().year
        self.assertEqual(troisieme.data['reference'], f'JUR-{annee}-0003')

    def test_societe_du_corps_de_requete_est_ignoree(self):
        resp = self.api.post(
            URL, self._payload(company=self.autre.id), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            DossierJuridique.objects.get(pk=resp.data['id']).company_id,
            self.company.id)

    def test_un_dossier_n_apparait_que_dans_sa_societe(self):
        cree = self.api.post(URL, self._payload(), format='json')
        api_autre = auth(self.admin_autre)
        liste = api_autre.get(URL)
        self.assertEqual(liste.status_code, 200)
        ids = [row['id'] for row in liste.data.get('results', liste.data)]
        self.assertNotIn(cree.data['id'], ids)
        detail = api_autre.get(f"{URL}{cree.data['id']}/")
        self.assertEqual(detail.status_code, 404)

    def test_dossier_confidentiel_invisible_hors_palier_admin(self):
        """404 (jamais 403) : révéler l'existence serait déjà une fuite."""
        confidentiel = DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0099',
            titre='Affaire direction', date_ouverture=date(2026, 1, 5),
            confidentialite=(
                DossierJuridique.NiveauConfidentialite.CONFIDENTIEL))
        responsable = make_responsable(self.company, 'jur-d1-resp')
        api_resp = auth(responsable)
        liste = api_resp.get(URL)
        ids = [row['id'] for row in liste.data.get('results', liste.data)]
        self.assertNotIn(confidentiel.id, ids)
        self.assertEqual(
            api_resp.get(f'{URL}{confidentiel.id}/').status_code, 404)
        # L'administrateur, lui, le voit.
        self.assertEqual(
            self.api.get(f'{URL}{confidentiel.id}/').status_code, 200)

    def test_responsable_interne_doit_etre_de_la_meme_societe(self):
        resp = self.api.post(
            URL,
            self._payload(responsable_interne=self.admin_autre.id),
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('responsable_interne', resp.data)

    def test_statut_est_en_lecture_seule(self):
        cree = self.api.post(URL, self._payload(), format='json')
        patch = self.api.patch(
            f"{URL}{cree.data['id']}/",
            {'statut': DossierJuridique.Statut.CLOS_GAGNE}, format='json')
        self.assertEqual(patch.status_code, 200, patch.data)
        self.assertEqual(
            DossierJuridique.objects.get(pk=cree.data['id']).statut,
            DossierJuridique.Statut.OUVERT)
