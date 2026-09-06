"""MRY5 — `RelanceEtape` v2 : cadence, heure, gabarit, devis.

Ce que ce fichier verrouille, et POURQUOI :
  * l'idempotence devient PAR CADENCE — sans elle, un lead déjà en prise de
    contact n'aurait jamais reçu le suivi de son devis (l'ancienne garde
    « ce lead a déjà des étapes » les confondait) ;
  * une touche porte une HEURE (`due_at`) recalée sur la fenêtre d'appel :
    un lead créé un vendredi 20:30 est rappelé lundi 08:30, pas le lendemain
    à 20:30 ;
  * un lead « ne plus contacter », perdu ou archivé n'est JAMAIS relancé, et
    le refus laisse une trace (un refus silencieux ferait croire à Meryem que
    le lead est suivi) ;
  * la prochaine touche voyage avec le lead (annotation), sans un N+1 sur la
    liste ni le kanban ;
  * `?lead=` renvoie la frise complète, et reste borné à la société.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.selectors import (
    devis_a_cadence_active, prochaine_touche_par_lead, relance_etapes_dues)
from apps.crm.services import initialiser_plan_relance, marquer_etape_relance
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Vendredi 4 septembre 2026, 20:30 heure de Casablanca — après la fermeture.
VENDREDI_SOIR = datetime.datetime(2026, 9, 4, 20, 30, tzinfo=horaires.CASABLANCA)
#: Lundi 7 septembre 2026, 09:00 — en pleine fenêtre d'appel.
LUNDI_MATIN = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CadenceContactTests(TestCase):
    def setUp(self):
        self.company = _company('mry5-contact')
        self.acteur = User.objects.create_user(
            username='mry5-acteur', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)

    def test_un_lead_du_vendredi_soir_est_rappele_lundi_matin(self):
        """LE défaut que MRY8+MRY5 corrigent : sans recalage, la touche 1
        tombait vendredi 20:30 — hors fenêtre d'appel."""
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=VENDREDI_SOIR)
        premiere = etapes[0]
        locale = premiere.due_at.astimezone(horaires.CASABLANCA)
        self.assertEqual(locale.date(), datetime.date(2026, 9, 7))
        self.assertEqual(locale.hour, 8)
        self.assertEqual(locale.minute, 30)
        self.assertEqual(premiere.due_date, datetime.date(2026, 9, 7))

    def test_la_deuxieme_touche_tombe_trois_minutes_apres(self):
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI_MATIN)
        premiere, seconde = etapes[0], etapes[1]
        self.assertEqual(
            (seconde.due_at - premiere.due_at), datetime.timedelta(minutes=3))

    def test_le_gabarit_de_message_voyage_sur_la_touche(self):
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI_MATIN)
        self.assertEqual(etapes[0].template_cle, 'identite')
        self.assertEqual(etapes[1].template_cle, 'appel_ouverture')

    def test_due_date_est_la_date_locale_de_due_at(self):
        for etape in initialiser_plan_relance(
                self.lead, self.acteur, depart=LUNDI_MATIN):
            self.assertEqual(
                etape.due_date,
                etape.due_at.astimezone(horaires.CASABLANCA).date())


class IdempotenceParCadenceTests(TestCase):
    def setUp(self):
        self.company = _company('mry5-idem')
        self.acteur = User.objects.create_user(
            username='mry5-idem-u', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)

    def test_deux_cadences_coexistent_sur_le_meme_lead(self):
        """L'ancienne idempotence GLOBALE aurait renvoyé la cadence contact
        au lieu de créer le suivi du devis — le lead n'aurait jamais été
        relancé après l'envoi."""
        contact = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI_MATIN, cadence='contact')
        apres = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI_MATIN,
            cadence='apres_devis')
        self.assertTrue(contact)
        self.assertTrue(apres)
        self.assertEqual({e.cadence for e in contact}, {'contact'})
        self.assertEqual({e.cadence for e in apres}, {'apres_devis'})
        self.assertEqual(
            RelanceEtape.objects.filter(lead=self.lead).count(),
            len(contact) + len(apres))

    def test_second_appel_sur_la_meme_cadence_ne_duplique_rien(self):
        premier = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI_MATIN)
        second = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI_MATIN)
        self.assertEqual([e.pk for e in premier], [e.pk for e in second])


