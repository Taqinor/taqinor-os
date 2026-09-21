"""CAD83 — la file du jour départage enfin par priorité puis par score.

La ligne de relance affiche DEUX signaux de priorisation — le badge de
priorité (`RelanceEtapeRow.jsx`) et le `ScoreBadge` servi par
`RelanceEtapeSerializer` — et le sélecteur n'en utilisait AUCUN : il triait
exclusivement par `due_at`, `due_date`, `ordre`. Deux dossiers dus à la même
minute se présentaient donc dans un ordre arbitraire (l'ordre de l'index),
et la commerciale devait relire toute la tranche pour retrouver le dossier
chaud.

Ces tests verrouillent les deux moitiés de la décision :

  * à heure ÉGALE, la priorité haute passe devant, puis le score le plus
    élevé — c'est le départage demandé ;
  * à heures DIFFÉRENTES, l'ordre horaire est intact : une touche de 11 h
    en priorité haute reste DERRIÈRE une touche de 9 h en priorité basse.
    C'est le garde-fou : `heure_cible` est un rendez-vous pris avec le
    client, aucun score ne le déplace.

Le temps est gelé (`testkit.time.frozen`) : « aujourd'hui » et « en retard »
sont exactement ce qu'une horloge vivante rend instable.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.selectors import relance_etapes_dues
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mercredi 9 septembre 2026, 8 h à Casablanca — jour ouvré, avant toutes les
#: heures testées, donc toutes les touches du jour sont « à venir ».
MERCREDI = datetime.datetime(2026, 9, 9, 8, 0, tzinfo=horaires.CASABLANCA)


def _heure(heure, minute=0, jour=9):
    return datetime.datetime(2026, 9, jour, heure, minute,
                             tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    """Société + responsable + horloge gelée sur MERCREDI."""

    slug = 'cad83'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD83 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self._compteur = 0

    def _lead(self, nom, *, priorite=Lead.Priorite.NORMALE, score=None):
        self._compteur += 1
        return Lead.objects.create(
            company=self.company, nom=nom, stage=stages.NEW,
            owner=self.acteur, priorite=priorite, score=score,
            telephone=f'+21266833{self._compteur:04d}')

    def _touche(self, lead, quand, *, ordre=1):
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=ordre,
            due_at=quand, due_date=quand.date(),
            canal=RelanceEtape.Canal.APPEL, libelle='Appel')

    def _file(self, scope='all'):
        return list(relance_etapes_dues(
            self.company, self.acteur, scope=scope,
            today=MERCREDI.date()).values_list('pk', flat=True))


class DepartageAHeureEgaleTests(_Base):
    """À la MÊME minute, priorité d'abord, puis score."""

    slug = 'cad83-egal'

    def test_priorite_haute_passe_devant_a_heure_egale(self):
        basse = self._lead('Basse', priorite=Lead.Priorite.BASSE)
        normale = self._lead('Normale', priorite=Lead.Priorite.NORMALE)
        haute = self._lead('Haute', priorite=Lead.Priorite.HAUTE)
        # Créées dans l'ordre INVERSE de l'ordre attendu : si le tri ne
        # départageait pas, l'ordre d'insertion ressortirait tel quel.
        t_basse = self._touche(basse, _heure(10))
        t_normale = self._touche(normale, _heure(10))
        t_haute = self._touche(haute, _heure(10))
        self.assertEqual(
            self._file(), [t_haute.pk, t_normale.pk, t_basse.pk])

    def test_score_departage_a_priorite_egale(self):
        faible = self._lead('Faible', score=12)
        fort = self._lead('Fort', score=88)
        sans = self._lead('Sans score', score=None)
        t_faible = self._touche(faible, _heure(10))
        t_fort = self._touche(fort, _heure(10))
        t_sans = self._touche(sans, _heure(10))
        # Score décroissant, les touches SANS score en dernier : une absence
        # de score n'est pas un score de zéro, mais elle ne doit pas non plus
        # remonter en tête de la tranche.
        self.assertEqual(
            self._file(), [t_fort.pk, t_faible.pk, t_sans.pk])

    def test_priorite_prime_sur_le_score(self):
        haute_sans_score = self._lead(
            'Haute sans score', priorite=Lead.Priorite.HAUTE, score=None)
        normale_top = self._lead(
            'Normale 99', priorite=Lead.Priorite.NORMALE, score=99)
        t_normale = self._touche(normale_top, _heure(10))
        t_haute = self._touche(haute_sans_score, _heure(10))
        self.assertEqual(self._file(), [t_haute.pk, t_normale.pk])

    def test_deux_touches_du_meme_lead_restent_dans_l_ordre_du_plan(self):
        lead = self._lead('Aziz', priorite=Lead.Priorite.HAUTE, score=70)
        deuxieme = self._touche(lead, _heure(10), ordre=2)
        premiere = self._touche(lead, _heure(10), ordre=1)
        self.assertEqual(self._file(), [premiere.pk, deuxieme.pk])


