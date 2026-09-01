# -*- coding: utf-8 -*-
"""QJR84 — UN SEUL constructeur de ``LigneDevis`` dans ``apps/ventes``.

CE QUE CES TESTS VERROUILLENT, ET POURQUOI.

Constat QB84 (audit L3 du 29/08/2026) : ``services.py`` créait des
``LigneDevis`` en direct sur quatorze sites — dix-huit une fois la vague M3
passée et les vues comptées — avec des jeux de champs légèrement différents,
pendant que les tests décrivaient ``_replace_lines_atomic`` comme « le SEUL
chemin d'écriture » des lignes. Le coût de cette divergence est mesurable et
documenté ailleurs dans ce dépôt :

  · un site qui oublie ``variante`` écrit une ligne COMMUNE là où elle devait
    servir UNE option — c'est exactement le défaut que QJR81 vient de corriger
    sur le chemin de réparation ;
  · un site qui oublie ``ordre`` laisse le tri retomber sur ``id`` et perd
    l'ordre de lignes voulu par la société (PVORD) ;
  · un site qui oublie ``prix_manuel`` / ``quantite_manuelle`` rouvre à la
    réécriture une valeur que le commercial avait TAPÉE (D12).

La parade n'est pas une convention, c'est un GOULOT : ``domain/lignes.
creer_ligne`` est le seul appel ``LigneDevis.objects.create`` de l'app, et le
jeu de champs complet y est nommé une fois (``CHAMPS_LIGNE``).

``test_un_seul_constructeur_dans_apps_ventes`` est le test qui compte : il
relit le CODE SOURCE et échoue dès qu'un second constructeur réapparaît — la
seule forme de garde qu'un futur contributeur ne peut pas contourner par
inadvertance.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_qjr_ecrivain_lignes -v 2
"""
import ast
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.stock.models import Produit
from apps.ventes.domain.lignes import CHAMPS_LIGNE, creer_ligne

User = get_user_model()

#: La racine de l'app, déduite du module lui-même (jamais un chemin en dur).
RACINE_VENTES = Path(__file__).resolve().parent.parent

#: Le SEUL site de production autorisé à appeler ``LigneDevis.objects.create``.
SITE_AUTORISE = ('domain/lignes.py', 'creer_ligne')


def _fichiers_de_production():
    """Les .py de ``apps/ventes`` hors tests, migrations et caches."""
    for chemin in sorted(RACINE_VENTES.rglob('*.py')):
        parties = set(chemin.parts)
        if 'tests' in parties or 'migrations' in parties:
            continue
        if chemin.name.startswith(('test_', 'tests_')):
            continue
        yield chemin


def _constructeurs_de_ligne(chemin):
    """Les ``(fonction, ligne)`` où ce fichier construit une ``LigneDevis``.

    Lecture AST, jamais un grep : un appel écrit sur trois lignes, ou cité dans
    un commentaire, ne doit ni échapper à la garde ni la déclencher à tort.
    """
    arbre = ast.parse(chemin.read_text(encoding='utf-8'), filename=str(chemin))
    porteurs = {}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for enfant in ast.walk(noeud):
                porteurs.setdefault(id(enfant), noeud.name)
    trouves = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        if not isinstance(cible, ast.Attribute) or cible.attr != 'create':
            continue
        source = ast.unparse(cible)
        if source.endswith('LigneDevis.objects.create') or (
                source.endswith('lignes.create')):
            trouves.append((porteurs.get(id(noeud), '<module>'), noeud.lineno))
    return trouves


class UnSeulConstructeurDeLigne(SimpleTestCase):
    """La garde STATIQUE — elle relit le code, pas la base."""

    def test_un_seul_constructeur_dans_apps_ventes(self):
        sites = []
        for chemin in _fichiers_de_production():
            relatif = chemin.relative_to(RACINE_VENTES).as_posix()
            for fonction, ligne in _constructeurs_de_ligne(chemin):
                sites.append((relatif, fonction, ligne))

        self.assertEqual(
            [(f, fn) for f, fn, _ in sites], [SITE_AUTORISE],
            'un second constructeur de LigneDevis est réapparu dans '
            'apps/ventes : %s. Passez par domain/lignes.creer_ligne — le jeu '
            'de champs complet y est nommé une fois (CHAMPS_LIGNE), et un '
            'site qui oublie variante/ordre/prix_manuel écrit une ligne '
            'silencieusement fausse.' % sites)

    def test_le_jeu_de_champs_couvre_le_modele(self):
        """``CHAMPS_LIGNE`` doit rester le jeu COMPLET : un champ métier ajouté
        au modèle et absent d'ici serait inatteignable par l'écrivain unique."""
        from apps.ventes.models import LigneDevis

        concrets = {
            champ.name for champ in LigneDevis._meta.get_fields()
            if getattr(champ, 'concrete', False)
        }
        # ``devis`` est posé par ``creer_ligne`` lui-même ; ``id`` et les
        # horodatages automatiques n'appartiennent à aucun appelant.
        techniques = {'id', 'devis', 'date_creation', 'date_modification',
                      'created_at', 'updated_at'}
        attendus = concrets - techniques
        manquants = sorted(attendus - set(CHAMPS_LIGNE))
        self.assertEqual(
            manquants, [],
            'ces champs de LigneDevis ne sont pas déclarés dans CHAMPS_LIGNE : '
            '%s — un appelant ne peut donc pas les écrire par l\'écrivain '
            'unique.' % manquants)

    def test_un_champ_inconnu_est_refuse_en_francais(self):
        with self.assertRaises(ValueError) as leve:
            creer_ligne(None, prix_unitaires=1)
        self.assertIn('Champ de ligne de devis inconnu', str(leve.exception))
        self.assertIn('prix_unitaires', str(leve.exception))

    def test_produit_et_produit_id_sexcluent(self):
        with self.assertRaises(ValueError) as leve:
            creer_ligne(None, produit=None, produit_id=1)
        self.assertIn('jamais par les deux', str(leve.exception))

    def test_lot_et_lot_id_sexcluent(self):
        with self.assertRaises(ValueError) as leve:
            creer_ligne(None, lot=None, lot_id=1)
        self.assertIn('jamais par les deux', str(leve.exception))


