"""Paginacion de la API."""
from rest_framework.pagination import PageNumberPagination


class PaginacionPorDefecto(PageNumberPagination):
    """Paginacion por numero de pagina, con envelope estable."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
