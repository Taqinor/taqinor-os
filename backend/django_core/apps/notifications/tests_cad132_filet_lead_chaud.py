"""CAD132 — le filet « lead chaud non contacté » voit enfin les leads Meta,
ne sonne plus la nuit, et ne s'éteint plus d'un clic.

Trois défauts dans le même balayage (audit L3 du 21/09/2026) :

  * un score ≥ 70 qu'un lead Meta ne peut pas atteindre — la première source
    de leads de la maison ne déclenchait jamais son propre filet. Le seuil est
    désormais UNIQUE, 60, le même que la file « leads chauds non contactés » ;
  * il regardait si la NOTIFICATION d'arrivée était encore non lue : un
    « tout marquer comme lu » éteignait toutes les escalades sans qu'aucun
    appel ait été passé. Il regarde maintenant le LEAD (`first_contacted_at`) ;
  * son délai était en minutes de PENDULE sur un balayage 24 h/24 : il
    pouvait sonner à 3 h du matin. Il compte en minutes OUVRÉES et ne part
    que pendant la fenêtre ouvrée.

S'y ajoutent : le balayage écarte lui-même les leads perdus, opposés,
archivés et clos, et il trie AVANT de tronquer.

Horloge FIXE partout (`now=`), jamais l'heure réelle.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires
from apps.crm.models import Lead
from apps.crm.selectors import leads_chauds_non_contactes
from apps.crm.stages import COLD, NEW, SIGNED
from apps.notifications import sweeps
from apps.notifications.models import EventType, Notification
from apps.notifications.sweeps import HOT_LEAD_TITRE, sweep_hot_leads

User = get_user_model()

CASA = horaires.CASABLANCA

#: Mercredi 2 septembre 2026 — jour ouvré, en pleine fenêtre.
ARRIVEE = datetime.datetime(2026, 9, 2, 9, 0, tzinfo=CASA)
#: Deux heures plus tard : 120 minutes ouvrées, bien au-delà du seuil.
CONTROLE = datetime.datetime(2026, 9, 2, 11, 0, tzinfo=CASA)
#: Un lead du soir : 60 minutes ouvrées avant la fermeture de 20 h.
SOIR = datetime.datetime(2026, 9, 2, 19, 0, tzinfo=CASA)
TROIS_HEURES = datetime.datetime(2026, 9, 3, 3, 0, tzinfo=CASA)
#: Le lendemain, un quart d'heure après l'ouverture des messages (08:30).
OUVERTURE = datetime.datetime(2026, 9, 3, 8, 45, tzinfo=CASA)
#: Un lead de nuit, arrivé après la fermeture.
NUIT = datetime.datetime(2026, 9, 2, 23, 0, tzinfo=CASA)

#: Un lead Meta bien renseigné atteint ~60 depuis CAD134 (le délai déclaré
#: pose `project_timeline`) ; le score est posé tel quel pour que le test ne
#: dépende ni des pondérations ni de l'horloge réelle (fraîcheur).
SCORE_META = 62


class _Base(TestCase):
    slug = 'cad132'

    def setUp(self):
        self.company = Company.objects.create(
            nom=f'CAD132 {self.slug}', slug=f'{self.slug}-a')
        self.manager = User.objects.create_user(
            username=f'{self.slug}-mgr', password='x',
            role_legacy='responsable', company=self.company)
        self.commerciale = User.objects.create_user(
            username=f'{self.slug}-com', password='x',
            role_legacy='commercial', company=self.company)

    def _lead(self, cree_le=ARRIVEE, **kw):
        champs = {'company': self.company, 'nom': 'Prospect Meta',
                  'owner': self.commerciale, 'stage': NEW,
                  'source': Lead.Source.META_LEAD_ADS,
                  'canal': Lead.Canal.META_ADS, 'score': SCORE_META}
        champs.update(kw)
        lead = Lead.objects.create(**champs)
        Lead.objects.filter(pk=lead.pk).update(date_creation=cree_le)
        lead.refresh_from_db(fields=['date_creation'])
        return lead

    def _escalades(self, utilisateur=None, lead=None):
        qs = Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD, title=HOT_LEAD_TITRE)
        if utilisateur is not None:
            qs = qs.filter(recipient=utilisateur)
        if lead is not None:
            qs = qs.filter(link=f'/crm/leads?lead={lead.pk}')
        return qs


class UnLeadMetaDeclencheLeFiletTests(_Base):
    """Premier « Done = » : un lead Meta non contacté déclenche le filet."""

    slug = 'cad132-meta'

    def test_un_lead_META_non_contacte_declenche_le_filet(self):
        lead = self._lead()
        self.assertGreaterEqual(sweep_hot_leads(now=CONTROLE), 2)
        # Le responsable du dossier ET le manager sont prévenus.
        self.assertEqual(self._escalades(self.commerciale, lead).count(), 1)
        self.assertEqual(self._escalades(self.manager, lead).count(), 1)

    def test_un_lead_CTWA_aussi(self):
        self._lead(source=Lead.Source.OS_NATIVE,
                   canal=Lead.Canal.WHATSAPP_CTWA)
        sweep_hot_leads(now=CONTROLE)
        self.assertEqual(self._escalades(self.commerciale).count(), 1)

    def test_le_seuil_est_60_et_non_plus_70(self):
        a_60 = self._lead(score=60, nom='Soixante')
        a_59 = self._lead(score=59, nom='Cinquante-neuf')
        sweep_hot_leads(now=CONTROLE)
        self.assertTrue(self._escalades(lead=a_60).exists())
        self.assertFalse(self._escalades(lead=a_59).exists())

    def test_seuil_unique_avec_la_file_des_leads_chauds(self):
        """Un lead est « chaud » partout ou nulle part : le filet et la file
        `leads_chauds_non_contactes` tranchent au même score."""
        a_60 = self._lead(score=60, nom='Soixante')
        a_59 = self._lead(score=59, nom='Cinquante-neuf')
        file_ids = set(leads_chauds_non_contactes(
            self.company, self.commerciale).values_list('pk', flat=True))
        sweep_hot_leads(now=CONTROLE)
        self.assertIn(a_60.pk, file_ids)
        self.assertTrue(self._escalades(lead=a_60).exists())
        self.assertNotIn(a_59.pk, file_ids)
        self.assertFalse(self._escalades(lead=a_59).exists())

    def test_un_lead_sans_score_reste_dehors(self):
        self._lead(score=None)
        sweep_hot_leads(now=CONTROLE)
        self.assertFalse(self._escalades().exists())

    def test_le_miroir_ODOO_reste_dehors(self):
        """Comme l'escalade premier-contact : les leads importés ne sont pas
        des demandes à rappeler."""
        self._lead(source=Lead.Source.ODOO_IMPORT_TEST)
        sweep_hot_leads(now=CONTROLE)
        self.assertFalse(self._escalades().exists())


class AucunDeclenchementHorsFenetreTests(_Base):
    """Deuxième « Done = » : aucun déclenchement hors fenêtre ouvrée."""

    slug = 'cad132-fenetre'

    def test_un_lead_du_soir_ne_sonne_pas_a_3h_mais_a_louverture(self):
        # 19 h → 20 h : 60 minutes ouvrées, le seuil (30) est franchi dès le
        # soir ; à 3 h du matin, rien ne part pour autant.
        lead = self._lead(cree_le=SOIR)
        self.assertEqual(sweep_hot_leads(now=TROIS_HEURES), 0)
        self.assertFalse(self._escalades().exists())
        # À l'ouverture, le filet sonne.
        sweep_hot_leads(now=OUVERTURE)
        self.assertTrue(self._escalades(self.commerciale, lead).exists())

    def test_les_minutes_sont_OUVREES_pas_de_pendule(self):
        # Arrivé à 23 h : à 08:50 le lendemain, 20 minutes ouvrées seulement
        # (près de dix heures de pendule).
        self._lead(cree_le=NUIT)
        sweep_hot_leads(
            now=datetime.datetime(2026, 9, 3, 8, 50, tzinfo=CASA))
        self.assertFalse(self._escalades().exists())
        # À 09:05, 35 minutes ouvrées : au-delà du seuil.
        sweep_hot_leads(
            now=datetime.datetime(2026, 9, 3, 9, 5, tzinfo=CASA))
        self.assertTrue(self._escalades(self.commerciale).exists())

    def test_le_samedi_non_ouvre_ne_sonne_pas(self):
        # Vendredi 4 septembre 2026, 18 h : 120 minutes ouvrées avant la
        # fermeture ; samedi 5 à 11 h n'est pas un jour ouvré par défaut.
        self._lead(cree_le=datetime.datetime(2026, 9, 4, 18, 0, tzinfo=CASA))
        self.assertEqual(sweep_hot_leads(
            now=datetime.datetime(2026, 9, 5, 11, 0, tzinfo=CASA)), 0)
        self.assertFalse(self._escalades().exists())


class ToutMarquerCommeLuNeLeteintPlusTests(_Base):
    """Troisième « Done = » : « tout marquer comme lu » ne l'éteint plus."""

    slug = 'cad132-lu'

    def _tout_marquer_comme_lu(self, utilisateur):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(utilisateur)}')
        resp = api.post('/api/django/notifications/notifications/read-all/')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_tout_marquer_comme_lu_ne_leteint_plus(self):
        lead = self._lead()
        # La notification d'arrivée, lue d'un clic par tout le monde.
        for utilisateur in (self.commerciale, self.manager):
            Notification.objects.create(
                company=self.company, recipient=utilisateur,
                event_type=EventType.LEAD_NEW, title='Nouveau lead',
                link=f'/crm/leads?lead={lead.pk}')
            self._tout_marquer_comme_lu(utilisateur)
        self.assertFalse(Notification.objects.filter(
            company=self.company, read=False).exists())
        sweep_hot_leads(now=CONTROLE)
        self.assertTrue(self._escalades(self.commerciale, lead).exists())
        self.assertTrue(self._escalades(self.manager, lead).exists())

    def test_une_seule_escalade_par_lead_lue_ou_non(self):
        lead = self._lead()
        sweep_hot_leads(now=CONTROLE)
        premieres = self._escalades(lead=lead).count()
        self.assertGreaterEqual(premieres, 2)
        # Lire l'escalade ne la fait pas repartir au passage suivant…
        self._tout_marquer_comme_lu(self.commerciale)
        self._tout_marquer_comme_lu(self.manager)
        self.assertEqual(sweep_hot_leads(
            now=CONTROLE + datetime.timedelta(minutes=15)), 0)
        self.assertEqual(self._escalades(lead=lead).count(), premieres)

    def test_un_lead_contacte_sort_du_filet(self):
        self._lead(first_contacted_at=datetime.datetime(
            2026, 9, 2, 9, 2, tzinfo=CASA))
        sweep_hot_leads(now=CONTROLE)
        self.assertFalse(self._escalades().exists())


