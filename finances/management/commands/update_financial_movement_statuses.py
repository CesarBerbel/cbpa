from django.core.management.base import BaseCommand

from finances.services import update_overdue_financial_movements


class Command(BaseCommand):
    """
    Update pending financial movements to overdue.
    """

    help = "Update pending financial movements to overdue when due date is older than today."

    def handle(self, *args, **options):
        """
        Execute the command.
        """
        updated_count = update_overdue_financial_movements()

        self.stdout.write(
            self.style.SUCCESS(
                f"{updated_count} financial movements updated to overdue."
            )
        )
