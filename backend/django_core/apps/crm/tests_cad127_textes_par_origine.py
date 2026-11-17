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
from apps.crm.cadence_messages import _cle_identite_pour_lead, message_pour_etape
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
                    _cle_identite_pour_lead(lead, 'identite',
                                            reference=AUJOURDHUI), cle)

    def test_aucune_AUTRE_cle_n_est_detournee(self):
        """Seule la touche d'identité change ; le reste passe intact."""
        lead = self._lead('telephone')
        for cle in ('valeur_j1', 'j9_validite', 'ma_cle_maison', ''):
            with self.subTest(cle=cle):
                self.assertEqual(
                    _cle_identite_pour_lead(lead, cle, reference=AUJOURDHUI),
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

    def test_parrain_anonymise_phrase_omise(self):
        """ASOC63 (C-ASOC-062) — un parrain effacé ne devient jamais
        « Anonymisé nous a parlé de vous » : phrase omise, manquant listé."""
        from apps.crm.dsr_provider import erase_crm
        lead = self._lead('reference', nom='Filleul')
        parrain = Client.objects.create(
            company=self.company, nom='Benali',
            email='parrain.asoc63@example.com')
        Parrainage.objects.create(
            company=self.company, parrain=parrain, filleul_lead=lead)
        erase_crm(self.company, 'parrain.asoc63@example.com')

        rendu = message_pour_etape(self._touche_identite(lead),
                                   user=self.acteur)

        self.assertNotIn('Anonymisé', rendu['message'])
        self.assertNotIn('nous a parlé de vous', rendu['message'])
        self.assertIn('prescripteur', rendu['placeholders_manquants'])

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
            _cle_identite_pour_lead(lead, 'identite', reference=AUJOURDHUI),
            'identite_ancien_dossier')

        rendu = message_pour_etape(self._touche_identite(lead),
                                   user=self.acteur)
        self.assertIn('mars 2026', rendu['message'])
        self.assertNotIn(PHRASE_FORMULAIRE, rendu['message'].lower())

    def test_le_mois_du_dossier_lit_la_date_d_origine(self):
        # ACVI47 — importé en septembre, le dossier de juin reste un dossier de juin.
        lead = self._lead('meta_ads', nom='Importe')
        Lead.objects.filter(pk=lead.pk).update(
            date_creation_origine=datetime.datetime(
                2026, 6, 10, 9, 0, tzinfo=horaires.CASABLANCA))
        lead.refresh_from_db()

        self.assertEqual(
            _cle_identite_pour_lead(lead, 'identite', reference=AUJOURDHUI),
            'identite_ancien_dossier')
        rendu = message_pour_etape(self._touche_identite(lead), user=self.acteur)
        self.assertIn('juin 2026', rendu['message'])

    def test_une_fiche_du_MOIS_EN_COURS_reste_une_demande_fraiche(self):
        lead = self._lead('site_web', nom='Frais')
        self.assertEqual(
            _cle_identite_pour_lead(lead, 'identite', reference=AUJOURDHUI),
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
            _cle_identite_pour_lead(lead, 'identite', reference=AUJOURDHUI),
            'identite_ancien_dossier')


class PiecesRecuesRendUnMessageTests(_Base):
    """16/11/2026 — l'étape « Relancer le client pour ses pièces » (clé moteur
    `pieces_recues`) a un message prêt : celle posée avec `relance_pieces`, et
    celle déjà ouverte en prod (`template_cle` vide) que le rendu retrouve par
    sa clé."""
    slug = 'cad127-pieces'

    def _etape(self, lead, template_cle, ordre):
        # Un `ordre` par touche : une seule touche OUVERTE par (lead, cadence, ordre).
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='generique', ordre=ordre,
            cle='pieces_recues', due_at=MAINTENANT, due_date=AUJOURDHUI,
            canal='whatsapp', libelle='Pièces reçues ?',
            template_cle=template_cle)

    def test_le_message_est_rendu_avec_ou_sans_template_cle(self):
        lead = self._lead('site_web', nom='Pro')
        lead.type_installation = Lead.TypeInstallation.INDUSTRIEL
        lead.societe = 'Boulangerie Atlas'
        lead.save(update_fields=['type_installation', 'societe'])
        for ordre, template_cle in enumerate(('relance_pieces', ''), start=1):
            with self.subTest(template_cle=template_cle):
                rendu = message_pour_etape(
                    self._etape(lead, template_cle, ordre), user=self.acteur)
                texte = rendu['message']
                self.assertTrue(texte.strip())
                self.assertIn('Boulangerie Atlas', texte)
                self.assertIn('factures', texte)
                self.assertIn('STOP', texte)
                self.assertNotIn('{', texte)

