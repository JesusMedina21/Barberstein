from rest_framework import serializers
from .models import *
from datetime import datetime, time
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from django.db.models import Avg 
User = get_user_model() # Obtén el modelo de usuario actual
from rest_framework import serializers
from django.core.validators import MinLengthValidator
from rest_framework.exceptions import ValidationError
from djoser import utils

# Diccionario para mapear nombres de días a números de semana de Python (lunes=0, domingo=6)
DAYS_OF_WEEK_MAP = {
    'lunes': 0,
    'martes': 1,
    'miercoles': 2,
    'jueves': 3,
    'viernes': 4,
    'sábado': 5,
    'domingo': 6,
}

###############################################AUTH

class UserCreateSerializer(serializers.ModelSerializer):
    barberia = serializers.JSONField(required=False)
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'password', 'first_name', 'last_name', 'biometric', 'barberia']
        extra_kwargs = {
            'password': {'write_only': True},
            'biometric': {'write_only': True},
        }
    def to_representation(self, instance):
       rep = super().to_representation(instance)
       rep['id'] = str(rep['id'])  # Asegúrate de que el id sea una cadena
       return rep
    def create(self, validated_data):
        barberia_data = validated_data.pop('barberia', None)
        user = User(**validated_data)
        user.set_password(validated_data['password'])
        user.save()
        if barberia_data:
            user.barberia = barberia_data
            user.save()
        return user

class EmailCambiadoSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_email = serializers.EmailField()

    default_error_messages = {
        "invalid_token": "Token inválido o expirado",
        "invalid_uid": "Usuario inválido",
    }

    def validate(self, attrs):
        try:
            uid = utils.decode_uid(attrs["uid"])
            self.user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError({"uid": self.default_error_messages["invalid_uid"]})

        return attrs
    
class ClienteSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ['id', 'last_name', 'first_name', 'username', 'email', 'password', 'biometric']
        extra_kwargs = {
            'password': {'write_only': True},
            'biometric': {'write_only': True}
        }

    def get_id(self, obj):
        return str(obj.id) if obj.id else None
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        
        request = self.context.get('request', None)
        
        # Lógica para ocultar el ID
        # Mantén el ID si:
        # 1. El request es None (es decir, es una operación interna de serialización, como la creación de un nuevo usuario en la respuesta)
        # 2. El usuario autenticado es staff.
        # 3. El usuario autenticado es el mismo que la instancia serializada.
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            if not request.user.is_staff and str(instance.id) != str(request.user.id): 
                rep.pop('id', None)
        elif request: # Si hay un request pero NO hay usuario autenticado (registro de un nuevo cliente)
            # No ocultes el ID en este caso para la respuesta de creación.
            # El ID debería estar presente en la respuesta del registro.
            pass
        else: # Si no hay request (ej. serialización interna sin contexto de request)
            pass # Mantén el ID, o decide si quieres ocultarlo en otros contextos

        return {key: value for key, value in rep.items() if value is not None}

    def create(self, validated_data):
        user = User(**validated_data)
        user.set_password(validated_data['password'])
        # Aquí se asegura que la cuenta no esté activa al crearse
        user.is_active = False
        user.save()  
        return user

    def update(self, instance, validated_data):
        old_username = instance.username
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        validated_data.pop('barberia', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        
        # Si el username cambió, actualizar en los comentarios de la nueva colección
        if 'username' in validated_data and old_username != validated_data['username']:
            # ¡CAMBIO AQUÍ! Usa cliente_username_cached
            Comment.objects.filter(cliente=instance).update(cliente_username_cached=instance.username)
            
        return instance

    def validate(self, data):
        
        # Campos que están explícitamente definidos en este serializador y son para entrada
        expected_input_fields = {'username', 'first_name', 'last_name', 'email', 'password', 'biometric'}
        
        initial_keys = set(self.initial_data.keys())
        
        # Encontrar campos que fueron enviados pero no son esperados por este serializer
        extra_fields = initial_keys - expected_input_fields
        
        if extra_fields:
            raise serializers.ValidationError(
                f"Campos no permitidos para clientes: {', '.join(sorted(list(extra_fields)))}. "
                f"Campos válidos para clientes: {', '.join(sorted(list(expected_input_fields)))}"
            )
        return data

#########################################################33#Serializadores para la barberia 

class ServicioBarberiaSerializer(serializers.Serializer):
    description = serializers.CharField(required=True)
    #imagen = serializers.CharField(required=True)


class HorarioSerializer(serializers.Serializer):
    turnos_max = serializers.IntegerField(min_value=1, required=True)
    days = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo'
        ]),
        required=True
    )

    def to_representation(self, instance):
        return [
            {"turnos_max": instance['turnos_max']},
            {"days": instance['days']}
        ]

    def to_internal_value(self, data):
        if isinstance(data, list):
            internal_data = {}
            for item in data:
                if isinstance(item, dict):
                    if 'turnos_max' in item:
                        internal_data['turnos_max'] = item['turnos_max']
                    if 'days' in item:
                        days = item['days']
                        internal_data['days'] = [days] if isinstance(days, str) else days
            return internal_data
        return super().to_internal_value(data)

