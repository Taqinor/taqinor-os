"""MRY9 — Les six déclencheurs d'arrêt, et l'unique fonction qui les sert.

La faute la plus visible qu'un CRM puisse commettre est de relancer un client
qui vient de signer. Six chemins mènent à « on arrête » ; deux implémentations
auraient dérivé, donc il n'y en a qu'UNE (`services.arreter_cadence`), et ce
fichier prouve que chacun des six l'emprunte :

  (a) devis accepté           (d) « ne plus contacter »
  (b) passage SIGNED / COLD   (e) issue d'appel joint / intéressé / refus
  (c) lead perdu — les TROIS chemins (fiche, masse, refus de devis)

Il verrouille aussi les deux nuances qui font la différence :
  * « joint » n'arrête PAS la cadence après devis (un client joint reste à
    relancer sur sa proposition) ;
  * « refus » au téléphone n'écrit PAS `perdu` — c'est une décision humaine
    qui exige un motif (MRY22), pas un effet de bord d'un appel.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    arreter_cadence, avancer_stage_lead_vers, initialiser_plan_relance)
from apps.parametres.models import CompanyProfile

User = get_user_model()

LUNDI = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'mry9'

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)
        self.contact = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence='contact')
        self.apres = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence='apres_devis')

    def _ouvertes(self, cadence=None):
        qs = self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE)
        if cadence:
            qs = qs.filter(cadence=cadence)
        return qs.count()


class ArreterCadenceTests(_Base):
    slug = 'mry9-fn'

    def test_arrete_tout_par_defaut(self):
        n = arreter_cadence(self.lead, user=self.acteur, motif='signé')
        self.assertEqual(n, len(self.contact) + len(self.apres))
        self.assertEqual(self._ouvertes(), 0)

    def test_arrete_seulement_les_cadences_demandees(self):
        arreter_cadence(self.lead, user=self.acteur, motif='joint',
                        cadences=['contact'])
        self.assertEqual(self._ouvertes('contact'), 0)
        self.assertEqual(self._ouvertes('apres_devis'), len(self.apres))

    def test_le_motif_est_ecrit_sur_chaque_touche(self):
        arreter_cadence(self.lead, user=self.acteur, motif='ne plus contacter')
        for etape in self.lead.relance_etapes.filter(
                statut=RelanceEtape.Statut.SAUTEE):
            self.assertEqual(etape.note, 'ne plus contacter')
            self.assertEqual(etape.traite_par, self.acteur)
            self.assertIsNotNone(etape.traite_le)

    def test_une_seule_note_chatter(self):
        avant = LeadActivity.objects.filter(lead=self.lead).count()
        arreter_cadence(self.lead, user=self.acteur, motif='signé')
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), avant + 1)

    def test_idempotente_sans_touche_ouverte(self):
        arreter_cadence(self.lead, user=self.acteur, motif='signé')
        avant = LeadActivity.objects.filter(lead=self.lead).count()
        n = arreter_cadence(self.lead, user=self.acteur, motif='signé')
        self.assertEqual(n, 0)
        # Pas même une note : sinon chaque passage d'étape empilerait des
        # lignes vides dans l'historique du lead.
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), avant)

    def test_relance_date_est_recalculee_puis_videe(self):
        arreter_cadence(self.lead, user=self.acteur, motif='joint',
                        cadences=['contact'])
        self.lead.refresh_from_db()
        restante = self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).order_by('due_date').first()
        self.assertEqual(self.lead.relance_date, restante.due_date)
        arreter_cadence(self.lead, user=self.acteur, motif='signé')
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.relance_date)

    def test_ne_touche_pas_le_lead_dune_autre_societe(self):
        autre = _company('mry9-autre')
        owner = User.objects.create_user(
            username='mry9-autre-u', password='x', company=autre)
        lead_autre = Lead.objects.create(
            company=autre, nom='Voisin', owner=owner)
        etapes = initialiser_plan_relance(lead_autre, owner, depart=LUNDI)
        arreter_cadence(self.lead, user=self.acteur, motif='signé')
        self.assertEqual(
            lead_autre.relance_etapes.filter(
                statut=RelanceEtape.Statut.A_FAIRE).count(), len(etapes))


class DeclencheurEtapeTests(_Base):
    """(b) — SIGNED arrête tout ; COLD ne touche pas les réveils."""

    slug = 'mry9-stage'

    def test_signed_arrete_tout(self):
        avancer_stage_lead_vers(self.lead, self.acteur, stages.SIGNED)
        self.assertEqual(self._ouvertes(), 0)

    def test_cold_arrete_contact_et_apres_devis(self):
        avancer_stage_lead_vers(self.lead, self.acteur, stages.COLD)
        self.assertEqual(self._ouvertes('contact'), 0)
        self.assertEqual(self._ouvertes('apres_devis'), 0)

    def test_cold_ne_touche_pas_les_reveils(self):
        """COLD est un PARKING : arrêter les réveils J30/J60 condamnerait le
        lead à ne plus jamais être réveillé (MRY11)."""
        reveils = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI, cadence='reveil')
        avancer_stage_lead_vers(self.lead, self.acteur, stages.COLD)
        self.assertEqual(self._ouvertes('reveil'), len(reveils))


class DeclencheurIssueAppelTests(_Base):
    """(e) — l'issue de l'appel arrête la BONNE cadence, et elle seule."""

    slug = 'mry9-outcome'

    #: Sentinelle : `None` est une VALEUR valide (activité système), on ne
    #: peut donc pas s'en servir comme « paramètre absent ».
    _DEFAUT = object()

    def _appel(self, outcome, user=_DEFAUT):
        return LeadActivity.objects.create(
            company=self.company, lead=self.lead,
            user=self.acteur if user is self._DEFAUT else user,
            kind=LeadActivity.Kind.APPEL, outcome=outcome, body='Appel')

    def test_joint_arrete_contact_seulement(self):
        self._appel('joint')
        self.assertEqual(self._ouvertes('contact'), 0)
        self.assertEqual(self._ouvertes('apres_devis'), len(self.apres))

    def test_interesse_arrete_contact_seulement(self):
        self._appel('interesse')
        self.assertEqual(self._ouvertes('contact'), 0)
        self.assertEqual(self._ouvertes('apres_devis'), len(self.apres))

    def test_refus_arrete_les_deux_sans_marquer_perdu(self):
        self._appel('refuse')
        # QJ-INVARIANT (07/09/2026) : les DEUX cadences sont arrêtées, mais le
        # dossier ne disparaît pas — une étape « décider la suite » reste (la
        # liste ne se termine que par Froid ou Signé ; « perdu » ci-dessous la
        # retire).
        self.assertEqual(self._ouvertes('contact'), 0)
        self.assertEqual(self._ouvertes('apres_devis'), 0)
        self.assertEqual(self._ouvertes('generique'), 1)
        self.lead.refresh_from_db()
        self.assertFalse(
            self.lead.perdu,
            "« perdu » est une décision humaine avec motif (MRY22), jamais "
            "un effet de bord d'un appel.")

    def test_une_issue_neutre_ne_change_rien(self):
        self._appel('non_joint')
        self.assertEqual(self._ouvertes('contact'), len(self.contact))

    def test_une_activite_systeme_ne_decide_pas(self):
        self._appel('joint', user=None)
        self.assertEqual(self._ouvertes('contact'), len(self.contact))


class DeclencheurPerduTests(_Base):
    """(c) — les TROIS chemins vers « perdu » arrêtent les relances."""

    slug = 'mry9-perdu'

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        return api

    def test_patch_de_la_fiche(self):
        resp = self._api().patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'perdu': True, 'motif_perte': 'Prix'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._ouvertes(), 0)

    def test_action_en_masse(self):
        from apps.crm.services import apply_bulk_action
        apply_bulk_action(
            company=self.company, user=self.acteur, lead_ids=[self.lead.pk],
            op='set_perdu', params={'motif': 'Concurrent'})
        self.assertEqual(self._ouvertes(), 0)

    def test_refus_de_devis_avec_marquage_perdu(self):
        from core.events import devis_refused

        class _Devis:
            pk = 1
            lead_id = self.lead.pk
            company = self.company
        devis_refused.send(
            sender='test', devis=_Devis, user=self.acteur,
            motif_refus='Trop cher', marquer_lead_perdu=True)
        self.assertEqual(self._ouvertes(), 0)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.perdu)


class DeclencheurNePlusContacterTests(_Base):
    """(d) — « ne plus contacter » coupe tout, sans marquer perdu."""

    slug = 'mry9-npc'

    def test_patch_arrete_tout_sans_marquer_perdu(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        resp = api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'ne_plus_contacter': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._ouvertes(), 0)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.ne_plus_contacter)
        self.assertFalse(self.lead.perdu)


class ActionArreterRelanceTests(_Base):
    slug = 'mry9-action'

    def _api(self, user=None):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user or self.acteur)}'))
        return api

    def test_motif_obligatoire(self):
        resp = self._api().post(
            f'/api/django/crm/leads/{self.lead.pk}/relance/arreter/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('motif', resp.data)

    def test_arrete_et_renvoie_le_compte(self):
        resp = self._api().post(
            f'/api/django/crm/leads/{self.lead.pk}/relance/arreter/',
            {'motif': 'Client injoignable'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            resp.data['arretees'], len(self.contact) + len(self.apres))
        self.assertEqual(self._ouvertes(), 0)

    def test_cadences_ciblees(self):
        resp = self._api().post(
            f'/api/django/crm/leads/{self.lead.pk}/relance/arreter/',
            {'motif': 'joint', 'cadences': ['contact']}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._ouvertes('apres_devis'), len(self.apres))

    def test_lead_dune_autre_societe_404(self):
        autre = _company('mry9-action-autre')
        owner = User.objects.create_user(
            username='mry9-action-autre-u', password='x', company=autre)
        lead_autre = Lead.objects.create(
            company=autre, nom='Voisin', owner=owner)
        resp = self._api().post(
            f'/api/django/crm/leads/{lead_autre.pk}/relance/arreter/',
            {'motif': 'test'}, format='json')
        self.assertEqual(resp.status_code, 404)