class AppelOuvertureSuitLOrigineTests(_Base):
    """17/11/2026 — « Vous venez de remplir notre formulaire » se disait aussi AU
    TÉLÉPHONE : l'appel d'ouverture suit l'origine comme `identite`, avec les
    MÊMES règles (canal enregistré, dossier d'un mois antérieur) et la même
    omission quand le prescripteur ou le mois manque — la mention légale
    (appel commercial, d'où viennent les coordonnées) part dans tous les cas."""
    slug = 'cad127-appel'

    def setUp(self):
        super().setUp()
        # Sans prénom de conseiller, la salutation (qui le porte) est omise.
        self.acteur.first_name = 'Karim'
        self.acteur.save(update_fields=['first_name'])

    MENTION = "d'où viennent vos coordonnées"

    def _touche_appel(self, lead, ordre=2):
        quand = datetime.datetime.combine(
            AUJOURDHUI, datetime.time(10, 3), tzinfo=horaires.CASABLANCA)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=ordre,
            due_at=quand, due_date=AUJOURDHUI, canal='appel',
            libelle="Appel d'ouverture", template_cle='appel_ouverture')

    def test_chaque_canal_d_origine_rend_SA_cle_d_appel(self):
        attendu = {
            'reference': 'appel_ouverture_reference',
            'telephone': 'appel_ouverture_telephone',
            'walk_in': 'appel_ouverture_telephone',
            'whatsapp_ctwa': 'appel_ouverture_whatsapp_entrant',
            'site_web': 'appel_ouverture',
            'meta_ads': 'appel_ouverture',
            'autre': 'appel_ouverture',
            '': 'appel_ouverture',
        }
        for canal, cle in attendu.items():
            with self.subTest(canal=canal):
                lead = self._lead(canal, nom=f'A-{canal or "vide"}')
                self.assertEqual(
                    _cle_identite_pour_lead(lead, 'appel_ouverture',
                                            reference=AUJOURDHUI), cle)

    def test_un_dossier_d_un_mois_anterieur_prime_sur_le_canal(self):
        lead = self._lead('telephone', nom='AncienAppel')
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=datetime.datetime(
                2026, 3, 4, 9, 0, tzinfo=horaires.CASABLANCA))
        lead.refresh_from_db()
        self.assertEqual(
            _cle_identite_pour_lead(lead, 'appel_ouverture',
                                    reference=AUJOURDHUI),
            'appel_ouverture_ancien_dossier')
        rendu = message_pour_etape(self._touche_appel(lead), user=self.acteur)
        self.assertIn('Vous nous aviez consultés en mars 2026 au sujet du '
                      'solaire.', rendu['message'])
        self.assertIn(self.MENTION, rendu['message'])

    def test_les_autres_cles_d_appel_ne_sont_pas_detournees(self):
        lead = self._lead('telephone', nom='AutresAppels')
        for cle in ('appel_relance', 'appel_dernier', 'repondeur',
                    'appel_validite', 'appel_ouverture_telephone'):
            with self.subTest(cle=cle):
                self.assertEqual(
                    _cle_identite_pour_lead(lead, cle, reference=AUJOURDHUI),
                    cle)

    def test_le_message_rendu_dit_l_origine_et_garde_la_mention_legale(self):
        for canal, phrase in (
                ('telephone', 'Suite à notre échange au sujet du solaire.'),
                ('walk_in', 'Suite à notre échange au sujet du solaire.'),
                ('whatsapp_ctwa',
                 'Merci pour votre message au sujet du solaire.')):
            with self.subTest(canal=canal):
                lead = self._lead(canal, nom=f'R-{canal}')
                rendu = message_pour_etape(self._touche_appel(lead),
                                           user=self.acteur)
                message = rendu['message']
                self.assertIn(phrase, message)
                self.assertNotIn('formulaire', message.lower())
                self.assertIn("c'est un appel commercial", message)
                self.assertIn(self.MENTION, message)
                self.assertTrue(message.endswith('Je vous dérange deux '
                                                 'minutes ?'))
                self.assertNotIn('STOP', message)

    def test_un_lead_de_formulaire_garde_le_texte_d_origine(self):
        lead = self._lead('site_web', nom='FormulaireAppel')
        rendu = message_pour_etape(self._touche_appel(lead), user=self.acteur)
        self.assertIn('Vous venez de remplir notre formulaire pour le solaire',
                      rendu['message'])

    def test_le_prescripteur_nomme_la_phrase_d_origine(self):
        lead = self._lead('reference', nom='ParrainAppel')
        parrain = Client.objects.create(
            company=self.company, nom='Benali',
            email='parrain.appel@example.com')
        Parrainage.objects.create(
            company=self.company, parrain=parrain, filleul_lead=lead)
        rendu = message_pour_etape(self._touche_appel(lead), user=self.acteur)
        self.assertIn('Benali nous a parlé de vous pour le solaire.',
                      rendu['message'])
        self.assertIn(self.MENTION, rendu['message'])

    def test_sans_parrain_la_phrase_d_origine_est_omise_la_mention_reste(self):
        """MRY13 : jamais un crochet, jamais un nom inventé — et la mention
        légale, dans sa propre phrase, n'est PAS emportée avec elle."""
        lead = self._lead('reference', nom='SansParrainAppel')
        rendu = message_pour_etape(self._touche_appel(lead), user=self.acteur)
        message = rendu['message']
        self.assertNotIn('{prescripteur}', message)
        self.assertNotIn('nous a parlé de vous', message)
        self.assertIn('prescripteur', rendu['placeholders_manquants'])
        self.assertIn("c'est un appel commercial", message)
        self.assertIn(self.MENTION, message)

    def test_la_langue_darija_suit_la_meme_origine(self):
        lead = self._lead('telephone', nom='DarijaAppel')
        rendu = message_pour_etape(self._touche_appel(lead),
                                   user=self.acteur, langue='darija')
        self.assertIn('بعد الهضرة ديالنا على الطاقة الشمسية.',
                      rendu['message'])
        self.assertIn('هادا اتصال تجاري', rendu['message'])
        self.assertNotIn('الفورم', rendu['message'])

    def test_le_client_deja_signe_lit_son_script_sur_son_barreau(self):
        lead = self._lead('site_web', nom='Signe')
        etape = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='deuxieme_affaire',
            ordre=2, due_at=MAINTENANT, due_date=AUJOURDHUI, canal='appel',
            libelle="Appel d'ouverture",
            template_cle='appel_ouverture_deuxieme_affaire')
        rendu = message_pour_etape(etape, user=self.acteur)
        self.assertIn('Nous avons déjà travaillé ensemble sur votre première '
                      'installation.', rendu['message'])
        self.assertNotIn('formulaire', rendu['message'].lower())
        self.assertIn(self.MENTION, rendu['message'])


