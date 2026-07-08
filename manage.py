#!/usr/bin/env python
# manage.py

"""Startet Django-Verwaltungsbefehle für Globi Flow."""

import os
import sys


def main() -> None:
    """Führt den angeforderten Django-Command aus."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
