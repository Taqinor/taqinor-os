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

    def test_service_relier_au_devis_revise_idempotent(self):
        """R6-N1 (suite) — LE service (appelé par l'abonné ET par ventes) :
        un second appel n'écrit rien, une seule version figée."""
        from apps.calepinage.services.liens import relier_au_devis_revise

        v2 = reviser_devis(self.v1, user=self.user)  # rappels non rejoués
        self.assertEqual(relier_au_devis_revise(self.v1, v2, user=self.user),
                         self.c)
        self.assertIsNone(relier_au_devis_revise(self.v1, v2, user=self.user))
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, v2.pk)
        libelle = LIBELLE_VERSION_ENVOYEE.format(reference=self.v1.reference)
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=self.c, libelle=libelle).count(), 1)

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


class EtudesDeLaV2SuiventLeCalepinageTest(BaseApiCalepinage):
    """R6-N1 — les études de la V2 voient le calepinage qu'elle porte.

    Calepinage RÉEL simulé (client météo rejoué, fiches matériel injectées,
    accès solaire 0,9 par module : perte d'ombrage MESURÉE), lié à la V1
    envoyée. La perte attendue est celle que ``ombrage_servi`` sert à la V1
    AVANT la révision ; l'espion n'enveloppe que le calcul des études et y lit
    la VRAIE ``perte_ombrage_du_devis`` (l'entrée que le moteur horaire et le
    balayage reçoivent, ``domain.entrees``). ROUGE AVANT : un seul calcul, dans
    le clonage, avant la re-liaison — perte ``None``."""

    def setUp(self):
        super().setUp()
        from unittest import mock

        from apps.calepinage.services.simulation import simuler_calepinage

        from .acal_livrables_helpers import patch_materiel
        from .test_acal_multi_pans import _ClientParOrientation, _layout, _zone
        from .test_calx5_simulation import MATERIEL

        # Les deux lecteurs réseau des études rejoués, comme ACAL144
        # (``ventes.tests.test_acal_ombrage_etude_devis``).
        from apps.ventes.tests.test_acal_ombrage_etude_devis import (
            _fake_productible, _fake_tmy)
        for cible, faux in (
                ('apps.ventes.weather_feed.fetch_irradiance_tmy', _fake_tmy),
                ('apps.parametres.pvgis.fetch_productible', _fake_productible)):
            patch = mock.patch(cible, side_effect=faux)
            patch.start()
            self.addCleanup(patch.stop)
        self.materiel = patch_materiel
        self.v1 = Devis.objects.create(
            company=self.company, reference=f'DEV-{MOIS}-0931',
            client=self.client_a, lead=self.lead,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        layout = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
        for zone in layout['zones']:
            zone['geometry']['solarAccess'] = {
                'values': [0.9] * zone['geometry']['count'],
                'method': {'horizon': False, 'rangees': False,
                           'resolution': 'annuelle',
                           'description': 'Accès solaire annuel'},
                'assumptions': {'periode': 'annee'},
                'computedAt': '2026-10-01T10:00:00Z'}
        self.c = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, client=self.client_a,
            devis=self.v1, titre='R6-N1 révision', roof_layout=layout)
        # Le profil de la société EXISTE avant le calcul, comme pour une
        # société en service. Sans lui, la simulation est faite sans fuseau
        # (``site._fuseau_du_profil`` → ``None``) ; puis l'acceptation crée la
        # ligne (abonné chantier → ``installations.services.default_installer_for``
        # → ``CompanyProfile.get``, fuseau par défaut « Africa/Casablanca ») :
        # le fuseau du site change, l'empreinte de simulation aussi, et la
        # péremption est VRAIE (les blocs horaires dépendent du fuseau).
        from apps.parametres.models_company import CompanyProfile
        CompanyProfile.objects.create(company=self.company,
                                      nom=self.company.nom,
                                      fuseau_horaire='Africa/Casablanca')
        with patch_materiel():
            simuler_calepinage(self.c, client=_ClientParOrientation(),
                               materiel=MATERIEL, enregistrer=True)
            servi = selectors.ombrage_servi(self.v1.pk, self.company)
        Devis.objects.filter(pk=self.v1.pk).update(
            statut=Devis.Statut.ENVOYE, date_envoi=timezone.now())
        self.v1.refresh_from_db()
        self.assertFalse(servi['perime'])
        self.assertIsNotNone(servi['global'])
        self.assertGreater(float(servi['global']), 0.0)
        self.perte_servie = float(servi['global'])

    def _reviser(self, *, hors_transaction=False):
        from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
        from apps.ventes.tests.test_acal_devis_revise_evenement import (
            espionner_etudes, hors_transaction as forcer_hors_transaction)

        journal = []
        espionner_etudes(self, journal, mesure=perte_ombrage_du_devis)
        if hors_transaction:
            forcer_hors_transaction(self)
        with self.materiel(), self.captureOnCommitCallbacks(execute=True):
            v2 = reviser_devis(self.v1, user=self.user)
        return v2, [appel for appel in journal if appel[1] == v2.pk]

    def test_accepter_sans_profil_ne_perime_pas_la_simulation(self):
        """Profil société — accepter le devis d'une société SANS profil ne
        crée plus le profil (``CompanyProfile.get`` dans l'aval : chantier,
        acompte, O&M) : son fuseau par défaut entrait dans l'empreinte de
        simulation (``site.fuseau_du_site``) et périmait le calepinage.
        Chaîne réelle : ``accept_devis`` + rappels du commit exécutés.
        ``build_quote_data`` (détection des options, lu à CHAQUE acceptation :
        langue, délais, validité) n'est PAS bouchonné. Seul le stockage de
        l'exemplaire signé l'est (MinIO, WeasyPrint) : ses lecteurs du profil
        (moteur + ``utils/pdf._company_context``) sont tenus sans base par
        ``apps.ventes.tests.test_profil_lecture_moteur``."""
        from datetime import date
        from unittest import mock

        from apps.calepinage.services.electrique import (
            conception_du_calepinage, parametres_societe,
        )
        from apps.calepinage.services.simulation import empreinte_simulation
        from apps.calepinage.services.site import fuseau_du_site
        from apps.parametres.models import CompanyProfile
        from apps.ventes.domain.cycle_vie import accept_devis
        from apps.ventes.models import LigneDevis
        from apps.ventes.tests._quote_engine_common import make_produit

        CompanyProfile.objects.filter(company=self.company).delete()

        def empreinte():
            calepinage = Calepinage.objects.get(pk=self.c.pk)
            with self.materiel():
                _, materiel, donnees, document = conception_du_calepinage(
                    calepinage)
                return empreinte_simulation(
                    calepinage, document=document, donnees=donnees,
                    materiel=materiel,
                    reglages=parametres_societe(calepinage))

        avant = empreinte()
        LigneDevis.objects.create(
            devis=self.v1, designation='Panneaux', quantite=Decimal('1'),
            produit=make_produit(self.company, 'Panneaux', 'PSL-1',
                                 '9600.00'),
            prix_unitaire=Decimal('9600.00'), remise=Decimal('0'),
            taux_tva=Decimal('10'))
        with mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails'), \
                mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'), \
                self.materiel(), \
                self.captureOnCommitCallbacks(execute=True):
            accept_devis(devis=Devis.objects.get(pk=self.v1.pk),
                         user=self.user, nom='Client sans profil',
                         date_acceptation=date.today(),
                         option='sans_batterie')
        self.assertEqual(Devis.objects.get(pk=self.v1.pk).statut,
                         Devis.Statut.ACCEPTE)
        self.assertFalse(
            CompanyProfile.objects.filter(company=self.company).exists())
        self.assertIsNone(
            fuseau_du_site({}, company=self.company)['provenance'])
        self.assertEqual(empreinte(), avant)

    def test_hors_transaction_un_calcul_avec_l_ombrage_du_calepinage(self):
        v2, appels = self._reviser(hors_transaction=True)
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, v2.pk)
        self.assertEqual(len(appels), 1, appels)
        self.assertTrue(appels[0][2])  # force
        self.assertAlmostEqual(appels[0][3], self.perte_servie, places=6)

    def test_dans_une_transaction_recalcule_apres_la_reliaison(self):
        v2, appels = self._reviser()
        self.assertEqual(len(appels), 2, appels)
        self.assertIsNone(appels[0][3])  # le clonage, avant la re-liaison
        self.assertAlmostEqual(appels[-1][3], self.perte_servie, places=6)
        # Règle #4 : la V1 n'est ni recalculée ni réécrite, son statut tient.
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.statut, Devis.Statut.ENVOYE)

    def test_reliaison_en_echec_la_v2_garde_des_etudes_sans_calepinage(self):
        """L'abonné du calepinage échoue (journalisé) : la V2 a quand même
        ses études — celles d'hier, sans calepinage — et le calepinage reste
        sur la V1. Rien n'est muet."""
        from unittest import mock

        with mock.patch('apps.calepinage.services.liens.lier_devis',
                        side_effect=RuntimeError('lien refusé')), \
                self.assertLogs('apps.calepinage.receivers', 'ERROR') as sortie:
            v2, appels = self._reviser(hors_transaction=True)
        self.assertTrue(any('ACAL92' in ligne for ligne in sortie.output))
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, self.v1.pk)
        self.assertEqual(len(appels), 1, appels)
        self.assertIsNone(appels[0][3])
        self.assertTrue(Devis.objects.filter(pk=v2.pk).exists())

    # ── R6-N1 (suite) — les trois appelants qui tiennent une transaction ──

    def _espion(self):
        from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
        from apps.ventes.tests.test_acal_devis_revise_evenement import (
            espionner_etudes)

        journal = []
        espionner_etudes(self, journal, mesure=perte_ombrage_du_devis)
        return journal

    def _versions_envoyees(self):
        return CalepinageVersion.objects.filter(
            calepinage=self.c, libelle=LIBELLE_VERSION_ENVOYEE.format(
                reference=self.v1.reference)).count()

    def test_avant_acceptation_un_calcul_relie_dans_la_transaction(self):
        """Prix négocié : AVANT le commit (là où la V2 est acceptée), le
        calepinage est déjà sur la V2 ; la révision ne calcule rien, le calcul
        de l'appelant (au prix négocié) voit l'ombrage du calepinage ; au
        commit, rien n'est refait (V2 acceptée) et une SEULE version figée
        existe. ROUGE AVANT : un calcul dans le clonage, perte ``None``, et la
        V2 acceptée le gardait."""
        from apps.ventes.domain import etudes
        from apps.ventes.domain.revision import ETUDES_AVANT_ACCEPTATION

        journal = self._espion()
        with self.materiel(), self.captureOnCommitCallbacks(execute=True):
            v2 = reviser_devis(self.v1, user=self.user,
                               etudes=ETUDES_AVANT_ACCEPTATION)
            self.c.refresh_from_db()
            self.assertEqual(self.c.devis_id, v2.pk)
            self.assertEqual([a for a in journal if a[1] == v2.pk], [])
            etudes.rafraichir_etudes_du_devis(v2, force=True)  # l'appelant
            avant = [a for a in journal if a[1] == v2.pk]
            self.assertEqual(len(avant), 1, avant)
            self.assertTrue(avant[0][2])  # force
            self.assertAlmostEqual(avant[0][3], self.perte_servie, places=6)
            # Comme ``appliquer_prix_negocie`` : acceptée avant le commit.
            Devis.objects.filter(pk=v2.pk).update(
                statut=Devis.Statut.ACCEPTE)
        self.assertEqual([a for a in journal if a[1] == v2.pk], avant)
        self.assertEqual(self._versions_envoyees(), 1)
        self.assertFalse(any(a[1] == self.v1.pk for a in journal))  # V1 jamais recalculée

    def test_prix_negocie_la_v2_acceptee_porte_l_ombrage_de_son_calepinage(self):
        """Le vrai geste « Prix négocié » (V2 créée ET acceptée en une
        transaction) sur une vente dont la V1 porte un calepinage simulé."""
        from datetime import date
        from unittest import mock

        from django.contrib.auth import get_user_model

        from apps.ventes.domain.cycle_vie import accept_devis
        from apps.ventes.domain.negociation import appliquer_prix_negocie
        from apps.ventes.models import LigneDevis
        from apps.ventes.tests._quote_engine_common import make_produit

        vendeur = get_user_model().objects.create_user(
            username='r6n1_negocie', password='x', role_legacy='responsable',
            company=self.company)
        for rang, (designation, pu, taux) in enumerate((
                ('Panneaux 10 %', '9600.00', '10'),
                ('Installation 20 %', '36643.50', '20'))):
            LigneDevis.objects.create(
                devis=self.v1, designation=designation, quantite=Decimal('1'),
                produit=make_produit(self.company, designation,
                                     f'R6N1-{rang}', pu),
                prix_unitaire=Decimal(pu), remise=Decimal('0'),
                taux_tva=Decimal(taux))
        with mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails'), \
                mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            v1 = accept_devis(devis=Devis.objects.get(pk=self.v1.pk),
                              user=vendeur, nom='Client R6-N1',
                              date_acceptation=date.today(),
                              option='sans_batterie')
            # Ce que la lecture de l'ombrage VOIT au moment du calcul (statut
            # du devis, verdict du calepinage) : dit par l'assertion plus bas,
            # au lieu d'un ``None`` sans cause.
            vu = {}

            def _mesure(d):
                from apps.calepinage import selectors as cal
                from apps.ventes.horaire.ombrage import perte_ombrage_du_devis
                from apps.ventes.selectors_calepinage import _conception_a_jour
                vu['statut'] = d.statut
                try:
                    c = cal._calepinage_lisible_pour_devis(d.pk, d.company)
                    vu['lisible'] = getattr(c, 'pk', None)
                    vu['devis_du_calepinage'] = getattr(c, 'devis_id', None)
                    if c is not None:
                        vu['conception_a_jour'] = _conception_a_jour(d, c)
                        servi = cal.resultat_servi(c)
                        vu['resultat'] = {k: servi.get(k) for k in (
                            'statut', 'simulation_perimee', 'motif')}
                    vu['ombrage_servi'] = cal.ombrage_servi(d.pk, d.company)
                except Exception as exc:  # noqa: BLE001 — diagnostic de test
                    vu['erreur'] = repr(exc)
                return perte_ombrage_du_devis(d)

            from apps.ventes.tests.test_acal_devis_revise_evenement import (
                espionner_etudes)
            journal = []
            espionner_etudes(self, journal, mesure=_mesure)
            # Sans rejouer les rappels du commit (abonnés de l'acceptation) :
            # tout ce qui est vérifié ici se joue DANS la transaction du geste.
            # Aucun échec SILENCIEUX : la re-liaison (journal ERROR de
            # ``domain.revision``) et la lecture de l'ombrage (journal WARNING
            # de ``horaire.ombrage``) avalent leurs exceptions — un rouge ici
            # nomme la cause au lieu d'un ``None`` muet plus bas.
            with self.materiel(), \
                    self.assertNoLogs('apps.ventes.domain.revision',
                                      level='ERROR'), \
                    self.assertNoLogs('apps.ventes.horaire.ombrage',
                                      level='WARNING'):
                corps = appliquer_prix_negocie(v1, user=vendeur,
                                               remise_pct='2')
        v2 = Devis.objects.get(pk=corps['devis_v2']['id'])
        self.assertEqual(v2.statut, Devis.Statut.ACCEPTE)
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, v2.pk)
        appels = [a for a in journal if a[1] == v2.pk]
        self.assertEqual(len(appels), 1, appels)
        self.assertIsNotNone(appels[0][3], vu)
        self.assertAlmostEqual(appels[0][3], self.perte_servie, places=6)
        self.assertEqual(self._versions_envoyees(), 1)

    def test_avant_acceptation_rollback_laisse_le_calepinage_sur_la_v1(self):
        from django.db import transaction

        from apps.ventes.domain.revision import ETUDES_AVANT_ACCEPTATION

        class _Annule(Exception):
            pass

        nb_devis = Devis.objects.count()
        with self.materiel(), self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(_Annule):
                with transaction.atomic():
                    reviser_devis(self.v1, user=self.user,
                                  etudes=ETUDES_AVANT_ACCEPTATION)
                    raise _Annule
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, self.v1.pk)
        self.assertEqual(self._versions_envoyees(), 0)
        self.assertEqual(Devis.objects.count(), nb_devis)
        self.v1.refresh_from_db()
        self.assertTrue(self.v1.is_active)

    def test_apres_recomposition_un_calcul_au_commit_apres_la_reliaison(self):
        """Atelier : le clonage ne calcule rien, LE calcul part au commit
        après la re-liaison (hier : clonage + commit)."""
        from apps.ventes.domain.revision import ETUDES_APRES_RECOMPOSITION

        journal = self._espion()
        with self.materiel(), self.captureOnCommitCallbacks(execute=True):
            v2 = reviser_devis(self.v1, user=self.user,
                               etudes=ETUDES_APRES_RECOMPOSITION)
            self.assertEqual([a for a in journal if a[1] == v2.pk], [])
        appels = [a for a in journal if a[1] == v2.pk]
        self.assertEqual(len(appels), 1, appels)
        self.assertTrue(appels[0][2])
        self.assertAlmostEqual(appels[0][3], self.perte_servie, places=6)
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, v2.pk)
        self.assertEqual(self._versions_envoyees(), 1)

    def test_par_l_appelant_relie_par_lui_aucun_calcul_au_commit(self):
        """Visite C&I : clonage comme hier, l'appelant re-lie à la fin de sa
        recomposition ; le commit ne refait ni lien, ni version, ni calcul."""
        from apps.ventes.domain.revision import (
            ETUDES_PAR_L_APPELANT, relier_calepinage_de_la_revision)

        journal = self._espion()
        with self.materiel(), self.captureOnCommitCallbacks(execute=True):
            v2 = reviser_devis(self.v1, user=self.user,
                               etudes=ETUDES_PAR_L_APPELANT)
            self.assertTrue(relier_calepinage_de_la_revision(
                self.v1, v2, user=self.user))
            self.assertEqual(self._versions_envoyees(), 1)
        appels = [a for a in journal if a[1] == v2.pk]
        self.assertEqual(len(appels), 1, appels)
        self.assertIsNone(appels[0][3])  # le clonage, comme hier
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, v2.pk)
        self.assertEqual(self._versions_envoyees(), 1)


