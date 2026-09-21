"""CAD32 — « WhatsApp uniquement » cesse d'être saisi puis ignoré.

`Lead.contact_preference` porte la valeur `whatsapp_only` : c'est une
question posée UNE FOIS au client, explicitement (« comment voulez-vous
qu'on vous recontacte ? »). Le mot n'apparaissait NULLE PART dans le moteur
de cadence — ni au calcul des échéances, ni à l'initialisation du plan, ni à
la matérialisation réactive, ni dans les horaires. Un prospect qui a coché
« ne m'appelez pas » recevait donc les six appels du protocole.

Ce qui change, et RIEN d'autre : sur ce segment, un barreau de canal APPEL
naît en canal WhatsApp. Le nombre de touches, les libellés, les délais et les
JOURS restent exactement ceux du protocole — c'est ce que ce fichier
verrouille, barreau par barreau, contre un lead témoin identique qui, lui,
accepte le téléphone.

La touche DOMINICALE reste un appel ICI : c'est CAD33 (décision fondateur du
21/09/2026) qui tranche qu'elle suit elle aussi la préférence du client. Ce
fichier fige donc l'état intermédiaire — « 0 barreau de canal appel HORS
dimanche » — et `tests_cad33_dimanche_whatsapp_only.py` fige la suite.

Le temps est GELÉ.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires
from apps.crm.models import Lead, RelanceEtape
from apps.crm.serializers import RelanceEtapeSerializer
from apps.crm.services import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 8 septembre 2026, 11 h — jour ouvré, en pleine fenêtre.
DEPART = datetime.datetime(2026, 9, 8, 11, 0, tzinfo=horaires.CASABLANCA)
GEL = datetime.datetime(2026, 9, 7, 7, 0, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad32'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD32 Solaire', slug=f'{self.slug}-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.whatsapp_only = self._lead(
            'Aziz', Lead.ContactPreference.WHATSAPP_ONLY)
        self.temoin = self._lead('Karim', Lead.ContactPreference.PHONE_OK)

    def _lead(self, prenom, preference):
        return Lead.objects.create(
            company=self.company, nom='Benali', prenom=prenom,
            ville='Bouskoura', owner=self.acteur,
            contact_preference=preference)

    def _plan(self, lead, cadence='contact'):
        return calculer_echeances_cadence(lead, cadence, DEPART)

    def _par_ordre(self, lead, cadence='contact'):
        return {g.ordre: (g, e.astimezone(horaires.CASABLANCA))
                for g, e in self._plan(lead, cadence)}


class ZeroAppelHorsDimancheTests(_Base):
    """Le « Done = » de la tâche."""

    slug = 'cad32-canal'

    def test_aucun_barreau_dappel_hors_dimanche(self):
        for gabarit, _echeance in self._plan(self.whatsapp_only):
            if getattr(gabarit, 'dimanche_ok', False):
                continue
            self.assertTrue(
                horaires.est_un_message(gabarit.canal),
                (gabarit.ordre, gabarit.libelle, gabarit.canal))

    def test_le_lead_temoin_garde_ses_appels(self):
        """Garde négative : sans la préférence, RIEN ne bouge."""
        appels = [g.ordre for g, _e in self._plan(self.temoin)
                  if not horaires.est_un_message(g.canal)]
        self.assertTrue(appels)

    def test_le_nombre_de_touches_est_identique(self):
        self.assertEqual(len(self._plan(self.whatsapp_only)),
                         len(self._plan(self.temoin)))

    def test_les_JOURS_sont_identiques(self):
        adapte = self._par_ordre(self.whatsapp_only)
        temoin = self._par_ordre(self.temoin)
        self.assertEqual(sorted(adapte), sorted(temoin))
        for ordre in temoin:
            self.assertEqual(adapte[ordre][1].date(), temoin[ordre][1].date(),
                             ordre)

    def test_les_libelles_et_les_delais_sont_identiques(self):
        adapte = self._par_ordre(self.whatsapp_only)
        temoin = self._par_ordre(self.temoin)
        for ordre, (gabarit, _quand) in temoin.items():
            autre = adapte[ordre][0]
            self.assertEqual(autre.libelle, gabarit.libelle, ordre)
            self.assertEqual(autre.delai_jours, gabarit.delai_jours, ordre)
            self.assertEqual(autre.delai_minutes, gabarit.delai_minutes,
                             ordre)

    def test_la_touche_dominicale_reste_un_appel_ICI(self):
        """État intermédiaire assumé : c'est CAD33 qui la bascule."""
        dominicales = [g for g, _e in self._plan(self.whatsapp_only)
                       if getattr(g, 'dimanche_ok', False)]
        self.assertEqual(len(dominicales), 1)
        self.assertFalse(horaires.est_un_message(dominicales[0].canal))

    def test_le_suivi_apres_devis_est_adapte_aussi(self):
        for gabarit, _echeance in self._plan(self.whatsapp_only,
                                             'apres_devis'):
            if getattr(gabarit, 'dimanche_ok', False):
                continue
            self.assertTrue(horaires.est_un_message(gabarit.canal),
                            (gabarit.ordre, gabarit.canal))


