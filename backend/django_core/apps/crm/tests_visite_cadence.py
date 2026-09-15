"""VISITE-CADENCE — le suivi commercial RÉAGIT à la visite technique.

Ordre fondateur du 15/09/2026 : la visite se place APRÈS l'envoi du devis,
comme outil de closing. Avant ce lot, le moteur de relances l'IGNORAIT
totalement — on pouvait caler un rendez-vous chez un client et continuer à lui
envoyer « le PDF s'ouvre bien ? », puis laisser le technicien repartir sans que
personne ne rappelle.

Ce qui est prouvé ici :

* **planification** — la cadence après-devis en cours est ARRÊTÉE avec son
  motif, la fiche porte la date, une note de chatter la dit, et DEUX gestes la
  remplacent (confirmer la veille, débriefer le lendemain). Une veille déjà
  passée tombe AUJOURD'HUI, jamais en retard. Une RE-planification DÉPLACE les
  deux étapes au lieu de les dupliquer ;
* **lead qu'on ne relance plus** (perdu / ne plus contacter) — chatter SEUL,
  pas une touche ;
* **retour terrain** — le TEXTE LIBRE du technicien entre dans l'historique,
  `visite_effectuee` est posé sans écraser les notes manuelles, le débrief est
  ramené à demain, et le RESPONSABLE du lead est prévenu ;
* **issue « visite acceptée »** — elle ne fait naître AUCUN barreau du
  protocole, n'arrête pas la cadence, ne clôt jamais le dossier au Froid, et
  pose le filet « planifier la visite » sauf si un rendez-vous existe déjà ;
* **les deux messages** — `{date_visite}` rendu « mardi 22 septembre », et sa
  phrase OMISE quand la fiche n'a pas de date.

Horloge FIXE partout : « demain » ne doit pas dépendre du jour de la CI.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from testkit.time import frozen

from apps.crm import horaires, services
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.notifications.models import EventType, Notification
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape
from apps.visites.models import VisiteTerrain
from authentication.models import Company

User = get_user_model()

#: Mardi 15 septembre 2026, 10 h locale — horloge FIXE.
MAINTENANT = datetime.datetime(2026, 9, 15, 10, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = datetime.date(2026, 9, 15)
#: Jeudi 17/09 : ni week-end, ni vendredi — la veille (mercredi 16) et le
#: lendemain (vendredi 18) restent des jours ouvrés dans toute configuration
#: raisonnable, donc les recalages d'horaires ne déplacent pas le JOUR.
VISITE_LE = datetime.date(2026, 9, 17)


def _company(slug, nom):
    """Une société RÉELLE (jamais un ``get_or_create`` sur un slug partagé :
    deux locataires qui se confondent ne prouvent aucune isolation)."""
    company = Company.objects.create(nom=nom, slug=slug)
    CompanyProfile.objects.get_or_create(company=company)
    return company


def _echeance_attendue(company, jour, canal):
    """La date que le moteur d'horaires produit pour ``jour`` à 9 h.

    On ne code PAS en dur « mercredi 16 » : les jours ouvrés viennent de la
    configuration de la société. Ce qui est vérifié ici est l'ANCRE (la veille,
    le lendemain), pas la politique d'horaires — qui a ses propres tests."""
    vise = datetime.datetime.combine(jour, datetime.time(9, 0),
                                     tzinfo=horaires.CASABLANCA)
    return horaires.prochain_creneau_appel(
        vise, company, canal=canal).astimezone(horaires.CASABLANCA).date()


