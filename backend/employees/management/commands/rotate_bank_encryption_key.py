
"""Safely rotate encrypted bank account data to the primary Fernet key."""

from cryptography.fernet import InvalidToken, MultiFernet
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from employees.encryption import get_bank_encryption_keys


BATCH_SIZE = 500
TABLE_NAME = "employees_bankaccount"


class Command(BaseCommand):
    help = (
        "Rotate encrypted bank account data to the primary Fernet key. "
        "Use --dry-run to validate without modifying data, or --confirm "
        "to perform the rotation."
    )

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)

        group.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate encrypted data without modifying the database.",
        )

        group.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm and perform the encryption key rotation.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        try:
            keys = get_bank_encryption_keys()
            primary_fernet = keys[0]
            cipher = MultiFernet(keys)

            summary = self.rotate_bank_data(
                primary_fernet=primary_fernet,
                cipher=cipher,
                dry_run=dry_run,
            )

        except Exception:
            raise CommandError(
                "Bank encryption key rotation failed. "
                "No sensitive data or exception details were exposed."
            ) from None

        self.stdout.write(
            self.style.SUCCESS(
                f"Rows scanned: {summary['rows_scanned']}"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: no database records were modified."
                )
            )
            self.stdout.write(
                "Fields that would be rotated: "
                f"{summary['fields_rotated']}"
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Rows updated: "
                    f"{summary['rows_updated']}"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "Fields rotated: "
                    f"{summary['fields_rotated']}"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "Bank encryption key rotation completed."
                )
            )


    def rotate_bank_data(
        self,
        primary_fernet,
        cipher,
        dry_run,
    ):
        """Validate and optionally rotate all encrypted bank fields."""

        summary = {
            "rows_scanned": 0,
            "rows_updated": 0,
            "fields_rotated": 0,
        }

        quote = connection.ops.quote_name

        table = quote(TABLE_NAME)
        id_column = quote("id")
        routing_column = quote("routing_number")
        account_column = quote("account_number")

        select_sql = (
            f"SELECT {id_column}, {routing_column}, {account_column} "  # nosec B608
            f"FROM {table} ORDER BY {id_column}"
        )

        if connection.vendor == "postgresql":
            select_sql += " FOR UPDATE"

        update_sql = (
            f"UPDATE {table} "  # nosec B608
            f"SET {routing_column} = %s, "
            f"{account_column} = %s "
            f"WHERE {id_column} = %s"
        )

        with transaction.atomic():
            with connection.cursor() as read_cursor:
                with connection.cursor() as write_cursor:
                    read_cursor.execute(select_sql)

                    while True:
                        rows = read_cursor.fetchmany(BATCH_SIZE)

                        if not rows:
                            break

                        updates = []

                        for row_id, routing_number, account_number in rows:
                            summary["rows_scanned"] += 1

                            rotated_routing = self.rotate_value(
                                routing_number,
                                primary_fernet,
                                cipher,
                            )

                            rotated_account = self.rotate_value(
                                account_number,
                                primary_fernet,
                                cipher,
                            )

                            routing_changed = (
                                rotated_routing != routing_number
                            )
                            account_changed = (
                                rotated_account != account_number
                            )

                            if routing_changed or account_changed:
                                summary["fields_rotated"] += sum(
                                    (routing_changed, account_changed)
                                )

                                if not dry_run:
                                    updates.append(
                                        (
                                            rotated_routing,
                                            rotated_account,
                                            row_id,
                                        )
                                    )

                        if updates:
                            write_cursor.executemany(
                                update_sql,
                                updates,
                            )
                            summary["rows_updated"] += len(updates)

        return summary

    @staticmethod
    def rotate_value(value, primary_fernet, cipher):
        """Return a token encrypted with the primary key."""

        if value in (None, ""):
            return value

        token = (
            value.encode("ascii")
            if isinstance(value, str)
            else bytes(value)
        )

        try:
            primary_fernet.decrypt(token)
            return value
        except InvalidToken:
            pass

        try:
            return cipher.rotate(token).decode("ascii")
        except InvalidToken:
            raise RuntimeError(
                "An encrypted bank value cannot be decrypted."
            ) from None
