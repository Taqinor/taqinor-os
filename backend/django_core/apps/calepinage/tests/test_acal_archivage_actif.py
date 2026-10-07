"""ACAL118 (C-ACAL-099) — l'archivage porté par le MODÈLE (survit à la purge
de la corbeille), un seul sélecteur « actifs », refus d'archiver un
calepinage qui porte un devis non brouillon.

Services et HTTP réels ; la purge est celle d'``apps.trash`` ; rien n'est
mocké.

Run :
    python manage.py test apps.calepinage.tests.test_acal_archivage_actif -v2
"""
import datetime

from django.utils import timezone

from apps.calepinage import selectors
from apps.calepinage.models import Calepinage
from apps.calepinage.services.archivage import (
    MESSAGE_ARCHIVE, archiver, est_archive,
)
from apps.calepinage.services.comparaison_projets import (
    MOTIF_ARCHIVE, comparer_calepinages,
)
from apps.calepinage.services.creation import (
    demarrer_depuis_modele, obtenir_ou_creer_pour_devis,
)
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.modeles import (
    ModeleInvalide, calepinages_modeles, creer_depuis_modele, marquer_modele,
)
from apps.calepinage.services.verrou import VerrouilleRefuse
from apps.trash.services import purger_expires
from apps.ventes.models import Devis

from .test_api_liste import URL, BaseApiCalepinage

DOCUMENT = {'version': 2, 'pin': {'lat': 33.57, 'lng': -7.59},
            'zones': [{'id': 'z1', 'label': 'Pan Sud',
                       'geometry': {'count': 8}}]}


class ArchivageActifTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL',
            roof_layout=dict(DOCUMENT), layout_hash='a' * 64)

    def _devis(self, statut, reference):
        return Devis.objects.create(
            company=self.company, client=self.client_a, reference=reference,
            statut=statut)

    def _archiver_http(self, calepinage):
        return self.api.post(f'{URL}{calepinage.pk}/archiver/')

    def _ids_liste(self):
        reponse = self.api.get(URL)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = reponse.data
        if isinstance(lignes, dict):
            lignes = lignes.get('results', [])
        return {ligne['id'] for ligne in lignes}

    def test_archive_survit_a_la_purge(self):
        marquer_modele(self.calepinage, user=self.user)
        reponse = self._archiver_http(self.calepinage)
        self.assertEqual(reponse.status_code, 200, reponse.data)

        purger_expires(now=timezone.now() + datetime.timedelta(days=31))

        self.calepinage.refresh_from_db()
        self.assertTrue(est_archive(self.calepinage))
        self.assertNotIn(self.calepinage.pk, self._ids_liste())
        # ACAL119 (D-ACAL-25) — le détail d'un archivé de SA société reste
        # LISIBLE (jamais 404) ; seule la liste l'écarte.
        self.assertEqual(
            self.api.get(f'{URL}{self.calepinage.pk}/').status_code, 200)
        self.assertIsNone(
            selectors.calepinage_ouvert_du_lead(self.company, self.lead.pk))
        self.assertNotIn(self.calepinage.pk, list(
            calepinages_modeles(self.company).values_list('pk', flat=True)))
        self.assertNotIn(self.calepinage.pk, list(
            selectors.calepinages_actifs(self.company)
            .values_list('pk', flat=True)))
        comparatif = comparer_calepinages(self.user, [self.calepinage.pk])
        self.assertEqual(comparatif['lignes'], [])
        self.assertEqual(comparatif['refus'],
                         [{'id': self.calepinage.pk, 'motif': MOTIF_ARCHIVE}])
        # depuis-lead ne ressuscite pas l'archivé : il en crée un neuf.
        reponse = self.api.post(f'{URL}depuis-lead/', {'lead': self.lead.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertNotEqual(reponse.data['calepinage'], self.calepinage.pk)

    def test_archiver_lie_a_un_envoye_refuse(self):
        for statut, reference in ((Devis.Statut.ENVOYE, 'DEV-ACAL118-E'),
                                  (Devis.Statut.ACCEPTE, 'DEV-ACAL118-A')):
            with self.subTest(statut=statut):
                devis = self._devis(statut, reference)
                calepinage = Calepinage.objects.create(
                    company=self.company, client=self.client_a, devis=devis,
                    titre=f'Lié {statut}')
                reponse = self._archiver_http(calepinage)
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertEqual(
                    reponse.data,
                    {'devis': (f'Ce calepinage porte le devis {reference} '
                               f'({devis.get_statut_display()}) : '
                               "détachez-le d'abord")})
                calepinage.refresh_from_db()
                self.assertFalse(est_archive(calepinage))
                self.assertEqual(calepinage.devis_id, devis.pk)
                self.assertEqual(
                    selectors.calepinage_du_devis(devis.pk, self.company),
                    calepinage)
                devis.refresh_from_db()
                self.assertEqual(devis.statut, statut)

    def test_archiver_brouillon_detache(self):
        devis = self._devis(Devis.Statut.BROUILLON, 'DEV-ACAL118-B')
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=devis,
            titre='Lié brouillon')

        reponse = self._archiver_http(calepinage)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        calepinage.refresh_from_db()
        self.assertTrue(est_archive(calepinage))
        self.assertIsNone(calepinage.devis_id)
        self.assertIsNone(
            selectors.calepinage_du_devis(devis.pk, self.company))

        # Restaurer : le devis, toujours libre, est rattaché.
        reponse = self.api.post(f'{URL}{calepinage.pk}/restaurer-corbeille/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        calepinage.refresh_from_db()
        self.assertFalse(est_archive(calepinage))
        self.assertEqual(calepinage.devis_id, devis.pk)
        self.assertEqual(self.api.get(f'{URL}{calepinage.pk}/').status_code,
                         200)

        # Ré-archiver, puis le devis reçoit un calepinage VIVANT : la
        # restauration le laisse alors détaché (le devis n'est plus libre).
        archiver(calepinage, user=self.user)
        vivant, cree = obtenir_ou_creer_pour_devis(devis.pk, self.company,
                                                   user=self.user)
        self.assertTrue(cree)
        self.assertNotEqual(vivant.pk, calepinage.pk)
        self.assertFalse(est_archive(vivant))
        self.api.post(f'{URL}{calepinage.pk}/restaurer-corbeille/')
        calepinage.refresh_from_db()
        self.assertFalse(est_archive(calepinage))
        self.assertIsNone(calepinage.devis_id)
        self.assertEqual(
            selectors.calepinage_du_devis(devis.pk, self.company), vivant)

    def test_ecrire_sur_archive_refuse(self):
        archiver(self.calepinage, user=self.user)
        self.calepinage.refresh_from_db()
        autre = dict(DOCUMENT, zones=[{'id': 'z9', 'label': 'Nord',
                                       'geometry': {'count': 2}}])
        with self.assertRaises(VerrouilleRefuse) as refus:
            enregistrer_layout(self.calepinage, autre, user=self.user)
        self.assertEqual(refus.exception.status_code, 409)
        self.assertEqual(refus.exception.detail,
                         {'calepinage': [MESSAGE_ARCHIVE]})
        self.assertIn('Calepinage archivé : restaurez-le', MESSAGE_ARCHIVE)
        relu = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertEqual(relu.roof_layout, DOCUMENT)

    def test_modele_archive_refuse(self):
        marquer_modele(self.calepinage, user=self.user)
        archiver(self.calepinage, user=self.user)
        self.calepinage.refresh_from_db()
        avant = Calepinage.objects.count()
        with self.assertRaises(ModeleInvalide) as refus:
            creer_depuis_modele(self.calepinage, user=self.user,
                                client_id=self.client_a.pk)
        self.assertEqual(refus.exception.champ, 'modele')
        with self.assertRaises(ModeleInvalide) as refus:
            demarrer_depuis_modele(self.calepinage, self.company,
                                   user=self.user,
                                   client_id=self.client_a.pk)
        self.assertEqual(refus.exception.champ, 'modele')
        self.assertEqual(Calepinage.objects.count(), avant)
