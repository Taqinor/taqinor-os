"""NTPRT22 — ASN entrant : annonce de livraison déposée par le fournisseur.

Ce que la tâche exige, et ce que ce module vérifie :

1. **CRITÈRE D'ACCEPTATION — une annonce apparaît IMMÉDIATEMENT côté interne.**
   Une annonce créée par le chemin portail (le service) est servie par
   l'endpoint interne `BonsCommandeFournisseur` au premier GET suivant, sans
   aucune action manuelle.
2. **L'annonce reste INFORMATIVE.** Aucun `MouvementStock`, aucune
   `ReceptionFournisseur`, aucune `quantite_recue`, aucun `quantite_stock`
   touché — et la date DEMANDÉE du BCF (XPUR7) n'est jamais écrasée par la date
   que le fournisseur déclare.
3. **Isolation.** Le BCF d'un autre fournisseur (ou d'une autre société) est
   INTROUVABLE, en création comme en mise à jour de statut.
4. **Aucun prix ne sort.** L'annonce dit QUOI arrive, jamais combien ça coûte.

Run :
    python manage.py test apps.stock.test_ntprt22_annonce_livraison -v2
"""
import datetime
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.achats.models import (
    BonCommandeFournisseur, LigneBonCommandeFournisseur, ReceptionFournisseur,
)
from apps.roles.models import Role
from apps.stock.models import (
    AnnonceLivraisonFournisseur, Fournisseur, MouvementStock, Produit,
)
from apps.stock.selectors import (
    annonces_livraison_bon_commande, annonces_livraison_portail_fournisseur,
    resume_portail_fournisseur,
)
from apps.stock.services import (
    annoncer_livraison_fournisseur, mettre_a_jour_statut_annonce_livraison,
)
from authentication.models import Company, CustomUser

URL_BCF = '/api/django/stock/bons-commande-fournisseur/'

#: Prix d'achat DISTINCTIF (5 chiffres) : un petit nombre se retrouverait par
#: hasard dans un id ou une quantité et rendrait l'assertion d'absence fausse.
PRIX_ACHAT_SECRET = '83527.00'

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def make_interne(company, username):
    role = Role.objects.create(
        company=company, nom=f'r-{username}',
        permissions=['stock_voir', 'stock_modifier'])
    return CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role, role_legacy='responsable')


def make_fournisseur(company, nom):
    return Fournisseur.objects.create(
        company=company, nom=f'{nom}-{next(_seq)}')


def make_produit(company, nom, sku):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku, prix_vente='9900.00',
        prix_achat=PRIX_ACHAT_SECRET)


def make_bcf(company, fournisseur, produit,
             statut=BonCommandeFournisseur.Statut.ENVOYE,
             date_prevue=datetime.date(2026, 5, 20)):
    bc = BonCommandeFournisseur.objects.create(
        company=company, fournisseur=fournisseur,
        reference=f'BCF-NTPRT22-{next(_seq)}',
        statut=statut,
        date_commande=datetime.date(2026, 5, 1),
        date_livraison_prevue=date_prevue)
    LigneBonCommandeFournisseur.objects.create(
        bon_commande=bc, produit=produit, quantite=10,
        prix_achat_unitaire=PRIX_ACHAT_SECRET)
    LigneBonCommandeFournisseur.objects.create(
        bon_commande=bc, designation='Transport Casablanca', sans_stock=True,
        quantite=1)
    return bc


class AnnoncerLivraisonTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt22-co', 'NTPRT22 Société')
        self.fournisseur = make_fournisseur(self.company, 'Alpha')
        self.produit = make_produit(
            self.company, 'Onduleur NTPRT22', 'OND-NTPRT22')
        self.bcf = make_bcf(self.company, self.fournisseur, self.produit)

    def _annoncer(self, **kwargs):
        params = {
            'date_expedition': datetime.date(2026, 5, 12),
            'date_livraison_prevue': datetime.date(2026, 5, 18),
            'transporteur': 'Transit Atlas',
            'numero_suivi': 'TA-889001',
            'lignes': [{'produit_id': self.produit.id, 'quantite': 6}],
        }
        params.update(kwargs)
        return annoncer_livraison_fournisseur(
            self.company, self.fournisseur.id, self.bcf.id, **params)

    def test_une_annonce_est_creee_avec_ses_lignes_normalisees(self):
        annonce, erreurs = self._annoncer()

        self.assertIsNone(erreurs)
        self.assertEqual(
            annonce.statut, AnnonceLivraisonFournisseur.Statut.ANNONCEE)
        self.assertEqual(annonce.company_id, self.company.id)
        self.assertEqual(annonce.bon_commande_fournisseur_id, self.bcf.id)
        self.assertEqual(annonce.transporteur, 'Transit Atlas')
        self.assertEqual(annonce.numero_suivi, 'TA-889001')
        self.assertEqual(annonce.date_expedition, datetime.date(2026, 5, 12))
        self.assertEqual(
            annonce.lignes,
            [{'produit_id': self.produit.id,
              'produit_nom': 'Onduleur NTPRT22',
              'quantite': '6'}])

    def test_une_ligne_libre_est_annoncable_par_sa_designation(self):
        annonce, erreurs = self._annoncer(
            lignes=[{'designation': 'Transport Casablanca', 'quantite': 1}])

        self.assertIsNone(erreurs)
        self.assertEqual(annonce.lignes, [
            {'produit_id': None, 'produit_nom': 'Transport Casablanca',
             'quantite': '1'}])

    def test_aucun_mouvement_de_stock_ni_reception(self):
        """Une annonce est une DÉCLARATION, jamais une entrée en stock."""
        stock_avant = Produit.objects.get(pk=self.produit.pk).quantite_stock
        mouvements_avant = MouvementStock.objects.filter(
            produit=self.produit).count()
        receptions_avant = ReceptionFournisseur.objects.filter(
            bon_commande=self.bcf).count()

        self._annoncer()

        self.assertEqual(
            Produit.objects.get(pk=self.produit.pk).quantite_stock,
            stock_avant)
        self.assertEqual(
            MouvementStock.objects.filter(produit=self.produit).count(),
            mouvements_avant)
        self.assertEqual(
            ReceptionFournisseur.objects.filter(
                bon_commande=self.bcf).count(),
            receptions_avant)
        ligne = self.bcf.lignes.filter(produit=self.produit).first()
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 0)

    def test_la_date_demandee_du_bcf_n_est_jamais_ecrasee(self):
        """La date déclarée par le fournisseur vit sur l'ANNONCE ; celle du
        bon de commande reste la date DEMANDÉE — c'est elle qui rend l'OTD
        promis-vs-reçu mesurable (XPUR7)."""
        self._annoncer(date_livraison_prevue=datetime.date(2026, 6, 30))

        self.bcf.refresh_from_db()
        self.assertEqual(
            self.bcf.date_livraison_prevue, datetime.date(2026, 5, 20))

    def test_un_article_hors_du_bon_de_commande_est_refuse(self):
        etranger = make_produit(self.company, 'Batterie hors BCF', 'BAT-X22')
        annonce, erreurs = self._annoncer(
            lignes=[{'produit_id': etranger.id, 'quantite': 2}])

        self.assertIsNone(annonce)
        self.assertIn('lignes', erreurs)
        self.assertEqual(AnnonceLivraisonFournisseur.objects.count(), 0)

    def test_une_quantite_nulle_ou_negative_est_refusee(self):
        for quantite in (0, -3):
            annonce, erreurs = self._annoncer(
                lignes=[{'produit_id': self.produit.id,
                         'quantite': quantite}])
            self.assertIsNone(annonce, quantite)
            self.assertIn('lignes', erreurs)
        self.assertEqual(AnnonceLivraisonFournisseur.objects.count(), 0)

    def test_une_quantite_illisible_est_refusee(self):
        annonce, erreurs = self._annoncer(
            lignes=[{'produit_id': self.produit.id, 'quantite': 'six'}])
        self.assertIsNone(annonce)
        self.assertIn('lignes', erreurs)

    def test_une_annonce_sans_ligne_reste_possible(self):
        """« C'est parti, voici le numéro de suivi » est déjà une information
        utile : on ne refuse pas une annonce dont le détail suivra."""
        annonce, erreurs = self._annoncer(lignes=[])
        self.assertIsNone(erreurs)
        self.assertEqual(annonce.lignes, [])


class IsolationAnnonceLivraisonTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt22-iso-co', 'NTPRT22 Isolation')
        self.autre_company = make_company('ntprt22-iso-co2', 'NTPRT22 Iso 2')
        self.f_a = make_fournisseur(self.company, 'Alpha')
        self.f_b = make_fournisseur(self.company, 'Beta')
        self.f_etranger = make_fournisseur(self.autre_company, 'Gamma')

        self.produit = make_produit(
            self.company, 'Onduleur ISO22', 'OND-ISO22')
        self.produit_etranger = make_produit(
            self.autre_company, 'Onduleur ISO22b', 'OND-ISO22B')

        self.bcf_a = make_bcf(self.company, self.f_a, self.produit)
        self.bcf_b = make_bcf(self.company, self.f_b, self.produit)
        self.bcf_etranger = make_bcf(
            self.autre_company, self.f_etranger, self.produit_etranger)

    def test_le_bcf_d_un_autre_fournisseur_est_introuvable(self):
        with self.assertRaises(ValueError):
            annoncer_livraison_fournisseur(
                self.company, self.f_a.id, self.bcf_b.id, lignes=[])
        self.assertEqual(AnnonceLivraisonFournisseur.objects.count(), 0)

    def test_le_bcf_d_une_autre_societe_est_introuvable(self):
        with self.assertRaises(ValueError):
            annoncer_livraison_fournisseur(
                self.company, self.f_etranger.id, self.bcf_etranger.id,
                lignes=[])
        self.assertEqual(AnnonceLivraisonFournisseur.objects.count(), 0)

    def test_un_brouillon_ou_un_annule_n_accepte_aucune_annonce(self):
        for statut in (BonCommandeFournisseur.Statut.BROUILLON,
                       BonCommandeFournisseur.Statut.ANNULE):
            bcf = make_bcf(self.company, self.f_a, self.produit,
                           statut=statut)
            with self.assertRaises(ValueError, msg=statut):
                annoncer_livraison_fournisseur(
                    self.company, self.f_a.id, bcf.id, lignes=[])

    def test_le_selecteur_portail_ne_rend_que_ses_annonces(self):
        annonce_a, _ = annoncer_livraison_fournisseur(
            self.company, self.f_a.id, self.bcf_a.id, lignes=[])
        annonce_b, _ = annoncer_livraison_fournisseur(
            self.company, self.f_b.id, self.bcf_b.id, lignes=[])

        ids_a = [ligne['id'] for ligne in
                 annonces_livraison_portail_fournisseur(
                     self.company, self.f_a.id)]
        self.assertEqual(ids_a, [annonce_a.id])
        self.assertNotIn(annonce_b.id, ids_a)

        # Sans rattachement : vide, jamais les annonces de la société entière.
        self.assertEqual(
            annonces_livraison_portail_fournisseur(self.company, None), [])
        self.assertEqual(
            annonces_livraison_portail_fournisseur(
                self.company, self.f_etranger.id), [])


class StatutAnnonceLivraisonTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt22-st-co', 'NTPRT22 Statut')
        self.f_a = make_fournisseur(self.company, 'Alpha')
        self.f_b = make_fournisseur(self.company, 'Beta')
        self.produit = make_produit(self.company, 'Onduleur ST22', 'OND-ST22')
        self.bcf = make_bcf(self.company, self.f_a, self.produit)
        self.annonce, _ = annoncer_livraison_fournisseur(
            self.company, self.f_a.id, self.bcf.id, lignes=[])

    def test_le_statut_avance(self):
        annonce, erreurs = mettre_a_jour_statut_annonce_livraison(
            self.company, self.f_a.id, self.annonce.id, statut='en_transit')
        self.assertIsNone(erreurs)
        self.assertEqual(annonce.statut, 'en_transit')

        annonce, erreurs = mettre_a_jour_statut_annonce_livraison(
            self.company, self.f_a.id, self.annonce.id, statut='livree')
        self.assertIsNone(erreurs)
        self.assertEqual(annonce.statut, 'livree')

    def test_le_statut_ne_recule_jamais(self):
        mettre_a_jour_statut_annonce_livraison(
            self.company, self.f_a.id, self.annonce.id, statut='livree')
        annonce, erreurs = mettre_a_jour_statut_annonce_livraison(
            self.company, self.f_a.id, self.annonce.id, statut='annoncee')

        self.assertIsNone(annonce)
        self.assertIn('statut', erreurs)
        self.annonce.refresh_from_db()
        self.assertEqual(self.annonce.statut, 'livree')

    def test_un_statut_inconnu_est_refuse(self):
        annonce, erreurs = mettre_a_jour_statut_annonce_livraison(
            self.company, self.f_a.id, self.annonce.id, statut='perdue')
        self.assertIsNone(annonce)
        self.assertIn('statut', erreurs)

    def test_l_annonce_d_un_autre_fournisseur_est_introuvable(self):
        with self.assertRaises(ValueError):
            mettre_a_jour_statut_annonce_livraison(
                self.company, self.f_b.id, self.annonce.id,
                statut='en_transit')

    def test_declarer_livree_ne_touche_aucun_stock(self):
        avant = Produit.objects.get(pk=self.produit.pk).quantite_stock
        mettre_a_jour_statut_annonce_livraison(
            self.company, self.f_a.id, self.annonce.id, statut='livree')
        self.assertEqual(
            Produit.objects.get(pk=self.produit.pk).quantite_stock, avant)
        self.assertEqual(
            ReceptionFournisseur.objects.filter(
                bon_commande=self.bcf).count(), 0)

    def test_le_resume_portail_compte_les_livraisons_attendues(self):
        attendu = (AnnonceLivraisonFournisseur.objects
                   .filter(company=self.company,
                           bon_commande_fournisseur__fournisseur=self.f_a)
                   .exclude(statut='livree').count())
        resume = resume_portail_fournisseur(self.company, self.f_a.id)
        self.assertEqual(resume['livraisons_annoncees'], attendu)

        mettre_a_jour_statut_annonce_livraison(
            self.company, self.f_a.id, self.annonce.id, statut='livree')
        resume = resume_portail_fournisseur(self.company, self.f_a.id)
        self.assertEqual(resume['livraisons_annoncees'], attendu - 1)

    def test_un_fournisseur_sans_rattachement_voit_zero(self):
        resume = resume_portail_fournisseur(self.company, None)
        self.assertEqual(resume['livraisons_annoncees'], 0)