class SuitLeDevisEnvoyeTest(BaseApiCalepinage):
    """ACAL1955 (D-ACAL-89) — à l'envoi d'un devis, le calepinage ouvert du lead
    resté sur un brouillon jamais envoyé le suit ; sinon rien ne bouge. Abonné
    RÉEL de ``core.events.devis_sent`` ; commande en liste et en application."""

    def setUp(self):
        super().setUp()
        self.d1 = self._devis('0951')
        self.d2 = self._devis('0961')
        self.c = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, client=self.client_a,
            devis=self.d1, titre='QA-ACAL1955', roof_layout=copy.deepcopy(DOCUMENT))

    def _devis(self, numero, statut=Devis.Statut.BROUILLON):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MOIS}-{numero}', client=self.client_a,
            lead=self.lead, statut=statut, taux_tva=Decimal('20'),
            mode_installation='residentiel')

    def _envoyer(self, devis):
        from core.events import devis_sent

        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ENVOYE, date_envoi=timezone.now())
        devis.refresh_from_db()
        return devis_sent.send(sender=Devis, devis=devis, user=self.user, ancien_statut='brouillon')

    def test_envoi_du_second_devis_auto_relie_le_calepinage(self):
        self._envoyer(self.d2)
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, self.d2.pk)
        self.assertEqual(selectors.calepinage_du_devis(self.d2.pk, self.company), self.c)
        self.assertFalse(CalepinageVariante.objects.filter(calepinage=self.c).exists())
        self.d1.refresh_from_db()
        self.assertEqual(self.d1.statut, Devis.Statut.BROUILLON)  # règle #4

    def test_deux_calepinages_ouverts_rien_ne_bouge(self):
        Calepinage.objects.create(company=self.company, lead_id=self.lead.pk,
                                  client=self.client_a, titre='QA-ACAL1955-bis')
        self._envoyer(self.d2)
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, self.d1.pk)

    def test_lie_a_un_devis_deja_envoye_rien_ne_bouge(self):
        Devis.objects.filter(pk=self.d1.pk).update(statut=Devis.Statut.ENVOYE, date_envoi=timezone.now())
        self._envoyer(self.d2)
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, self.d1.pk)

    def test_lie_a_la_revision_d_un_devis_deja_recu_rien_ne_bouge(self):
        # V1 reçue par le client puis révisée : d1 est sa V2 en brouillon, et porte le calepinage.
        v1 = self._devis('0941', statut=Devis.Statut.ENVOYE)
        Devis.objects.filter(pk=v1.pk).update(
            date_envoi=timezone.now(), superseded_by=self.d1, is_active=False)
        self._envoyer(self.d2)
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, self.d1.pk)

    def test_commande_liste_puis_applique(self):
        import io

        from django.core.management import call_command

        Devis.objects.filter(pk=self.d2.pk).update(statut=Devis.Statut.ENVOYE, date_envoi=timezone.now())
        sortie = io.StringIO()
        call_command('relier_calepinages_devis_envoye', stdout=sortie)
        self.assertIn('%s | %s | %s' % (self.c.pk, self.d1.pk, self.d2.pk), sortie.getvalue())
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, self.d1.pk)  # liste seulement
        voisine = io.StringIO()
        call_command('relier_calepinages_devis_envoye', '--company', self.autre.slug, stdout=voisine)
        self.assertIn('0 calepinage(s) à re-lier.', voisine.getvalue())
        call_command('relier_calepinages_devis_envoye', '--appliquer', stdout=io.StringIO())
        self.c.refresh_from_db()
        self.assertEqual(self.c.devis_id, self.d2.pk)
