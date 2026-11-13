"""AMSG62 (D-AMSG-6) — liste, puis sur ordre neutralise, les e-mails et
téléphones des fiches du jeu de démonstration restées dans une société RÉELLE.

Les fiches visées sont lues de ``seed_demo.py`` (même source, aucune copie) :
clients par nom, prénom et partie locale de l'e-mail, fournisseurs par nom et
contact. Sans ``--appliquer`` : liste (id, nom, domaine), 0 écriture.
``--appliquer --sauf <ids>`` : e-mail ``@example.invalid`` et téléphone fictif,
une ligne de journal d'audit par fiche, par l'ORM dans une transaction.
"""
import ast
from pathlib import Path

from django.apps import apps as django_apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from authentication.models import Company
from core import audit_registry

SEED = Path(__file__).with_name('seed_demo.py')


def fiches_du_seed():
    """``(clients[(nom, prénom, partie locale)], fournisseurs[(nom, contact)])``."""
    clients, fournisseurs = [], []
    for noeud in ast.walk(ast.parse(SEED.read_text(encoding='utf-8'))):
        if isinstance(noeud, ast.Assign) and getattr(noeud.targets[0], 'id', '') == 'clients_data':
            for ligne in ast.literal_eval(noeud.value):
                clients.append((ligne[0], ligne[1], ligne[2].split('@')[0]))
        if isinstance(noeud, ast.Call) and getattr(noeud.func, 'attr', '') == 'create' \
                and getattr(noeud.func.value, 'value', None) is not None \
                and getattr(noeud.func.value.value, 'id', '') == 'Fournisseur':
            kw = {k.arg: ast.literal_eval(k.value) for k in noeud.keywords if k.arg in ('nom', 'contact_personne')}
            fournisseurs.append((kw['nom'], kw['contact_personne']))
    return clients, fournisseurs


def fiches_concernees(societe):
    Client = django_apps.get_model('crm', 'Client')
    Fournisseur = django_apps.get_model('stock', 'Fournisseur')
    clients, fournisseurs = fiches_du_seed()
    out = []
    for nom, prenom, locale in clients:
        out += Client.objects.filter(company=societe, nom=nom, prenom=prenom, email__istartswith=f'{locale}@')
    for nom, contact in fournisseurs:
        out += Fournisseur.objects.filter(company=societe, nom=nom, contact_personne=contact)
    return out


class Command(BaseCommand):
    help = "AMSG62 — liste (défaut) ou neutralise (--appliquer) les contacts du jeu de démo d'une société."

    def add_arguments(self, parser):
        parser.add_argument('--societe', required=True, help='slug de la société')
        parser.add_argument('--appliquer', action='store_true')
        parser.add_argument('--sauf', nargs='*', type=int, default=[], help='ids confirmés réels à garder')

    def handle(self, *args, **opts):
        societe = Company.objects.filter(slug=opts['societe']).first()
        if societe is None:
            raise CommandError(f"Société introuvable : {opts['societe']}")
        fiches = [f for f in fiches_concernees(societe) if f.pk not in set(opts['sauf'])]
        for f in fiches:
            domaine = (f.email or '').rpartition('@')[2] or '—'
            self.stdout.write(f'{f._meta.model_name} {f.pk} — {f.nom} — {domaine}')
        if not opts['appliquer']:
            self.stdout.write(f'{len(fiches)} fiche(s) concernée(s) — dry-run, rien écrit.')
            return
        with transaction.atomic():
            for f in fiches:
                champs = {'email': f'demo-{f._meta.model_name}-{f.pk}@example.invalid',
                          'telephone': f'+212600{f.pk % 1000000:06d}'}
                if any(c.name == 'search_vector' for c in f._meta.fields):
                    champs['search_vector'] = None  # ré-indexé (repli icontains d'ici là)
                type(f).objects.filter(pk=f.pk).update(**champs)
                audit_registry.record('update', instance=f, user=None,
                                      detail='AMSG62 — contact de démonstration neutralisé (e-mail, téléphone)')
        self.stdout.write(f'{len(fiches)} fiche(s) neutralisée(s).')