class VisiteCadenceBase(TestCase):
    def setUp(self):
        self.company = _company('vcadcrm-a', 'VCADCRM Solaire')
        self.autre = _company('vcadcrm-b', 'VCADCRM Concurrent')
        CadenceRelanceEtape.seed_defaults(self.company)
        self.owner = User.objects.create_user(
            username='vcadcrm-owner', password='x', company=self.company,
            first_name='Nadia')
        self.acteur = User.objects.create_user(
            username='vcadcrm-acteur', password='x', company=self.company,
            role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            ville='Bouskoura', owner=self.owner)
        self.lead_autre = Lead.objects.create(
            company=self.autre, nom='Client concurrent', ville='Rabat')

    def _touches(self, libelle=None, statut=RelanceEtape.Statut.A_FAIRE):
        qs = self.lead.relance_etapes.filter(statut=statut)
        if libelle is not None:
            qs = qs.filter(libelle=libelle)
        return qs

    def _touche_generique_ouverte(self):
        """Une touche du GABARIT après-devis, ouverte — ce que la visite
        doit faire taire."""
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=1, canal=RelanceEtape.Canal.WHATSAPP,
            libelle="Le PDF s'ouvre bien ?", template_cle='j1_pdf',
            due_date=AUJOURDHUI, due_at=MAINTENANT)


class VisitePlanifieeTests(VisiteCadenceBase):

    def test_arrete_la_cadence_et_pose_les_deux_gestes(self):
        generique = self._touche_generique_ouverte()
        with frozen(MAINTENANT):
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, VISITE_LE,
                commercial_nom='Youssef Alami')

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.visite_prevue_le, VISITE_LE)

        generique.refresh_from_db()
        self.assertEqual(generique.statut, RelanceEtape.Statut.ANNULEE)
        self.assertEqual(generique.note, 'visite technique planifiée')
        # CKP1 — geste du MOTEUR : aucun humain n'est estampillé dessus.
        self.assertIsNone(generique.traite_par)

        confirmation = self._touches(
            services.VISITE_CONFIRMATION_LIBELLE).get()
        debrief = self._touches(services.VISITE_DEBRIEF_LIBELLE).get()
        self.assertEqual(
            confirmation.due_date,
            _echeance_attendue(self.company,
                               VISITE_LE - datetime.timedelta(days=1),
                               'whatsapp'))
        self.assertEqual(confirmation.canal, RelanceEtape.Canal.WHATSAPP)
        self.assertEqual(confirmation.template_cle, 'visite_confirmation')
        self.assertEqual(
            debrief.due_date,
            _echeance_attendue(self.company,
                               VISITE_LE + datetime.timedelta(days=1),
                               'appel'))
        self.assertEqual(debrief.canal, RelanceEtape.Canal.APPEL)

    def test_pose_une_note_de_chatter_systeme_qui_nomme_lassigne(self):
        with frozen(MAINTENANT):
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, VISITE_LE,
                commercial_nom='Youssef Alami')
        note = self.lead.activites.filter(
            body__startswith='Visite technique planifiée').get()
        self.assertIn('17/09/2026', note.body)
        self.assertIn('Youssef Alami', note.body)
        # Note SYSTÈME (garde QJ7) : PLANIFIER n'est pas AVOIR contacté.
        self.assertIsNone(note.user)
        self.assertEqual(note.kind, LeadActivity.Kind.NOTE)

    def test_sans_assigne_la_note_le_dit_au_lieu_dun_blanc(self):
        with frozen(MAINTENANT):
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, VISITE_LE)
        note = self.lead.activites.filter(
            body__startswith='Visite technique planifiée').get()
        self.assertIn('pas encore assignée', note.body)

    def test_pose_les_deux_gestes_meme_sans_cadence_active(self):
        """Invariant « jamais zéro prochaine étape »."""
        with frozen(MAINTENANT):
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, VISITE_LE)
        self.assertEqual(self._touches().count(), 2)
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.relance_date)

    def test_une_veille_deja_passee_tombe_aujourdhui(self):
        with frozen(MAINTENANT):
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, AUJOURDHUI)
        confirmation = self._touches(
            services.VISITE_CONFIRMATION_LIBELLE).get()
        self.assertGreaterEqual(confirmation.due_date, AUJOURDHUI)

    def test_replanifier_deplace_sans_dupliquer(self):
        with frozen(MAINTENANT):
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, VISITE_LE)
            confirmation_avant = self._touches(
                services.VISITE_CONFIRMATION_LIBELLE).get()
            nouveau = VISITE_LE + datetime.timedelta(days=7)
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, nouveau)

        self.assertEqual(self._touches(
            services.VISITE_CONFIRMATION_LIBELLE).count(), 1)
        self.assertEqual(self._touches(
            services.VISITE_DEBRIEF_LIBELLE).count(), 1)
        confirmation = self._touches(
            services.VISITE_CONFIRMATION_LIBELLE).get()
        self.assertEqual(confirmation.pk, confirmation_avant.pk)
        self.assertEqual(
            confirmation.due_date,
            _echeance_attendue(self.company,
                               nouveau - datetime.timedelta(days=1),
                               'whatsapp'))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.visite_prevue_le, nouveau)

    def test_annule_le_filet_planifier_la_visite(self):
        with frozen(MAINTENANT):
            filet = services.poser_filet_visite_a_planifier(
                self.lead, self.acteur)
            self.assertIsNotNone(filet)
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, VISITE_LE)
        filet.refresh_from_db()
        self.assertEqual(filet.statut, RelanceEtape.Statut.ANNULEE)
        self.assertEqual(filet.note, 'visite planifiée')
        self.assertIsNone(filet.traite_par)

    def test_lead_perdu_chatter_seul(self):
        self.lead.perdu = True
        self.lead.save(update_fields=['perdu'])
        with frozen(MAINTENANT):
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, VISITE_LE)
        self.assertEqual(self._touches().count(), 0)
        self.assertTrue(self.lead.activites.filter(
            body__startswith='Visite technique planifiée').exists())

    def test_lead_ne_plus_contacter_chatter_seul(self):
        self.lead.ne_plus_contacter = True
        self.lead.save(update_fields=['ne_plus_contacter'])
        with frozen(MAINTENANT):
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, VISITE_LE)
        self.assertEqual(self._touches().count(), 0)
        self.assertTrue(self.lead.activites.filter(
            body__startswith='Visite technique planifiée').exists())

    def test_naffecte_jamais_le_lead_dune_autre_societe(self):
        with frozen(MAINTENANT):
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, VISITE_LE)
        self.assertEqual(self.lead_autre.relance_etapes.count(), 0)
        self.assertEqual(self.lead_autre.activites.count(), 0)
        self.lead_autre.refresh_from_db()
        self.assertIsNone(self.lead_autre.visite_prevue_le)

    def test_ne_touche_jamais_letape_du_funnel(self):
        avant = self.lead.stage
        with frozen(MAINTENANT):
            services.appliquer_visite_planifiee(
                self.lead, self.acteur, VISITE_LE)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, avant)


