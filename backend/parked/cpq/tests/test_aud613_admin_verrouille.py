"""AUD613 — l'admin Django de `cpq` ne contourne plus la matrice d'approbation.

`EtapeApprobationDevis` et `PrixContractuel` étaient administrés par des
`ModelAdmin` NUS : un compte `is_staff` pouvait, en un formulaire, passer une
étape d'approbation à « approuvé » (donc envoyer une remise profonde sans
approbation), réécrire un accord tarifaire négocié par-dessus le verrou
d'auteur NTCPQ37, et le faire sans laisser la moindre trace d'audit NTCPQ46 —
le Django admin ne connaît ni les services ni les vues, il écrit le modèle.

Run :
    python manage.py test apps.cpq.tests.test_aud613_admin_verrouille -v2
"""
from decimal import Decimal

from django.contrib import admin as django_admin
from django.test import Client as HttpClient
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.cpq.models import EtapeApprobationDevis, PrixContractuel
from testkit.factories import (
    ClientFactory, CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

MODELES_VERROUILLES = (EtapeApprobationDevis, PrixContractuel)


class BaseAdminCpq(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.superuser = UserFactory(
            username='aud613-root', company=self.company,
            is_staff=True, is_superuser=True)
        self.http = HttpClient()
        self.http.force_login(self.superuser)

        self.devis = DevisFactory(company=self.company,
                                  remise_globale=Decimal('25'))
        self.etape = EtapeApprobationDevis.objects.create(
            company=self.company, devis=self.devis, niveau=1,
            statut=EtapeApprobationDevis.Statut.EN_ATTENTE)
        self.prix = PrixContractuel.objects.create(
            company=self.company, client=ClientFactory(company=self.company),
            produit=ProduitFactory(company=self.company),
            prix_ht=Decimal('1234.00'))

    def _requete(self):
        requete = RequestFactory().get('/')
        requete.user = self.superuser
        return requete

    @staticmethod
    def _url(modele, vue, *args):
        """URL d'admin par ``reverse`` — le préfixe est configurable
        (``DJANGO_ADMIN_URL``), l'écrire en dur périmerait le test."""
        return reverse(
            'admin:cpq_%s_%s' % (modele._meta.model_name, vue), args=args)


class TestAucuneEcriturePossible(BaseAdminCpq):
    def test_les_trois_permissions_d_ecriture_sont_fermees(self):
        requete = self._requete()
        for modele in MODELES_VERROUILLES:
            option = django_admin.site._registry[modele]
            with self.subTest(modele=modele.__name__):
                self.assertFalse(option.has_add_permission(requete))
                self.assertFalse(option.has_change_permission(requete))
                self.assertFalse(option.has_delete_permission(requete))

    def test_l_ecran_d_ajout_repond_403(self):
        for modele in MODELES_VERROUILLES:
            with self.subTest(modele=modele.__name__):
                reponse = self.http.get(self._url(modele, 'add'))
                self.assertEqual(reponse.status_code, 403)

    def test_le_post_de_suppression_ne_supprime_rien(self):
        for modele, objet in ((EtapeApprobationDevis, self.etape),
                              (PrixContractuel, self.prix)):
            with self.subTest(modele=modele.__name__):
                self.http.post(self._url(modele, 'delete', objet.pk),
                               {'post': 'yes'})
                self.assertTrue(
                    modele.objects.filter(pk=objet.pk).exists(),
                    f'{modele.__name__} supprimé depuis /admin/.')

    def test_une_etape_ne_peut_pas_etre_approuvee_par_l_admin(self):
        """Le cas qui coûte cher : approuver sans passer par la matrice."""
        url = self._url(EtapeApprobationDevis, 'change', self.etape.pk)
        self.http.post(url, {
            'company': self.company.pk, 'devis': self.devis.pk, 'niveau': 1,
            'statut': EtapeApprobationDevis.Statut.APPROUVE,
        })
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut,
                         EtapeApprobationDevis.Statut.EN_ATTENTE)

    def test_un_prix_negocie_ne_peut_pas_etre_reecrit(self):
        url = self._url(PrixContractuel, 'change', self.prix.pk)
        self.http.post(url, {
            'company': self.company.pk, 'client': self.prix.client_id,
            'produit': self.prix.produit_id, 'prix_ht': '1.00',
        })
        self.prix.refresh_from_db()
        self.assertEqual(self.prix.prix_ht, Decimal('1234.00'))


class TestLectureConservee(BaseAdminCpq):
    """Fermer l'écriture ne doit pas rendre la donnée invisible."""

    def test_la_liste_reste_consultable(self):
        for modele in MODELES_VERROUILLES:
            with self.subTest(modele=modele.__name__):
                reponse = self.http.get(self._url(modele, 'changelist'))
                self.assertEqual(reponse.status_code, 200)


class TestScopeSociete(BaseAdminCpq):
    """Même garantie qu'AUD185 : l'admin ne montre pas la société voisine."""

    def test_la_ligne_d_une_autre_societe_est_hors_liste(self):
        voisine = CompanyFactory()
        PrixContractuel.objects.create(
            company=voisine, client=ClientFactory(company=voisine),
            produit=ProduitFactory(company=voisine),
            prix_ht=Decimal('999.00'))
        option = django_admin.site._registry[PrixContractuel]
        societes = set(
            option.get_queryset(self._requete())
            .values_list('company_id', flat=True))
        self.assertEqual(societes, {self.company.pk})
