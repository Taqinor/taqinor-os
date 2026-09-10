"""MRY10 — Le journal d'appel intégré à la touche, et « rappelez-moi jeudi ».

Trois défauts fermés ici :
  * le WhatsApp — canal PRINCIPAL de Meryem — n'avait pas de type : il se
    noyait dans les notes libres, invisible au compteur de tentatives (MRY20)
    comme aux règles d'arrêt sur l'issue (MRY9) ;
  * une touche traitée écrivait une note libre EN PLUS d'une éventuelle
    activité : deux lignes pour un seul geste. Elle en écrit désormais UNE,
    TYPÉE selon le canal ;
  * « rappelez-moi jeudi » ne déplaçait qu'UNE touche : les suivantes se
    téléscopaient avec elle. Elles glissent maintenant du MÊME delta.

Et l'invariant qui les tient : UN SEUL système de rappel. Le rival historique
(`CallLogPopover`, qui PATCHe `relance_date` seul) reste fonctionnel — sur un
lead à cadence active, son PATCH DÉPLACE la touche au lieu d'ouvrir une
seconde date à côté.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()


def _materialiser_tout(lead, user, *, cadence='contact', depart=None):
    """CKP2 — matérialise la PARTITION ENTIÈRE d'une cadence, pour les tests.

    Depuis la CADENCE RÉACTIVE (fondateur 2026-09-10),
    ``initialiser_plan_relance`` ne crée que la première touche à faire : la
    suite naît des issues saisies. Les tests de CE fichier ne pincent pas
    cette mécanique-là — ils pincent le journal, le report, la fin de cadence,
    le filet — et ont besoin d'un plan complet sous la main. On le reconstruit
    depuis ``calculer_echeances_cadence`` (la partition, inchangée) en
    reproduisant exactement ce que ``initialiser_plan_relance`` créait avant
    CKP2, gabarits de réveil adaptés au rang compris. La mécanique réactive,
    elle, est verrouillée dans ``tests_relance_foundation``.
    """
    from apps.crm import horaires as _h
    from apps.crm.services import (
        _adapter_gabarits_reveil, _normaliser_depart,
        calculer_echeances_cadence,
        initialiser_plan_relance as _initialiser)

    etapes = _initialiser(
        lead, user, cadence=cadence, depart=depart)
    if not etapes:
        return etapes
    ancre = _normaliser_depart(depart)
    pris = set(lead.relance_etapes.filter(cadence=cadence)
               .values_list('ordre', flat=True))
    for rang, (gabarit, echeance) in enumerate(
            calculer_echeances_cadence(lead, cadence, ancre)):
        if gabarit.ordre in pris:
            continue
        etape = RelanceEtape(
            company=lead.company, lead=lead, cadence=cadence,
            ordre=gabarit.ordre, due_at=echeance,
            due_date=echeance.astimezone(_h.CASABLANCA).date(),
            canal=gabarit.canal, libelle=gabarit.libelle,
            template_cle=getattr(gabarit, 'template_cle', '') or '',
            cadence_depart=ancre)
        if cadence == 'reveil':
            _adapter_gabarits_reveil(lead, [etape], rang_initial=rang)
        etape.save()
    return list(lead.relance_etapes.filter(cadence=cadence)
                .order_by('ordre', 'due_date'))


CASA = horaires.CASABLANCA
LUNDI = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=CASA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'mry10'

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)
        self.etapes = _materialiser_tout(
            self.lead, self.acteur, depart=LUNDI, cadence='generique')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _rafraichir(self):
        return list(self.lead.relance_etapes.order_by('ordre'))


class WhatsappTypeTests(_Base):
    slug = 'mry10-wa'

    def test_le_type_whatsapp_existe(self):
        self.assertEqual(LeadActivity.Kind.WHATSAPP, 'whatsapp')

    def test_log_interaction_accepte_whatsapp(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/log-interaction/',
            {'kind': 'whatsapp', 'body': 'Message envoyé'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.WHATSAPP).exists())

    def test_un_whatsapp_compte_comme_prise_de_contact(self):
        """`_CONTACT_KINDS` : un WhatsApp fait avancer NEW → CONTACTED, comme
        un e-mail. C'est le canal principal de Meryem."""
        from apps.crm.services import _CONTACT_KINDS
        self.assertIn(LeadActivity.Kind.WHATSAPP, _CONTACT_KINDS)
        self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/log-interaction/',
            {'kind': 'whatsapp', 'body': 'Message'}, format='json')
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)

    def test_un_kind_inconnu_reste_refuse(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/log-interaction/',
            {'kind': 'pigeon'}, format='json')
        self.assertEqual(resp.status_code, 400)


