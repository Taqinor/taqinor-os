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

    def test_capture_en_envoye_jamais_en_accepte(self):
        """QJR552 — remplace ``test_pas_dinstantane_hors_brouillon``, qui
        figeait le comportement fautif : un devis ENVOYÉ corrigé garde l'état
        vu par le client (PREMIER instantané) et l'état corrigé (DERNIER) ; un
        ACCEPTÉ refuse le geste (409) et ne prend aucun instantané. Le statut
        n'est jamais écrit."""
        ligne = self._ligne(qte='2', prix='100.00')
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.ENVOYE)
        self.assertEqual(self._snaps().count(), 0)

        resp = self.api.patch(f'/api/django/ventes/devis/{self.devis.id}/',
                              {'remise_globale': '5'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': [{'produit': self.produit.id,
                         'designation': ligne.designation, 'quantite': '2',
                         'prix_unitaire': '120.00'}]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        snaps = list(self._snaps())
        self.assertGreaterEqual(len(snaps), 2)
        premier, dernier = snaps[0].contenu, snaps[-1].contenu
        self.assertEqual(premier['remise_globale'], '0.00')
        self.assertEqual(premier['lignes'][0]['prix_unitaire'], '100.00')
        self.assertEqual(dernier['remise_globale'], '5.00')
        self.assertEqual(dernier['lignes'][0]['prix_unitaire'], '120.00')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)

        accepte = DevisFactory(company=self.company)
        LigneDevis.objects.create(
            devis=accepte, produit=self.produit, designation='X',
            quantite=Decimal('1'), prix_unitaire=Decimal('100.00'))
        Devis.objects.filter(pk=accepte.pk).update(
            statut=Devis.Statut.ACCEPTE)
        resp = self.api.post(
            f'/api/django/ventes/devis/{accepte.id}/replace-lines/',
            {'lignes': self._lignes_corps(1)}, format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(ConfigurationDevisSnapshot.objects.filter(
            devis=accepte).count(), 0)

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
        # QJR551 — étendu au contenu ENRICHI (paramètres, étude, totaux).
        Devis.objects.filter(pk=self.devis.pk).update(
            etude_params={'scenario': 'Sans batterie'},
            echeancier=[{'libelle': 'Acompte', 'type': 'acompte',
                         'pct_or_montant': 40}])
        self._ajouter()
        snap = ConfigurationDevisSnapshot.objects.get(devis=self.devis)
        for cle in ('lignes', 'remise_globale', 'echeancier', 'etude',
                    'totaux'):
            self.assertIn(cle, snap.contenu)
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
        # QJR551 — appariement par identité stable (type, produit, variante)
        # + rang d'occurrence, plus par ``ligne_id``.
        self.assertEqual([li['cle'] for li in diff['ajoutees']],
                         [f'produit:{self.produit.id}:#1'])
        self.assertEqual(diff['ajoutees'][0]['prix_unitaire'],
                         str(ajoutee.prix_unitaire))
        self.assertEqual(diff['retirees'], [])
        self.assertEqual(diff['modifiees'][0]['cle'],
                         f'produit:{self.produit.id}:#0')
        self.assertEqual(diff['modifiees'][0]['champs']['quantite'],
                         ['1.00', '7.00'])
        self.assertEqual(ligne.produit_id, self.produit.id)

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

    def test_reponse_conforme_au_contrat_qjr513(self):
        """QJR553 — la réponse lue par l'écran d'historique a la forme du
        contrat committé ``devis_historique_configuration.json``."""
        import json
        from pathlib import Path
        contrat = json.loads(
            (Path(__file__).resolve().parent.parent / 'contract_samples'
             / 'devis_historique_configuration.json').read_text(encoding='utf-8'))
        ligne = self._ajouter()
        self._modifier(ligne, quantite='5')
        snaps = list(self._snaps())
        url = (f'/api/django/ventes/devis/{self.devis.id}/'
               'historique-configuration/')
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        attendu = contrat['exemple']['snapshots'][0]
        recu = resp.data['snapshots'][0]
        self.assertEqual(set(recu), set(attendu))
        self.assertLessEqual(set(attendu['contenu']), set(recu['contenu']))
        self.assertLessEqual(set(attendu['contenu']['lignes'][0]),
                             set(recu['contenu']['lignes'][0]))
        resp = self.api.get(f'{url}?a={snaps[0].id}&b={snaps[1].id}')
        self.assertEqual(set(resp.data['diff']),
                         set(contrat['exemple_avec_diff']['diff']))
        texte = json.dumps(resp.data, default=str)
        self.assertNotIn('prix_achat', texte)
        self.assertNotIn('marge', texte)

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


class InstantaneCompletEtApparie(_Base):
    """QJR551 — lignes appariées par une identité stable, instantané complet
    (lignes restaurables, paramètres, échéancier, totaux)."""

    def _remplacer(self, lignes):
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': lignes}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_un_seul_prix_change_une_seule_ligne_modifiee(self):
        lignes = self._lignes_corps(4)
        self._remplacer(lignes)
        lignes[2] = dict(lignes[2], prix_unitaire='130.00')
        self._remplacer(lignes)
        a, b = list(self._snaps())[-2:]
        diff = diff_configurations_devis(a, b)
        self.assertEqual(diff['ajoutees'], [])
        self.assertEqual(diff['retirees'], [])
        self.assertEqual(len(diff['modifiees']), 1)
        self.assertEqual(diff['modifiees'][0]['champs']['prix_unitaire'],
                         ['100.00', '130.00'])
        # Troisième enregistrement identique : aucun nouvel instantané.
        avant = self._snaps().count()
        self._remplacer(lignes)
        self.assertEqual(self._snaps().count(), avant)

    def test_la_remise_apparait_dans_les_parametres(self):
        lignes = self._lignes_corps(2)
        self._remplacer(lignes)
        resp = self.api.patch(f'/api/django/ventes/devis/{self.devis.id}/',
                              {'remise_globale': '5'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self._remplacer(lignes)
        a, b = list(self._snaps())[-2:]
        diff = diff_configurations_devis(a, b)
        self.assertEqual(diff['parametres']['remise_globale'],
                         ['0.00', '5.00'])
        self.assertEqual(diff['modifiees'], [])

    def test_les_lignes_portent_le_jeu_clone_sans_id_de_ligne(self):
        from apps.ventes.domain.lignes import CHAMPS_CLONES
        self._remplacer(self._lignes_corps(1))
        ligne = self._snaps().last().contenu['lignes'][0]
        self.assertEqual(set(ligne), set(CHAMPS_CLONES))
        self.assertNotIn('ligne_id', ligne)
        self.assertEqual(ligne['produit'], self.produit.id)

    def test_un_ancien_instantane_reste_lisible(self):
        ancien = {'lignes': [{'ligne_id': 1, 'produit_id': self.produit.id,
                              'designation': 'X', 'quantite': '1.00',
                              'prix_unitaire': '100.00', 'remise': '0.00'}]}
        self._remplacer(self._lignes_corps(1))
        diff = diff_configurations_devis(ancien, self._snaps().last())
        self.assertEqual(diff['ajoutees'], [])
        self.assertEqual(diff['retirees'], [])
        self.assertIn('remise_globale', diff['parametres'])
