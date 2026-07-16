"""ARC18/19 — Backfill idempotent du répertoire unifié ``Tiers``.

Pour chaque enregistrement historique porteur d'une identité (crm.Client,
stock.Fournisseur — ARC18 ; crm.Partenaire [ODX13 : ex-compta.Partenaire],
rh.DossierEmploye — ARC19),
crée OU rattache son ``Tiers`` miroir, pose les drapeaux de rôle et écrit le
lien retour ``<modèle>.tiers``. La déduplication (email/ICE) est STRICTEMENT
company-scopée : deux sociétés partageant un même email/ICE gardent des Tiers
séparés.

``tiers`` reste une couche fondation : ce module n'IMPORTE aucun modèle de
domaine (contrat ``tiers-is-a-base-layer``) — il les résout paresseusement via
``django.apps.apps.get_model`` (même motif que
``core.management.commands.export_anonymise``).

Idempotent & additif : un second passage retrouve chaque Tiers par email/ICE
(ou par le lien ``tiers`` déjà posé) et ne duplique rien — il ne fait que
compléter les trous. Aucune donnée existante n'est écrasée ; l'identité reste
maître côté modèle historique (pont réversible — la bascule write-path est la
décision ARC21).

Rapport chiffré (« backfill 100 % ») : la commande imprime, par modèle et au
total, le nombre d'enregistrements traités / Tiers créés / rattachés (dédup) /
liens déjà présents.

    docker compose exec django_core python manage.py backfill_tiers
    (option --company-slug pour se limiter à une société)
"""
from django.apps import apps as django_apps
from django.core.management.base import BaseCommand
from django.db import transaction


def _type_client(client):
    return 'entreprise' if client.type_client == 'entreprise' else 'particulier'


def _fields_client(client):
    """Champs d'identité miroités depuis un ``crm.Client``."""
    type_tiers = _type_client(client)
    return {
        'nom': client.nom or '',
        'roles': ('is_client',),
        'email': client.email or '',
        'ice': client.ice or '',
        'type_tiers': type_tiers,
        'prenom': client.prenom or '',
        'raison_sociale': client.nom or '' if type_tiers == 'entreprise' else '',
        'telephone': client.telephone or '',
        'adresse': client.adresse or '',
        'rc': client.rc or '',
        'identifiant_fiscal': client.if_fiscal or '',
        'cin': client.cin or '',
    }


def _fields_fournisseur(fournisseur):
    """Champs d'identité miroités depuis un ``stock.Fournisseur``."""
    roles = ['is_fournisseur']
    if fournisseur.type in ('service', 'mixte'):
        roles.append('is_soustraitant')
    type_tiers = 'entreprise' if (fournisseur.ice or '').strip() \
        else 'particulier'
    return {
        'nom': fournisseur.nom or '',
        'roles': tuple(roles),
        'email': fournisseur.email or '',
        'ice': fournisseur.ice or '',
        'type_tiers': type_tiers,
        'raison_sociale': (fournisseur.nom or ''
                           if type_tiers == 'entreprise' else ''),
        'telephone': fournisseur.telephone or '',
        'adresse': fournisseur.adresse or '',
        'rc': fournisseur.rc or '',
        'identifiant_fiscal': fournisseur.identifiant_fiscal or '',
        'rib': fournisseur.rib or '',
    }


def _fields_partenaire(partenaire):
    """ARC19 — Champs d'identité miroités depuis un ``crm.Partenaire`` (ODX13
    — rapatrié de compta, même modèle historique)."""
    return {
        'nom': partenaire.nom or '',
        'roles': ('is_partenaire',),
        'email': partenaire.email or '',
        'type_tiers': 'entreprise',
        'raison_sociale': partenaire.nom or '',
        'telephone': partenaire.telephone or '',
    }


