"""NTCPQ20 — Historique fin des configurations d'un devis brouillon.

QJR550 — l'instantané est pris UNE fois par GESTE d'enregistrement, avec son
auteur, par le pipeline / ``LigneDevisViewSet`` / la resynchronisation
catalogue — plus par un signal ``post_save`` par ligne (qui produisait ~N+1
instantanés partiels sans auteur à chaque replace-lines). Une erreur SQL
pendant la capture n'avorte plus l'enregistrement (point de sauvegarde).
"""
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import ConfigurationDevisSnapshot, Devis, LigneDevis
from apps.ventes.services import (
    capturer_configuration_devis, diff_configurations_devis,
)
from authentication.models import CustomUser
from testkit.factories import (
    ClientFactory, CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.produit = ProduitFactory(company=self.company)
        self.devis = DevisFactory(company=self.company)
        self.api = auth(self.user)

    def _snaps(self):
        return ConfigurationDevisSnapshot.objects.filter(
            devis=self.devis).order_by('id')

    def _ligne(self, qte='1', prix='100.00'):
        """Écriture DIRECTE (hors geste) : aucun instantané depuis QJR550."""
        return LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal(qte),
            prix_unitaire=Decimal(prix))

    def _ajouter(self, qte='1', prix='100.00'):
        resp = self.api.post('/api/django/ventes/devis-lignes/', {
            'devis': self.devis.id, 'produit': self.produit.id,
            'designation': self.produit.nom, 'quantite': qte,
            'prix_unitaire': prix}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return LigneDevis.objects.get(pk=resp.data['id'])

    def _modifier(self, ligne, **champs):
        resp = self.api.patch(f'/api/django/ventes/devis-lignes/{ligne.id}/',
                              champs, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def _retirer(self, ligne):
        resp = self.api.delete(f'/api/django/ventes/devis-lignes/{ligne.id}/')
        self.assertEqual(resp.status_code, 204)

    def _lignes_corps(self, n, prix='100.00'):
        return [{'produit': self.produit.id, 'designation': f'{self.produit.nom}',
                 'quantite': '1', 'prix_unitaire': prix} for _ in range(n)]


class TestConfigurationSnapshot(_Base):

    def test_cinq_reconfigurations_produisent_cinq_etats(self):
        ligne = self._ajouter()                     # 1 — ajout
        self._modifier(ligne, quantite='2')         # 2 — quantité
        self._modifier(ligne, quantite='3')         # 3 — quantité
        autre = self._ajouter(qte='4')              # 4 — ajout
        self._retirer(autre)                        # 5 — retrait
        snaps = self._snaps()
        self.assertEqual(snaps.count(), 5)
        quantites = [s.contenu['lignes'][0]['quantite'] for s in snaps]
        self.assertEqual(quantites[:3], ['1.00', '2.00', '3.00'])
        self.assertTrue(all(s.auteur_id == self.user.id for s in snaps))

    def test_pas_dinstantane_hors_brouillon(self):
        self.devis.statut = Devis.Statut.ENVOYE
        self.devis.save(update_fields=['statut'])
        self.devis.refresh_from_db()
        self._ligne()
        self.assertEqual(self._snaps().count(), 0)

    def test_une_ecriture_directe_de_ligne_ne_prend_plus_d_instantane(self):
        """QJR550 — ROUGE AVANT : le signal post_save en prenait un."""
        self._ligne()
        self.assertEqual(self._snaps().count(), 0)

    def test_contenu_identique_ne_cree_pas_de_doublon(self):
        ligne = self._ajouter()
        avant = ConfigurationDevisSnapshot.objects.count()
        self._modifier(ligne, quantite='1')  # aucun changement réel
        self.assertEqual(ConfigurationDevisSnapshot.objects.count(), avant)

    def test_aucune_donnee_de_marge_dans_le_contenu(self):
        self._ajouter()
        snap = ConfigurationDevisSnapshot.objects.get(devis=self.devis)
        blob = str(snap.contenu)
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('marge', blob)

    def test_capture_explicite_porte_lauteur(self):
        ligne = self._ligne()
        premier = capturer_configuration_devis(self.devis, user=self.user)
        self.assertIsNotNone(premier)
        # Contenu identique au dernier instantané → aucun doublon.
        self.assertIsNone(
            capturer_configuration_devis(self.devis, user=self.user))
        LigneDevis.objects.filter(id=ligne.id).update(quantite=Decimal('8'))
        snap = capturer_configuration_devis(self.devis, user=self.user)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.auteur_id, self.user.id)
        self.assertEqual(snap.company_id, self.company.id)

    def test_diff_entre_deux_instantanes(self):
        ligne = self._ajouter()
        premier = self._snaps().first()
        self._modifier(ligne, quantite='7')
        ajoutee = self._ajouter(qte='2', prix='50.00')
        dernier = self._snaps().last()
        diff = diff_configurations_devis(premier, dernier)
        self.assertEqual([li['ligne_id'] for li in diff['ajoutees']],
                         [ajoutee.id])
        self.assertEqual(diff['retirees'], [])
        self.assertEqual(diff['modifiees'][0]['ligne_id'], ligne.id)
        self.assertEqual(diff['modifiees'][0]['champs']['quantite'],
                         ['1.00', '7.00'])

    def test_endpoint_historique_et_diff(self):
        ligne = self._ajouter()
        self._modifier(ligne, quantite='5')
        snaps = list(self._snaps())
        url = (f'/api/django/ventes/devis/{self.devis.id}/'
               'historique-configuration/')
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['snapshots']), 2)
        self.assertNotIn('diff', resp.data)
        resp = self.api.get(f'{url}?a={snaps[0].id}&b={snaps[1].id}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['diff']['modifiees'][0]['champs']
                         ['quantite'], ['1.00', '5.00'])

    def test_endpoint_isole_les_societes(self):
        autre = DevisFactory(company=CompanyFactory())
        resp = auth(self.user).get(
            f'/api/django/ventes/devis/{autre.id}/historique-configuration/')
        self.assertEqual(resp.status_code, 404)


