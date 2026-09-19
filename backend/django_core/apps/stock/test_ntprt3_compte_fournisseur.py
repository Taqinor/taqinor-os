"""NTPRT3 — compte portail fournisseur RÉEL (`CompteFournisseurPortail`).

Ce que la tâche exige, et ce que ce module vérifie :

1. **Le fournisseur se connecte par le login STANDARD.** Le provisionnement
   crée un `CustomUser` `portee=portail_fournisseur` rattaché au fournisseur,
   avec un mot de passe temporaire à changer — jamais un second système
   d'authentification, jamais un mot de passe rendu à l'appelant.
2. **ISOLATION CROISÉE (critère d'acceptation).** Deux fournisseurs provisionnés
   dans la MÊME société : chacun, authentifié par SON jeton, ne voit que SES
   bons de commande. Et un `fournisseur_id` d'une AUTRE société ne provisionne
   rien.
3. **La révocation ferme les DEUX portes** — le drapeau métier `actif` ET
   `CustomUser.is_active`, que SimpleJWT refuse dès l'authentification (donc un
   jeton déjà distribué cesse de fonctionner).

Run :
    python manage.py test apps.stock.test_ntprt3_compte_fournisseur -v2
"""
import datetime
import itertools

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.achats.models import (
    BonCommandeFournisseur, LigneBonCommandeFournisseur,
)
from apps.roles.models import ROLE_PORTAIL_FOURNISSEUR
from apps.stock.models import CompteFournisseurPortail, Fournisseur, Produit
from apps.stock.selectors import (
    bcf_portail_fournisseur, compte_fournisseur_portail_actif,
)
from apps.stock.services import (
    provisionner_compte_fournisseur, reactiver_acces_compte_fournisseur,
    revoquer_acces_compte_fournisseur,
)
from authentication.models import Company, CustomUser

#: Endpoint AUTHENTIFIÉ « Mes BCF » (NTPRT21) — la surface que ce compte ouvre.
URL_MES_BCF = '/api/django/portail/mes-bons-commande/'

#: Prix d'achat DISTINCTIF (5 chiffres) : un petit nombre se retrouverait par
#: hasard dans un id ou une quantité et rendrait l'assertion d'absence fausse.
PRIX_ACHAT_SECRET = '74391.00'

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def make_fournisseur(company, nom, email=''):
    return Fournisseur.objects.create(
        company=company, nom=f'{nom}-{next(_seq)}', email=email)


def make_bcf(company, fournisseur, produit=None):
    bc = BonCommandeFournisseur.objects.create(
        company=company, fournisseur=fournisseur,
        reference=f'BCF-NTPRT3-{next(_seq)}',
        statut=BonCommandeFournisseur.Statut.ENVOYE,
        date_commande=datetime.date(2026, 4, 1),
        date_livraison_prevue=datetime.date(2026, 4, 20))
    if produit is None:
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, designation='Onduleur hybride', sans_stock=True,
            quantite=4)
    else:
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=produit, quantite=4,
            prix_achat_unitaire=PRIX_ACHAT_SECRET)
    return bc


