"""MSGACC2 — LE MESSAGE DE DEMAIN MATIN (fondateur, 15/09/2026).

Sème, pour chaque société NON-démo, un ``MessageAccueil`` visible demain à
07:00 (Africa/Casablanca) pour chaque utilisateur ACTIF qui fait la relance
CRM — annonçant que la visite technique rejoint désormais le suivi
commercial après-devis.

AUDIENCE — repli documenté (fondateur : « si la résolution par rôles est trop
fragile en migration, replie sur les owners + les admins »). Une migration de
données tourne sur les MODÈLES HISTORIQUES (``apps.get_model``) : ils ne
portent QUE les champs enregistrés dans les migrations, jamais les méthodes/
constantes ajoutées à la main sur la vraie classe (``is_admin_role``,
``has_erp_permission``, ``CustomUser.ROLE_ADMIN``…). Résoudre l'audience par
les permissions FINES du rôle (``crm_voir``, en excluant nommément le rôle
« Commercial terrain ») demanderait de rejouer ici cette logique applicative
à la main, sur un modèle qui ne la porte pas — fragile et hors de portée
d'une migration. On retombe donc sur le repli explicitement autorisé :
    - les ADMINS de la société (``role_legacy == 'admin'`` — comportement
      legacy directement porté par le champ, aucune méthode requise) ;
    - UNION les OWNERS distincts de leads NON ARCHIVÉS de la société (ce sont,
      par construction, les comptes qui font réellement la relance — un
      compte « Commercial terrain » n'est jamais owner d'un lead : son métier
      est la visite terrain, pas le portefeuille CRM, cf. VTA4).
Seuls les comptes ACTIFS reçoivent le message.

IDEMPOTENTE — clé de dédoublonnage ``(company, destinataire, auteur IS NULL,
corps EXACT)`` : un second passage (fake-reapply, retry) ne crée jamais de
doublon.

RÉVERSIBLE — le retour arrière supprime exactement les lignes que CETTE
migration peut avoir créées, repérées par ``auteur IS NULL`` + le corps EXACT
du message (un texte long et distinctif : aucune autre fonctionnalité ne
crée jamais cette combinaison). Le filtre ne contraint PAS
``visible_a_partir_de`` — recalculer « demain 7h » au moment du retour
arrière ne coïnciderait avec la valeur créée à l'aller que si aucune journée
ne s'est écoulée entre les deux (vrai pour un test aller-retour automatisé,
pas garanti pour un rollback tardif) ; le corps, lui, est un identifiant sûr
en toute circonstance.

CE N'EST PAS UNE NOTIFICATION : aucun ``EventType``, aucune ligne du centre
de notifications — voir la docstring de ``MessageAccueil`` (models.py).
"""
from datetime import datetime, time, timedelta

from django.db import migrations
from django.db.models import Q
from django.utils import timezone as dj_timezone

CASABLANCA_TZ = 'Africa/Casablanca'

CORPS = (
    "Bonjour ! ☀️\n"
    "\n"
    "Du nouveau dans ton suivi commercial à partir d'aujourd'hui : la "
    "visite technique fait maintenant partie de la relance après-devis.\n"
    "\n"
    "1. Le panneau « Proposer la visite » apparaît sur chaque touche du "
    "suivi de proposition. Avant J2 : on n'en parle pas encore. De J2 à "
    "J6 : on la sème (« quand le technicien passe, il confirme juste "
    "l'orientation du toit et la charpente pour verrouiller le prix »). "
    "À partir de J7 : on la propose franchement — toujours deux créneaux "
    "au choix (« mardi matin ou jeudi après-midi ? »), jamais « voulez-vous "
    "qu'on passe ? ».\n"
    "\n"
    "2. Les signaux qui disent « propose-la tout de suite », peu importe le "
    "jour : il demande les délais d'installation, les garanties, le "
    "financement ; il parle de SON toit ; il demande des références ; ou "
    "toute question « comment ça se passe quand… ». Et chaque objection "
    "technique se ferme par la visite, jamais par un débat au téléphone.\n"
    "\n"
    "3. Le client dit oui ? Choisis « Visite acceptée » sur la touche : la "
    "fenêtre de planification s'ouvre (date + qui fait la visite). Ses "
    "relances se décalent automatiquement après la visite — rien ne "
    "redémarre, rien n'est perdu.\n"
    "\n"
    "4. Important : la visite se fait avec le client lui-même — jamais le "
    "gardien ni la bonne. Confirme sa présence au moment de fixer le "
    "créneau.\n"
    "\n"
    "5. La veille, une touche « Confirmer la visite » se pose toute seule, "
    "message prêt à envoyer.\n"
    "\n"
    "6. Quand le technicien termine, son compte-rendu arrive dans "
    "l'historique du lead avec sa qualification : client chaud/tiède/froid, "
    "le devis convient ou à modifier, qui décide, le frein principal, ce "
    "qui l'a accroché, et quand rappeler. Rappelle dans les 24-48 h en "
    "ouvrant sur un détail concret vu chez lui — c'est là que ça se signe. "
    "S'il veut un devis modifié, l'étape devient « Préparer le devis "
    "modifié — rappeler le client » ; quand tu envoies le nouveau devis, le "
    "suivi en cours continue (décalé après la visite) — jamais deux séries "
    "de relances en parallèle.\n"
    "\n"
    "Tout est dans la fiche lead, section « Suivi commercial », en haut — "
    "plus besoin de descendre dans la page.\n"
    "\n"
    "7. Le guide complet de ces étapes (avec les phrases exactes à dire) est "
    "un PDF rangé dans le module Documents : Documents (GED) → cabinet "
    "« Documentation » → dossier « Guides » → « Guide — La visite technique "
    "dans le suivi commercial ». Ouvre le module ici : /ged\n"
    "\n"
    "PS : ce message t'arrive par la nouvelle fenêtre d'accueil de l'ERP — "
    "ferme-le avec « Compris ». Bonne journée !"
)