class EtapesDuMoteurSansGabaritTests(_Base):
    """17/11/2026 — une étape posée SANS `template_cle` mais portant une clé de
    moteur rend le texte PAR DÉFAUT de cette clé (étapes déjà ouvertes en prod,
    société dont la ligne de gabarit est vide). `pieces_recues` garde le sien."""
    slug = 'cad127-moteur'

    def setUp(self):
        super().setUp()
        # Sans prénom de conseiller, la salutation (qui le porte) est omise.
        self.acteur.first_name = 'Karim'
        self.acteur.save(update_fields=['first_name'])

    def _etape(self, lead, ordre, cle, canal, libelle, template_cle=''):
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='generique', ordre=ordre,
            cle=cle, due_at=MAINTENANT, due_date=AUJOURDHUI, canal=canal,
            libelle=libelle, template_cle=template_cle)

    def test_chaque_etape_du_moteur_sans_gabarit_rend_le_defaut_de_sa_cle(self):
        lead = self._lead('site_web', nom='Moteur')
        cas = (
            ('message_creneau', 'whatsapp',
             "Message — proposer un créneau pour l'appel",
             "Je n'ai pas réussi à vous joindre. Quel moment vous arrange "
             'pour un appel de cinq minutes ?'),
            ('dernier_appel', 'appel',
             'Rappeler — dernier essai avant de chiffrer',
             'Je reviens vers vous pour votre demande solaire — vous avez '
             'deux minutes maintenant ?'),
            ('rappel_convenu', 'appel', 'Rappeler le client — rappel convenu',
             'Je vous rappelle comme convenu — vous avez deux minutes '
             'maintenant ?'),
            ('planifier', 'appel', 'Planifier la visite technique convenue',
             'Je vous appelle pour fixer la date de la visite technique.'),
        )
        for ordre, (cle, canal, libelle, phrase) in enumerate(cas, start=1):
            with self.subTest(cle=cle):
                rendu = message_pour_etape(
                    self._etape(lead, ordre, cle, canal, libelle),
                    user=self.acteur)
                self.assertIn(phrase, rendu['message'])
                self.assertTrue(rendu['message'].startswith('Bonjour'))
                self.assertNotIn('{', rendu['message'])
        # Seul le message écrit porte la porte de sortie.
        message = message_pour_etape(
            RelanceEtape.objects.get(lead=lead, cle='message_creneau'),
            user=self.acteur)['message']
        self.assertIn('STOP', message)

    def test_une_etape_reconnue_par_son_libelle_par_defaut_aussi(self):
        """Posée avant la clé (`cle` vide) : reconnue par son libellé par défaut."""
        lead = self._lead('site_web', nom='MoteurAncien')
        rendu = message_pour_etape(
            self._etape(lead, 1, '', 'appel',
                        'Rappeler le client — rappel convenu'),
            user=self.acteur)
        self.assertIn('Je vous rappelle comme convenu', rendu['message'])

    def test_l_etape_devis_n_a_toujours_aucun_texte(self):
        lead = self._lead('site_web', nom='Devis')
        rendu = message_pour_etape(
            self._etape(lead, 1, 'devis', 'appel',
                        'Préparer et envoyer le devis (ou fixer un rappel)'),
            user=self.acteur)
        self.assertEqual(rendu['message'], '')

    def test_un_gabarit_pose_n_est_jamais_remplace(self):
        lead = self._lead('site_web', nom='Gabarit')
        rendu = message_pour_etape(
            self._etape(lead, 1, 'dernier_appel', 'appel',
                        'Rappeler — dernier essai avant de chiffrer',
                        template_cle='appel_dernier'), user=self.acteur)
        self.assertIn('Dernier essai avant de classer votre demande',
                      rendu['message'])


