from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0033_zged1_rolesignataire'),
    ]

    operations = [
        migrations.AddField(
            model_name='signatairedemande',
            name='auth_extra',
            field=models.CharField(blank=True, choices=[('aucune', 'Aucune'), ('sms', 'Code SMS'), ('email_otp', 'Code par email (OTP)')], default='', max_length=10, verbose_name='authentification extra (effective)'),
        ),
        migrations.AddField(
            model_name='signatairedemande',
            name='otp_code_hash',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='hash du code OTP (SHA-256)'),
        ),
        migrations.AddField(
            model_name='signatairedemande',
            name='otp_expires_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='code OTP expire le'),
        ),
        migrations.AddField(
            model_name='signatairedemande',
            name='otp_essais',
            field=models.PositiveIntegerField(default=0, verbose_name='essais de code OTP'),
        ),
        migrations.AddField(
            model_name='signatairedemande',
            name='otp_valide',
            field=models.BooleanField(default=False, verbose_name='authentification extra validée'),
        ),
        migrations.AddField(
            model_name='signatairedemande',
            name='otp_valide_le',
            field=models.DateTimeField(blank=True, null=True, verbose_name='authentification extra validée le'),
        ),
    ]