class AnnonceVisibleCoteInterneTests(TestCase):
    """Le critère d'acceptation : « sans action manuelle »."""

    def setUp(self):
        self.company = make_company('ntprt22-int-co', 'NTPRT22 Interne')
        self.fournisseur = make_fournisseur(self.company, 'Alpha')
        self.produit = make_produit(self.company, 'Onduleur IN22', 'OND-IN22')
        self.bcf = make_bcf(self.company, self.fournisseur, self.produit)
        self.api = APIClient()
        self.api.force_authenticate(user=make_interne(
            self.company, 'ntprt22-interne'))

    def test_une_annonce_portail_apparait_au_prochain_get_interne(self):
        avant = self.api.get(f'{URL_BCF}{self.bcf.id}/')
        self.assertEqual(avant.status_code, 200, avant.data)
        self.assertEqual(avant.data['livraisons_annoncees'], [])

        annoncer_livraison_fournisseur(
            self.company, self.fournisseur.id, self.bcf.id,
            date_expedition=datetime.date(2026, 5, 12),
            date_livraison_prevue=datetime.date(2026, 5, 18),
            transporteur='Transit Atlas', numero_suivi='TA-889002',
            lignes=[{'produit_id': self.produit.id, 'quantite': 6}])

        apres = self.api.get(f'{URL_BCF}{self.bcf.id}/')
        self.assertEqual(apres.status_code, 200, apres.data)
        annoncees = apres.data['livraisons_annoncees']
        self.assertEqual(len(annoncees), 1)
        self.assertEqual(annoncees[0]['transporteur'], 'Transit Atlas')
        self.assertEqual(annoncees[0]['numero_suivi'], 'TA-889002')
        self.assertEqual(annoncees[0]['statut'], 'annoncee')
        self.assertEqual(annoncees[0]['bon_commande_reference'],
                         self.bcf.reference)
        self.assertEqual(
            annoncees[0]['lignes'][0]['produit_id'], self.produit.id)

    def test_la_liste_interne_porte_la_meme_charge_utile(self):
        annoncer_livraison_fournisseur(
            self.company, self.fournisseur.id, self.bcf.id,
            transporteur='Transit Atlas', lignes=[])

        res = self.api.get(URL_BCF)
        self.assertEqual(res.status_code, 200, res.data)
        ligne = next(r for r in res.data['results'] if r['id'] == self.bcf.id)
        self.assertEqual(
            ligne['livraisons_annoncees'],
            annonces_livraison_bon_commande(self.bcf))

    def test_le_champ_est_en_lecture_seule_sur_le_document_interne(self):
        """Une annonce se dépose au PORTAIL : un PATCH interne ne l'invente
        jamais (le champ est calculé, il n'est pas écrit)."""
        res = self.api.patch(
            f'{URL_BCF}{self.bcf.id}/',
            {'livraisons_annoncees': [{'transporteur': 'Faux'}]},
            format='json')
        self.assertIn(res.status_code, (200, 400), res.data)
        self.assertEqual(
            AnnonceLivraisonFournisseur.objects.filter(
                bon_commande_fournisseur=self.bcf).count(), 0)

    def test_aucun_prix_d_achat_dans_la_charge_utile_de_l_annonce(self):
        annoncer_livraison_fournisseur(
            self.company, self.fournisseur.id, self.bcf.id,
            lignes=[{'produit_id': self.produit.id, 'quantite': 6}])

        charge = str(annonces_livraison_bon_commande(self.bcf))
        self.assertNotIn(PRIX_ACHAT_SECRET, charge)
        self.assertNotIn(PRIX_ACHAT_SECRET.split('.')[0], charge)
        for interdit in ('prix_achat', 'prix_achat_unitaire', 'marge'):
            self.assertNotIn(interdit, charge)