class UnInstantaneParGeste(_Base):
    """QJR550 — UN instantané par geste d'enregistrement, avec son auteur."""

    def test_replace_lines_de_dix_lignes_un_seul_instantane_avec_auteur(self):
        self._ligne()
        avant = self._snaps().count()
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': self._lignes_corps(10)}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._snaps().count(), avant + 1)
        dernier = self._snaps().last()
        self.assertEqual(dernier.auteur_id, self.user.id)
        self.assertEqual(len(dernier.contenu['lignes']), 10)

    def test_atomic_un_seul_instantane(self):
        client = ClientFactory(company=self.company)
        resp = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': client.id, 'statut': 'brouillon', 'taux_tva': '20',
            'lignes': self._lignes_corps(4)}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        snaps = ConfigurationDevisSnapshot.objects.filter(
            devis_id=resp.data['id'])
        self.assertEqual(snaps.count(), 1)
        self.assertEqual(snaps.get().auteur_id, self.user.id)

    def test_patch_de_ligne_un_instantane(self):
        ligne = self._ligne()
        avant = self._snaps().count()
        self._modifier(ligne, quantite='3')
        self.assertEqual(self._snaps().count(), avant + 1)

    def test_erreur_sql_dans_la_capture_n_avorte_pas_replace_lines(self):
        def _boum(devis):
            with connection.cursor() as curseur:
                curseur.execute('SELECT * FROM table_qjr550_inexistante')
        with mock.patch(
                'apps.ventes.domain.cycle_vie.configuration_devis_contenu',
                side_effect=_boum):
            resp = self.api.post(
                f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
                {'lignes': self._lignes_corps(3)}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.devis.lignes.count(), 3)
