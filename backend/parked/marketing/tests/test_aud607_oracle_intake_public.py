"""AUD607 — le formulaire d'intake public ne doit plus être un ORACLE
d'existence de lead (fuite de données personnelles, loi 09-08/CNDP).

Constat d'origine : ``formulaire_intake_public`` (``AllowAny``, seul rempart
un débit 30/min/IP) retirait de ``champs`` les entrées déjà renseignées sur
le lead correspondant à ``?identifiant=`` — un e-mail CONNU renvoyait donc
une liste plus courte qu'un e-mail INCONNU. Un tiers pouvait énumérer des
adresses et savoir lesquelles sont clientes.

Test ROUGE d'abord : ``test_reponses_indistinguables_connu_vs_inconnu``
échoue sur le code d'avant (3 champs pour l'inconnu, 1 seul pour le connu).

Après correctif : la réponse est uniforme par construction et le progressive
profiling n'a lieu que sur PREUVE de propriété de l'identifiant (jeton signé,
même modèle de confiance que ``desinscription/<token>``).
"""
from django.test import TestCase
from django.urls import reverse

from authentication.models import Company

from apps.crm.models import Lead
from apps.marketing import services
from apps.marketing.models import FormulaireIntake


class OracleIntakePublicTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud607', nom='AUD607')
        self.formulaire = FormulaireIntake.objects.create(
            company=self.co, nom='Pompage agricole', slug='pompage-aud607',
            champs=[{'code': 'nom'}, {'code': 'email'}, {'code': 'ville'}])
        # Un lead RÉEL, celui que l'attaquant cherche à détecter.
        Lead.objects.create(
            company=self.co, nom='Ahmed', email='ahmed@exemple.ma')

    def _get(self, query=''):
        url = reverse('mkt-formulaire-intake-public',
                      kwargs={'slug': 'pompage-aud607'})
        res = self.client.get(url + query)
        self.assertEqual(res.status_code, 200)
        return res.json()

    def test_reponses_indistinguables_connu_vs_inconnu(self):
        """Le coeur d'AUD607 : aucune différence observable entre un
        identifiant CONNU et un identifiant INCONNU."""
        connu = self._get('?identifiant=ahmed@exemple.ma')
        inconnu = self._get('?identifiant=personne@exemple.ma')
        self.assertEqual(connu, inconnu)

    def test_identifiant_ne_change_rien_par_rapport_a_aucun_identifiant(self):
        """Fournir un identifiant ne change strictement rien : le paramètre
        en clair est ignoré, aucune lecture CRM n'a lieu."""
        anonyme = self._get()
        avec_identifiant = self._get('?identifiant=ahmed@exemple.ma')
        self.assertEqual(anonyme, avec_identifiant)

    def test_telephone_connu_indistinguable_aussi(self):
        """Le même oracle existait par téléphone (branche ``phone``)."""
        Lead.objects.create(
            company=self.co, nom='Fatima', telephone='0612345678',
            ville='Agadir')
        connu = self._get('?identifiant=0612345678')
        inconnu = self._get('?identifiant=0699999999')
        self.assertEqual(connu, inconnu)

    def test_liste_toujours_complete_avec_drapeau_deja_rempli(self):
        """Contrat uniforme : liste COMPLÈTE, jamais une entrée retirée, et
        un drapeau ``deja_rempli`` séparé par champ."""
        data = self._get('?identifiant=ahmed@exemple.ma')
        codes = [c['code'] for c in data['champs']]
        self.assertEqual(codes, ['nom', 'email', 'ville'])
        self.assertTrue(
            all(c['deja_rempli'] is False for c in data['champs']))

    def test_jeton_signe_reactive_le_progressive_profiling(self):
        """La capacité NTMKT17 survit, mais seulement sur PREUVE de
        propriété de l'identifiant."""
        jeton = services.generer_token_profilage(
            self.co.id, 'ahmed@exemple.ma')
        data = self._get(f'?jeton={jeton}')
        drapeaux = {c['code']: c['deja_rempli'] for c in data['champs']}
        # La liste reste complète — seuls les drapeaux changent.
        self.assertEqual(sorted(drapeaux), ['email', 'nom', 'ville'])
        self.assertTrue(drapeaux['nom'])
        self.assertTrue(drapeaux['email'])
        self.assertFalse(drapeaux['ville'])

    def test_jeton_invalide_retombe_sur_la_reponse_anonyme(self):
        """Jeton forgé/corrompu : aucune 500, aucune différence observable."""
        self.assertEqual(self._get('?jeton=nimportequoi'), self._get())

    def test_jeton_dune_autre_societe_nouvre_rien(self):
        """Multi-tenance : un jeton émis pour une autre société ne peut pas
        lire le CRM de celle-ci."""
        autre = Company.objects.create(slug='aud607b', nom='AUD607b')
        jeton = services.generer_token_profilage(
            autre.id, 'ahmed@exemple.ma')
        self.assertEqual(self._get(f'?jeton={jeton}'), self._get())

    def test_lire_token_profilage_rejette_le_vide(self):
        self.assertEqual(services.lire_token_profilage(None), (None, None))
        self.assertEqual(services.lire_token_profilage(''), (None, None))
