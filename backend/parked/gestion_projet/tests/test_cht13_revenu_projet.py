"""CHT13 — P&L projet : brancher le VRAI revenu.

``_revenu_projet_cross_app`` (consommé par ``pnl_projet``) et le court-circuit
revenu=0 de ``tableau_portefeuille`` renvoyaient TOUJOURS ``Decimal('0')`` —
« aucune app cible n'expose de sélecteur de montant par projet ». CHT12 a
comblé ce trou (``ventes.selectors.montants_devis``/``montants_factures_
par_devis`` + ``installations.selectors.devis_id_du_chantier``) : cette tâche
branche le revenu RÉEL, cohérent avec FG295
(``installations.selectors.projet_pnl``) — le revenu est le CA FACTURÉ
(Σ factures HT), jamais le total d'un devis simplement accepté.

Deux chemins de résolution devis, jamais un import de ``ventes``/
``installations`` ``models`` hors des tests (frontière cross-app,
CLAUDE.md) :
  * ``ProjetLien`` type ``devis`` → ``cible_id`` EST le devis_id (chemin
    UNIQUE de ``creer_projet_depuis_devis``, XPRJ21, à ce jour) ;
  * ``ProjetChantier.chantier_id`` → devis via
    ``installations.selectors.devis_id_du_chantier`` — couvert par
    ``_revenu_projet_cross_app``/``pnl_projet`` (par-projet) ET, depuis le
    correctif du trou documenté par CHT13/CHT14, par ``tableau_portefeuille``
    vectorisé via le sélecteur BATCH ``installations.selectors.
    devis_ids_des_chantiers`` (jumeau de ``devis_id_du_chantier`` — UNE
    requête pour tous les chantiers de tous les projets filtrés, jamais une
    boucle par chantier, donc sans réintroduire le N+1 qu'AUDV16 a éliminé).

Couvre : revenu réel par devis+factures (ProjetLien) ; revenu réel par
chantier rattaché (ProjetChantier, sans ProjetLien) ; étanchéité société sur
les deux chemins ; projet sans lien → 0 inchangé (non-régression) ; un projet
rattaché SEULEMENT par ``ProjetChantier`` affiche dans le portefeuille le
MÊME revenu que ``pnl_projet`` (plus de divergence portefeuille/pnl_projet) ;
un devis rattaché par les DEUX chemins n'est compté qu'une fois ; portefeuille
vectorisé = somme des projets avec nombre de requêtes FIXE indépendant de N
(scaling incluant des projets rattachés par chantier seul) ; contrat partagé
(PACT10) — la forme RÉELLE de l'action ``portefeuille`` égale l'exemple
committé dans ``contract_samples/tableau_portefeuille.json`` (le même fichier
que le test frontend importe).

Run :
    docker compose exec django_core python manage.py test \
        apps.gestion_projet.tests.test_cht13_revenu_projet -v 2
"""
import itertools
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.gestion_projet import selectors
from apps.gestion_projet.models import Projet, ProjetChantier, ProjetLien
from apps.installations.models import Installation
from apps.ventes.models import Devis, Facture

User = get_user_model()

_seq = itertools.count(1)

# PACT10 — l'exemple de réponse committé, porteur du contrat front <-> back.
ECHANTILLON = (
    Path(__file__).resolve().parent.parent
    / 'contract_samples' / 'tableau_portefeuille.json')


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'cht13-co-{n}', defaults={'nom': nom or f'CHT13 Co {n}'})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_client_obj(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='CHT13',
        email=f'cht13-{company.id}-{n}@example.invalid')


def make_devis(company, client):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-CHT13-{n}', client=client,
        statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))


def make_facture(company, client, devis, *, montant_ht, montant_ttc,
                 statut=Facture.Statut.EMISE):
    n = next(_seq)
    return Facture.objects.create(
        company=company, reference=f'FAC-CHT13-{n}', client=client,
        devis=devis, statut=statut, taux_tva=Decimal('20'),
        montant_ht=Decimal(str(montant_ht)),
        montant_ttc=Decimal(str(montant_ttc)))


