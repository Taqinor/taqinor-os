"""CAD75 — « cadences échues à clore » : les rendre VISIBLES, jamais les clore.

Constat de l'audit L3 du 21/09/2026 : ``cloturer_cadence`` n'a qu'un seul
appelant, ``marquer_etape_relance`` — tant que l'issue de la DERNIÈRE touche
n'est pas saisie, le lead n'entre jamais au Froid, ne reçoit ni étiquette ni
réveil J30/J60, et reste au milieu du pipeline avec une touche en retard.
Aucune tâche planifiée ne clôt une cadence échue.

Ce module verrouille les deux garanties de la tâche :

  * un lead dont la dernière touche est échue depuis plus de N jours APPARAÎT
    dans la liste ;
  * **aucun lead n'est clos automatiquement** — le sélecteur est une lecture
    pure : ni étape traitée, ni étape de réveil créée, ni étape du pipeline
    changée, ni étiquette posée.

Le temps est GELÉ : « échu depuis plus de N jours » est exactement la question
qu'une horloge vivante rend instable.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.selectors import cadences_echues_a_clore
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Jeudi 10 septembre 2026, 12 h à Casablanca — jour ouvré, en pleine fenêtre.
MAINTENANT = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = MAINTENANT.date()

#: Seuil de retard utilisé par CE test. Le sélecteur n'en porte AUCUN par
#: défaut (« zéro chiffre inventé » : ni le texte de la tâche ni un réglage
#: société ne fixe N) — c'est l'appelant qui le fournit, donc le test aussi.
SEUIL_JOURS = 7


def _company(slug):
    company = Company.objects.create(slug=slug, nom=slug)
    CompanyProfile.objects.create(company=company)
    return company


class _Base(TestCase):
    slug = 'cad75'

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, nom, *, stage=stages.CONTACTED, owner=-1, perdu=False,
              archive=False, company=None):
        return Lead.objects.create(
            company=company or self.company, nom=nom, prenom='Benali',
            ville='Bouskoura', stage=stage, perdu=perdu,
            is_archived=archive,
            owner=(self.acteur if owner == -1 else owner))

    def _touche(self, lead, *, due_jours, statut=RelanceEtape.Statut.A_FAIRE,
                cadence='contact', ordre=1, canal=RelanceEtape.Canal.APPEL,
                libelle='Appel de relance', company=None):
        due = AUJOURDHUI - datetime.timedelta(days=due_jours)
        quand = datetime.datetime.combine(
            due, datetime.time(10, 0), tzinfo=horaires.CASABLANCA)
        return RelanceEtape.objects.create(
            company=company or lead.company, lead=lead, cadence=cadence,
            ordre=ordre, due_at=quand, due_date=due, canal=canal,
            libelle=libelle, statut=statut)

    def _liste(self, **kw):
        kw.setdefault('jours', SEUIL_JOURS)
        return cadences_echues_a_clore(self.company, self.acteur, **kw)

    def _ids(self, **kw):
        return [ligne['lead_id'] for ligne in self._liste(**kw)]


class LaListeTests(_Base):
    slug = 'cad75-liste'

    def test_une_touche_echue_au_dela_du_seuil_apparait(self):
        """Le cœur du Done : le dossier abandonné devient VISIBLE."""
        lead = self._lead('Abandonne')
        self._touche(lead, due_jours=SEUIL_JOURS + 3)
        lignes = self._liste()
        self.assertEqual([lig['lead_id'] for lig in lignes], [lead.id])
        self.assertEqual(lignes[0]['jours_de_retard'], SEUIL_JOURS + 3)
        self.assertEqual(lignes[0]['cadence'], 'contact')
        self.assertEqual(lignes[0]['canal'], RelanceEtape.Canal.APPEL)

    def test_une_touche_en_retard_sous_le_seuil_n_apparait_pas(self):
        """En retard d'un jour, ce n'est pas un dossier abandonné : c'est la
        file du jour de la commerciale, qui a son propre écran."""
        lead = self._lead('Hier')
        self._touche(lead, due_jours=1)
        self.assertEqual(self._ids(), [])

    def test_le_seuil_est_strict(self):
        """Exactement N jours de retard n'est pas ENCORE « plus de N jours »."""
        lead = self._lead('Pile')
        self._touche(lead, due_jours=SEUIL_JOURS)
        self.assertEqual(self._ids(), [])

    def test_une_touche_deja_traitee_n_apparait_pas(self):
        lead = self._lead('Traite')
        self._touche(lead, due_jours=SEUIL_JOURS + 5,
                     statut=RelanceEtape.Statut.FAIT)
        self.assertEqual(self._ids(), [])

    def test_un_lead_deja_au_froid_n_apparait_pas(self):
        """Le Froid EST le résultat de la clôture : proposer de clore un lead
        déjà clos remplirait la liste de bruit."""
        lead = self._lead('DejaFroid', stage=stages.COLD)
        self._touche(lead, due_jours=SEUIL_JOURS + 5)
        self.assertEqual(self._ids(), [])

    def test_les_archives_et_les_perdus_n_apparaissent_pas(self):
        archive = self._lead('Archive', archive=True)
        self._touche(archive, due_jours=SEUIL_JOURS + 5)
        perdu = self._lead('Perdu', perdu=True)
        self._touche(perdu, due_jours=SEUIL_JOURS + 5)
        self.assertEqual(self._ids(), [])

    def test_une_touche_de_reveil_n_apparait_pas(self):
        """``cloturer_cadence`` refuse de clore un plan de réveil (boucle
        infinie de réveils) : il n'y a donc aucune clôture à proposer."""
        lead = self._lead('Dormant')
        self._touche(lead, due_jours=SEUIL_JOURS + 20, cadence='reveil')
        self.assertEqual(self._ids(), [])

    def test_un_lead_n_apparait_qu_une_fois_sur_son_retard_le_plus_ancien(self):
        lead = self._lead('DeuxPlans')
        self._touche(lead, due_jours=SEUIL_JOURS + 2, cadence='apres_devis',
                     ordre=3)
        self._touche(lead, due_jours=SEUIL_JOURS + 9, cadence='contact',
                     ordre=1)
        lignes = self._liste()
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['jours_de_retard'], SEUIL_JOURS + 9)

    def test_tri_du_retard_le_plus_ancien_au_plus_recent(self):
        vieux = self._lead('Vieux')
        self._touche(vieux, due_jours=SEUIL_JOURS + 30)
        recent = self._lead('Recent')
        self._touche(recent, due_jours=SEUIL_JOURS + 1)
        self.assertEqual(self._ids(), [vieux.id, recent.id])