def api_jwt(user):
    """Client authentifié par un VRAI jeton : c'est la seule façon de prouver
    qu'une désactivation de compte referme la porte (``force_authenticate``
    court-circuite l'authentification et ne le verrait jamais)."""
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ProvisionnementCompteFournisseurTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt3-co', 'NTPRT3 Société')
        self.fournisseur = make_fournisseur(
            self.company, 'Alpha', email='contact@alpha-ntprt3.ma')

    def test_cree_un_compte_portee_fournisseur_rattache(self):
        user, cree = provisionner_compte_fournisseur(
            self.company, self.fournisseur.id)

        self.assertTrue(cree)
        self.assertEqual(user.portee, CustomUser.PORTEE_PORTAIL_FOURNISSEUR)
        self.assertEqual(user.portail_fournisseur_id, self.fournisseur.id)
        self.assertEqual(user.company_id, self.company.id)
        self.assertEqual(user.email, 'contact@alpha-ntprt3.ma')
        self.assertEqual(user.role.nom, ROLE_PORTAIL_FOURNISSEUR)
        # Le compte n'est ni interne ni administrateur : par construction il
        # n'atteint aucun endpoint interne.
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsNone(user.portail_client_id)
        self.assertIsNone(user.portail_partenaire_id)

    def test_mot_de_passe_temporaire_a_changer_et_jamais_rendu(self):
        user, _ = provisionner_compte_fournisseur(
            self.company, self.fournisseur.id)
        self.assertTrue(user.must_change_password)
        # Le mot de passe n'est PAS renvoyé : la fonction ne rend que le
        # compte, et le hash stocké n'est jamais un mot de passe utilisable.
        self.assertNotEqual(user.password, '')
        self.assertTrue(user.has_usable_password())
        self.assertFalse(user.check_password(''))

    def test_la_ligne_de_rattachement_est_creee(self):
        user, _ = provisionner_compte_fournisseur(
            self.company, self.fournisseur.id)
        compte = CompteFournisseurPortail.objects.get(
            company=self.company, fournisseur=self.fournisseur)
        self.assertEqual(compte.utilisateur_id, user.id)
        self.assertTrue(compte.actif)

    def test_idempotent_sans_effet_de_bord(self):
        premier, cree1 = provisionner_compte_fournisseur(
            self.company, self.fournisseur.id)
        avant = premier.password
        second, cree2 = provisionner_compte_fournisseur(
            self.company, self.fournisseur.id)

        self.assertTrue(cree1)
        self.assertFalse(cree2)
        self.assertEqual(premier.id, second.id)
        # Aucun mot de passe réinitialisé par le second appel.
        self.assertEqual(second.password, avant)
        nb_comptes = CompteFournisseurPortail.objects.filter(
            company=self.company, fournisseur=self.fournisseur).count()
        self.assertEqual(nb_comptes, 1)

    def test_re_provisionner_ne_reactive_jamais_un_acces_revoque(self):
        user, _ = provisionner_compte_fournisseur(
            self.company, self.fournisseur.id)
        revoquer_acces_compte_fournisseur(self.company, self.fournisseur.id)

        rendu, cree = provisionner_compte_fournisseur(
            self.company, self.fournisseur.id)
        self.assertFalse(cree)
        self.assertEqual(rendu.id, user.id)
        rendu.refresh_from_db()
        self.assertFalse(rendu.is_active)
        compte = CompteFournisseurPortail.objects.get(
            company=self.company, fournisseur=self.fournisseur)
        self.assertFalse(compte.actif)

    def test_fournisseur_d_une_autre_societe_ne_provisionne_rien(self):
        autre = make_company('ntprt3-autre-co', 'NTPRT3 Autre')
        etranger = make_fournisseur(autre, 'Etranger')

        self.assertEqual(
            provisionner_compte_fournisseur(self.company, etranger.id),
            (None, False))
        self.assertEqual(
            CompteFournisseurPortail.objects.filter(
                fournisseur=etranger).count(), 0)

    def test_arguments_manquants_renvoient_rien(self):
        self.assertEqual(
            provisionner_compte_fournisseur(None, self.fournisseur.id),
            (None, False))
        self.assertEqual(
            provisionner_compte_fournisseur(self.company, None),
            (None, False))


class IsolationCroiseeComptesFournisseurTests(TestCase):
    """Le critère d'acceptation de NTPRT3, joué de bout en bout."""

    def setUp(self):
        self.company = make_company('ntprt3-iso-co', 'NTPRT3 Isolation')
        self.autre_company = make_company('ntprt3-iso-co2', 'NTPRT3 Iso 2')

        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur NTPRT3', sku='OND-NTPRT3',
            prix_vente='9900.00', prix_achat=PRIX_ACHAT_SECRET)

        self.f_a = make_fournisseur(self.company, 'Alpha')
        self.f_b = make_fournisseur(self.company, 'Beta')
        self.f_etranger = make_fournisseur(self.autre_company, 'Gamma')

        self.bcf_a = make_bcf(self.company, self.f_a, produit=self.produit)
        self.bcf_b = make_bcf(self.company, self.f_b)
        self.bcf_etranger = make_bcf(self.autre_company, self.f_etranger)

        self.user_a = self._compte_utilisable(self.company, self.f_a)
        self.user_b = self._compte_utilisable(self.company, self.f_b)

    def _compte_utilisable(self, company, fournisseur):
        """Provisionne puis simule « le mot de passe temporaire a été
        changé » : sans cela la garde AUD139 refuse tout écran portail et on
        ne testerait pas l'isolation mais le rappel de mot de passe."""
        user, _ = provisionner_compte_fournisseur(company, fournisseur.id)
        user.must_change_password = False
        user.save(update_fields=['must_change_password'])
        return user

    def test_chaque_fournisseur_ne_voit_que_ses_propres_bcf(self):
        res_a = api_jwt(self.user_a).get(URL_MES_BCF)
        self.assertEqual(res_a.status_code, 200, res_a.data)
        refs_a = [ligne['reference'] for ligne in res_a.data['results']]
        self.assertIn(self.bcf_a.reference, refs_a)
        self.assertNotIn(self.bcf_b.reference, refs_a)
        self.assertNotIn(self.bcf_etranger.reference, refs_a)

        res_b = api_jwt(self.user_b).get(URL_MES_BCF)
        self.assertEqual(res_b.status_code, 200, res_b.data)
        refs_b = [ligne['reference'] for ligne in res_b.data['results']]
        self.assertIn(self.bcf_b.reference, refs_b)
        self.assertNotIn(self.bcf_a.reference, refs_b)

    def test_le_selecteur_borne_au_couple_societe_fournisseur(self):
        # Le fournisseur de l'AUTRE société, lu avec CETTE société : vide.
        self.assertEqual(
            bcf_portail_fournisseur(self.company, self.f_etranger.id), [])
        # Sans rattachement : vide, jamais les commandes de la société entière.
        self.assertEqual(bcf_portail_fournisseur(self.company, None), [])

    def test_aucun_prix_d_achat_ne_sort_vers_le_fournisseur(self):
        res = api_jwt(self.user_a).get(URL_MES_BCF)
        charge = str(res.data)
        self.assertNotIn(PRIX_ACHAT_SECRET, charge)
        self.assertNotIn(PRIX_ACHAT_SECRET.split('.')[0], charge)
        for interdit in ('prix_achat', 'prix_achat_unitaire', 'total_achat',
                         'marge'):
            self.assertNotIn(interdit, charge)


class RevocationAccesFournisseurTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt3-rev-co', 'NTPRT3 Révocation')
        self.fournisseur = make_fournisseur(self.company, 'Alpha')
        make_bcf(self.company, self.fournisseur)
        self.user, _ = provisionner_compte_fournisseur(
            self.company, self.fournisseur.id)
        self.user.must_change_password = False
        self.user.save(update_fields=['must_change_password'])

    def test_revocation_ferme_les_deux_portes(self):
        compte, nb = revoquer_acces_compte_fournisseur(
            self.company, self.fournisseur.id)

        self.assertIsNotNone(compte)
        self.assertFalse(compte.actif)
        self.assertEqual(nb, 1)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_un_jeton_deja_emis_cesse_de_fonctionner(self):
        api = api_jwt(self.user)
        self.assertEqual(api.get(URL_MES_BCF).status_code, 200)

        revoquer_acces_compte_fournisseur(self.company, self.fournisseur.id)
        # Même jeton, même client : l'authentification elle-même refuse.
        self.assertEqual(api.get(URL_MES_BCF).status_code, 401)

    def test_la_reactivation_est_explicite_et_symetrique(self):
        revoquer_acces_compte_fournisseur(self.company, self.fournisseur.id)
        compte, nb = reactiver_acces_compte_fournisseur(
            self.company, self.fournisseur.id)

        self.assertTrue(compte.actif)
        self.assertEqual(nb, 1)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(api_jwt(self.user).get(URL_MES_BCF).status_code, 200)

    def test_revoquer_un_fournisseur_sans_compte_ne_fait_rien(self):
        sans_compte = make_fournisseur(self.company, 'Sans compte')
        self.assertEqual(
            revoquer_acces_compte_fournisseur(self.company, sans_compte.id),
            (None, 0))


class EtatAccesPortailFournisseurTests(TestCase):
    """Le sélecteur distingue « jamais eu de compte » de « accès révoqué »."""

    def setUp(self):
        self.company = make_company('ntprt3-etat-co', 'NTPRT3 État')
        self.fournisseur = make_fournisseur(self.company, 'Alpha')

    def test_aucun_compte_renvoie_none(self):
        self.assertIsNone(compte_fournisseur_portail_actif(
            self.company.id, self.fournisseur.id))

    def test_compte_ouvert_renvoie_true(self):
        provisionner_compte_fournisseur(self.company, self.fournisseur.id)
        self.assertIs(compte_fournisseur_portail_actif(
            self.company.id, self.fournisseur.id), True)

    def test_compte_revoque_renvoie_false(self):
        provisionner_compte_fournisseur(self.company, self.fournisseur.id)
        revoquer_acces_compte_fournisseur(self.company, self.fournisseur.id)
        self.assertIs(compte_fournisseur_portail_actif(
            self.company.id, self.fournisseur.id), False)

    def test_arguments_manquants_renvoient_none(self):
        self.assertIsNone(
            compte_fournisseur_portail_actif(None, self.fournisseur.id))
        self.assertIsNone(
            compte_fournisseur_portail_actif(self.company.id, None))