class LeReveilJ30EnAppelLitLeScriptDAppelTests(_Base):
    """17/11/2026 — le réveil J30 est un APPEL : il lisait le WhatsApp
    `reveil_a1`/`reveil_a2` (« je vous l'envoie ici… Répondez STOP »). Les
    étapes déjà ouvertes en prod portent encore l'ancienne clé : le rendu la
    traduit sur un canal d'appel ; un réveil passé en WhatsApp la garde."""
    slug = 'cad127-reveil'

    def setUp(self):
        super().setUp()
        # Sans prénom de conseiller, la salutation (qui le porte) est omise.
        self.acteur.first_name = 'Karim'
        self.acteur.save(update_fields=['first_name'])

    def _reveil(self, lead, ordre, template_cle, canal):
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='reveil', ordre=ordre,
            due_at=MAINTENANT, due_date=AUJOURDHUI, canal=canal,
            libelle='Réveil J30', template_cle=template_cle)

    def test_un_reveil_en_appel_lit_le_script_d_appel(self):
        lead = self._lead('site_web', nom='ReveilAppel')
        for ordre, (cle, phrase) in enumerate((
                ('reveil_a1', 'Vous aviez reçu un devis solaire chez nous.'),
                ('reveil_a2', 'Il y a un mois, vous vous renseigniez sur le '
                              'solaire.')), start=1):
            with self.subTest(cle=cle):
                rendu = message_pour_etape(
                    self._reveil(lead, ordre, cle, 'appel'), user=self.acteur)
                message = rendu['message']
                self.assertIn(phrase, message)
                self.assertIn("c'est un appel commercial", message)
                self.assertTrue(message.endswith(
                    "Votre projet est-il toujours d'actualité ?"))
                self.assertNotIn('STOP', message)
                self.assertNotIn(' ici', message)

    def test_un_reveil_en_whatsapp_garde_son_texte_whatsapp(self):
        lead = self._lead('site_web', nom='ReveilWhatsApp')
        rendu = message_pour_etape(
            self._reveil(lead, 1, 'reveil_a1', 'whatsapp'), user=self.acteur)
        self.assertIn('Je me lance ?', rendu['message'])
        self.assertIn('STOP', rendu['message'])

    def test_le_script_d_appel_stocke_se_rend_tel_quel(self):
        lead = self._lead('site_web', nom='ReveilStocke')
        rendu = message_pour_etape(
            self._reveil(lead, 1, 'appel_reveil_devis', 'appel'),
            user=self.acteur)
        self.assertIn('en 3D', rendu['message'])
        self.assertNotIn('STOP', rendu['message'])

    def test_un_lead_agricole_n_entend_ni_toit_ni_3d(self):
        lead = self._lead('site_web', nom='ReveilAgricole')
        lead.type_installation = Lead.TypeInstallation.AGRICOLE
        lead.save(update_fields=['type_installation'])
        devis = message_pour_etape(
            self._reveil(lead, 1, 'reveil_a1', 'appel'),
            user=self.acteur)['message']
        self.assertIn('devis de pompage solaire', devis)
        self.assertIn('je vous refais le chiffrage à jour', devis)
        for mot in ('toit', '3D', 'économies'):
            self.assertNotIn(mot, devis)
        sans = message_pour_etape(
            self._reveil(lead, 2, 'reveil_a2', 'appel'),
            user=self.acteur)['message']
        self.assertIn('vous renseigniez sur le pompage solaire', sans)