# ── Les sites convertis, sur de vraies lignes ───────────────────────────────

class _BaseSites(TestCase):
    slug = 'qjr84-ecrivain'

    def setUp(self):
        from authentication.models import Company
        from apps.crm.models import Client
        from apps.ventes.models import Devis

        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.user = User.objects.create_user(
            username='qjr84-%s' % self.slug, password='x',
            company=self.company, role_legacy='admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W',
            sku='QJR84-PAN-%s' % self.company.pk, prix_vente=Decimal('1100'),
            prix_achat=Decimal('1'), quantite_stock=500)
        # Devis.client est NOT NULL en base (NotNullViolation au 1er run CI).
        self.client_crm, _ = Client.objects.get_or_create(
            company=self.company, email='qjr84-%s@example.com' % self.slug,
            defaults={'nom': 'QJR84', 'prenom': self.slug,
                      'telephone': '+212600000084'})
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_crm,
            reference='DEV-QJR84-1',
            statut=Devis.Statut.BROUILLON, created_by=self.user)
        # Une ligne qui porte TOUT ce qu'un site pouvait perdre en route.
        self.ligne = creer_ligne(
            self.devis, produit=self.produit, designation='Panneau Jinko 550W',
            quantite=Decimal('12'), prix_unitaire=Decimal('980'),
            remise=Decimal('0'), ordre=3, variante='avec',
            groupe_index=2, groupe_label='Villa B', optionnelle=True,
            quantite_manuelle=True, prix_manuel=True)

    @staticmethod
    def _empreinte(ligne):
        """Ce qu'une COPIE fidèle doit reproduire, champ par champ."""
        return {
            'designation': ligne.designation,
            'quantite': ligne.quantite,
            'ordre': ligne.ordre,
            'variante': ligne.variante,
            'groupe_index': ligne.groupe_index,
            'groupe_label': ligne.groupe_label,
            'optionnelle': ligne.optionnelle,
            'quantite_manuelle': ligne.quantite_manuelle,
            'prix_manuel': ligne.prix_manuel,
        }


class LesCopiesPortentLeJeuDeChampsComplet(_BaseSites):
    """Les trois chemins qui CLONENT un devis ne perdent plus rien."""

    slug = 'qjr84-copies'

    def test_dupliquer_devis_clone_vraiment_a_l_identique(self):
        """NTUX13 dit « lignes clonées à l'identique » : ça n'était pas vrai —
        variante, optionnelle et les marqueurs D12 tombaient."""
        from apps.ventes.domain.creation import dupliquer_devis

        copie = dupliquer_devis(self.devis, user=self.user)
        clonee = copie.lignes.get()
        self.assertEqual(self._empreinte(clonee), self._empreinte(self.ligne))

    def test_creer_variante_gamme_clone_le_jeu_complet(self):
        from apps.ventes.domain.gammes import creer_variante_gamme

        soeur = creer_variante_gamme(self.devis, 'Premium', user=self.user)
        clonee = soeur.lignes.get()
        self.assertEqual(self._empreinte(clonee), self._empreinte(self.ligne))

    def test_renouveler_devis_garde_le_prix_manuel(self):
        """D12 — un renouvellement re-tarife au catalogue courant, SAUF une
        ligne dont le prix a été tapé : elle est négociée, pas périmée."""
        from apps.ventes.models import Devis
        from apps.ventes.domain.cycle_vie import renouveler_devis

        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])

        nouveau = renouveler_devis(self.devis, user=self.user)
        clonee = nouveau.lignes.get()
        self.assertEqual(self._empreinte(clonee), self._empreinte(self.ligne))
        # Le prix TAPÉ (980) survit au renouvellement — le catalogue dit 1100.
        self.assertEqual(clonee.prix_unitaire, Decimal('980.00'))

    def test_renouveler_devis_retarife_une_ligne_NON_manuelle(self):
        """Le témoin négatif : sans marqueur, NTCPQ13 re-tarife comme avant."""
        from apps.ventes.models import Devis
        from apps.ventes.domain.cycle_vie import renouveler_devis

        self.ligne.prix_manuel = False
        self.ligne.save(update_fields=['prix_manuel'])
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])

        nouveau = renouveler_devis(self.devis, user=self.user)
        self.assertEqual(nouveau.lignes.get().prix_unitaire,
                         Decimal('1100.00'))
