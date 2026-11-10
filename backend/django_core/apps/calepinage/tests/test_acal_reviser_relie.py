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
from apps.calepinage.services.variantes import bascule_autorisee
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
        # ``retenue`` ne s'écrit pas directement : la bascule documentée
        # du service de variantes (même fixture que CAL245).
        with bascule_autorisee():
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

    def test_abandon_de_la_v2_relie_c_a_la_v1_au_dessin_envoye(self):
        """ACON91 — « Réviser », C retouché sur la V2 (16 modules), puis
        abandon de la V2 : C lié à la V1 au dessin envoyé (version
        « Avant restauration » + restaurée), un seul calepinage sur le lead."""
        from apps.calepinage.services.layout import enregistrer_layout
        from apps.ventes.domain.revision import abandonner_revision

        v2 = self._reviser()
        retouche = copy.deepcopy(DOCUMENT)
        retouche['zones'][0]['geometry']['count'] = 16
        self.c.refresh_from_db()
        enregistrer_layout(self.c, retouche, user=self.user)
        v2.refresh_from_db()

        reactivees = abandonner_revision(v2, self.user, retrait=True)

        self.assertEqual([v.pk for v in reactivees], [self.v1.pk])
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, self.v1.pk)
        self.assertEqual(
            self.c.roof_layout['zones'][0]['geometry']['count'], 12)
        self.assertTrue(CalepinageVersion.objects.filter(
            calepinage=self.c, libelle__startswith='Avant restauration')
            .exists())
        self.assertEqual(
            selectors.calepinage_du_devis(self.v1.pk, self.company), self.c)
        self.assertEqual(
            Calepinage.objects.filter(lead_id=self.lead.pk).count(), 1)

    def test_archivage_de_la_v2_relie_c_a_la_v1_au_dessin_envoye(self):
        """ERR-ACON-REVISION-ARCHIVEE-VERROU (ACON91, sonde C-ACON-041 (b)) —
        la VRAIE route d'archivage (PATCH ``is_active: false``) : le dessin
        est restauré AVANT que la V2 archivée le verrouille, C revient à la
        V1, et la 3D de la V1 n'ouvre aucun second calepinage."""
        from apps.calepinage.services.layout import enregistrer_layout

        v2 = self._reviser()
        retouche = copy.deepcopy(DOCUMENT)
        retouche['zones'][0]['geometry']['count'] = 16
        self.c.refresh_from_db()
        enregistrer_layout(self.c, retouche, user=self.user)

        with self.captureOnCommitCallbacks(execute=True):
            reponse = self.api.patch(f'/api/django/ventes/devis/{v2.pk}/',
                                     {'is_active': False}, format='json')
        statut = reponse.status_code
        self.assertEqual(statut, 200)

        self.c.refresh_from_db()
        v2.refresh_from_db()
        self.assertFalse(v2.is_active)
        self.assertEqual(self.c.devis_id, self.v1.pk)
        self.assertEqual(
            self.c.roof_layout['zones'][0]['geometry']['count'], 12)
        self.assertTrue(CalepinageVersion.objects.filter(
            calepinage=self.c, libelle__startswith='Avant restauration')
            .exists())
        calepinage, _origine = adopter_ou_creer_pour_devis(
            self.v1.pk, self.company, user=self.user)
        self.assertEqual(calepinage, self.c)
        self.assertEqual(
            Calepinage.objects.filter(lead_id=self.lead.pk).count(), 1)

    def test_abonne_en_echec_rend_un_resultat_nomme_et_journalise(self):
        """ERR-ACON-REVISION-ARCHIVEE-VERROU — un re-lien impossible n'est plus
        avalé en silence : l'abonné journalise et REND un résultat nommé
        (``relie: False`` + motif) ; l'abandon reste acté."""
        from unittest import mock

        from apps.calepinage.receivers import (
            relier_calepinage_a_la_version_reactivee)

        v2 = self._reviser()
        with mock.patch('apps.calepinage.services.liens.lier_devis',
                        side_effect=RuntimeError('lien refusé')), \
                self.assertLogs('apps.calepinage.receivers', 'ERROR') as journal:
            resultat = relier_calepinage_a_la_version_reactivee(
                Devis, ancien=v2, reactivees=[self.v1], user=self.user)

        self.assertEqual(resultat['relie'], False)
        self.assertEqual(resultat['calepinage'], self.c.pk)
        self.assertIn('lien refusé', resultat['motif'])
        self.assertIn('ACON91', journal.output[0])
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, v2.pk)  # savepoint annulé

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

    def test_second_devis_actif_nait_variante_de_c1(self):
        """ACON6 (D-ACON-2) — un second devis ACTIF B du lead (pas une
        révision de A) naît comme VARIANTE liée de C1 : aucun second
        calepinage ; la synchronisation de B écrit la variante, C1 et A
        restent intacts ; B supprimé ⇒ la variante garde son document."""
        from apps.calepinage.services.creation import ORIGINE_VARIANTE
        from apps.ventes.domain.resynchronisation import (
            ecrire_conception_du_devis)

        b = Devis.objects.create(
            company=self.company, reference=f'DEV-{MOIS}-0922',
            client=self.client_a, lead=self.lead,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        calepinage, origine = adopter_ou_creer_pour_devis(
            b.pk, self.company, user=self.user)
        self.assertEqual((calepinage, origine), (self.c, ORIGINE_VARIANTE))
        self.assertEqual(
            Calepinage.objects.filter(lead_id=self.lead.pk).count(), 1)
        v = CalepinageVariante.objects.get(devis=b)
        self.assertEqual((v.calepinage_id, v.nom),
                         (self.c.pk, f'Devis {b.reference}'))
        self.assertEqual(v.roof_layout, DOCUMENT)
        # Idempotent : le second geste rend le conteneur, rien de neuf.
        self.assertEqual(adopter_ou_creer_pour_devis(
            b.pk, self.company, user=self.user), (self.c, 'existant'))

        huit = copy.deepcopy(DOCUMENT)
        huit['zones'][0]['geometry']['count'] = 8
        # L'affiche CLIENT de C1 n'est jamais transmise au devis B (variante).
        from unittest import mock

        import apps.ventes.services as ventes_services
        Calepinage.objects.filter(pk=self.c.pk).update(
            roof_image='calepinages/c1/affiche.png')
        with mock.patch.object(
                ventes_services, 'resynchroniser_conception',
                wraps=ventes_services.resynchroniser_conception) as espion:
            ecrire_conception_du_devis(b, huit, user=self.user)
        self.assertEqual(espion.call_count, 1)
        self.assertIsNone(espion.call_args.kwargs['roof_image'])
        v.refresh_from_db()
        self.c.refresh_from_db()
        self.v1.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(v.roof_layout['zones'][0]['geometry']['count'], 8)
        self.assertEqual(self.c.roof_layout, DOCUMENT)
        self.assertEqual(self.v1.roof_layout, DOCUMENT)
        self.assertEqual(b.roof_layout['zones'][0]['geometry']['count'], 8)
        conception = selectors.conception_du_devis(b.pk, self.company)
        self.assertEqual(
            (conception['calepinage'], conception['variante'],
             conception['layout_hash']), (self.c, v, v.layout_hash))
        self.assertEqual(conception['roof_layout'], v.roof_layout)
        # Le contrat partagé (lu par ACON80) décrit EXACTEMENT ces clés.
        import json
        from pathlib import Path

        contrat = json.loads((Path(__file__).resolve().parents[1]
                              / 'contract_samples'
                              / 'calepinage_conception_du_devis.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(set(conception), set(contrat['exemple']))
        # A : la conception du calepinage lui-même, sans variante.
        self.assertIsNone(selectors.conception_du_devis(
            self.v1.pk, self.company)['variante'])
        self.assertEqual(self.v1.statut, Devis.Statut.ENVOYE)  # règle #4

        b.delete()
        v.refresh_from_db()
        self.assertIsNone(v.devis_id)
        self.assertEqual(v.roof_layout['zones'][0]['geometry']['count'], 8)
