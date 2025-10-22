from django.shortcuts import render, redirect, get_object_or_404
from .models import Tarea

#vistas HTML
def inicio(request):
    return render(request, 'inicio.html')

def perfil(request):
    return render(request, 'perfil.html')

def tareas(request):
    # Si el usuario envía el formulario, crea una nueva tarea
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        responsable = request.POST.get('responsable')
        if nombre and responsable:
            Tarea.objects.create(nombre=nombre, responsable=responsable)
        return redirect('tareas')  # recarga la página

    # Si es GET, muestra todas las tareas
    tareas = Tarea.objects.all()
    return render(request, 'tareas.html', {'tareas': tareas})

#vistas API
from rest_framework import viewsets
from .serializers import TareaSerializer

class TareaViewSet(viewsets.ModelViewSet):
    queryset = Tarea.objects.all()
    serializer_class = TareaSerializer

#Vista para completar tarea
def completar_tarea(request, id):
    tarea = get_object_or_404(Tarea, id=id)
    if request.method == "POST":
        if tarea.estado == "pendiente":
            tarea.estado = "hecha"
        else:
            tarea.estado = "pendiente"
        tarea.save()
    return redirect('tareas')

# AUTENTICACIÓN DE USUARIOS

from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout

# Registro de usuario nuevo
def registro(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # inicia sesión automáticamente después de registrarse
            return redirect('inicio')
    else:
        form = UserCreationForm()
    return render(request, 'registro.html', {'form': form})

# Iniciar sesión
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('inicio')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

# Cerrar sesión
def logout_view(request):
    logout(request)
    return redirect('inicio')