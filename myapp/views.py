from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Tarea, Familia, Horario
from .forms import HorarioForm
from rest_framework import viewsets
from .serializers import TareaSerializer

# VISTAS HTML PRINCIPALES (tocar con cuidado)

def inicio(request):
    familia = None
    if request.user.is_authenticated:
        familia = (Familia.objects.filter(jefe=request.user).first() or 
                   Familia.objects.filter(miembros=request.user).first())
    return render(request, 'inicio.html', {'familia': familia})


@login_required
def perfil(request):
    usuario = request.user
    familia = None
    es_jefe = False

    # Revisar si el usuario es jefe o miembro
    if hasattr(usuario, "familia_jefe"):
        familia = usuario.familia_jefe
        es_jefe = True
    else:
        familia = Familia.objects.filter(miembros=usuario).first()

    # Obtener horarios del usuario
    horarios_usuario = Horario.objects.filter(usuario=usuario)

    # Crear o editar horario
    if request.method == "POST":
        form = HorarioForm(request.POST)
        if form.is_valid():
            horario = form.save(commit=False)
            horario.usuario = request.user
            horario.disponible = True  # Solo guarda si está disponible
            horario.save()
            messages.success(request, "Horario agregado correctamente 🕒")
            return redirect("perfil")
    else:
        form = HorarioForm()

    # Si pertenece a una familia, obtener sus miembros
    miembros = familia.miembros.exclude(id=usuario.id) if familia else None

    contexto = {
        "usuario": usuario,
        "familia": familia,
        "es_jefe": es_jefe,
        "miembros": miembros,
        "horarios_usuario": horarios_usuario,
        "form": form,
    }
    return render(request, "perfil.html", contexto)


@login_required
def editar_horario(request, id):
    """Permite editar un horario existente."""
    horario = get_object_or_404(Horario, id=id, usuario=request.user)
    if request.method == "POST":
        form = HorarioForm(request.POST, instance=horario)
        if form.is_valid():
            form.save()
            messages.success(request, "Horario actualizado correctamente ✅")
            return redirect("perfil")
    else:
        form = HorarioForm(instance=horario)
    return render(request, "editar_horario.html", {"form": form})


@login_required
def tareas(request):
    usuario = request.user
    familia_usuario = (
        Familia.objects.filter(jefe=usuario).first()
        or Familia.objects.filter(miembros=usuario).first()
    )

    if not familia_usuario:
        return render(request, 'tareas.html', {
            'tareas': [],
            'mensaje': "No perteneces a ningún núcleo. Pide a tu jefe de hogar que te invite o crea uno."
        })

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        responsable_username = request.POST.get('responsable')
        if nombre and responsable_username:
            try:
                responsable = User.objects.get(username=responsable_username)
            except User.DoesNotExist:
                responsable = usuario
            Tarea.objects.create(
                nombre=nombre,
                responsable=responsable,
                familia=familia_usuario
            )
        return redirect('tareas')

    tareas = Tarea.objects.filter(familia=familia_usuario)
    from itertools import chain
    miembros = list(chain([familia_usuario.jefe], familia_usuario.miembros.all()))

    return render(request, 'tareas.html', {
        'tareas': tareas,
        'familia': familia_usuario,
        'miembros': miembros
    })


@login_required
def crear_familia(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre")
        if nombre:
            if Familia.objects.filter(jefe=request.user).exists():
                messages.warning(request, "Ya eres jefe de una familia.")
                return redirect("perfil")

            elif Familia.objects.filter(miembros=request.user).exists():
                messages.warning(request, "Ya perteneces a una familia, no puedes crear otra.")
                return redirect("perfil")

            nueva_familia = Familia.objects.create(nombre=nombre, jefe=request.user)
            nueva_familia.miembros.add(request.user)
            messages.success(request, f"Familia '{nombre}' creada con éxito 🎉")
            return redirect("perfil")
        else:
            messages.error(request, "Debes ingresar un nombre para la familia.")
    return render(request, "crear_familia.html")


@login_required
def invitar_miembro(request):
    if request.method == "POST":
        nombre_usuario = request.POST.get("nombre_usuario")
        codigo = request.POST.get("codigo")

        if nombre_usuario:
            try:
                usuario_a_invitar = User.objects.get(username=nombre_usuario)
                familia = Familia.objects.filter(jefe=request.user).first()
                if not familia:
                    messages.error(request, "No eres jefe de ninguna familia.")
                else:
                    familia.miembros.add(usuario_a_invitar)
                    messages.success(request, f"{nombre_usuario} fue agregado a tu familia.")
            except User.DoesNotExist:
                messages.error(request, "Ese usuario no existe.")
            return redirect('perfil')

        elif codigo:
            try:
                familia = Familia.objects.get(codigo_invitacion=codigo)
                familia.miembros.add(request.user)
                messages.success(request, f"Te has unido a la familia '{familia.nombre}'.")
                return redirect('perfil')
            except Familia.DoesNotExist:
                messages.error(request, "Código de invitación inválido.")
    return render(request, 'invitar_miembro.html')


@login_required
def unirse_familia(request):
    if request.method == "POST":
        codigo = request.POST.get("codigo")
        try:
            familia = Familia.objects.get(codigo_invitacion=codigo)
            if familia.miembros.filter(id=request.user.id).exists():
                messages.warning(request, "Ya perteneces a esta familia.")
            elif Familia.objects.filter(jefe=request.user).exists():
                messages.warning(request, "Eres jefe/a de otra familia, no puedes unirte.")
            else:
                familia.miembros.add(request.user)
                messages.success(request, f"Te uniste a la familia '{familia.nombre}' 🎉")
                return redirect("perfil")
        except Familia.DoesNotExist:
            messages.error(request, "El código ingresado no corresponde a ninguna familia.")
    return render(request, "unirse_familia.html")


# vistas de horario

@login_required
def agregar_horario(request):
    if request.method == 'POST':
        form = HorarioForm(request.POST)
        if form.is_valid():
            horario = form.save(commit=False)
            horario.usuario = request.user
            horario.save()
            return redirect('perfil')
    else:
        form = HorarioForm()
    return render(request, 'agregar_horario.html', {'form': form})


@login_required
def ver_horario(request):
    horarios = Horario.objects.filter(usuario=request.user)
    return render(request, 'ver_horario.html', {'horarios': horarios})

@login_required
def eliminar_horario(request, horario_id):
    horario = get_object_or_404(Horario, id=horario_id, usuario=request.user)
    horario.delete()
    return redirect('ver_horario')

# Autenticación

from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout

def registro(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('inicio')
    else:
        form = UserCreationForm()
    return render(request, 'registro.html', {'form': form})


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


def logout_view(request):
    logout(request)
    return redirect('inicio')

# API restful
class TareaViewSet(viewsets.ModelViewSet):
    queryset = Tarea.objects.all()
    serializer_class = TareaSerializer


def completar_tarea(request, id):
    tarea = get_object_or_404(Tarea, id=id)
    if request.method == "POST":
        tarea.estado = "hecha" if tarea.estado == "pendiente" else "pendiente"
        tarea.save()
    return redirect('tareas')