from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from rest_framework import viewsets
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
import json # Necesario para serializar datos a JavaScript
from .models import Tarea, Familia, Horario, Perfil
from .forms import HorarioForm, RegistroForm, PerfilForm, UserEditForm, TareaForm
from .serializers import TareaSerializer
from itertools import chain, cycle 
from django.db import transaction 
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, fields 
from datetime import timedelta, date, datetime

#🚨🚨🚨NO CAMBIAR NOMBRES DE VARIABLES NI FUNCIONES A MENOS QUE SEA ABSOLUTA Y ESTRICTAMENTE NECESARIO 🚨🚨🚨
# VISTAS HTML PRINCIPALES (🚨TOCAR VISTAS EXISTENTES SOLO DE SER NECESARIO Y CON CUIDADO🚨)

def inicio(request):
    #Vista de inicio: muestra la familia del usuario si existe.
    familia = None
    if request.user.is_authenticated:
        familia = (Familia.objects.filter(jefe=request.user).first() or 
                   Familia.objects.filter(miembros=request.user).first())
    return render(request, 'inicio.html', {'familia': familia})

#perfil y familias

    # Mapeo de códigos de día a números de weekday de Python (Lunes=0, Domingo=6)
DAY_MAPPING = {
    'LU': 0, 'MA': 1, 'MI': 2, 'JU': 3, 'VI': 4, 'SA': 5, 'DO': 6, 
    'LUN': 0, 'MAR': 1, 'MIE': 2, 'JUE': 3, 'VIE': 4, 'SAB': 5, 'DOM': 6
}
DAY_CODES = list(DAY_MAPPING.keys())

@login_required
def perfil(request):
    #muestra la información del usuario, su familia, horarios y tareas.
    usuario = request.user

    # Obtener todas las familias a las que el usuario pertenece
    familias_jefe = Familia.objects.filter(jefe=usuario)
    familias_miembro = Familia.objects.filter(miembros=usuario).exclude(jefe=usuario)
    familias_a_consultar = list(chain(familias_jefe, familias_miembro))

    #si el usuario no tiene familia, lo redirige a crear una
    if not familias_a_consultar:
        return redirect('crear_familia')
    
    # Establecer el contexto principal (para la cabecera, formularios)
    familia = familias_jefe.first() if familias_jefe.exists() else familias_miembro.first()
    es_jefe = familias_jefe.exists()

    #obtener horarios disponibles del usuario
    horarios_disponibles = Horario.objects.filter(usuario=usuario, disponible=True)
    disponibilidad_data = {}

    for h in horarios_disponibles:
        dia_semana = h.dia
        if dia_semana not in disponibilidad_data:
            disponibilidad_data[dia_semana] = []
        disponibilidad_data[dia_semana].append({
            'inicio': str(h.hora_inicio),
            'termino': str(h.hora_termino),
        })

    # TAREAS PENDIENTES PARA EL CALENDARIO (¡CORREGIDO!)
    tareas_pendientes_data = []
    
    # 🚨 FILTRO CORREGIDO: Muestra solo las instancias generadas y asignadas al usuario.
    tareas_qs = Tarea.objects.filter(
        familia__in=familias_a_consultar,
        estado='pendiente',
        responsable__isnull=False, # 🛡️ Debe tener responsable (solo asignaciones)
    ).filter(
        # 🛡️ Debe ser instancia (sin recurrencia)
        Q(dias_recurrencia_csv__isnull=True) | Q(dias_recurrencia_csv__exact='') 
    ).select_related('responsable')
    
    # Adaptamos la data al formato de calendario (title, start)
    for t in tareas_qs:
        
        # 1. Buscar el día de la semana en el nombre de la tarea (ej. "LU")
        dia_encontrado = None
        for code in DAY_CODES:
            if f"({code})" in t.nombre.upper() or t.nombre.upper().endswith(f"({code})"):
                dia_encontrado = code
                break
                
        
        # 2. Inicializar la fecha de inicio del evento
        fecha_inicio_evento = t.fecha_creacion.date()
        
        if dia_encontrado:
            # 3. Calcular la fecha correcta: Próximo día de la semana, a partir de la fecha de creación
            target_weekday = DAY_MAPPING[dia_encontrado]
            current_weekday = t.fecha_creacion.date().weekday() # Lunes=0, Domingo=6
            
            # Calcular cuántos días hay que avanzar
            days_to_advance = (target_weekday - current_weekday + 7) % 7
            
            fecha_inicio_evento = t.fecha_creacion.date() + timedelta(days=days_to_advance)
        #Crear el objeto de datos con la fecha calculada y el responsable
        titulo_con_responsable = f"{t.nombre} — Resp: {t.responsable.username}" if t.responsable else f"{t.nombre} (Sin Asignar)"

        # 4. Crear el objeto de datos con la fecha calculada
        tareas_pendientes_data.append({
            'id': t.id,
            'title': titulo_con_responsable, 
            'start': fecha_inicio_evento.isoformat(), # 🚨 Usa la fecha CALCULADA
            'responsable': t.responsable.username if t.responsable else 'Sin asignar', 
            'tiempo_requerido_minutos': t.tiempo_requerido_minutos,
            'allDay': True,
        })
        
    #si pertenece a una familia, obtener sus miembros (sin el usuario actual)
    miembros = familia.miembros.exclude(id=usuario.id) if familia else None

    #manejo del perfil con fecha de nacimiento
    perfil, creado = Perfil.objects.get_or_create(usuario=usuario)

    if request.method == 'POST':
        form = PerfilForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado correctamente ✅")
            return redirect('perfil')
    else:
        form = PerfilForm(instance=perfil)

    contexto = {
        'usuario': usuario,
        'familia': familia,
        'es_jefe': es_jefe,
        'miembros': miembros,
        'horarios_disponibles': horarios_disponibles,
        'disponibilidad_json': json.dumps(disponibilidad_data),
        'tareas_json': json.dumps(tareas_pendientes_data), 
        'form': form,
        'perfil': perfil,
    }

    return render(request, 'perfil.html', contexto)

