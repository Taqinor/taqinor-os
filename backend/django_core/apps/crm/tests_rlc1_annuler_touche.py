"""RLC1 — Annuler une touche « Fait »/« Sautée » traitée par erreur (< 24 h).

Relevé fondateur du 08/09/2026 : « une touche "Fait" par erreur ne se défait
pas ». Ce fichier prouve les trois moitiés de la réponse :

  * ce qui SE DÉFAIT — la touche revient à faire à SON échéance d'origine, les
    touches retirées du plan par l'arrêt de cadence repartent, l'étape que
    l'issue avait programmée disparaît, l'avance NEW → Contacté est défaite ;
  * ce qui NE SE DÉFAIT PAS — refus MOTIVÉ nommant le champ fautif (passé
    24 h, touche jamais traitée, devis parti, lead signé) ;
  * l'ISOLATION société — une touche d'une autre société est introuvable,
    jamais annulable.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    ANNULATION_TOUCHE_HEURES, AnnulationToucheRefusee, FILET_JOINT_LIBELLE,
    annuler_touche_relance, initialiser_plan_relance, marquer_etape_relance)
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Cadence RÉTRODATÉE : la matérialisation réactive pose alors toutes les
#: touches échues du gabarit — l'état qu'il faut pour voir un ARRÊT de cadence
#: en retirer plusieurs d'un coup. Ancrée à midi, heure de Casablanca (jamais
#: un `now()` UTC, qui basculerait de jour une heure par nuit).
LUNDI_PASSE = datetime.datetime(2026, 9, 7, 12, 0, tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'rlc1'
    depart = LUNDI_PASSE

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)
        self.etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=self.depart, cadence='contact')
        self.assertTrue(self.etapes, "le gabarit de contact doit poser des touches")

    def _api(self, user=None):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user or self.acteur)}'))
        return api

    def _ouvertes(self):
        return self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).count()


class ToucheNeeDeLIssueTests(_Base):
    """Ce que la clôture a fait NAÎTRE repart avec elle."""

    slug = 'rlc1-nee'
    #: Départ à VENIR : une seule touche est matérialisée, et c'est l'issue
    #: saisie qui fait naître la suivante (cadence réactive CKP2) — l'état
    #: exact où « la touche née de cette issue » est identifiable.
    depart = datetime.datetime(2099, 1, 4, 12, 0, tzinfo=horaires.CASABLANCA)

    def test_la_touche_revient_a_faire_a_son_echeance_dorigine(self):
        etape = self.etapes[0]
        due_at, due_date = etape.due_at, etape.due_date
        total_avant = self.lead.relance_etapes.count()
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='non_joint')
        self.assertGreater(
            self.lead.relance_etapes.count(), total_avant,
            "l'issue « pas de réponse » doit faire naître la touche suivante")

        annuler_touche_relance(etape, self.acteur)

        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(etape.due_at, due_at)
        self.assertEqual(etape.due_date, due_date)
        self.assertIsNone(etape.traite_par)
        self.assertIsNone(etape.traite_le)
        self.assertEqual(etape.note, '')
        # L'étape programmée par l'issue a été retirée : le plan retrouve
        # exactement le nombre de lignes qu'il portait avant la clôture.
        self.assertEqual(self.lead.relance_etapes.count(), total_avant)

    def test_lannulation_est_journalisee_en_note_systeme_nommant_lauteur(self):
        etape = self.etapes[0]
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='non_joint')
        activites_avant = self.lead.activites.count()

        annuler_touche_relance(etape, self.acteur)

        self.assertEqual(
            self.lead.activites.count(), activites_avant + 1,
            "l'annulation ajoute UNE note, et n'efface aucune ligne existante")
        note = self.lead.activites.order_by('-created_at', '-pk').first()
        self.assertEqual(note.kind, LeadActivity.Kind.NOTE)
        # Geste du moteur tracé : l'auteur vit dans le TEXTE, jamais en acteur
        # de l'activité (sans quoi une annulation compterait comme un contact).
        self.assertIsNone(note.user)
        self.assertIn('Annulation par', note.body)
        self.assertIn(self.acteur.username, note.body)

    def test_une_touche_sautee_sannule_aussi(self):
        etape = self.etapes[0]
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.SAUTEE, note='doublon')

        annuler_touche_relance(etape, self.acteur)

        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(etape.note, '')


class ArretDeCadenceDefaitTests(_Base):
    """Les touches retirées par l'ARRÊT de cadence repartent, et l'avance
    NEW → Contacté qu'aucune autre réponse ne confirme est défaite."""

    slug = 'rlc1-arret'

    def test_les_touches_annulees_par_larret_repartent_et_letape_recule(self):
        etape = self.etapes[0]
        ouvertes_avant = self._ouvertes()
        self.assertGreater(
            ouvertes_avant, 1,
            'la cadence rétrodatée doit porter plusieurs touches ouvertes')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)

        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='joint')
        self.assertEqual(
            self.lead.relance_etapes.filter(
                statut=RelanceEtape.Statut.ANNULEE).count(),
            ouvertes_avant - 1,
            "« joint » arrête la cadence : les autres touches sont annulées")
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)
        filets = self.lead.relance_etapes.filter(
            cadence='generique', statut=RelanceEtape.Statut.A_FAIRE)
        self.assertTrue(filets.exists(), 'le filet « client joint » est posé')

        annuler_touche_relance(etape, self.acteur)

        self.assertEqual(
            self.lead.relance_etapes.filter(
                statut=RelanceEtape.Statut.ANNULEE).count(), 0)
        self.assertEqual(self._ouvertes(), ouvertes_avant)
        self.assertFalse(
            filets.exists(),
            "l'étape de filet posée par cette issue est retirée")
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)

    def test_lavance_detape_tient_si_une_autre_reponse_la_confirme(self):
        """« annulée si aucune AUTRE réponse ne l'a confirmée » : un « joint »
        journalisé ailleurs, hier, garde le lead à Contacté — l'annulation de la
        touche ne va pas effacer un fait vrai."""
        lead = Lead.objects.create(
            company=self.company, nom='Déjà joint', owner=self.acteur)
        autre = LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.acteur,
            kind=LeadActivity.Kind.APPEL, outcome='joint',
            body='Appel journalisé à la main — client joint.')
        # Fixture : cette réponse date d'HIER (hors de toute fenêtre de clôture)
        # et l'état du plan repart de zéro — le filet posé par le récepteur
        # MRY9 n'est pas le sujet de ce test, et l'étape est remise à NEW pour
        # que la touche ci-dessous produise bien l'avance qu'on veut voir TENIR.
        LeadActivity.objects.filter(pk=autre.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=1))
        lead.relance_etapes.all().delete()
        Lead.objects.filter(pk=lead.pk).update(stage=stages.NEW)
        lead.refresh_from_db()
        etapes = initialiser_plan_relance(
            lead, self.acteur, depart=self.depart, cadence='contact')
        etape = etapes[0]

        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='joint')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)

        annuler_touche_relance(etape, self.acteur)

        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)