class HeureIntouchableTests(_Base):
    """À heures DIFFÉRENTES, l'ordre horaire est conservé, sans exception."""

    slug = 'cad83-heure'

    def test_l_heure_prime_sur_la_priorite(self):
        basse = self._lead('Basse tôt', priorite=Lead.Priorite.BASSE, score=5)
        haute = self._lead('Haute tard', priorite=Lead.Priorite.HAUTE,
                           score=99)
        t_haute = self._touche(haute, _heure(11))
        t_basse = self._touche(basse, _heure(9))
        # 9 h avant 11 h : le rendez-vous pris avec le client de 9 h n'est
        # jamais doublé par le dossier chaud de 11 h.
        self.assertEqual(self._file(), [t_basse.pk, t_haute.pk])

    def test_le_retard_passe_devant_le_jour_meme(self):
        hier_basse = self._lead('Hier', priorite=Lead.Priorite.BASSE)
        aujourdhui_haute = self._lead(
            'Aujourd_hui', priorite=Lead.Priorite.HAUTE, score=99)
        t_aujourdhui = self._touche(aujourdhui_haute, _heure(9))
        t_hier = self._touche(hier_basse, _heure(16, jour=8))
        self.assertEqual(self._file(), [t_hier.pk, t_aujourdhui.pk])

    def test_les_touches_sans_heure_restent_en_dernier(self):
        avec = self._lead('Avec heure', priorite=Lead.Priorite.BASSE)
        sans = self._lead('Sans heure', priorite=Lead.Priorite.HAUTE,
                          score=99)
        t_sans = RelanceEtape.objects.create(
            company=self.company, lead=sans, cadence='contact', ordre=1,
            due_at=None, due_date=MERCREDI.date(),
            canal=RelanceEtape.Canal.APPEL, libelle='Appel')
        t_avec = self._touche(avec, _heure(18))
        # MRY5 inchangé : une touche sans heure connue ne remonte pas en tête
        # de la file, même en priorité haute avec le meilleur score.
        self.assertEqual(self._file(), [t_avec.pk, t_sans.pk])


class IsolationSocieteTests(_Base):
    """Le départage ne fait pas traverser les sociétés."""

    slug = 'cad83-tenant'

    def test_une_touche_d_une_autre_societe_n_entre_pas_dans_la_file(self):
        autre = Company.objects.create(nom='CAD83 Autre', slug='cad83-autre')
        CompanyProfile.objects.get_or_create(company=autre)
        autre_resp = User.objects.create_user(
            username='cad83-autre-resp', password='x',
            role_legacy='responsable', company=autre)
        lead_autre = Lead.objects.create(
            company=autre, nom='Voisin', stage=stages.NEW, owner=autre_resp,
            priorite=Lead.Priorite.HAUTE, score=99,
            telephone='+212668339999')
        RelanceEtape.objects.create(
            company=autre, lead=lead_autre, cadence='contact', ordre=1,
            due_at=_heure(10), due_date=MERCREDI.date(),
            canal=RelanceEtape.Canal.APPEL, libelle='Appel')
        mien = self._lead('Mien', priorite=Lead.Priorite.BASSE)
        t_mien = self._touche(mien, _heure(10))
        self.assertEqual(self._file(), [t_mien.pk])