class LeBalayageEcarteLuiMemeTests(_Base):
    """`get_company_lead` ne filtrait ni perdu, ni opposé, ni archivé : le
    balayage les écarte lui-même, avec les dossiers clos de STAGES.py."""

    slug = 'cad132-ecarte'

    def test_perdu_oppose_archive_et_clos_restent_dehors(self):
        self._lead(perdu=True, motif_perte='Prix', nom='Perdu')
        self._lead(ne_plus_contacter=True, nom='Opposé')
        self._lead(is_archived=True, nom='Archivé')
        self._lead(stage=SIGNED, nom='Signé')
        self._lead(stage=COLD, nom='Froid')
        self.assertEqual(sweep_hot_leads(now=CONTROLE), 0)
        self.assertFalse(self._escalades().exists())

    def test_une_autre_societe_nest_jamais_prevenue(self):
        autre = Company.objects.create(nom='CAD132 Bis', slug='cad132-bis')
        chez_elle = User.objects.create_user(
            username='cad132-bis-u', password='x',
            role_legacy='responsable', company=autre)
        lead_ailleurs = Lead.objects.create(
            company=autre, nom='Ailleurs', owner=chez_elle, stage=NEW,
            source=Lead.Source.META_LEAD_ADS, score=SCORE_META)
        Lead.objects.filter(pk=lead_ailleurs.pk).update(date_creation=ARRIVEE)
        self._lead()
        sweep_hot_leads(now=CONTROLE)
        self.assertTrue(self._escalades(chez_elle, lead_ailleurs).exists())
        self.assertFalse(self._escalades(self.manager, lead_ailleurs).exists())
        self.assertFalse(self._escalades(chez_elle).exclude(
            link=f'/crm/leads?lead={lead_ailleurs.pk}').exists())


