"""PARAM-CADENCE — le moteur lit la chaîne de la société dans Paramètres.

Décision fondateur du 25/09/2026 : « cette cadence doit être dans Paramètres,
pour qu'une autre société ou nous puissions tout y changer ». Côté GABARIT :
``apps/parametres/tests_param_cadence_cle.py``. Ici, côté MOTEUR :

(a) une société renomme « Préparer et envoyer le devis » en « Faire le
    devis » et le passe à J+2 : le filet pose « Faire le devis » à J+2 avec
    ``cle='devis'``, et « Fait » sans issue vaut toujours « devis parti » ;
(b) barreau ``dernier_appel`` désactivé : un débrief « pas de réponse »
    retombe directement sur l'étape devis (palier SAUTÉ, jamais une boucle) ;
(c) barreau ``debrief`` supprimé : le défaut TAQINOR est posé (pilier) ;
(d) ``confirmation.delai_jours = 2`` : la confirmation tombe à J-2 de la
    visite ;
(e) une étape posée AVANT la clé (``cle`` vide, libellé par défaut) est
    reconnue ; un libellé renommé sans clé ne l'est jamais ;
(f) deux sociétés, deux réglages, aucune fuite.

Et : l'heure cible est honorée, l'escalier saute un palier désactivé, un
débrief RENOMMÉ reste une étape de visite pour le récepteur d'issue, et les
deux gabarits du moteur ne se démarrent jamais comme un plan.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import cadence_config, horaires, services, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import (
    CADENCES_DEFAUT, CADENCES_MOTEUR, Cadence, CadenceRelanceEtape,
)

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = datetime.date(2026, 9, 23)
#: Jeudi 01/10/2026 : J-2 (mardi 29/09) et J+1 (vendredi 02/10) sont ouvrés.
VISITE_LE = datetime.date(2026, 10, 1)

A_FAIRE = RelanceEtape.Statut.A_FAIRE
APPEL = RelanceEtape.Canal.APPEL


def _societe(slug):
    company = Company.objects.create(nom=f'{slug} Solaire', slug=slug)
    CompanyProfile.objects.get_or_create(company=company)
    for cadence in CADENCES_DEFAUT:
        CadenceRelanceEtape.cadence_pour(company, cadence)
    return company


def _barreau(company, cadence, cle):
    return CadenceRelanceEtape.objects.get(
        company=company, cadence=cadence, cle=cle)


class _Base(TestCase):
    slug = 'pcad-m'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _societe(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = self._lead(self.company, self.acteur)

    @staticmethod
    def _lead(company, owner, nom='Alaoui'):
        return Lead.objects.create(
            company=company, nom=nom, prenom='Fatima',
            stage=stages.CONTACTED, owner=owner, telephone='+212661000741')

    def _touche(self, *, cadence='contact', ordre=2, canal=APPEL,
                libelle="Appel d'ouverture", cle='', lead=None):
        lead = lead or self.lead
        return RelanceEtape.objects.create(
            company=lead.company, lead=lead, cadence=cadence, ordre=ordre,
            canal=canal, libelle=libelle, cle=cle, due_at=GEL,
            due_date=GEL.date(), cadence_depart=GEL)

    def _fait(self, etape, outcome=''):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': outcome}, format='json')

    def _ouvertes(self, lead=None):
        return list((lead or self.lead).relance_etapes.filter(
            statut=A_FAIRE).order_by('due_at', 'pk'))

    @staticmethod
    def _creneau(company, instant, canal=APPEL):
        return horaires.prochain_creneau_appel(instant, company, canal=canal)


class RenommerEtDecalerLeDevisTests(_Base):
    """(a) — le libellé et le délai de la société, la clé du moteur."""

    slug = 'pcad-m-a'

    def setUp(self):
        super().setUp()
        devis = _barreau(self.company, Cadence.APRES_CONTACT, 'devis')
        devis.libelle = 'Faire le devis'
        devis.delai_jours = 2
        devis.save()

    def test_le_filet_pose_l_etape_renommee_a_son_delai(self):
        resp = self._fait(self._touche(), outcome='joint')

        self.assertEqual(resp.status_code, 200, resp.data)
        [etape] = self._ouvertes()
        self.assertEqual(etape.libelle, 'Faire le devis')
        self.assertEqual(etape.cle, 'devis')
        self.assertEqual(etape.cadence, 'generique')
        attendu = self._creneau(self.company,
                                timezone.now() + datetime.timedelta(days=2))
        self.assertEqual(etape.due_at, attendu)
        self.assertEqual(etape.due_date, datetime.date(2026, 9, 25))

    def test_fait_sans_issue_vaut_toujours_devis_parti(self):
        self._fait(self._touche(), outcome='joint')
        [etape] = self._ouvertes()

        resp = self._fait(etape)

        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)
        # Le suivi de proposition démarre (devis parti hors ERP).
        self.assertTrue(self.lead.relance_etapes.filter(
            cadence='apres_devis', statut=A_FAIRE).exists())

    def test_l_heure_cible_de_la_societe_est_honoree(self):
        devis = _barreau(self.company, Cadence.APRES_CONTACT, 'devis')
        devis.heure_cible = datetime.time(10, 15)
        devis.save()

        self._fait(self._touche(), outcome='joint')

        [etape] = self._ouvertes()
        locale = etape.due_at.astimezone(horaires.CASABLANCA)
        self.assertEqual((locale.date(), locale.hour, locale.minute),
                         (datetime.date(2026, 9, 25), 10, 15))

    def test_la_piece_recue_pose_aussi_l_etape_renommee(self):
        touche = self._touche()
        _, etape_devis = services.enregistrer_piece_recue(
            touche, self.acteur, type_piece='facture')
        self.assertEqual((etape_devis.libelle, etape_devis.cle),
                         ('Faire le devis', 'devis'))


class PalierDesactiveTests(_Base):
    """(b) — un palier désactivé est SAUTÉ, jamais une boucle."""

    slug = 'pcad-m-b'

    def _desactiver(self, cle):
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.APRES_CONTACT,
            cle=cle).update(actif=False)

    def test_debrief_sans_reponse_retombe_sur_le_devis(self):
        self._desactiver('dernier_appel')
        debrief = self._touche(
            cadence='apres_devis', ordre=services.VISITE_ORDRE_DEBRIEF,
            libelle=services.VISITE_DEBRIEF_LIBELLE, cle='debrief')

        resp = self._fait(debrief, outcome='non_joint')

        self.assertEqual(resp.status_code, 200, resp.data)
        [etape] = self._ouvertes()
        self.assertEqual(etape.cle, 'devis')
        self.assertEqual(etape.libelle, services.FILET_JOINT_LIBELLE)
        self.lead.refresh_from_db()
        self.assertNotEqual(self.lead.stage, stages.COLD)

    def test_palier_actif_le_dernier_essai_est_pose(self):
        """Témoin : la même clôture, palier gardé → « dernier essai »."""
        debrief = self._touche(
            cadence='apres_devis', ordre=services.VISITE_ORDRE_DEBRIEF,
            libelle=services.VISITE_DEBRIEF_LIBELLE, cle='debrief')

        self._fait(debrief, outcome='non_joint')

        [etape] = self._ouvertes()
        self.assertEqual(etape.cle, 'dernier_appel')

    def test_message_creneau_desactive_passe_au_dernier_essai(self):
        self._desactiver('message_creneau')
        appel = self._touche(cadence='generique', ordre=1,
                             libelle=services.FILET_APPEL_LIBELLE,
                             cle='appel_apres_reponse')

        self._fait(appel, outcome='non_joint')

        [etape] = self._ouvertes()
        self.assertEqual(etape.cle, 'dernier_appel')

    def test_appel_apres_reponse_desactive_le_devis_suit_le_message(self):
        self._desactiver('appel_apres_reponse')
        message = self._touche(ordre=1, canal=RelanceEtape.Canal.WHATSAPP,
                               libelle="Message d'identité")

        self._fait(message, outcome='joint')

        [etape] = self._ouvertes()
        self.assertEqual(etape.cle, 'devis')

    def test_l_escalier_se_lit_en_cles(self):
        tous = lambda cle: True  # noqa: E731
        aucun = lambda cle: False  # noqa: E731
        self.assertEqual(services.prochain_palier_sans_reponse(
            'appel_apres_reponse', 'non_joint', tous), 'message_creneau')
        self.assertEqual(services.prochain_palier_sans_reponse(
            'appel_apres_reponse', 'non_joint', aucun), None)
        self.assertEqual(services.prochain_palier_sans_reponse(
            'devis_modifie', 'non_joint', tous), 'dernier_appel')
        self.assertIsNone(services.prochain_palier_sans_reponse(
            'dernier_appel', 'non_joint', tous))


class PilierSupprimeTests(_Base):
    """(c) — un pilier supprimé retombe sur le défaut TAQINOR."""

    slug = 'pcad-m-c'

    def test_debrief_supprime_le_defaut_est_pose(self):
        _barreau(self.company, Cadence.VISITE, 'debrief').delete()

        services.appliquer_visite_planifiee(self.lead, self.acteur, VISITE_LE)

        debrief = self.lead.relance_etapes.get(cle='debrief', statut=A_FAIRE)
        self.assertEqual(debrief.libelle, services.VISITE_DEBRIEF_LIBELLE)
        self.assertEqual(debrief.due_date, datetime.date(2026, 10, 2))

    def test_devis_desactive_le_defaut_est_pose(self):
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.APRES_CONTACT,
            cle='devis').update(actif=False, libelle='Ne pas utiliser')

        self._fait(self._touche(), outcome='joint')

        [etape] = self._ouvertes()
        self.assertEqual((etape.cle, etape.libelle),
                         ('devis', services.FILET_JOINT_LIBELLE))


class ConfirmationAvantLaVisiteTests(_Base):
    """(d) — ``delai_jours`` de la confirmation = jours AVANT la visite."""

    slug = 'pcad-m-d'

    def test_confirmation_a_j_moins_deux(self):
        confirmation = _barreau(self.company, Cadence.VISITE, 'confirmation')
        confirmation.delai_jours = 2
        confirmation.libelle = 'Appeler pour confirmer'
        confirmation.canal = 'appel'
        confirmation.save()

        services.appliquer_visite_planifiee(self.lead, self.acteur, VISITE_LE)

        etape = self.lead.relance_etapes.get(cle='confirmation',
                                             statut=A_FAIRE)
        self.assertEqual(etape.due_date, datetime.date(2026, 9, 29))
        self.assertEqual((etape.libelle, etape.canal),
                         ('Appeler pour confirmer', 'appel'))

    def test_jamais_avant_aujourd_hui(self):
        confirmation = _barreau(self.company, Cadence.VISITE, 'confirmation')
        confirmation.delai_jours = 30
        confirmation.save()

        services.appliquer_visite_planifiee(self.lead, self.acteur, VISITE_LE)

        etape = self.lead.relance_etapes.get(cle='confirmation',
                                             statut=A_FAIRE)
        self.assertEqual(etape.due_date, AUJOURDHUI)

    def test_debrief_a_j_plus_quatre(self):
        debrief = _barreau(self.company, Cadence.VISITE, 'debrief')
        debrief.delai_jours = 4
        debrief.save()

        services.appliquer_visite_planifiee(self.lead, self.acteur, VISITE_LE)

        etape = self.lead.relance_etapes.get(cle='debrief', statut=A_FAIRE)
        # Jeudi + 4 = lundi 05/10 (ouvré).
        self.assertEqual(etape.due_date, datetime.date(2026, 10, 5))


class EtapeAvantLaCleTests(_Base):
    """(e) — les étapes posées avant la clé restent reconnues."""

    slug = 'pcad-m-e'

    def test_l_ancienne_etape_devis_vaut_devis_parti(self):
        ancienne = self._touche(cadence='generique', ordre=1,
                                libelle=services.FILET_JOINT_LIBELLE)
        self.assertEqual(ancienne.cle, '')

        resp = self._fait(ancienne)

        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)

    def test_le_predicat(self):
        for libelle in (services.FILET_JOINT_LIBELLE,
                        services._FILET_JOINT_LIBELLE_ANCIEN):
            with self.subTest(libelle=libelle):
                self.assertTrue(cadence_config.est_etape(
                    RelanceEtape(libelle=libelle), 'devis'))
        # Un libellé RENOMMÉ sans clé n'est jamais reconnu…
        self.assertFalse(cadence_config.est_etape(
            RelanceEtape(libelle='Faire le devis'), 'devis'))
        # … et la clé l'emporte sur un libellé par défaut trompeur.
        self.assertFalse(cadence_config.est_etape(
            RelanceEtape(libelle=services.FILET_JOINT_LIBELLE,
                         cle='debrief'), 'devis'))
        self.assertTrue(cadence_config.est_etape(
            RelanceEtape(libelle='Faire le devis', cle='devis'), 'devis'))

    def test_la_requete_suit_le_predicat(self):
        cle = self._touche(cadence='generique', ordre=1,
                           libelle='Faire le devis', cle='devis')
        ancienne = self._touche(cadence='generique', ordre=1,
                                libelle=services._FILET_JOINT_LIBELLE_ANCIEN)
        self._touche(cadence='generique', ordre=1, libelle='Faire le devis')
        trouvees = set(self.lead.relance_etapes.filter(
            cadence_config.q_etape('devis')).values_list('pk', flat=True))
        self.assertEqual(trouvees, {cle.pk, ancienne.pk})

    def test_un_debrief_renomme_reste_une_etape_de_visite(self):
        """Le récepteur d'issue ne tient que la ligne de chatter : un débrief
        RENOMMÉ ne doit jamais démarrer le suivi de proposition (CAD2)."""
        debrief = self._touche(
            cadence='apres_devis', ordre=services.VISITE_ORDRE_DEBRIEF,
            libelle='Rappeler après la visite', cle='debrief')
        services.marquer_etape_relance(
            debrief, self.acteur, RelanceEtape.Statut.FAIT, outcome='joint')
        ligne = LeadActivity.objects.filter(
            lead=self.lead,
            body__startswith='Touche « Rappeler après la visite »').get()
        self.assertTrue(services.est_cloture_d_etape_visite(ligne))
        self.assertTrue(services.est_etape_de_visite(debrief))


class DeuxSocietesTests(_Base):
    """(f) — deux sociétés, deux réglages, aucune fuite."""

    slug = 'pcad-m-f'

    def test_chaque_societe_lit_son_gabarit(self):
        devis = _barreau(self.company, Cadence.APRES_CONTACT, 'devis')
        devis.libelle = 'Faire le devis'
        devis.delai_jours = 2
        devis.save()
        autre = _societe(f'{self.slug}-b')
        acteur_b = User.objects.create_user(
            username=f'{self.slug}-b-resp', password='x',
            role_legacy='responsable', company=autre)
        lead_b = self._lead(autre, acteur_b, nom='Tazi')

        services.assurer_prochaine_etape_apres_succes(self.lead, self.acteur)
        services.assurer_prochaine_etape_apres_succes(lead_b, acteur_b)

        [a] = self._ouvertes()
        [b] = self._ouvertes(lead_b)
        self.assertEqual((a.libelle, a.due_date),
                         ('Faire le devis', datetime.date(2026, 9, 25)))
        self.assertEqual((b.libelle, b.due_date),
                         (services.FILET_JOINT_LIBELLE,
                          datetime.date(2026, 9, 24)))
        self.assertEqual((a.cle, b.cle), ('devis', 'devis'))
        self.assertEqual(b.company_id, autre.pk)


class JamaisUnPlanTests(TestCase):
    """« Après l'appel » et « Visite technique » sont les gabarits des étapes
    que le moteur pose — jamais un plan qu'on démarre sur un lead."""

    def test_le_demarrage_d_une_cadence_moteur_est_refuse(self):
        company = Company.objects.create(nom='PCAD Plan', slug='pcad-plan')
        responsable = User.objects.create_user(
            username='pcad-plan-resp', password='pw',
            role_legacy='responsable', company=company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(responsable)}')
        lead = Lead.objects.create(company=company, nom='Plan',
                                   owner=responsable)
        for cadence in CADENCES_MOTEUR:
            resp = api.post(
                f'/api/django/crm/leads/{lead.pk}/relance/initialiser/',
                {'cadence': cadence}, format='json')
            self.assertEqual(resp.status_code, 400, resp.data)
            self.assertIn('cadence', resp.data)
        self.assertFalse(lead.relance_etapes.exists())