def make_chantier(company, devis=None):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CH-CHT13-{n}', devis=devis)


class RevenuProjetCrossAppTests(TestCase):
    """``_revenu_projet_cross_app`` (consommé par ``pnl_projet``)."""

    def setUp(self):
        self.co = make_company()
        self.client_obj = make_client_obj(self.co)
        self.projet = Projet.objects.create(
            company=self.co, code='P-CHT13', nom='Projet CHT13')

    def test_sans_lien_revenu_zero_inchange(self):
        """Non-régression : aucun lien → revenu 0 + note, comme avant CHT13."""
        data = selectors.pnl_projet(self.co, self.projet)
        self.assertEqual(data['revenu'], Decimal('0'))
        self.assertIn('Aucun devis/facture rattaché', data['note_revenu'])

    def test_revenu_via_projet_lien_devis_et_factures(self):
        """Devis rattaché par ``ProjetLien`` + factures émises → revenu réel
        = Σ factures HT (cohérent FG295), jamais le total du devis."""
        devis = make_devis(self.co, self.client_obj)
        ProjetLien.objects.create(
            company=self.co, projet=self.projet,
            type_cible=ProjetLien.TypeCible.DEVIS, cible_id=devis.id)
        make_facture(
            self.co, self.client_obj, devis, montant_ht=1000, montant_ttc=1200)
        make_facture(
            self.co, self.client_obj, devis, montant_ht=500, montant_ttc=600)
        data = selectors.pnl_projet(self.co, self.projet)
        self.assertEqual(data['revenu'], Decimal('1500'))
        self.assertIn('Revenu réel', data['note_revenu'])

    def test_devis_accepte_sans_facture_ne_compte_pas(self):
        """Un devis rattaché mais JAMAIS facturé reste à 0 (cohérent FG295 —
        un devis accepté n'est pas un revenu tant que rien n'est facturé)."""
        devis = make_devis(self.co, self.client_obj)
        ProjetLien.objects.create(
            company=self.co, projet=self.projet,
            type_cible=ProjetLien.TypeCible.DEVIS, cible_id=devis.id)
        data = selectors.pnl_projet(self.co, self.projet)
        self.assertEqual(data['revenu'], Decimal('0'))
        self.assertIn('aucune facture émise', data['note_revenu'])

    def test_facture_annulee_exclue(self):
        devis = make_devis(self.co, self.client_obj)
        ProjetLien.objects.create(
            company=self.co, projet=self.projet,
            type_cible=ProjetLien.TypeCible.DEVIS, cible_id=devis.id)
        make_facture(
            self.co, self.client_obj, devis, montant_ht=1000, montant_ttc=1200)
        make_facture(
            self.co, self.client_obj, devis, montant_ht=700, montant_ttc=840,
            statut=Facture.Statut.ANNULEE)
        data = selectors.pnl_projet(self.co, self.projet)
        self.assertEqual(data['revenu'], Decimal('1000'))

    def test_revenu_via_chantier_rattache_sans_projet_lien(self):
        """``ProjetChantier`` (rattachement manuel, SANS ``ProjetLien``) →
        devis résolu via ``devis_id_du_chantier`` → revenu réel."""
        devis = make_devis(self.co, self.client_obj)
        chantier = make_chantier(self.co, devis=devis)
        ProjetChantier.objects.create(
            company=self.co, projet=self.projet, chantier_id=chantier.id)
        make_facture(
            self.co, self.client_obj, devis, montant_ht=800, montant_ttc=960)
        data = selectors.pnl_projet(self.co, self.projet)
        self.assertEqual(data['revenu'], Decimal('800'))

    def test_chantier_cross_tenant_etanche(self):
        """Un ``chantier_id`` d'une AUTRE société ne résout à rien (0)."""
        autre = make_company()
        autre_client = make_client_obj(autre)
        autre_devis = make_devis(autre, autre_client)
        autre_chantier = make_chantier(autre, devis=autre_devis)
        make_facture(
            autre, autre_client, autre_devis,
            montant_ht=999, montant_ttc=1198.80)
        # Un utilisateur de `self.co` réussit à poser un ProjetChantier
        # pointant l'id d'un chantier de l'AUTRE société (CHT1 protège la
        # création API, pas cette lecture directe en base) : le sélecteur doit
        # rester étanche et dégrader à 0.
        ProjetChantier.objects.create(
            company=self.co, projet=self.projet, chantier_id=autre_chantier.id)
        data = selectors.pnl_projet(self.co, self.projet)
        self.assertEqual(data['revenu'], Decimal('0'))

    def test_devis_cross_tenant_via_projet_lien_etanche(self):
        """Un ``cible_id`` de devis d'une autre société ne résout à rien."""
        autre = make_company()
        autre_client = make_client_obj(autre)
        autre_devis = make_devis(autre, autre_client)
        make_facture(
            autre, autre_client, autre_devis,
            montant_ht=999, montant_ttc=1198.80)
        ProjetLien.objects.create(
            company=self.co, projet=self.projet,
            type_cible=ProjetLien.TypeCible.DEVIS, cible_id=autre_devis.id)
        data = selectors.pnl_projet(self.co, self.projet)
        self.assertEqual(data['revenu'], Decimal('0'))

    def test_lien_facture_sans_devis_resolvable_reste_degrade(self):
        """Non-régression exacte de ``test_note_revenu_avec_liens``
        (test_pnl.py) : un ``ProjetLien`` type ``facture`` (TypeCible partagé
        avec les dépenses fournisseur, jamais créé côté revenu client
        aujourd'hui) n'a pas de chemin de résolution → revenu 0 + note."""
        ProjetLien.objects.create(
            company=self.co, projet=self.projet,
            type_cible=ProjetLien.TypeCible.FACTURE, cible_id=7)
        data = selectors.pnl_projet(self.co, self.projet)
        self.assertEqual(data['revenu'], Decimal('0'))
        self.assertIn('facture', data['note_revenu'])


