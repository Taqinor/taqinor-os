"""CADX (fondateur 15/09/2026) — « jamais deux cadences en parallèle ».

La garde vit dans ``services.initialiser_plan_relance`` : démarrer une
cadence PLUS prioritaire (après-devis > contact > générique > réveil)
REMPLACE l'active (annulée moteur, motif tracé) ; une cadence de priorité
inférieure ou égale est REFUSÉE (``CadenceActiveConflit``) — c'est ce refus
qui neutralise le job du 11/09 (placement « contact » par-dessus un
après-devis actif, lead #348). La migration crm/0102 nettoie l'existant.
"""
import datetime
from importlib import import_module

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm import services
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from authentication.models import Company

User = get_user_model()

MIGRATION = import_module(
    'apps.crm.migrations.0102_cadx_une_seule_cadence_active')


def _touche(lead, cadence, ordre=1, libelle='Touche', jours=0):
    due = timezone.now() + datetime.timedelta(days=jours)
    return RelanceEtape.objects.create(
        company=lead.company, lead=lead, cadence=cadence, ordre=ordre,
        canal=RelanceEtape.Canal.APPEL, libelle=libelle,
        due_at=due, due_date=due.date())


class CadxBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CADX', slug='cadx-a')
        self.user = User.objects.create_user(
            username='cadx-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Client CADX', owner=self.user,
            telephone='+212661000000')


class GardeCadenceUniqueTests(CadxBase):

    def test_contact_refuse_quand_apres_devis_actif(self):
        # Le scénario EXACT du lead #348 : après-devis en cours, un job
        # (re)lance « contact » → REFUS, et le plan après-devis est INTACT.
        etape = _touche(self.lead, 'apres_devis', ordre=7,
                        libelle='Validité de la proposition', jours=1)
        with self.assertRaises(services.CadenceActiveConflit):
            services.initialiser_plan_relance(
                self.lead, self.user, cadence='contact')
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertFalse(self.lead.relance_etapes
                         .filter(cadence='contact').exists())

    def test_apres_devis_remplace_un_contact_actif(self):
        # Sens INVERSE (devis envoyé pendant une prise de contact) : la
        # cadence prioritaire remplace — contact ANNULÉ moteur, motif tracé.
        contact = _touche(self.lead, 'contact', ordre=3,
                          libelle='Appel 2 (répondeur)')
        etapes = services.initialiser_plan_relance(
            self.lead, self.user, cadence='apres_devis',
            depart=timezone.now())
        self.assertTrue(etapes)
        contact.refresh_from_db()
        self.assertEqual(contact.statut, RelanceEtape.Statut.ANNULEE)
        self.assertIsNone(contact.traite_par)
        self.assertIn('remplacée par la cadence « apres_devis »',
                      contact.note)

    def test_reveil_refuse_sous_toute_cadence_active(self):
        _touche(self.lead, 'contact')
        with self.assertRaises(services.CadenceActiveConflit):
            services.initialiser_plan_relance(
                self.lead, self.user, cadence='reveil')

    def test_meme_cadence_reste_idempotente_jamais_un_conflit(self):
        premieres = services.initialiser_plan_relance(
            self.lead, self.user, cadence='contact', depart=timezone.now())
        self.assertTrue(premieres)
        secondes = services.initialiser_plan_relance(
            self.lead, self.user, cadence='contact', depart=timezone.now())
        self.assertEqual([e.pk for e in secondes],
                         [e.pk for e in premieres])

    def test_demarrer_cadence_contact_trace_le_refus_au_chatter(self):
        _touche(self.lead, 'apres_devis', ordre=7, jours=1)
        resultat = services.demarrer_cadence_contact(
            self.lead, user=self.user, origine='test-cadx')
        self.assertEqual(resultat, [])
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead,
            body__icontains='Une seule cadence à la fois').exists())

    def test_le_refus_de_la_vue_nomme_le_champ(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        _touche(self.lead, 'apres_devis', ordre=7, jours=1)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        reponse = api.post(
            f'/api/django/crm/leads/{self.lead.id}/relance/initialiser/',
            {'cadence': 'contact'}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('cadence', reponse.data.get('erreurs', {}))


class MigrationNettoyageTests(CadxBase):

    def test_garde_la_plus_prioritaire_et_annule_le_reste(self):
        _touche(self.lead, 'contact', ordre=3, libelle='Appel 2 (répondeur)')
        garde = _touche(self.lead, 'apres_devis', ordre=7,
                        libelle='Validité de la proposition', jours=1)
        MIGRATION._annuler_doublons(django_apps, None)
        garde.refresh_from_db()
        self.assertEqual(garde.statut, RelanceEtape.Statut.A_FAIRE)
        annulee = self.lead.relance_etapes.get(cadence='contact')
        self.assertEqual(annulee.statut, RelanceEtape.Statut.ANNULEE)
        self.assertIn('CADX', annulee.note)
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, body__icontains='Nettoyage CADX').exists())

    def test_idempotente_et_muette_sans_doublon(self):
        _touche(self.lead, 'apres_devis', ordre=7, jours=1)
        MIGRATION._annuler_doublons(django_apps, None)
        MIGRATION._annuler_doublons(django_apps, None)
        self.assertEqual(
            self.lead.relance_etapes.filter(
                statut=RelanceEtape.Statut.ANNULEE).count(), 0)
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, body__icontains='Nettoyage CADX').exists())