class TimeFieldToString(serializers.Field):
    def to_representation(self, value):
        """Convierte time a string (ej: "16:30")"""
        if isinstance(value, str):
            return value  # Ya está en formato string
        return value.strftime('%H:%M') if value else None

    def to_internal_value(self, data):
        """Convierte string a objeto time, aceptando múltiples formatos"""
        try:
            if isinstance(data, time):
                return data  # Si ya es objeto time, lo devuelve
            
            if isinstance(data, str):
                # Elimina espacios y la 'Z' final si existe
                clean_data = data.strip().rstrip('Z')
                
                # Intenta con diferentes formatos
                for time_format in ['%H:%M', '%H:%M:%S', '%H:%M:%S.%f']:
                    try:
                        return datetime.strptime(clean_data, time_format).time()
                    except ValueError:
                        continue
                
            raise ValueError
        except (ValueError, TypeError):
            raise serializers.ValidationError(
                "Formato de hora inválido. Use HH:MM, HH:MM:SS o HH:MM:SS.sss"
            )
        
class BarberiaProfileSerializer(serializers.Serializer):
    name_barber = serializers.CharField(
        required=True,
        min_length=4,
        validators=[MinLengthValidator(4)],
        error_messages={
            'min_length': 'El nombre de la barbería debe tener al menos 4 caracteres.'
        }
    )
    phone = serializers.CharField(required=True)
    address = serializers.CharField(required=True)
    services = ServicioBarberiaSerializer(many=True, required=True)
    horario = HorarioSerializer(many=True, required=True)
    openingTime = TimeFieldToString(required=True)
    closingTime = TimeFieldToString(required=True)
    rating = serializers.SerializerMethodField(read_only=True)

    def validate(self, data):
        if data['openingTime'] == data['closingTime']:
            raise serializers.ValidationError({
                'openingTime': 'El horario de apertura no puede ser igual al horario de cierre.'
            })
        
        return data

    def validate_services(self, value):
        """
        Valida que el campo 'services' no sea una lista vacía.
        """
        if not value: # Si la lista está vacía
            raise serializers.ValidationError("El campo 'services' no puede estar vacío. Debe contener al menos un servicio.")
        return value

    def validate_horario(self, value):
        """
        Valida que el campo 'horario' tenga la estructura correcta
        """
        if not value:
            raise serializers.ValidationError("El campo 'horario' no puede estar vacío.")
        
        # Verificar que haya al menos un día y un turnos_max
        has_days = False
        has_turnos = False
        
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    if 'days' in item:
                        if item['days']:  # Verifica que no esté vacío
                            has_days = True
                    if 'turnos_max' in item:
                        has_turnos = True
        
        if not has_days:
            raise serializers.ValidationError("Debe especificar al menos un día en el horario.")
        if not has_turnos:
            raise serializers.ValidationError("Debe especificar el número máximo de turnos.")
        
        return value

    def get_rating(self, obj):
        # obj en este punto es el diccionario del perfil de barbería, no la instancia de User
        # Necesitamos el ID del usuario (la barbería) para buscar los comentarios.
        # Esto requerirá pasar el ID del usuario desde BarberiaSerializer.
        
        # Una forma más robusta es pasar el user_id al contexto del BarberiaProfileSerializer
        # O calcularlo en BarberiaSerializer y luego pasarlo al to_representation.
        # Por ahora, asumamos que obj es el objeto de User, no solo el dict de barberia.
        # Si obj es el dict, necesitarás el ID del usuario.
        
        # Si 'obj' es una instancia de User (como cuando es llamado desde BarberiaSerializer.to_representation)
        if isinstance(obj, User):
            barberia_user_id = obj.id
        # Si 'obj' es el diccionario 'barberia' del JSONField, y necesitas el ID del User padre
        else: # Esto es más probable si se llama desde dentro de BarberiaSerializer.to_representation
            # Accede al ID de la instancia de User que contiene este perfil de barbería
            # Esto asume que BarberiaSerializer pasa 'instance' a este serializador, lo cual es estándar.
            barberia_user_id = self.context.get('user_id_for_rating') # Necesitamos pasar este en el context
            if not barberia_user_id:
                return None # O lanzar un error si es un dato esencial

        # Busca los comentarios en la nueva colección Comment
        comments = Comment.objects.filter(barberia_id=barberia_user_id)
        if not comments.exists():
            return None
        
        total_rating = sum(c.rating for c in comments)
        return round(total_rating / comments.count(), 1)
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        
        # ***** MODIFICACIÓN CLAVE AQUÍ PARA OCULTAR 'rating' si es None *****
        if rep.get('rating') is None:
            rep.pop('rating', None)
        # *******************************************************************
        
        return rep
    