class RetourVisiteTests(VisiteCadenceBase):

    RETOUR = {
        'notes': 'Le tableau est saturé, prévoir un départ dédié.',
        'commentaires_photos': [
            {'slot': 'Vue générale du toit', 'commentaire': 'Tuiles fragiles'},
            {'slot': 'Tableau ouvert', 'commentaire': ''},
        ],
        'nb_photos': 2,
    }

    def test_la_note_porte_le_texte_libre_du_terrain(self):
        with frozen(MAINTENANT):
            services.appliquer_retour_visite(
                self.lead, self.acteur, self.RETOUR, auteur='Youssef Alami')
        note = self.lead.activites.filter(
            body__startswith='Visite technique terminée').get()
        self.assertIn('Youssef Alami', note.body)
        self.assertIn('Le tableau est saturé, prévoir un départ dédié.',
                      note.body)
        self.assertIn('— Vue générale du toit : Tuiles fragiles', note.body)
        # Commentaire vide : pas de ligne fantôme.
        self.assertNotIn('Tableau ouvert', note.body)
        self.assertIsNone(note.user)

    def test_un_retour_muet_le_dit(self):
        with frozen(MAINTENANT):
            services.appliquer_retour_visite(
                self.lead, self.acteur,
                {'notes': '', 'commentaires_photos': [], 'nb_photos': 0})
        note = self.lead.activites.filter(
            body__startswith='Visite technique terminée').get()
        self.assertIn('Aucun commentaire écrit sur place.', note.body)

    def test_la_note_est_tronquee_sans_perdre_le_debut(self):
        long = 'x' * 4000
        corps = services.composer_note_retour_visite({'notes': long})
        self.assertLessEqual(len(corps), services.RETOUR_VISITE_MAX)
        self.assertTrue(corps.endswith('…'))
        self.assertIn('Visite technique terminée', corps)

    def test_pose_visite_effectuee_sans_ecraser_les_notes_manuelles(self):
        self.lead.visite_notes = 'Note écrite à la main.'
        self.lead.save(update_fields=['visite_notes'])
        with frozen(MAINTENANT):
            services.appliquer_retour_visite(
                self.lead, self.acteur, self.RETOUR)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.visite_effectuee)
        self.assertEqual(self.lead.visite_notes, 'Note écrite à la main.')

    def test_ramene_le_debrief_a_demain(self):
        with frozen(MAINTENANT):
            services.appliquer_visite_planifiee(
                self.lead, self.acteur,
                AUJOURDHUI + datetime.timedelta(days=10))
            lointain = self._touches(services.VISITE_DEBRIEF_LIBELLE).get()
            self.assertGreater(lointain.due_date,
                               AUJOURDHUI + datetime.timedelta(days=1))
            services.appliquer_retour_visite(
                self.lead, self.acteur, self.RETOUR)

        self.assertEqual(self._touches(
            services.VISITE_DEBRIEF_LIBELLE).count(), 1)
        debrief = self._touches(services.VISITE_DEBRIEF_LIBELLE).get()
        self.assertEqual(debrief.pk, lointain.pk)
        self.assertEqual(
            debrief.due_date,
            _echeance_attendue(self.company,
                               AUJOURDHUI + datetime.timedelta(days=1),
                               'appel'))

    def test_ne_repousse_jamais_un_debrief_deja_du(self):
        with frozen(MAINTENANT):
            proche = RelanceEtape.objects.create(
                company=self.company, lead=self.lead, cadence='apres_devis',
                ordre=services.VISITE_ORDRE_DEBRIEF,
                canal=RelanceEtape.Canal.APPEL,
                libelle=services.VISITE_DEBRIEF_LIBELLE,
                due_date=AUJOURDHUI, due_at=MAINTENANT)
            services.appliquer_retour_visite(
                self.lead, self.acteur, self.RETOUR)
        proche.refresh_from_db()
        self.assertEqual(proche.due_date, AUJOURDHUI)

    def test_pose_le_debrief_meme_sans_planification_prealable(self):
        with frozen(MAINTENANT):
            services.appliquer_retour_visite(
                self.lead, self.acteur, self.RETOUR)
        self.assertEqual(self._touches(
            services.VISITE_DEBRIEF_LIBELLE).count(), 1)

    def test_lead_perdu_chatter_seul(self):
        self.lead.perdu = True
        self.lead.save(update_fields=['perdu'])
        with frozen(MAINTENANT):
            services.appliquer_retour_visite(
                self.lead, self.acteur, self.RETOUR)
        self.assertEqual(self._touches().count(), 0)
        self.assertTrue(self.lead.activites.filter(
            body__startswith='Visite technique terminée').exists())

    def test_ne_touche_jamais_letape_du_funnel(self):
        avant = self.lead.stage
        with frozen(MAINTENANT):
            services.appliquer_retour_visite(
                self.lead, self.acteur, self.RETOUR)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, avant)


