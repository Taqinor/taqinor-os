"""NTDOC18 — Matrice d'obligations avec preuves de réalisation.

Couvre :
  * lier un document GED à une obligation la rend visible (lien + nom) dans la
    matrice ;
  * une obligation « faite » SANS preuve reste parfaitement valide, mais est
    signalée `preuve_manquante` (jamais un blocage) ;
  * une obligation `à faire` sans preuve n'est PAS signalée (le badge ne vise
    que le réalisé) ;
  * la matrice groupe bien par redevable × statut ;
  * un document d'une AUTRE société est refusé en preuve (AUD601) ;
  * isolation société sur l'endpoint.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.contrats import selectors
from apps.contrats.models import Contrat, Obligation

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_admin(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='admin')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_document(company, nom):
    from apps.ged.models import Cabinet, Document, Folder
    cabinet, _ = Cabinet.objects.get_or_create(company=company, nom='Admin')
    folder, _ = Folder.objects.get_or_create(
        company=company, cabinet=cabinet, nom='Preuves')
    return Document.objects.create(company=company, folder=folder, nom=nom)


class NtDoc18Base(TestCase):
    def setUp(self):
        self.co_a = make_company('ntdoc18-a', 'Ntdoc18 A')
        self.co_b = make_company('ntdoc18-b', 'Ntdoc18 B')
        self.admin_a = make_admin(self.co_a, 'ntdoc18-admin-a')
        self.admin_b = make_admin(self.co_b, 'ntdoc18-admin-b')
        self.api = auth(self.admin_a)
        self.contrat = Contrat.objects.create(
            company=self.co_a, objet='Maintenance annuelle')

    def _obligation(self, intitule, **kwargs):
        return Obligation.objects.create(
            company=self.co_a, contrat=self.contrat, intitule=intitule,
            **kwargs)


class PreuveManquanteTests(NtDoc18Base):
    def test_obligation_faite_sans_preuve_valide_mais_signalee(self):
        obligation = self._obligation(
            'Remise du dossier ONEE', statut=Obligation.Statut.FAITE)
        self.assertTrue(obligation.preuve_manquante)
        # Toujours valide : aucune règle ne la rejette.
        obligation.full_clean()

    def test_obligation_a_faire_sans_preuve_non_signalee(self):
        obligation = self._obligation('Mise en service')
        self.assertEqual(obligation.statut, Obligation.Statut.A_FAIRE)
        self.assertFalse(obligation.preuve_manquante)

    def test_obligation_faite_avec_preuve_non_signalee(self):
        document = make_document(self.co_a, 'PV de réception.pdf')
        obligation = self._obligation(
            'Réception', statut=Obligation.Statut.FAITE,
            preuve_document=document)
        self.assertFalse(obligation.preuve_manquante)


class MatriceTests(NtDoc18Base):
    def test_groupement_par_redevable_et_statut(self):
        self._obligation('A', redevable=Obligation.Redevable.PRESTATAIRE,
                         statut=Obligation.Statut.FAITE)
        self._obligation('B', redevable=Obligation.Redevable.PRESTATAIRE,
                         statut=Obligation.Statut.FAITE)
        self._obligation('C', redevable=Obligation.Redevable.PRESTATAIRE,
                         statut=Obligation.Statut.A_FAIRE)
        self._obligation('D', redevable=Obligation.Redevable.CLIENT,
                         statut=Obligation.Statut.A_FAIRE)

        matrice = selectors.matrice_obligations(self.contrat)
        self.assertEqual(matrice['total'], 4)
        self.assertEqual(len(matrice['lignes']), 3)
        self.assertEqual(matrice['preuves_manquantes'], 2)
        couples = {(ligne['redevable'], ligne['statut'])
                   for ligne in matrice['lignes']}
        self.assertEqual(couples, {
            ('prestataire', 'faite'), ('prestataire', 'a_faire'),
            ('client', 'a_faire')})

    def test_contrat_sans_obligation(self):
        matrice = selectors.matrice_obligations(self.contrat)
        self.assertEqual(matrice['total'], 0)
        self.assertEqual(matrice['lignes'], [])
        self.assertEqual(matrice['preuves_manquantes'], 0)


class ApiMatriceTests(NtDoc18Base):
    def _url(self, contrat=None):
        contrat = contrat or self.contrat
        return (f'/api/django/contrats/contrats/{contrat.pk}/'
                f'matrice-obligations/')

    def test_endpoint_expose_le_lien_de_preuve(self):
        document = make_document(self.co_a, 'PV de réception.pdf')
        self._obligation('Réception', statut=Obligation.Statut.FAITE,
                         preuve_document=document)
        self._obligation('Rapport trimestriel',
                         statut=Obligation.Statut.FAITE)

        reponse = self.api.get(self._url())
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['total'], 2)
        self.assertEqual(reponse.data['preuves_manquantes'], 1)
        obligations = reponse.data['lignes'][0]['obligations']
        par_intitule = {o['intitule']: o for o in obligations}
        self.assertEqual(
            par_intitule['Réception']['preuve_document'], document.pk)
        self.assertEqual(
            par_intitule['Réception']['preuve_document_nom'],
            'PV de réception.pdf')
        self.assertFalse(par_intitule['Réception']['preuve_manquante'])
        self.assertTrue(
            par_intitule['Rapport trimestriel']['preuve_manquante'])

    def test_preuve_d_une_autre_societe_refusee(self):
        obligation = self._obligation('Réception')
        etranger = make_document(self.co_b, 'Pièce voisine.pdf')
        reponse = self.api.patch(
            f'/api/django/contrats/obligations/{obligation.pk}/',
            {'preuve_document': etranger.pk}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        obligation.refresh_from_db()
        self.assertIsNone(obligation.preuve_document_id)

    def test_preuve_de_la_societe_acceptee(self):
        obligation = self._obligation('Réception')
        document = make_document(self.co_a, 'PV.pdf')
        reponse = self.api.patch(
            f'/api/django/contrats/obligations/{obligation.pk}/',
            {'preuve_document': document.pk}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        obligation.refresh_from_db()
        self.assertEqual(obligation.preuve_document_id, document.pk)

    def test_matrice_d_un_contrat_voisin_inaccessible(self):
        contrat_b = Contrat.objects.create(
            company=self.co_b, objet='Contrat voisin')
        self.assertEqual(self.api.get(self._url(contrat_b)).status_code, 404)
