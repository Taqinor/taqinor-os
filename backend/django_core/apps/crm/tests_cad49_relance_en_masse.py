"""CAD49 — « définir la relance » en masse ne double plus le moteur.

Le chemin de la FICHE passe par le moteur (``reporter_prochaine_touche``) :
la touche bouge, ses suivantes glissent, l'ancre suit. L'action en MASSE,
elle, écrivait directement ``Lead.relance_date`` sans rien dire au moteur —
la fiche affichait une date, la frise une autre, et au premier geste de
cadence le serveur réécrivait la date depuis la touche. C'était le « second
système de rappel concurrent » que tout le reste du code s'interdit.

Décision : REFUSER l'action en masse sur les leads à cadence active, en
NOMMANT la raison (règle fondateur du 08/09 : jamais un refus muet). Passer
N plans par ``reporter_prochaine_touche`` en masse serait pire — des
centaines de plans décalés d'un clic, avec leurs suivantes et leurs ancres.

Le Done est le lot MIXTE : dans la même sélection, les leads à cadence sont
refusés avec un motif, les autres traités comme avant.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import (
    MOTIF_BULK_CADENCE_ACTIVE, apply_bulk_action)
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 22 septembre 2026, 10 h à Casablanca.
MARDI = datetime.datetime(2026, 9, 22, 10, 0, tzinfo=horaires.CASABLANCA)
RELANCE_VISEE = datetime.date(2026, 9, 30)


class _Base(TestCase):
    slug = 'cad49'

    def setUp(self):
        gel = frozen(MARDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD49 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self._compteur = 0

    def _lead(self, nom, *, avec_cadence=False, relance_date=None):
        self._compteur += 1
        lead = Lead.objects.create(
            company=self.company, nom=nom, stage=stages.CONTACTED,
            owner=self.acteur, relance_date=relance_date,
            telephone=f'+21266104{self._compteur:04d}')
        if avec_cadence:
            RelanceEtape.objects.create(
                company=self.company, lead=lead, cadence='contact', ordre=1,
                due_at=MARDI, due_date=MARDI.date(),
                canal=RelanceEtape.Canal.APPEL, libelle="Appel d'ouverture",
                cadence_depart=MARDI)
        return lead

    def _bulk(self, op, leads, **params):
        return apply_bulk_action(
            company=self.company, user=self.acteur,
            lead_ids=[lead.id for lead in leads], op=op, params=params)


class LotMixteTests(_Base):
    slug = 'cad49-mixte'

    def setUp(self):
        super().setUp()
        self.avec = self._lead('Avec cadence', avec_cadence=True)
        self.sans = self._lead('Sans cadence')

    def test_set_relance_refuse_le_lead_a_cadence_et_traite_l_autre(self):
        res = self._bulk('set_relance', [self.avec, self.sans],
                         relance_date=RELANCE_VISEE.isoformat())
        self.assertEqual(res['updated'], 1)
        self.assertEqual([s['id'] for s in res['skipped']], [self.avec.id])
        self.avec.refresh_from_db()
        self.sans.refresh_from_db()
        # Le lead à cadence n'a PAS bougé ; l'autre porte la date demandée.
        self.assertIsNone(self.avec.relance_date)
        self.assertEqual(self.sans.relance_date, RELANCE_VISEE)

    def test_le_refus_nomme_sa_raison(self):
        res = self._bulk('set_relance', [self.avec],
                         relance_date=RELANCE_VISEE.isoformat())
        self.assertEqual(len(res['skipped']), 1)
        self.assertEqual(res['skipped'][0]['reason'],
                         MOTIF_BULK_CADENCE_ACTIVE)
        # Le motif dit QUOI faire à la place, pas seulement « non ».
        self.assertIn('Reporter', res['skipped'][0]['reason'])

    def test_clear_relance_refuse_aussi(self):
        avec = self._lead('Avec date et cadence', avec_cadence=True,
                          relance_date=RELANCE_VISEE)
        sans = self._lead('Avec date seule', relance_date=RELANCE_VISEE)
        res = self._bulk('clear_relance', [avec, sans])
        self.assertEqual(res['updated'], 1)
        self.assertEqual([s['id'] for s in res['skipped']], [avec.id])
        avec.refresh_from_db()
        sans.refresh_from_db()
        self.assertEqual(avec.relance_date, RELANCE_VISEE)
        self.assertIsNone(sans.relance_date)


class TouchesClosesNonBloquantesTests(_Base):
    """Un plan ENTIÈREMENT traité n'est plus une cadence active : le lead
    redevient éligible à l'action en masse."""

    slug = 'cad49-closes'

    def test_un_plan_tout_traite_ne_bloque_plus(self):
        lead = self._lead('Plan terminé')
        RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=1,
            due_at=MARDI, due_date=MARDI.date(),
            canal=RelanceEtape.Canal.APPEL, libelle="Appel d'ouverture",
            statut=RelanceEtape.Statut.FAIT, traite_par=self.acteur,
            traite_le=MARDI)
        res = self._bulk('set_relance', [lead],
                         relance_date=RELANCE_VISEE.isoformat())
        self.assertEqual(res['updated'], 1)
        self.assertEqual(res['skipped'], [])

    def test_une_etape_de_filet_ouverte_bloque_aussi(self):
        # Une étape de filet est une touche ouverte du moteur : sa date
        # écraserait la saisie en masse exactement comme un barreau.
        lead = self._lead('Filet ouvert')
        RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='generique', ordre=1,
            due_at=MARDI, due_date=MARDI.date(),
            canal=RelanceEtape.Canal.APPEL,
            libelle='Préparer et envoyer le devis (ou fixer un rappel)')
        res = self._bulk('set_relance', [lead],
                         relance_date=RELANCE_VISEE.isoformat())
        self.assertEqual(res['updated'], 0)
        self.assertEqual(len(res['skipped']), 1)


class AutresActionsInchangeesTests(_Base):
    """Garde-fou : seules `set_relance`/`clear_relance` sont concernées."""

    slug = 'cad49-autres'

    def test_set_priorite_traite_aussi_les_leads_a_cadence(self):
        lead = self._lead('Avec cadence', avec_cadence=True)
        res = self._bulk('set_priorite', [lead], priorite='haute')
        self.assertEqual(res['updated'], 1)
        self.assertEqual(res['skipped'], [])


class IsolationSocieteTests(_Base):
    """La cadence d'une AUTRE société ne bloque rien ici."""

    slug = 'cad49-tenant'

    def test_une_touche_d_une_autre_societe_ne_bloque_pas(self):
        autre = Company.objects.create(nom='CAD49 Autre', slug='cad49-autre')
        CompanyProfile.objects.get_or_create(company=autre)
        autre_resp = User.objects.create_user(
            username='cad49-autre-resp', password='x',
            role_legacy='responsable', company=autre)
        lead_autre = Lead.objects.create(
            company=autre, nom='Voisin', stage=stages.CONTACTED,
            owner=autre_resp, telephone='+212661049999')
        RelanceEtape.objects.create(
            company=autre, lead=lead_autre, cadence='contact', ordre=1,
            due_at=MARDI, due_date=MARDI.date(),
            canal=RelanceEtape.Canal.APPEL, libelle="Appel d'ouverture")
        mien = self._lead('Mien sans cadence')
        res = self._bulk('set_relance', [mien],
                         relance_date=RELANCE_VISEE.isoformat())
        self.assertEqual(res['updated'], 1)
        self.assertEqual(res['skipped'], [])
