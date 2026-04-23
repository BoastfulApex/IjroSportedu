"""
Chair modeli endi Department emas, Organization bilan bog'liq.
Mavjud ma'lumotlar bo'lmasa (yangi loyiha), to'g'ridan migration qilinadi.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        # Eski department FK ni olib tashlaymiz
        migrations.RemoveField(
            model_name="chair",
            name="department",
        ),
        # Yangi organization FK qo'shamiz
        migrations.AddField(
            model_name="chair",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="chairs",
                to="organizations.organization",
                verbose_name="Tashkilot",
                null=True,
            ),
        ),
        # null=True ni olib tashlaymiz (bir qadamda NOT NULL qilib bo'lmaydi)
        migrations.AlterField(
            model_name="chair",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="chairs",
                to="organizations.organization",
                verbose_name="Tashkilot",
            ),
        ),
        # ordering yangilash
        migrations.AlterModelOptions(
            name="chair",
            options={
                "ordering": ["organization", "name"],
                "verbose_name": "Kafedra",
                "verbose_name_plural": "Kafedralar",
            },
        ),
    ]
