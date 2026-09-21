"""CAD31 — la promesse « 5 minutes » surveille enfin le flot publicitaire, et
cesse de réveiller tout le monde à l'ouverture.

Trois défauts, un seul balayage :

  * `source=OS_NATIVE` laissait dehors SITE_WEB et META_LEAD_ADS — précisément
    le flot qui arrive la nuit et le week-end. Aucun lead publicitaire n'a
    jamais déclenché d'escalade ;
  * `stage=NEW` laissait dehors un lead avancé à la main sans avoir été
    rappelé. Ce qui compte est « jamais contacté », pas « encore au premier
    barreau » ;
  * l'objectif SERVAIT de seuil d'alerte : trois leads de nuit franchissent
    les cinq minutes ouvrées à la même minute, à l'ouverture, et trois
    alertes identiques partaient au responsable ET à son supérieur.

Ce qui NE change pas : le miroir Odoo reste dehors (les leads importés ne
sont pas des demandes à rappeler — `tests_mry17_notifications.py` le
verrouille déjà, et la décision fondateur du 21/09/2026 dit la même chose du
miroir pour la cadence automatique), les minutes restent OUVRÉES, et
l'idempotence par lead tient.

Les deux paliers sont VIDES par défaut : sans réglage, le comportement est
exactement celui d'avant — seul le périmètre des leads surveillés s'élargit.

Horloge FIXE partout.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires
from apps.crm.management.commands.escalader_premier_contact import (
    MARQUEUR, escalader_premier_contact)
from apps.crm.models import Lead, LeadActivity
from apps.crm.stages import COLD, CONTACTED, NEW, SIGNED
from apps.notifications.models import EventType, Notification
from apps.parametres.models import CompanyProfile

User = get_user_model()

CASA = horaires.CASABLANCA

#: Mercredi 2 septembre 2026 — jour ouvré, en pleine fenêtre.
ARRIVEE = datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA)
#: Deux heures plus tard : bien au-delà de l'objectif.
CONTROLE = datetime.datetime(2026, 9, 2, 11, 0, tzinfo=CASA)
#: Une nuit, puis l'ouverture du lendemain.
NUIT = datetime.datetime(2026, 9, 2, 23, 0, tzinfo=CASA)
LENDEMAIN_MATIN = datetime.datetime(2026, 9, 3, 9, 30, tzinfo=CASA)


class _Base(TestCase):
    slug = 'cad31'

    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD31 Solaire', slug=f'{self.slug}-a')
        self.profil, _ = CompanyProfile.objects.get_or_create(
            company=self.company)
        self.superieure = User.objects.create_user(
            username=f'{self.slug}-sup', password='x',
            role_legacy='directeur', company=self.company)
        self.commerciale = User.objects.create_user(
            username=f'{self.slug}-com', password='x',
            role_legacy='responsable', company=self.company,
            supervisor=self.superieure)

    def _lead(self, cree_le=ARRIVEE, **kw):
        champs = {'company': self.company, 'nom': 'Prospect',
                  'owner': self.commerciale,
                  'source': Lead.Source.OS_NATIVE, 'stage': NEW}
        champs.update(kw)
        lead = Lead.objects.create(**champs)
        Lead.objects.filter(pk=lead.pk).update(date_creation=cree_le)
        lead.refresh_from_db(fields=['date_creation'])
        return lead

    def _notifs(self, utilisateur=None):
        qs = Notification.objects.filter(
            event_type=EventType.PREMIER_CONTACT_DEPASSE)
        if utilisateur is not None:
            qs = qs.filter(recipient=utilisateur)
        return qs


class ToutesLesSourcesTests(_Base):
    """Le premier « Done = » : un lead META_LEAD_ADS en retard escalade."""

    slug = 'cad31-sources'

    def test_un_lead_META_LEAD_ADS_en_retard_est_escalade(self):
        self._lead(source=Lead.Source.META_LEAD_ADS)
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 1)
        self.assertEqual(self._notifs(self.commerciale).count(), 1)

    def test_un_lead_du_SITE_WEB_aussi(self):
        self._lead(source=Lead.Source.SITE_WEB)
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 1)

    def test_le_lead_natif_continue_bien_sur_descalader(self):
        self._lead(source=Lead.Source.OS_NATIVE)
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 1)

    def test_le_miroir_ODOO_reste_dehors(self):
        """Les leads importés ne sont pas des demandes à rappeler : les
        ouvrir ferait partir des centaines d'alertes d'un coup."""
        self._lead(source=Lead.Source.ODOO_IMPORT_TEST)
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 0)
        self.assertEqual(self._notifs().count(), 0)


class LEtapeNeFiltrePlusTests(_Base):
    """Ce qui compte est « jamais contacté », pas « encore au premier
    barreau »."""

    slug = 'cad31-etape'

    def test_un_lead_avance_a_la_main_mais_jamais_contacte_escalade(self):
        self._lead(stage=CONTACTED)
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 1)

    def test_un_dossier_CLOS_nescalade_jamais(self):
        for etape in (SIGNED, COLD):
            with self.subTest(stage=etape):
                LeadActivity.objects.all().delete()
                Lead.objects.all().delete()
                self._lead(stage=etape)
                self.assertEqual(escalader_premier_contact(now=CONTROLE), 0)

    def test_un_lead_deja_contacte_reste_ignore(self):
        self._lead(first_contacted_at=datetime.datetime(
            2026, 9, 2, 9, 2, tzinfo=CASA))
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 0)


class UneSeuleAlerteAuSuperieurTests(_Base):
    """Le second « Done = » : trois leads de nuit, une seule alerte en
    haut."""

    slug = 'cad31-nuit'

    def test_trois_leads_de_nuit_ne_font_quUNE_alerte_au_superieur(self):
        for rang in range(3):
            self._lead(cree_le=NUIT, nom=f'Prospect {rang}')
        self.assertEqual(
            escalader_premier_contact(now=LENDEMAIN_MATIN), 3)
        # Le responsable, lui, voit bien ses trois dossiers.
        self.assertEqual(self._notifs(self.commerciale).count(), 3)
        # Le supérieur n'en reçoit QU'UNE.
        self.assertEqual(self._notifs(self.superieure).count(), 1)

    def test_lalerte_groupee_dit_combien_de_prospects_attendent(self):
        for rang in range(3):
            self._lead(cree_le=NUIT, nom=f'Prospect {rang}')
        escalader_premier_contact(now=LENDEMAIN_MATIN)
        notif = self._notifs(self.superieure).get()
        self.assertIn('3', notif.title)

    def test_un_seul_lead_nomme_le_prospect_au_superieur(self):
        self._lead(nom='Aziz Benali')
        escalader_premier_contact(now=CONTROLE)
        notif = self._notifs(self.superieure).get()
        self.assertIn('Aziz Benali', notif.title)


class LesDeuxPaliersTests(_Base):
    """L'objectif affiché n'est plus le seuil d'alerte."""

    slug = 'cad31-paliers'

    def test_sans_reglage_le_comportement_est_celui_davant(self):
        self._lead()
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 1)
        self.assertEqual(self._notifs(self.commerciale).count(), 1)
        self.assertEqual(self._notifs(self.superieure).count(), 1)

    def test_un_palier_dalerte_plus_haut_retarde_lescalade(self):
        self.profil.premier_contact_alerte_min = 180
        self.profil.save(update_fields=['premier_contact_alerte_min'])
        self._lead()
        # 120 minutes ouvrées écoulées : sous le palier réglé.
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 0)

    def test_le_superieur_nest_prevenu_quau_SECOND_palier(self):
        self.profil.premier_contact_escalade_min = 180
        self.profil.save(update_fields=['premier_contact_escalade_min'])
        self._lead()
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 1)
        # Le responsable est réveillé…
        self.assertEqual(self._notifs(self.commerciale).count(), 1)
        # …mais pas encore son supérieur.
        self.assertEqual(self._notifs(self.superieure).count(), 0)

    def test_au_dela_du_second_palier_le_superieur_est_prevenu(self):
        self.profil.premier_contact_escalade_min = 60
        self.profil.save(update_fields=['premier_contact_escalade_min'])
        self._lead()
        escalader_premier_contact(now=CONTROLE)
        self.assertEqual(self._notifs(self.superieure).count(), 1)

    def test_lobjectif_a_zero_desactive_toujours_la_surveillance(self):
        self.profil.premier_contact_objectif_min = 0
        self.profil.save(update_fields=['premier_contact_objectif_min'])
        self._lead()
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 0)


