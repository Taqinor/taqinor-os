"""WIR128 — PermisTravail.delivre_par / valide_par : CharField → FK utilisateur.

Un permis validé ne portait aucun lien auditable (texte libre). On aligne sur
les modèles voisins (ActionCorrectivePreventive.verifiee_par, ConsignationLoto)
en traçant le délivreur / valideur par FK ``authentication.User`` (SET_NULL).

Migration en quatre temps pour préserver un backfill best-effort du texte
existant : (1) ajout des FK temporaires, (2) appariement best-effort de l'ancien
texte à un utilisateur de la même société (username / nom complet), (3) retrait
des anciens CharField, (4) renommage des FK aux noms définitifs.

────────────────────────────────────────────────────────────────────────────
REVUE HUMAINE DE SÛRETÉ — retour arrière : DÉFAUT RÉEL TROUVÉ, CORRIGÉ ICI
────────────────────────────────────────────────────────────────────────────
La première version annonçait « Réversible : l'inverse recrée les CharField
vides (le texte d'origine n'est pas restauré — best-effort assumé) » et posait
un reverse ``noop``. C'était une PERTE DE DONNÉES SILENCIEUSE, pas une
réversibilité : un simple ``migrate qhse 0055`` détruisait TOUT, des deux
côtés à la fois.

Déroulé exact du rollback (Django rejoue la liste ``operations`` à l'envers) :
    op 6 inv. — renomme ``valide_par``  -> ``valide_par_user``   (non destructif)
    op 5 inv. — renomme ``delivre_par`` -> ``delivre_par_user``  (non destructif)
    op 4 inv. — recrée ``valide_par``  CharField(default='')      -> VIDE
    op 3 inv. — recrée ``delivre_par`` CharField(default='')      -> VIDE
    op 2 inv. — ``noop``                                          -> RIEN
    op 1 inv. — SUPPRIME la colonne ``valide_par_user_id``        -> DESTRUCTIF
    op 0 inv. — SUPPRIME la colonne ``delivre_par_user_id``       -> DESTRUCTIF
Résultat : les deux CharField reviennent vides (le texte d'origine a déjà été
détruit par les ``RemoveField`` de l'aller) ET les FK patiemment appariées sont
supprimées. Le rollback ne restaurait rien : il achevait la destruction.

POURQUOI UN RETOUR SANS PERTE EST IMPOSSIBLE. L'aller n'est pas inversible : le
texte libre a été apparié de façon FLOUE (``_match_user`` : username exact, à
défaut « Prénom Nom »), une projection non injective — plusieurs textes
distincts donnent le même utilisateur, et tout texte non apparié donne NULL,
indiscernable d'un champ qui était vide. Recalculer le texte depuis la FK
(p. ex. ``f"{user.first_name} {user.last_name}"``) FABRIQUERAIT une valeur
plausible mais fausse : ce serait un mensonge, pas une restauration.
Restaurer suppose donc de disposer du texte d'origine — et il n'existe nulle
part : audit du dépôt effectué, ``qhse.PermisTravail`` n'est inscrit ni dans
``apps/audit`` (``TRACKED_MODELS`` ne contient aucun modèle qhse, et le
journal ne capte que les écritures faites pendant une requête HTTP — jamais
une migration), ni dans le chatter ``apps/qhse/chatter.py``
(``_CIBLE_PAR_MODELE`` : NonConformite / ACP / Audit / Incident uniquement),
ni dans ``apps/records``; le modèle n'hérite d'aucun mixin d'historique et le
dépôt n'utilise pas ``django-simple-history``. Aucune fixture ni commande de
seed ne porte ces valeurs. Une fois l'aller appliqué, le texte n'existe plus
que dans une sauvegarde PostgreSQL antérieure — hors du périmètre du code.

AUCUN CHEMIN DE PRÉSERVATION NE PEUT ÊTRE AJOUTÉ APRÈS COUP. Sauvegarder le
texte exigerait une colonne d'archive, donc un ``AddField`` DANS cette
migration — or elle est déjà appliquée en production : la base ne rejouerait
jamais l'opération alors que l'état Django, lui, connaîtrait la colonne. Toute
migration ultérieure divergerait de la base réelle. Et une nouvelle migration
0057 arriverait trop tard : le texte est déjà détruit quand elle s'exécute.

CORRECTIF RETENU — ÉCHEC BRUYANT plutôt que destruction silencieuse. Le reverse
``noop`` est remplacé par ``refuser_retour_arriere``, qui lève
``IrreversibleError`` avec un message expliquant ce qui serait perdu et ce que
l'opérateur doit faire. Position dans la séquence : il occupe l'op 2, donc il
se déclenche APRÈS les seules opérations non destructives (renommages, qui
préservent la donnée, et recréations de colonnes vides, purement additives) et
AVANT les deux ``RemoveField`` inverses qui, eux, détruiraient les FK. La
migration étant atomique (défaut) et PostgreSQL sachant annuler du DDL, la
transaction est intégralement annulée : la base retrouve son état exact, rien
n'est perdu. Même sur un moteur sans DDL transactionnel, les quatre opérations
déjà jouées restent non destructives — la garantie « aucune perte » tient dans
les deux cas.
"""
from django.conf import settings
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError
import django.db.models.deletion