class AucunScriptDappelNestEnvoyeTests(_Base):
    """Un script d'appel n'est pas un message à coller."""

    slug = 'cad32-scripts'

    def test_un_barreau_adapte_perd_sa_cle_de_script(self):
        temoin = self._par_ordre(self.temoin)
        adapte = self._par_ordre(self.whatsapp_only)
        adaptes = [ordre for ordre, (g, _e) in temoin.items()
                   if not horaires.est_un_message(g.canal)
                   and not getattr(g, 'dimanche_ok', False)]
        self.assertTrue(adaptes)
        for ordre in adaptes:
            self.assertEqual(adapte[ordre][0].template_cle, '', ordre)

    def test_un_barreau_DEJA_message_garde_son_gabarit(self):
        temoin = self._par_ordre(self.temoin)
        adapte = self._par_ordre(self.whatsapp_only)
        for ordre, (gabarit, _quand) in temoin.items():
            if horaires.est_un_message(gabarit.canal):
                self.assertEqual(adapte[ordre][0].template_cle,
                                 gabarit.template_cle, ordre)

    def test_le_gabarit_de_la_societe_nest_jamais_mute(self):
        """On ENVELOPPE, on ne réécrit pas le référentiel : le lead témoin
        calculé APRÈS doit retrouver ses appels."""
        self._plan(self.whatsapp_only)
        appels = [g.ordre for g, _e in self._plan(self.temoin)
                  if not horaires.est_un_message(g.canal)]
        self.assertTrue(appels)


class LaFicheDitPourquoiTests(_Base):
    """« La fiche affiche : canal adapté à la préférence du client. »"""

    slug = 'cad32-fiche'

    def _touche(self, lead):
        due = DEPART + datetime.timedelta(days=1)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=4,
            due_at=due, due_date=due.date(),
            canal=RelanceEtape.Canal.WHATSAPP, libelle='Appel 3')

    def test_la_touche_dun_lead_whatsapp_only_porte_la_phrase(self):
        donnees = RelanceEtapeSerializer(
            self._touche(self.whatsapp_only)).data
        self.assertIn('canal_adapte', donnees)
        self.assertIn('préférence du client', donnees['canal_adapte'])

    def test_une_touche_ordinaire_ne_porte_RIEN(self):
        donnees = RelanceEtapeSerializer(self._touche(self.temoin)).data
        self.assertEqual(donnees['canal_adapte'], '')

    def test_la_forme_est_celle_du_contrat_partage(self):
        import json
        from pathlib import Path
        contrat = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'relance_etape_v2.json').read_text(encoding='utf-8'))
        donnees = RelanceEtapeSerializer(self._touche(self.temoin)).data
        self.assertEqual(set(donnees),
                         set(contrat['exemple']['results'][0]))