class AucuneClotureAutomatiqueTests(_Base):
    slug = 'cad75-lecture'

    def test_la_liste_ne_clot_RIEN(self):
        """Garde-fou de la tâche : « aucun lead n'est clos automatiquement ».

        Après l'appel : la touche reste ``a_faire``, le lead reste à son
        étape, aucune étape de réveil n'est née, aucune étiquette n'est posée.
        """
        lead = self._lead('Intact')
        etape = self._touche(lead, due_jours=SEUIL_JOURS + 40)
        avant_etapes = RelanceEtape.objects.count()

        self.assertEqual(self._ids(), [lead.id])

        etape.refresh_from_db()
        lead.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertIsNone(etape.traite_le)
        self.assertIsNone(etape.traite_par_id)
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertFalse(lead.perdu)
        self.assertEqual(lead.tags or '', '')
        self.assertEqual(RelanceEtape.objects.count(), avant_etapes)
        self.assertFalse(
            RelanceEtape.objects.filter(cadence='reveil').exists())


class SeuilEtIsolationTests(_Base):
    slug = 'cad75-garde'

    def test_un_seuil_illisible_dit_QUEL_champ_est_en_cause(self):
        """Règle fondateur du 08/09 : jamais un refus générique — le message
        nomme le champ fautif, en français."""
        lead = self._lead('Peu importe')
        self._touche(lead, due_jours=99)
        with self.assertRaises(ValueError) as boite:
            self._liste(jours='beaucoup')
        self.assertIn('jours', str(boite.exception))
        with self.assertRaises(ValueError) as boite:
            self._liste(jours=-1)
        self.assertIn('jours', str(boite.exception))

    def test_une_societe_ne_voit_pas_les_cadences_echues_de_l_autre(self):
        voisine = _company(f'{self.slug}-voisine')
        etranger = self._lead('Etranger', owner=None, company=voisine)
        self._touche(etranger, due_jours=SEUIL_JOURS + 12, company=voisine)
        mien = self._lead('Mien')
        self._touche(mien, due_jours=SEUIL_JOURS + 12)
        self.assertEqual(self._ids(), [mien.id])
