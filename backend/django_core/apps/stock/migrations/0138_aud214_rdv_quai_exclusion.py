"""AUD214 — non-chevauchement des créneaux de quai posé PAR LA BASE.

La garde NTWMS7 vivait uniquement dans ``RendezVousTransporteur.save()`` :
lire les chevauchements, puis insérer. C'est un TOCTOU classique — et il est
atteignable depuis un endpoint PUBLIC (``AllowAny``) : le portail fournisseur
``portail_fournisseur_reserver_creneau_view`` → ``reserver_creneau_fournisseur``.
Deux réservations simultanées du même créneau exécutent leur SELECT avant que
l'autre n'ait inséré : aucune ne voit de conflit, les DEUX passent, et deux
camions se présentent au même quai à la même heure.

TROIS OPÉRATIONS, DANS CET ORDRE :

1. ``BtreeGistExtension`` — ``EXCLUDE USING GIST`` a besoin de ``btree_gist``
   pour l'opérateur d'ÉGALITÉ sur ``quai_id`` (un entier) à côté de
   l'opérateur de RECOUVREMENT sur la plage. Extension contrib standard de
   PostgreSQL, créée exactement comme ``VectorExtension`` l'est déjà dans
   ``core.0044``/``ged.0007``.

2. ``annuler_chevauchements_residuels`` — nettoie AVANT la contrainte (sans
   quoi la migration échouerait sur une base qui en porte). Un chevauchement
   résiduel ne peut venir que de la course que cette tâche ferme : le
   rendez-vous le plus RÉCEMMENT créé (``pk`` le plus élevé) est celui qui
   aurait DÛ être refusé à l'insertion — il est donc passé à ``annule`` (le
   statut qui, par définition métier, libère le créneau), avec la raison
   ajoutée à sa note. Rien n'est supprimé, la ligne reste consultable et le
   résumé est imprimé pendant le ``migrate`` (visible au déploiement).

3. ``AddConstraint`` de l'``ExclusionConstraint`` déclarée dans
   ``models_wms.py`` — l'état Django reste aligné sur les modèles.

RÉVERSIBILITÉ : la contrainte se retire sans perte (``RemoveConstraint``
auto-généré) ; l'annulation d'un doublon, elle, ne se « dé-annule » pas
automatiquement (on ne sait pas lequel le métier voulait garder) — son sens
inverse est un no-op explicite.
"""
import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations, models

import apps.stock.models_wms

# Miroir de ``RendezVousTransporteur.STATUTS_OCCUPANTS`` au moment de cette
# migration (tout sauf « annule »).
STATUTS_OCCUPANTS = ['planifie', 'arrive', 'en_cours', 'termine', 'no_show']


def annuler_chevauchements_residuels(apps_registry, schema_editor):
    RendezVous = apps_registry.get_model('stock', 'RendezVousTransporteur')

    occupes = {}      # quai_id -> [(debut, fin), ...] déjà retenus
    annules = []
    # ``iterator`` + tri stable (jamais de ``.update()`` global) : le créneau
    # le plus ancien d'un quai est vu en premier et gagne la place.
    for rdv in (RendezVous.objects
                .filter(statut__in=STATUTS_OCCUPANTS)
                .order_by('quai_id', 'date_heure_debut', 'pk')
                .iterator(chunk_size=500)):
        if not (rdv.date_heure_debut and rdv.date_heure_fin):
            continue
        retenus = occupes.setdefault(rdv.quai_id, [])
        if any(rdv.date_heure_debut < fin and rdv.date_heure_fin > debut
               for debut, fin in retenus):
            rdv.statut = 'annule'
            rdv.note = ((rdv.note or '') + '\nAUD214 — annulé : ce créneau '
                        'chevauchait un rendez-vous déjà posé sur le même '
                        'quai (course de réservation désormais refusée par '
                        'la base).').strip()
            rdv.save(update_fields=['statut', 'note'])
            annules.append((rdv.pk, rdv.quai_id))
            continue
        retenus.append((rdv.date_heure_debut, rdv.date_heure_fin))

    if annules:
        print(f"\nstock.0138 — {len(annules)} rendez-vous transporteur "
              "chevauchant(s) passé(s) à « annulé » (aucune suppression) :")
        for pk, quai_id in annules:
            print(f"  rendez-vous #{pk} (quai #{quai_id})")
    else:
        print("\nstock.0138 — aucun chevauchement de créneau de quai trouvé.")


def sens_inverse(apps_registry, schema_editor):
    """Une annulation de doublon ne se défait pas : no-op explicite."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0137_aud218_lotentrepot_unique'),
    ]

    operations = [
        BtreeGistExtension(),
        migrations.RunPython(annuler_chevauchements_residuels, sens_inverse),
        migrations.AddConstraint(
            model_name='rendezvoustransporteur',
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(
                condition=models.Q(('statut__in', STATUTS_OCCUPANTS)),
                expressions=[
                    (apps.stock.models_wms.TsTzRange(
                        'date_heure_debut', 'date_heure_fin',
                        django.contrib.postgres.fields.ranges.RangeBoundary()),
                     '&&'),
                    ('quai', '='),
                ],
                name='stock_rdvtransporteur_quai_sans_chevauchement'),
        ),
    ]