class TableauPortefeuilleRevenuTests(TestCase):
    """``tableau_portefeuille`` — court-circuit revenu=0 mis à jour."""

    def setUp(self):
        self.co = make_company()
        self.client_obj = make_client_obj(self.co)

    def test_marge_reelle_utilise_le_revenu_facture(self):
        projet = Projet.objects.create(
            company=self.co, code='P-PORT', nom='Projet portefeuille')
        devis = make_devis(self.co, self.client_obj)
        ProjetLien.objects.create(
            company=self.co, projet=projet,
            type_cible=ProjetLien.TypeCible.DEVIS, cible_id=devis.id)
        make_facture(
            self.co, self.client_obj, devis, montant_ht=2000, montant_ttc=2400)
        data = selectors.tableau_portefeuille(self.co)
        ligne = data['projets'][0]
        # Aucun coût engagé dans ce fixture → marge réelle = revenu.
        self.assertEqual(ligne['marge_reelle'], Decimal('2000'))
        self.assertEqual(data['total_marge_reelle'], Decimal('2000'))

    def test_portefeuille_marge_totale_est_la_somme_des_projets(self):
        p1 = Projet.objects.create(company=self.co, code='P-A', nom='A')
        devis1 = make_devis(self.co, self.client_obj)
        ProjetLien.objects.create(
            company=self.co, projet=p1,
            type_cible=ProjetLien.TypeCible.DEVIS, cible_id=devis1.id)
        make_facture(
            self.co, self.client_obj, devis1, montant_ht=1000, montant_ttc=1200)

        p2 = Projet.objects.create(company=self.co, code='P-B', nom='B')
        devis2 = make_devis(self.co, self.client_obj)
        ProjetLien.objects.create(
            company=self.co, projet=p2,
            type_cible=ProjetLien.TypeCible.DEVIS, cible_id=devis2.id)
        make_facture(
            self.co, self.client_obj, devis2, montant_ht=300, montant_ttc=360)

        data = selectors.tableau_portefeuille(self.co)
        somme = sum(
            (ligne['marge_reelle'] for ligne in data['projets']), Decimal('0'))
        self.assertEqual(data['total_marge_reelle'], somme)
        self.assertEqual(somme, Decimal('1300'))

    def test_projet_sans_lien_reste_a_zero(self):
        Projet.objects.create(company=self.co, code='P-VIDE', nom='Vide')
        data = selectors.tableau_portefeuille(self.co)
        self.assertEqual(data['projets'][0]['marge_reelle'], Decimal('0'))

    def test_projet_rattache_uniquement_par_chantier_meme_revenu_que_pnl(
            self):
        """CHT13/CHT14 — un projet rattaché SEULEMENT par ``ProjetChantier``
        (sans ``ProjetLien``) doit afficher dans le portefeuille EXACTEMENT
        le même revenu que ``pnl_projet`` (par-projet) : avant le correctif,
        le portefeuille vectorisé ne résolvait pas ce chemin et affichait 0
        pendant que ``pnl_projet`` affichait le vrai revenu — la divergence
        que CHT13 interdit."""
        projet = Projet.objects.create(
            company=self.co, code='P-CHANTIER-SEUL', nom='Chantier seul')
        devis = make_devis(self.co, self.client_obj)
        chantier = make_chantier(self.co, devis=devis)
        ProjetChantier.objects.create(
            company=self.co, projet=projet, chantier_id=chantier.id)
        make_facture(
            self.co, self.client_obj, devis, montant_ht=900, montant_ttc=1080)

        pnl = selectors.pnl_projet(self.co, projet)
        data = selectors.tableau_portefeuille(self.co)
        ligne = next(
            row for row in data['projets'] if row['projet_id'] == projet.id)

        self.assertEqual(pnl['revenu'], Decimal('900'))
        self.assertEqual(ligne['marge_reelle'], pnl['marge_reelle'])
        self.assertEqual(ligne['marge_reelle'], Decimal('900'))

    def test_devis_rattache_par_les_deux_chemins_compte_une_fois(self):
        """Un devis rattaché à la fois par ``ProjetLien`` ET par
        ``ProjetChantier`` (même devis) ne doit être compté qu'UNE fois dans
        le revenu portefeuille — jamais doublé."""
        projet = Projet.objects.create(
            company=self.co, code='P-DEUX-CHEMINS', nom='Deux chemins')
        devis = make_devis(self.co, self.client_obj)
        ProjetLien.objects.create(
            company=self.co, projet=projet,
            type_cible=ProjetLien.TypeCible.DEVIS, cible_id=devis.id)
        chantier = make_chantier(self.co, devis=devis)
        ProjetChantier.objects.create(
            company=self.co, projet=projet, chantier_id=chantier.id)
        make_facture(
            self.co, self.client_obj, devis, montant_ht=400, montant_ttc=480)

        data = selectors.tableau_portefeuille(self.co)
        ligne = next(
            row for row in data['projets'] if row['projet_id'] == projet.id)
        self.assertEqual(ligne['marge_reelle'], Decimal('400'))

    def test_devis_cross_tenant_jamais_agrege(self):
        autre = make_company()
        autre_client = make_client_obj(autre)
        autre_devis = make_devis(autre, autre_client)
        make_facture(
            autre, autre_client, autre_devis,
            montant_ht=5000, montant_ttc=6000)
        projet = Projet.objects.create(
            company=self.co, code='P-SCOPE', nom='Scope')
        # Le devis d'une AUTRE société, même référencé, ne doit jamais entrer
        # dans le calcul (montants_factures_par_devis scope déjà par company,
        # mais on vérifie ici l'intégration bout en bout).
        ProjetLien.objects.create(
            company=self.co, projet=projet,
            type_cible=ProjetLien.TypeCible.DEVIS, cible_id=autre_devis.id)
        data = selectors.tableau_portefeuille(self.co)
        self.assertEqual(data['projets'][0]['marge_reelle'], Decimal('0'))

    def test_nombre_de_requetes_reste_fixe_avec_devis_factures(self):
        """CHT13/CHT14 — les requêtes groupées ajoutées (``ProjetLien``,
        ``ProjetChantier``, ``devis_ids_des_chantiers`` puis
        ``montants_factures_par_devis`` en BATCH) restent FIXES, comme le
        reste de la vectorisation AUDV16 : même compte pour 2 et pour 6
        projets facturés (jamais une requête par projet) — le scaling
        alterne projets rattachés par ``ProjetLien`` et par ``ProjetChantier``
        seul pour exercer les DEUX chemins."""
        def peupler(nb):
            for i in range(nb):
                projet = Projet.objects.create(
                    company=self.co, code=f'P-{next(_seq)}', nom='Projet')
                devis = make_devis(self.co, self.client_obj)
                if i % 2 == 0:
                    ProjetLien.objects.create(
                        company=self.co, projet=projet,
                        type_cible=ProjetLien.TypeCible.DEVIS,
                        cible_id=devis.id)
                else:
                    chantier = make_chantier(self.co, devis=devis)
                    ProjetChantier.objects.create(
                        company=self.co, projet=projet,
                        chantier_id=chantier.id)
                make_facture(
                    self.co, self.client_obj, devis,
                    montant_ht=100, montant_ttc=120)

        peupler(2)
        with CaptureQueriesContext(connection) as ctx2:
            portefeuille2 = selectors.tableau_portefeuille(self.co)

        peupler(4)
        with CaptureQueriesContext(connection) as ctx6:
            portefeuille6 = selectors.tableau_portefeuille(self.co)

        self.assertEqual(portefeuille2['nb_projets'], 2)
        self.assertEqual(portefeuille6['nb_projets'], 6)
        self.assertEqual(
            len(ctx2), len(ctx6),
            f'N+1 revenu : {len(ctx2)} requêtes pour 2 projets facturés, '
            f'{len(ctx6)} pour 6.')


