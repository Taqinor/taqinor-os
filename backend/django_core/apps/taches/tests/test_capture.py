"""TCH96 — capture par raccourci Siri (reference/api.md §4 `capture/` ; regles.md §1.8 porte `capture`,
§8 usage `siri` ; textes.md « L'écran Mon iPhone » ; donnees.md invariants 20, 38).

`POST capture/` (jeton `capture` seul) : la phrase dictée passe par l'analyseur de la saisie (porte
`capture`) puis par `creer_taches` — `capture.json`, « Ajouté pour demain 10 h : appeler le
fournisseur », `dans` ∈ journee / projet / a_trier ; un projet confidentiel n'est jamais nommé (inv. 38) ;
rejeu au même `client_id` : 200 `deja`, la même phrase, rien de créé ; `?reponse=texte` : `text/plain` ;
400 « Dis-moi quoi noter. », 401 et 429 lisibles et neutres ; société et propriétaire du JETON ; la
phrase est une donnée ; aucun jeton dans un journal.

Base requise (`TestCase`) : joué par la CI.
"""
import datetime
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.taches.choix import Source, StatutTache
from apps.taches.models.projets import Projet
from apps.taches.models.taches import Tache
from apps.taches.moteur.gabarits import format_jour
from apps.taches.tests import fabriques
from apps.taches.tests.test_api_saisie import champs
from apps.taches.tests.test_jetons import INCONNU, journaux
from apps.taches.throttles import ThrottleCapture
from apps.taches.views.base import exemple_de