#gestión de tareas
@login_required
def tareas(request):
    usuario = request.user
    
    # 1. Obtiene TODAS las familias donde el usuario es jefe
    familias_jefe = Familia.objects.filter(jefe=usuario)
    es_jefe = familias_jefe.exists()
    
    # 2. Obtiene TODAS las familias donde el usuario es miembro (excluyendo donde ya es jefe)
    familias_miembro = Familia.objects.filter(miembros=usuario).exclude(jefe=usuario)
    
    # 3. Determinar el QuerySet de Tareas
    familias_a_consultar = list(chain(familias_jefe, familias_miembro))
    
    if not familias_a_consultar:
        return render(request, 'tareas.html', {
            'tareas': [],
            'mensaje': "No perteneces a ninguna familia. Crea o únete a una para ver tareas.",
            'form': TareaForm() 
        })

    # Consulta unificada: TAREAS ORIGINALES (PLANTILLAS) para la LISTA
    # 🚨 FILTRO CORREGIDO: Solo muestra las plantillas base (con recurrencia definida)
    tareas = Tarea.objects.filter(
        familia__in=familias_a_consultar,
        estado='pendiente' # Solo queremos ver las tareas que requieren acción
    ).order_by('-fecha_creacion')

    # 4. Preparar contexto para la plantilla
    contexto = {
        'tareas': tareas,
        'es_jefe': es_jefe, # Es jefe en al menos una familia
        'familias_jefe': familias_jefe,
        'es_jefe_multi': familias_jefe.count() > 1,
        'form': TareaForm(user=usuario) if es_jefe else TareaForm(), 
        'miembros_por_familia': {}, 
    }

    # 5. Lógica de creación de tareas (Solo si es jefe)
    if es_jefe:
        # Prepara los miembros solo para las familias donde es jefe (para el formulario, etc.)
        for familia in familias_jefe:
            contexto['miembros_por_familia'][familia.id] = list(chain([familia.jefe], familia.miembros.all()))

        if request.method == 'POST':
            
            # Simplificación: La familia se asigna automáticamente (no se pide en POST)
            familia_seleccionada = familias_jefe.first() 
            
            form = TareaForm(request.POST, user=usuario) 
            
            if form.is_valid():
                tarea = form.save(commit=False)
                tarea.familia = familia_seleccionada # Asignar la familia principal
                tarea.save()
                messages.success(request, f"Tarea creada exitosamente para '{familia_seleccionada.nombre}'. ✅")
                return redirect('tareas')
            else:
                messages.error(request, "Error al crear la tarea. Revisa los campos marcados.")
                contexto['form'] = form 
    
    elif not es_jefe and familias_miembro.exists():
        # Si es SOLO miembro, solo necesita ver las tareas, no crear/editar.
        contexto['familia_miembro'] = familias_miembro.first()

    return render(request, 'tareas.html', contexto)

