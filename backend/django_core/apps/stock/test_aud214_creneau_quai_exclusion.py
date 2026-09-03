"""AUD214 — le non-chevauchement des créneaux de quai est posé PAR LA BASE.

Défaut d'origine : la garde NTWMS7 vivait uniquement dans
``RendezVousTransporteur.save()`` — lire les chevauchements PUIS insérer, sans
verrou. Un TOCTOU, atteignable depuis un endpoint PUBLIC (``AllowAny``) : le
portail fournisseur (`portail_fournisseur_reserver_creneau_view` →
`reserver_creneau_fournisseur`). Deux réservations simultanées du même créneau
exécutent leur SELECT avant que l'autre n'ait inséré : aucune ne voit de
conflit et les DEUX passent.

Correctif : une ``ExclusionConstraint`` PostgreSQL
(``EXCLUDE USING GIST (tstzrange(debut, fin, '[)') WITH &&, quai_id WITH =)``
filtrée aux statuts OCCUPANTS). Les tests ci-dessous prouvent le refus par la
BASE, pas par Python : chaque scénario contourne délibérément ``save()``
(``bulk_create``, ``queryset.update()``) ou neutralise sa lecture de
chevauchements (ce que fait, de fait, une transaction concurrente non encore
visible).

Run :
    python manage.py test apps.stock.test_aud214_creneau_quai_exclusion -v 2
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import EmplacementStock, Fournisseur, PortailFournisseurToken
from apps.stock.models_wms import Quai, RendezVousTransporteur
from apps.stock.services_creneaux import reserver_creneau_fournisseur
from authentication.models import Company

User = get_user_model()

CONTRAINTE = 'stock_rdvtransporteur_quai_sans_chevauchement'
URL_RDV = '/api/django/stock/rendez-vous-transporteur/'


def _jour_futur():
    """Un jour FUTUR stable (demain) — la réservation refuse le passé."""
    return timezone.localdate() + datetime.timedelta(days=1)


def _h(jour, heure):
    return timezone.make_aware(
        datetime.datetime.combine(jour, datetime.time(hour=heure)))


class Aud214Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD214 Co', slug='aud214-co')
        self.admin = User.objects.create_user(
            username='aud214_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt AUD214', is_principal=True)
        self.quai = Quai.objects.create(
            company=self.company, nom='Quai AUD214',
            type_quai=Quai.TypeQuai.RECEPTION, emplacement=self.emplacement)
        self.autre_quai = Quai.objects.create(
            company=self.company, nom='Quai AUD214 bis',
            type_quai=Quai.TypeQuai.RECEPTION, emplacement=self.emplacement)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur AUD214')
        self.token_obj = PortailFournisseurToken.objects.create(
            company=self.company, fournisseur=self.fournisseur)
        self.jour = _jour_futur()

    def _rdv_brut(self, quai, debut_h, fin_h, statut='planifie',
                  code_checkin=''):
        """Insertion qui NE PASSE PAS par ``save()`` (donc pas par la garde
        Python) : exactement ce que voit la base sous une course."""
        return RendezVousTransporteur(
            company=self.company, quai=quai,
            date_heure_debut=_h(self.jour, debut_h),
            date_heure_fin=_h(self.jour, fin_h),
            statut=statut, code_checkin=code_checkin)


class Aud214ContrainteDeclareeTests(Aud214Base):
    """La contrainte existe, et sa condition ne dérive pas des statuts."""

    def test_la_contrainte_est_declaree_dans_le_modele(self):
        noms = {c.name for c in RendezVousTransporteur._meta.constraints}
        self.assertIn(CONTRAINTE, noms)

    def test_la_condition_est_le_miroir_exact_des_statuts_occupants(self):
        contrainte = next(c for c in RendezVousTransporteur._meta.constraints
                          if c.name == CONTRAINTE)
        _, valeurs = contrainte.condition.children[0]
        self.assertEqual(
            sorted(valeurs),
            sorted(str(s) for s in RendezVousTransporteur.STATUTS_OCCUPANTS))

    def test_seul_le_statut_annule_libere_le_creneau(self):
        """Garde anti-dérive : un statut ajouté plus tard force à revisiter la
        condition de la contrainte (et cette liste)."""
        tous = set(RendezVousTransporteur.Statut.values)
        occupants = {str(s) for s in RendezVousTransporteur.STATUTS_OCCUPANTS}
        self.assertEqual(tous - occupants, {'annule'})


class Aud214RefusParLaBaseTests(Aud214Base):
    """Le refus vient de la BASE : chaque insertion contourne ``save()``."""

    def test_deux_creneaux_chevauchants_inseres_en_masse_sont_refuses(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RendezVousTransporteur.objects.bulk_create([
                    self._rdv_brut(self.quai, 8, 10, code_checkin='AUD214AA'),
                    self._rdv_brut(self.quai, 9, 11, code_checkin='AUD214BB'),
                ])
        self.assertEqual(RendezVousTransporteur.objects.count(), 0)

    def test_deux_creneaux_disjoints_inseres_en_masse_passent(self):
        # Bornes [) : 8h-9h et 9h-10h ne se chevauchent PAS (même sémantique
        # que la garde Python historique).
        RendezVousTransporteur.objects.bulk_create([
            self._rdv_brut(self.quai, 8, 9, code_checkin='AUD214CC'),
            self._rdv_brut(self.quai, 9, 10, code_checkin='AUD214DD'),
        ])
        self.assertEqual(RendezVousTransporteur.objects.count(), 2)

    def test_le_meme_creneau_sur_un_autre_quai_reste_accepte(self):
        RendezVousTransporteur.objects.bulk_create([
            self._rdv_brut(self.quai, 8, 10, code_checkin='AUD214EE'),
            self._rdv_brut(self.autre_quai, 8, 10, code_checkin='AUD214FF'),
        ])
        self.assertEqual(RendezVousTransporteur.objects.count(), 2)

    def test_un_creneau_annule_ne_bloque_pas_la_place(self):
        RendezVousTransporteur.objects.bulk_create([
            self._rdv_brut(self.quai, 8, 10, statut='annule',
                           code_checkin='AUD214GG'),
            self._rdv_brut(self.quai, 8, 10, code_checkin='AUD214HH'),
        ])
        self.assertEqual(RendezVousTransporteur.objects.count(), 2)

    def test_reactiver_un_creneau_annule_par_update_est_refuse(self):
        """``queryset.update()`` ne passe JAMAIS par ``save()`` : sans la
        contrainte de base, ce chemin ré-ouvrait un chevauchement en silence."""
        occupant = RendezVousTransporteur.objects.create(
            company=self.company, quai=self.quai,
            date_heure_debut=_h(self.jour, 8), date_heure_fin=_h(self.jour, 10))
        annule = RendezVousTransporteur.objects.create(
            company=self.company, quai=self.quai,
            date_heure_debut=_h(self.jour, 8), date_heure_fin=_h(self.jour, 10),
            statut=RendezVousTransporteur.Statut.ANNULE)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RendezVousTransporteur.objects.filter(pk=annule.pk).update(
                    statut=RendezVousTransporteur.Statut.PLANIFIE)

        annule.refresh_from_db()
        self.assertEqual(annule.statut, RendezVousTransporteur.Statut.ANNULE)
        self.assertEqual(occupant.statut,
                         RendezVousTransporteur.Statut.PLANIFIE)


def _sans_garde_python():
    """Simule la fenêtre TOCTOU : la lecture de chevauchements ne voit rien.

    C'est EXACTEMENT ce que voit chacune des deux transactions concurrentes —
    l'autre n'a pas encore committé. Sans la contrainte de base, les deux
    insertions passaient.
    """
    return mock.patch.object(
        RendezVousTransporteur, 'chevauchements',
        lambda self: RendezVousTransporteur.objects.none())


class Aud214CourseSurLeCreneauTests(Aud214Base):
    """Le portail PUBLIC : la seconde réservation est refusée proprement."""

    def test_deux_reservations_concurrentes_ne_passent_pas_toutes_les_deux(self):
        debut = _h(self.jour, 9).isoformat()
        with _sans_garde_python():
            premiere = reserver_creneau_fournisseur(
                self.token_obj, quai_id=self.quai.id, debut=debut)
            with self.assertRaises(ValueError) as ctx:
                reserver_creneau_fournisseur(
                    self.token_obj, quai_id=self.quai.id, debut=debut)

        # Message MÉTIER (jamais une trace, jamais une 500) sur un endpoint
        # public.
        self.assertIn('vient d\'être réservé', str(ctx.exception))
        self.assertEqual(
            RendezVousTransporteur.objects.filter(quai=self.quai).count(), 1)
        self.assertEqual(
            RendezVousTransporteur.objects.first().pk, premiere.pk)

    def test_l_endpoint_public_repond_400_et_pas_500(self):
        debut = _h(self.jour, 14).isoformat()
        url = (f'/api/django/public/stock/portail-fournisseur/'
               f'{self.token_obj.token}/reserver-creneau/')
        api = APIClient()
        with _sans_garde_python():
            premiere = api.post(
                url, {'quai': self.quai.id, 'debut': debut}, format='json')
            seconde = api.post(
                url, {'quai': self.quai.id, 'debut': debut}, format='json')

        self.assertEqual(premiere.status_code, 201)
        self.assertEqual(seconde.status_code, 400)
        self.assertIn('vient d\'être réservé', seconde.data['detail'])

    def test_l_api_interne_repond_400_et_pas_500(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        corps = {
            'quai': self.quai.id,
            'date_heure_debut': _h(self.jour, 16).isoformat(),
            'date_heure_fin': _h(self.jour, 17).isoformat(),
        }
        with _sans_garde_python():
            premiere = api.post(URL_RDV, corps, format='json')
            seconde = api.post(URL_RDV, corps, format='json')

        self.assertEqual(premiere.status_code, 201)
        self.assertEqual(seconde.status_code, 400)
        self.assertEqual(
            RendezVousTransporteur.objects.filter(quai=self.quai).count(), 1)


class Aud214GardePythonPreserveeTests(Aud214Base):
    """Le chemin courant garde son message français immédiat (NTWMS7)."""

    def test_le_chevauchement_sequentiel_reste_une_valueerror_lisible(self):
        RendezVousTransporteur.objects.create(
            company=self.company, quai=self.quai,
            date_heure_debut=_h(self.jour, 8), date_heure_fin=_h(self.jour, 10))
        with self.assertRaises(ValueError) as ctx:
            RendezVousTransporteur.objects.create(
                company=self.company, quai=self.quai,
                date_heure_debut=_h(self.jour, 9),
                date_heure_fin=_h(self.jour, 11))
        self.assertIn('chevauche', str(ctx.exception))
