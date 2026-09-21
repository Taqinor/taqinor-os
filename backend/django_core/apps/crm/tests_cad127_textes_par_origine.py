"""CAD127 — « vous venez de remplir notre formulaire » n'est plus dit à tort.

Constat de l'audit L3 du 21/09/2026 : le message d'identité et le script
d'appel affirment tous deux que le client vient de laisser une demande, alors
que la MÊME cadence part pour un lead arrivé par téléphone, en boutique, par
recommandation, depuis un salon, repositionné par l'écran de placement, ou né
d'une conversation entrante (CTWA, livechat). Une première phrase fausse est
exactement ce qui fait perdre la confiance au premier contact — et
``unique_together (company, cle)`` interdit toute variante sur ``identite``.

Quatre clés ADDITIVES, choisies d'après le canal DÉJÀ enregistré. Correction
du round 2 : le ticket SAV n'est PAS une origine
(``create_lead_depuis_ticket`` ne démarre aucune cadence).

Le temps est GELÉ : « fiche ouverte un mois antérieur » est exactement ce
qu'une horloge vivante rend instable.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Client, Lead, Parrainage, RelanceEtape
from apps.crm.services import cle_identite_pour_lead, message_pour_etape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_messages import (
    CLE_IDENTITE_PAR_CANAL, CLES_IDENTITE_PAR_ORIGINE,
    MESSAGE_TEMPLATE_DEFAULTS,
)

User = get_user_model()

#: Lundi 21 septembre 2026, 10 h à Casablanca.
MAINTENANT = datetime.datetime(2026, 9, 21, 10, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = MAINTENANT.date()

#: La phrase qui MENT quand l'origine n'est pas un formulaire.
PHRASE_FORMULAIRE = 'laisser une demande'


class LesQuatreClesExistentTests(SimpleTestCase):
    def test_les_cinq_cles_d_identite_sont_au_catalogue(self):
        self.assertEqual(len(CLES_IDENTITE_PAR_ORIGINE), 5)
        for cle in CLES_IDENTITE_PAR_ORIGINE:
            with self.subTest(cle=cle):
                self.assertIn(cle, MESSAGE_TEMPLATE_DEFAULTS)

    def test_aucune_des_quatre_ne_pretend_un_formulaire(self):
        """Le Done, mot pour mot."""
        for cle in CLES_IDENTITE_PAR_ORIGINE[1:]:
            bas = MESSAGE_TEMPLATE_DEFAULTS[cle].lower()
            with self.subTest(cle=cle):
                self.assertNotIn('formulaire', bas)
                self.assertNotIn('demande pour le solaire', bas)
                self.assertNotIn(PHRASE_FORMULAIRE, bas)

    def test_le_texte_du_FORMULAIRE_lui_le_dit_toujours(self):
        """Anti-faux-vert : `identite` reste le texte du vrai formulaire."""
        self.assertIn(PHRASE_FORMULAIRE,
                      MESSAGE_TEMPLATE_DEFAULTS['identite'].lower())

    def test_aucun_prenom_code_en_dur_dans_les_quatre(self):
        """Le prescripteur est un PLACEHOLDER, jamais un prénom écrit."""
        self.assertIn('{prescripteur}',
                      MESSAGE_TEMPLATE_DEFAULTS['identite_reference'])
        for cle in CLES_IDENTITE_PAR_ORIGINE:
            texte = MESSAGE_TEMPLATE_DEFAULTS[cle]
            with self.subTest(cle=cle):
                self.assertNotIn('Meryem', texte)
                self.assertNotIn('Reda', texte)
                self.assertNotIn('TAQINOR', texte)

    def test_les_vrais_formulaires_ne_sont_PAS_detournes(self):
        for canal in ('site_web', 'meta_ads', 'autre', ''):
            with self.subTest(canal=canal):
                self.assertNotIn(canal, CLE_IDENTITE_PAR_CANAL)


class _Base(TestCase):
    slug = 'cad127'

    def setUp(self):
        from testkit.time import frozen

        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        CompanyProfile.objects.create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, canal, *, nom='Prospect'):
        return Lead.objects.create(
            company=self.company, nom=nom, prenom='Aziz', owner=self.acteur,
            stage=stages.NEW, canal=canal, telephone='+212661112233')

    def _touche_identite(self, lead, due=None):
        jour = due or AUJOURDHUI
        quand = datetime.datetime.combine(
            jour, datetime.time(10, 0), tzinfo=horaires.CASABLANCA)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=1,
            due_at=quand, due_date=jour, canal='whatsapp',
            libelle="Message d'identité", template_cle='identite')


class ChaqueCanalRendSonTexteTests(_Base):
    slug = 'cad127-canal'

    def test_chaque_canal_d_origine_rend_SA_cle(self):
        attendu = {
            'reference': 'identite_reference',
            'telephone': 'identite_telephone',
            'walk_in': 'identite_telephone',
            'whatsapp_ctwa': 'identite_whatsapp_entrant',
            'site_web': 'identite',
            'meta_ads': 'identite',
            'autre': 'identite',
            '': 'identite',
        }
        for canal, cle in attendu.items():
            with self.subTest(canal=canal):
                lead = self._lead(canal, nom=f'L-{canal or "vide"}')
                self.assertEqual(
                    cle_identite_pour_lead(lead, 'identite',
                                           reference=AUJOURDHUI), cle)

    def test_aucune_AUTRE_cle_n_est_detournee(self):
        """Seule la touche d'identité change ; le reste passe intact."""
        lead = self._lead('telephone')
        for cle in ('valeur_j1', 'j9_validite', 'ma_cle_maison', ''):
            with self.subTest(cle=cle):
                self.assertEqual(
                    cle_identite_pour_lead(lead, cle, reference=AUJOURDHUI),
                    cle)

    def test_le_message_rendu_ne_pretend_AUCUN_formulaire(self):
        for canal in ('reference', 'telephone', 'walk_in', 'whatsapp_ctwa'):
            with self.subTest(canal=canal):
                lead = self._lead(canal, nom=f'M-{canal}')
                etape = self._touche_identite(lead)
                rendu = message_pour_etape(etape, user=self.acteur)
                self.assertNotIn(PHRASE_FORMULAIRE,
                                 rendu['message'].lower())
                self.assertTrue(rendu['message'].strip())

    def test_un_lead_de_formulaire_garde_son_texte_d_origine(self):
        lead = self._lead('site_web', nom='Formulaire')
        rendu = message_pour_etape(self._touche_identite(lead),
                                   user=self.acteur)
        self.assertIn(PHRASE_FORMULAIRE, rendu['message'].lower())


