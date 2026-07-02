# DC34 — Sous-traitant : plus de référentiel parallèle.
#
# On fond l'ancien référentiel sous-traitant (installations.SousTraitant, FG304)
# et son AP dédiée (installations.FactureSousTraitant / PaiementSousTraitant,
# FG306) dans le référentiel tiers UNIFIÉ de stock :
#   * chaque SousTraitant devient un stock.Fournisseur(type='service') porteur
#     d'un stock.SousTraitantProfile (métier / actif / note) ;
#   * les FK sous_traitant des ordres / attestations / évaluations sont
#     repointées vers stock.Fournisseur ;
#   * chaque FactureSousTraitant/PaiementSousTraitant est déplacée sur la chaîne
#     AP standard stock.FactureFournisseur/PaiementFournisseur.
#
# La migration de DONNÉES est RÉVERSIBLE : le reverse recrée les SousTraitant à
# partir des Fournisseur(type='service')+profil taggés DC34, repointe les FK,
# reconstitue l'AP dédiée depuis la chaîne standard, puis supprime les objets
# stock créés. On passe la FK en ``db_constraint=False`` le temps du remap (les
# anciens ids pointent encore l'ancienne table) puis on rétablit la contrainte.
#
# Le tag DC34 (préfixe de note technique) marque les objets stock issus de cette
# migration, pour que le reverse ne touche QUE ce qu'elle a créé.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

_TAG = '[DC34-migr]'


def _forward(apps, schema_editor):
    SousTraitant = apps.get_model('installations', 'SousTraitant')
    OrdreSousTraitance = apps.get_model('installations', 'OrdreSousTraitance')
    AttestationSousTraitant = apps.get_model(
        'installations', 'AttestationSousTraitant')
    EvaluationSousTraitant = apps.get_model(
        'installations', 'EvaluationSousTraitant')
    FactureSousTraitant = apps.get_model(
        'installations', 'FactureSousTraitant')
    PaiementSousTraitant = apps.get_model(
        'installations', 'PaiementSousTraitant')
    Fournisseur = apps.get_model('stock', 'Fournisseur')
    SousTraitantProfile = apps.get_model('stock', 'SousTraitantProfile')
    FactureFournisseur = apps.get_model('stock', 'FactureFournisseur')
    PaiementFournisseur = apps.get_model('stock', 'PaiementFournisseur')

    # 1) SousTraitant → Fournisseur(type=service) + profil. Mapping old→new.
    mapping = {}
    for st in SousTraitant.objects.all():
        f = Fournisseur.objects.create(
            company_id=st.company_id, nom=st.raison_sociale, type='service',
            contact_personne=st.contact_nom, email=st.email,
            telephone=st.telephone, adresse=st.adresse, ice=st.ice,
            rib=st.rib)
        SousTraitantProfile.objects.create(
            company_id=st.company_id, fournisseur=f, metier=st.metier,
            actif=st.actif,
            note=f'{_TAG}#{st.id}' + (f' {st.note}' if st.note else ''),
            created_by_id=st.created_by_id)
        mapping[st.id] = f.id

    # 2) Repointe les FK sous_traitant (contrainte déjà retirée en amont).
    for model in (OrdreSousTraitance, AttestationSousTraitant,
                  EvaluationSousTraitant):
        for row in model.objects.all():
            new_id = mapping.get(row.sous_traitant_id)
            if new_id is not None:
                model.objects.filter(pk=row.pk).update(sous_traitant_id=new_id)

    # 3) AP dédiée → chaîne standard. La référence FF est posée ici (préfixe
    #    FF + id d'origine pour rester unique par société et traçable au reverse).
    statut_map = {
        'brouillon': 'a_payer', 'a_payer': 'a_payer',
        'partielle': 'partiellement_payee', 'payee': 'payee',
        'annulee': 'a_payer',
    }
    fac_mapping = {}
    for fac in FactureSousTraitant.objects.all():
        new_fac = FactureFournisseur.objects.create(
            company_id=fac.company_id,
            reference=f'FF-{_TAG}-{fac.id}',
            fournisseur_id=mapping.get(fac.sous_traitant_id),
            ref_fournisseur=fac.numero,
            date_facture=fac.date_facture, date_echeance=fac.date_echeance,
            montant_ht=fac.montant_ht, montant_tva=fac.montant_tva,
            montant_ttc=fac.montant_ttc,
            statut=statut_map.get(fac.statut, 'a_payer'),
            note=f'{_TAG}#{fac.id}' + (f' {fac.note}' if fac.note else ''),
            created_by_id=fac.created_by_id)
        fac_mapping[fac.id] = new_fac.id
    for pay in PaiementSousTraitant.objects.all():
        PaiementFournisseur.objects.create(
            company_id=pay.company_id,
            facture_id=fac_mapping.get(pay.facture_id),
            montant=pay.montant, date_paiement=pay.date_paiement,
            mode=pay.mode,
            note=f'{_TAG}#{pay.id}' + (f' {pay.note}' if pay.note else ''),
            created_by_id=pay.created_by_id)


