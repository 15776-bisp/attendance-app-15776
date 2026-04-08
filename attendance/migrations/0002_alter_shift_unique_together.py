

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='shift',
            unique_together={('date', 'shift_type', 'department')},
        ),
    ]
