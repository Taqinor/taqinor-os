"""RLC2 — Le journal « ce qui s'est passé » du plan de relance, et l'état du
lead en une phrase.

Relevé fondateur du 08/09/2026 : « on ne voit pas d'un coup d'œil ce qui s'est
passé dans le plan de relance ». Ce fichier verrouille les trois promesses du
panneau :

  * ORDRE CHRONOLOGIQUE — une histoire, du plus ancien au plus récent ;
  * CAUSES EXACTES — chaque ligne dit POURQUOI (issue saisie, motif d'arrêt,
    motif de retrait), et un geste du MOTEUR ne porte JAMAIS un nom d'humain ;
  * ISOLATION SOCIÉTÉ — un lead d'une autre société est « inconnu », jamais
    lisible, et jamais distingué d'un lead inexistant.

Plus la garantie qui rend le panneau sûr : LECTURE PURE — le journal n'écrit
rien, pas une activité, pas une touche.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.selectors import JOURNAL_TYPES, journal_relance
from apps.crm.services import (
    annuler_touche_relance, initialiser_plan_relance, marquer_etape_relance)
from apps.parametres.models import CompanyProfile

User = get_user_model()

LUNDI_PASSE = datetime.datetime(2026, 9, 7, 12, 0, tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'rlc2'

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)
        self.etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI_PASSE, cadence='contact')
        self.assertTrue(self.etapes)

    def _journal(self):
        journal = journal_relance(self.company, self.acteur, self.lead.pk)
        self.assertIsNotNone(journal)
        return journal

    def _lignes(self, journal, nature):
        return [ligne for ligne in journal['lignes']
                if ligne['type'] == nature]


class OrdreEtNaturesTests(_Base):
    slug = 'rlc2-ordre'

    def test_les_lignes_sont_en_ordre_chronologique_et_toutes_typees(self):
        marquer_etape_relance(
            self.etapes[0], self.acteur, RelanceEtape.Statut.FAIT,
            outcome='joint')

        journal = self._journal()

        quands = [ligne['quand'] for ligne in journal['lignes']]
        self.assertEqual(quands, sorted(quands))
        self.assertTrue(journal['lignes'])
        for ligne in journal['lignes']:
            self.assertIn(ligne['type'], JOURNAL_TYPES)
            self.assertTrue(ligne['titre'].strip())

    def test_lecho_de_chatter_dune_touche_ne_fait_pas_une_ligne_de_plus(self):
        """La touche EST la ligne : sa propre ligne de chatter (« Touche « … »
        marquée faite. ») sert à retrouver l'issue, jamais à doubler l'entrée."""
        marquer_etape_relance(
            self.etapes[0], self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')

        journal = self._journal()

        self.assertEqual(len(self._lignes(journal, 'touche_faite')), 1)
        self.assertFalse([ligne for ligne in journal['lignes']
                          if 'marquée faite' in ligne['titre']])


class CausesTests(_Base):
    slug = 'rlc2-causes'

    def test_chaque_ligne_dit_sa_cause(self):
        ouvertes_avant = self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).count()
        self.assertGreater(ouvertes_avant, 1)

        marquer_etape_relance(
            self.etapes[0], self.acteur, RelanceEtape.Statut.FAIT,
            outcome='joint')
        journal = self._journal()

        # La touche FAITE porte l'ISSUE saisie, en clair, et le nom de l'humain.
        faites = self._lignes(journal, 'touche_faite')
        self.assertEqual(len(faites), 1)
        self.assertEqual(faites[0]['cause'], 'Joint')
        self.assertEqual(faites[0]['par'], self.acteur.username)

        # Les touches RETIRÉES par le moteur portent le motif — et AUCUN nom.
        retirees = self._lignes(journal, 'touche_annulee')
        self.assertEqual(len(retirees), ouvertes_avant - 1)
        for ligne in retirees:
            self.assertEqual(ligne['cause'], 'joint')
            self.assertEqual(ligne['par'], '')

        # L'arrêt de cadence dit son motif, sans auteur (note système).
        arrets = self._lignes(journal, 'cadence_arretee')
        self.assertTrue(arrets)
        self.assertEqual(arrets[-1]['cause'], 'joint')
        self.assertEqual(arrets[-1]['par'], '')

        # Le changement d'étape du funnel dit la cause écrite par le moteur.
        funnel = self._lignes(journal, 'etape_funnel')
        self.assertTrue(funnel)
        self.assertIn(stages.STAGE_LABELS[stages.NEW], funnel[-1]['titre'])
        self.assertIn(stages.STAGE_LABELS[stages.CONTACTED],
                      funnel[-1]['titre'])
        self.assertTrue(funnel[-1]['cause'].strip())

        # Le filet posé automatiquement est visible comme tel.
        self.assertTrue(self._lignes(journal, 'filet_pose'))

    def test_une_touche_sautee_porte_sa_note_comme_cause(self):
        marquer_etape_relance(
            self.etapes[0], self.acteur, RelanceEtape.Statut.SAUTEE,
            note='Client en congé')

        sautees = self._lignes(self._journal(), 'touche_sautee')

        self.assertEqual(len(sautees), 1)
        self.assertEqual(sautees[0]['cause'], 'Client en congé')
        self.assertEqual(sautees[0]['par'], self.acteur.username)

    def test_une_annulation_de_touche_apparait_dans_le_journal(self):
        """RLC1 × RLC2 — « tout ce qui s'annule se journalise » : le retour
        arrière est une ligne du journal, pas un trou dans l'histoire."""
        marquer_etape_relance(
            self.etapes[0], self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')
        annuler_touche_relance(self.etapes[0], self.acteur)

        annulations = self._lignes(self._journal(), 'annulation')

        self.assertEqual(len(annulations), 1)
        self.assertIn(self.acteur.username, annulations[0]['titre'])

    def test_le_message_ouvert_est_une_ligne(self):
        from apps.crm.services import journaliser_whatsapp_ouvert

        message = next(
            (e for e in self.etapes
             if e.canal == RelanceEtape.Canal.WHATSAPP), None)
        if message is None:  # gabarit sans touche message : rien à prouver ici
            self.skipTest("le gabarit de contact ne porte aucune touche message")
        journaliser_whatsapp_ouvert(message, self.acteur)

        ouverts = self._lignes(self._journal(), 'message_ouvert')

        self.assertEqual(len(ouverts), 1)
        self.assertEqual(ouverts[0]['par'], self.acteur.username)


class EtatCourantTests(_Base):
    slug = 'rlc2-etat'

    def test_letat_dit_letape_la_cadence_et_la_prochaine_touche(self):
        etat = self._journal()['etat']

        self.assertEqual(etat['stage'], stages.NEW)
        self.assertEqual(etat['stage_libelle'],
                         stages.STAGE_LABELS[stages.NEW])
        self.assertEqual(etat['cadence_active'], 'contact')
        self.assertIsNotNone(etat['prochaine_touche'])
        self.assertIn(etat['stage_libelle'], etat['phrase'])
        self.assertIn(etat['prochaine_touche']['libelle'], etat['phrase'])

    def test_sans_touche_ouverte_la_phrase_le_DIT_sans_rien_inventer(self):
        self.lead.relance_etapes.all().delete()

        etat = self._journal()['etat']

        self.assertIsNone(etat['prochaine_touche'])
        self.assertEqual(etat['cadence_active'], '')
        self.assertIn('aucune touche ouverte', etat['phrase'])
        # Règle des faits vérifiés : aucun tiret ni zéro de remplissage.
        self.assertNotIn('—', etat['phrase'])

    def test_le_dernier_echange_porte_son_issue(self):
        marquer_etape_relance(
            self.etapes[0], self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')

        echange = self._journal()['etat']['dernier_echange']

        self.assertIsNotNone(echange)
        self.assertEqual(echange['issue'], 'Non joint')
        self.assertEqual(echange['par'], self.acteur.username)


class LecturePureTests(_Base):
    slug = 'rlc2-pure'

    def test_le_journal_nECRIT_rien(self):
        marquer_etape_relance(
            self.etapes[0], self.acteur, RelanceEtape.Statut.FAIT,
            outcome='joint')
        activites = self.lead.activites.count()
        touches = self.lead.relance_etapes.count()
        stage = Lead.objects.get(pk=self.lead.pk).stage
        relance_date = Lead.objects.get(pk=self.lead.pk).relance_date

        self._journal()
        self._journal()

        self.assertEqual(self.lead.activites.count(), activites)
        self.assertEqual(self.lead.relance_etapes.count(), touches)
        frais = Lead.objects.get(pk=self.lead.pk)
        self.assertEqual(frais.stage, stage)
        self.assertEqual(frais.relance_date, relance_date)


class ApiJournalTests(_Base):
    slug = 'rlc2-api'

    URL = '/api/django/crm/relance-etapes/journal/'

    def _api(self, user=None):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user or self.acteur)}'))
        return api

    def test_200_avec_etat_et_lignes(self):
        marquer_etape_relance(
            self.etapes[0], self.acteur, RelanceEtape.Statut.FAIT,
            outcome='joint')

        resp = self._api().get(self.URL, {'lead': self.lead.pk})

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['lead'], self.lead.pk)
        self.assertTrue(resp.data['etat']['phrase'].strip())
        self.assertTrue(resp.data['lignes'])

    def test_400_sans_lead(self):
        resp = self._api().get(self.URL)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('lead', resp.data)

    def test_404_pour_un_lead_dune_autre_societe(self):
        autre = _company(f'{self.slug}-autre')
        intruse = User.objects.create_user(
            username=f'{self.slug}-intruse', password='x',
            role_legacy='responsable', company=autre)

        resp = self._api(intruse).get(self.URL, {'lead': self.lead.pk})

        self.assertEqual(resp.status_code, 404)
        # Le MÊME message qu'un lead inexistant : aucun oracle d'existence.
        inexistant = self._api(intruse).get(self.URL, {'lead': 9876543})
        self.assertEqual(resp.data['detail'], inexistant.data['detail'])

    def test_le_selecteur_rend_None_hors_societe(self):
        autre = _company(f'{self.slug}-autre2')
        self.assertIsNone(
            journal_relance(autre, self.acteur, self.lead.pk))

    def test_une_activite_dun_autre_lead_nentre_pas_dans_le_journal(self):
        voisin = Lead.objects.create(
            company=self.company, nom='Voisin', owner=self.acteur)
        LeadActivity.objects.create(
            company=self.company, lead=voisin, user=self.acteur,
            kind=LeadActivity.Kind.APPEL, outcome='joint',
            body='Touche « Appel voisin » (Appel, cadence contact) '
                 'marquée faite.')

        journal = self._journal()

        for ligne in journal['lignes']:
            self.assertNotIn('voisin', ligne['titre'].lower())