def _fields_dossier(dossier):
    """ARC19 — Champs d'identité miroités depuis un ``rh.DossierEmploye``
    (partie INTERNE : aucun rôle commercial, JAMAIS de RIB — voir ARC25)."""
    return {
        'nom': dossier.nom or '',
        'roles': (),
        'email': dossier.email or '',
        'type_tiers': 'particulier',
        'prenom': dossier.prenom or '',
        'telephone': dossier.telephone or '',
        'cin': dossier.cin or '',
    }


# Registre (modèle → extracteur de champs). Le moteur ci-dessous est agnostique
# du modèle : ajouter une source = ajouter une ligne ici + un extracteur.
_SOURCES = [
    ('crm', 'Client', _fields_client),          # ARC18
    ('stock', 'Fournisseur', _fields_fournisseur),  # ARC18
    ('crm', 'Partenaire', _fields_partenaire),      # ARC19 (ODX13: ex-compta)
    ('rh', 'DossierEmploye', _fields_dossier),      # ARC19
]


class Command(BaseCommand):
    help = ('ARC18/19 — Backfill idempotent du répertoire unifié Tiers depuis '
            'les modèles historiques (Client, Fournisseur, Partenaire, '
            'DossierEmploye). Company-scopé, additif, sans écrasement.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-slug', default=None,
            help='Limite le backfill à une société (slug). Défaut : toutes.')
        parser.add_argument(
            '--dry-run', action='store_true', default=False,
            help='Simule (aucune écriture) et imprime seulement le rapport.')

    def _company_filter(self, model, company):
        qs = model.objects.all()
        if company is not None:
            qs = qs.filter(company=company)
        return qs

    def handle(self, *args, **options):
        from apps.tiers import services as tiers_services

        company = None
        slug = options.get('company_slug')
        if slug:
            Company = django_apps.get_model('authentication', 'Company')
            company = Company.objects.filter(slug=slug).first()
            if company is None:
                self.stderr.write(self.style.ERROR(
                    f"Société introuvable pour le slug « {slug} »."))
                return

        dry_run = options.get('dry_run', False)
        totaux = {'traites': 0, 'crees': 0, 'rattaches': 0, 'deja_lies': 0}

        for app_label, model_name, extract in _SOURCES:
            try:
                model = django_apps.get_model(app_label, model_name)
            except LookupError:
                # Un modèle absent (app non installée) est simplement ignoré.
                continue

            stats = {'traites': 0, 'crees': 0, 'rattaches': 0, 'deja_lies': 0}
            for obj in self._company_filter(model, company).iterator():
                if getattr(obj, 'company_id', None) is None:
                    continue  # jamais de Tiers hors société (isolation tenant).
                stats['traites'] += 1
                champs = extract(obj)
                if dry_run:
                    # On ne mesure que « déjà lié » vs « à (re)lier » sans écrire.
                    if getattr(obj, 'tiers_id', None):
                        stats['deja_lies'] += 1
                    continue
                with transaction.atomic():
                    # Réutilise le Tiers déjà lié (idempotence pour les
                    # enregistrements sans clé de dédup email/ICE).
                    existant = getattr(obj, 'tiers', None) \
                        if getattr(obj, 'tiers_id', None) else None
                    tiers, cree = tiers_services.attacher_ou_creer_tiers(
                        company=obj.company, tiers_existant=existant, **champs)
                    if getattr(obj, 'tiers_id', None) == tiers.id:
                        stats['deja_lies'] += 1
                    else:
                        model.objects.filter(pk=obj.pk).update(tiers=tiers)
                        if cree:
                            stats['crees'] += 1
                        else:
                            stats['rattaches'] += 1

            for k in totaux:
                totaux[k] += stats[k]
            self.stdout.write(
                f"{app_label}.{model_name} : {stats['traites']} traité(s) — "
                f"{stats['crees']} créé(s), {stats['rattaches']} rattaché(s), "
                f"{stats['deja_lies']} déjà lié(s).")

        prefixe = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f"{prefixe}Total : {totaux['traites']} enregistrement(s) — "
            f"{totaux['crees']} Tiers créé(s), {totaux['rattaches']} "
            f"rattaché(s) (dédup), {totaux['deja_lies']} déjà lié(s)."))
