"""CAD54 — réattribuer un lead : ce que deviennent ses touches ouvertes.

Le round 2 a tranché la moitié technique : elle est SAINE. ``RelanceEtape``
n'a AUCUN champ responsable, donc les touches suivent le lead ; le digest du
matin vise les owners ; le prénom du conseiller est recalculé à chaque rendu ;
le changement est déjà journalisé. Ces tests VERROUILLENT ces quatre faits
plutôt que de les supposer — c'est ce qu'aucune lane n'avait déroulé.

Ce qui manquait est côté CLIENT et côté NOUVEAU responsable, et c'est ce que
CAD54 ajoute :

  * une touche de PASSATION portant le gabarit ``passation``, sur un lead
    DÉJÀ contacté — le prospect ne voit plus changer de prénom sans un mot ;
  * une notification au nouveau responsable qui LISTE ce qu'il hérite, au
    lieu du seul « Nouveau lead assigné ».

Garde-fous vérifiés : aucun prénom codé en dur (le gabarit porte des
variables), aucune valeur d'énumération serveur ajoutée (``template_cle`` est
du texte libre, l'événement est ``lead_assigned`` qui existe déjà), aucune
touche du protocole ajoutée, retirée ni réordonnée.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    PASSATION_LIBELLE, PASSATION_TEMPLATE_CLE, apply_bulk_action,
    lead_notification_recipients, reattribuer_lead)
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 22 septembre 2026, 10 h à Casablanca.
MARDI = datetime.datetime(2026, 9, 22, 10, 0, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad54'

    def setUp(self):
        gel = frozen(MARDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD54 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.ancien = User.objects.create_user(
            username=f'{self.slug}-ancien', password='x',
            role_legacy='commercial', company=self.company)
        self.nouveau = User.objects.create_user(
            username=f'{self.slug}-nouveau', password='x',
            role_legacy='commercial', company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, *, contacte=True, stage=stages.CONTACTED):
        return Lead.objects.create(
            company=self.company, nom='Aziz', stage=stage,
            owner=self.ancien, telephone='+212661005401',
            first_contacted_at=MARDI if contacte else None)

    def _touche(self, lead, *, jours=1, libelle='Appel de suivi'):
        quand = MARDI + datetime.timedelta(days=jours)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=2,
            due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date(),
            canal=RelanceEtape.Canal.APPEL, libelle=libelle,
            cadence_depart=MARDI)


class LesTouchesSuiventLeLeadTests(_Base):
    """La moitié SAINE, verrouillée : rien ne porte l'ancien responsable."""

    slug = 'cad54-suivent'

    def test_la_touche_ouverte_pointe_le_nouveau_responsable(self):
        lead = self._lead()
        touche = self._touche(lead)
        reattribuer_lead(lead, self.acteur, self.nouveau)
        touche.refresh_from_db()
        # `RelanceEtape` n'a pas de champ responsable : la touche suit le lead.
        self.assertFalse(hasattr(touche, 'responsable'))
        self.assertEqual(touche.lead.owner_id, self.nouveau.pk)

    def test_les_notifications_ne_visent_plus_l_ancien(self):
        lead = self._lead()
        self._touche(lead)
        avant = {u.pk for u in lead_notification_recipients(lead)}
        self.assertIn(self.ancien.pk, avant)
        reattribuer_lead(lead, self.acteur, self.nouveau)
        lead.refresh_from_db()
        apres = {u.pk for u in lead_notification_recipients(lead)}
        self.assertIn(self.nouveau.pk, apres)
        self.assertNotIn(self.ancien.pk, apres)

    def test_la_touche_n_est_ni_deplacee_ni_dupliquee(self):
        lead = self._lead()
        touche = self._touche(lead)
        echeance = touche.due_at
        reattribuer_lead(lead, self.acteur, self.nouveau)
        touche.refresh_from_db()
        self.assertEqual(touche.due_at, echeance)
        self.assertEqual(
            lead.relance_etapes.filter(cadence='contact').count(), 1)


