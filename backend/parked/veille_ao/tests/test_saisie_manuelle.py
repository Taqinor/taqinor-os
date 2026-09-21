"""VAO27 — la porte MANUELLE : la leçon FRDISI.

L'appel d'offres qui a réellement occupé le fondateur n'est passé par AUCUN
portail : il est arrivé par un partenaire, sur une liste d'invitation, et
aucun dispositif de veille — gratuit ou payant — ne l'aurait fait remonter.
La porte automatique ne peut donc jamais être la seule.

Le « Done = » :
  * création manuelle en 4 champs ;
  * informateur OBLIGATOIRE (400 FR sinon) ;
  * l'avis manuel entre dans le MÊME sas et suit le MÊME cycle ;
  * dédoublonnage de niveau 2 appliqué (VAO11) — saisi puis collecté, il
    FUSIONNE au lieu de doubler.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.roles.models import Role

from apps.veille_ao.models import (
    AvisMarche, Informateur, MotCleVeille, NiveauMotCle, SourceVeille,
    StatutAvis, TypeSource,
)
from apps.veille_ao.services import (
    changer_statut_avis, collecter, creer_avis_manuel, resoudre_source,
)

URL = '/api/django/veille_ao/avis/'


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME Manuel')
        MotCleVeille.objects.create(
            company=self.company, libelle='solaire',
            niveau=NiveauMotCle.NOYAU, poids=10, actif=True)

    def _api(self, permissions=('veille_ao_voir', 'veille_ao_gerer')):
        role = Role.objects.create(
            company=self.company, nom='Rôle saisie',
            permissions=list(permissions))
        user = CustomUser.objects.create_user(
            username='vao_saisie', password='x', company=self.company,
            role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api


class InformateurObligatoireTests(_Base):
    def test_sans_informateur_la_saisie_est_refusee_en_francais(self):
        with self.assertRaises(ValidationError) as capture:
            creer_avis_manuel(self.company, {'objet': 'Pompage solaire'})
        message = str(capture.exception.detail['informateur'][0])
        self.assertIn('obligatoire', message)
        self.assertIn('signalé', message)
        self.assertEqual(AvisMarche.objects.count(), 0)

    def test_un_informateur_inconnu_est_refuse_en_nommant_les_valeurs(self):
        with self.assertRaises(ValidationError) as capture:
            creer_avis_manuel(self.company, {
                'objet': 'Pompage solaire', 'informateur': 'pigeon'})
        message = str(capture.exception.detail['informateur'][0])
        self.assertIn('partenaire', message)

    def test_l_endpoint_refuse_en_400_avec_le_message_FR(self):
        api = self._api()
        reponse = api.post(URL, {'objet': 'Pompage solaire'}, 'json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('informateur', reponse.data)


class QuatreChampsTests(_Base):
    """« Aucune validation qui bloque une saisie faite depuis un chantier. »"""

    def test_quatre_champs_suffisent(self):
        avis, cree = creer_avis_manuel(self.company, {
            'objet': 'Pompage solaire à Figuig',
            'acheteur': 'Commune de Figuig',
            'date_limite_remise': timezone.now() + timedelta(days=20),
            'informateur': Informateur.PARTENAIRE,
        })
        self.assertTrue(cree)
        self.assertEqual(avis.informateur, Informateur.PARTENAIRE)
        self.assertEqual(avis.statut, StatutAvis.NOUVEAU)

    def test_sans_date_ni_reference_la_saisie_passe_quand_meme(self):
        avis, cree = creer_avis_manuel(self.company, {
            'acheteur': 'FRDISI', 'informateur': Informateur.PARTENAIRE})
        self.assertTrue(cree)
        self.assertIsNone(avis.date_limite_remise)

    def test_ni_objet_ni_acheteur_est_le_SEUL_autre_refus(self):
        """Un avis sans objet NI acheteur serait introuvable dans le sas."""
        with self.assertRaises(ValidationError):
            creer_avis_manuel(self.company, {
                'informateur': Informateur.PARTENAIRE})

    def test_l_avis_manuel_est_scoré_comme_les_autres(self):
        avis, _ = creer_avis_manuel(self.company, {
            'objet': 'Pompage solaire', 'informateur': Informateur.CLIENT})
        self.assertEqual(avis.score, 10)
        self.assertEqual(avis.mots_cles_declenches, ['solaire'])


class SourceParTypeTests(_Base):
    """Une saisie de chantier ne connaît pas la clé primaire d'une source."""

    def test_le_code_de_type_cree_la_porte_humaine_a_la_volee(self):
        source = resoudre_source(self.company, 'tuyau_partenaire')
        self.assertEqual(source.type_source, TypeSource.TUYAU_PARTENAIRE)
        self.assertTrue(source.actif)

    def test_la_resolution_par_type_est_idempotente(self):
        resoudre_source(self.company, 'tuyau_partenaire')
        resoudre_source(self.company, 'tuyau_partenaire')
        self.assertEqual(SourceVeille.objects.filter(
            company=self.company,
            type_source=TypeSource.TUYAU_PARTENAIRE).count(), 1)

    def test_une_source_reseau_creee_a_la_volee_naît_DESARMEE(self):
        """Règle #5 : rien de collectable ne s'active tout seul."""
        source = resoudre_source(self.company, 'portail_officiel')
        self.assertFalse(source.actif)

    def test_l_identifiant_technique_marche_aussi(self):
        existante = SourceVeille.objects.create(
            company=self.company, code='perso', libelle='Ma source',
            type_source=TypeSource.TUYAU_PARTENAIRE, actif=True)
        self.assertEqual(
            resoudre_source(self.company, str(existante.pk)), existante)

    def test_la_source_d_une_AUTRE_societe_est_introuvable(self):
        autre = Company.objects.create(nom='Autre société')
        etrangere = SourceVeille.objects.create(
            company=autre, code='perso', libelle='Ailleurs',
            type_source=TypeSource.TUYAU_PARTENAIRE, actif=True)
        with self.assertRaises(ValidationError):
            resoudre_source(self.company, str(etrangere.pk))

    def test_un_type_inconnu_est_refuse_en_nommant_les_valeurs(self):
        with self.assertRaises(ValidationError) as capture:
            resoudre_source(self.company, 'pigeon_voyageur')
        self.assertIn('tuyau_partenaire',
                      str(capture.exception.detail['source'][0]))