class RecepteurRetourVisiteTests(VisiteCadenceBase):
    """Le récepteur complet : chatter + fiche + débrief + notification."""

    def _emettre(self, lead=None, user=None):
        from core.events import visite_terminee

        lead = lead or self.lead
        visite = VisiteTerrain.objects.create(
            company=lead.company, lead=lead, date_prevue=AUJOURDHUI,
            notes='Accès par le garage.')
        visite_terminee.send(
            sender=VisiteTerrain, visite=visite, lead_id=lead.id,
            user=self.acteur if user is None else user,
            retour={'notes': 'Accès par le garage.',
                    'commentaires_photos': [], 'nb_photos': 0})
        return visite

    def test_notifie_le_responsable_du_lead(self):
        with frozen(MAINTENANT):
            self._emettre()
        notification = Notification.objects.get(
            recipient=self.owner,
            event_type=EventType.VISITE_RETOUR_TERRAIN)
        self.assertEqual(notification.link, f'/crm/leads/{self.lead.pk}')
        self.assertIn('24-48', notification.body)
        self.assertEqual(notification.company_id, self.company.id)

    def test_ne_se_notifie_pas_soi_meme(self):
        self.lead.owner = self.acteur
        self.lead.save(update_fields=['owner'])
        with frozen(MAINTENANT):
            self._emettre()
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.VISITE_RETOUR_TERRAIN).exists())

    def test_lead_sans_responsable_ne_casse_rien(self):
        self.lead.owner = None
        self.lead.save(update_fields=['owner'])
        with frozen(MAINTENANT):
            self._emettre()
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.VISITE_RETOUR_TERRAIN).exists())
        # Le reste du récepteur a bien tourné malgré l'absence de owner.
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.visite_effectuee)

    def test_le_texte_libre_atteint_lhistorique_du_lead(self):
        with frozen(MAINTENANT):
            self._emettre()
        self.assertTrue(self.lead.activites.filter(
            body__contains='Accès par le garage.').exists())