def _reverse(apps, schema_editor):
    SousTraitant = apps.get_model('installations', 'SousTraitant')
    OrdreSousTraitance = apps.get_model('installations', 'OrdreSousTraitance')
    AttestationSousTraitant = apps.get_model(
        'installations', 'AttestationSousTraitant')
    EvaluationSousTraitant = apps.get_model(
        'installations', 'EvaluationSousTraitant')
    FactureSousTraitant = apps.get_model(
        'installations', 'FactureSousTraitant')
    PaiementSousTraitant = apps.get_model(
        'installations', 'PaiementSousTraitant')
    Fournisseur = apps.get_model('stock', 'Fournisseur')
    SousTraitantProfile = apps.get_model('stock', 'SousTraitantProfile')
    FactureFournisseur = apps.get_model('stock', 'FactureFournisseur')
    PaiementFournisseur = apps.get_model('stock', 'PaiementFournisseur')

    # 1) Recrée les SousTraitant depuis les profils taggés DC34 ; mapping
    #    Fournisseur.id → SousTraitant.id restauré.
    inverse = {}
    profils = SousTraitantProfile.objects.filter(note__startswith=_TAG)
    for profil in profils.select_related('fournisseur'):
        f = profil.fournisseur
        note = profil.note or ''
        # note = '[DC34-migr]#<id> <note d'origine>'
        reste = note[len(_TAG):].lstrip()
        old_note = ''
        if reste.startswith('#'):
            tete, _, old_note = reste.partition(' ')
        st = SousTraitant.objects.create(
            company_id=f.company_id, raison_sociale=f.nom,
            metier=profil.metier, contact_nom=f.contact_personne,
            telephone=f.telephone, email=f.email, ice=f.ice, rib=f.rib,
            adresse=f.adresse, actif=profil.actif,
            note=old_note or None, created_by_id=profil.created_by_id)
        inverse[f.id] = st.id

    # 2) Repointe les FK sous_traitant vers les SousTraitant recréés.
    for model in (OrdreSousTraitance, AttestationSousTraitant,
                  EvaluationSousTraitant):
        for row in model.objects.all():
            old_id = inverse.get(row.sous_traitant_id)
            if old_id is not None:
                model.objects.filter(pk=row.pk).update(sous_traitant_id=old_id)

    # 3) Reconstitue l'AP dédiée depuis la chaîne standard taggée DC34.
    statut_inverse = {
        'a_payer': 'a_payer', 'partiellement_payee': 'partielle',
        'payee': 'payee',
    }
    fac_inverse = {}
    for ff in FactureFournisseur.objects.filter(note__startswith=_TAG):
        st_id = inverse.get(ff.fournisseur_id)
        note = ff.note or ''
        reste = note[len(_TAG):].lstrip()
        old_note = ''
        if reste.startswith('#'):
            _, _, old_note = reste.partition(' ')
        fac = FactureSousTraitant.objects.create(
            company_id=ff.company_id, sous_traitant_id=st_id,
            numero=ff.ref_fournisseur,
            montant_ht=ff.montant_ht, montant_tva=ff.montant_tva,
            montant_ttc=ff.montant_ttc,
            date_facture=ff.date_facture, date_echeance=ff.date_echeance,
            statut=statut_inverse.get(ff.statut, 'a_payer'),
            note=old_note or None, created_by_id=ff.created_by_id)
        fac_inverse[ff.id] = fac.id
    for pf in PaiementFournisseur.objects.filter(note__startswith=_TAG):
        note = pf.note or ''
        reste = note[len(_TAG):].lstrip()
        old_note = ''
        if reste.startswith('#'):
            _, _, old_note = reste.partition(' ')
        PaiementSousTraitant.objects.create(
            company_id=pf.company_id,
            facture_id=fac_inverse.get(pf.facture_id),
            montant=pf.montant, date_paiement=pf.date_paiement,
            mode=pf.mode, note=old_note or None,
            created_by_id=pf.created_by_id)

    # 4) Supprime les objets stock créés par la migration (uniquement les
    #    taggés DC34 — on ne touche jamais un fournisseur/AP légitime).
    PaiementFournisseur.objects.filter(note__startswith=_TAG).delete()
    FactureFournisseur.objects.filter(note__startswith=_TAG).delete()
    fourn_ids = list(profils.values_list('fournisseur_id', flat=True))
    SousTraitantProfile.objects.filter(note__startswith=_TAG).delete()
    Fournisseur.objects.filter(id__in=fourn_ids, type='service').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0048_dc40_equipe_canonique'),
        ('stock', '0028_dc34_fournisseur_type_soustraitantprofile'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1) On retire la contrainte FK (retarget vers stock.Fournisseur sans
        #    contrainte) pour pouvoir remapper des ids qui pointent encore
        #    l'ancienne table pendant la migration de données.
        migrations.AlterField(
            model_name='ordresoustraitance',
            name='sous_traitant',
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='installations_ordres_sous_traitance',
                to='stock.fournisseur'),
        ),
        migrations.AlterField(
            model_name='attestationsoustraitant',
            name='sous_traitant',
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='installations_attestations',
                to='stock.fournisseur'),
        ),
        migrations.AlterField(
            model_name='evaluationsoustraitant',
            name='sous_traitant',
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='installations_evaluations',
                to='stock.fournisseur'),
        ),
        # 2) Migration de données RÉVERSIBLE.
        migrations.RunPython(_forward, _reverse),
        # 3) On rétablit la contrainte FK (les ids pointent désormais des
        #    Fournisseur valides).
        migrations.AlterField(
            model_name='ordresoustraitance',
            name='sous_traitant',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='installations_ordres_sous_traitance',
                to='stock.fournisseur'),
        ),
        migrations.AlterField(
            model_name='attestationsoustraitant',
            name='sous_traitant',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='installations_attestations',
                to='stock.fournisseur'),
        ),
        migrations.AlterField(
            model_name='evaluationsoustraitant',
            name='sous_traitant',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='installations_evaluations',
                to='stock.fournisseur'),
        ),
        # 4) L'AP dédiée et l'ancien référentiel disparaissent. DeleteModel
        #    retire aussi les index de chaque table (dépendants d'abord :
        #    PaiementSousTraitant → FactureSousTraitant → SousTraitant).
        migrations.DeleteModel(name='PaiementSousTraitant'),
        migrations.DeleteModel(name='FactureSousTraitant'),
        migrations.DeleteModel(name='SousTraitant'),
    ]