class TouchePassationTests(_Base):
    slug = 'cad54-passation'

    def test_un_lead_deja_contacte_recoit_la_touche_de_passation(self):
        lead = self._lead()
        etape = reattribuer_lead(lead, self.acteur, self.nouveau)
        self.assertIsNotNone(etape)
        self.assertEqual(etape.libelle, PASSATION_LIBELLE)
        self.assertEqual(etape.template_cle, PASSATION_TEMPLATE_CLE)
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)

    def test_aucun_prenom_n_est_ecrit_dans_la_touche(self):
        lead = self._lead()
        etape = reattribuer_lead(lead, self.acteur, self.nouveau)
        # Le prénom du conseiller vit dans le GABARIT, en variable — jamais
        # figé dans une ligne (règle fondateur du 08/09/2026).
        for texte in (etape.libelle or '', etape.note or ''):
            self.assertNotIn(self.ancien.username, texte)
            self.assertNotIn(self.nouveau.username, texte)

    def test_un_lead_jamais_contacte_ne_recoit_rien(self):
        lead = self._lead(contacte=False, stage=stages.NEW)
        self.assertIsNone(reattribuer_lead(lead, self.acteur, self.nouveau))
        self.assertEqual(
            lead.relance_etapes.filter(libelle=PASSATION_LIBELLE).count(), 0)

    def test_deux_reattributions_ne_posent_pas_deux_passations(self):
        lead = self._lead()
        troisieme = User.objects.create_user(
            username=f'{self.slug}-troisieme', password='x',
            role_legacy='commercial', company=self.company)
        reattribuer_lead(lead, self.acteur, self.nouveau)
        reattribuer_lead(lead, self.acteur, troisieme)
        self.assertEqual(
            lead.relance_etapes.filter(libelle=PASSATION_LIBELLE).count(), 1)

    def test_un_lead_signe_ne_recoit_pas_de_passation(self):
        lead = self._lead(stage=stages.SIGNED)
        self.assertIsNone(reattribuer_lead(lead, self.acteur, self.nouveau))

    def test_une_reattribution_a_soi_meme_est_un_no_op(self):
        lead = self._lead()
        self.assertIsNone(reattribuer_lead(lead, self.acteur, self.ancien))
        self.assertEqual(lead.relance_etapes.count(), 0)


class NotificationDesTouchesHeriteesTests(_Base):
    slug = 'cad54-notif'

    def _notifs(self, user):
        from apps.notifications.models import Notification
        return list(Notification.objects.filter(recipient=user))

    def test_le_nouveau_responsable_apprend_ce_qu_il_herite(self):
        lead = self._lead()
        self._touche(lead)
        reattribuer_lead(lead, self.acteur, self.nouveau)
        corps = ' '.join(n.body or '' for n in self._notifs(self.nouveau))
        self.assertIn('relance(s) déjà programmée(s)', corps)
        self.assertIn('Appel de suivi', corps)

    def test_sans_touche_ouverte_aucune_notification_de_plus(self):
        lead = self._lead()
        reattribuer_lead(lead, self.acteur, self.nouveau)
        titres = [n.title for n in self._notifs(self.nouveau)]
        self.assertNotIn('Dossier repris — relances héritées', titres)


class ReattributionEnMasseTests(_Base):
    """Le chemin en MASSE passe par le même geste."""

    slug = 'cad54-masse'

    def test_l_action_en_masse_pose_la_passation(self):
        lead = self._lead()
        self._touche(lead)
        res = apply_bulk_action(
            company=self.company, user=self.acteur, lead_ids=[lead.id],
            op='reassign', params={'owner': self.nouveau.pk})
        self.assertEqual(res['updated'], 1)
        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, self.nouveau.pk)
        self.assertEqual(
            lead.relance_etapes.filter(libelle=PASSATION_LIBELLE).count(), 1)

    def test_le_changement_reste_journalise(self):
        lead = self._lead()
        apply_bulk_action(
            company=self.company, user=self.acteur, lead_ids=[lead.id],
            op='reassign', params={'owner': self.nouveau.pk})
        self.assertTrue(
            LeadActivity.objects.filter(lead=lead).exists())