class RecepteurPlanificationTests(VisiteCadenceBase):
    """Le récepteur : émettre l'événement suffit à recaler le suivi."""

    def test_levenement_recale_le_suivi(self):
        from core.events import visite_planifiee

        generique = self._touche_generique_ouverte()
        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, date_prevue=VISITE_LE)
        with frozen(MAINTENANT):
            visite_planifiee.send(
                sender=VisiteTerrain, visite=visite, lead_id=self.lead.id,
                user=self.acteur, date_prevue=VISITE_LE,
                commercial_nom='Youssef Alami')

        generique.refresh_from_db()
        self.assertEqual(generique.statut, RelanceEtape.Statut.ANNULEE)
        self.assertEqual(self._touches().count(), 2)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.visite_prevue_le, VISITE_LE)

    def test_un_lead_inconnu_ne_leve_pas(self):
        from core.events import visite_planifiee

        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, date_prevue=VISITE_LE)
        with frozen(MAINTENANT):
            visite_planifiee.send(
                sender=VisiteTerrain, visite=visite, lead_id=999999,
                user=self.acteur, date_prevue=VISITE_LE, commercial_nom='')
        self.assertEqual(self._touches().count(), 0)


class IssueVisiteAccepteeTests(VisiteCadenceBase):

    def _touche_appel(self):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=2, canal=RelanceEtape.Canal.APPEL,
            libelle='Appel de suivi', due_date=AUJOURDHUI,
            due_at=MAINTENANT, cadence_depart=MAINTENANT)

    def test_pose_le_filet_et_aucune_touche_du_gabarit(self):
        etape = self._touche_appel()
        with frozen(MAINTENANT):
            services.marquer_etape_relance(
                etape, self.acteur, RelanceEtape.Statut.FAIT,
                outcome=services.OUTCOME_VISITE_ACCEPTEE)

        filet = self._touches(services.VISITE_FILET_LIBELLE).get()
        self.assertEqual(filet.canal, RelanceEtape.Canal.APPEL)
        self.assertEqual(filet.due_date, AUJOURDHUI)
        self.assertEqual(filet.cadence, services.VISITE_CADENCE)
        # AUCUN barreau du gabarit n'est né de cette issue.
        self.assertEqual(self._touches().count(), 1)

    def test_narrete_pas_la_cadence_et_ne_clot_pas_au_froid(self):
        from apps.crm import stages

        etape = self._touche_appel()
        avant = self.lead.stage
        with frozen(MAINTENANT):
            services.marquer_etape_relance(
                etape, self.acteur, RelanceEtape.Statut.FAIT,
                outcome=services.OUTCOME_VISITE_ACCEPTEE)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, avant)
        self.assertNotEqual(self.lead.stage, stages.COLD)

    def test_pas_de_filet_si_une_visite_est_deja_calee(self):
        VisiteTerrain.objects.create(
            company=self.company, lead=self.lead,
            date_prevue=AUJOURDHUI + datetime.timedelta(days=3))
        etape = self._touche_appel()
        with frozen(MAINTENANT):
            services.marquer_etape_relance(
                etape, self.acteur, RelanceEtape.Statut.FAIT,
                outcome=services.OUTCOME_VISITE_ACCEPTEE)
        self.assertEqual(self._touches(
            services.VISITE_FILET_LIBELLE).count(), 0)

    def test_une_visite_passee_ne_compte_pas_comme_calee(self):
        VisiteTerrain.objects.create(
            company=self.company, lead=self.lead,
            date_prevue=AUJOURDHUI - datetime.timedelta(days=3))
        etape = self._touche_appel()
        with frozen(MAINTENANT):
            services.marquer_etape_relance(
                etape, self.acteur, RelanceEtape.Statut.FAIT,
                outcome=services.OUTCOME_VISITE_ACCEPTEE)
        self.assertEqual(self._touches(
            services.VISITE_FILET_LIBELLE).count(), 1)

    def test_lissue_est_un_choix_declare_du_modele(self):
        self.assertIn(
            services.OUTCOME_VISITE_ACCEPTEE,
            {code for code, _ in LeadActivity.OUTCOMES})

    def test_lactivite_porte_lissue(self):
        etape = self._touche_appel()
        with frozen(MAINTENANT):
            services.marquer_etape_relance(
                etape, self.acteur, RelanceEtape.Statut.FAIT,
                outcome=services.OUTCOME_VISITE_ACCEPTEE)
        self.assertTrue(self.lead.activites.filter(
            outcome=services.OUTCOME_VISITE_ACCEPTEE).exists())


