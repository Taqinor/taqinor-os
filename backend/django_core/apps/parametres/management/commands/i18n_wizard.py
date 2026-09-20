"""NTI18N32 — ``manage.py i18n_wizard <fichier.jsx>``.

Outil INTERNE pour développeurs (aucun écran UI) : liste les littéraux FR
détectés dans un fichier JSX donné, propose une clé ``domaine.section.
libelle`` générée automatiquement, et — après confirmation — écrit le
remplacement dans le fichier ET l'entrée dans les 3 catalogues
(``frontend/src/i18n/catalogs/{fr,en,ar}.json`` : fr obligatoire,
en/ar avec ``TODO_TRADUCTION`` explicite). Accélère le rollout NTI18N1 sans
automatiser la traduction elle-même.

Usage ::

    python manage.py i18n_wizard frontend/src/features/ventes/DevisForm.jsx
    python manage.py i18n_wizard <fichier.jsx> --yes        # confirme tout
    python manage.py i18n_wizard <fichier.jsx> --dry-run    # liste seulement
    python manage.py i18n_wizard <fichier.jsx> --catalogs-dir <dossier>

Logique de détection/remplacement : ``apps.parametres.i18n_wizard_core``
(pure, testée séparément — voir sa docstring pour les limites assumées).
"""
import json
import os

from django.core.management.base import BaseCommand, CommandError

from apps.parametres.i18n_wizard_core import (
    appliquer_remplacements,
    domaine_et_section,
    entrees_catalogues,
    litteraux_candidats,
    proposer_cle,
)

#: Dossier des 3 catalogues JSON par défaut — calculé depuis l'emplacement de
#: CE fichier (backend/django_core/apps/parametres/management/commands/) vers
#: frontend/src/i18n/catalogs/ à la racine du dépôt.
_CATALOGS_DIR_DEFAUT = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    '..', '..', '..', '..', '..', '..',
    'frontend', 'src', 'i18n', 'catalogs'))


class Command(BaseCommand):
    help = (
        "Détecte les littéraux FR d'un fichier JSX, propose une clé i18n "
        'par littéral et écrit le remplacement + les 3 catalogues (fr '
        'obligatoire, en/ar TODO_TRADUCTION) après confirmation.')

    def add_arguments(self, parser):
        parser.add_argument('fichier_jsx')
        parser.add_argument(
            '--yes', action='store_true',
            help='Confirme automatiquement chaque littéral (non-interactif).')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Liste les littéraux candidats sans rien écrire.')
        parser.add_argument(
            '--catalogs-dir', default=_CATALOGS_DIR_DEFAUT,
            help='Dossier des 3 catalogues JSON (défaut : '
                 'frontend/src/i18n/catalogs).')

    def handle(self, *args, **options):
        chemin = options['fichier_jsx']
        if not os.path.isfile(chemin):
            raise CommandError(f'Fichier introuvable : {chemin}')

        with open(chemin, encoding='utf-8') as f:
            contenu = f.read()

        candidats = litteraux_candidats(contenu)
        if not candidats:
            self.stdout.write('Aucun littéral FR candidat détecté.')
            return

        domaine, section = domaine_et_section(chemin)
        confirmes = []
        for candidat in candidats:
            cle = proposer_cle(domaine, section, candidat['texte'])
            self.stdout.write(f"« {candidat['texte']} » -> {cle}")
            if options['dry_run']:
                continue
            if options['yes']:
                ok = True
            else:
                reponse = input(
                    'Remplacer par cette clé ? [O/n] ').strip().lower()
                ok = reponse in ('', 'o', 'oui', 'y', 'yes')
            if ok:
                confirmes.append({**candidat, 'cle': cle})

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'{len(candidats)} littéral(aux) détecté(s) — dry-run, '
                'aucune écriture.'))
            return
        if not confirmes:
            self.stdout.write(self.style.WARNING(
                'Aucun littéral confirmé — aucune écriture.'))
            return

        nouveau_contenu = appliquer_remplacements(contenu, confirmes)
        with open(chemin, 'w', encoding='utf-8') as f:
            f.write(nouveau_contenu)

        entrees = entrees_catalogues(confirmes)
        catalogs_dir = options['catalogs_dir']
        for langue, valeurs in entrees.items():
            chemin_catalogue = os.path.join(catalogs_dir, f'{langue}.json')
            with open(chemin_catalogue, encoding='utf-8') as f:
                catalogue = json.load(f)
            catalogue.update(valeurs)
            with open(chemin_catalogue, 'w', encoding='utf-8') as f:
                json.dump(
                    catalogue, f, ensure_ascii=False, indent=2, sort_keys=True)
                f.write('\n')

        self.stdout.write(self.style.SUCCESS(
            f'{len(confirmes)} littéral(aux) remplacé(s) dans {chemin} ; '
            f'{len(confirmes)} entrée(s) ajoutée(s) aux 3 catalogues '
            f'({catalogs_dir}). Pensez à vérifier que `t` est en scope '
            "(useT()) dans le composant modifié."))
