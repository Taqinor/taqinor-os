"""CIQ427 — panneau d'appel PRO : le numéro direct de celui qui décide quand la
fiche n'a qu'un fixe (étape 5), et le mode de financement posé au RAPPEL.

Aucune sixième étape (budget CAD175 inchangé) : ``whatsapp`` et
``contact_secondaire_*`` sont servis EN COMPLÉMENT de ``decideur`` ; la
cadence ne lit que le numéro (règle (c) de CIQ505), jamais le second contact
(CAD144). ``financing_intent`` est servi en dernier — l'écran ne le pose
qu'au rappel — sans jamais dire « crédit-bail » (D-CIQ-15).
"""
import datetime
import json
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import cadence_temps, horaires
from apps.crm import panneau_appel as panneau
from apps.crm.models import Lead
from apps.crm.services import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'panneau_appel.json').read_text(encoding='utf-8'))

FIXE = '+212522334455'
MOBILE = '+212661000002'
FRAGMENTS_ECONOMIE = ('econom', 'payback', 'retour', 'gain')


def _champs(lead):
    return [q['champ'] for q in panneau.questions_a_poser(lead)]


def _pro(segment='commercial', **kw):
    return Lead(nom='P', type_installation=segment, **kw)


def _panneau(lead, exemple):
    with mock.patch.object(panneau, '_touche_en_cours', return_value=None), \
            mock.patch.object(panneau, '_couches_composables',
                              return_value=set()), \
            mock.patch.object(panneau, 'fenetre_du_jour_servie',
                              return_value=exemple['fenetre_du_jour']), \
            mock.patch.object(panneau, 'profil_suppose_servi',
                              return_value=exemple['profil_suppose']):
        return panneau.panneau_appel(lead)


class MobileDirectSurFixeTests(SimpleTestCase):
    def test_fixe_decideur_vide_sert_whatsapp_apres_decideur(self):
        champs = _champs(_pro(telephone=FIXE))
        self.assertIn('whatsapp', champs)
        self.assertEqual(champs.index('whatsapp'),
                         champs.index('decideur') + 1)
        self.assertNotIn('contact_secondaire_nom', champs)

    def test_decideur_seul_sert_whatsapp_seul(self):
        champs = _champs(_pro(telephone=FIXE, decideur='seul'))
        self.assertIn('whatsapp', champs)
        self.assertNotIn('decideur', champs)
        self.assertNotIn('contact_secondaire_nom', champs)

    def test_le_meme_lead_sur_mobile_ne_recoit_pas_whatsapp(self):
        champs = _champs(_pro(telephone=MOBILE))
        self.assertNotIn('whatsapp', champs)
        self.assertNotIn('contact_secondaire_nom', champs)

    def test_un_whatsapp_declare_distinct_n_est_plus_reposé(self):
        lead = _pro(telephone=FIXE, whatsapp=MOBILE)
        self.assertNotIn('whatsapp', _champs(lead))

    def test_un_whatsapp_copie_du_fixe_reste_une_question(self):
        lead = _pro(telephone=FIXE, whatsapp=FIXE)
        self.assertIn('whatsapp', _champs(lead))
        self.assertNotIn('whatsapp', panneau.prefill_du_panneau(lead))

    def test_sans_aucun_numero_rien_n_est_servi(self):
        self.assertNotIn('whatsapp', _champs(_pro()))

    def test_industriel_sur_fixe_aussi(self):
        champs = _champs(_pro('industriel', telephone=FIXE))
        self.assertIn('whatsapp', champs)

    def test_la_question_est_celle_du_fondateur(self):
        question = next(q for q in panneau.questions_a_poser(
            _pro(telephone=FIXE)) if q['champ'] == 'whatsapp')
        self.assertEqual(
            question['question'],
            "Question à l'appel : « Sur quel mobile ou WhatsApp puis-je "
            "vous joindre directement ? »")
        self.assertEqual(question['nature'], 'texte')

    def test_un_lead_residentiel_ou_agricole_n_est_pas_touche(self):
        for segment in ('residentiel', 'agricole'):
            champs = _champs(Lead(nom='P', type_installation=segment,
                                  telephone=FIXE))
            for colonne in ('whatsapp', 'contact_secondaire_nom',
                            'financing_intent'):
                self.assertNotIn(colonne, champs, (segment, colonne))


class ContactSecondaireTests(SimpleTestCase):
    def test_associe_direction_sert_le_contact_secondaire_pas_whatsapp(self):
        for decideur in ('associe_direction', 'proprietaire_tiers'):
            champs = _champs(_pro(telephone=FIXE, decideur=decideur))
            self.assertIn('contact_secondaire_nom', champs, decideur)
            self.assertIn('contact_secondaire_telephone', champs, decideur)
            self.assertNotIn('whatsapp', champs, decideur)
            self.assertEqual(
                champs.index('contact_secondaire_telephone'),
                champs.index('contact_secondaire_nom') + 1)

    def test_un_contact_deja_connu_n_est_pas_redemande(self):
        lead = _pro(telephone=FIXE, decideur='associe_direction',
                    contact_secondaire_nom='M. Alami',
                    contact_secondaire_telephone='0661000099')
        champs = _champs(lead)
        self.assertNotIn('contact_secondaire_nom', champs)
        self.assertNotIn('contact_secondaire_telephone', champs)
        prefill = panneau.prefill_du_panneau(lead)
        self.assertEqual(prefill['contact_secondaire_nom'], 'M. Alami')

    def test_sur_mobile_aucun_contact_secondaire(self):
        champs = _champs(_pro(telephone=MOBILE,
                              decideur='associe_direction'))
        self.assertNotIn('contact_secondaire_nom', champs)

    def test_la_cadence_ne_lit_jamais_le_second_contact(self):
        lead = _pro(telephone='', contact_secondaire_telephone=MOBILE)
        self.assertEqual(cadence_temps.numero_joignable(lead), '')