class GardesTests(TestCase):
    def setUp(self):
        self.company = _company('mry5-gardes')
        self.acteur = User.objects.create_user(
            username='mry5-garde-u', password='x', role_legacy='responsable',
            company=self.company)

    def _lead(self, **kw):
        return Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur, **kw)

    def _refus(self, lead, fragment):
        etapes = initialiser_plan_relance(lead, self.acteur)
        self.assertEqual(etapes, [])
        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any(fragment in (n.body or '') for n in notes),
            'le refus doit être TRACÉ : un refus silencieux fait croire à '
            'Meryem que le lead est suivi.')

    def test_ne_plus_contacter_refuse_et_trace(self):
        self._refus(self._lead(ne_plus_contacter=True), 'ne plus contacter')

    def test_lead_perdu_refuse_et_trace(self):
        self._refus(self._lead(perdu=True, motif_perte='Prix'), 'perdu')

    def test_lead_archive_refuse_et_trace(self):
        self._refus(self._lead(is_archived=True), 'archivé')

    def test_ne_plus_contacter_est_journalise_dans_le_chatter(self):
        """Un « ne plus contacter » posé par erreur coupe tout : il doit
        laisser une trace datée et nommée."""
        from apps.crm.activity import TRACKED_FIELDS
        self.assertIn('ne_plus_contacter', TRACKED_FIELDS)


class ProchaineToucheTests(TestCase):
    def setUp(self):
        self.company = _company('mry5-prochaine')
        self.acteur = User.objects.create_user(
            username='mry5-proch-u', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)
        self.etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI_MATIN)

    def test_selecteur_rend_la_touche_la_plus_proche(self):
        table = prochaine_touche_par_lead(self.company, [self.lead.pk])
        due_at, due_date, cadence, canal = table[self.lead.pk]
        self.assertEqual(due_at, self.etapes[0].due_at)
        self.assertEqual(cadence, 'contact')
        self.assertEqual(canal, self.etapes[0].canal)

    def test_lead_sans_touche_ouverte_est_absent(self):
        autre = Lead.objects.create(
            company=self.company, nom='Sans plan', owner=self.acteur)
        table = prochaine_touche_par_lead(
            self.company, [self.lead.pk, autre.pk])
        self.assertIn(self.lead.pk, table)
        self.assertNotIn(autre.pk, table)

    def test_liste_vide_ne_touche_pas_la_base(self):
        self.assertEqual(prochaine_touche_par_lead(self.company, []), {})

    def test_la_file_trie_a_la_minute(self):
        """Les lignes sans heure (créées avant MRY5) passent EN DERNIER —
        sans `nulls_last`, Postgres les remonterait en tête de la file."""
        ancienne = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=99,
            due_date=self.etapes[0].due_date, canal='appel', due_at=None)
        qs = relance_etapes_dues(
            self.company, self.acteur, scope='all',
            today=self.etapes[1].due_date)
        rangs = [e.pk for e in qs]
        self.assertIn(ancienne.pk, rangs)
        self.assertEqual(rangs[-1], ancienne.pk)


class LeadExposeSaProchaineToucheTests(TestCase):
    """Bug CI #29 — ces tests parlent de « en retard » / « pas en retard » :
    leur départ est RELATIF à maintenant, jamais une date fixe qui basculerait
    dans le passé au fil des mois."""

    def setUp(self):
        from django.utils import timezone
        self.company = _company('mry5-lead-api')
        self.acteur = User.objects.create_user(
            username='mry5-lead-u', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)
        self.api = _auth(self.acteur)
        self.futur = timezone.now() + datetime.timedelta(days=30)

    def test_les_trois_champs_arrivent_dans_la_liste_des_leads(self):
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=self.futur)
        resp = self.api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        ligne = next(r for r in rows if r['id'] == self.lead.pk)
        self.assertIsNotNone(ligne['prochaine_touche_at'])
        self.assertEqual(ligne['prochaine_touche_canal'], etapes[0].canal)
        self.assertFalse(ligne['touche_en_retard'])

    def test_touche_en_retard_bascule_a_vrai(self):
        initialiser_plan_relance(
            self.lead, self.acteur, depart=self.futur)
        RelanceEtape.objects.filter(lead=self.lead).update(
            due_date=datetime.date(2020, 1, 6))
        resp = self.api.get('/api/django/crm/leads/')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        ligne = next(r for r in rows if r['id'] == self.lead.pk)
        self.assertTrue(ligne['touche_en_retard'])

    def test_lead_sans_cadence_ne_ment_pas(self):
        resp = self.api.get('/api/django/crm/leads/')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        ligne = next(r for r in rows if r['id'] == self.lead.pk)
        self.assertIsNone(ligne['prochaine_touche_at'])
        self.assertFalse(ligne['touche_en_retard'])