@login_required
def completar_tarea(request, id):
    #cambia el estado de una tarea (pendiente/hecha)
    tarea = get_object_or_404(Tarea, id=id)
    if request.method == "POST":
        tarea.estado = "hecha" if tarea.estado == "pendiente" else "pendiente"
        tarea.save()
    return redirect('tareas')

@login_required
def editar_tarea(request, tarea_id):
    # Obtiene la tarea, asegurando que el usuario sea el jefe de la familia a la que pertenece
    tarea = get_object_or_404(Tarea, id=tarea_id)

    # Verificar si el usuario es jefe de la familia de la tarea
    if not Familia.objects.filter(jefe=request.user, id=tarea.familia.id).exists():
        messages.error(request, "❌ No tienes permiso para editar esta tarea.")
        return redirect('tareas')

    #Manejo del formulario
    if request.method == 'POST':
        form = TareaForm(request.POST, instance=tarea, user=request.user) 
        if form.is_valid():
            form.save()
            messages.success(request, f"Tarea '{tarea.nombre}' actualizada correctamente. ✅")
            return redirect('tareas')
        else:
            messages.error(request, "Hubo un error al guardar el tarea. Revisa los campos.")
    else:
        # Petición GET: Cargar el formulario prellenado
        form = TareaForm(instance=tarea, user=request.user) 

    contexto = {
        'form': form,
        'tarea': tarea
    }
    return render(request, 'editar_tarea.html', contexto)


@login_required
def eliminar_tarea(request, tarea_id):
    # Obtiene la tarea
    tarea = get_object_or_404(Tarea, id=tarea_id)

    # Verificar si el usuario es jefe de la familia de la tarea
    if not Familia.objects.filter(jefe=request.user, id=tarea.familia.id).exists():
        messages.error(request, "❌ No tienes permiso para eliminar esta tarea.")
        return redirect('tareas')

    # Lógica de eliminación
    if request.method == 'POST':
        nombre_tarea = tarea.nombre
        tarea.delete()
        messages.success(request, f"Tarea '{nombre_tarea}' eliminada correctamente. 🗑️")
        return redirect('tareas')

    # Petición GET: Mostrar la página de confirmación de eliminación (opcional)
    return render(request, 'eliminar_tarea.html', {'tarea': tarea})

#gestión de familias
@login_required
def crear_familia(request):
    # Permite crear una nueva familia solo si el usuario NO es jefe de otra.
    
    if request.method == "POST":
        nombre = request.POST.get("nombre")

        if not nombre:
            messages.error(request, "Debes ingresar un nombre para la familia.")
            # Es mejor usar render aquí para conservar los mensajes de error
            return render(request, "crear_familia.html") 

        # Restricción principal: Si ya es jefe de una familia, lo detenemos.
        if Familia.objects.filter(jefe=request.user).exists():
            messages.warning(request, "Ya eres jefe de una familia y no puedes crear otra.")
            return redirect("perfil")

        # Crear la nueva familia
        nueva_familia = Familia.objects.create(nombre=nombre, jefe=request.user)
        # Añadir al usuario como miembro de su nueva familia
        nueva_familia.miembros.add(request.user) 
        messages.success(request, f"Familia '{nombre}' creada con éxito 🎉")
        return redirect("perfil")

    return render(request, "crear_familia.html")

@login_required
def invitar_miembro(request):
    #Permite al jefe invitar usuarios o unirse con código
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
    # Permite unirse a una familia mediante un código de invitación, incluso si ya pertenece a otras.
    
    if request.method == "POST":
        codigo = request.POST.get("codigo")
        if not codigo:
            messages.error(request, "Debes ingresar un código de invitación.")
            return render(request, "unirse_familia.html")

        try:
            familia = Familia.objects.get(codigo_invitacion=codigo)
            
            # NUEVA RESTRICCIÓN: Chequear si el usuario YA es miembro (incluyendo si es jefe) de ESTA familia.
            if familia.jefe == request.user or familia.miembros.filter(id=request.user.id).exists():
                messages.warning(request, f"Ya perteneces a la familia '{familia.nombre}'.")
                return redirect("perfil")
            
            # Si pasa la validación, unir al usuario como miembro
            familia.miembros.add(request.user)
            messages.success(request, f"Te uniste a la familia '{familia.nombre}' 🎉")
            return redirect("perfil")
            
        except Familia.DoesNotExist:
            messages.error(request, "El código ingresado no corresponde a ninguna familia.")
            
    return render(request, "unirse_familia.html")