class LePrescripteurTests(_Base):
    slug = 'cad127-prescripteur'

    def test_le_nom_du_parrain_remplit_le_placeholder(self):
        lead = self._lead('reference')
        parrain = Client.objects.create(
            company=self.company, nom='Benali',
            email='parrain@example.com')
        Parrainage.objects.create(
            company=self.company, parrain=parrain, filleul_lead=lead)

        rendu = message_pour_etape(self._touche_identite(lead),
                                   user=self.acteur)

        self.assertIn('Benali', rendu['message'])

    def test_sans_parrain_la_phrase_est_OMISE_jamais_un_crochet(self):
        """MRY13 : jamais un blanc, jamais un nom inventé."""
        lead = self._lead('reference', nom='SansParrain')
        rendu = message_pour_etape(self._touche_identite(lead),
                                   user=self.acteur)
        self.assertNotIn('{prescripteur}', rendu['message'])
        self.assertNotIn('nous a parlé de vous', rendu['message'])
        self.assertIn('prescripteur', rendu['placeholders_manquants'])


class LAncienDossierTests(_Base):
    slug = 'cad127-ancien'

    def test_une_fiche_d_un_mois_anterieur_est_un_dossier_REPRIS(self):
        lead = self._lead('site_web', nom='Ancien')
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=datetime.datetime(
                2026, 3, 4, 9, 0, tzinfo=horaires.CASABLANCA))
        lead.refresh_from_db()

        self.assertEqual(
            cle_identite_pour_lead(lead, 'identite', reference=AUJOURDHUI),
            'identite_ancien_dossier')

        rendu = message_pour_etape(self._touche_identite(lead),
                                   user=self.acteur)
        self.assertIn('mars 2026', rendu['message'])
        self.assertNotIn(PHRASE_FORMULAIRE, rendu['message'].lower())

    def test_une_fiche_du_MOIS_EN_COURS_reste_une_demande_fraiche(self):
        lead = self._lead('site_web', nom='Frais')
        self.assertEqual(
            cle_identite_pour_lead(lead, 'identite', reference=AUJOURDHUI),
            'identite')

    def test_l_ancien_dossier_PRIME_sur_le_canal(self):
        """Quel que soit le canal, une fiche de mars n'est pas une demande
        d'aujourd'hui."""
        lead = self._lead('telephone', nom='AncienTel')
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=datetime.datetime(
                2026, 3, 4, 9, 0, tzinfo=horaires.CASABLANCA))
        lead.refresh_from_db()
        self.assertEqual(
            cle_identite_pour_lead(lead, 'identite', reference=AUJOURDHUI),
            'identite_ancien_dossier')