class BarberiaSerializer(serializers.ModelSerializer):
    barberia = BarberiaProfileSerializer(many=True, required=True)
    id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'biometric', 'barberia']
        extra_kwargs = {
            'password': {'write_only': True},
            'biometric': {'write_only': True}
        }

    def get_id(self, obj):
        return str(obj.pk) if obj.pk else None
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        
        request = self.context.get('request', None)
        
        # Pasa el user_id al contexto del BarberiaProfileSerializer para el cálculo del rating
        if 'barberia' in rep and rep['barberia']:
            # Pasa el ID del usuario actual para que BarberiaProfileSerializer pueda calcular el rating
            # 'instance' es la instancia de User, por lo tanto instance.id es el _id del usuario/barbería
            profile_serializer = self.fields['barberia']
            # Asegurarse de que el contexto se propague correctamente a los serializadores anidados
            profile_serializer.context['user_id_for_rating'] = str(instance.id)
            
            # Re-serializar el perfil para que el get_rating se active con el contexto
            rep['barberia'] = BarberiaProfileSerializer(
                instance.barberia[0] if instance.barberia else {},
                context={'user_id_for_rating': str(instance.id)}
            ).data

        return {key: value for key, value in rep.items() if value is not None}
    
    # **** AÑADE ESTE MÉTODO PARA LA VALIDACIÓN ****
    def validate_barberia(self, value):
        """
        Valida que el campo 'barberia' no sea una lista vacía.
        """
        if not value: # Si la lista está vacía (o None, aunque required=True ya lo maneja)
            raise serializers.ValidationError("El campo 'barberia' no puede estar vacío. Debe contener al menos un objeto de barbería.")
    
    # ***** AÑADE ESTA NUEVA VALIDACIÓN *****
        if len(value) > 1:
            raise serializers.ValidationError("No puedes tener mas de una barberia")
        
        barberia_data = value[0]
        name_barber = barberia_data.get('name_barber')
        
        if name_barber:
            # Filtra todos los usuarios que son barberías y busca si ya existe un
            # documento con el mismo 'name_barber'.
            # Usamos `barberia__0__name_barber` para acceder al primer elemento
            # de la lista `barberia` y su campo `name_barber` en MongoDB.
            if User.objects.filter(barberia__0__name_barber=name_barber).exists():
                raise serializers.ValidationError({"name_barber": "Ya existe una barbería con este nombre."})
        
        
        return value

    # Si necesitas validar múltiples campos a la vez, podrías usar el método `validate` general:
    # def validate(self, data):
    #     if 'barberia' in data and not data['barberia']:
    #         raise serializers.ValidationError({"barberia": "El campo 'barberia' no puede estar vacío. Debe contener al menos un objeto de barbería."})
    #     return data

    def create(self, validated_data):
        barberia_data = validated_data.pop('barberia', [])
        
        
        for barberia_item in barberia_data:
            # Procesar horario para guardarlo correctamente
            if 'horario' in barberia_item:
                horario_data = barberia_item['horario']
                # Convertir a formato normalizado para guardar en BD
                if isinstance(horario_data, list):
                    normalized_horario = {}
                    for item in horario_data:
                        if isinstance(item, dict):
                            if 'days' in item:
                                normalized_horario['days'] = item['days']
                            if 'turnos_max' in item:
                                normalized_horario['turnos_max'] = item['turnos_max']
                    barberia_item['horario'] = [normalized_horario]
            
            # ¡Ya convertido por TimeFieldToString.to_internal_value() a `time` object!
            # Aquí lo reconvertimos a string para guardarlo en JSONField
            if 'openingTime' in barberia_item and isinstance(barberia_item['openingTime'], time):
                barberia_item['openingTime'] = barberia_item['openingTime'].strftime('%H:%M')
            if 'closingTime' in barberia_item and isinstance(barberia_item['closingTime'], time):
                barberia_item['closingTime'] = barberia_item['closingTime'].strftime('%H:%M')

        user = User(**validated_data)
        user.set_password(validated_data['password'])
        # Aquí se asegura que la cuenta no esté activa al crearse
        user.is_active = False
        user.barberia = barberia_data # Aquí se asigna la lista con strings
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)

        barberia_data_from_request = validated_data.pop('barberia', None)
        
        if barberia_data_from_request is not None:
            existing_barberia_profile = instance.barberia[0] if instance.barberia and len(instance.barberia) > 0 else {}
            incoming_barberia_profile = barberia_data_from_request[0] if barberia_data_from_request and len(barberia_data_from_request) > 0 else {}

            # Procesar horario para la estructura deseada
            if 'horario' in incoming_barberia_profile:
                horario_data = incoming_barberia_profile['horario']
                new_horario = []
                for item in horario_data:
                    if isinstance(item, dict):
                        if 'days' in item and 'turnos_max' in item:
                            new_horario.append({'days': item['days']})
                            new_horario.append({'turnos_max': item['turnos_max']})
                    else:
                        new_horario.append(item)
                incoming_barberia_profile['horario'] = new_horario

            
            merged_barberia_profile = existing_barberia_profile.copy()
            merged_barberia_profile.update(incoming_barberia_profile)

            merged_barberia_profile.pop('rating', None)
            merged_barberia_profile.pop('comments', None)

            if 'openingTime' in merged_barberia_profile and isinstance(merged_barberia_profile['openingTime'], time):
                merged_barberia_profile['openingTime'] = merged_barberia_profile['openingTime'].strftime('%H:%M')
            
            if 'closingTime' in merged_barberia_profile and isinstance(merged_barberia_profile['closingTime'], time):
                merged_barberia_profile['closingTime'] = merged_barberia_profile['closingTime'].strftime('%H:%M')
            
            instance.barberia = [merged_barberia_profile]

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
    

    def validate(self, data):
        
        # Campos que están explícitamente definidos en este serializador y son para entrada
        expected_input_fields = {'username', 'email', 'password', 'biometric', 'barberia'}
        
        initial_keys = set(self.initial_data.keys())
        
        # Encontrar campos que fueron enviados pero no son esperados por este serializer
        extra_fields = initial_keys - expected_input_fields
        
        if extra_fields:
            raise serializers.ValidationError(
                f"Campos no permitidos para barberias: {', '.join(sorted(list(extra_fields)))}. "
                f"Campos válidos para barberias: {', '.join(sorted(list(expected_input_fields)))}"
            )
        return data

