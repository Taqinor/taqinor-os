"""SUIVI E19 — parquer au Froid ferme les étapes moteur restantes.

SUIVI-PARCOURS 30/09/2026 (table : « Après la dernière touche : le dossier part
au Froid et ses réveils sont programmés »). ``cloturer_cadence`` (MRY11)
parquait le lead au Froid puis démarrait les réveils — mais une étape de
FILET encore ouverte (cadence ``generique`` : « Appeler le client », « Rappeler
le client (il l'a demandé) »…) faisait lever ``CadenceActiveConflit`` à
``initialiser_plan_relance('reveil')`` (une seule cadence à la fois, CADX),
exception avalée : le lead restait au Froid SANS aucun réveil — et avec une
étape orpheline.

Décision : avant de poser les réveils, les étapes ``generique`` encore
ouvertes sont annulées (statut moteur, motif « dossier parqué au Froid »).

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages, cadence_plan
from apps.crm import cadence_reperes
from apps.crm.cadence_config import CLE_APPEL_APRES_REPONSE, CLE_DEVIS, q_etape
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
ANNULEE = RelanceEtape.Statut.ANNULEE

_seq = itertools.count(1)


class ParquerAuFroidTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E19 {n}', slug=f'suivi-e19-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e19-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Injoignable E19 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266219{n:04d}')
        self._appels(self.lead)

    def _appels(self, lead, nombre=5):
        """CADV22 — les appels signés sans lesquels « injoignable » est refusé."""
        LeadActivity.objects.bulk_create([
            LeadActivity(company=self.company, lead=lead, user=self.acteur,
                         kind=LeadActivity.Kind.APPEL, body='Pas de réponse.')
            for _ in range(nombre)])

    def _filet_ouvert(self):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL,
            libelle='Appeler le client — il a répondu au message',
            cle=CLE_APPEL_APRES_REPONSE,
            due_at=GEL + datetime.timedelta(days=3),
            due_date=(GEL + datetime.timedelta(days=3)).date())

    def _reveils(self):
        return self.lead.relance_etapes.filter(cadence='reveil',
                                               statut=A_FAIRE)

    def test_une_etape_de_filet_ne_bloque_plus_les_reveils(self):
        filet = self._filet_ouvert()

        cadence_plan.cloturer_cadence(self.lead, self.acteur, 'contact')

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.COLD)
        filet.refresh_from_db()
        self.assertEqual(filet.statut, ANNULEE)
        self.assertEqual(filet.note, cadence_reperes.MOTIF_PARQUE_AU_FROID)
        self.assertTrue(self._reveils().exists())

    def test_sans_filet_les_reveils_sont_poses_comme_avant(self):
        cadence_plan.cloturer_cadence(self.lead, self.acteur, 'contact')

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.COLD)
        self.assertTrue(self._reveils().exists())

    def test_la_derniere_touche_sans_reponse_parque_avec_ses_reveils(self):
        filet = self._filet_ouvert()
        derniere = max(CADENCES_DEFAUT['contact'], key=lambda e: e['ordre'])
        touche = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=derniere['ordre'], canal=derniere['canal'],
            libelle=derniere['libelle'], due_at=GEL, due_date=GEL.date(),
            cadence_depart=GEL - datetime.timedelta(days=14))

        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{touche.pk}/fait/',
            {'outcome': 'non_joint'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.COLD)
        filet.refresh_from_db()
        self.assertEqual(filet.statut, ANNULEE)
        self.assertTrue(self._reveils().exists())
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='generique', statut=A_FAIRE).exists())

    def test_la_fin_de_gabarit_ecrit_la_raison(self):
        """CADV72 — contact : injoignable ; après-devis : sans date ; étiquette
        gardée, rejouer n'écrit aucune seconde ligne. Mutant : ne plus appeler
        ``parquer_lead`` ⇒ ``parc_raison`` vide."""
        cadence_plan.cloturer_cadence(self.lead, self.acteur, 'contact')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.COLD)
        self.assertEqual((self.lead.parc_etat, self.lead.parc_raison),
                         ('nurture', 'injoignable'))
        self.assertIn('Injoignable', self.lead.tags)
        cadence_plan.cloturer_cadence(self.lead, self.acteur, 'contact')
        self.assertEqual(self.lead.activites.filter(
            field='parc_raison').count(), 1)
        autre = Lead.objects.create(
            company=self.company, nom='Apres devis', stage=stages.FOLLOW_UP,
            owner=self.acteur, telephone='+212662190001')
        self._appels(autre, 1)
        cadence_plan.cloturer_cadence(autre, self.acteur, 'apres_devis')
        autre.refresh_from_db()
        self.assertEqual((autre.parc_etat, autre.parc_raison, autre.stage),
                         ('nurture', 'pas_maintenant_sans_date', stages.COLD))

    # ── CADV21 — parquer_lead : le point d'écriture unique ──

    def test_parquer_lead_pose_l_etat_la_raison_et_le_froid(self):
        from apps.crm.fiche_funnel import parquer_lead
        parquer_lead(self.lead, 'injoignable', None, self.acteur)
        self.lead.refresh_from_db()
        self.assertEqual(
            (self.lead.parc_etat, self.lead.parc_raison,
             self.lead.parc_jusqu_au), ('nurture', 'injoignable', None))
        self.assertEqual(self.lead.stage, stages.COLD)
        self.assertEqual(self.lead.activites.filter(
            field='parc_raison').count(), 1)

    def test_un_lead_sorti_du_froid_se_range_a_nouveau(self):
        """CADV72 — le no-op de rejeu ne vaut que pour un lead DÉJÀ au Froid :
        sorti depuis (colonnes gardées), le même parcage le range encore.
        Mutant : retirer la condition sur l'étape ⇒ échec."""
        from apps.crm.fiche_funnel import parquer_lead
        parquer_lead(self.lead, 'injoignable', None, self.acteur)
        parquer_lead(self.lead, 'injoignable', None, self.acteur)
        self.assertEqual(self.lead.activites.filter(
            field='parc_raison').count(), 1)
        Lead.objects.filter(pk=self.lead.pk).update(stage=stages.CONTACTED)
        self.lead.refresh_from_db()
        parquer_lead(self.lead, 'injoignable', None, self.acteur)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.COLD)

    def _lead_neuf(self, **kw):
        return Lead.objects.create(
            company=self.company, nom='Neuf', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212662190002', **kw)

    def _instantane(self, lead):
        lead.refresh_from_db()
        return (lead.stage, lead.parc_etat, lead.parc_raison, lead.tags,
                lead.activites.count())

    def test_injoignable_sous_cinq_appels_est_refuse(self):
        """CADV22 — un refus n'écrit rien. Mutant : seuil 5 → 3 ⇒ échec."""
        from apps.crm.fiche_funnel import ParcRefuse, parquer_lead
        lead = self._lead_neuf()
        self._appels(lead, 3)
        avant = self._instantane(lead)
        with self.assertRaisesMessage(
                ParcRefuse, 'injoignable exige 5 appels tracés (3 trouvés)'):
            parquer_lead(lead, 'injoignable', None, self.acteur)
        self.assertEqual(self._instantane(lead), avant)
        self._appels(lead, 2)
        parquer_lead(lead, 'injoignable', None, self.acteur)
        self.assertEqual(lead.parc_raison, 'injoignable')

    def test_un_gabarit_court_parque_apres_ses_propres_appels(self):
        """D-CADV22-GABARIT-COURT — min(5, appels du gabarit). Mutant : min → 5 fixe,
        ou comptage de tous les canaux ⇒ échec."""
        from apps.crm.fiche_funnel import ParcRefuse, appels_exiges_injoignable, parquer_lead
        gabarit = CadenceRelanceEtape.objects.filter(
            company=self.company, cadence='contact', actif=True)
        appels = list(gabarit.filter(canal='appel').order_by('ordre'))
        self.assertGreater(len(appels), 5, 'le gabarit livré dépasse le plafond')
        self.assertEqual(appels_exiges_injoignable(self.lead), 5)
        gabarit.filter(pk__in=[e.pk for e in appels[3:]]).update(actif=False)
        self.assertEqual(appels_exiges_injoignable(self.lead), 3)

        lead = self._lead_neuf()
        self._appels(lead, 2)
        avant = self._instantane(lead)
        with self.assertRaisesMessage(
                ParcRefuse, 'injoignable exige 3 appels tracés (2 trouvés)'):
            parquer_lead(lead, 'injoignable', None, self.acteur)
        self.assertEqual(self._instantane(lead), avant)
        self._appels(lead, 1)
        parquer_lead(lead, 'injoignable', None, self.acteur)
        self.assertEqual(lead.parc_raison, 'injoignable')

    def test_un_gabarit_sans_appel_reste_soumis_a_la_regle_des_zero_touches(self):
        from apps.crm.fiche_funnel import ParcRefuse, parquer_lead
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence='contact', canal='appel').update(actif=False)
        with self.assertRaisesMessage(ParcRefuse, 'aucun parcage à 0 touche'):
            parquer_lead(self._lead_neuf(), 'injoignable', None, self.acteur)

    def test_le_compte_des_appels_ne_seede_rien(self):
        # L'écran le lit : une lecture n'écrit jamais (société sans gabarit).
        from apps.crm.fiche_funnel import APPELS_MIN_INJOIGNABLE, appels_exiges_injoignable
        vierge = Company.objects.create(nom='E19 vierge', slug='suivi-e19-vierge')
        lead = Lead(company=vierge, nom='Sans gabarit')
        self.assertEqual(appels_exiges_injoignable(lead), APPELS_MIN_INJOIGNABLE)
        self.assertFalse(CadenceRelanceEtape.objects.filter(company=vierge).exists())

    def test_les_appels_systeme_ne_comptent_pas(self):
        from apps.crm.fiche_funnel import nb_contacts_humains
        lead = self._lead_neuf()
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=None,
            kind=LeadActivity.Kind.APPEL, body='Système.')
        self.assertEqual(nb_contacts_humains(lead), 0)

    def test_aucun_parcage_a_zero_touche_sauf_les_trois_raisons(self):
        from apps.crm.fiche_funnel import ParcRefuse, parquer_lead
        lead = self._lead_neuf()
        avant = self._instantane(lead)
        with self.assertRaisesMessage(ParcRefuse, 'aucun parcage à 0 touche'):
            parquer_lead(lead, 'budget', None, self.acteur)
        self.assertEqual(self._instantane(lead), avant)
        for raison in ('faux_numero', 'doublon', 'test'):
            with self.subTest(raison):
                sans_touche = self._lead_neuf()
                parquer_lead(sans_touche, raison, None, self.acteur)
                self.assertEqual(sans_touche.parc_etat, 'archive')

    def test_exiger_touche_faux_laisse_passer_la_seule_regle_des_zero_touches(self):
        from apps.crm.fiche_funnel import ParcRefuse, parquer_lead
        lead = self._lead_neuf()
        parquer_lead(lead, 'pas_maintenant_sans_date', None, None,
                     exiger_touche=False)
        self.assertEqual(lead.parc_raison, 'pas_maintenant_sans_date')
        with self.assertRaises(ParcRefuse):
            parquer_lead(self._lead_neuf(), 'injoignable', None, None,
                         exiger_touche=False)

    def test_whatsapp_only_compte_ses_whatsapp(self):
        from apps.crm.fiche_funnel import parquer_lead
        lead = self._lead_neuf(
            contact_preference=Lead.ContactPreference.WHATSAPP_ONLY)
        LeadActivity.objects.bulk_create([
            LeadActivity(company=self.company, lead=lead, user=self.acteur,
                         kind=LeadActivity.Kind.WHATSAPP, body='Message.')
            for _ in range(5)])
        parquer_lead(lead, 'injoignable', None, self.acteur)
        self.assertEqual(lead.parc_etat, 'nurture')

    def test_la_fin_de_gabarit_note_le_refus_sans_parquer(self):
        lead = self._lead_neuf()
        self._appels(lead, 3)
        cadence_plan.cloturer_cadence(lead, self.acteur, 'contact')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertIsNone(lead.parc_raison)
        self.assertFalse(lead.relance_etapes.filter(cadence='reveil').exists())
        self.assertTrue(lead.activites.filter(
            body__startswith='Mise au Froid refusée : injoignable exige').exists())
        # D-CADV22-PROMESSE — la suite est un autre appel de la même cadence,
        # jamais l'étape devis, et le filet n'a plus rien à poser.
        [appel] = lead.relance_etapes.filter(statut=A_FAIRE)
        self.assertEqual((appel.cadence, appel.canal), ('contact', 'appel'))
        self.assertEqual(appel.libelle, cadence_plan.LIBELLE_TOUCHE_AVANT_FROID)
        self.assertGreater(appel.ordre, max(e['ordre'] for e in CADENCES_DEFAUT['contact']))
        self.assertFalse(lead.relance_etapes.filter(q_etape(CLE_DEVIS)).exists())

    def test_whatsapp_uniquement_la_touche_de_plus_reste_un_whatsapp(self):
        lead = self._lead_neuf(
            contact_preference=Lead.ContactPreference.WHATSAPP_ONLY)
        cadence_plan.cloturer_cadence(lead, self.acteur, 'contact')
        self.assertEqual(lead.relance_etapes.get(statut=A_FAIRE).canal, 'whatsapp')

    def test_parquer_en_standby_garde_l_etape_et_la_date(self):
        from apps.crm.fiche_funnel import parquer_lead
        jour = datetime.date(2026, 12, 15)
        parquer_lead(self.lead, 'plus_tard_date', jour, self.acteur)
        self.lead.refresh_from_db()
        self.assertEqual(
            (self.lead.parc_etat, self.lead.parc_raison,
             self.lead.parc_jusqu_au), ('standby', 'plus_tard_date', jour))
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_parquer_refuse_raison_inconnue_et_standby_sans_date(self):
        from apps.crm.fiche_funnel import parquer_lead
        with self.assertRaises(ValueError):
            parquer_lead(self.lead, 'pas_envie', None, self.acteur)
        with self.assertRaises(ValueError):
            parquer_lead(self.lead, 'plus_tard_date', None, self.acteur)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.parc_etat)
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_la_table_des_raisons_est_celle_du_contrat(self):
        import json
        from pathlib import Path
        from apps.crm.fiche_funnel import ETAT_PAR_RAISON
        contrat = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'lead.json').read_text(encoding='utf-8'))
        self.assertEqual(ETAT_PAR_RAISON, contrat['notes']['codes_raison'])
        self.assertEqual({r.value for r in Lead.ParcRaison},
                         set(ETAT_PAR_RAISON))

    def test_un_patch_portant_parc_etat_est_ignore_et_la_fiche_le_sert(self):
        reponse = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'parc_etat': 'archive', 'parc_raison': 'doublon',
             'parc_jusqu_au': '2026-12-31'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.parc_etat)
        self.assertIsNone(self.lead.parc_raison)
        lu = self.api.get(f'/api/django/crm/leads/{self.lead.pk}/').data
        for cle in ('parc_etat', 'parc_raison', 'parc_jusqu_au'):
            self.assertIn(cle, lu)
            self.assertIsNone(lu[cle])

    def test_le_froid_sans_raison_est_liste(self):
        """CADV75 — trois COLD (un avec parc_raison, un sans, un perdu), un
        CONTACTED sans raison, un COLD d'une autre société : seul le COLD natif,
        vivant et sans raison est listé, sans donnée personnelle."""
        from apps.crm.fiche_funnel import parquer_lead
        from apps.crm.selectors import leads_froid_sans_raison

        def froid(nom, **champs):
            return Lead.objects.create(
                company=self.company, nom=nom, stage=stages.COLD,
                owner=self.acteur, **champs)

        avec = froid('Avec raison')
        self._appels(avec, 1)
        parquer_lead(avec, 'budget', None, self.acteur)
        sans = froid('Sans raison')
        froid('Perdu', perdu=True, motif_perte='Prix')
        froid('Opposé', ne_plus_contacter=True)
        froid('Archivé', is_archived=True)
        autre = Company.objects.create(nom='Autre froid', slug='autre-froid')
        Lead.objects.create(company=autre, nom='Froid ailleurs',
                            stage=stages.COLD)
        self.assertEqual(leads_froid_sans_raison(self.company), [
            {'id': sans.pk, 'stage': stages.COLD, 'source': sans.source}])
        self.assertEqual(self.lead.stage, stages.CONTACTED)
