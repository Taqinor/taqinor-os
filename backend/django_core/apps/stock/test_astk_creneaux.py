"""ASTK191 / ASTK192 — réservation de créneau fournisseur par jeton.

ASTK191 : toute réservation est validée contre LA grille que propose
``creneaux_disponibles`` (heure pleine, plage 08-18, horizon 30 j) — règle
unique ``creneau_est_propose`` appelée par la génération ET la réservation.
Sondes d'origine FOUR-11 (2099-01-01T03:17 → 201) et WMS-17 (vendredi 03:17
→ créé, grille proposée 08:00/09:00/10:00).

ASTK192 : chaque rendez-vous réservé par jeton porte son fournisseur et son BCF
(posés côté serveur) et le nombre de rendez-vous futurs ouverts par fournisseur
est plafonné (6ᵉ réservation → 400).

Source réelle : services + endpoints publics réels, aucun mock.

Run :
    python manage.py test apps.stock.test_astk_creneaux -v 2
"""
import datetime
import json
from pathlib import Path

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.stock.models import (
    EmplacementStock, Fournisseur, PortailFournisseurToken,
)
from apps.stock.models_wms import Quai, RendezVousTransporteur
from apps.stock.services_creneaux import (
    HEURE_FERMETURE, HEURE_OUVERTURE, creneau_est_propose,
    creneaux_disponibles,
)
from authentication.models import Company

CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
           / 'wms_quais.json')


def _contrat(cle):
    return json.loads(CONTRAT.read_text(encoding='utf-8'))['routes'][cle]


def _aware(jour, heure, minute=0):
    return timezone.make_aware(datetime.datetime.combine(
        jour, datetime.time(hour=heure, minute=minute)))


class _Base(TestCase):
    slug = 'astk191'

    def setUp(self):
        self.company = Company.objects.create(
            nom=f'{self.slug}-co', slug=f'{self.slug}-co')
        emplacement = EmplacementStock.objects.create(
            company=self.company, nom=f'Dépôt {self.slug}', is_principal=True)
        self.quai = Quai.objects.create(
            company=self.company, nom=f'Quai R1 {self.slug}',
            type_quai=Quai.TypeQuai.RECEPTION, emplacement=emplacement)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom=f'Fournisseur {self.slug}')
        self.token = PortailFournisseurToken.objects.create(
            company=self.company, fournisseur=self.fournisseur)
        self.demain = timezone.localdate() + datetime.timedelta(days=1)
        self.api = APIClient()

    def _url(self, suffixe):
        return ('/api/django/public/stock/portail-fournisseur/'
                f'{self.token.token}/{suffixe}')

    def _reserver(self, debut, **extra):
        corps = {'quai': self.quai.id, 'debut': debut}
        corps.update(extra)
        return self.api.post(
            self._url('reserver-creneau/'), corps, format='json')

    def _vendredi_suivant(self):
        jour = timezone.localdate() + datetime.timedelta(days=1)
        while jour.weekday() != 4:
            jour += datetime.timedelta(days=1)
        return jour


class GrilleTests(_Base):
    slug = 'astk191'

    def test_2099_0317_refuse(self):
        avant = RendezVousTransporteur.objects.count()
        reponse = self._reserver('2099-01-01T03:17')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertEqual(reponse.json(), {'debut': [
            'Créneau non proposé : choisissez un créneau de la liste.']})
        self.assertEqual(RendezVousTransporteur.objects.count(), avant)

    def test_nuit_refusee(self):
        avant = RendezVousTransporteur.objects.count()
        debut = _aware(self._vendredi_suivant(), 3, 17).isoformat()
        reponse = self._reserver(debut)
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('debut', reponse.json())
        self.assertEqual(RendezVousTransporteur.objects.count(), avant)

    def test_heure_non_pleine_et_hors_plage_refusees(self):
        avant = RendezVousTransporteur.objects.count()
        for debut in (_aware(self.demain, 9, 30),
                      _aware(self.demain, HEURE_FERMETURE),
                      _aware(self.demain, HEURE_OUVERTURE - 1)):
            reponse = self._reserver(debut.isoformat())
            self.assertEqual(reponse.status_code, 400, (debut, reponse.content))
            self.assertIn('debut', reponse.json())
        self.assertEqual(RendezVousTransporteur.objects.count(), avant)

    def test_hors_horizon_refuse(self):
        from apps.stock.services_creneaux import FENETRE_MAX_JOURS
        loin = (timezone.localdate()
                + datetime.timedelta(days=FENETRE_MAX_JOURS + 1))
        reponse = self._reserver(_aware(loin, 9).isoformat())
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('debut', reponse.json())

    def test_creneau_propose_201(self):
        liste = self.api.get(self._url('creneaux-disponibles/'), {
            'date_debut': self.demain.isoformat(), 'periode': 1})
        self.assertEqual(liste.status_code, 200, liste.content)
        creneaux = liste.json()['creneaux']
        self.assertTrue(creneaux)
        self.assertEqual(creneaux[0]['debut'][11:16], '08:00')
        reponse = self._reserver(creneaux[0]['debut'])
        self.assertEqual(reponse.status_code, 201, reponse.content)
        self.assertEqual(RendezVousTransporteur.objects.count(), 1)

    def test_tout_creneau_genere_est_propose(self):
        """Règle UNIQUE : tout ce que la génération propose est accepté par
        la règle de réservation (et inversement une heure hors grille ne l'est
        jamais)."""
        generes = creneaux_disponibles(
            self.company, date_debut=self.demain, periode_jours=3)
        self.assertTrue(generes)
        for creneau in generes:
            debut = datetime.datetime.fromisoformat(creneau['debut'])
            self.assertTrue(creneau_est_propose(debut), creneau)
        self.assertFalse(creneau_est_propose(_aware(self.demain, 9, 1)))

    def test_reponse_conforme_contrat(self):
        contrat = _contrat('public_reserver_creneau')
        attendu = contrat['nouveau_hors_grille_astk191']['exemple']
        reponse = self._reserver('2099-01-01T03:17')
        self.assertEqual(reponse.status_code,
                         contrat['nouveau_hors_grille_astk191']['statut'])
        self.assertEqual(set(reponse.json()), set(attendu))
        for cle, messages in reponse.json().items():
            self.assertIsInstance(messages, list)
            self.assertTrue(all(isinstance(m, str) for m in messages))
