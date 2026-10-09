"""ADEV32 (C-ADEV-045) — aucun marqueur interne (« [Copie de DEV-…] »,
« [Variante …] », « [Gamme …] », « pièce jointe #… ») n'est plus écrit dans
``Devis.note`` (texte CLIENT, servi en ``note_client`` par la page publique et
imprimé par ``/proposal``) : il va au chatter ``DevisActivity`` de la copie.

Rejoue la sonde VB q2 : devis note vidée puis dupliqué ⇒ ``note_client
'[Copie de DEV-202609-0004]'`` dans le JSON public.

Test-du-test : remettre l'écriture ``[Copie de …]`` dans ``note`` ⇒
``test_copie`` échoue. Garde de classe (AST, paquet ventes) : aucun écrivain
de ``Devis.note`` n'y injecte de texte littéral hors liste d'exemption NOMMÉE.
"""
import ast
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisActivity, LigneDevis, ShareLink
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
VENTES = Path(__file__).resolve().parent.parent
MARQUEURS = ('[Copie de', '[Variante', '[Gamme', 'pièce jointe #')


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class NoteClientSansMarqueurTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ADEV32 Co',
                                              slug='adev32-co')
        self.user = User.objects.create_user(
            username='adev32_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV32',
            email='adev32@example.test', telephone='+212600003232')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='ADEV32-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 5kW',
            sku='ADEV32-OND', prix_vente=Decimal('3000'),
            prix_achat=Decimal('2000'), quantite_stock=100)
        self.source = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-3201',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.user, note='')
        for produit, qte, pu in ((self.panneau, '10', '1000'),
                                 (self.onduleur, '1', '3000')):
            LigneDevis.objects.create(
                devis=self.source, produit=produit,
                designation=produit.nom, quantite=Decimal(qte),
                prix_unitaire=Decimal(pu), remise=Decimal('0'))
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _note_client_publique(self, devis):
        # La copie naît brouillon : on la considère envoyée pour lire le vrai
        # payload public (la note n'est pas touchée par cet UPDATE).
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ENVOYE)
        lien = ShareLink.for_devis(devis)
        r = APIClient().get(f'/api/django/ventes/proposal/{lien.token}/')
        self.assertEqual(r.status_code, 200, r.content)
        return r.data['note_client']

    def _sans_marqueur(self, devis, trace):
        devis.refresh_from_db()
        # CLAUSE PERSISTANCE — relu en base.
        for m in MARQUEURS:
            self.assertNotIn(m, devis.note or '')
        # CLAUSE CLIENT — le vrai payload public.
        note_client = self._note_client_publique(devis) or ''
        for m in MARQUEURS:
            self.assertNotIn(m, note_client)
        # Le marqueur est au chatter.
        self.assertTrue(DevisActivity.objects.filter(
            devis=devis, body__contains=trace).exists(), trace)

    def test_copie(self):
        from apps.ventes.domain.creation_clone import dupliquer_devis
        copie = dupliquer_devis(self.source, user=self.user)
        self.assertEqual(copie.note, '')
        self._sans_marqueur(copie, f'Copie de {self.source.reference}')

    def test_copie_garde_la_note_client(self):
        from apps.ventes.domain.creation_clone import dupliquer_devis
        Devis.objects.filter(pk=self.source.pk).update(
            note='Pose prévue en mars.')
        self.source.refresh_from_db()
        copie = dupliquer_devis(self.source, user=self.user)
        self.assertEqual(self._note_client_publique(copie),
                         'Pose prévue en mars.')

    def test_variante(self):
        r = self.api.post(
            f'/api/django/ventes/devis/{self.source.pk}/dupliquer-variante/',
            {'scales': [0.8]}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        variante = Devis.objects.get(pk=r.data[0]['id'])
        self._sans_marqueur(variante, 'Variante')

    def test_gamme(self):
        from apps.ventes.domain.gammes import creer_variante_gamme
        soeur = creer_variante_gamme(self.source, 'Premium', user=self.user)
        self._sans_marqueur(soeur, 'Gamme Premium')

    def test_reserve(self):
        from apps.installations.models import Installation, Intervention
        from apps.ventes.domain.gammes import create_devis_from_reserve
        installation = Installation.objects.create(
            company=self.company, reference='CHT-ADEV32-1',
            client=self.client_obj)
        intervention = Intervention.objects.create(
            company=self.company, installation=installation,
            type_intervention='depannage', created_by=self.user)
        # Réserve avec photo : ``photo_id`` suffit au service (aucune lecture
        # de la pièce jointe) — pas de fichier à stocker ici.
        reserve = SimpleNamespace(
            id=3201, company=self.company, intervention=intervention,
            description='Fissure sur le rail de fixation.', photo_id=4242)
        devis = create_devis_from_reserve(reserve=reserve, user=self.user)
        self.assertEqual(devis.note, 'Fissure sur le rail de fixation.')
        self.assertTrue(DevisActivity.objects.filter(
            devis=devis, body__contains='pièce jointe #4242').exists())
        devis.refresh_from_db()
        for m in MARQUEURS:
            self.assertNotIn(m, devis.note)


# ── Garde de classe : aucun écrivain de ``Devis.note`` n'y injecte de texte ──

#: Écrivains (``module:fonction``) qui pré-remplissent ``Devis.note`` d'un
#: texte d'ORIGINE — hors périmètre ADEV32 (signalé au groupe ADEV) : chacun
#: est NOMMÉ ici avec sa raison, jamais ignoré en silence.
EXEMPTIONS = {
    'domain/creation.py:create_devis_upsell_from_intervention':
        'upsell : référence chantier attendue par tests_zfsm5 (installations).',
    'domain/imports.py:creer_devis_import':
        "import d'un autre système : référence source (« Migré … »).",
}


def _texte_litteral(noeud):
    """Le nœud porte-t-il du texte LITTÉRAL non vide (marqueur possible) ?"""
    for sous in ast.walk(noeud):
        if isinstance(sous, ast.JoinedStr):
            return True
        if (isinstance(sous, ast.Constant) and isinstance(sous.value, str)
                and sous.value.strip()):
            return True
    return False


def _ecrit_devis_note(appel):
    """``Devis.objects.create(note=…)`` ou ``cloner_devis(note=…)``."""
    f = appel.func
    if isinstance(f, ast.Name) and f.id == 'cloner_devis':
        return True
    if isinstance(f, ast.Attribute) and f.attr == 'cloner_devis':
        return True
    return (isinstance(f, ast.Attribute) and f.attr == 'create'
            and isinstance(f.value, ast.Attribute)
            and f.value.attr == 'objects'
            and isinstance(f.value.value, ast.Name)
            and f.value.value.id == 'Devis')


def _ecrivains_avec_texte():
    trouves = set()
    for chemin in sorted(VENTES.rglob('*.py')):
        rel = chemin.relative_to(VENTES).as_posix()
        if rel.startswith(('tests/', 'migrations/')) or '/tests/' in rel:
            continue
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        # Fonctions de niveau module et méthodes de classe : une fonction
        # imbriquée (``_create`` passé à ``create_numbered``) est parcourue
        # avec son englobante, qui porte souvent l'affectation de la note.
        fonctions = [n for n in arbre.body
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for classe in arbre.body:
            if isinstance(classe, ast.ClassDef):
                fonctions += [
                    n for n in classe.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for fonction in fonctions:
            affectations = {}
            for n in ast.walk(fonction):
                if isinstance(n, ast.Assign):
                    for cible in n.targets:
                        if isinstance(cible, ast.Name):
                            affectations.setdefault(cible.id, []).append(
                                n.value)

            def _suspect(valeur, _aff=affectations):
                if _texte_litteral(valeur):
                    return True
                if isinstance(valeur, ast.Name):
                    return any(_texte_litteral(v)
                               for v in _aff.get(valeur.id, ()))
                return False

            for n in ast.walk(fonction):
                if isinstance(n, ast.Call) and _ecrit_devis_note(n):
                    for kw in n.keywords:
                        if kw.arg == 'note' and _suspect(kw.value):
                            trouves.add(f'{rel}:{fonction.name}')
                if isinstance(n, ast.Assign):
                    for cible in n.targets:
                        if (isinstance(cible, ast.Attribute)
                                and cible.attr == 'note'
                                and isinstance(cible.value, ast.Name)
                                and 'devis' in cible.value.id.lower()
                                and _suspect(n.value)):
                            trouves.add(f'{rel}:{fonction.name}')
    return trouves


class GardeEcrivainsNoteTests(SimpleTestCase):

    def test_aucun_marqueur_injecte_dans_la_note(self):
        trouves = _ecrivains_avec_texte()
        non_exemptes = sorted(t for t in trouves if t not in EXEMPTIONS)
        self.assertEqual(
            non_exemptes, [],
            'Écrivain de Devis.note qui injecte un texte littéral (marqueur '
            'interne ?) : écrire au chatter DevisActivity, ou déclarer '
            "l'écrivain dans EXEMPTIONS avec sa raison.")

    def test_exemptions_vivantes(self):
        """Une exemption qui ne correspond plus à rien est retirée."""
        trouves = _ecrivains_avec_texte()
        self.assertEqual(sorted(e for e in EXEMPTIONS if e not in trouves),
                         [])
