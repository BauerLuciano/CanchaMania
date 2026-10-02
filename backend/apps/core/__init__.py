"""App nucleo: abstracciones compartidas de CanchaMania.

No contiene modelos de negocio. Solo la infraestructura transversal:

* modelos base con timestamps y abstraccion de ambito multi-tenant;
* manager que recorta cualquier queryset por el ambito del usuario;
* resolucion de ambito a partir de las membresias activas;
* formato de error uniforme de la API (SPEC §19);
* paginacion, permisos y viewset base.
"""
