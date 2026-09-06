"""MRY2 — Étiquettes et motifs de perte standard, strictement ADDITIFS.

Deux trous réels que cette tâche ferme :
  * `seed_motifs_perte` ne sert QUE les sociétés SANS aucun motif — une liste
    déjà personnalisée n'a donc jamais reçu les motifs ajoutés après coup
    (« Locataire », « Déjà équipé »… que Meryem entend au téléphone) ;
  * `LeadTag` n'avait AUCUN seeder : chaque société démarrait sur une liste
    vide, y compris pour les deux étiquettes que la clôture de cadence écrit
    (« Injoignable 6 appels », « Devis sans suite »).

Garanties vérifiées ici : jamais un doublon, jamais la modification d'une ligne
existante, jamais une suppression, jamais de fuite entre sociétés.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import LeadTag, MotifPerte
from apps.crm.views import (
    _DEFAULT_MOTIFS_PERTE, _DEFAULT_TAGS, completer_motifs_perte, seed_tags)

User = get_user_model()


def make_company(slug, nom=None):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom or slug})
    return company


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class MotifsStandardTests(TestCase):
    def test_les_cinq_motifs_de_meryem_sont_dans_les_defauts(self):
        noms = {nom for nom, _ in _DEFAULT_MOTIFS_PERTE}
        for attendu in ('Locataire', 'Consommation trop faible',
                        'Déjà équipé', 'Ne plus contacter', 'Devis refusé'):
            self.assertIn(attendu, noms)

    def test_aucun_nouveau_motif_nest_junk(self):
        """Ce sont des pertes COMMERCIALES réelles, pas de faux prospects :
        les marquer junk fausserait le taux de junk par annonce (PUB28)."""
        junk = {nom for nom, est_junk in _DEFAULT_MOTIFS_PERTE if est_junk}
        self.assertEqual(
            junk, {'Numéro invalide', 'Spam/bot', 'Hors zone',
                   'Jamais répondu'})

    def test_completer_ajoute_les_manquants_sans_toucher_lexistant(self):
        company = make_company('mry2-complete')
        perso = MotifPerte.objects.create(
            company=company, nom='Motif perso fondateur', est_junk=True)
        completer_motifs_perte(company)
        noms = set(MotifPerte.objects.filter(company=company)
                   .values_list('nom', flat=True))
        self.assertIn('Motif perso fondateur', noms)
        self.assertIn('Locataire', noms)
        perso.refresh_from_db()
        self.assertTrue(perso.est_junk)  # jamais réécrit

    def test_completer_est_idempotent(self):
        company = make_company('mry2-idem')
        completer_motifs_perte(company)
        completer_motifs_perte(company)
        self.assertEqual(
            MotifPerte.objects.filter(company=company).count(),
            len(_DEFAULT_MOTIFS_PERTE))

    def test_completer_ne_touche_pas_les_autres_societes(self):
        une = make_company('mry2-tenant-1')
        autre = make_company('mry2-tenant-2')
        completer_motifs_perte(une)
        self.assertEqual(
            MotifPerte.objects.filter(company=autre).count(), 0)

    def test_la_liste_api_complete_une_societe_personnalisee(self):
        company = make_company('mry2-api-motifs')
        MotifPerte.objects.create(company=company, nom='Motif perso')
        user = User.objects.create_user(
            username='mry2-motifs', password='x', company=company)
        resp = make_api(user).get('/api/django/crm/motifs-perte/')
        self.assertEqual(resp.status_code, 200)
        noms = set(MotifPerte.objects.filter(company=company)
                   .values_list('nom', flat=True))
        self.assertIn('Motif perso', noms)
        self.assertIn('Ne plus contacter', noms)


class EtiquettesStandardTests(TestCase):
    def test_les_deux_etiquettes_de_cloture_sont_seedees(self):
        self.assertIn('Injoignable 6 appels', _DEFAULT_TAGS)
        self.assertIn('Devis sans suite', _DEFAULT_TAGS)
        # MRY11 — l'ancien libellé annonçait « 7 tentatives » là où le
        # Protocole v3 compte SIX appels (migration crm.0093).
        self.assertNotIn('Injoignable 7 tentatives', _DEFAULT_TAGS)

    def test_seed_tags_cree_les_defauts(self):
        company = make_company('mry2-tags')
        seed_tags(company)
        noms = set(LeadTag.objects.filter(company=company)
                   .values_list('nom', flat=True))
        self.assertEqual(noms, set(_DEFAULT_TAGS))

    def test_seed_tags_est_idempotent(self):
        company = make_company('mry2-tags-idem')
        seed_tags(company)
        seed_tags(company)
        self.assertEqual(
            LeadTag.objects.filter(company=company).count(),
            len(_DEFAULT_TAGS))

    def test_seed_tags_ne_touche_pas_une_etiquette_existante(self):
        company = make_company('mry2-tags-existant')
        tag = LeadTag.objects.create(
            company=company, nom='Déjà équipé', couleur='#ff0000',
            archived=True)
        seed_tags(company)
        tag.refresh_from_db()
        self.assertEqual(tag.couleur, '#ff0000')
        self.assertTrue(tag.archived)
        self.assertEqual(
            LeadTag.objects.filter(company=company,
                                   nom='Déjà équipé').count(), 1)

    def test_seed_tags_est_par_societe(self):
        une = make_company('mry2-tags-t1')
        autre = make_company('mry2-tags-t2')
        seed_tags(une)
        self.assertEqual(LeadTag.objects.filter(company=autre).count(), 0)

    def test_la_liste_api_amorce_les_etiquettes(self):
        company = make_company('mry2-api-tags')
        user = User.objects.create_user(
            username='mry2-tags-user', password='x', company=company)
        self.assertEqual(LeadTag.objects.filter(company=company).count(), 0)
        resp = make_api(user).get('/api/django/crm/tags/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            LeadTag.objects.filter(company=company).count(),
            len(_DEFAULT_TAGS))
