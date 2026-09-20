"""CAL24 — « Générer le devis » depuis un calepinage.

Ce qui est prouvé ici :

* le chemin canonique est APPELÉ, pas doublé : ``build_devis_from_layout``
  reçoit le lead/client DU CALEPINAGE, la société et l'auteur côté serveur ;
* le devis créé porte le MÊME ``layout_hash`` que le calepinage, et le
  calepinage lui est rattaché ;
* un SECOND appel rend le MÊME devis (dédup ``lead`` + ``layout_hash``), sans
  rappeler le constructeur ;
* un catalogue invalide remonte le 422 du serveur ventes MOT POUR MOT ;
* un calepinage sans conception est refusé en nommant le champ ;
* un calepinage d'une autre société est introuvable (404).

Le constructeur ventes est simulé : ce fichier prouve le PONT, pas la
composition (qui a ses propres tests côté ventes).

Run :
    python manage.py test apps.calepinage.tests.test_api_generer_devis -v2
"""
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {'schema_version': 2, 'result': {'panels': 12, 'kwc': 8.64}}


def url_generer(pk):
    return f'{url_detail(pk)}generer-devis/'


class GenererDevisTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.client_lie = Client.objects.create(company=self.company,
                                                nom='Bâtiment Atlas 24')
        self.lead_lie = Lead.objects.create(company=self.company,
                                            nom='Toiture Anfa 24')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk,
            titre='Villa Anfa', roof_layout=LAYOUT, layout_hash='c' * 64)
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=3, titre='Chez la voisine')

    def _devis_neuf(self):
        return Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference='DEV-202609-2424')

    def test_creation_lie_le_devis_et_porte_la_meme_empreinte(self):
        devis = self._devis_neuf()
        with mock.patch('apps.ventes.services.validate_composition_for_layout',
                        return_value=[]), \
                mock.patch('apps.ventes.services.build_devis_from_layout',
                           return_value=devis) as construire:
            reponse = self.api.post(url_generer(self.calepinage.pk), {},
                                    format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertTrue(construire.called)
        appel = construire.call_args.kwargs
        self.assertEqual(appel['company'], self.company)
        self.assertEqual(appel['lead'].pk, self.lead_lie.pk)
        self.assertEqual(appel['user'], self.user)
        devis.refresh_from_db()
        self.calepinage.refresh_from_db()
        self.assertEqual(devis.layout_hash, self.calepinage.layout_hash)
        self.assertEqual(self.calepinage.devis_id, devis.pk)
        self.assertFalse(reponse.data['deduplique'])

    def test_second_appel_rend_le_meme_devis(self):
        devis = self._devis_neuf()
        devis.layout_hash = self.calepinage.layout_hash
        devis.save(update_fields=['layout_hash'])
        with mock.patch('apps.ventes.services.validate_composition_for_layout',
                        return_value=[]), \
                mock.patch('apps.ventes.services.build_devis_from_layout'
                           ) as construire:
            reponse = self.api.post(url_generer(self.calepinage.pk), {},
                                    format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['deduplique'])
        self.assertEqual(reponse.data['devis'], devis.pk)
        construire.assert_not_called()

    def test_catalogue_invalide_remonte_le_422_mot_pour_mot(self):
        motifs = ['Aucun panneau tarifé au catalogue.']
        with mock.patch('apps.ventes.services.validate_composition_for_layout',
                        return_value=motifs):
            reponse = self.api.post(url_generer(self.calepinage.pk), {},
                                    format='json')
        self.assertEqual(reponse.status_code, 422)
        self.assertEqual(reponse.data['detail'], motifs[0])
        self.assertEqual(reponse.data['errors'], motifs)

    def test_sans_conception_refuse_en_nommant_le_champ(self):
        nu = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, titre='Nu')
        reponse = self.api.post(url_generer(nu.pk), {}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('roof_layout', reponse.data)

    def test_autre_societe_introuvable(self):
        reponse = self.api.post(url_generer(self.etranger.pk), {},
                                format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_d_ecriture_403(self):
        reponse = self.api_sans.post(url_generer(self.calepinage.pk), {},
                                     format='json')
        self.assertEqual(reponse.status_code, 403)
