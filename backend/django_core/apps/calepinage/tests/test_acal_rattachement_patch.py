"""ACAL179 — renommer et PATCHer un calepinage lead+client.

Avant : le sérialiseur imposait « lead OU client, pas les deux » (XOR) alors
que depuis-lead, la création pour un devis, ``lier_devis`` et la duplication
posent TOUS lead ET client — renommer un tel calepinage rendait 400 {client}.
Et un PATCH ``{nom}`` (clé servie, dérivée du titre) rendait 200 sans rien
écrire.

HTTP réel, quatre services de création réels, ``crm.selectors`` réel : aucun
mock.
"""
from __future__ import annotations

from apps.calepinage.models import Calepinage
from apps.calepinage.services.creation import (
    creer_pour_lead, obtenir_ou_creer_pour_devis,
)
from apps.calepinage.services.liens import lier_devis
from apps.calepinage.services.variantes import dupliquer
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail


class RattachementPatchTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.lead_client = Lead.objects.create(
            company=self.company, nom='Toiture Ain Diab',
            client=self.client_a)
        self.autre_client = Client.objects.create(company=self.company,
                                                  nom='Bâtiment Rif')

    def _quatre_calepinages(self):
        depuis_lead = creer_pour_lead(self.lead_client.pk, self.company,
                                      user=self.user)
        devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            lead=self.lead_client, reference='DEV-202610-1791')
        pour_devis, _ = obtenir_ou_creer_pour_devis(devis.pk, self.company,
                                                    user=self.user)
        lie = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_client.pk, titre='Lié')
        devis_2 = Devis.objects.create(
            company=self.company, client=self.client_a,
            lead=self.lead_client, reference='DEV-202610-1792')
        lier_devis(lie, devis_2.pk)
        # ACAL187 (D-ACAL-12) — la source est OUVERTE : la copie vise un
        # AUTRE lead du même client, dont le client est repris.
        self.lead_copie = Lead.objects.create(
            company=self.company, nom='Toiture Oasis', client=self.client_a)
        copie = dupliquer(depuis_lead, user=self.user,
                          lead_id=self.lead_copie.pk)
        calepinages = {'depuis-lead': depuis_lead, 'pour-devis': pour_devis,
                       'lier-devis': lie, 'dupliquer': copie}
        for nom, calepinage in calepinages.items():
            calepinage.refresh_from_db()
            lead = (self.lead_copie if nom == 'dupliquer'
                    else self.lead_client)
            self.assertEqual(
                (calepinage.lead_id, calepinage.client_id),
                (lead.pk, self.client_a.pk), nom)
        return calepinages

    def test_patch_titre_sur_calepinage_cree_depuis_lead_avec_client(self):
        for nom, calepinage in self._quatre_calepinages().items():
            with self.subTest(service=nom):
                for _ in range(2):  # idempotent
                    reponse = self.api.patch(url_detail(calepinage.pk),
                                             {'titre': 'Renommé'},
                                             format='json')
                    self.assertEqual(reponse.status_code, 200, reponse.data)
                relu = self.api.get(url_detail(calepinage.pk))
                self.assertEqual(relu.status_code, 200, relu.data)
                self.assertEqual(relu.data['nom'], 'Renommé')
                calepinage.refresh_from_db()
                self.assertEqual(calepinage.titre, 'Renommé')
                self.assertEqual(
                    (calepinage.lead_id, calepinage.client_id),
                    (self.lead_client.pk, self.client_a.pk))

    def test_patch_responsable_idem(self):
        for nom, calepinage in self._quatre_calepinages().items():
            with self.subTest(service=nom):
                reponse = self.api.patch(url_detail(calepinage.pk),
                                         {'responsable': self.user.pk},
                                         format='json')
                self.assertEqual(reponse.status_code, 200, reponse.data)
                calepinage.refresh_from_db()
                self.assertEqual(calepinage.responsable_id, self.user.pk)

    def test_client_incoherent_avec_le_lead_refuse(self):
        calepinage = creer_pour_lead(self.lead_client.pk, self.company,
                                     user=self.user)
        reponse = self.api.patch(url_detail(calepinage.pk),
                                 {'client': self.autre_client.pk},
                                 format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('client', reponse.data)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.client_id, self.client_a.pk)

    def test_lead_sans_client_reste_valide(self):
        reponse = self.api.post('/api/django/calepinage/calepinages/',
                                {'lead': self.lead.pk, 'titre': 'Lead seul'},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        cree = Calepinage.objects.get(pk=reponse.data['id'])
        self.assertIsNone(cree.client_id)
        renomme = self.api.patch(url_detail(cree.pk), {'titre': 'Encore'},
                                 format='json')
        self.assertEqual(renomme.status_code, 200, renomme.data)

    def test_patch_nom_lecture_seule_400(self):
        calepinage = creer_pour_lead(self.lead_client.pk, self.company,
                                     user=self.user, titre='Avant')
        reponse = self.api.patch(url_detail(calepinage.pk),
                                 {'nom': 'QA-CAL-RT'}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('nom', reponse.data)
        self.assertIn('titre', str(reponse.data['nom']))
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.titre, 'Avant')

    def test_cle_inconnue_ou_en_lecture_seule_nommee(self):
        calepinage = creer_pour_lead(self.lead_client.pk, self.company,
                                     user=self.user, titre='Avant')
        for cle, valeur in (('layout_hash', 'x' * 64), ('inconnue', 1)):
            with self.subTest(cle=cle):
                reponse = self.api.patch(url_detail(calepinage.pk),
                                         {'titre': 'Après', cle: valeur},
                                         format='json')
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertIn(cle, reponse.data)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.titre, 'Avant')