##############Serializador para comentario

class CommentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        # Solo incluye los campos que PUEDEN ser actualizados
        fields = ['rating', 'description']

class CommentSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField(read_only=True) 
    cliente = serializers.SerializerMethodField(read_only=True)  # Para mostrar info del cliente que comentó
    date = serializers.DateTimeField(format='%d/%m/%y', read_only=True)  # Formato de fecha de salida
    barberia_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(barberia__isnull=False), 
        write_only=True,
        required=False, # Lo hacemos no requerido para PATCH/PUT, aunque el método update lo maneja
                       # Esto puede ayudar a Swagger a inferir que no es para actualización.
                       # Sin embargo, el método 'update' es la última palabra.
    )

    # Campo para la SALIDA de datos (información de la barbería)
    barberia = serializers.SerializerMethodField(read_only=True) 


    class Meta:
        model = Comment
        # Para creación, normalmente los obtienes del contexto/URL.
        fields = ['id', 'cliente', 'barberia_id', 'barberia', 'rating', 'description', 'date']
        read_only_fields = ['id', 'barberia', 'cliente', 'date']

    def get_id(self, obj):
        # Retorna el _id de MongoDB como string
        return str(obj.id)

    def get_cliente(self, obj):
        # Retorna la información del usuario que hizo el comentario
        user_data = {
            'id': str(obj.cliente.id), # ID del usuario que comentó
            'username': obj.cliente.username, # Nombre del usuario que comentó
            # 'img_profile': obj.cliente.img_profile # Si tu User model tiene esto
        }
        
        request = self.context.get('request', None)
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            if not request.user.is_staff:
                user_data.pop('id', None) # Oculta el ID del usuario si NO es staff
        else:
            user_data.pop('id', None) # Oculta el ID si no hay usuario autenticado
        
        return user_data
    
    def get_barberia(self, obj):
        if obj.barberia and obj.barberia.barberia:
            if obj.barberia.barberia and len(obj.barberia.barberia) > 0:
                return {'nombre': obj.barberia.barberia[0].get('name_barber')}
        return None 

    def create(self, validated_data):
        barberia_instance = validated_data.pop('barberia_id')
        cliente = self.context['request'].user  # El usuario autenticado es el cliente.

        # Comprueba si el usuario autenticado está intentando comentar sobre su propia barbería
        if cliente == barberia_instance:
            raise serializers.ValidationError({"detail": "No puedes comentar tu propia barbería."})

        if Comment.objects.filter(barberia=barberia_instance, cliente=cliente).exists():
            raise serializers.ValidationError({"detail": "Ya has dejado un comentario para esta barbería."})

        
        comment = Comment.objects.create(
            barberia=barberia_instance,
            cliente=cliente,
            **validated_data
        )
        self.update_barber_rating(barberia_instance) 

        return comment

    def update(self, instance, validated_data):
        if 'barberia_id' in validated_data:
            raise serializers.ValidationError({"barberia": "No se puede cambiar la barbería de un comentario existente."})
        if 'cliente' in validated_data:
            raise serializers.ValidationError({"cliente": "No se puede cambiar el cliente de un comentario existente."})

        old_rating = instance.rating
        
        instance.rating = validated_data.get('rating', instance.rating)
        instance.description = validated_data.get('description', instance.description)
        instance.save()

        if old_rating != instance.rating:
            self.update_barber_rating(instance.barberia)

        return instance
    
    # Nuevo método para actualizar el rating de la barbería
    def update_barber_rating(self, barberia_instance):
        average_rating = Comment.objects.filter(barberia=barberia_instance).aggregate(Avg('rating'))['rating__avg']
        
        if average_rating is None:
            average_rating = 0.0
        else:
            average_rating = round(average_rating, 2)
        

        if barberia_instance.barberia and len(barberia_instance.barberia) > 0:
            
            # Opción 1: Acceso directo y guardado (si el campo 'barberia' es un tipo de lista manejado)
            # Esto puede variar si barberia_instance.barberia[0] es un objeto complejo o un dict simple.
            # Asumiendo que es un diccionario que puedes modificar:
            barberia_data = barberia_instance.barberia[0] 
            barberia_data['rating'] = average_rating

    def validate(self, data):
        
        # Campos que están explícitamente definidos en este serializador y son para entrada
        expected_input_fields = {'barberia_id', 'rating', 'description'}
        
        initial_keys = set(self.initial_data.keys())
        
        # Encontrar campos que fueron enviados pero no son esperados por este serializer
        extra_fields = initial_keys - expected_input_fields
        
        if extra_fields:
            raise serializers.ValidationError(
                f"Campos no permitidos para comentarios: {', '.join(sorted(list(extra_fields)))}. "
                f"Campos válidos para comentarios: {', '.join(sorted(list(expected_input_fields)))}"
            )
        return data
  
