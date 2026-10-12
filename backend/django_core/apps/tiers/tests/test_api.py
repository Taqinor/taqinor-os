"""Tests API du répertoire ``Tiers`` (ARC17) — CRUD + isolation multi-société.

Hérite de ``TenantAPITestCase`` (deux sociétés + utilisateurs). On prouve :
  - CRUD nominal (create/list/retrieve/update/delete) pour une société ;
  - ``company`` posée côté serveur (jamais depuis le corps) ;
  - isolation stricte : la société B ne voit/modifie/supprime jamais un tiers
    de la société A (404) et sa liste ne fuit aucun tiers d'A.
"""
from testkit.base import TenantAPITestCase

from apps.tiers.models import Tiers

URL = '/api/django/tiers/tiers/'


class TiersApiTests(TenantAPITestCase):

    def _create(self, **overrides):
        payload = {
            'type_tiers': 'entreprise',
            'nom': 'ACME Solaire',
            'raison_sociale': 'ACME Solaire SARL',
            'email': 'contact@acme.ma',
            'telephone': '0522000000',
            'ice': '001122334455667',
            'is_client': True,
        }
        payload.update(overrides)
        return self.client_as().post(URL, payload, format='json')

    def test_create_scopes_company_server_side(self):
        # Même en tentant d'injecter une autre société dans le corps, le
        # serveur force request.user.company.
        r = self.client_as().post(
            URL,
            {'nom': 'Client X', 'company': self.other_company.id,
             'is_client': True},
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.content)
        tiers = Tiers.objects.get(pk=r.data['id'])
        self.assertEqual(tiers.company_id, self.company.id)

    def test_list_is_company_scoped(self):
        self._create()
        # Un tiers de l'autre société ne doit jamais apparaître.
        Tiers.objects.create(company=self.other_company, nom='Autre société')
        r = self.client_as().get(URL)
        self.assertEqual(r.status_code, 200)
        results = r.data['results'] if isinstance(r.data, dict) else r.data
        noms = {row['nom'] for row in results}
        self.assertIn('ACME Solaire', noms)
        self.assertNotIn('Autre société', noms)

    def test_retrieve_own_ok_other_company_404(self):
        r = self._create()
        tid = r.data['id']
        self.assertEqual(self.client_as().get(f'{URL}{tid}/').status_code, 200)
        # La société B ne peut pas lire le tiers de la société A.
        r2 = self.client_as(user=self.other_user).get(f'{URL}{tid}/')
        self.assertIn(r2.status_code, (403, 404))

    def test_update_and_roles(self):
        r = self._create()
        tid = r.data['id']
        r2 = self.client_as().patch(
            f'{URL}{tid}/',
            {'is_fournisseur': True, 'ville': 'Casablanca'},
            format='json',
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        tiers = Tiers.objects.get(pk=tid)
        self.assertTrue(tiers.is_fournisseur)
        self.assertTrue(tiers.is_client)
        self.assertEqual(tiers.ville, 'Casablanca')

    def test_other_company_cannot_update(self):
        r = self._create()
        tid = r.data['id']
        r2 = self.client_as(user=self.other_user).patch(
            f'{URL}{tid}/', {'ville': 'Rabat'}, format='json')
        self.assertIn(r2.status_code, (403, 404))
        self.assertNotEqual(Tiers.objects.get(pk=tid).ville, 'Rabat')

    def test_other_company_cannot_delete(self):
        r = self._create()
        tid = r.data['id']
        r2 = self.client_as(user=self.other_user).delete(f'{URL}{tid}/')
        self.assertIn(r2.status_code, (403, 404))
        self.assertTrue(Tiers.objects.filter(pk=tid).exists())

    def test_delete_own(self):
        r = self._create()
        tid = r.data['id']
        r2 = self.client_as().delete(f'{URL}{tid}/')
        self.assertEqual(r2.status_code, 204)
        self.assertFalse(Tiers.objects.filter(pk=tid).exists())

    def test_nom_complet_particulier(self):
        t = Tiers.objects.create(
            company=self.company, type_tiers='particulier',
            nom='Alaoui', prenom='Youssef')
        self.assertEqual(t.nom_complet, 'Youssef Alaoui')

    def test_nom_complet_entreprise(self):
        t = Tiers.objects.create(
            company=self.company, type_tiers='entreprise',
            nom='ACME', raison_sociale='ACME Solaire SARL')
        self.assertEqual(t.nom_complet, 'ACME Solaire SARL')


class TiersEnf11Tests(TenantAPITestCase):
    """ENF11 (api-fuzz) — corps strictement typés, e-mail vide servi tel quel."""

    def _post(self, **overrides):
        payload = {'nom': 'Strict SARL'}
        payload.update(overrides)
        return self.client_as().post(URL, payload, format='json')

    def test_texte_non_chaine_refuse_400_nommant_le_champ(self):
        for champ in ('nom', 'ville', 'adresse', 'ice'):
            r = self._post(**{champ: 0})
            self.assertEqual(r.status_code, 400, (champ, r.content))
            self.assertIn(champ, r.data, (champ, r.data))
        self.assertFalse(Tiers.objects.filter(nom='Strict SARL').exists())

    def test_booleen_non_booleen_refuse_400(self):
        for valeur in (1, 0, 'true'):
            r = self._post(is_client=valeur)
            self.assertEqual(r.status_code, 400, (valeur, r.content))
            self.assertIn('is_client', r.data)
        self.assertEqual(self._post(is_client=True).status_code, 201)

    def test_decimal_gps_est_une_chaine(self):
        r = self._post(gps_lat=33.5)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('gps_lat', r.data)
        ok = self._post(gps_lat='33.5731100', gps_lng='-7.5898430')
        self.assertEqual(ok.status_code, 201, ok.content)
        self.assertEqual(ok.data['gps_lat'], '33.5731100')
        vide = self._post(nom='Sans GPS', gps_lat='')
        self.assertEqual(vide.status_code, 201, vide.content)
        self.assertIsNone(vide.data['gps_lat'])

    def test_email_vide_accepte_et_servi_vide(self):
        r = self._post(email='')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['email'], '')
        self.assertEqual(self._post(email='pas-un-email').status_code, 400)
        self.assertEqual(self._post(email=5).status_code, 400)

    def test_schema_email_reponse_sans_format_requete_avec(self):
        from apps.tiers.serializers import EmailTiersExtension
        ext = EmailTiersExtension(target=None)
        rep = ext.map_serializer_field(None, 'response')
        req = ext.map_serializer_field(None, 'request')
        self.assertNotIn('format', rep)
        self.assertEqual(req['anyOf'][0]['format'], 'email')
