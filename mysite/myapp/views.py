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