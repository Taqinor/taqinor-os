"""CAD34 — un lead arrivé par téléphone, sans WhatsApp, a enfin une cadence.

La touche 1 du protocole est un WhatsApp. Sur un lead dont le numéro ne
portera jamais WhatsApp, la garde disait « aucun numéro exploitable —
cadence à lancer à la main » et rien ne proposait une composition « appel
d'abord ». Le lead sortait du protocole en silence.

Symétrique EXACT de CAD32 : les barreaux de canal WhatsApp naissent en canal
APPEL — sans gabarit de message, comme les autres appels —, le nombre de
touches et les jours restant identiques.

Round 2, les deux points rouverts :

  * un numéro FIXE marocain PASSE toutes les gardes : `_MA_LOCAL_RE`
    (`apps/ventes/utils/phone.py`) accepte le 5 comme le 6 et le 7 — « fixe
    (5) ou mobile (6, 7) ». La cadence démarrait donc par un WhatsApp qui
    n'arrivera jamais. On ne BLOQUE pas wa.me (WhatsApp Business accepte un
    fixe) : on démarre par un appel, et le motif le dit ;
  * `lead.whatsapp or lead.telephone` ne se repliait sur le téléphone que si
    le champ WhatsApp était VIDE, jamais s'il était INUTILISABLE — une fiche
    au champ WhatsApp bancal et au téléphone bon perdait sa cadence.

GARDE-FOU : aucun numéro DU TOUT ⇒ on ne convertit rien. Rien n'est
joignable, ni message ni appel ; la garde refuse la cadence et NOMME les
champs à remplir (règle fondateur du 08/09/2026). Convertir des touches ne
rendrait pas la fiche plus joignable.

Le temps est GELÉ.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import cadence_temps, horaires, services
from apps.crm.models import Lead
from apps.crm.services import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile

User = get_user_model()

DEPART = datetime.datetime(2026, 9, 8, 11, 0, tzinfo=horaires.CASABLANCA)
GEL = datetime.datetime(2026, 9, 7, 7, 0, tzinfo=horaires.CASABLANCA)

#: Un FIXE de Casablanca : `05 22 …` — accepté par toutes les gardes, mais
#: WhatsApp n'y arrivera pas chez un particulier.
FIXE = '+212522334455'
#: Un mobile ordinaire.
MOBILE = '+212661000002'


class _Base(TestCase):
    slug = 'cad34'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD34 Solaire', slug=f'{self.slug}-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, prenom='Aziz', telephone='', whatsapp='', **kw):
        return Lead.objects.create(
            company=self.company, nom='Benali', prenom=prenom,
            ville='Bouskoura', owner=self.acteur,
            telephone=telephone, whatsapp=whatsapp, **kw)

    def _plan(self, lead, cadence='contact'):
        return calculer_echeances_cadence(lead, cadence, DEPART)

    def _canaux(self, lead, cadence='contact'):
        return [(g.ordre, g.canal) for g, _e in self._plan(lead, cadence)]


class UnFixeDemarreParUnAppelTests(_Base):
    """Le « Done = » : cadence démarrée, 0 barreau WhatsApp, même nombre de
    touches."""

    slug = 'cad34-fixe'

    def test_aucun_barreau_WhatsApp_sur_un_fixe(self):
        lead = self._lead(telephone=FIXE)
        for gabarit, _echeance in self._plan(lead):
            self.assertEqual(gabarit.canal, cadence_temps.CANAL_APPEL,
                             (gabarit.ordre, gabarit.libelle))

    def test_le_nombre_de_touches_est_identique(self):
        fixe = self._lead('Aziz', telephone=FIXE)
        mobile = self._lead('Karim', telephone=MOBILE)
        self.assertEqual(len(self._plan(fixe)), len(self._plan(mobile)))

    def test_les_JOURS_et_les_libelles_sont_identiques(self):
        fixe = {g.ordre: (g, e.astimezone(horaires.CASABLANCA))
                for g, e in self._plan(self._lead('Aziz', telephone=FIXE))}
        mobile = {g.ordre: (g, e.astimezone(horaires.CASABLANCA))
                  for g, e in self._plan(
                      self._lead('Karim', telephone=MOBILE))}
        self.assertEqual(sorted(fixe), sorted(mobile))
        for ordre, (gabarit, quand) in mobile.items():
            self.assertEqual(fixe[ordre][1].date(), quand.date(), ordre)
            self.assertEqual(fixe[ordre][0].libelle, gabarit.libelle, ordre)

    def test_un_barreau_converti_nemporte_aucun_texte(self):
        """Un appel n'a pas de message à envoyer — comme les barreaux
        d'appel qui n'ont déjà aucun gabarit."""
        mobile = {g.ordre: g for g, _e in self._plan(
            self._lead('Karim', telephone=MOBILE))}
        fixe = {g.ordre: g for g, _e in self._plan(
            self._lead('Aziz', telephone=FIXE))}
        convertis = [o for o, g in mobile.items() if g.canal == 'whatsapp']
        self.assertTrue(convertis)
        for ordre in convertis:
            self.assertEqual(fixe[ordre].template_cle, '', ordre)

    def test_le_motif_dit_que_le_WhatsApp_est_improbable(self):
        lead = self._lead(telephone=FIXE)
        improbable, motif = cadence_temps.whatsapp_improbable(lead)
        self.assertTrue(improbable)
        self.assertIn('fixe', motif)

    def test_la_cadence_DEMARRE_bien_sur_un_fixe(self):
        """On ne bloque pas wa.me : la garde laisse passer, et le plan est
        celui du protocole, en appels."""
        lead = self._lead(telephone=FIXE, stage=services.stages.NEW)
        self.assertIsNone(services._garde_cadence_contact(lead))

    def test_un_mobile_garde_ses_WhatsApp(self):
        """Garde négative : rien ne change pour le cas ordinaire."""
        lead = self._lead(telephone=MOBILE)
        canaux = {canal for _o, canal in self._canaux(lead)}
        self.assertIn('whatsapp', canaux)


class LeRepliSurLeTelephoneTests(_Base):
    """Round 2 (b) : un champ WhatsApp inutilisable ne tue plus la fiche."""

    slug = 'cad34-repli'

    def test_un_champ_whatsapp_bancal_se_replie_sur_le_telephone(self):
        lead = self._lead(telephone=MOBILE, whatsapp='n/a')
        self.assertTrue(cadence_temps.numero_joignable(lead))
        self.assertIsNone(services._garde_cadence_contact(lead))

    def test_le_plan_reste_celui_du_protocole_dans_ce_cas(self):
        lead = self._lead(telephone=MOBILE, whatsapp='n/a')
        canaux = {canal for _o, canal in self._canaux(lead)}
        self.assertIn('whatsapp', canaux)

    def test_un_whatsapp_valide_reste_prioritaire(self):
        lead = self._lead(telephone=FIXE, whatsapp=MOBILE)
        self.assertEqual(cadence_temps.numero_joignable(lead), MOBILE)
        canaux = {canal for _o, canal in self._canaux(lead)}
        self.assertIn('whatsapp', canaux)


class SansAucunNumeroTests(_Base):
    """Le garde-fou : rien n'est joignable, on ne convertit rien."""

    slug = 'cad34-aucun'

    def test_la_garde_refuse_toujours_et_NOMME_les_champs(self):
        lead = self._lead(telephone='', whatsapp='')
        code, motif = services._garde_cadence_contact(lead)
        self.assertEqual(code, 'sans_numero')
        self.assertIn('aucun numéro exploitable', motif)
        self.assertIn('Téléphone', motif)
        self.assertIn('WhatsApp', motif)

    def test_aucune_touche_nest_convertie_en_appel(self):
        sans = self._lead('Aziz', telephone='', whatsapp='')
        mobile = self._lead('Karim', telephone=MOBILE)
        self.assertEqual(self._canaux(sans), self._canaux(mobile))


class LaPreferenceDuClientGagneTests(_Base):
    """CAD32 × CAD34 : « WhatsApp uniquement » n'est jamais rebasculé en
    appel par le moteur."""

    slug = 'cad34-preference'

    def test_un_whatsapp_only_sur_un_fixe_reste_en_WhatsApp(self):
        lead = self._lead(
            telephone=FIXE,
            contact_preference=Lead.ContactPreference.WHATSAPP_ONLY)
        for gabarit, _echeance in self._plan(lead):
            self.assertTrue(horaires.est_un_message(gabarit.canal),
                            (gabarit.ordre, gabarit.canal))
