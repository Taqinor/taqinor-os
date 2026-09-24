"""CAD130 — le client rouvre sa proposition trois fois : la cadence BOUGE.

Avant : chaque ouverture produisait une note et une notification, le moteur
d'engagement (toutes les 3 h) une notification de plus — et la file de Meryem
ne bougeait pas d'un millimètre.

Done : trois ouvertures produisent UNE touche « Proposition rouverte —
appeler », la prochaine touche du plan est DÉCALÉE (derrière elle) et non
doublée, et aucune des cinq gardes n'est violée :

  1. la touche signal remplace la prochaine touche du plan en la décalant ;
  2. jamais plus d'un appel et d'un message par jour (CAD20) ;
  3. jamais hors fenêtre ;
  4. jamais sur un lead « ne plus contacter », perdu, archivé ou signé ;
  5. un délai minimal depuis la dernière touche faite.

Le calcul des dates est PUR (``cadence_temps.echeances_signal``) et testé
sans base ; le câblage (service CRM + moteur d'engagement de ``ventes``) est
testé en base, temps gelé.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from authentication.models import Company
from testkit.time import frozen

from apps.crm import cadence_temps, horaires, services, stages
from apps.crm.models import Client, Lead, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

TZ = horaires.CASABLANCA

#: Mercredi 23/09/2026, 21 h à Casablanca — la fenêtre d'appel est fermée
#: (20 h) : le client relit sa proposition dans la soirée.
MERCREDI_SOIR = datetime.datetime(2026, 9, 23, 21, 0, tzinfo=TZ)
JEUDI_9H = datetime.datetime(2026, 9, 24, 9, 0, tzinfo=TZ)
JEUDI_10H = datetime.datetime(2026, 9, 24, 10, 0, tzinfo=TZ)
VENDREDI_9H = datetime.datetime(2026, 9, 25, 9, 0, tzinfo=TZ)

LIBELLE = services.TOUCHES_SIGNAL[services.SIGNAL_PROPOSITION_ROUVERTE]


def _local(dt):
    return dt.astimezone(TZ)


# ── Le calcul pur ────────────────────────────────────────────────────────────

def _creneau_9h_20h(dt):
    """Fenêtre simplifiée pour le test pur : 9 h-20 h, tous les jours."""
    local = _local(dt)
    if local.time() < datetime.time(9, 0):
        return local.replace(hour=9, minute=0, second=0, microsecond=0)
    if local.time() >= datetime.time(20, 0):
        demain = local.date() + datetime.timedelta(days=1)
        return datetime.datetime.combine(demain, datetime.time(9, 0),
                                         tzinfo=TZ)
    return local


def _lendemain(dt):
    return _creneau_9h_20h(dt + datetime.timedelta(days=1))


def _libre(_jour):
    return False


class EcheancesSignalPurTests(SimpleTestCase):

    def test_la_touche_tombe_a_la_prochaine_minute_joignable(self):
        echeance, glisse = cadence_temps.echeances_signal(
            maintenant=MERCREDI_SOIR, derniere_faite=None, prochaine=None,
            jour_occupe=_libre, creneau=_creneau_9h_20h, lendemain=_lendemain)
        self.assertEqual(echeance, JEUDI_9H)
        self.assertIsNone(glisse)

    def test_la_touche_du_plan_trop_proche_glisse_derriere(self):
        echeance, glisse = cadence_temps.echeances_signal(
            maintenant=MERCREDI_SOIR, derniere_faite=None,
            prochaine=JEUDI_10H, jour_occupe=_libre,
            creneau=_creneau_9h_20h, lendemain=_lendemain)
        self.assertEqual(echeance, JEUDI_9H)
        self.assertEqual(glisse, JEUDI_9H + cadence_temps.SIGNAL_ECART_MIN)

    def test_une_touche_du_plan_lointaine_ne_bouge_pas(self):
        lointaine = JEUDI_10H + datetime.timedelta(days=5)
        _echeance, glisse = cadence_temps.echeances_signal(
            maintenant=MERCREDI_SOIR, derniere_faite=None,
            prochaine=lointaine, jour_occupe=_libre,
            creneau=_creneau_9h_20h, lendemain=_lendemain)
        self.assertIsNone(glisse)

    def test_la_touche_du_plan_n_est_jamais_tiree_en_avant(self):
        for prochaine in (MERCREDI_SOIR - datetime.timedelta(days=2),
                          JEUDI_10H, VENDREDI_9H):
            _echeance, glisse = cadence_temps.echeances_signal(
                maintenant=MERCREDI_SOIR, derniere_faite=None,
                prochaine=prochaine, jour_occupe=_libre,
                creneau=_creneau_9h_20h, lendemain=_lendemain)
            if glisse is not None:
                self.assertGreater(glisse, prochaine)

    def test_delai_minimal_depuis_la_derniere_touche_faite(self):
        faite = MERCREDI_SOIR - datetime.timedelta(minutes=30)
        echeance, _glisse = cadence_temps.echeances_signal(
            maintenant=MERCREDI_SOIR, derniere_faite=faite, prochaine=None,
            jour_occupe=_libre, creneau=_creneau_9h_20h, lendemain=_lendemain)
        self.assertGreaterEqual(echeance,
                                faite + cadence_temps.SIGNAL_ECART_MIN)

    def test_un_jour_deja_pris_pousse_au_lendemain(self):
        jeudi = JEUDI_9H.date()
        echeance, _glisse = cadence_temps.echeances_signal(
            maintenant=MERCREDI_SOIR, derniere_faite=None, prochaine=None,
            jour_occupe=lambda jour: jour == jeudi,
            creneau=_creneau_9h_20h, lendemain=_lendemain)
        self.assertEqual(echeance, VENDREDI_9H)


# ── Le câblage, en base ──────────────────────────────────────────────────────

@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class ToucheParSignalTests(TestCase):

    def setUp(self):
        gel = frozen(MERCREDI_SOIR)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='CAD130 Solaire',
                                              slug='cad130-solaire')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad130-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Aziz',
            stage=stages.QUOTE_SENT, owner=self.acteur,
            telephone='+212661112233')
        # La touche du PLAN (suivi de proposition) prévue jeudi 10 h.
        self.plan = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=3, canal=RelanceEtape.Canal.WHATSAPP,
            libelle='Preuve — installation comparable',
            due_at=JEUDI_10H, due_date=JEUDI_10H.date(),
            cadence_depart=MERCREDI_SOIR - datetime.timedelta(days=4))

    def _touches_signal(self):
        return RelanceEtape.objects.filter(lead=self.lead, libelle=LIBELLE)

    def _signal(self):
        return services.poser_touche_signal(
            self.lead, services.SIGNAL_PROPOSITION_ROUVERTE)

    # ── Done : trois ouvertures, UNE touche, le plan décalé et non doublé ──

    def test_trois_signaux_une_seule_touche_et_un_seul_decalage(self):
        for _ in range(3):
            self._signal()
        self.assertEqual(self._touches_signal().count(), 1)
        touche = self._touches_signal().get()
        self.assertEqual(touche.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(_local(touche.due_at), JEUDI_9H)
        self.plan.refresh_from_db()
        # Décalée DERRIÈRE la touche signal, une seule fois, jamais doublée.
        self.assertEqual(self.plan.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(_local(self.plan.due_at), VENDREDI_9H)
        self.assertEqual(RelanceEtape.objects.filter(
            lead=self.lead, libelle=self.plan.libelle).count(), 1)
        # Le lead pointe la touche signal (la plus proche).
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, JEUDI_9H.date())

    def test_l_ancre_du_plan_glisse_avec_lui(self):
        ancre_avant = self.plan.cadence_depart
        self._signal()
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.cadence_depart - ancre_avant,
                         VENDREDI_9H - JEUDI_10H)

    def test_une_note_systeme_dit_ce_que_le_moteur_a_fait(self):
        self._signal()
        note = self.lead.activites.filter(
            body__startswith='Signal client').get()
        self.assertIsNone(note.user)
        self.assertIn(LIBELLE, note.body)
        self.assertIn('glisse au 25/09/2026', note.body)

    def test_moteur_d_engagement_rouverte_3_fois_pose_la_touche(self):
        from apps.ventes.models import Devis, ShareLink
        from apps.ventes.scheduled import engagement_followup_engine

        client = Client.objects.create(
            company=self.company, nom='Benali', email='cad130@example.com')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-2609-CAD130',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), created_by=self.acteur,
            date_envoi=MERCREDI_SOIR - datetime.timedelta(days=1))
        ShareLink.objects.create(
            company=self.company, devis=devis, view_count=3,
            first_viewed_at=MERCREDI_SOIR - datetime.timedelta(hours=2))
        for _ in range(3):
            engagement_followup_engine()
        self.assertEqual(self._touches_signal().count(), 1)
        self.plan.refresh_from_db()
        self.assertEqual(_local(self.plan.due_at), VENDREDI_9H)

    def test_moteur_deux_visites_seulement_aucune_touche(self):
        from apps.ventes.models import Devis, ShareLink
        from apps.ventes.scheduled import engagement_followup_engine

        client = Client.objects.create(
            company=self.company, nom='Benali', email='cad130b@example.com')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-2609-CAD130B',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), created_by=self.acteur,
            date_envoi=MERCREDI_SOIR - datetime.timedelta(hours=3))
        ShareLink.objects.create(
            company=self.company, devis=devis, view_count=2,
            first_viewed_at=MERCREDI_SOIR - datetime.timedelta(hours=2))
        engagement_followup_engine()
        self.assertFalse(self._touches_signal().exists())

    # ── Garde 3 : jamais hors fenêtre ──

    def test_jamais_hors_fenetre(self):
        touche = self._signal()
        self.assertTrue(horaires.est_dans_fenetre(
            touche.due_at, self.company, canal=touche.canal))

    # ── Garde 2 : un appel par jour ──

    def test_un_jour_deja_pris_par_un_appel_pousse_au_lendemain(self):
        RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=services.VISITE_ORDRE_CONFIRMATION,
            canal=RelanceEtape.Canal.APPEL,
            libelle=services.VISITE_CONFIRMATION_LIBELLE,
            due_at=JEUDI_10H, due_date=JEUDI_10H.date())
        touche = self._signal()
        self.assertEqual(_local(touche.due_at), VENDREDI_9H)
        # Le geste de visite n'est pas une touche du plan : il ne bouge pas.
        visite = RelanceEtape.objects.get(
            lead=self.lead, libelle=services.VISITE_CONFIRMATION_LIBELLE)
        self.assertEqual(_local(visite.due_at), JEUDI_10H)

    # ── Garde 4 : jamais sur un lead qu'on ne relance plus ──

    def test_jamais_sur_un_lead_hors_cadence(self):
        cas = (
            ('ne_plus_contacter', True),
            ('perdu', True),
            ('is_archived', True),
            ('stage', stages.SIGNED),
        )
        for champ, valeur in cas:
            with self.subTest(champ=champ):
                lead = Lead.objects.create(
                    company=self.company, nom=f'Garde {champ}',
                    owner=self.acteur, telephone='+212661112244')
                setattr(lead, champ, valeur)
                lead.save()
                self.assertTrue(services.refus_touche_signal(lead))
                self.assertIsNone(services.poser_touche_signal(
                    lead, services.SIGNAL_PROPOSITION_ROUVERTE))
                self.assertFalse(lead.relance_etapes.exists())

    def test_un_lead_hors_cadence_ne_decale_pas_son_plan(self):
        self.lead.perdu = True
        self.lead.save(update_fields=['perdu'])
        self._signal()
        self.plan.refresh_from_db()
        self.assertEqual(_local(self.plan.due_at), JEUDI_10H)

    # ── Garde 5 : un délai minimal depuis la dernière touche faite ──

    def test_delai_minimal_depuis_la_derniere_touche_faite(self):
        faite_a = MERCREDI_SOIR - datetime.timedelta(minutes=30)
        RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=2, canal=RelanceEtape.Canal.APPEL, libelle='Appel J+2',
            due_at=faite_a, due_date=faite_a.date(),
            statut=RelanceEtape.Statut.FAIT, traite_le=faite_a)
        touche = self._signal()
        self.assertGreaterEqual(touche.due_at,
                                faite_a + cadence_temps.SIGNAL_ECART_MIN)
        self.assertTrue(horaires.est_dans_fenetre(
            touche.due_at, self.company, canal=touche.canal))

    # ── Idempotence étendue ──

    def test_un_rappel_demande_ouvert_couvre_deja_le_signal(self):
        rappel = RelanceEtape.objects.create(
            company=self.company, lead=self.lead,
            cadence=services.RAPPEL_DEMANDE_CADENCE, ordre=0,
            canal=RelanceEtape.Canal.APPEL,
            libelle=services.RAPPEL_DEMANDE_LIBELLE,
            due_at=JEUDI_9H, due_date=JEUDI_9H.date())
        avant = RelanceEtape.objects.filter(lead=self.lead).count()
        self.assertEqual(self._signal().pk, rappel.pk)
        self.assertEqual(RelanceEtape.objects.filter(lead=self.lead).count(),
                         avant)

    def test_une_touche_signal_traitee_laisse_poser_la_suivante(self):
        premiere = self._signal()
        premiere.statut = RelanceEtape.Statut.FAIT
        premiere.traite_le = MERCREDI_SOIR
        premiere.save(update_fields=['statut', 'traite_le'])
        seconde = self._signal()
        self.assertNotEqual(seconde.pk, premiere.pk)

    # ── La préférence du client gagne (CAD32) ──

    def test_whatsapp_uniquement_la_touche_est_un_message(self):
        self.lead.contact_preference = (
            cadence_temps.PREFERENCE_WHATSAPP_ONLY)
        self.lead.save(update_fields=['contact_preference'])
        touche = self._signal()
        self.assertEqual(touche.canal, RelanceEtape.Canal.WHATSAPP)

    def test_signal_inconnu_ne_pose_rien(self):
        self.assertIsNone(services.poser_touche_signal(self.lead, 'inconnu'))
        self.assertFalse(self._touches_signal().exists())

    def test_variante_par_id_scopee_a_la_societe(self):
        autre = Company.objects.create(nom='CAD130 Autre',
                                       slug='cad130-autre')
        self.assertIsNone(services.poser_touche_signal_du_lead_id(
            self.lead.pk, services.SIGNAL_PROPOSITION_ROUVERTE,
            company=autre))
        self.assertFalse(self._touches_signal().exists())
        self.assertIsNotNone(services.poser_touche_signal_du_lead_id(
            self.lead.pk, services.SIGNAL_PROPOSITION_ROUVERTE,
            company=self.company))
