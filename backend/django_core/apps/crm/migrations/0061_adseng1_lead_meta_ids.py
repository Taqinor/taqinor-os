from django.db import migrations, models


class Migration(migrations.Migration):
    """ADSENG1 — Identifiants Meta natifs sur crm.Lead (additif, nullable).

    Meta ne pousse jamais campaign_name/adset_name dans le webhook leadgen ; il
    pousse ad_id/adgroup_id/form_id. On les capture comme clés de jointure
    stables vers les miroirs adsengine + un index (company, meta_ad_id) pour la
    jointure d'attribution par variante (ADSENG6).
    """

    dependencies = [
        ("crm", "0060_yopsb11_leadactivityarchive"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="meta_ad_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="lead",
            name="meta_adset_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="lead",
            name="meta_campaign_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="lead",
            name="meta_form_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddIndex(
            model_name="lead",
            index=models.Index(
                fields=["company", "meta_ad_id"],
                name="crm_lead_meta_ad_idx"),
        ),
    ]
