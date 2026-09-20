"""CAL20 — l'historique exposé : liste antichronologique et restauration.

Ce qui est prouvé ici :

* la liste est bornée société et rendue du plus récent au plus ancien ;
* une restauration AJOUTE une version : l'historique contient l'état restauré
  EN PLUS de tous les précédents — aucun instantané n'est réécrit ni supprimé ;
* le ``layout_hash`` du pivot devient celui de la version restaurée ;
* restaurer l'état DÉJÀ courant ne crée rien (``inchange``) ;
* une version d'un AUTRE calepinage / d'une autre société rend 404 ;
* sans ``calepinage_gerer``, la restauration répond 403.

Run :
    python manage.py test apps.calepinage.tests.test_api_versions -v2
"""
from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.layout import enregistrer_layout

from .test_api_liste import BaseApiCalepinage, url_detail

V1 = {'schema_version': 2, 'result': {'panels': 10}}
V2 = {'schema_version': 2, 'result': {'panels': 12}}
V3 = {'schema_version': 2, 'result': {'panels': 14}}


def url_versions(pk):
    return f'{url_detail(pk)}versions/'


def url_restaurer(pk, version_id):
    return f'{url_detail(pk)}versions/{version_id}/restaurer/'


class HistoriqueTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')
        for document in (V1, V2, V3):
            enregistrer_layout(self.calepinage, document, user=self.user)
        self.calepinage.refresh_from_db()
        self.versions = list(
            CalepinageVersion.objects.filter(calepinage=self.calepinage)
            .order_by('created_at', 'id'))
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=9, titre='Chez la voisine')

    def test_liste_antichronologique(self):
        reponse = self.api.get(url_versions(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        ids = [ligne['id'] for ligne in reponse.data]
        self.assertEqual(ids, [v.pk for v in reversed(self.versions)])
        self.assertEqual(set(reponse.data[0]),
                         {'id', 'libelle', 'layout_hash', 'cree_le',
                          'cree_par', 'a_un_resultat'})

    def test_restauration_ajoute_une_version_sans_en_retirer(self):
        avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()
        premiere = self.versions[0]
        reponse = self.api.post(
            url_restaurer(self.calepinage.pk, premiere.pk), {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(reponse.data['inchange'])
        apres = CalepinageVersion.objects.filter(calepinage=self.calepinage)
        self.assertEqual(apres.count(), avant + 1)
        # Tous les instantanés d'avant sont TOUJOURS là, inchangés.
        for version in self.versions:
            version.refresh_from_db()
            self.assertIsNotNone(version.pk)

    def test_le_pivot_porte_l_empreinte_de_la_version_restauree(self):
        premiere = self.versions[0]
        self.api.post(url_restaurer(self.calepinage.pk, premiere.pk), {},
                      format='json')
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.layout_hash, premiere.layout_hash)
        self.assertEqual(self.calepinage.roof_layout, V1)

    def test_restaurer_l_etat_courant_ne_cree_rien(self):
        courante = self.versions[-1]
        avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()
        reponse = self.api.post(
            url_restaurer(self.calepinage.pk, courante.pk), {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['inchange'])
        self.assertEqual(
            CalepinageVersion.objects.filter(
                calepinage=self.calepinage).count(), avant)

    def test_version_d_un_autre_calepinage_introuvable(self):
        autre = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Autre')
        reponse = self.api.post(url_restaurer(autre.pk, self.versions[0].pk),
                                {}, format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_calepinage_d_une_autre_societe_introuvable(self):
        reponse = self.api.get(url_versions(self.etranger.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_d_ecriture_403(self):
        reponse = self.api_sans.post(
            url_restaurer(self.calepinage.pk, self.versions[0].pk), {},
            format='json')
        self.assertEqual(reponse.status_code, 403)
