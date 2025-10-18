from django.shortcuts import render

def inicio(request):
    return render(request, 'inicio.html')

def perfil(request):
    return render(request, 'perfil.html')

def tareas(request):
    return render(request, 'tareas.html')