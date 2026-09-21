"""CAD116 — le rappel de 08:30 donne enfin une prise, et n'oublie personne.

Le digest disait « N relance(s) à faire aujourd'hui » et renvoyait au
cockpit : face à trente touches, aucune prise — aucun nom cité, aucun ordre
suggéré. Deux angles morts du même envoi :

  * il ne citait AUCUN dossier alors que la file est déjà triée (en retard
    d'abord, puis l'heure, puis la priorité et le score) — les données
    étaient dans la même requête ;
  * un lead SANS propriétaire, ou dont le propriétaire est DÉSACTIVÉ,
    n'entrait dans aucun digest, puisque les destinataires sont les owners
    ACTIFS.

Ce module verrouille les deux moitiés du Done : le digest CITE les dossiers
prioritaires, et il SIGNALE les leads sans propriétaire — au responsable par
défaut de la société, jamais à un prénom codé en dur.

Temps gelé : « dû aujourd'hui » et « en retard » sont exactement ce qu'une
horloge vivante rend instable.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.management.commands.notifier_relances_dues import (
    DIGEST_DOSSIERS_CITES, notifier_relances_dues)
from apps.crm.models import Lead, RelanceEtape
from apps.notifications.models import EventType, Notification
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 22 septembre 2026, 8 h 30 à Casablanca — l'heure du digest.
MARDI = datetime.datetime(2026, 9, 22, 8, 30, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad116'

    def setUp(self):
        gel = frozen(MARDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD116 Solaire', slug=self.slug)
        self.profil, _ = CompanyProfile.objects.get_or_create(
            company=self.company)
        self.commerciale = User.objects.create_user(
            username=f'{self.slug}-com', password='x',
            role_legacy='commercial', company=self.company)
        self._compteur = 0

    def _lead(self, nom, *, owner='commerciale', priorite=None, score=None):
        self._compteur += 1
        proprietaire = (self.commerciale if owner == 'commerciale'
                        else owner)
        kw = {}
        if priorite is not None:
            kw['priorite'] = priorite
        if score is not None:
            kw['score'] = score
        return Lead.objects.create(
            company=self.company, nom=nom, stage=stages.CONTACTED,
            owner=proprietaire, telephone=f'+21266111{self._compteur:04d}',
            **kw)

    def _touche(self, lead, *, jours=0, heure=10, libelle='Appel de suivi'):
        quand = datetime.datetime(
            2026, 9, 22 + jours, heure, 0, tzinfo=horaires.CASABLANCA)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=1,
            due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date(),
            canal=RelanceEtape.Canal.APPEL, libelle=libelle,
            cadence_depart=quand)

    def _digest(self, user):
        return Notification.objects.filter(
            recipient=user, event_type=EventType.RELANCE_DUE).first()

    def _lancer(self):
        return notifier_relances_dues(today=MARDI.date())


class DossiersCitesTests(_Base):
    slug = 'cad116-cites'

    def test_le_digest_cite_les_premiers_dossiers(self):
        for nom, heure in (('Aziz', 9), ('Brahim', 11), ('Chadia', 15)):
            self._touche(self._lead(nom), heure=heure)
        self._lancer()
        digest = self._digest(self.commerciale)
        self.assertIsNotNone(digest)
        for nom in ('Aziz', 'Brahim', 'Chadia'):
            self.assertIn(nom, digest.body)

    def test_il_n_en_cite_pas_plus_de_trois(self):
        noms = ['Lead%02d' % i for i in range(8)]
        for i, nom in enumerate(noms):
            self._touche(self._lead(nom), heure=9 + i)
        self._lancer()
        digest = self._digest(self.commerciale)
        cites = [n for n in noms if n in digest.body]
        self.assertEqual(len(cites), DIGEST_DOSSIERS_CITES, cites)

    def test_les_dossiers_suivent_l_ordre_de_la_file(self):
        # En retard d'abord : le dossier d'hier passe devant ceux du jour.
        self._touche(self._lead('Hier'), jours=-1, heure=16)
        self._touche(self._lead('Aujourdhui'), heure=9)
        self._lancer()
        corps = self._digest(self.commerciale).body
        self.assertLess(corps.index('Hier'), corps.index('Aujourdhui'))

    def test_le_retard_est_dit(self):
        self._touche(self._lead('Hier'), jours=-1, heure=16)
        self._lancer()
        self.assertIn('en retard', self._digest(self.commerciale).body)

    def test_le_total_reste_dans_le_titre(self):
        for nom in ('Aziz', 'Brahim'):
            self._touche(self._lead(nom))
        self._lancer()
        self.assertEqual(
            self._digest(self.commerciale).title,
            "2 relance(s) à faire aujourd'hui")


class LeadsSansResponsableTests(_Base):
    slug = 'cad116-orphelins'

    def setUp(self):
        super().setUp()
        self.patronne = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.profil.responsable_defaut_leads = self.patronne
        self.profil.save(update_fields=['responsable_defaut_leads'])

    def test_un_lead_sans_proprietaire_est_signale_au_responsable_defaut(self):
        self._touche(self._lead('Orphelin', owner=None))
        self._lancer()
        digest = self._digest(self.patronne)
        self.assertIsNotNone(digest)
        self.assertIn('sans responsable', (digest.title or '') + digest.body)

    def test_un_proprietaire_desactive_compte_aussi(self):
        parti = User.objects.create_user(
            username=f'{self.slug}-parti', password='x',
            role_legacy='commercial', company=self.company, is_active=False)
        self._touche(self._lead('Dossier du parti', owner=parti))
        self._lancer()
        digest = self._digest(self.patronne)
        self.assertIsNotNone(digest)
        self.assertIn('sans responsable', (digest.title or '') + digest.body)

    def test_la_ligne_rejoint_le_digest_du_responsable_quand_il_en_a_un(self):
        # La patronne a un dossier à elle : UN seul message, qui porte les
        # deux informations.
        self._touche(self._lead('A elle', owner=self.patronne))
        self._touche(self._lead('Orphelin', owner=None))
        self._lancer()
        digests = Notification.objects.filter(
            recipient=self.patronne, event_type=EventType.RELANCE_DUE)
        self.assertEqual(digests.count(), 1)
        self.assertIn('sans responsable', digests.first().body)

    def test_sans_orphelin_le_responsable_defaut_ne_recoit_rien_de_plus(self):
        self._touche(self._lead('A moi'))
        self._lancer()
        self.assertIsNone(self._digest(self.patronne))

    def test_sans_responsable_defaut_configure_rien_n_est_invente(self):
        self.profil.responsable_defaut_leads = None
        self.profil.save(update_fields=['responsable_defaut_leads'])
        self._touche(self._lead('Orphelin', owner=None))
        self._lancer()
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.RELANCE_DUE).count(), 0)

    def test_le_digest_reste_idempotent_dans_la_journee(self):
        self._touche(self._lead('Orphelin', owner=None))
        self._lancer()
        self._lancer()
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.patronne,
                event_type=EventType.RELANCE_DUE).count(), 1)


class IsolationSocieteTests(_Base):
    slug = 'cad116-tenant'

    def test_les_orphelins_d_une_autre_societe_ne_comptent_pas(self):
        patronne = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.profil.responsable_defaut_leads = patronne
        self.profil.save(update_fields=['responsable_defaut_leads'])

        autre = Company.objects.create(nom='CAD116 Autre',
                                       slug='cad116-autre')
        CompanyProfile.objects.get_or_create(company=autre)
        lead_autre = Lead.objects.create(
            company=autre, nom='Orphelin voisin', stage=stages.CONTACTED,
            owner=None, telephone='+212661119999')
        RelanceEtape.objects.create(
            company=autre, lead=lead_autre, cadence='contact', ordre=1,
            due_at=MARDI, due_date=MARDI.date(),
            canal=RelanceEtape.Canal.APPEL, libelle='Appel de suivi')

        self._lancer()
        self.assertIsNone(self._digest(patronne))
