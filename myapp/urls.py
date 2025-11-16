from django.urls import path, include
from rest_framework import routers
from . import views
from django.contrib.auth import views as auth_views

router = routers.DefaultRouter()
router.register(r'tareas', views.TareaViewSet, basename='tarea')

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('perfil/', views.perfil, name='perfil'),
    path('tareas/', views.tareas, name='tareas'),
    path('tareas/<int:id>/completar/', views.completar_tarea, name='completar_tarea'),
    path('tareas/editar/<int:tarea_id>/', views.editar_tarea, name='editar_tarea'),
    path('tareas/eliminar/<int:tarea_id>/', views.eliminar_tarea, name='eliminar_tarea'),
    path('familia/crear/', views.crear_familia, name='crear_familia'),
    path('familia/invitar/', views.invitar_miembro, name='invitar_miembro'),
    path('familia/unirse/', views.unirse_familia, name='unirse_familia'),
    path('api/', include(router.urls)),
    path('registro/', views.registro, name='registro'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset_done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('horario/agregar/', views.agregar_horario, name='agregar_horario'),
    path('horario/ver/', views.ver_horario, name='ver_horario'),
    path('horario/editar/<int:horario_id>/', views.editar_horario, name='editar_horario'),
    path('horario/eliminar/<int:horario_id>/', views.eliminar_horario, name='eliminar_horario'),
    path('tareas/repartir/<int:familia_id>/', views.repartir_tareas, name='repartir_tareas'),
    path('familia/limpiar-tareas/<int:familia_id>/', views.limpiar_instancias_tareas, name='limpiar_instancias_tareas'),
]
