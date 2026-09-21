"""NTGRC20 — attestation de lecture des politiques internes.

Garanties : attester une version PUBLIÉE horodate CÔTÉ SERVEUR (horloge figée
dans les tests, jamais un ``timezone.now()`` vivant dans une assertion) ; le
taux d'attestation se calcule par politique sur la version courante ; une
politique en brouillon ne s'atteste pas ; tout reste scopé société.
"""
from django.test import TestCase

from apps.grc.models import AttestationPolitique, PolitiqueInterne
from apps.grc.selectors import employes_cibles, taux_attestation
from apps.grc.services import (
    AttestationImpossible, attester_politique, publier_politique,
)
from apps.rh.models import DossierEmploye
from authentication.models import Company
from testkit.base import TenantAPITestCase
from testkit.time import frozen

#: Instant de référence des assertions d'horodatage (horloge FIGÉE).
INSTANT = '2026-09-12 10:30:00+00:00'


def _dossier(company, matricule, **kw):
    params = {'nom': 'Salarie', 'prenom': matricule}
    params.update(kw)
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, **params)


class AttestationServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC20 SA', slug='ntgrc20')

    def _publiee(self, **kw):
        params = {'titre': 'Charte informatique', 'contenu': 'Texte v1'}
        params.update(kw)
        politique = PolitiqueInterne.objects.create(
            company=self.company, **params)
        publier_politique(politique, auteur='dpo')
        politique.refresh_from_db()
        return politique

    def test_attester_horodate_cote_serveur(self):
        politique = self._publiee()
        with frozen(INSTANT):
            attestation, creee = attester_politique(
                self.company, politique, employe_ref='7',
                nom_saisi='Reda Kasri')
        self.assertTrue(creee)
        self.assertEqual(attestation.version_attestee, 1)
        self.assertEqual(
            attestation.date_attestation.isoformat(),
            '2026-09-12T10:30:00+00:00')
        self.assertEqual(attestation.nom_saisi, 'Reda Kasri')
        self.assertEqual(attestation.company, self.company)

    def test_reatester_la_meme_version_est_idempotent(self):
        politique = self._publiee()
        with frozen(INSTANT):
            premiere, creee = attester_politique(
                self.company, politique, employe_ref='7', nom_saisi='Reda')
        self.assertTrue(creee)
        seconde, recreee = attester_politique(
            self.company, politique, employe_ref='7', nom_saisi='Reda')
        self.assertFalse(recreee)
        self.assertEqual(seconde.pk, premiere.pk)
        self.assertEqual(AttestationPolitique.objects.count(), 1)

    def test_une_nouvelle_version_redemande_une_attestation(self):
        politique = self._publiee()
        attester_politique(self.company, politique, employe_ref='7',
                           nom_saisi='Reda')
        politique.contenu = 'Texte v2'
        politique.save()
        publier_politique(politique)
        politique.refresh_from_db()
        _, creee = attester_politique(
            self.company, politique, employe_ref='7', nom_saisi='Reda')
        self.assertTrue(creee)
        self.assertEqual(AttestationPolitique.objects.count(), 2)

    def test_une_politique_brouillon_ne_s_atteste_pas(self):
        politique = PolitiqueInterne.objects.create(
            company=self.company, titre='Brouillon', contenu='Texte')
        with self.assertRaises(AttestationImpossible) as ctx:
            attester_politique(self.company, politique, employe_ref='7',
                               nom_saisi='Reda')
        self.assertEqual(ctx.exception.champ, 'politique')
        self.assertEqual(AttestationPolitique.objects.count(), 0)

    def test_le_nom_saisi_est_obligatoire_loi_53_05(self):
        politique = self._publiee()
        with self.assertRaises(AttestationImpossible) as ctx:
            attester_politique(self.company, politique, employe_ref='7',
                               nom_saisi='   ')
        self.assertEqual(ctx.exception.champ, 'nom_saisi')


class TauxAttestationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC20 T', slug='ntgrc20-t')
        cls.a = _dossier(cls.company, 'E1')
        cls.b = _dossier(cls.company, 'E2')
        cls.c = _dossier(cls.company, 'E3')

    def _publiee(self, **kw):
        params = {'titre': 'Charte', 'contenu': 'Texte'}
        params.update(kw)
        politique = PolitiqueInterne.objects.create(
            company=self.company, **params)
        publier_politique(politique)
        politique.refresh_from_db()
        return politique

    def test_cible_tous_couvre_les_dossiers_actifs(self):
        politique = self._publiee()
        self.assertEqual(
            employes_cibles(self.company, politique),
            {self.a.pk, self.b.pk, self.c.pk})

    def test_un_dossier_sorti_n_est_plus_dans_la_cible(self):
        politique = self._publiee()
        self.c.statut = DossierEmploye.Statut.SORTI
        self.c.save()
        self.assertEqual(
            employes_cibles(self.company, politique),
            {self.a.pk, self.b.pk})

    def test_taux_par_politique(self):
        politique = self._publiee()
        attester_politique(self.company, politique,
                           employe_ref=str(self.a.pk), nom_saisi='A')
        attester_politique(self.company, politique,
                           employe_ref=str(self.b.pk), nom_saisi='B')
        taux = taux_attestation(self.company, politique)
        self.assertEqual(taux['version'], 1)
        self.assertEqual(taux['cible'], 3)
        self.assertEqual(taux['attestants'], 2)
        self.assertEqual(taux['taux_pct'], 66.7)
        self.assertEqual(taux['manquants'], [self.c.pk])

    def test_une_politique_jamais_publiee_ne_vaut_pas_100_pct(self):
        politique = PolitiqueInterne.objects.create(
            company=self.company, titre='Brouillon', contenu='Texte')
        taux = taux_attestation(self.company, politique)
        self.assertEqual(taux['version'], 0)
        self.assertEqual(taux['cible'], 0)
        self.assertEqual(taux['attestants'], 0)
        self.assertEqual(taux['taux_pct'], 0.0)

    def test_l_attestation_d_une_ancienne_version_ne_compte_plus(self):
        politique = self._publiee()
        attester_politique(self.company, politique,
                           employe_ref=str(self.a.pk), nom_saisi='A')
        politique.contenu = 'v2'
        politique.save()
        publier_politique(politique)
        politique.refresh_from_db()
        taux = taux_attestation(self.company, politique)
        self.assertEqual(taux['version'], 2)
        self.assertEqual(taux['attestants'], 0)


class EndpointAttestationTests(TenantAPITestCase):
    BASE = '/api/django/grc/attestations-politique/'

    def setUp(self):
        super().setUp()
        self.politique = PolitiqueInterne.objects.create(
            company=self.company, titre='Charte', contenu='Texte')
        publier_politique(self.politique)
        self.politique.refresh_from_db()

    def test_attester_par_l_utilisateur_connecte(self):
        dossier = _dossier(self.company, 'E9', user=self.user)
        with frozen(INSTANT):
            r = self.client_as().post(
                f'{self.BASE}attester/',
                {'politique': self.politique.pk, 'nom_saisi': 'Reda K.'},
                format='json')
        self.assertEqual(r.status_code, 201, r.content)
        attestation = AttestationPolitique.objects.get(pk=r.data['id'])
        self.assertEqual(attestation.company, self.company)
        self.assertEqual(attestation.employe_ref, str(dossier.pk))
        self.assertEqual(attestation.version_attestee, 1)
        self.assertEqual(
            attestation.date_attestation.isoformat(),
            '2026-09-12T10:30:00+00:00')

    def test_attester_deux_fois_ne_cree_pas_deux_preuves(self):
        _dossier(self.company, 'E9', user=self.user)
        self.client_as().post(
            f'{self.BASE}attester/',
            {'politique': self.politique.pk, 'nom_saisi': 'Reda K.'},
            format='json')
        r = self.client_as().post(
            f'{self.BASE}attester/',
            {'politique': self.politique.pk, 'nom_saisi': 'Reda K.'},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(AttestationPolitique.objects.count(), 1)

    def test_attester_sans_nom_nomme_le_champ(self):
        _dossier(self.company, 'E9', user=self.user)
        r = self.client_as().post(
            f'{self.BASE}attester/',
            {'politique': self.politique.pk},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('nom_saisi', r.data)

    def test_attester_une_politique_d_une_autre_societe_est_refuse(self):
        etrangere = PolitiqueInterne.objects.create(
            company=self.other_company, titre='Etrangere', contenu='T')
        publier_politique(etrangere)
        r = self.client_as().post(
            f'{self.BASE}attester/',
            {'politique': etrangere.pk, 'nom_saisi': 'Reda'},
            format='json')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(AttestationPolitique.objects.count(), 0)

    def test_liste_scopee_societe(self):
        etrangere = PolitiqueInterne.objects.create(
            company=self.other_company, titre='Etrangere', contenu='T')
        publier_politique(etrangere)
        etrangere.refresh_from_db()
        AttestationPolitique.objects.create(
            company=self.other_company, politique=etrangere,
            version_attestee=1, employe_ref='1', nom_saisi='X')
        r = self.client_as(role='admin').get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])

    def test_pas_de_route_de_suppression(self):
        attestation = AttestationPolitique.objects.create(
            company=self.company, politique=self.politique,
            version_attestee=1, employe_ref='42', nom_saisi='X')
        r = self.client_as(role='admin').delete(
            f'{self.BASE}{attestation.pk}/')
        self.assertEqual(r.status_code, 405)

    def test_taux_attestation_par_endpoint(self):
        dossier = _dossier(self.company, 'E4')
        attester_politique(self.company, self.politique,
                           employe_ref=str(dossier.pk), nom_saisi='A')
        r = self.client_as(role='admin').get(
            f'/api/django/grc/politiques-internes/{self.politique.pk}/'
            'taux-attestation/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['cible'], 1)
        self.assertEqual(r.data['attestants'], 1)
        self.assertEqual(r.data['taux_pct'], 100.0)
