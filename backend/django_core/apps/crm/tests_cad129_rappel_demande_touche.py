"""CAD129 — « rappelez-moi » entre dans la FILE, pas seulement dans la cloche.

Audit L3 du 21/09/2026, section CAD-K. Le clic « rappelez-moi » écrivait une
note, notifiait le responsable et son supérieur, et posait la préférence
« joignable par téléphone » — mais ne créait AUCUNE touche. Si la notification
est noyée dans la cloche, la demande la plus forte qu'un prospect puisse faire
disparaît.

Ce fichier verrouille la règle « décaler, jamais redémarrer » :

  * un lead avec un plan en cours voit sa prochaine touche RAMENÉE au prochain
    créneau d'appel, et tout le reste du plan glisse du MÊME écart ;
  * un lead sans aucune touche ouverte reçoit UNE touche — jamais un second
    plan ;
  * deux clics ne laissent jamais deux lignes dans la file ;
  * et l'échéance est toujours dans la fenêtre d'appel de la société : un
    rappel promis à 23 h ne rend service à personne.

Le temps est GELÉ (les créneaux d'appel sont des questions d'horloge).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 15 septembre 2026, 10 h à Casablanca — jour ouvré, fenêtre ouverte.
MAINTENANT = datetime.datetime(2026, 9, 15, 10, 0, tzinfo=horaires.CASABLANCA)


class RappelDemandeTests(TestCase):
    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug='cad129', defaults={'nom': 'cad129'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad129-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', stage=stages.CONTACTED,
            owner=self.acteur, telephone='0600000041')

    def _touche(self, *, ordre, dans_jours, canal=RelanceEtape.Canal.APPEL):
        due = MAINTENANT + datetime.timedelta(days=dans_jours)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=ordre, canal=canal, libelle=f'Touche {ordre}',
            due_at=due, due_date=due.date(),
            cadence_depart=MAINTENANT,
            statut=RelanceEtape.Statut.A_FAIRE)

    def test_sans_plan_ouvert_une_seule_touche_est_posee(self):
        etape = services.poser_touche_rappel_demande(
            self.lead, user=self.acteur)
        self.assertIsNotNone(etape)
        self.assertEqual(etape.libelle, services.RAPPEL_DEMANDE_LIBELLE)
        self.assertEqual(etape.canal, RelanceEtape.Canal.APPEL)
        self.assertEqual(
            self.lead.relance_etapes.filter(
                statut=RelanceEtape.Statut.A_FAIRE).count(), 1)

    def test_lecheance_tombe_dans_la_fenetre_dappel(self):
        etape = services.poser_touche_rappel_demande(
            self.lead, user=self.acteur)
        self.assertTrue(horaires.est_dans_fenetre(
            etape.due_at, self.company, canal=RelanceEtape.Canal.APPEL))

    def test_un_rappel_demande_a_23h_ne_tombe_pas_a_23h(self):
        nuit = datetime.datetime(
            2026, 9, 15, 23, 0, tzinfo=horaires.CASABLANCA)
        etape = services.poser_touche_rappel_demande(
            self.lead, user=self.acteur, quand=nuit)
        self.assertGreater(etape.due_at, nuit)
        self.assertTrue(horaires.est_dans_fenetre(
            etape.due_at, self.company, canal=RelanceEtape.Canal.APPEL))

    def test_deux_clics_ne_laissent_quune_ligne(self):
        premiere = services.poser_touche_rappel_demande(
            self.lead, user=self.acteur)
        seconde = services.poser_touche_rappel_demande(
            self.lead, user=self.acteur)
        self.assertEqual(premiere.pk, seconde.pk)
        self.assertEqual(
            self.lead.relance_etapes.filter(
                libelle=services.RAPPEL_DEMANDE_LIBELLE).count(), 1)

    def test_avec_un_plan_en_cours_la_suite_glisse_du_meme_ecart(self):
        """« Décaler, jamais redémarrer » : aucun second plan n'est créé."""
        prochaine = self._touche(ordre=1, dans_jours=3)
        suivante = self._touche(ordre=2, dans_jours=6)
        avant_prochaine = prochaine.due_at
        avant_suivante = suivante.due_at

        deplacee = services.poser_touche_rappel_demande(
            self.lead, user=self.acteur)
        prochaine.refresh_from_db()
        suivante.refresh_from_db()

        self.assertEqual(deplacee.pk, prochaine.pk)
        # La touche est RAMENÉE (le client attend maintenant).
        self.assertLess(prochaine.due_at, avant_prochaine)
        delta = prochaine.due_at - avant_prochaine
        self.assertEqual(suivante.due_at, avant_suivante + delta)
        # Aucune touche supplémentaire : on n'a pas fabriqué un second plan.
        self.assertEqual(
            self.lead.relance_etapes.filter(
                libelle=services.RAPPEL_DEMANDE_LIBELLE).count(), 0)
        self.assertEqual(self.lead.relance_etapes.count(), 2)

    def test_lancre_de_la_cadence_glisse_aussi(self):
        """CKP2 — sinon le barreau suivant renaîtrait à sa date d'origine."""
        prochaine = self._touche(ordre=1, dans_jours=3)
        ancre_avant = prochaine.cadence_depart
        services.poser_touche_rappel_demande(self.lead, user=self.acteur)
        prochaine.refresh_from_db()
        self.assertNotEqual(prochaine.cadence_depart, ancre_avant)

    def test_le_chatter_dit_pourquoi_le_plan_a_bouge(self):
        self._touche(ordre=1, dans_jours=3)
        services.poser_touche_rappel_demande(self.lead, user=self.acteur)
        notes = list(self.lead.activites.values_list('body', flat=True))
        self.assertTrue(
            any('Rappel demandé par le client' in n for n in notes), notes)

    def test_un_lead_sans_societe_ne_casse_rien(self):
        orphelin = Lead(nom='Sans société')
        self.assertIsNone(
            services.poser_touche_rappel_demande(orphelin))

    def test_la_file_du_lead_est_recalee(self):
        etape = services.poser_touche_rappel_demande(
            self.lead, user=self.acteur)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, etape.due_date)