def _demain_7h_casablanca(reference=None):
    """« Demain 07:00 » heure du Maroc, en datetime AWARE (même patron que
    ``apps/crm/horaires.py``/``apps/ventes/scheduled.py`` : ``zoneinfo``,
    jamais un décalage fixe codé en dur — Django stocke en UTC quel que soit
    le fuseau porté par l'objet, ``USE_TZ=True``)."""
    from zoneinfo import ZoneInfo
    reference = reference or dj_timezone.now()
    ici = reference.astimezone(ZoneInfo(CASABLANCA_TZ))
    demain = (ici + timedelta(days=1)).date()
    return datetime.combine(demain, time(7, 0), tzinfo=ZoneInfo(CASABLANCA_TZ))


def _audience_relance_crm(apps, company):
    """Utilisateurs ACTIFS de `company` qui font la relance CRM — voir le
    repli documenté en tête de fichier. Renvoie un queryset (modèle
    historique) dédoublonné de ``CustomUser``.

    Frontière cross-app (CLAUDE.md) : lire ``crm.Lead`` via
    ``apps.get_model('crm', 'Lead')`` (modèle HISTORIQUE, jamais
    ``apps.crm.models``/``apps.crm.selectors``) est la voie standard Django
    pour une migration — un `selectors.py` réel suppose le SCHÉMA courant, pas
    l'état de migration à ce point de l'historique, et romprait au premier
    changement de schéma de ``crm`` rejoué depuis zéro. Migration UNIQUE
    (données, pas d'import Python permanent) : `lint-imports`/M3 restent
    intacts, aucun couplage durable n'est introduit."""
    CustomUser = apps.get_model('authentication', 'CustomUser')
    Lead = apps.get_model('crm', 'Lead')

    owner_ids = list(
        Lead.objects.filter(company=company, is_archived=False)
        .exclude(owner__isnull=True)
        .values_list('owner_id', flat=True).distinct()
    )
    return (
        CustomUser.objects.filter(company=company, is_active=True)
        .filter(Q(role_legacy='admin') | Q(pk__in=owner_ids))
        .distinct()
    )


def semer_message_demain_matin(apps, schema_editor):
    Company = apps.get_model('authentication', 'Company')
    MessageAccueil = apps.get_model('notifications', 'MessageAccueil')

    moment = _demain_7h_casablanca()
    for company in Company.objects.filter(est_demo=False):
        for user in _audience_relance_crm(apps, company):
            MessageAccueil.objects.get_or_create(
                company=company, destinataire=user, auteur=None, corps=CORPS,
                defaults={'visible_a_partir_de': moment},
            )


def retirer_message_demain_matin(apps, schema_editor):
    MessageAccueil = apps.get_model('notifications', 'MessageAccueil')
    # Marqueur sûr : auteur NULL + corps EXACT (texte long et distinctif —
    # voir la docstring du module pour pourquoi `visible_a_partir_de` n'entre
    # pas dans ce filtre).
    MessageAccueil.objects.filter(auteur__isnull=True, corps=CORPS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('crm', '0101_visite_cadence_outcome'),
        ('notifications', '0058_message_accueil'),
    ]

    operations = [
        migrations.RunPython(
            semer_message_demain_matin, retirer_message_demain_matin),
    ]