def _match_user(User, company_id, texte):
    """Meilleur appariement d'un texte libre à un utilisateur de la société."""
    texte = (texte or '').strip()
    if not texte:
        return None
    qs = User.objects.filter(company_id=company_id)
    # 1) username exact
    u = qs.filter(username__iexact=texte).first()
    if u is not None:
        return u
    # 2) nom complet « Prénom Nom »
    parts = texte.split()
    if len(parts) >= 2:
        u = qs.filter(
            first_name__iexact=parts[0],
            last_name__iexact=' '.join(parts[1:])).first()
        if u is not None:
            return u
    return None


def backfill_valideurs(apps, schema_editor):
    PermisTravail = apps.get_model('qhse', 'PermisTravail')
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0],
                          settings.AUTH_USER_MODEL.split('.')[1])
    for permis in PermisTravail.objects.all().iterator():
        delivre = _match_user(User, permis.company_id, permis.delivre_par)
        valide = _match_user(User, permis.company_id, permis.valide_par)
        changed = False
        if delivre is not None:
            permis.delivre_par_user = delivre
            changed = True
        if valide is not None:
            permis.valide_par_user = valide
            changed = True
        if changed:
            permis.save(update_fields=['delivre_par_user', 'valide_par_user'])


def refuser_retour_arriere(apps, schema_editor):
    """Reverse HONNÊTE : refuse bruyamment au lieu de détruire en silence.

    Voir la revue de sûreté en tête de fichier. Le retour arrière ne peut RIEN
    restaurer (le texte libre n'existe plus nulle part) et détruirait en plus
    les FK appariées. On lève donc avant les deux ``RemoveField`` inverses ;
    la transaction atomique annule les opérations déjà jouées, toutes non
    destructives — la base ressort intacte.
    """
    raise IrreversibleError(
        "qhse.0056 (WIR128) ne peut pas être annulée sans perte de données.\n"
        "\n"
        "CE QUI SERAIT PERDU si l'on passait outre :\n"
        "  1. les FK 'PermisTravail.delivre_par' / 'valide_par' (colonnes "
        "delivre_par_user_id / valide_par_user_id) seraient SUPPRIMÉES ;\n"
        "  2. les anciens CharField reviendraient VIDES : leur texte a été "
        "détruit par l'aller (RemoveField) et n'a été copié nulle part "
        "(PermisTravail n'est suivi ni par apps.audit, ni par le chatter "
        "qhse, ni par apps.records ; aucun historique de modèle).\n"
        "\n"
        "L'aller n'est pas inversible : l'appariement texte -> utilisateur "
        "était FLOU (username exact, sinon « Prénom Nom »). Reconstruire le "
        "texte depuis la FK fabriquerait une valeur plausible mais fausse, et "
        "une FK NULL ne permet pas de distinguer « champ vide » de « texte non "
        "apparié ». Ce serait un mensonge, pas une restauration.\n"
        "\n"
        "CE QU'IL FAUT FAIRE : restaurer une sauvegarde PostgreSQL antérieure "
        "à l'application de qhse.0056 — c'est le seul endroit où le texte "
        "d'origine subsiste encore.\n"
        "\n"
        "Si la perte est ACCEPTÉE en connaissance de cause : exporter d'abord "
        "les liens (SELECT id, delivre_par_user_id, valide_par_user_id FROM "
        "qhse_permistravail), puis remplacer ce reverse par "
        "migrations.RunPython.noop dans une copie locale. Ce geste doit rester "
        "délibéré et tracé — il n'existe volontairement aucun contournement "
        "silencieux dans le code."
    )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('qhse', '0055_ncr_date_creation_editable'),
    ]

    operations = [
        migrations.AddField(
            model_name='permistravail',
            name='delivre_par_user',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='qhse_permis_delivres',
                to=settings.AUTH_USER_MODEL, verbose_name='Délivré par'),
        ),
        migrations.AddField(
            model_name='permistravail',
            name='valide_par_user',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='qhse_permis_valides',
                to=settings.AUTH_USER_MODEL, verbose_name='Validé par'),
        ),
        migrations.RunPython(backfill_valideurs, refuser_retour_arriere),
        migrations.RemoveField(model_name='permistravail', name='delivre_par'),
        migrations.RemoveField(model_name='permistravail', name='valide_par'),
        migrations.RenameField(
            model_name='permistravail',
            old_name='delivre_par_user', new_name='delivre_par'),
        migrations.RenameField(
            model_name='permistravail',
            old_name='valide_par_user', new_name='valide_par'),
    ]