# vistas de horario

@login_required
def agregar_horario(request):
    #agrega un horario al usuario autenticado
    if request.method == 'POST':
        form = HorarioForm(request.POST)
        if form.is_valid():
            horario = form.save(commit=False)
            horario.usuario = request.user
            horario.disponible = True
            horario.save()
            messages.success(request, '¡Horario agregado con éxito! Puedes verlo en la lista.')
            return redirect('ver_horario')
    else:
        form = HorarioForm()
    return render(request, 'agregar_horario.html', {'form': form})

@login_required
def ver_horario(request):
    #muestra los horarios del usuario autenticado
    usuario = request.user #usuario autenticado
    horarios = Horario.objects.filter(usuario=usuario)
    return render(request, 'ver_horario.html', {'horarios': horarios})

@login_required
def editar_horario(request, horario_id):
    #obteiene la instancia del horario, asegurando que solo el dueño pueda editarlo.
    horario_instancia = get_object_or_404(Horario, id=horario_id, usuario=request.user)
    
    if request.method == 'POST':
        form = HorarioForm(request.POST, instance=horario_instancia)
        if form.is_valid():
            form.save()
            messages.success(request, "Horario actualizado correctamente. ✅")
            #redirige a la página principal de perfil donde se ven los horarios
            return redirect('perfil') 
        else:
            messages.error(request, "Hubo un error al guardar el horario. Revisa los campos.")
            
    else:
        # Inicializa el formulario llenado antes con los datos actuales
        form = HorarioForm(instance=horario_instancia)
        
    contexto = {
        'form': form,
        'horario': horario_instancia
    }
    return render(request, 'editar_horario.html', contexto)

@login_required
def eliminar_horario(request, horario_id):
    # Elimina un horario del usuario.
    horario = get_object_or_404(Horario, id=horario_id, usuario=request.user)
    horario.delete()
    messages.success(request, "Horario eliminado correctamente.")
    return redirect('ver_horario')

# Autenticación

def registro(request):
    #registro de nuevos usuarios con email y fecha de nacimiento
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "¡Registro exitoso! Bienvenido a HomeBalance 🎉")
            return redirect('inicio')
    else:
        form = RegistroForm()
    return render(request, 'registro.html', {'form': form})


def login_view(request):
    #inicio de sesión de usuarios
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
    #cierre de sesión de usuarios
    logout(request)
    return redirect('inicio')

# API restful
class TareaViewSet(viewsets.ModelViewSet):
    serializer_class = TareaSerializer
    
    def get_queryset(self):
        """
        Devuelve solo las tareas que pertenecen a las familias del usuario logueado.
        """
        user = self.request.user
        
        familias_del_usuario = Familia.objects.filter(
            Q(jefe=user) | Q(miembros=user)
        ).distinct()
        
        # Se añade select_related('responsable') y se filtra
        return Tarea.objects.filter(familia__in=familias_del_usuario).select_related('responsable')

#funciónes helper

def get_next_weekday(start_date, day_code):
    """Calcula la fecha del próximo día de la semana a partir de start_date."""
    # Mapeo de códigos de día a índice de día de la semana (Lunes=0, Domingo=6)
    day_map = {'LUN': 0, 'MAR': 1, 'MIE': 2, 'JUE': 3, 'VIE': 4, 'SAB': 5, 'DOM': 6}
    
    target_weekday = day_map.get(day_code)
    if target_weekday is None:
        return None
    
    # current_weekday es el día de la semana de start_date (Lunes=0, Domingo=6)
    current_weekday = start_date.weekday()
    
    # Calcular la diferencia de días
    days_until_target = target_weekday - current_weekday
    
    # Si el día objetivo ya pasó o es hoy, se calcula para la próxima semana (+7 días)
    if days_until_target <= 0:
        days_until_target += 7
        
    return start_date + timedelta(days=days_until_target)