class FinancementTests(SimpleTestCase):
    def test_le_financement_vient_apres_les_cinq_etapes(self):
        champs = _champs(_pro('industriel', telephone=MOBILE))
        self.assertIn('financing_intent', champs)
        for colonne in ('conso_mensuelle_kwh', 'compteur_puissance_kva',
                        'type_surface', 'decideur'):
            self.assertLess(champs.index(colonne),
                            champs.index('financing_intent'), colonne)

    def test_jamais_credit_bail_dans_les_questions_servies(self):
        for segment in ('commercial', 'industriel'):
            for q in panneau.questions_a_poser(_pro(segment)):
                texte = json.dumps(q, ensure_ascii=False).lower()
                self.assertNotIn('crédit-bail', texte, q['champ'])
                self.assertNotIn('credit_bail', texte, q['champ'])

    def test_les_trois_choix_publics_seulement(self):
        question = next(q for q in panneau.questions_a_poser(_pro())
                        if q['champ'] == 'financing_intent')
        self.assertEqual([c['valeur'] for c in question['choix']],
                         ['cash', 'credit', 'indecis'])
        self.assertEqual(question['nature'], 'choix')
        self.assertEqual(
            question['question'],
            "Question à l'appel : « Vous pensez régler comment : comptant, "
            "par un crédit, ou ce n'est pas encore décidé ? »")

    def test_un_financement_connu_n_est_pas_redemande(self):
        lead = _pro(financing_intent='cash')
        self.assertNotIn('financing_intent', _champs(lead))
        self.assertEqual(panneau.prefill_du_panneau(lead)['financing_intent'],
                         'cash')

    def test_aucune_cle_d_economie(self):
        data = _panneau(_pro(telephone=FIXE),
                        CONTRAT['exemple_commercial'])
        for cle in _cles(data):
            for fragment in FRAGMENTS_ECONOMIE:
                self.assertNotIn(fragment, cle.lower(), cle)


def _cles(objet):
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            yield cle
            yield from _cles(valeur)
    elif isinstance(objet, list):
        for valeur in objet:
            yield from _cles(valeur)


class ContratTests(SimpleTestCase):
    def test_les_exemples_du_contrat_egalent_la_sortie_reelle(self):
        cas = {
            'exemple_industriel_fixe': ('industriel', {'telephone': FIXE}),
            'exemple_commercial_associe': (
                'commercial', {'telephone': FIXE,
                               'decideur': 'associe_direction'}),
            'exemple_commercial': ('commercial', {}),
            'exemple_industriel': ('industriel', {}),
        }
        for nom, (segment, extra) in cas.items():
            exemple = CONTRAT[nom]
            with self.subTest(exemple=nom):
                lead = Lead(pk=exemple['lead_id'], nom='P',
                            type_installation=segment,
                            **{**exemple['prefill'], **extra})
                self.assertEqual(_panneau(lead, exemple), exemple)

    def test_le_contrat_fixe_porte_whatsapp_apres_decideur(self):
        champs = [q['champ']
                  for q in CONTRAT['exemple_industriel_fixe']['champs_a_poser']]
        self.assertEqual(champs.index('whatsapp'),
                         champs.index('decideur') + 1)
        champs = [q['champ'] for q in
                  CONTRAT['exemple_commercial_associe']['champs_a_poser']]
        self.assertIn('contact_secondaire_nom', champs)
        self.assertNotIn('whatsapp', champs)


class WhatsappDeclareReplanificationTests(TestCase):
    """PATCH d'un ``whatsapp`` mobile distinct du téléphone, puis
    replanification : les touches WhatsApp restent WhatsApp (CIQ505 (c))."""

    def setUp(self):
        gel = frozen(datetime.datetime(
            2026, 9, 7, 7, 0, tzinfo=horaires.CASABLANCA))
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CIQ427 Solaire', slug='ciq427-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.user = User.objects.create_user(
            username='ciq427-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_patch_whatsapp_mobile_puis_replanification(self):
        lead = Lead.objects.create(
            company=self.company, nom='Standard', owner=self.user,
            telephone=FIXE, type_installation='commercial',
            email='standard@hotel.ma')
        depart = datetime.datetime(
            2026, 9, 8, 11, 0, tzinfo=horaires.CASABLANCA)
        avant = {g.canal for g, _e in calculer_echeances_cadence(
            lead, 'contact', depart)}
        self.assertNotIn('whatsapp', avant)
        reponse = self.api.patch(
            f'/api/django/crm/leads/{lead.pk}/',
            {'whatsapp': MOBILE}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        lead.refresh_from_db()
        apres = {g.canal for g, _e in calculer_echeances_cadence(
            lead, 'contact', depart)}
        self.assertIn('whatsapp', apres)
        # Le panneau ne repose plus la question : c'est une déclaration.
        self.assertNotIn('whatsapp', _champs(lead))
