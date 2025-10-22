from django.urls import path, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r'tareas', views.TareaViewSet)

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('perfil/', views.perfil, name='perfil'),
    path('tareas/', views.tareas, name='tareas'),
    path('tareas/<int:id>/completar/', views.completar_tarea, name='completar_tarea'),  # 👈 nueva ruta
    path('api/', include(router.urls)),
]