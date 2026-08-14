"""NTWMS35 — créneaux de rendez-vous entrant proposés au fournisseur.

Critère d'acceptation testé : un fournisseur connecté à SON portail voit les
créneaux libres d'un quai de réception et peut RÉSERVER sans intervention du
magasinier — et ne voit jamais un quai d'expédition, un créneau déjà pris, ni
quoi que ce soit d'une autre société.

Les horodatages sont FIXES et dérivés d'une date de référence future calculée
sans lire d'assertion sur l'horloge.

Run :
    python manage.py test apps.stock.test_ntwms35_creneaux_fournisseur -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.stock.models import EmplacementStock, Fournisseur
from apps.stock.models_wms import Quai, RendezVousTransporteur
from apps.stock.services_creneaux import (
    creneaux_disponibles, reserver_creneau_fournisseur,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _prochain_jour_ouvre():
    """Un jour FUTUR stable (demain) — la réservation refuse le passé."""
    return timezone.localdate() + datetime.timedelta(days=1)


def _creneau(jour, heure):
    return timezone.make_aware(
        datetime.datetime.combine(jour, datetime.time(hour=heure)))


class Ntwms35Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms35-co', 'NTWMS35 Co')
        self.autre = make_company('ntwms35-autre', 'NTWMS35 Autre')
        self.admin = User.objects.create_user(
            username='ntwms35_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS35', is_principal=True)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTWMS35')

        self.quai_reception = Quai.objects.create(
            company=self.company, nom='Quai R1 NTWMS35',
            type_quai=Quai.TypeQuai.RECEPTION, emplacement=self.emplacement)
        self.quai_expedition = Quai.objects.create(
            company=self.company, nom='Quai E1 NTWMS35',
            type_quai=Quai.TypeQuai.EXPEDITION, emplacement=self.emplacement)
        self.quai_inactif = Quai.objects.create(
            company=self.company, nom='Quai R2 NTWMS35',
            type_quai=Quai.TypeQuai.RECEPTION, emplacement=self.emplacement,
            actif=False)

        from apps.stock.models import PortailFournisseurToken
        self.token_obj = PortailFournisseurToken.objects.create(
            company=self.company, fournisseur=self.fournisseur)
        self.jour = _prochain_jour_ouvre()

    def _url(self, suffixe):
        return (f'/api/django/public/stock/portail-fournisseur/'
                f'{self.token_obj.token}/{suffixe}')


class Ntwms35CreneauxTests(Ntwms35Base):
    def test_seuls_les_quais_de_reception_actifs_sont_proposes(self):
        creneaux = creneaux_disponibles(
            self.company, date_debut=self.jour, periode_jours=1)
        quais = {c['quai'] for c in creneaux}
        self.assertEqual(quais, {self.quai_reception.id})

    def test_un_creneau_deja_occupe_nest_jamais_propose(self):
        debut = _creneau(self.jour, 9)
        RendezVousTransporteur.objects.create(
            company=self.company, quai=self.quai_reception,
            date_heure_debut=debut,
            date_heure_fin=debut + datetime.timedelta(hours=1))

        creneaux = creneaux_disponibles(
            self.company, date_debut=self.jour, periode_jours=1)
        debuts = {c['debut'] for c in creneaux}
        self.assertNotIn(debut.isoformat(), debuts)
        # Le créneau de 10 h reste libre.
        self.assertIn(_creneau(self.jour, 10).isoformat(), debuts)

    def test_la_fenetre_est_plafonnee(self):
        from apps.stock.services_creneaux import FENETRE_MAX_JOURS

        creneaux = creneaux_disponibles(
            self.company, date_debut=self.jour, periode_jours=3650)
        jours = {c['date'] for c in creneaux}
        self.assertEqual(len(jours), FENETRE_MAX_JOURS)

    def test_aucun_creneau_dune_autre_societe(self):
        autre_emplacement = EmplacementStock.objects.create(
            company=self.autre, nom='Dépôt voisin', is_principal=True)
        Quai.objects.create(
            company=self.autre, nom='Quai voisin', emplacement=autre_emplacement,
            type_quai=Quai.TypeQuai.RECEPTION)
        creneaux = creneaux_disponibles(
            self.company, date_debut=self.jour, periode_jours=1)
        self.assertTrue(creneaux)
        self.assertTrue(all(c['quai'] == self.quai_reception.id
                            for c in creneaux))


class Ntwms35ReservationTests(Ntwms35Base):
    def test_le_fournisseur_reserve_sans_magasinier(self):
        rdv = reserver_creneau_fournisseur(
            self.token_obj, quai_id=self.quai_reception.id,
            debut=_creneau(self.jour, 11).isoformat(),
            chauffeur_nom='Youssef', immatriculation='1234-A-56')

        self.assertEqual(rdv.company_id, self.company.id)
        self.assertEqual(rdv.quai_id, self.quai_reception.id)
        self.assertEqual(rdv.statut, RendezVousTransporteur.Statut.PLANIFIE)
        self.assertTrue(rdv.code_checkin)
        self.assertIn('NTWMS35', rdv.note)

    def test_reserver_deux_fois_le_meme_creneau_est_refuse(self):
        debut = _creneau(self.jour, 12).isoformat()
        reserver_creneau_fournisseur(
            self.token_obj, quai_id=self.quai_reception.id, debut=debut)
        with self.assertRaises(ValueError):
            reserver_creneau_fournisseur(
                self.token_obj, quai_id=self.quai_reception.id, debut=debut)

    def test_un_quai_dexpedition_ou_inactif_est_refuse(self):
        debut = _creneau(self.jour, 13).isoformat()
        with self.assertRaises(ValueError):
            reserver_creneau_fournisseur(
                self.token_obj, quai_id=self.quai_expedition.id, debut=debut)
        with self.assertRaises(ValueError):
            reserver_creneau_fournisseur(
                self.token_obj, quai_id=self.quai_inactif.id, debut=debut)

    def test_un_creneau_passe_est_refuse(self):
        hier = timezone.localdate() - datetime.timedelta(days=1)
        with self.assertRaises(ValueError):
            reserver_creneau_fournisseur(
                self.token_obj, quai_id=self.quai_reception.id,
                debut=_creneau(hier, 9).isoformat())

    def test_un_bcf_dun_autre_fournisseur_est_invisible(self):
        from apps.stock.models import BonCommandeFournisseur

        autre_fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Autre fournisseur NTWMS35')
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTWMS35-X',
            fournisseur=autre_fournisseur)
        with self.assertRaises(ValueError):
            reserver_creneau_fournisseur(
                self.token_obj, quai_id=self.quai_reception.id,
                debut=_creneau(self.jour, 14).isoformat(),
                bon_commande_id=bcf.id)


class Ntwms35EndpointTests(Ntwms35Base):
    def test_endpoints_publics_repondent_avec_le_jeton(self):
        api = APIClient()
        liste = api.get(self._url('creneaux-disponibles/'), {'periode': 1})
        self.assertEqual(liste.status_code, 200)
        self.assertTrue(liste.data['creneaux'])
        self.assertEqual(liste['X-Robots-Tag'], 'noindex, nofollow, noarchive')

        reserve = api.post(self._url('reserver-creneau/'), {
            'quai': self.quai_reception.id,
            'debut': _creneau(self.jour, 15).isoformat(),
        }, format='json')
        self.assertEqual(reserve.status_code, 201)
        self.assertTrue(reserve.data['code_checkin'])

    def test_jeton_invalide_renvoie_404_sans_fuite(self):
        api = APIClient()
        url = ('/api/django/public/stock/portail-fournisseur/bidon/'
               'creneaux-disponibles/')
        self.assertEqual(api.get(url).status_code, 404)

    def test_jeton_revoque_renvoie_404(self):
        self.token_obj.revoked = True
        self.token_obj.save(update_fields=['revoked'])
        res = APIClient().get(self._url('creneaux-disponibles/'))
        self.assertEqual(res.status_code, 404)

    def test_reservation_sur_un_creneau_invalide_renvoie_400(self):
        res = APIClient().post(self._url('reserver-creneau/'), {
            'quai': self.quai_reception.id, 'debut': 'pas-une-date',
        }, format='json')
        self.assertEqual(res.status_code, 400)


# Garde de non-régression du prix : aucun montant ne transite par ces
# endpoints publics (le portail fournisseur ne doit jamais exposer de marge).
class Ntwms35AucunPrixExposeTests(Ntwms35Base):
    def test_la_reponse_ne_contient_aucun_montant(self):
        Decimal('0')  # rappel : aucun prix n'entre dans ce flux.
        res = APIClient().get(self._url('creneaux-disponibles/'),
                              {'periode': 1})
        brut = str(res.data)
        for interdit in ('prix', 'marge', 'cout'):
            self.assertNotIn(interdit, brut.lower())
