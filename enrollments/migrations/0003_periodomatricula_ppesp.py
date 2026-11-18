from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enrollments', '0002_periodomatricula_descricao'),
    ]

    operations = [
        migrations.AlterField(
            model_name='periodomatricula',
            name='programa',
            field=models.CharField(
                choices=[('PGEDA', 'PGEDA'), ('PPEB', 'PPEB'), ('PPESP', 'PPESP')],
                max_length=10,
            ),
        ),
    ]
