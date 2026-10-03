"""AGR622 — audit EN LECTURE SEULE des garanties pompe / variateur.

La migration 0012 a posé ``garantie_mois = 24`` sur toutes les pompes et tous
les variateurs par simple mot-clé ; la migration 0124 a vidé leur texte
« Garantie constructeur 2 ans », jugé SANS source, sans toucher à cette durée.
Cette commande LISTE les produits pompe / variateur (rôles AGR7 :
``role_pompage`` ∈ {pompe, variateur_pompage} quand le champ existe et est
saisi ; sinon repli sur le nom — classement « nom » du contrat
``produit_pompage.json``) avec ``garantie_mois`` et le texte ``garantie``, et
SIGNALE « durée sans texte source ». Elle n'écrit RIEN : la correction est une
décision du fondateur, dans la fiche produit. Aucun prix n'est affiché.

Run:
    docker compose exec django_core python manage.py audit_garanties_pompage \
        [--company-slug <slug>]
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.stock.models import Produit

ROLES_AUDITES = ('pompe', 'variateur_pompage')
SIGNAL_SANS_SOURCE = 'durée sans texte source'


def _a_le_champ_role():
    return any(f.name == 'role_pompage' for f in Produit._meta.get_fields())


def classer_produit(produit, champ_role=None):
    """Renvoie (role, classement) pour une pompe / un variateur, sinon
    (None, None). ``classement`` = « declare » (role_pompage saisi) ou
    « nom » (repli sur le nom/la marque)."""
    if champ_role is None:
        champ_role = _a_le_champ_role()
    if champ_role:
        role = (getattr(produit, 'role_pompage', '') or '').strip()
        if role:
            return (role, 'declare') if role in ROLES_AUDITES else (None, None)
    nom = (produit.nom or '').lower()
    marque = (getattr(produit, 'marque', '') or '').lower()
    if 'pompe' in nom:
        return 'pompe', 'nom'
    if 'variateur' in nom or 'veichi' in marque:
        return 'variateur_pompage', 'nom'
    return None, None


def audit_garanties_pompage(company_slug=None):
    """Liste (lecture seule) des pompes / variateurs et de leur garantie."""
    qs = Produit.objects.filter(company__isnull=False).select_related(
        'company').order_by('company__slug', 'nom', 'id')
    if company_slug:
        qs = qs.filter(company__slug=company_slug)
    champ_role = _a_le_champ_role()
    lignes = []
    for produit in qs:
        role, classement = classer_produit(produit, champ_role)
        if role is None:
            continue
        texte = (produit.garantie or '').strip()
        signaux = []
        if produit.garantie_mois and not texte:
            signaux.append(SIGNAL_SANS_SOURCE)
        lignes.append({
            'societe': produit.company.slug,
            'produit_id': produit.id,
            'nom': produit.nom,
            'role': role,
            'classement': classement,
            'garantie_mois': produit.garantie_mois,
            'garantie': texte,
            'signaux': signaux,
        })
    return lignes


class Command(BaseCommand):
    help = ("AGR622 — liste (LECTURE SEULE) les pompes et variateurs avec "
            "garantie_mois et le texte garantie ; signale « durée sans texte "
            "source ». N'écrit rien.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-slug', dest='company_slug', default=None,
            help='Limiter l\'audit à une société (slug). Défaut : toutes.')

    def handle(self, *args, **options):
        lignes = audit_garanties_pompage(options.get('company_slug'))
        if not lignes:
            self.stdout.write('Aucune pompe ni aucun variateur trouvé.')
            return
        nb_signaux = 0
        for ligne in lignes:
            mois = (f"{ligne['garantie_mois']} mois"
                    if ligne['garantie_mois'] else 'non renseignée')
            texte = ligne['garantie'] or '(texte vide)'
            signal = ''
            if ligne['signaux']:
                nb_signaux += 1
                signal = ' — ' + ', '.join(ligne['signaux'])
            self.stdout.write(
                f"[{ligne['societe']}] #{ligne['produit_id']} {ligne['nom']} "
                f"({ligne['role']}, classé par {ligne['classement']}) : "
                f"garantie {mois} ; texte : {texte}{signal}")
        self.stdout.write(
            f'{len(lignes)} produit(s) audité(s), {nb_signaux} signalé(s) '
            f'« {SIGNAL_SANS_SOURCE} ». Aucune ligne modifiée.')
