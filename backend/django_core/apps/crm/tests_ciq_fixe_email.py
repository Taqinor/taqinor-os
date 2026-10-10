"""CIQ505 — convention 8 : un numéro fixe reçoit un E-MAIL quand une adresse
existe, sinon un APPEL qui GARDE son texte comme fil de conversation.

Avant : ``adapter_canal_au_numero`` changeait en APPEL toute touche WhatsApp
d'un fixe et lui retirait sa clé — un standard ou une réception ne recevait
plus aucun texte (J1 PDF, J4 preuve, J6 garanties, J9 validité, J13, J14), et
``Lead.email`` n'était jamais lu. Règle de DONNÉE, aucun axe segment : les
mêmes jours, les mêmes libellés, le même nombre de touches (CAD52/CAD124).

Le temps est GELÉ.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import cadence_temps, horaires, services
from apps.crm import cadence_messages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.serializers import RelanceEtapeSerializer
from apps.crm.services import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile

User = get_user_model()

DEPART = datetime.datetime(2026, 9, 8, 11, 0, tzinfo=horaires.CASABLANCA)
GEL = datetime.datetime(2026, 9, 7, 7, 0, tzinfo=horaires.CASABLANCA)

FIXE = '+212522334455'
FIXE_BIS = '+212522998877'
MOBILE = '+212661000002'
EMAIL = 'standard@hotel-atlas.ma'


class _Base(TestCase):
    slug = 'ciq505'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        # Une société qui a une réalisation éligible : la touche J4 « preuve »
        # existe au suivi après devis (AGR514).
        patcher = mock.patch.object(
            services, '_realisation_eligible', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.company = Company.objects.create(
            nom='CIQ505 Solaire', slug=f'{self.slug}-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, prenom='Aziz', telephone='', whatsapp='', email='',
              **kw):
        return Lead.objects.create(
            company=self.company, nom='Benali', prenom=prenom,
            ville='Bouskoura', owner=self.acteur, email=email,
            telephone=telephone, whatsapp=whatsapp, **kw)

    def _plan(self, lead, cadence='apres_devis'):
        return calculer_echeances_cadence(lead, cadence, DEPART)

    def _par_ordre(self, lead, cadence='apres_devis'):
        return {g.ordre: (g, e.astimezone(horaires.CASABLANCA))
                for g, e in self._plan(lead, cadence)}


class FixeAvecEmailTests(_Base):
    """(a) Chaque touche WhatsApp du suivi après devis naît e-mail, avec sa
    clé ; les appels restent des appels ; les dates sont celles du mobile."""

    slug = 'ciq505-email'

    def test_chaque_touche_whatsapp_devient_email_avec_sa_cle(self):
        mobile = self._par_ordre(self._lead('Karim', telephone=MOBILE))
        fixe = self._par_ordre(
            self._lead('Aziz', telephone=FIXE, email=EMAIL))
        convertis = [o for o, (g, _q) in mobile.items()
                     if g.canal == 'whatsapp']
        self.assertTrue(convertis)
        for ordre in convertis:
            gabarit = fixe[ordre][0]
            self.assertEqual(gabarit.canal, cadence_temps.CANAL_EMAIL, ordre)
            self.assertEqual(gabarit.template_cle,
                             mobile[ordre][0].template_cle, ordre)
            self.assertTrue(gabarit.template_cle, ordre)

    def test_les_appels_restent_des_appels(self):
        mobile = self._par_ordre(self._lead('Karim', telephone=MOBILE))
        fixe = self._par_ordre(
            self._lead('Aziz', telephone=FIXE, email=EMAIL))
        appels = [o for o, (g, _q) in mobile.items() if g.canal == 'appel']
        self.assertTrue(appels)
        for ordre in appels:
            self.assertEqual(fixe[ordre][0].canal, 'appel', ordre)
            self.assertEqual(fixe[ordre][0].template_cle,
                             mobile[ordre][0].template_cle, ordre)

    def test_les_dates_et_les_libelles_sont_ceux_dun_lead_sur_mobile(self):
        mobile = self._par_ordre(self._lead('Karim', telephone=MOBILE))
        fixe = self._par_ordre(
            self._lead('Aziz', telephone=FIXE, email=EMAIL))
        self.assertEqual(sorted(fixe), sorted(mobile))
        for ordre, (gabarit, quand) in mobile.items():
            self.assertEqual(fixe[ordre][1].date(), quand.date(), ordre)
            self.assertEqual(fixe[ordre][0].libelle, gabarit.libelle, ordre)

    def test_le_gabarit_de_la_societe_nest_jamais_mute(self):
        self._plan(self._lead('Aziz', telephone=FIXE, email=EMAIL))
        temoin = self._par_ordre(self._lead('Karim', telephone=MOBILE))
        self.assertIn('whatsapp', {g.canal for g, _q in temoin.values()})


class FixeSansEmailTests(_Base):
    """(b) Sans e-mail ⇒ appels qui gardent leur clé."""

    slug = 'ciq505-sans'

    def test_appels_qui_gardent_leur_cle(self):
        mobile = self._par_ordre(self._lead('Karim', telephone=MOBILE))
        fixe = self._par_ordre(self._lead('Aziz', telephone=FIXE))
        convertis = [o for o, (g, _q) in mobile.items()
                     if g.canal == 'whatsapp']
        self.assertTrue(convertis)
        for ordre in convertis:
            gabarit = fixe[ordre][0]
            self.assertEqual(gabarit.canal, cadence_temps.CANAL_APPEL, ordre)
            self.assertEqual(gabarit.template_cle,
                             mobile[ordre][0].template_cle, ordre)

    def test_la_cadence_de_contact_garde_aussi_ses_cles(self):
        mobile = self._par_ordre(
            self._lead('Karim', telephone=MOBILE), 'contact')
        fixe = self._par_ordre(
            self._lead('Aziz', telephone=FIXE, email=EMAIL), 'contact')
        for ordre, (g_mobile, _q) in mobile.items():
            if g_mobile.canal != 'whatsapp':
                continue
            gabarit = fixe[ordre][0]
            # Aucune forme e-mail pour les touches de la cadence contact :
            # elles deviennent des appels, avec leur texte.
            self.assertEqual(gabarit.canal, cadence_temps.CANAL_APPEL, ordre)
            self.assertEqual(gabarit.template_cle, g_mobile.template_cle,
                             ordre)


class WhatsappDeclareTests(_Base):
    """(c) Un numéro saisi dans ``whatsapp`` DIFFÉRENT du téléphone vaut
    déclaration ; une simple copie du téléphone ne la vaut pas."""

    slug = 'ciq505-declare'

    def test_un_whatsapp_fixe_distinct_du_telephone_reste_whatsapp(self):
        lead = self._lead(telephone=MOBILE, whatsapp=FIXE, email=EMAIL)
        self.assertTrue(cadence_temps.whatsapp_declare(lead))
        canaux = {g.canal for g, _q in self._plan(lead)}
        self.assertIn('whatsapp', canaux)
        self.assertNotIn('email', canaux)

    def test_un_fixe_en_telephone_ET_en_whatsapp_reste_converti(self):
        lead = self._lead(telephone=FIXE, whatsapp=FIXE, email=EMAIL)
        self.assertFalse(cadence_temps.whatsapp_declare(lead))
        canaux = {g.canal for g, _q in self._plan(lead)}
        self.assertNotIn('whatsapp', canaux)
        self.assertIn('email', canaux)

    def test_une_copie_en_autre_graphie_nest_pas_une_declaration(self):
        lead = self._lead(telephone='0522334455', whatsapp='+212 5 22 33 44 55')
        self.assertFalse(cadence_temps.whatsapp_declare(lead))

    def test_un_whatsapp_fixe_distinct_nest_pas_improbable(self):
        lead = self._lead(telephone=FIXE, whatsapp=FIXE_BIS)
        improbable, _motif = cadence_temps.whatsapp_improbable(lead)
        self.assertFalse(improbable)


class CanalAdapteTests(_Base):
    """(d) ``canal_adapte`` donne la cause, par la MÊME fonction pure."""

    slug = 'ciq505-cause'

    def _touche(self, lead, ordre, canal, cle):
        # Le plan seme le protocole de la societe (lu par le serialiseur).
        self._plan(lead)
        due = DEPART + datetime.timedelta(days=ordre)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='apres_devis',
            ordre=ordre, due_at=due, due_date=due.date(), canal=canal,
            libelle='Le PDF s\'ouvre bien ?', template_cle=cle)

    def test_cause_email(self):
        lead = self._lead(telephone=FIXE, email=EMAIL)
        donnees = RelanceEtapeSerializer(
            self._touche(lead, 1, 'email', 'j1_pdf')).data
        self.assertEqual(donnees['canal_adapte'],
                         cadence_temps.CAUSE_FIXE_EMAIL)

    def test_cause_appel_sans_email(self):
        lead = self._lead(telephone=FIXE)
        donnees = RelanceEtapeSerializer(
            self._touche(lead, 1, 'appel', 'j1_pdf')).data
        self.assertEqual(donnees['canal_adapte'],
                         cadence_temps.CAUSE_FIXE_APPEL)

    def test_un_appel_du_protocole_nest_pas_une_conversion(self):
        lead = self._lead(telephone=FIXE, email=EMAIL)
        donnees = RelanceEtapeSerializer(
            self._touche(lead, 2, 'appel', 'appel_suivi_j2')).data
        self.assertEqual(donnees['canal_adapte'], '')

    def test_un_lead_sur_mobile_ne_porte_rien(self):
        lead = self._lead(telephone=MOBILE, email=EMAIL)
        donnees = RelanceEtapeSerializer(
            self._touche(lead, 1, 'whatsapp', 'j1_pdf')).data
        self.assertEqual(donnees['canal_adapte'], '')

    def test_whatsapp_only_garde_sa_phrase(self):
        lead = self._lead(
            telephone=FIXE, email=EMAIL,
            contact_preference=Lead.ContactPreference.WHATSAPP_ONLY)
        donnees = RelanceEtapeSerializer(
            self._touche(lead, 1, 'whatsapp', 'j1_pdf')).data
        self.assertIn('préférence du client', donnees['canal_adapte'])

    def test_les_causes_du_contrat_sont_celles_du_moteur(self):
        import json
        from pathlib import Path
        contrat = json.loads(
            (Path(__file__).parent / 'contract_samples'
             / 'relance_etape_v2.json').read_text(encoding='utf-8'))
        causes = {cadence_temps.CAUSE_FIXE_EMAIL,
                  cadence_temps.CAUSE_FIXE_APPEL}
        self.assertTrue(causes <= set(
            json.dumps(contrat, ensure_ascii=False).split('"')))


class DarijaTests(_Base):
    """(e) Lead darija sur fixe avec e-mail ⇒ appels avec clé : la forme
    e-mail n'existe qu'en français."""

    slug = 'ciq505-darija'

    def test_darija_sur_fixe_avec_email_donne_des_appels_avec_cle(self):
        mobile = self._par_ordre(self._lead('Karim', telephone=MOBILE))
        lead = self._lead(
            'Aziz', telephone=FIXE, email=EMAIL,
            langue_preferee=Lead.LanguePreferee.DARIJA)
        fixe = self._par_ordre(lead)
        for ordre, (g_mobile, _q) in mobile.items():
            if g_mobile.canal != 'whatsapp':
                continue
            gabarit = fixe[ordre][0]
            self.assertEqual(gabarit.canal, cadence_temps.CANAL_APPEL, ordre)
            self.assertEqual(gabarit.template_cle, g_mobile.template_cle,
                             ordre)


class PreferenceEtAbsenceTests(_Base):
    slug = 'ciq505-garde'

    def test_whatsapp_only_gagne_toujours(self):
        lead = self._lead(
            telephone=FIXE, email=EMAIL,
            contact_preference=Lead.ContactPreference.WHATSAPP_ONLY)
        for gabarit, _q in self._plan(lead):
            self.assertTrue(horaires.est_un_message(gabarit.canal))
            self.assertNotEqual(gabarit.canal, cadence_temps.CANAL_EMAIL)

    def test_aucun_numero_aucune_conversion(self):
        lead = self._lead(telephone='', whatsapp='', email=EMAIL)
        self.assertIsNone(cadence_temps.conversion_numero(lead, 'j1_pdf'))


# ── CIQ506 — rendu e-mail d'une touche : objet et lien mailto ─────────────

class RenduEmailTests(_Base):
    """Une touche de canal ``email`` rend sa FORME e-mail ; ``objet`` et
    ``mailto_url`` sont construits par le serveur ; ``wa_url`` vaut null."""

    slug = 'ciq506'

    def setUp(self):
        super().setUp()
        from apps.crm.models import Client
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='c506@example.com')
        self._n_devis = 0

    def _devis(self, date_validite=datetime.date(2026, 10, 15)):
        from decimal import Decimal

        from apps.ventes.models import Devis
        # Référence unique par appel (contrainte company+reference) : le
        # premier devis d'un test reste DEV-CIQ506-0001.
        self._n_devis += 1
        return Devis.objects.create(
            company=self.company,
            reference=f'DEV-CIQ506-{self._n_devis:04d}',
            client=self.client_obj, statut='envoye',
            taux_tva=Decimal('20.00'), date_envoi=DEPART,
            date_validite=date_validite)

    def _etape(self, lead, canal, cle='j9_validite', devis=None):
        due = DEPART + datetime.timedelta(days=9)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='apres_devis', ordre=7,
            due_at=due, due_date=due.date(), canal=canal,
            libelle='Validité de la proposition', template_cle=cle,
            devis=devis)

    def test_a_objet_et_corps_de_la_forme_email_et_mailto_decodable(self):
        from urllib.parse import parse_qs, unquote, urlsplit

        from apps.parametres.models_messages import forme_email
        lead = self._lead(telephone=FIXE, email=EMAIL)
        rendu = cadence_messages.message_pour_etape(
            self._etape(lead, 'email', devis=self._devis()),
            user=self.acteur)
        forme = forme_email('j9_validite')
        self.assertTrue(rendu['objet'].startswith('Validité de votre proposition'))
        self.assertIn('DEV-CIQ506-0001', rendu['objet'])
        # {date_validite} = la date du PDF (garde CAD59).
        self.assertIn('15/10/2026', rendu['message'])
        self.assertIn("Elle est valable jusqu'au", rendu['message'])
        self.assertIn(forme['corps'].split('{')[0].strip()[:8],
                      rendu['message'])
        self.assertIsNone(rendu['wa_url'])
        self.assertFalse(rendu['vocal'])
        url = urlsplit(rendu['mailto_url'])
        self.assertEqual(url.scheme, 'mailto')
        self.assertEqual(unquote(url.path), EMAIL)
        params = parse_qs(url.query, keep_blank_values=True)
        self.assertEqual(params['subject'], [rendu['objet']])
        self.assertEqual(params['body'],
                         [rendu['message'].replace('\n', '\r\n')])
        self.assertEqual(rendu['placeholders_manquants'], [])

    def test_b_role_sans_pii_ou_sans_adresse_mailto_null(self):
        from apps.roles.models import Role
        lead = self._lead(telephone=FIXE, email=EMAIL)
        etape = self._etape(lead, 'email', devis=self._devis())
        role = Role.objects.create(
            company=self.company, nom='CIQ506 sans PII',
            permissions=['crm_voir'])
        sans_pii = User.objects.create_user(
            username='ciq506-sanspii', password='x', role=role,
            company=self.company)
        rendu = cadence_messages.message_pour_etape(etape, user=sans_pii)
        self.assertIsNone(rendu['mailto_url'])
        rendu_ok = cadence_messages.message_pour_etape(etape, user=self.acteur)
        self.assertIsNotNone(rendu_ok['mailto_url'])
        sans_adresse = self._lead('Karim', telephone=FIXE, email='')
        rendu_vide = cadence_messages.message_pour_etape(
            self._etape(sans_adresse, 'email', devis=self._devis()),
            user=self.acteur)
        self.assertIsNone(rendu_vide['mailto_url'])
        # Le texte reste rendu : seule l'adresse manque.
        self.assertTrue(rendu_vide['message'])

    def test_c_une_touche_whatsapp_garde_sa_reponse_actuelle(self):
        lead = self._lead(telephone=MOBILE, email=EMAIL)
        rendu = cadence_messages.message_pour_etape(
            self._etape(lead, 'whatsapp', devis=self._devis()),
            user=self.acteur)
        self.assertEqual(rendu['objet'], '')
        self.assertIsNone(rendu['mailto_url'])
        self.assertTrue(rendu['wa_url'].startswith('https://wa.me/'))

    def test_une_cle_sans_forme_email_rend_le_texte_de_la_cle_sans_objet(self):
        lead = self._lead(telephone=FIXE, email=EMAIL)
        rendu = cadence_messages.message_pour_etape(
            self._etape(lead, 'email', cle='relance_email_j10'),
            user=self.acteur)
        self.assertEqual(rendu['objet'], '')
        self.assertIsNone(rendu['wa_url'])
        self.assertTrue(rendu['mailto_url'].startswith('mailto:'))
        self.assertNotIn('subject=', rendu['mailto_url'])

    def test_un_objet_dont_le_placeholder_manque_est_omis(self):
        lead = self._lead(telephone=FIXE, email=EMAIL)
        # Touche sans devis : `{reference}` n'a pas de valeur réelle.
        rendu = cadence_messages.message_pour_etape(
            self._etape(lead, 'email', cle='j6_garanties'),
            user=self.acteur)
        self.assertEqual(rendu['objet'], '')
        self.assertIn('reference', rendu['placeholders_manquants'])
