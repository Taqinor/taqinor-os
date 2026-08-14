"""NTWMS39 — historique de versions du plan d'entrepôt.

Critère d'acceptation testé : consulter l'historique d'un casier montre QUI a
changé quoi et QUAND — création, modification d'un champ structurant,
archivage, réactivation.

Le champ ``type_bin`` annoncé par la tâche n'existe pas sur
``installations.BinLocation`` (constat déjà posé par NTWMS31) : le journal
suit la CATÉGORIE DE STOCKAGE (capacité/compatibilité, ZSTK9), qui est
l'équivalent réel du « type » de casier dans ce dépôt.

Run :
    python manage.py test apps.stock.test_ntwms39_historique_casier -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import EmplacementStock, HistoriqueCasier

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms39Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinLocation, CategorieStockage

        self.company = make_company('ntwms39-co', 'NTWMS39 Co')
        self.autre = make_company('ntwms39-autre', 'NTWMS39 Autre')
        self.admin = User.objects.create_user(
            username='ntwms39_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS39', is_principal=True)
        self.picking = CategorieStockage.objects.create(
            company=self.company, nom='Picking NTWMS39', qte_max=50)
        self.quarantaine = CategorieStockage.objects.create(
            company=self.company, nom='Quarantaine NTWMS39', qte_max=10)
        self._BinLocation = BinLocation


class Ntwms39JournalTests(Ntwms39Base):
    def test_la_creation_dun_casier_est_journalisee(self):
        casier = self._BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-01', zone='A', allee='01', casier='01', ordre=10,
            categorie=self.picking)

        lignes = HistoriqueCasier.objects.filter(bin=casier)
        self.assertEqual(lignes.count(), 1)
        self.assertEqual(lignes.first().action,
                         HistoriqueCasier.Action.CREATION)
        self.assertEqual(lignes.first().nouvelle_valeur, 'A-01-01')
        self.assertEqual(lignes.first().company_id, self.company.id)

    def test_le_changement_de_categorie_est_journalise(self):
        casier = self._BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-02', zone='A', allee='01', casier='02', ordre=20,
            categorie=self.picking)
        casier.categorie = self.quarantaine
        casier.save()

        modif = HistoriqueCasier.objects.filter(
            bin=casier, action=HistoriqueCasier.Action.MODIFICATION,
            champ='categorie_id').first()
        self.assertIsNotNone(modif)
        self.assertEqual(modif.ancienne_valeur, str(self.picking.id))
        self.assertEqual(modif.nouvelle_valeur, str(self.quarantaine.id))

    def test_archivage_puis_reactivation(self):
        casier = self._BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-03', zone='A', allee='01', casier='03', ordre=30)
        casier.archived = True
        casier.save()
        casier.archived = False
        casier.save()

        actions = list(HistoriqueCasier.objects.filter(bin=casier)
                       .order_by('id').values_list('action', flat=True))
        self.assertEqual(actions, [
            HistoriqueCasier.Action.CREATION,
            HistoriqueCasier.Action.ARCHIVAGE,
            HistoriqueCasier.Action.REACTIVATION,
        ])

    def test_un_save_sans_changement_najoute_aucune_ligne(self):
        casier = self._BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-04', zone='A', allee='01', casier='04', ordre=40)
        avant = HistoriqueCasier.objects.filter(bin=casier).count()
        casier.save()
        self.assertEqual(HistoriqueCasier.objects.filter(bin=casier).count(),
                         avant)

    def test_plusieurs_champs_modifies_donnent_plusieurs_lignes(self):
        casier = self._BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-05', zone='A', allee='01', casier='05', ordre=50)
        casier.zone = 'B'
        casier.ordre = 60
        casier.save()

        champs = set(HistoriqueCasier.objects.filter(
            bin=casier, action=HistoriqueCasier.Action.MODIFICATION)
            .values_list('champ', flat=True))
        self.assertEqual(champs, {'zone', 'ordre'})


class Ntwms39EndpointTests(Ntwms39Base):
    def test_lhistorique_est_consultable(self):
        casier = self._BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='C-01-01', zone='C', allee='01', casier='01', ordre=10,
            categorie=self.picking)
        casier.categorie = self.quarantaine
        casier.save()

        res = auth(self.admin).get(
            f'/api/django/stock/casiers/{casier.id}/historique/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['bin'], casier.id)
        self.assertEqual(res.data['bin_code'], 'C-01-01')
        actions = {ligne['action'] for ligne in res.data['lignes']}
        self.assertIn('modification', actions)
        self.assertIn('creation', actions)

    def test_le_casier_dune_autre_societe_ne_livre_aucun_historique(self):
        autre_emplacement = EmplacementStock.objects.create(
            company=self.autre, nom='Dépôt voisin', is_principal=True)
        casier_voisin = self._BinLocation.objects.create(
            company=self.autre, emplacement=autre_emplacement,
            code='Z-99-99', zone='Z', allee='99', casier='99', ordre=999)

        res = auth(self.admin).get(
            f'/api/django/stock/casiers/{casier_voisin.id}/historique/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['lignes'], [])

    def test_endpoint_refuse_lanonyme(self):
        res = APIClient().get('/api/django/stock/casiers/1/historique/')
        self.assertEqual(res.status_code, 401)
