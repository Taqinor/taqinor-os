# STKCAT27 (16/09/2026) — recherche catalogue INSENSIBLE AUX ACCENTS.
#
# Pose, quand la base le permet, les deux extensions PostgreSQL `unaccent` et
# `pg_trgm`, une fonction enveloppe IMMUTABLE `public.f_unaccent(text)`, et un
# index GIN trigramme sur `f_unaccent(lower(nom))` de `stock_produit`. Le
# `?search=` de `ProduitViewSet` ne devient insensible aux accents QUE si ces
# trois objets existent (cf. `apps.stock.selectors
# .recherche_sans_accents_disponible`) — sinon il garde le comportement
# `SearchFilter` d'aujourd'hui, à l'octet près.
#
# CETTE MIGRATION NE PEUT PAS ÉCHOUER, ET C'EST TOUT SON INTÉRÊT.
# ------------------------------------------------------------------
# Le rôle applicatif de la base de production n'a pas forcément le droit de
# faire `CREATE EXTENSION`. Une migration qui planterait là-dessus laisserait
# le serveur dans l'état le plus dangereux qui soit — « code déployé,
# migrations NON appliquées » (cf. CLAUDE.md, section Deploys). Tout le DDL est
# donc enfermé dans des blocs `BEGIN ... EXCEPTION WHEN OTHERS THEN RAISE
# NOTICE ... END` : chaque échec (droits insuffisants, extension installée dans
# un autre schéma, droit de création de fonction refusé…) se transforme en
# NOTICE dans le journal du déploiement, jamais en erreur. Le pire scénario est
# donc « rien n'a été créé, la recherche reste sensible aux accents » — le
# propriétaire de la base rattrape ensuite d'un simple
# `CREATE EXTENSION unaccent; CREATE EXTENSION pg_trgm;` puis en rejouant cette
# migration (`migrate stock 0148 --fake` puis un re-run n'est PAS nécessaire :
# le SQL est idempotent, cf. plus bas).
#
# IDEMPOTENCE : `CREATE EXTENSION IF NOT EXISTS`, `CREATE OR REPLACE FUNCTION`
# et `CREATE INDEX IF NOT EXISTS` — rejouer ce SQL deux fois de suite ne lève
# rien (verrouillé par `test_stkcat27_recherche_accents.py`).
#
# POURQUOI UNE FONCTION ENVELOPPE : `unaccent(text)` (1 argument) est déclarée
# STABLE et non IMMUTABLE — elle lit le dictionnaire par défaut — donc
# PostgreSQL REFUSE de l'utiliser dans une expression d'index. La forme à deux
# arguments `unaccent('public.unaccent', $1)` nomme le dictionnaire
# explicitement : c'est la recette canonique du wiki PostgreSQL pour pouvoir
# déclarer l'enveloppe IMMUTABLE en toute sûreté. Tout est qualifié `public.`
# pour que l'expression indexée ne dépende jamais d'un `search_path`.
#
# POURQUOI PAS `CREATE INDEX CONCURRENTLY` : un index concurrent ne peut PAS
# tourner dans un bloc de transaction, donc ni dans un bloc `DO`. `stock_produit`
# est une table de CATALOGUE (quelques centaines de lignes par société, cf. la
# note de la migration 0147) : la construction est instantanée et le verrou
# imperceptible. La garde `scripts/check_safe_migrations.py` ne vise que les
# opérations `AddIndex`, pas le SQL brut — cette exemption est ici assumée et
# justifiée par la taille de la table.
#
# AUCUN CHANGEMENT D'ÉTAT DJANGO : pas de `state_operations`, aucun modèle ne
# bouge, donc aucun risque de dérive `makemigrations --check`. L'index n'est
# PAS déclaré dans `Meta.indexes` — Django ne doit pas le connaître, sinon il
# voudrait le recréer sur une base où les extensions manquent.

from django.db import migrations

NOM_INDEX = 'stock_produit_nom_unaccent_trgm_idx'

# NOTE — aucun caractère « pour cent » ne doit apparaître dans ce SQL : Django
# le transmet avec `params=None`, mais le test d'idempotence le rejoue via
# `connection.cursor()`. D'où `RAISE NOTICE USING MESSAGE = ...` (concaténation)
# plutôt que `RAISE NOTICE '...', SQLERRM` (qui utiliserait un marqueur).
SQL_AVANT = """
DO $stkcat27$
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS unaccent;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE USING MESSAGE =
                'STKCAT27 : extension unaccent NON installee ('
                || SQLERRM
                || '). La recherche produit reste sensible aux accents.';
    END;

    BEGIN
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE USING MESSAGE =
                'STKCAT27 : extension pg_trgm NON installee ('
                || SQLERRM
                || '). La recherche produit reste sensible aux accents.';
    END;

    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'unaccent')
       AND EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
        BEGIN
            CREATE OR REPLACE FUNCTION public.f_unaccent(text)
                RETURNS text
                LANGUAGE sql
                IMMUTABLE
                PARALLEL SAFE
                STRICT
            AS $stkcat27fn$
                SELECT public.unaccent('public.unaccent', $1)
            $stkcat27fn$;

            CREATE INDEX IF NOT EXISTS stock_produit_nom_unaccent_trgm_idx
                ON stock_produit
                USING gin (public.f_unaccent(lower(nom)) gin_trgm_ops);
        EXCEPTION
            WHEN OTHERS THEN
                RAISE NOTICE USING MESSAGE =
                    'STKCAT27 : enveloppe f_unaccent ou index trigramme NON '
                    || 'crees (' || SQLERRM
                    || '). La recherche produit reste sensible aux accents.';
        END;
    ELSE
        RAISE NOTICE USING MESSAGE =
            'STKCAT27 : unaccent et/ou pg_trgm absentes de pg_extension - ni '
            || 'enveloppe ni index crees. La recherche produit reste sensible '
            || 'aux accents ; un CREATE EXTENSION par le proprietaire de la '
            || 'base puis un redemarrage des workers suffit a l''activer.';
    END IF;
END
$stkcat27$;
"""

# RETOUR ARRIÈRE — on retire ce que cette migration a posé (index puis
# enveloppe, dans cet ordre : l'index DÉPEND de la fonction) et JAMAIS les
# extensions : `unaccent` / `pg_trgm` sont des objets de base de données
# partagés, d'autres modules (ou d'autres bases logiques) peuvent s'en servir,
# et les détruire serait une destruction hors périmètre. Mêmes gardes
# d'exception : un retour arrière ne doit pas pouvoir échouer non plus.
SQL_ARRIERE = """
DO $stkcat27r$
BEGIN
    BEGIN
        DROP INDEX IF EXISTS stock_produit_nom_unaccent_trgm_idx;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE USING MESSAGE =
                'STKCAT27 (retour arriere) : index trigramme NON supprime ('
                || SQLERRM || ').';
    END;

    BEGIN
        DROP FUNCTION IF EXISTS public.f_unaccent(text);
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE USING MESSAGE =
                'STKCAT27 (retour arriere) : f_unaccent NON supprimee ('
                || SQLERRM || ').';
    END;
END
$stkcat27r$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0147_stkcat21_produit_role_devis'),
    ]

    # Le SQL est passé en LISTE (et non en chaîne) DÉLIBÉRÉMENT : avec une
    # chaîne, `RunSQL` le découpe via `prepare_sql_script` (sqlparse), ce qui
    # ferait courir un risque de découpage sur les points-virgules INTERNES au
    # bloc `DO`. Une liste est exécutée telle quelle, instruction par élément.
    operations = [
        migrations.RunSQL([SQL_AVANT], [SQL_ARRIERE]),
    ]