class FiletGeneriqueSansIssueTests(CadxBase):
    """Capture fondateur du 15/09 : « Fait — passer à la suite » sur un filet
    générique (canal appel) partait sans issue et se heurtait au mur CKP2
    « issue obligatoire » — que l'écran ne propose volontairement pas sur les
    filets. La garde exempte désormais la cadence « generique » ; les appels
    du PROTOCOLE (contact/après-devis) gardent l'issue obligatoire."""

    def _api(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        return api

    def test_fait_sans_issue_passe_sur_un_filet_generique(self):
        filet = _touche(self.lead, 'generique', ordre=1,
                        libelle=services.FILET_JOINT_LIBELLE)
        reponse = self._api().post(
            f'/api/django/crm/relance-etapes/{filet.id}/fait/', {},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        filet.refresh_from_db()
        self.assertEqual(filet.statut, RelanceEtape.Statut.FAIT)

    def test_un_appel_du_protocole_exige_toujours_son_issue(self):
        appel = _touche(self.lead, 'contact', ordre=2,
                        libelle='Appel de suivi')
        reponse = self._api().post(
            f'/api/django/crm/relance-etapes/{appel.id}/fait/', {},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('outcome', reponse.data.get('erreurs', {}))


class TreadmillTests(CadxBase):
    """TREADMILL-1538 (fondateur 15/09, « stuck at this step over and over ») :
    l'idempotence de plan porte sur les touches OUVERTES seulement, le cas AR
    sans devis ERP démarre le suivi de proposition, la matérialisation se
    borne à la génération (ancre), et la ceinture interdit de re-poser à
    l'identique la touche qu'on vient de clore."""

    def _devis(self, statut='brouillon', date_envoi=None):
        from decimal import Decimal

        from apps.ventes.models import Devis
        from apps.crm.models import Client
        client = Client.objects.create(
            company=self.company, nom='Client CADX',
            email='cadx@example.com')
        return Devis.objects.create(
            company=self.company, reference='DEV-CADX-0001', client=client,
            lead=self.lead, statut=statut, taux_tva=Decimal('20.00'),
            date_envoi=date_envoi)

    def _filet_envoi(self):
        return RelanceEtape.objects.create(
            company=self.lead.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL,
            libelle=services.FILET_JOINT_LIBELLE,
            due_at=timezone.now(), due_date=timezone.now().date())

    def test_relancer_apres_arret_cree_un_nouveau_plan(self):
        # La recette du 08/09 (« Arrêter la cadence » puis « Relancer »)
        # butait sur l'idempotence-historique : réparée.
        services.initialiser_plan_relance(
            self.lead, self.user, cadence='contact', depart=timezone.now())
        services.arreter_cadence(self.lead, user=self.user, motif='test')
        self.assertEqual(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).count(), 0)
        relance = services.initialiser_plan_relance(
            self.lead, self.user, cadence='contact', depart=timezone.now())
        self.assertTrue(any(
            e.statut == RelanceEtape.Statut.A_FAIRE for e in relance))

    def test_scenario_1538_fait_sur_filet_demarre_puis_redemarre(self):
        # Rejeu du lead TEST-16 : AR (devis brouillon) → plan démarré ;
        # « client a répondu » → plan arrêté ; ENVOI RÉEL du devis → le plan
        # REDÉMARRE (l'historique clos ne le bloque plus) — et plus jamais un
        # filet identique re-posé.
        devis = self._devis(statut='brouillon')
        filet = self._filet_envoi()
        services.marquer_etape_relance(
            filet, self.user, RelanceEtape.Statut.FAIT)
        ouvertes = self.lead.relance_etapes.filter(
            cadence='apres_devis', statut=RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(ouvertes.count(), 1)
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='generique', libelle=services.FILET_JOINT_LIBELLE,
            statut=RelanceEtape.Statut.A_FAIRE).exists())
        # Le client répond → le moteur annule le plan (équivalent MRY9).
        services.arreter_cadence(self.lead, user=self.user, motif='joint',
                                 cadences=['apres_devis', 'generique'])
        # ENVOI réel du devis (ce que fait le récepteur devis_sent) :
        relance = services.initialiser_plan_relance(
            self.lead, self.user, cadence='apres_devis',
            depart=timezone.now(), devis=devis)
        self.assertTrue(any(
            e.statut == RelanceEtape.Statut.A_FAIRE for e in relance),
            'l’historique clos ne doit jamais bloquer le redémarrage')

    def test_ar_sans_devis_demarre_le_plan_sans_objet_devis(self):
        filet = self._filet_envoi()
        services.marquer_etape_relance(
            filet, self.user, RelanceEtape.Statut.FAIT)
        ouvertes = self.lead.relance_etapes.filter(
            cadence='apres_devis', statut=RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(ouvertes.count(), 1)
        self.assertIsNone(ouvertes.get().devis_id)
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='generique', libelle=services.FILET_JOINT_LIBELLE,
            statut=RelanceEtape.Statut.A_FAIRE).exists())

    def test_ceinture_jamais_le_meme_libelle_repose(self):
        etape = services.assurer_prochaine_etape_apres_succes(
            self.lead, self.user, avec_plan_devis=False,
            libelle_touche_close=services.FILET_JOINT_LIBELLE)
        self.assertIsNotNone(etape)
        self.assertEqual(etape.libelle, services.FILET_REFUS_LIBELLE)

    def test_un_plan_redemarre_fait_naitre_ses_propres_barreaux(self):
        # Génération (ancre) : les ordres consommés par l'ANCIEN plan clos ne
        # doivent pas étouffer la naissance des barreaux du nouveau.
        services.initialiser_plan_relance(
            self.lead, self.user, cadence='contact', depart=timezone.now())
        services.arreter_cadence(self.lead, user=self.user, motif='test')
        relance = services.initialiser_plan_relance(
            self.lead, self.user, cadence='contact', depart=timezone.now())
        premiere = next(e for e in relance
                        if e.statut == RelanceEtape.Statut.A_FAIRE)
        services.marquer_etape_relance(
            premiere, self.user, RelanceEtape.Statut.FAIT,
            outcome='non_joint')
        suivantes = self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE,
            cadence_depart=premiere.cadence_depart)
        self.assertTrue(suivantes.exists(),
                        'le barreau suivant du plan redémarré doit naître')
