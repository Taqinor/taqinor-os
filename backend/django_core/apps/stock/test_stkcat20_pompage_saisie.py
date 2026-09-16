"""STKCAT20 — caractéristiques de pompage éditables depuis la fiche produit
(`pompe_cv`, `hmt_m`, `debit_m3j`, `pompe_kw`, `tension_v`, `courbe_pompe`) +
garde anti-effacement SERVEUR sur `courbe_pompe`.

Deux gardes mirorées ici, jamais réinventées :

* la FORME attendue par `debitAtHmt`/`selectPompeByCurve`
  (frontend/src/features/ventes/solar.js) avant de considérer une pompe
  éligible au dimensionnement Agricole : un dict {debits_m3h, hmt_m} de deux
  listes de MÊME longueur, au moins 2 points, valeurs numériques finies — une
  divergence de forme y était silencieuse (la pompe redevenait juste
  invisible) ; côté API c'est un 400 explicite (`ProduitSerializer.
  validate_courbe_pompe`) ;
* le garde anti-effacement de `ProduitAdminForm.clean()` (apps/stock/admin.py,
  CHAMP_CATALOGUE_VIDE_INTERDIT) : une courbe déjà enregistrée (donnée
  constructeur RÉELLE, non reconstructible) ne peut pas être remplacée par
  None/{} — seule une NOUVELLE courbe valide peut la remplacer ; la création
  (pas encore d'instance) reste exemptée, exactement comme côté admin.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role, CANONICAL_SYSTEM_ROLES
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()

URL_PRODUITS = '/api/django/stock/produits/'


def api_for(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


def url_produit(pk):
    return f'{URL_PRODUITS}{pk}/'


class STKCAT20Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='stkcat20-co', defaults={'nom': 'STKCAT20 Co'})[0]
        cls.roles = {}
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            cls.roles[nom] = Role.objects.create(
                company=cls.company, nom=nom, permissions=list(perms),
                est_systeme=True)

    def user_for(self, nom_role, username):
        return User.objects.create_user(
            username=username, password='x', company=self.company,
            role=self.roles[nom_role])


class TestCreationAvecCourbeValide(STKCAT20Base):
    """Une pompe créée via l'API avec une courbe bien formée passe (même
    garde de forme que `debitAtHmt` — au moins 2 points, listes de même
    longueur, valeurs numériques)."""

    def test_pompe_creee_avec_courbe_valide_201(self):
        user = self.user_for('Directeur', 'stkcat20_create_ok')
        payload = {
            'nom': 'Pompe OSP 30/8 (test STKCAT20)',
            'prix_vente': '6000',
            'pompe_cv': '10', 'pompe_kw': '7.5', 'tension_v': 380,
            'hmt_m': '91', 'debit_m3j': '84',
            'courbe_pompe': {
                'debits_m3h': [0, 6, 12],
                'hmt_m': [91, 88, 85],
            },
        }
        r = api_for(user).post(URL_PRODUITS, payload, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        produit = Produit.objects.get(id=r.data['id'])
        self.assertEqual(
            produit.courbe_pompe,
            {'debits_m3h': [0, 6, 12], 'hmt_m': [91, 88, 85]})
        self.assertEqual(produit.tension_v, 380)

    def test_pompe_sans_courbe_reste_acceptee_null_omis(self):
        # Une pompe fraîchement créée (pas encore mesurée par le fondateur)
        # part légitimement sans courbe — comportement historique préservé.
        user = self.user_for('Directeur', 'stkcat20_create_nocurve')
        r = api_for(user).post(
            URL_PRODUITS,
            {'nom': 'Pompe pas encore mesurée', 'prix_vente': '4000'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(Produit.objects.get(id=r.data['id']).courbe_pompe)


class TestFormeInvalideEst400(STKCAT20Base):
    """Toute divergence par rapport à la forme attendue par `debitAtHmt` est
    un 400 explicite, jamais un silence (la pompe qui « disparaît » côté
    dimensionnement)."""

    def _post(self, courbe):
        user = self.user_for('Directeur', f'stkcat20_bad_{id(courbe)}')
        return api_for(user).post(
            URL_PRODUITS,
            {'nom': 'Pompe forme invalide', 'prix_vente': '5000',
             'courbe_pompe': courbe},
            format='json')

    def test_pas_un_dict_400(self):
        r = self._post([0, 12])
        self.assertEqual(r.status_code, 400)
        self.assertIn('courbe_pompe', r.data)

    def test_cle_manquante_400(self):
        r = self._post({'debits_m3h': [0, 12]})
        self.assertEqual(r.status_code, 400)
        self.assertIn('courbe_pompe', r.data)

    def test_longueurs_differentes_400(self):
        r = self._post({'debits_m3h': [0, 6, 12], 'hmt_m': [91, 85]})
        self.assertEqual(r.status_code, 400)
        self.assertIn('courbe_pompe', r.data)

    def test_moins_de_deux_points_400(self):
        r = self._post({'debits_m3h': [0], 'hmt_m': [91]})
        self.assertEqual(r.status_code, 400)
        self.assertIn('courbe_pompe', r.data)

    def test_valeurs_non_numeriques_400(self):
        r = self._post({'debits_m3h': [0, 'douze'], 'hmt_m': [91, 85]})
        self.assertEqual(r.status_code, 400)
        self.assertIn('courbe_pompe', r.data)

    def test_booleen_refuse_meme_si_int_compatible(self):
        # `bool` est une sous-classe d'`int` en Python — explicitement exclu
        # (un True/False glissé dans la courbe n'est pas une mesure).
        r = self._post({'debits_m3h': [0, True], 'hmt_m': [91, 85]})
        self.assertEqual(r.status_code, 400)
        self.assertIn('courbe_pompe', r.data)


class TestGardeAntiEffacement(STKCAT20Base):
    """Miroir de `ProduitAdminForm.clean()` / CHAMP_CATALOGUE_VIDE_INTERDIT :
    une courbe déjà enregistrée ne peut pas être vidée par une mise à jour,
    seule une NOUVELLE courbe valide peut la remplacer ; une mise à jour qui
    ne touche pas `courbe_pompe` du tout ne la vide jamais."""

    def setUp(self):
        self.user = self.user_for('Directeur', 'stkcat20_wipe')
        self.pompe = Produit.objects.create(
            company=self.company, nom='Pompe OSP existante (STKCAT20)',
            prix_vente=6000,
            pompe_cv=10, pompe_kw=7.5, tension_v=380, hmt_m=91,
            courbe_pompe={'debits_m3h': [0, 6, 12], 'hmt_m': [91, 88, 85]},
        )

    def _patch(self, data):
        return api_for(self.user).patch(
            url_produit(self.pompe.id), data, format='json')

    def test_vider_avec_null_est_refuse(self):
        r = self._patch({'courbe_pompe': None})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('courbe_pompe', r.data)
        self.pompe.refresh_from_db()
        self.assertEqual(
            self.pompe.courbe_pompe,
            {'debits_m3h': [0, 6, 12], 'hmt_m': [91, 88, 85]})

    def test_vider_avec_dict_vide_est_refuse(self):
        r = self._patch({'courbe_pompe': {}})
        self.assertEqual(r.status_code, 400, r.data)
        self.pompe.refresh_from_db()
        self.assertTrue(self.pompe.courbe_pompe)

    def test_remplacer_par_une_nouvelle_courbe_valide_est_accepte(self):
        nouvelle = {'debits_m3h': [0, 5, 10], 'hmt_m': [95, 90, 80]}
        r = self._patch({'courbe_pompe': nouvelle})
        self.assertEqual(r.status_code, 200, r.data)
        self.pompe.refresh_from_db()
        self.assertEqual(self.pompe.courbe_pompe, nouvelle)

    def test_mise_a_jour_sans_toucher_courbe_pompe_ne_la_vide_pas(self):
        # PATCH partiel classique (ex. renommer) : le champ est absent du
        # corps -> `validate_courbe_pompe` n'est même pas appelé, la valeur
        # stockée reste intacte (comportement DRF standard du PATCH partiel).
        r = self._patch({'nom': 'Pompe OSP existante (renommée)'})
        self.assertEqual(r.status_code, 200, r.data)
        self.pompe.refresh_from_db()
        self.assertEqual(self.pompe.nom, 'Pompe OSP existante (renommée)')
        self.assertEqual(
            self.pompe.courbe_pompe,
            {'debits_m3h': [0, 6, 12], 'hmt_m': [91, 88, 85]})

    def test_creation_sans_courbe_exemptee_de_la_garde(self):
        # `self.instance` est None à la création : jamais de « vidage »
        # possible, un produit neuf part légitimement sans courbe.
        r = api_for(self.user).post(
            URL_PRODUITS,
            {'nom': 'Pompe toute neuve (STKCAT20)', 'prix_vente': '3000'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(Produit.objects.get(id=r.data['id']).courbe_pompe)