class ContratTableauPortefeuilleTests(TestCase):
    """PACT10 — l'exemple committé porte le VRAI contrat de l'action
    ``portefeuille`` (forme RÉSEAU, pas le dict brut du sélecteur — voir
    ``pourquoi`` du fichier de contrat)."""

    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co, 'cht13-contrat')
        self.client_obj = make_client_obj(self.co)

    def test_forme_reponse_egale_exemple_committe(self):
        projet = Projet.objects.create(
            company=self.co, code='P-CONTRAT', nom='Contrat')
        devis = make_devis(self.co, self.client_obj)
        ProjetLien.objects.create(
            company=self.co, projet=projet,
            type_cible=ProjetLien.TypeCible.DEVIS, cible_id=devis.id)
        make_facture(
            self.co, self.client_obj, devis, montant_ht=100, montant_ttc=120)

        contrat = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
        exemple = contrat['exemple']

        api = auth(self.user)
        resp = api.get('/api/django/gestion-projet/projets/portefeuille/')
        self.assertEqual(resp.status_code, 200)

        # Comparaison par FORME (les clés) — patron test_emprunts.py /
        # test_cht16_indemnite_chantier_installation.py.
        self.assertEqual(sorted(exemple), sorted(resp.data))
        self.assertEqual(
            sorted(exemple['projets'][0]), sorted(resp.data['projets'][0]))
