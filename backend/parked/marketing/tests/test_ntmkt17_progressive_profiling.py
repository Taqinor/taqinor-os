"""NTMKT17 — Progressive profiling sur le formulaire public d'intake, tel
qu'AMENDÉ par AUD607.

Contrat d'origine : ``?identifiant=`` (e-mail/téléphone repris du navigateur)
RETIRAIT de la liste les champs déjà renseignés. AUD607 a montré que ce
paramètre en clair, sur un endpoint ``AllowAny``, faisait de la réponse un
oracle d'existence de lead (loi 09-08/CNDP) : la liste est désormais toujours
COMPLÈTE, chaque champ portant un drapeau ``deja_rempli``, et le profilage
n'a lieu que sur preuve de propriété (jeton signé).

Couvre ici la capacité NTMKT17 elle-même (le non-oracle est couvert par
``test_aud607_oracle_intake_public``) : visiteur sans jeton = aucun drapeau,
jeton valide = drapeaux exacts par e-mail et par téléphone, isolation
multi-société.
"""
from django.test import TestCase
from django.urls import reverse

from authentication.models import Company

from apps.crm.models import Lead
from apps.marketing import services
from apps.marketing.models import FormulaireIntake


class ProgressiveProfilingTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt17', nom='NTMKT17')
        self.formulaire = FormulaireIntake.objects.create(
            company=self.co, nom='Pompage agricole', slug='pompage-ntmkt17',
            champs=[{'code': 'nom'}, {'code': 'email'}, {'code': 'ville'}])

    def _url(self, query=''):
        return reverse(
            'mkt-formulaire-intake-public',
            kwargs={'slug': 'pompage-ntmkt17'}) + query

    def _drapeaux(self, query=''):
        res = self.client.get(self._url(query))
        self.assertEqual(res.status_code, 200)
        champs = res.json()['champs']
        # AUD607 — la liste n'est JAMAIS amputée.
        self.assertEqual([c['code'] for c in champs],
                         ['nom', 'email', 'ville'])
        return {c['code']: c['deja_rempli'] for c in champs}

    def _jeton(self, identifiant, company=None):
        return services.generer_token_profilage(
            (company or self.co).id, identifiant)

    def test_visiteur_inconnu_voit_le_formulaire_complet(self):
        self.assertEqual(
            self._drapeaux(),
            {'nom': False, 'email': False, 'ville': False})

    def test_jeton_sans_lead_correspondant_ne_leve_aucun_drapeau(self):
        jeton = self._jeton('inconnu@exemple.ma')
        self.assertEqual(
            self._drapeaux(f'?jeton={jeton}'),
            {'nom': False, 'email': False, 'ville': False})

    def test_visiteur_prouve_voit_ses_champs_deja_connus_marques(self):
        Lead.objects.create(
            company=self.co, nom='Ahmed', email='ahmed@exemple.ma')
        jeton = self._jeton('ahmed@exemple.ma')
        # nom + email déjà connus, ville jamais renseignée.
        self.assertEqual(
            self._drapeaux(f'?jeton={jeton}'),
            {'nom': True, 'email': True, 'ville': False})

    def test_visiteur_prouve_par_telephone(self):
        Lead.objects.create(
            company=self.co, nom='Fatima', telephone='0612345678',
            ville='Agadir')
        jeton = self._jeton('0612345678')
        # nom + ville connus, email jamais renseigné.
        self.assertEqual(
            self._drapeaux(f'?jeton={jeton}'),
            {'nom': True, 'email': False, 'ville': True})

    def test_no_op_sans_doublon_detecte_pour_une_autre_societe(self):
        autre = Company.objects.create(slug='ntmkt17b', nom='NTMKT17b')
        Lead.objects.create(
            company=autre, nom='Ahmed', email='ahmed@exemple.ma', ville='X')
        # Le lead existe mais dans une AUTRE société : jamais adressable,
        # même avec un jeton correctement signé pour CETTE société-ci.
        jeton = self._jeton('ahmed@exemple.ma')
        self.assertEqual(
            self._drapeaux(f'?jeton={jeton}'),
            {'nom': False, 'email': False, 'ville': False})