class MemeSasMemeCycleTests(_Base):
    def test_un_avis_manuel_suit_le_MEME_cycle_de_statuts(self):
        avis, _ = creer_avis_manuel(self.company, {
            'objet': 'Pompage solaire', 'informateur': Informateur.PARTENAIRE})
        changer_statut_avis(avis, StatutAvis.RETENU, motif='Intéressant')
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.RETENU)

    def test_saisi_puis_COLLECTE_l_avis_FUSIONNE_au_lieu_de_doubler(self):
        """Dédoublonnage de NIVEAU 2 (VAO11) : le filet traverse les sources."""
        limite = timezone.now() + timedelta(days=20)
        creer_avis_manuel(self.company, {
            'reference_avis': 'AO-2026-042',
            'objet': 'Pompage solaire à Figuig',
            'acheteur': 'Commune de Figuig',
            'date_limite_remise': limite,
            'informateur': Informateur.PARTENAIRE,
        })

        portail = SourceVeille.objects.create(
            company=self.company, code='pmmp', libelle='Portail',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test/', actif=True)
        collecter(portail, self.company, lecteur=lambda s, m: [{
            'ref_consultation': '9001', 'org_acronyme': 'FIG',
            'reference_avis': 'AO-2026-042',
            'objet': 'Pompage solaire à Figuig',
            'acheteur': 'Commune de Figuig',
            'date_limite_remise': limite,
        }])

        self.assertEqual(AvisMarche.objects.filter(
            company=self.company).count(), 1)
        avis = AvisMarche.objects.get(company=self.company)
        # Le tuyau n'est JAMAIS effacé par la collecte : c'est la matière de
        # la mesure d'attribution (VAO31).
        self.assertEqual(avis.informateur, Informateur.PARTENAIRE)
        self.assertEqual(avis.ref_consultation, '9001')

    def test_collecte_PUIS_signale_a_la_main_l_avis_GAGNE_son_tuyau(self):
        portail = SourceVeille.objects.create(
            company=self.company, code='pmmp', libelle='Portail',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test/', actif=True)
        limite = timezone.now() + timedelta(days=20)
        collecter(portail, self.company, lecteur=lambda s, m: [{
            'ref_consultation': '9002', 'reference_avis': 'AO-2026-043',
            'objet': 'Pompage solaire', 'acheteur': 'Commune X',
            'date_limite_remise': limite,
        }])

        creer_avis_manuel(self.company, {
            'reference_avis': 'AO-2026-043', 'objet': 'Pompage solaire',
            'acheteur': 'Commune X', 'date_limite_remise': limite,
            'informateur': Informateur.CLIENT})

        self.assertEqual(AvisMarche.objects.count(), 1)
        self.assertEqual(AvisMarche.objects.get().informateur,
                         Informateur.CLIENT)


class EndpointTests(_Base):
    def test_l_ecran_cree_un_avis_avec_les_noms_qu_il_publie(self):
        """Le contrat que l'écran envoie réellement : ``date_limite``,
        ``informateur``, et ``source`` en code de TYPE."""
        api = self._api()
        reponse = api.post(URL, {
            'objet': 'Pompage solaire à Figuig',
            'acheteur': 'Commune de Figuig',
            'date_limite': '2026-12-20',
            'informateur': 'partenaire',
            'source': 'tuyau_partenaire',
        }, 'json')

        self.assertEqual(reponse.status_code, 201, reponse.data)
        avis = AvisMarche.objects.get(company=self.company)
        self.assertEqual(avis.informateur, Informateur.PARTENAIRE)
        self.assertEqual(avis.source.type_source, TypeSource.TUYAU_PARTENAIRE)
        self.assertIsNotNone(avis.date_limite_remise)

    def test_la_societe_est_FORCEE_serveur_jamais_lue_du_corps(self):
        autre = Company.objects.create(nom='Autre société')
        api = self._api()
        api.post(URL, {
            'objet': 'Pompage solaire', 'informateur': 'partenaire',
            'company': autre.pk}, 'json')
        self.assertEqual(AvisMarche.objects.get().company, self.company)

    def test_la_lecture_expose_les_alias_que_l_ecran_consomme(self):
        creer_avis_manuel(self.company, {
            'objet': 'Pompage solaire', 'informateur': Informateur.PARTENAIRE,
            'date_limite_remise': timezone.now() + timedelta(days=5)})
        api = self._api()

        reponse = api.get(URL)

        corps = reponse.data
        lignes = corps['results'] if isinstance(corps, dict) else corps
        ligne = lignes[0]
        for cle in ('date_limite', 'cree_le', 'informateur', 'source',
                    'source_libelle'):
            self.assertIn(cle, ligne, cle)
        self.assertIsInstance(ligne['source'], int)
