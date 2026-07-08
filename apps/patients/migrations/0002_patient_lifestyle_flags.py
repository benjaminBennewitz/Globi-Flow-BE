# apps/patients/migrations/0002_patient_lifestyle_flags.py

"""Ergänzt strukturierte Lebensstil-Flags für Testpersonen."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Fügt boolesche Lebensstilfelder hinzu."""

    dependencies = [
        ('patients', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='patient',
            name='non_smoker',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='patient',
            name='drinks_alcohol',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='patient',
            name='uses_drugs',
            field=models.BooleanField(default=False),
        ),
    ]
