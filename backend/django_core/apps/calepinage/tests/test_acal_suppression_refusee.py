"""ACAL120 (C-ACAL-098) — ``DELETE`` et ``PUT`` sur ``calepinages/<pk>/``
répondent 405 (« archivez le calepinage ») : archiver est l'unique geste ;
``permissions.peut_supprimer`` du détail suit le prédicat d'archivage.

HTTP réel, services réels ; rien n'est mocké.

Run :
    python manage.py test apps.calepinage.tests.test_acal_suppression_refusee -v2
"""
from apps.calepinage.models import (
    Calepinage, CalepinageVariante, CalepinageVersion,
)
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.variantes import creer_variante
from apps.trash.selectors import ids_dans_corbeille
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail


def _document(modules):
    return {'version': 2, 'zones': [{'id': 'z1', 'label': 'Pan Sud',
                                     'geometry': {'count': modules}}]}


class SuppressionRefuseeTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-ACAL120-1', statut=Devis.Statut.BROUILLON)
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='QA-ACAL 120')
        for modules in (4, 6, 8):
            enregistrer_layout(self.calepinage, _document(modules),
                               user=self.user)
        creer_variante(self.calepinage, nom='Variante B',
                       roof_layout=_document(10))
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            devis=self.devis)
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.ENVOYE)
        self.versions = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()
        self.assertEqual(self.versions, 3)

    def _intact(self):
        self.assertTrue(
            Calepinage.objects.filter(pk=self.calepinage.pk).exists())
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count(), self.versions)
        self.assertEqual(CalepinageVariante.objects.filter(
            calepinage=self.calepinage).count(), 1)
        self.assertNotIn(self.calepinage.pk,
                         list(ids_dans_corbeille('calepinage.calepinage')))
        self.assertEqual(
            self.api.get(url_detail(self.calepinage.pk)).status_code, 200)

    def test_delete_405_rien_detruit(self):
        reponse = self.api.delete(url_detail(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 405, reponse.data)
        self.assertIn('archivez le calepinage', reponse.data['detail'])
        self._intact()

    def test_put_405(self):
        reponse = self.api.put(url_detail(self.calepinage.pk),
                               {'titre': 'Remplacé', 'client':
                                self.client_a.pk}, format='json')
        self.assertEqual(reponse.status_code, 405, reponse.data)
        self.assertIn('archivez le calepinage', reponse.data['detail'])
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.titre, 'QA-ACAL 120')
        self._intact()
        # Le renommage reste servi par PATCH (R3).
        reponse = self.api.patch(url_detail(self.calepinage.pk),
                                 {'titre': 'Renommé'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def test_peut_supprimer_suit_l_archivage(self):
        # Lié à un devis ENVOYÉ : archiver refuse ⇒ peut_supprimer faux.
        detail = self.api.get(url_detail(self.calepinage.pk)).data
        self.assertFalse(detail['permissions']['peut_supprimer'])
        refus = self.api.post(f'{url_detail(self.calepinage.pk)}archiver/')
        self.assertEqual(refus.status_code, 400, refus.data)

        # Devis repassé en BROUILLON : archiver accepte ⇒ peut_supprimer vrai.
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.BROUILLON)
        detail = self.api.get(url_detail(self.calepinage.pk)).data
        self.assertTrue(detail['permissions']['peut_supprimer'])

        # Sans calepinage_gerer : jamais.
        detail = self.api_sans.get(url_detail(self.calepinage.pk))
        if detail.status_code == 200:
            self.assertFalse(detail.data['permissions']['peut_supprimer'])