class TriAvantTroncatureTests(_Base):
    """La troncature `[:500]` se faisait sans tri : elle garde désormais les
    plus chauds, et les leads déjà escaladés sortent AVANT elle."""

    slug = 'cad132-tri'

    def test_le_plus_chaud_passe_en_premier_puis_le_suivant(self):
        tiede = self._lead(score=65, nom='Tiède')     # pk le plus petit
        brulant = self._lead(score=90, nom='Brûlant')
        with mock.patch.object(sweeps, 'HOT_LEAD_LOT_MAX', 1):
            sweep_hot_leads(now=CONTROLE)
            self.assertTrue(self._escalades(lead=brulant).exists())
            self.assertFalse(self._escalades(lead=tiede).exists())
            # Le lead déjà escaladé ne bloque pas le lot suivant.
            sweep_hot_leads(now=CONTROLE + datetime.timedelta(minutes=15))
            self.assertTrue(self._escalades(lead=tiede).exists())

    def test_lalerte_SLA_Meta_de_ladsengine_ne_vaut_pas_escalade(self):
        """PUB68 émet le même type d'événement sous un autre titre : elle ne
        doit ni éteindre ni doubler ce filet."""
        lead = self._lead()
        Notification.objects.create(
            company=self.company, recipient=self.commerciale,
            event_type=EventType.HOT_LEAD_UNREAD,
            title='Lead Meta sans premier contact',
            link=f'/crm/leads?lead={lead.pk}')
        sweep_hot_leads(now=CONTROLE)
        self.assertEqual(self._escalades(self.commerciale, lead).count(), 1)