class LesGardeFousConservesTests(_Base):
    """Ce que CAD31 ne casse pas."""

    slug = 'cad31-gardes'

    def test_les_minutes_restent_OUVREES(self):
        self._lead(cree_le=NUIT)
        self.assertEqual(escalader_premier_contact(
            now=datetime.datetime(2026, 9, 3, 6, 0, tzinfo=CASA)), 0)

    def test_lidempotence_par_lead_tient(self):
        self._lead()
        escalader_premier_contact(now=CONTROLE)
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 0)
        self.assertEqual(
            LeadActivity.objects.filter(body__startswith=MARQUEUR).count(), 1)

    def test_le_dry_run_ne_notifie_ni_necrit(self):
        self._lead()
        self.assertEqual(
            escalader_premier_contact(now=CONTROLE, dry_run=True), 1)
        self.assertEqual(self._notifs().count(), 0)
        self.assertEqual(
            LeadActivity.objects.filter(body__startswith=MARQUEUR).count(), 0)

    def test_un_lead_perdu_ou_archive_reste_ignore(self):
        self._lead(perdu=True, motif_perte='Prix')
        self._lead(is_archived=True)
        self.assertEqual(escalader_premier_contact(now=CONTROLE), 0)

    def test_une_autre_societe_nest_jamais_touchee(self):
        autre = Company.objects.create(nom='CAD31 Bis', slug='cad31-b')
        CompanyProfile.objects.get_or_create(company=autre)
        chez_elle = User.objects.create_user(
            username='cad31-bis-u', password='x',
            role_legacy='responsable', company=autre)
        lead = Lead.objects.create(
            company=autre, nom='Ailleurs', owner=chez_elle,
            source=Lead.Source.META_LEAD_ADS, stage=NEW)
        Lead.objects.filter(pk=lead.pk).update(date_creation=ARRIVEE)
        self._lead()
        escalader_premier_contact(now=CONTROLE)
        # Chacune reçoit la sienne, jamais celle de l'autre.
        self.assertEqual(
            self._notifs(self.commerciale).count(), 1)
        self.assertEqual(self._notifs(chez_elle).count(), 1)