def calcular_capacidad_para_tarea(miembro, tarea, dia_requerido):
    #Calcula el score de capacidad de un miembro para UNA TAREA ESPECÍFICA, filtrando SOLO por el día requerido (dia_requerido).

    # 1. Preparación del día requerido (en MAYÚSCULAS)
    dia_codigo = dia_requerido.upper()
    
    # 2. Obtener horarios SOLO para el día requerido
    # Filtramos directamente en la DB para el día específico
    horarios_query = Horario.objects.filter(
        usuario=miembro, 
        dia=dia_codigo, # Filtro directo
        disponible=True
    )
    
    if not horarios_query.exists():
        # Si no hay NINGÚN horario para este día, descalificado.
        return 0 
            
    # 3. Cálculo de Minutos Disponibles en ese día
    minutos_disponibles_en_dia = 0
    
    for horario in horarios_query:
        # Cálculo de la duración (MEJORADO: Usa timedelta para evitar negativos en cruces de medianoche si es necesario)
        # Nota: Usaremos el cálculo original si no hay cruce de medianoche en los datos
        duracion = (horario.hora_termino.hour * 60 + horario.hora_termino.minute) - \
                   (horario.hora_inicio.hour * 60 + horario.hora_inicio.minute)
                   
        minutos_disponibles_en_dia += duracion
            
    # 4. Filtro de Tiempo: ¿El tiempo total disponible es menor que el tiempo de la tarea?
    if minutos_disponibles_en_dia < tarea.tiempo_requerido_minutos:
        return 0 
        
    # 5. Score
    score_capacidad = minutos_disponibles_en_dia 

    return score_capacidad

# VISTA PRINCIPAL: REPARTO DE TAREAS
@login_required
def repartir_tareas(request, familia_id):
    """
    Ejecuta el algoritmo de reparto. Se crea una INSTANCIA ÚNICA por cada día de recurrencia,
    sin usar fecha_vencimiento para la programación.
    """
    
    usuario = request.user
    # Seguridad: Solo el jefe de esta familia puede repartir
    familia = get_object_or_404(Familia, id=familia_id, jefe=usuario)
    
    if request.method == "POST":
        
        with transaction.atomic():
            
            miembros = list(familia.miembros.all())
            
            if not miembros:
                messages.error(request, "❌ No hay miembros en esta familia para asignar tareas.")
                return redirect('tareas')
                
            # 1. TAREAS ORIGINALES (Plantillas): Las que tienen recurrencia y están pendientes
            tareas_recurrentes_qs = Tarea.objects.filter(
                familia=familia, 
                estado='pendiente' 
            ).exclude(
                dias_recurrencia_csv__isnull=True
            ).exclude(
                dias_recurrencia_csv__exact=''
            ).order_by('fecha_creacion')
            
            if not tareas_recurrentes_qs.exists():
                messages.info(request, "🎉 No hay tareas recurrentes pendientes que repartir.")
                return redirect('tareas')

            asignaciones_realizadas = 0
            fallos_reportados = []
            
            hoy = date.today()
            tareas_a_procesar = list(tareas_recurrentes_qs)

            # 🚨 CORRECCIÓN CLAVE: El bucle interno ahora crea INSTANCIAS ÚNICAS
            # por cada día de la semana que se requiere la tarea.
            for tarea_original in tareas_a_procesar: 
                dias_requeridos = set(tarea_original.dias_recurrencia_csv.upper().split(','))
                
                # 🚨 Problema de Aglomeración: Iteramos por día y creamos la instancia
                for dia_codigo in dias_requeridos:
                        
                    candidatos_validos = {} # {miembro: score}
                    
                    # 2.2. Cálculo de Candidatos: Filtro y Score
                    for miembro in miembros:
                        
                        # A. FILTRO DE EDAD
                        edad_requerida = tarea_original.edad_minima or 0
                        perfil = getattr(miembro, 'perfil', None)
                        edad_miembro = perfil.edad() if perfil and perfil.edad() is not None else 0
                        
                        if edad_miembro < edad_requerida:
                            continue 
                            
                        # B. FILTRO DE CAPACIDAD Y DÍAS (Usando la función Helper)
                        score = calcular_capacidad_para_tarea(miembro, tarea_original, dia_codigo) 
                        
                        if score > 0: 
                            candidatos_validos[miembro] = score
                    
                    
                    # 2.3. ASIGNACIÓN AL MEJOR CANDIDATO
                    if candidatos_validos:
                        
                        candidatos_finales = []
                        for miembro, score in candidatos_validos.items():
                            # LÓGICA DE EQUIDAD RESTAURADA 
                            tareas_pendientes_count = Tarea.objects.filter(
                                responsable=miembro, 
                                estado='pendiente'
                            ).exclude(
                                dias_recurrencia_csv__isnull=False 
                            ).count()
                            
                            candidatos_finales.append((miembro, score, tareas_pendientes_count))

                        # Ordenar por MENOR carga (x[2]), luego por MAYOR score (-x[1])
                        candidatos_finales.sort(key=lambda x: (x[2], -x[1])) 
                        responsable_elegido = candidatos_finales[0][0]
                        
                        # CREACIÓN DE LA INSTANCIA DE TAREA DIARIA
                        Tarea.objects.create(
                            nombre=f"{tarea_original.nombre} ({dia_codigo})", # Nombre con día para referencia
                            responsable=responsable_elegido, 
                            familia=familia,
                            estado='pendiente',
                            tiempo_requerido_minutos=tarea_original.tiempo_requerido_minutos,
                            # 🚨 CLAVE: dias_recurrencia_csv es NULL para marcarla como INSTANCIA
                            dias_recurrencia_csv=None 
                        )
                        asignaciones_realizadas += 1
                    
                    else:
                        fallos_reportados.append(f"La tarea '{tarea_original.nombre}' para el día **{dia_codigo}** no encontró ningún miembro disponible.")

            
            # 4. RESULTADO FINAL
            for fallo in fallos_reportados:
                messages.warning(request, f"⚠️ {fallo}")

            if asignaciones_realizadas > 0:
                messages.success(request, f"🎉 ¡Reparto de tareas completado! Se asignaron {asignaciones_realizadas} instancias de tareas con éxito.")
            
            return redirect('tareas')
            
    # Si es GET, mostramos la página de confirmación
    contexto = {'familia': familia}
    return render(request, 'repartir_confirmar.html', contexto)

