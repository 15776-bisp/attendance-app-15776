from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

from attendance.models import Shift


class Command(BaseCommand):
    help = "Generate daily shifts for all departments"

    def handle(self, *args, **options):
        today = date.today()
        days_to_create = 7

        excluded_groups = ["Manager"]

        departments = Group.objects.exclude(name__in=excluded_groups)

        created_count = 0

        for i in range(days_to_create):
            shift_date = today + timedelta(days=i)

            for department in departments:
                shift, created = Shift.objects.get_or_create(
                    date=shift_date,
                    shift_type="morning",
                    department=department,
                )

                if created:
                    created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Successfully created {created_count} shifts.")
        )