class ApiRelanceEtapeTests(TestCase):
    def setUp(self):
        self.company = _company('mry5-api')
        self.autre = _company('mry5-api-autre')
        self.acteur = User.objects.create_user(
            username='mry5-api-u', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)
        self.api = _auth(self.acteur)

    def test_initialiser_accepte_une_cadence(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/relance/initialiser/',
            {'cadence': 'reveil'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual({r['cadence'] for r in resp.data}, {'reveil'})

    def test_cadence_inconnue_refusee(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/relance/initialiser/',
            {'cadence': 'inventee'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('cadence', resp.data)

    def test_ne_plus_contacter_refuse_linitialisation(self):
        self.lead.ne_plus_contacter = True
        self.lead.save(update_fields=['ne_plus_contacter'])
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/relance/initialiser/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_filtre_lead_rend_la_frise_complete(self):
        etapes = initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI_MATIN)
        marquer_etape_relance(
            etapes[0], self.acteur, RelanceEtape.Statut.FAIT)
        resp = self.api.get(
            f'/api/django/crm/relance-etapes/?lead={self.lead.pk}')
        self.assertEqual(resp.status_code, 200)
        # La frise montre le PASSÉ autant que le futur : la touche faite y est.
        self.assertEqual(resp.data['count'], len(etapes))
        statuts = {r['statut'] for r in resp.data['results']}
        self.assertIn('fait', statuts)

    def test_filtre_lead_dune_autre_societe_rend_une_liste_vide(self):
        owner_autre = User.objects.create_user(
            username='mry5-api-autre-u', password='x',
            role_legacy='responsable', company=self.autre)
        lead_autre = Lead.objects.create(
            company=self.autre, nom='Voisin', owner=owner_autre)
        initialiser_plan_relance(
            lead_autre, owner_autre, depart=LUNDI_MATIN)
        resp = self.api.get(
            f'/api/django/crm/relance-etapes/?lead={lead_autre.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)

    def test_la_forme_porte_les_champs_du_contrat(self):
        initialiser_plan_relance(
            self.lead, self.acteur, depart=LUNDI_MATIN)
        resp = self.api.get(
            f'/api/django/crm/relance-etapes/?lead={self.lead.pk}')
        ligne = resp.data['results'][0]
        for champ in ('id', 'lead', 'lead_nom', 'lead_owner_nom',
                      'lead_telephone', 'lead_whatsapp', 'lead_langue',
                      'lead_score', 'lead_priorite', 'cadence', 'ordre',
                      'due_date', 'due_at', 'canal', 'libelle',
                      'template_cle', 'statut', 'note', 'overdue', 'devis',
                      'devis_reference'):
            self.assertIn(champ, ligne)


class DevisACadenceActiveTests(TestCase):
    """Sélecteur consommé par ``ventes`` (MRY7) — jamais un import de
    ``crm.models`` côté ventes."""

    def setUp(self):
        self.company = _company('mry5-devis')
        self.acteur = User.objects.create_user(
            username='mry5-devis-u', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)

    def _devis(self, reference):
        from decimal import Decimal

        from apps.crm.models import Client
        from apps.ventes.models import Devis
        client = Client.objects.create(
            company=self.company, nom='Client', email=f'{reference}@ex.com')
        return Devis.objects.create(
            company=self.company, reference=reference, client=client,
            lead=self.lead, statut='envoye', taux_tva=Decimal('20.00'))

    def _touche(self, devis, statut=RelanceEtape.Statut.A_FAIRE):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=1,
            due_date=datetime.date(2026, 9, 9), canal='whatsapp',
            cadence='apres_devis', devis=devis, statut=statut)

    def test_faux_sans_devis(self):
        self.assertFalse(devis_a_cadence_active(None))
        self.assertFalse(devis_a_cadence_active(999999))

    def test_vrai_quand_une_touche_du_devis_reste_a_faire(self):
        devis = self._devis('DEV-MRY5-0001')
        self._touche(devis)
        self.assertTrue(devis_a_cadence_active(devis.pk))

    def test_faux_quand_toutes_les_touches_sont_traitees(self):
        devis = self._devis('DEV-MRY5-0002')
        self._touche(devis, statut=RelanceEtape.Statut.FAIT)
        self.assertFalse(devis_a_cadence_active(devis.pk))

    def test_la_touche_survit_a_la_suppression_du_devis(self):
        """`on_delete=SET_NULL` : l'historique de relance reste, orphelin —
        supprimer un devis ne doit pas effacer la trace du travail fait."""
        devis = self._devis('DEV-MRY5-0003')
        touche = self._touche(devis)
        devis.delete()
        touche.refresh_from_db()
        self.assertIsNone(touche.devis_id)
        self.assertEqual(touche.cadence, 'apres_devis')
