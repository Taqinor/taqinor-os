"""ACAL92 (D-ACAL-3, C-ACAL-115) — à la révision, le calepinage est RE-LIÉ à
la V2 (même conception, variantes, versions) ; la V1 garde une version
FIGÉE « Version envoyée » ; plus de second calepinage à la première
sauvegarde de la V2.

Le service réel ``ventes.domain.revision.reviser_devis`` émet
``core.events.devis_revise`` après le commit (rappels exécutés) ; l'abonné
réel du calepinage re-lie. Rien n'est mocké.

Run :
    python manage.py test apps.calepinage.tests.test_acal_reviser_relie -v2
"""
import copy
from decimal import Decimal

from django.utils import timezone

from apps.calepinage import selectors
from apps.calepinage.models import (
    Calepinage, CalepinageVariante, CalepinageVersion,
)
from apps.calepinage.receivers import LIBELLE_VERSION_ENVOYEE
from apps.calepinage.services.creation import adopter_ou_creer_pour_devis
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis
from core.events import layout_finalise

from .test_api_liste import BaseApiCalepinage

MOIS = timezone.now().strftime('%Y%m')

DOCUMENT = {'version': 2, 'pin': {'lat': 33.5731, 'lng': -7.5898},
            'zones': [{'id': 'z1', 'label': 'Pan Sud',
                       'geometry': {'count': 12, 'azimuthDeg': 180.0,
                                    'tiltDeg': 15.0}}]}
PERTES = [{'poste': 'iam', 'libelle': 'IAM', 'pct': 3.0, 'source': None,
           'reference': '', 'mensuel': None}]
RESULTAT = {'entree_electrique': {'dc_m': 30}}


class ReviserRelieTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.v1 = Devis.objects.create(
            company=self.company, reference=f'DEV-{MOIS}-0921',
            client=self.client_a, lead=self.lead,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            mode_installation='residentiel',
            roof_layout=copy.deepcopy(DOCUMENT))
        self.c = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, client=self.client_a,
            devis=self.v1, titre='QA-ACAL révision',
            roof_layout=copy.deepcopy(DOCUMENT), layout_hash='d' * 64,
            pertes=copy.deepcopy(PERTES), resultat=copy.deepcopy(RESULTAT))
        self.variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.c, nom='Retenue',
            roof_layout=copy.deepcopy(DOCUMENT), retenue=True)

    def _reviser(self):
        with self.captureOnCommitCallbacks(execute=True):
            return reviser_devis(self.v1, user=self.user)

    def test_reviser_relie_calepinage_a_v2_avec_variantes(self):
        v2 = self._reviser()
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, v2.pk)
        self.assertEqual(selectors.calepinage_du_devis(v2.pk, self.company),
                         self.c)
        variantes = CalepinageVariante.objects.filter(calepinage=self.c)
        self.assertEqual(list(variantes.values_list('pk', 'retenue')),
                         [(self.variante.pk, True)])
        self.assertEqual(self.c.pertes, PERTES)
        self.assertEqual(self.c.resultat, RESULTAT)
        self.assertEqual(self.c.roof_layout, DOCUMENT)
        # Un seul calepinage ouvert pour le lead.
        self.assertEqual(len(selectors.calepinages_ouverts_du_lead(
            self.company, self.lead.pk)), 1)
        # Règle #4 : aucun statut de devis écrit.
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.statut, Devis.Statut.ENVOYE)

    def test_sauvegarde_v2_ne_cree_pas_second_calepinage(self):
        v2 = self._reviser()
        avant = Calepinage.objects.filter(company=self.company).count()
        # La première sauvegarde de la conception de la V2 (layout_finalise,
        # ACAL38) ADOPTE le calepinage re-lié, n'en crée aucun.
        v2.refresh_from_db()
        layout_finalise.send(sender=Devis, devis=v2, user=self.user)
        self.assertEqual(
            Calepinage.objects.filter(company=self.company).count(), avant)
        calepinage, origine = adopter_ou_creer_pour_devis(
            v2.pk, self.company, user=self.user)
        self.assertEqual(calepinage, self.c)
        self.assertEqual(origine, 'existant')
        self.assertEqual(
            Calepinage.objects.filter(lead_id=self.lead.pk).count(), 1)

    def test_version_envoyee_figee(self):
        self._reviser()
        libelle = LIBELLE_VERSION_ENVOYEE.format(reference=self.v1.reference)
        versions = CalepinageVersion.objects.filter(calepinage=self.c,
                                                    libelle=libelle)
        self.assertEqual(versions.count(), 1)
        figee = versions.get()
        self.assertEqual(figee.roof_layout, DOCUMENT)
        self.assertIsNone(figee.resultat)

    def test_calepinage_du_devis_v1_suit_la_chaine(self):
        v2 = self._reviser()
        self.assertEqual(
            selectors.calepinage_du_devis(self.v1.pk, self.company), self.c)
        # Une révision de plus : V1 → V2 → V3, toujours le même.
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ENVOYE)
        v2.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            v3 = reviser_devis(v2, user=self.user)
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, v3.pk)
        for devis in (self.v1, v2, v3):
            with self.subTest(devis=devis.reference):
                self.assertEqual(selectors.calepinage_du_devis(
                    devis.pk, self.company), self.c)
        # Jamais dans une autre société.
        self.assertIsNone(
            selectors.calepinage_du_devis(self.v1.pk, self.autre))