class RefusMotiveTests(_Base):
    """Ce qui ne se défait plus le dit, en nommant le champ fautif."""

    slug = 'rlc1-refus'

    def test_une_touche_jamais_traitee_na_rien_a_annuler(self):
        etape = self.etapes[0]
        with self.assertRaises(AnnulationToucheRefusee) as capture:
            annuler_touche_relance(etape, self.acteur)
        self.assertEqual(capture.exception.champ, 'statut')

    def test_passe_24h_la_touche_ne_sannule_plus(self):
        etape = self.etapes[0]
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='non_joint')
        RelanceEtape.objects.filter(pk=etape.pk).update(
            traite_le=timezone.now() - datetime.timedelta(
                hours=ANNULATION_TOUCHE_HEURES, minutes=1))
        etape.refresh_from_db()

        with self.assertRaises(AnnulationToucheRefusee) as capture:
            annuler_touche_relance(etape, self.acteur)
        self.assertEqual(capture.exception.champ, 'traite_le')
        self.assertIn(str(ANNULATION_TOUCHE_HEURES), capture.exception.message)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.FAIT)

    def test_un_lead_signe_ne_rouvre_plus_ses_touches(self):
        etape = self.etapes[0]
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='non_joint')
        Lead.objects.filter(pk=self.lead.pk).update(stage=stages.SIGNED)

        with self.assertRaises(AnnulationToucheRefusee) as capture:
            annuler_touche_relance(etape, self.acteur)
        self.assertEqual(capture.exception.champ, 'lead')

    def test_un_lead_perdu_ne_rouvre_plus_ses_touches(self):
        etape = self.etapes[0]
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='non_joint')
        Lead.objects.filter(pk=self.lead.pk).update(perdu=True)

        with self.assertRaises(AnnulationToucheRefusee) as capture:
            annuler_touche_relance(etape, self.acteur)
        self.assertEqual(capture.exception.champ, 'lead')

    def test_lenvoi_du_devis_ne_se_defait_pas(self):
        """La touche « préparer et envoyer le devis » cochée place le lead à
        « Devis envoyé » (QJ-FUNNEL) : cet effet-là est irréversible ici."""
        envoi = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL,
            libelle=FILET_JOINT_LIBELLE,
            due_at=self.depart,
            due_date=self.depart.astimezone(horaires.CASABLANCA).date())
        marquer_etape_relance(envoi, self.acteur, RelanceEtape.Statut.FAIT)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)

        with self.assertRaises(AnnulationToucheRefusee) as capture:
            annuler_touche_relance(envoi, self.acteur)
        self.assertEqual(capture.exception.champ, 'statut')
        envoi.refresh_from_db()
        self.assertEqual(envoi.statut, RelanceEtape.Statut.FAIT)


class ApiAnnulerTests(_Base):
    """La route POST /relance-etapes/<pk>/annuler/."""

    slug = 'rlc1-api'

    def _url(self, etape):
        return f'/api/django/crm/relance-etapes/{etape.pk}/annuler/'

    def test_200_et_touche_a_faire(self):
        etape = self.etapes[0]
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='non_joint')

        resp = self._api().post(self._url(etape), {}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], RelanceEtape.Statut.A_FAIRE)

    def test_400_nomme_le_champ_fautif(self):
        resp = self._api().post(self._url(self.etapes[0]), {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('statut', resp.data['erreurs'])
        self.assertTrue(resp.data['erreurs']['statut'].strip())

    def test_isolation_societe(self):
        etape = self.etapes[0]
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='non_joint')
        autre_company = _company(f'{self.slug}-autre')
        intruse = User.objects.create_user(
            username=f'{self.slug}-intruse', password='x',
            role_legacy='responsable', company=autre_company)

        resp = self._api(intruse).post(self._url(etape), {}, format='json')

        self.assertEqual(resp.status_code, 404)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.FAIT)