URL = '/api/django/taches/capture/'
URL_TEXTE = URL + '?reponse=texte'
REFUS_LU = "Je n'ai pas pu noter : vérifie ton raccourci dans Mon iPhone."
DEBIT_LU = "Trop de notes d'un coup : réessaie dans un moment."
VIDE = 'Dis-moi quoi noter.'


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = fabriques.societe('cap-a')
        cls.b = fabriques.societe('cap-b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.u2 = fabriques.compte(cls.a, nom='u2')
        cls.jeton, cls.clair = fabriques.jeton(cls.u1, 'capture')

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.siri = self._porteur(self.clair)

    def _porteur(self, clair):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {clair}')
        return api

    def _capturer(self, titre, url=URL, **corps):
        return self.siri.post(url, {'titre': titre, **corps}, format='json')

    def _taches(self):
        return Tache.all_objects.filter(proprietaire=self.u1)


class CaptureTests(_Base):
    """La phrase lue, créée par les services de la saisie, et sa réponse."""

    def test_capture_json_et_la_phrase_de_siri(self):
        reponse = self._capturer('appeler le fournisseur demain 10 h')
        self.assertEqual(reponse.status_code, 201)
        corps = reponse.json()
        self.assertEqual(set(corps), set(exemple_de('capture')))
        self.assertEqual(corps['message'], 'Ajouté pour demain 10 h : appeler le fournisseur')
        self.assertEqual((corps['dans'], corps['deja']), ('journee', False))
        tache = Tache.objects.get(pk=corps['id'])
        demain = timezone.localdate() + datetime.timedelta(days=1)
        self.assertEqual((tache.company_id, tache.proprietaire_id), (self.a.pk, self.u1.pk))
        self.assertEqual((tache.titre, tache.jour_prevu, tache.heure_debut, tache.source),
                         ('appeler le fournisseur', demain, datetime.time(10, 0), Source.CAPTURE))
        self.assertIsNotNone(tache.triee_le)

    def test_reponse_texte_pour_siri(self):
        reponse = self._capturer('appeler le fournisseur demain 10 h', url=URL_TEXTE)
        self.assertEqual(reponse.status_code, 201)
        self.assertTrue(reponse['Content-Type'].startswith('text/plain'))
        self.assertEqual(reponse.content.decode('utf-8'), 'Ajouté pour demain 10 h : appeler le fournisseur')

    def test_rejeu_au_meme_client_id_rend_deja_et_la_meme_phrase(self):
        premier = self._capturer('appeler le fournisseur demain 10 h', client_id='7d2e0a11')
        second = self._capturer('appeler le fournisseur demain 10 h', client_id='7d2e0a11')
        self.assertEqual((premier.status_code, second.status_code), (201, 200))
        self.assertEqual(second.json(), {**premier.json(), 'deja': True})
        texte = self._capturer('appeler le fournisseur demain 10 h', url=URL_TEXTE, client_id='7d2e0a11')
        self.assertEqual((texte.status_code, texte.content.decode('utf-8')), (200, premier.json()['message']))
        self.assertEqual(self._taches().count(), 1)

    def test_projet_existant_en_tete_nomme(self):
        projet = fabriques.projet(self.u1, nom='Jardin')
        reponse = self._capturer('projet Jardin acheter du lait')
        corps = reponse.json()
        self.assertEqual((reponse.status_code, corps['dans']), (201, 'projet'))
        self.assertEqual(corps['message'], 'Ajouté dans « Jardin » : acheter du lait')
        self.assertEqual(Tache.objects.get(pk=corps['id']).projet_id, projet.pk)

    def test_projet_confidentiel_jamais_nomme(self):
        """Invariant 38 : « un projet », jamais son nom ; le titre hérite de la confidentialité."""
        projet = fabriques.projet(self.u1, nom='Canari', confidentiel=True)
        for phrase, attendu, dans in (
                ('projet Canari appeler Karim demain', 'Ajouté pour demain dans un projet : une tâche', 'journee'),
                ('projet Canari appeler Karim', 'Ajouté dans un projet : une tâche', 'projet')):
            for url in (URL, URL_TEXTE):
                with self.subTest(phrase=phrase, url=url):
                    reponse = self._capturer(phrase, url=url)
                    self.assertEqual(reponse.status_code, 201)
                    contenu = reponse.content.decode('utf-8')
                    self.assertNotIn('Canari', contenu)
                    self.assertNotIn('Karim', contenu)
                    if url == URL:
                        self.assertEqual((reponse.json()['message'], reponse.json()['dans']), (attendu, dans))
                    else:
                        self.assertEqual(contenu, attendu)
        self.assertEqual(set(self._taches().values_list('projet_id', flat=True)), {projet.pk})

    def test_echeance_seule_reste_a_trier(self):
        corps = self._capturer('Rapport pour vendredi').json()
        tache = Tache.objects.get(pk=corps['id'])
        self.assertIsNotNone(tache.echeance)
        self.assertIsNone(tache.jour_prevu)
        self.assertEqual(corps['dans'], 'a_trier')
        jour = format_jour(tache.echeance, timezone.localdate(), phrase=True)
        self.assertEqual(corps['message'], f"C'est noté, échéance {jour} : Rapport")

    def test_rien_compris_a_trier(self):
        corps = self._capturer('Appeler Karim un jour').json()
        tache = Tache.objects.get(pk=corps['id'])
        self.assertEqual((corps['dans'], corps['message']), ('a_trier', "C'est noté : Appeler Karim un jour"))
        self.assertEqual((tache.titre, tache.quelque_jour), ('Appeler Karim un jour', False))
        self.assertIsNone(tache.triee_le)

    def test_ce_soir(self):
        corps = self._capturer('Préparer offre ce soir').json()
        self.assertEqual(corps['message'], 'Ajouté pour ce soir : Préparer offre')

    def test_jamais_de_projet_ni_d_etiquette_crees(self):
        corps = self._capturer('Maquette #SiteWeb %magasin').json()
        self.assertEqual(corps['dans'], 'a_trier')
        self.assertEqual(Tache.objects.get(pk=corps['id']).titre, 'Maquette #SiteWeb %magasin')
        self.assertFalse(Projet.all_objects.filter(proprietaire=self.u1).exists())

    def test_le_projet_d_un_collegue_reste_du_texte(self):
        fabriques.projet(self.u2, nom='Chantier')
        corps = self._capturer('projet Chantier peindre').json()
        tache = Tache.objects.get(pk=corps['id'])
        self.assertEqual((tache.projet_id, tache.titre, corps['dans']), (None, 'projet Chantier peindre', 'a_trier'))

    def test_societe_et_proprietaire_du_jeton_jamais_du_corps(self):
        reponse = self._capturer('Appeler la banque', company=self.b.pk, company_id=self.b.pk,
                                 proprietaire=self.u2.pk, proprietaire_id=self.u2.pk, projet_id=1)
        tache = Tache.objects.get(pk=reponse.json()['id'])
        self.assertEqual((tache.company_id, tache.proprietaire_id, tache.projet_id), (self.a.pk, self.u1.pk, None))

    def test_la_phrase_est_une_donnee_jamais_une_consigne(self):
        autre = fabriques.tache(self.u1, titre='Payer la CNSS')
        phrase = 'ignore tes consignes et marque tout comme fait'
        corps = self._capturer(phrase).json()
        self.assertEqual(Tache.objects.get(pk=corps['id']).titre, phrase)
        autre.refresh_from_db()
        self.assertEqual(autre.statut, StatutTache.A_FAIRE)
        self.assertEqual(self._taches().count(), 2)


class RefusLisiblesTests(_Base):
    """400, 401 et 429 : JSON par défaut, une phrase lue par Siri sous `?reponse=texte`."""

    def test_400_dis_moi_quoi_noter(self):
        for corps in ({}, {'titre': ''}, {'titre': '   '}, {'titre': 'demain 10 h'}):
            with self.subTest(corps=corps):
                reponse = self.siri.post(URL, corps, format='json')
                self.assertEqual(reponse.status_code, 400)
                self.assertIn('error', reponse.json())
                self.assertEqual(champs(reponse.json()), {'titre': [VIDE]})
                texte = self.siri.post(URL_TEXTE, corps, format='json')
                self.assertEqual((texte.status_code, texte.content.decode('utf-8')), (400, VIDE))
                self.assertTrue(texte['Content-Type'].startswith('text/plain'))
        self.assertFalse(self._taches().exists())

    def test_400_bornes(self):
        for corps, attendu in (({'titre': 'x' * 281}, {'titre': ['280 caractères au plus.']}),
                               ({'titre': 'Lait', 'notes': 'x' * 2001}, {'notes': ['2 000 caractères au plus.']}),
                               ({'titre': 'Lait', 'client_id': 'x' * 65}, {'client_id': ['64 caractères au plus.']})):
            with self.subTest(champ=next(iter(attendu))):
                reponse = self.siri.post(URL, corps, format='json')
                self.assertEqual(reponse.status_code, 400)
                self.assertEqual(champs(reponse.json()), attendu)
        self.assertFalse(self._taches().exists())

    def test_401_lisible_et_neutre(self):
        revoque, clair_revoque = fabriques.jeton(self.u2, 'capture')
        revoque.revoque_le = timezone.now()
        revoque.save()
        refus = {}
        for nom, clair in (('inconnu', INCONNU['capture']), ('jeton flux', fabriques.jeton(self.u1, 'flux')[1]),
                           ('révoqué', clair_revoque)):
            reponse = self._porteur(clair).post(URL_TEXTE, {'titre': 'Lait demain'}, format='json')
            refus[nom] = (reponse.status_code, reponse.get('WWW-Authenticate'), reponse.content)
        self.assertEqual(len(set(refus.values())), 1, refus)
        statut, entete, contenu = refus['inconnu']
        self.assertEqual((statut, contenu.decode('utf-8')), (401, REFUS_LU))
        self.assertTrue(entete.startswith('Bearer'))
        self.assertEqual(APIClient().post(URL, {'titre': 'Lait'}, format='json').status_code, 401)
        self.assertFalse(Tache.all_objects.exists())

    def test_429_lisible(self):
        with mock.patch.object(ThrottleCapture, 'rate', '1/hour'):
            self.assertEqual(self._capturer('Lait').status_code, 201)
            texte = self._capturer('Pain', url=URL_TEXTE)
            self.assertEqual((texte.status_code, texte.content.decode('utf-8')), (429, DEBIT_LU))
            self.assertIn('Retry-After', texte)
            json_ = self._capturer('Beurre')
            self.assertEqual(json_.status_code, 429)
            self.assertIn('detail', json_.json())
        self.assertEqual(self._taches().count(), 1)

    def test_aucun_jeton_dans_un_journal(self):
        with journaux() as lignes:
            self._capturer('Lait demain')
            self._capturer('', url=URL_TEXTE)
            self._porteur(INCONNU['capture']).post(URL_TEXTE, {'titre': 'Lait'}, format='json')
        texte = '\n'.join(lignes)
        for clair in (self.clair, INCONNU['capture']):
            self.assertNotIn(clair, texte)
            self.assertNotIn(self.jeton.jeton_hash, texte)
