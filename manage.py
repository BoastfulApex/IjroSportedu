#!/usr/bin/env python
import os
import sys


def main():
    default_settings = (
        "config.settings.production"
        if os.environ.get("DJANGO_ENV") == "production"
        else "config.settings.local"
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings)
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django.") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