class MessageVisiteTests(VisiteCadenceBase):

    def test_rend_la_date_en_francais_parle(self):
        self.lead.visite_prevue_le = datetime.date(2026, 9, 22)
        self.lead.save(update_fields=['visite_prevue_le'])
        rendu = services.message_visite_pour_lead(
            self.lead, 'visite_confirmation', user=self.acteur)
        self.assertIn('mardi 22 septembre', rendu['corps_fr'])
        self.assertNotIn('{date_visite}', rendu['corps_fr'])
        self.assertNotIn('{date_visite}', rendu['corps_darija'])

    def test_sans_date_la_phrase_est_omise_jamais_un_trou(self):
        self.assertIsNone(self.lead.visite_prevue_le)
        rendu = services.message_visite_pour_lead(
            self.lead, 'visite_confirmation', user=self.acteur)
        self.assertNotIn('{date_visite}', rendu['corps_fr'])
        self.assertNotIn('la visite technique prévue', rendu['corps_fr'])
        # Le reste du message tient debout.
        self.assertIn('technicien', rendu['corps_fr'])

    def test_le_conseiller_est_le_responsable_du_lead(self):
        rendu = services.message_visite_pour_lead(
            self.lead, 'visite_proposition', user=self.acteur)
        self.assertIn('Nadia', rendu['corps_fr'])
        self.assertNotIn('{conseiller}', rendu['corps_fr'])

    def test_une_cle_inconnue_rend_none(self):
        self.assertIsNone(services.message_visite_pour_lead(
            self.lead, 'apres_visite', user=self.acteur))

    def test_aucun_chiffre_ni_prenom_code_en_dur_dans_les_defauts(self):
        from apps.parametres.models_messages import (
            MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
        )

        for cle in services.CLES_MESSAGE_VISITE:
            for source in (MESSAGE_TEMPLATE_DEFAULTS,
                           MESSAGE_TEMPLATE_DEFAULTS_DARIJA):
                texte = source.get(cle, '')
                self.assertTrue(texte, cle)
                for interdit in ('Meryem', 'Reda', 'مريم', 'رضا'):
                    self.assertNotIn(interdit, texte)


class DateVisiteFrancaisTests(TestCase):
    """Le formateur, isolé — il ne dépend d'aucune locale serveur."""

    def test_rend_le_jour_et_le_mois(self):
        self.assertEqual(
            services._date_visite_francais(datetime.date(2026, 9, 16)),
            'mercredi 16 septembre')

    def test_une_date_absente_rend_une_chaine_vide(self):
        self.assertEqual(services._date_visite_francais(None), '')
        self.assertEqual(services._date_visite_francais('pas une date'), '')