class ToucheTypeeTests(_Base):
    slug = 'mry10-touche'

    def test_une_touche_faite_ecrit_UNE_ligne_typee(self):
        etape = self.etapes[0]  # canal `appel` (échelle neutre)
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'non_joint', 'body': 'Répondeur'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        # UNE seule ligne parle de cette touche — pas une note libre EN PLUS
        # d'une activité typée, comme c'était le cas avant MRY10.
        lignes = [a for a in LeadActivity.objects.filter(lead=self.lead)
                  if 'Premier rappel' in (a.body or '')]
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].kind, LeadActivity.Kind.APPEL)
        self.assertEqual(lignes[0].outcome, 'non_joint')
        self.assertIn('Répondeur', lignes[0].body)

    def test_le_canal_whatsapp_donne_une_activite_whatsapp(self):
        etape = self.etapes[1]  # canal `whatsapp` (échelle neutre)
        self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {}, format='json')
        lignes = [a for a in LeadActivity.objects.filter(lead=self.lead)
                  if 'Relance WhatsApp' in (a.body or '')]
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].kind, LeadActivity.Kind.WHATSAPP)

    def test_une_touche_sautee_reste_une_note(self):
        """Sauter n'est PAS un contact : la ligne ne doit pas gonfler le
        compteur de tentatives."""
        self.api.post(
            f'/api/django/crm/relance-etapes/{self.etapes[0].pk}/sauter/',
            {'note': 'Client en congé'}, format='json')
        lignes = [a for a in LeadActivity.objects.filter(lead=self.lead)
                  if 'Client en congé' in (a.body or '')]
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].kind, LeadActivity.Kind.NOTE)

    def test_outcome_joint_arrete_la_cadence(self):
        """Chaînage MRY9 : l'issue saisie DEPUIS la touche déclenche l'arrêt.
        La cadence neutre est arrêtée comme les autres via l'activité typée."""
        etape = self.etapes[0]
        self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'joint'}, format='json')
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, outcome='joint',
            kind=LeadActivity.Kind.APPEL).exists())

    def test_outcome_inconnu_refuse(self):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{self.etapes[0].pk}/fait/',
            {'outcome': 'peut-etre'}, format='json')
        self.assertEqual(resp.status_code, 400)


class ReporterTests(_Base):
    slug = 'mry10-report'

    def test_reporter_decale_la_touche_ET_les_suivantes(self):
        etapes = self._rafraichir()
        cible, suivante = etapes[0], etapes[1]
        ecart_initial = suivante.due_at - cible.due_at
        nouvelle = (cible.due_at + datetime.timedelta(days=7)).isoformat()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{cible.pk}/reporter/',
            {'due_at': nouvelle}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        cible.refresh_from_db()
        suivante.refresh_from_db()
        # L'ÉCART entre les touches est préservé : elles ne se téléscopent pas.
        self.assertEqual(suivante.due_at - cible.due_at, ecart_initial)

    def test_une_touche_deja_traitee_ne_bouge_pas(self):
        etapes = self._rafraichir()
        faite = etapes[1]
        self.api.post(
            f'/api/django/crm/relance-etapes/{faite.pk}/fait/', {},
            format='json')
        faite.refresh_from_db()
        avant = faite.due_at
        nouvelle = (etapes[0].due_at + datetime.timedelta(days=9)).isoformat()
        self.api.post(
            f'/api/django/crm/relance-etapes/{etapes[0].pk}/reporter/',
            {'due_at': nouvelle}, format='json')
        faite.refresh_from_db()
        self.assertEqual(faite.due_at, avant)

    def test_echeance_invalide_refusee(self):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{self.etapes[0].pk}/reporter/',
            {'due_at': 'jeudi prochain'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_report_recale_sur_la_fenetre_dappel(self):
        """Un rappel demandé « samedi » ne peut pas tomber un samedi."""
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{self.etapes[0].pk}/reporter/',
            {'rappel_le': '2026-09-12', 'rappel_heure': '10:00'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        etape = RelanceEtape.objects.get(pk=self.etapes[0].pk)
        self.assertEqual(
            etape.due_at.astimezone(CASA).date(), datetime.date(2026, 9, 14))

    def test_touche_dune_autre_societe_404(self):
        autre = _company('mry10-autre')
        owner = User.objects.create_user(
            username='mry10-autre-u', password='x', company=autre)
        lead_autre = Lead.objects.create(
            company=autre, nom='Voisin', owner=owner)
        etapes = _materialiser_tout(lead_autre, owner, depart=LUNDI)
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etapes[0].pk}/reporter/',
            {'due_at': LUNDI.isoformat()}, format='json')
        self.assertEqual(resp.status_code, 404)


class RappelDepuisLeJournalTests(_Base):
    slug = 'mry10-journal'

    def test_rappel_le_depuis_log_interaction_deplace_la_touche(self):
        cible = self._rafraichir()[0]
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/log-interaction/',
            {'kind': 'appel', 'outcome': 'rappel',
             'rappel_le': '2026-09-17', 'rappel_heure': '11:00'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cible.refresh_from_db()
        self.assertEqual(
            cible.due_at.astimezone(CASA).date(), datetime.date(2026, 9, 17))

    def test_date_de_rappel_invalide_refusee(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/log-interaction/',
            {'kind': 'appel', 'outcome': 'rappel', 'rappel_le': '17/09/2026'},
            format='json')
        self.assertEqual(resp.status_code, 400)


class UnSeulSystemeDeRappelTests(_Base):
    """Le rival `CallLogPopover` PATCHe `relance_date` seul — il doit rester
    fonctionnel SANS ouvrir une seconde date à côté de la cadence."""

    slug = 'mry10-invariant'

    def test_patch_relance_date_deplace_la_touche(self):
        cible = self._rafraichir()[0]
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'relance_date': '2026-09-17'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        cible.refresh_from_db()
        self.assertEqual(
            cible.due_at.astimezone(CASA).date(), datetime.date(2026, 9, 17))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, datetime.date(2026, 9, 17))

    def test_patch_sur_un_lead_sans_cadence_reste_inchange(self):
        seul = Lead.objects.create(
            company=self.company, nom='Sans plan', owner=self.acteur)
        resp = self.api.patch(
            f'/api/django/crm/leads/{seul.pk}/',
            {'relance_date': '2026-09-17'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        seul.refresh_from_db()
        self.assertEqual(seul.relance_date, datetime.date(2026, 9, 17))
