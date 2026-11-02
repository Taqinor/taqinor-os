"""CAD107 — un lead perdu qui revient : UN seul comportement, trois chemins.

Le meilleur signal d'achat qui existe — un client perdu qui revient — avait
trois sorties différentes :

  * le PATCH de la fiche ne traitait que le passage `not old.perdu →
    new.perdu` : DÉCOCHER « Perdu » ne déclenchait rien du tout ;
  * le lot `unset_perdu` appelait le filet ;
  * `reactivate_lead_on_new_touch` (nouvelle demande entrante) ne créait
    aucune `RelanceEtape`.

Et dans les trois cas la prise de contact ne pouvait de toute façon pas
repartir (garde « déjà contacté ») : au mieux une étape nue.

Le comportement unique REUTILISE la cadence RÉVEIL — jamais une nouvelle
cadence (CADX), et c'est exactement ce à quoi elle sert : reprendre le
contact d'un dossier mis de côté, sans rejouer six appels en quatorze jours à
quelqu'un qu'on a déjà travaillé. La reprise est VISIBLE : une note de
chatter la dit, et la touche apparaît dans la file (`relance_date`).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import stages, leads_intake
from apps.crm import cadence_touche
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

MOBILE = '+212661000002'
LEADS_URL = '/api/django/crm/leads/'
BULK_URL = '/api/django/crm/leads/bulk/'


class _Base(TestCase):
    slug = 'cad107'

    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD107 Solaire', slug=f'{self.slug}-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        CadenceRelanceEtape.seed_defaults(self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='admin', company=self.company)

    def _lead_perdu(self, prenom='Aziz', **kw):
        champs = {'company': self.company, 'nom': 'Benali', 'prenom': prenom,
                  'ville': 'Bouskoura', 'owner': self.acteur,
                  'telephone': MOBILE, 'stage': stages.CONTACTED,
                  'perdu': True, 'motif_perte': 'Prix'}
        champs.update(kw)
        return Lead.objects.create(**champs)

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        return api

    def _ouvertes(self, lead):
        return lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE)

    def _cadences_ouvertes(self, lead):
        return set(self._ouvertes(lead).values_list('cadence', flat=True))


class LesTroisCheminsProduisentLaMemeRepriseTests(_Base):
    """Le « Done = »."""

    slug = 'cad107-trois'

    def test_chemin_1_le_PATCH_qui_decoche_perdu_pose_la_reprise(self):
        lead = self._lead_perdu()
        resp = self._api().patch(
            f'{LEADS_URL}{lead.pk}/', {'perdu': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._cadences_ouvertes(lead), {'reveil'})

    def test_chemin_2_le_lot_unset_perdu_pose_la_meme(self):
        lead = self._lead_perdu()
        resp = self._api().post(
            BULK_URL, {'ids': [lead.pk], 'action': 'unset_perdu'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._cadences_ouvertes(lead), {'reveil'})

    def test_chemin_3_une_nouvelle_demande_entrante_pose_la_meme(self):
        lead = self._lead_perdu()
        self.assertTrue(leads_intake.reactivate_lead_on_new_touch(lead))
        self.assertEqual(self._cadences_ouvertes(lead), {'reveil'})

    def test_les_trois_chemins_posent_le_MEME_nombre_de_touches(self):
        a = self._lead_perdu('Aziz')
        b = self._lead_perdu('Karim', telephone='+212661000003')
        c = self._lead_perdu('Samir', telephone='+212661000004')
        self._api().patch(f'{LEADS_URL}{a.pk}/', {'perdu': False},
                          format='json')
        self._api().post(BULK_URL, {'ids': [b.pk], 'action': 'unset_perdu'},
                         format='json')
        leads_intake.reactivate_lead_on_new_touch(c)
        comptes = {self._ouvertes(x).count() for x in (a, b, c)}
        self.assertEqual(len(comptes), 1, comptes)
        self.assertNotIn(0, comptes)


class LaRepriseEstVISIBLETests(_Base):
    """« L'écran affiche ce qui vient d'être posé. »

    Le lead de ces deux tests est un dossier DÉJÀ ROUVERT (`perdu=False`) :
    `reprendre_cadence_apres_reouverture` refuse délibérément un lead encore
    perdu — « ce n'est pas une réouverture », no-op vérifié par
    `LesNoOpDeliberesTests.test_un_lead_encore_PERDU_ne_recoit_rien`. Les
    appeler sur un lead `perdu=True` demandait au moteur l'exact contraire de
    ce que le même module exige ailleurs.
    """

    slug = 'cad107-visible'

    def test_une_note_de_chatter_dit_que_le_dossier_est_rouvert(self):
        lead = self._lead_perdu(perdu=False)
        etapes = cadence_touche.reprendre_cadence_apres_reouverture(
            lead, self.acteur, origine='fiche rouverte')
        self.assertTrue(etapes)
        notes = [n.body for n in LeadActivity.objects.filter(lead=lead)]
        self.assertTrue(
            any('cadence de reprise posée' in (b or '') for b in notes),
            notes)

    def test_la_prochaine_touche_remonte_dans_la_file(self):
        lead = self._lead_perdu(perdu=False)
        self.assertTrue(
            cadence_touche.reprendre_cadence_apres_reouverture(lead, self.acteur))
        lead.refresh_from_db()
        self.assertIsNotNone(lead.relance_date)
        prochaine = self._ouvertes(lead).order_by('due_date').first()
        self.assertEqual(lead.relance_date, prochaine.due_date)


class LesNoOpDeliberesTests(_Base):
    """Ce que la reprise ne fait JAMAIS."""

    slug = 'cad107-noop'

    def test_un_lead_DEJA_suivi_ne_recoit_pas_une_seconde_cadence(self):
        """CADX — jamais deux cadences en parallèle."""
        lead = self._lead_perdu(perdu=False)
        deja = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='apres_devis', ordre=1,
            due_date=lead.date_creation.date(),
            canal=RelanceEtape.Canal.WHATSAPP, libelle='Le PDF s’ouvre bien ?')
        self.assertEqual(
            cadence_touche.reprendre_cadence_apres_reouverture(lead, self.acteur),
            [])
        self.assertEqual([e.pk for e in self._ouvertes(lead)], [deja.pk])

    def test_un_lead_encore_PERDU_ne_recoit_rien(self):
        lead = self._lead_perdu()
        self.assertEqual(
            cadence_touche.reprendre_cadence_apres_reouverture(lead, self.acteur),
            [])

    def test_un_lead_quon_ne_relance_plus_ne_recoit_rien(self):
        lead = self._lead_perdu(perdu=False, ne_plus_contacter=True)
        self.assertEqual(
            cadence_touche.reprendre_cadence_apres_reouverture(lead, self.acteur),
            [])

    def test_un_lead_SIGNE_ou_FROID_ne_recoit_rien(self):
        for etape in (stages.SIGNED, stages.COLD):
            with self.subTest(stage=etape):
                lead = self._lead_perdu(perdu=False, stage=etape)
                self.assertEqual(
                    cadence_touche.reprendre_cadence_apres_reouverture(
                        lead, self.acteur), [])

    def test_un_lead_archive_ne_recoit_rien(self):
        lead = self._lead_perdu(perdu=False, is_archived=True)
        self.assertEqual(
            cadence_touche.reprendre_cadence_apres_reouverture(lead, self.acteur),
            [])

    def _lead_froid(self, **kw):
        self.meryem = (
            User.objects.filter(username=f'{self.slug}-meryem').first()
            or User.objects.create_user(
                username=f'{self.slug}-meryem', password='x',
                role_legacy='commercial', company=self.company))
        champs = {'perdu': False, 'motif_perte': None, 'stage': stages.COLD,
                  'owner': self.meryem, 'prenom': 'Yassine', 'nom': 'Ennaji',
                  'telephone': '+212661445566', 'parc_etat': 'nurture',
                  'parc_raison': 'injoignable'}
        champs.update(kw)
        return self._lead_perdu(**champs)

    def _recontact(self, lead, corps=None):
        return self._api().post(
            f'{LEADS_URL}{lead.pk}/recontact/',
            corps or {'canal': 'whatsapp', 'note': 'a répondu au message de juin'},
            format='json')

    def test_un_recontact_client_rouvre_un_lead_au_froid(self):
        """CADV35 — Froid → Contacté, parc effacé, UNE étape d'appel, chatter
        de l'acteur, responsable prévenu."""
        from apps.notifications.models import Notification

        lead = self._lead_froid()
        reponse = self._recontact(lead)
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(
            reponse.json(),
            {'etape': 'appel_apres_reponse', 'stage': stages.CONTACTED})
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertIsNone(lead.parc_etat)
        self.assertIsNone(lead.parc_raison)
        self.assertIsNone(lead.parc_jusqu_au)
        ouverte = self._ouvertes(lead).get()
        self.assertEqual(ouverte.cle, 'appel_apres_reponse')
        self.assertEqual(ouverte.canal, RelanceEtape.Canal.APPEL)
        ligne = LeadActivity.objects.get(
            lead=lead, body__startswith='Le client a recontacté')
        self.assertEqual(ligne.user, self.acteur)
        self.assertIn('a répondu au message de juin', ligne.body)
        self.assertTrue(Notification.objects.filter(
            user=self.meryem, title__contains='le client a recontacté').exists())

    def test_le_recontact_remplace_les_reveils_encore_ouverts(self):
        """Sans cet arrêt, le filet (no-op dès qu'une touche est ouverte) ne
        poserait aucune étape d'appel."""
        lead = self._lead_froid()
        reveil = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='reveil', ordre=1,
            due_date=lead.date_creation.date(),
            canal=RelanceEtape.Canal.APPEL, libelle='Appel de réveil')
        self.assertEqual(self._recontact(lead).status_code, 200)
        reveil.refresh_from_db()
        self.assertEqual(reveil.statut, RelanceEtape.Statut.ANNULEE)
        self.assertEqual(
            self._ouvertes(lead).get().cle, 'appel_apres_reponse')

    def test_le_recontact_refuse_perdu_archive_oppose_signe_et_hors_froid(self):
        """Un ÉTAT de la fiche : 409 (ENF11), et rien n'est écrit."""
        for nom, champs in (('perdu', {'perdu': True, 'motif_perte': 'Prix'}),
                            ('archive', {'is_archived': True}),
                            ('oppose', {'ne_plus_contacter': True}),
                            ('signe', {'stage': stages.SIGNED}),
                            ('vivant', {'stage': stages.CONTACTED})):
            with self.subTest(nom):
                lead = self._lead_froid(**champs)
                avant = lead.stage
                self.assertEqual(self._recontact(lead).status_code, 409)
                lead.refresh_from_db()
                self.assertEqual(lead.stage, avant)
                self.assertEqual(lead.parc_raison, 'injoignable')
                self.assertFalse(self._ouvertes(lead).exists())

    def test_le_recontact_refuse_un_canal_inconnu(self):
        lead = self._lead_froid()
        for canal in ('formulaire_meta', 'pigeon', ''):
            with self.subTest(canal):
                self.assertEqual(
                    self._recontact(lead, {'canal': canal}).status_code, 400)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.COLD)

    def test_la_cadence_posee_est_bien_le_REVEIL_jamais_une_neuve(self):
        """Garde-fou CADX : aucune cadence n'est inventée pour l'occasion."""
        lead = self._lead_perdu(perdu=False)
        etapes = cadence_touche.reprendre_cadence_apres_reouverture(
            lead, self.acteur)
        self.assertTrue(etapes)
        self.assertEqual({e.cadence for e in etapes}, {'reveil'})