@login_required
def limpiar_instancias_tareas(request, familia_id):
    """
    Permite al jefe de hogar eliminar instancias de tareas diarias no completadas
    y automáticamente restablece el estado de las plantillas recurrentes a 'pendiente'.
    """
    usuario = request.user
    
    # Seguridad: Solo el jefe de esta familia puede ejecutar la limpieza
    familia = get_object_or_404(Familia, id=familia_id, jefe=usuario)
    
    # Solo el jefe puede continuar
    if not Familia.objects.filter(jefe=usuario, id=familia_id).exists():
        messages.error(request, "❌ No tienes permiso para limpiar estas tareas.")
        return redirect('perfil')

    if request.method == "POST":
        # 1. Filtros (simplificados)
        filtro_dia = request.POST.get('filtro_dia')
        filtro_fecha = request.POST.get('filtro_fecha')
        
        # QuerySet base: Solo instancias diarias pendientes (las que están en el calendario)
        qs = Tarea.objects.filter(
            familia=familia,
            estado='pendiente',
            dias_recurrencia_csv__isnull=True 
        )
        
        filtro_aplicado = "todo el calendario"

        # 2. Aplicar Filtros Específicos
        if filtro_dia and filtro_dia != 'TODOS':
            # Filtra por el nombre asignado en el reparto (ej: Cocinar (LUN))
            qs = qs.filter(nombre__icontains=f"({filtro_dia.upper()})")
            filtro_aplicado = f"el día {filtro_dia.upper()}"

        elif filtro_fecha:
            messages.warning(request, "⚠️ El filtro por fecha/semana está deshabilitado. No se aplicó.")
            
        # 3. Borrar INSTANCIAS (Tareas diarias/semanales)
        tareas_borradas, _ = qs.delete()
        
        # 🚨 LÓGICA CLAVE: RESTABLECER PLANTILLAS (listas para el siguiente reparto) 🚨
        tareas_plantilla_restablecidas = Tarea.objects.filter(
            familia=familia,
        ).exclude(
            dias_recurrencia_csv__isnull=True
        ).exclude(
            dias_recurrencia_csv__exact=''
        ).update(estado='pendiente')
        
        messages.success(request, f"🗑️ Se eliminaron {tareas_borradas} instancias de tareas pendientes de {filtro_aplicado}.")
        
        if tareas_plantilla_restablecidas > 0:
             messages.info(request, f"🔄 {tareas_plantilla_restablecidas} tareas plantilla (base) se restablecieron a 'pendiente' para el siguiente reparto automático.")
        
        return redirect('perfil') 
        
    # Si es GET, muestra la página de confirmación con opciones de filtro
    DIAS_SEMANA_CHOICES = [
        ('LUN', 'Lunes'), ('MAR', 'Martes'), ('MIE', 'Miércoles'), 
        ('JUE', 'Jueves'), ('VIE', 'Viernes'), ('SAB', 'Sábado'), ('DOM', 'Domingo')
    ]
    
    contexto = {
        'familia': familia,
        'dias_semana': DIAS_SEMANA_CHOICES
    }
    return render(request, 'limpiar_confirmar.html', contexto)