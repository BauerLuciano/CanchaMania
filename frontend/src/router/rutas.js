/**
 * Navegacion del panel.
 *
 * Cada entrada declara el permiso del backend que necesita para verse
 * (`meta.permiso`). El componente lo lee de `route.meta` y lo consulta contra
 * `/api/auth/me/`: si el backend no lo devolvio, el elemento no se muestra.
 *
 * En esta etapa solo existen las pantallas del esqueleto y de la sesion. Las
 * secciones de negocios, sucursales y usuarios estan declaradas en
 * `config/navegacion.js` con su permiso, pero todavia no tienen ruta: aparecen
 * como "proximamente" para que se vea de donde saldra la navegacion por
 * permisos sin enlazar a pantallas que no existen.
 */
import { RUTA_PANEL } from './guard.js'

export const rutas = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../modules/auth/LoginView.vue'),
    meta: { requiereAuth: false, titulo: 'Iniciar sesion', layout: 'publico' },
  },
  {
    path: '/panel/acceso',
    name: 'acceso',
    component: () => import('../modules/panel/AccesoView.vue'),
    meta: { requiereAuth: true, titulo: 'Mi acceso' },
  },
  {
    path: '/panel/sin-permiso',
    name: 'sin-permiso',
    component: () => import('../modules/panel/SinPermisoView.vue'),
    meta: { requiereAuth: true, titulo: 'Sin permisos' },
  },
  {
    path: '/panel',
    name: RUTA_PANEL,
    component: () => import('../modules/panel/InicioView.vue'),
    meta: { requiereAuth: true, titulo: 'Panel' },
  },
  {
    path: '/',
    redirect: { name: RUTA_PANEL },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'no-encontrado',
    component: () => import('../modules/panel/NoEncontradoView.vue'),
    meta: { requiereAuth: false, titulo: 'Pagina no encontrada' },
  },
]

export default rutas