#########################################3333Turno

class TurnoUpdateSerializer(serializers.ModelSerializer):
    dia = serializers.CharField(write_only=True, required=False) # El día se puede actualizar

    class Meta:
        model = Turnos
        fields = ['turno', 'dia', 'estado'] # Solo estos campos son editables

    def update(self, instance, validated_data):
        # 1. Obtener la barbería asociada al turno que se está actualizando
        barberia_instance = instance.barberia
        
        # 2. Obtener el turno solicitado en la actualización
        turno_solicitado = validated_data.get('turno', instance.turno)

        # 3. Validar si el turno solicitado excede el máximo permitido
        max_turnos = barberia_instance.barberia[0]['horario'][0]['turnos_max']
        if turno_solicitado > max_turnos:
            raise ValidationError({"turno": f"El turno solicitado excede el máximo permitido ({max_turnos})."})

        # 4. Validar si el día se ha modificado (si el campo 'dia' está en los datos)
        if 'dia' in validated_data:
            dia_seleccionado = validated_data.pop('dia')

            # Calcular la nueva fecha del turno
            try:
                fecha_turno_calculada = Turnos.calcular_fecha_turno(dia_seleccionado.lower())
            except KeyError:
                raise ValidationError({"dia": "El día seleccionado no es válido."})

            # Validar si ya se ha tomado ese turno en la nueva fecha
            if Turnos.objects.filter(
                barberia=barberia_instance, 
                fecha_turno=fecha_turno_calculada, 
                turno=turno_solicitado
            ).exclude(id=instance.id).exists(): # 💡 Importante: Excluir el turno actual para evitar falsos positivos
                raise ValidationError({"turno": "Este turno ya está reservado para la fecha seleccionada."})

            # Validar la hora de cierre si el turno es para hoy (con la nueva fecha)
            if fecha_turno_calculada == datetime.now().date():
                hora_cierre_str = barberia_instance.barberia[0]['closingTime']
                hora_cierre = datetime.strptime(hora_cierre_str, '%H:%M').time()
                if datetime.now().time() > hora_cierre:
                    raise ValidationError({"dia": "El horario de cierre para hoy ha pasado. El turno se reservará para la próxima semana."})

            # Actualizar la fecha del turno en la instancia
            instance.fecha_turno = fecha_turno_calculada
        
        # 5. Actualizar los campos restantes
        # `turno` y `dia` se actualizan automáticamente si están en `validated_data`
        # pero es buena práctica hacerlo de forma explícita si hay lógica compleja.
        instance.turno = turno_solicitado
        
        instance.save()
        return instance
    
    def validate(self, data):
        
        # Campos que están explícitamente definidos en este serializador y son para entrada
        expected_input_fields = {'rating', 'description'}
        
        initial_keys = set(self.initial_data.keys())
        
        # Encontrar campos que fueron enviados pero no son esperados por este serializer
        extra_fields = initial_keys - expected_input_fields
        
        if extra_fields:
            raise serializers.ValidationError(
                f"Campos no permitidos para comentarios: {', '.join(sorted(list(extra_fields)))}. "
                f"Campos válidos para comentarios: {', '.join(sorted(list(expected_input_fields)))}"
            )
        return data

class TurnoSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField(read_only=True) 
    cliente = serializers.SerializerMethodField(read_only=True)  # Para mostrar info del cliente que comentó
    # campo para el día de la semana. Será solo de escritura.
    dia = serializers.CharField(write_only=True, required=True) 
    fecha_turno = serializers.DateField(format='%d/%m/%y', read_only=True)  # Formato de fecha de salida
    barberia_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(barberia__isnull=False), 
        write_only=True,
        required=False, # Lo hacemos no requerido para PATCH/PUT, aunque el método update lo maneja
                       # Esto puede ayudar a Swagger a inferir que no es para actualización.
                       # Sin embargo, el método 'update' es la última palabra.
    )

    # Campo para la SALIDA de datos (información de la barbería)
    barberia = serializers.SerializerMethodField(read_only=True) 


    class Meta:
        model = Turnos
        # Incluye el nuevo campo 'dia' para la entrada de datos
        fields = ['id', 'cliente', 'barberia_id', 'barberia', 'turno', 'fecha_turno', 'dia', 'estado'] 
        read_only_fields = ['id', 'barberia', 'cliente', 'fecha_turno', 'estado'] # 'fecha_turno' sigue siendo de solo lectura en la salida. 'estado' también.
        extra_kwargs = {
            'estado': {'read_only': True}
        }

    def get_id(self, obj):
        # Retorna el _id de MongoDB como string
        return str(obj.id)

    def get_cliente(self, obj):
        # Retorna la información del usuario que hizo el comentario
        user_data = {
            'id': str(obj.cliente.id), # ID del usuario que comentó
            'username': obj.cliente.username, # Nombre del usuario que comentó
            # 'img_profile': obj.cliente.img_profile # Si tu User model tiene esto
        }
        
        request = self.context.get('request', None)
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            if not request.user.is_staff:
                user_data.pop('id', None) # Oculta el ID del usuario si NO es staff
        else:
            user_data.pop('id', None) # Oculta el ID si no hay usuario autenticado
        
        return user_data
    
    def get_barberia(self, obj):
        if obj.barberia and obj.barberia.barberia:
            if obj.barberia.barberia and len(obj.barberia.barberia) > 0:
                return {'nombre': obj.barberia.barberia[0].get('name_barber')}
        return None 
    

    def create(self, validated_data):
        barberia_instance = validated_data.pop('barberia_id')
        cliente = self.context['request'].user
        dia_seleccionado = validated_data.pop('dia')
        turno_solicitado = validated_data.get('turno')

        # 1. Validar si la barbería trabaja el día seleccionado
        dias_laborables = [d.lower() for d in barberia_instance.barberia[0]['horario'][0]['days']]
        if dia_seleccionado.lower() not in dias_laborables:
            raise serializers.ValidationError({"dia": "La barbería no trabaja el día seleccionado."})

        # 2. Calcular la fecha_turno
        try:
            fecha_turno_calculada = Turnos.calcular_fecha_turno(dia_seleccionado.lower())
        except KeyError:
            raise serializers.ValidationError({"dia": "El día seleccionado no es válido."})
        
        # 3. Validar si el turno solicitado excede el máximo
        max_turnos = barberia_instance.barberia[0]['horario'][0]['turnos_max']
        if turno_solicitado > max_turnos:
            raise serializers.ValidationError({"turno": f"El turno solicitado excede el máximo permitido ({max_turnos})."})

        # 4. Validar si ya se ha tomado ese turno en esa fecha
        if Turnos.objects.filter(barberia=barberia_instance, fecha_turno=fecha_turno_calculada, turno=turno_solicitado).exists():
            raise serializers.ValidationError({"turno": "Este turno ya está reservado para la fecha seleccionada."})

        # 5. Validar la hora de cierre si el turno es para hoy
        if fecha_turno_calculada == datetime.now().date():
            hora_cierre_str = barberia_instance.barberia[0]['closingTime']
            hora_cierre = datetime.strptime(hora_cierre_str, '%H:%M').time()
            if datetime.now().time() > hora_cierre:
                raise serializers.ValidationError({"dia": "El horario de cierre para hoy ha pasado. El turno se reservará para la próxima semana."})


        turno = Turnos.objects.create(
            barberia=barberia_instance,
            cliente=cliente,
            fecha_turno=fecha_turno_calculada,
            estado='R', # 'R' se puede establecer aquí o en el modelo.
            **validated_data
        )

        return turno


    def update(self, instance, validated_data):
        if 'barberia_id' in validated_data:
            raise serializers.ValidationError({"barberia": "No se puede cambiar la barbería de un turno existente."})
        if 'cliente' in validated_data:
            raise serializers.ValidationError({"cliente": "No se puede cambiar el cliente de un turno existente."})
        
        return instance 

############################33LOGIN
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        User = get_user_model()  # Obtiene el modelo de usuario actual
        try:
            user = User.objects.get(email=email)  # Busca el usuario por email
        except User.DoesNotExist:
            raise serializers.ValidationError(_('Invalid email or password.'))
        if not user.check_password(password):  # Verifica la contraseña
            raise serializers.ValidationError(_('Invalid email or password.'))
        
        attrs['user'] = user
        return attrs
    
######################################TOKEN
class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()