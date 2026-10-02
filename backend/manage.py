#!/usr/bin/env python
"""Utilidad de linea de comandos de Django para CanchaMania."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "No se pudo importar Django. Esta instalado y el entorno virtual activo? "
            "Verificar con: python -c \"import django; print(django.get_version())\""
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
