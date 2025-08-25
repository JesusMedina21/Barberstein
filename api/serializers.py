import cloudinary
from rest_framework import serializers
from .models import *
from datetime import datetime, time
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.db.models import Avg 
User = get_user_model() # Obtén el modelo de usuario actual
from rest_framework import serializers
from django.core.validators import MinLengthValidator
from rest_framework.exceptions import ValidationError
from djoser import utils
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str, force_bytes
import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException

from decouple import config
# Diccionario para mapear nombres de días a números de semana de Python (lunes=0, domingo=6)
DAYS_OF_WEEK_MAP = {
    'lunes': 0,
    'martes': 1,
    'miercoles': 2,
    'jueves': 3,
    'viernes': 4,
    'sabado': 5,
    'domingo': 6,
}

#####################VALIDAR COORDENADAS

class CoordenadasField(serializers.JSONField):
    def to_internal_value(self, data):
        # Validar formato de coordenadas
        if isinstance(data, dict) and data.get('type') == 'Point':
            coordinates = data.get('coordinates', [])
            if len(coordinates) == 2:
                lat, lng = coordinates
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    return data
        
        raise serializers.ValidationError(
            'Formato de coordenadas inválido. Use: {"type": "Point", "coordinates": [lat, lng]}'
        )

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

class ConfirmarEmailSerializer(serializers.Serializer):
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
    
class ActivarEmailSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uid']))
            self.user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError({"uid": "ID de usuario inválido"})

        if not default_token_generator.check_token(self.user, attrs['token']):
            raise serializers.ValidationError({"token": "Token inválido o expirado"})

        if not self.user.pending_email:
            raise serializers.ValidationError({"detail": "No hay cambio de email pendiente"})

        return attrs
class ActivarNuevoEmailSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uid']))
            self.user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError({"uid": "ID de usuario inválido"})

        if not default_token_generator.check_token(self.user, attrs['token']):
            raise serializers.ValidationError({"token": "Token inválido o expirado"})

        if not self.user.pending_email:
            raise serializers.ValidationError({"detail": "No hay cambio de email pendiente"})

        return attrs
    
class ClienteSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    email = serializers.EmailField(required=True) 
    profile_imagen = serializers.ImageField(  # Cambia a ImageField
        required=False,
        allow_null=True,
    )
    ubicacion_coordenadas = CoordenadasField(  # ← Campo validado
        required=False, 
        allow_null=True,
        help_text='Coordenadas en formato: {"type": "Point", "coordinates": [lat, lng]}'
    )

    class Meta:
        model = User
        fields = ['id',  'first_name', 'last_name', 'username', 'email', 'password', 'profile_imagen', 'ubicacion_coordenadas', 'biometric']
        extra_kwargs = {
            'password': {'write_only': True},
            'biometric': {'write_only': True},
            'email': {'read_only': False}  # Permitimos escritura inicial
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

    def validate(self, data):
        # Validación de email único antes de procesar la imagen
        email = data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({
                "email": "Ya existe un usuario con este email."
            })
        
        # Validación de username único si es necesario
        username = data.get('username')
        if username and User.objects.filter(username=username).exists():
            raise serializers.ValidationError({
                "username": "Ya existe un usuario con este username."
            })
        
        # Resto de tus validaciones existentes
        if self.instance and 'email' in self.initial_data:
            if self.initial_data['email'] != self.instance.email:
                raise serializers.ValidationError({
                    "email": "El email no puede ser modificado."
                })
        
        expected_input_fields = {'username', 'profile_imagen', 'first_name', 'last_name', 'ubicacion_coordenadas', 'email', 'password', 'biometric'}
        initial_keys = set(self.initial_data.keys())
        extra_fields = initial_keys - expected_input_fields
        
        if extra_fields:
            raise serializers.ValidationError(
                f"Campos no permitidos para clientes: {', '.join(sorted(list(extra_fields)))}"
            )
        
        return data

    def create(self, validated_data):
    
        # Extraer la imagen de perfil
        profile_imagen_file = validated_data.pop('profile_imagen', None)
        profile_imagen_public_id = None
        
        # Subir imagen a Cloudinary si existe
        if profile_imagen_file:
            # Configurar Cloudinary para cuenta principal
            cloudinary.config(
                cloud_name=config('CLOUDINARY_PROFILE_CLOUD_NAME'),
                api_key=config('CLOUDINARY_PROFILE_API_KEY'),
                api_secret=config('CLOUDINARY_PROFILE_API_SECRET')
            )
            
            # Subir imagen a la carpeta profile_images
            upload_result = cloudinary.uploader.upload(
                profile_imagen_file,
                folder="profile_images/",  # Aquí especificas la carpeta
                resource_type="image"
            )
            
            profile_imagen_public_id = upload_result['public_id']
            print(f"Imagen de perfil subida a: {profile_imagen_public_id}")
        
        # Crear usuario con el public_id de la imagen
        user = User(**validated_data)
        user.set_password(validated_data['password'])
        user.is_active = False
        user.profile_imagen = profile_imagen_public_id  # Guardar el public_id
        
        try:
            user.save()
            return user
        except Exception as e:
            # Si hay error al guardar, eliminar la imagen subida
            if profile_imagen_public_id:
                try:
                    cloudinary.uploader.destroy(profile_imagen_public_id)
                    print(f"Imagen revertida debido a error: {profile_imagen_public_id}")
                except Exception as delete_error:
                    print(f"Error al eliminar imagen: {delete_error}")
            raise e
    def update(self, instance, validated_data):
        
        # Extraer la nueva imagen de perfil si existe
        profile_imagen_file = validated_data.pop('profile_imagen', None)
        old_profile_imagen = instance.profile_imagen
        
        # Procesar nueva imagen si se proporciona
        if profile_imagen_file:
            # Configurar Cloudinary
            cloudinary.config(
                cloud_name=config('CLOUDINARY_PROFILE_CLOUD_NAME'),
                api_key=config('CLOUDINARY_PROFILE_API_KEY'),
                api_secret=config('CLOUDINARY_PROFILE_API_SECRET')
            )
            
            # Subir nueva imagen
            upload_result = cloudinary.uploader.upload(
                profile_imagen_file,
                folder="profile_images/",
                resource_type="image"
            )
            
            # Guardar nuevo public_id
            validated_data['profile_imagen'] = upload_result['public_id']
            
            # Eliminar imagen anterior si existe
            if old_profile_imagen:
                try:
                    cloudinary.uploader.destroy(old_profile_imagen)
                    print(f"Imagen anterior eliminada: {old_profile_imagen}")
                except Exception as delete_error:
                    print(f"Error al eliminar imagen anterior: {delete_error}")
        
        # Resto del código de update...
        old_username = instance.username
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
    
        instance.save()
        return instance

#########################################################33#Serializadores para la barberia 


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
        """Convierte string a objeto time, pero luego lo mantiene como string para MongoDB"""
        try:
            if isinstance(data, time):
                return data.strftime('%H:%M')  # Convertir time a string inmediatamente
            
            if isinstance(data, str):
                # Elimina espacios y la 'Z' final si existe
                clean_data = data.strip().rstrip('Z')
                
                # Intenta con diferentes formatos
                for time_format in ['%H:%M', '%H:%M:%S', '%H:%M:%S.%f']:
                    try:
                        time_obj = datetime.strptime(clean_data, time_format).time()
                        return time_obj.strftime('%H:%M')  # Convertir a string
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
    #services = ServicioBarberiaSerializer(many=True, required=True)
    horario = HorarioSerializer(many=True, required=True)
    openingTime = TimeFieldToString(required=True)
    closingTime = TimeFieldToString(required=True)
    rating = serializers.SerializerMethodField(read_only=True)

    def validate(self, data):
        # Obtener los valores existentes si estamos en una actualización
        existing_opening = None
        existing_closing = None
        
        if self.instance:
            existing_opening = self.instance.get('openingTime')
            existing_closing = self.instance.get('closingTime')
        
        # Obtener nuevos valores o usar los existentes
        opening_time = data.get('openingTime', existing_opening)
        closing_time = data.get('closingTime', existing_closing)
        
        # Solo validar si ambos tiempos están disponibles
        if opening_time is not None and closing_time is not None:
            if opening_time == closing_time:
                raise serializers.ValidationError({
                    'openingTime': 'El horario de apertura no puede ser igual al horario de cierre.'
                })
        
        return data

    def validate_horario(self, value):
        """
        Valida que el campo 'horario' tenga la estructura correcta
        """
        if not value:
            raise serializers.ValidationError("El campo 'horario' no puede estar vacío.")
        
        # AGREGAR ESTA VALIDACIÓN para asegurar que solo haya un objeto en la lista
        if len(value) > 1:
            raise serializers.ValidationError("El campo 'horario' no puede tener más de un objeto. Un solo objeto debe contener todos los días.")

        
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
    
    def validate_phone(self, value):
        """
        Valida y formatea el número de teléfono internacional
        """
        value = value.strip()
        
        try:
            parsed_number = phonenumbers.parse(value, None)
            
            if not phonenumbers.is_valid_number(parsed_number):
                raise serializers.ValidationError("Número de teléfono no válido.")
            
            # Formatear en formato internacional legible
            formatted_number = phonenumbers.format_number(
                parsed_number, 
                phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )
            
            return formatted_number
            
        except NumberParseException:
            raise serializers.ValidationError(
                "Formato de teléfono inválido. Use formato internacional: +58 4121234567"
            )
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        
        # ***** MODIFICACIÓN CLAVE AQUÍ PARA OCULTAR 'rating' si es None *****
        if rep.get('rating') is None:
            rep.pop('rating', None)
        # *******************************************************************
        
        return rep
    
class ConvertToBarberiaSerializer(serializers.Serializer):
    name_barber = serializers.CharField(required=True, min_length=4)
    phone = serializers.CharField(required=True)
    address = serializers.CharField(required=True)
    horario = HorarioSerializer(many=True, required=True)
    openingTime = TimeFieldToString(required=True)
    closingTime = TimeFieldToString(required=True)
    
    def create(self, validated_data):
        user = self.context['user']
        
        # Crear la estructura que espera el modelo
        barberia_data = [validated_data]
        
        # Actualizar el usuario
        user.barberia = barberia_data
        user.save()
        
        return user
    
class BarberiaSerializer(serializers.ModelSerializer):
    barberia = BarberiaProfileSerializer(many=True, required=True)
    id = serializers.SerializerMethodField()
    email = serializers.EmailField(required=True) 
    ubicacion_coordenadas = CoordenadasField(  # ← Campo validado
        required=False, 
        allow_null=True,
        help_text='Coordenadas en formato: {"type": "Point", "coordinates": [lat, lng]}'
    )
    distancia_km = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'profile_imagen', 'distancia_km', 'ubicacion_coordenadas', 'biometric',  'barberia']
        extra_kwargs = {
            'password': {'write_only': True},
            'biometric': {'write_only': True},
            'email': {'read_only': False}  # Permitimos escritura inicial
        }

    def get_distancia_km(self, obj):
        """Calcula y devuelve la distancia desde el usuario autenticado"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            user = request.user
            if (hasattr(user, 'ubicacion_coordenadas') and user.ubicacion_coordenadas and
                hasattr(obj, 'ubicacion_coordenadas') and obj.ubicacion_coordenadas):
                
                try:
                    user_coords = user.ubicacion_coordenadas.get('coordinates', [])
                    barberia_coords = obj.ubicacion_coordenadas.get('coordinates', [])
                    
                    if len(user_coords) == 2 and len(barberia_coords) == 2:
                        user_lng, user_lat = user_coords
                        barberia_lng, barberia_lat = barberia_coords
                        
                        # Calcular distancia
                        from math import radians, sin, cos, sqrt, atan2
                        R = 6371
                        lat1_rad, lng1_rad = radians(user_lat), radians(user_lng)
                        lat2_rad, lng2_rad = radians(barberia_lat), radians(barberia_lng)
                        dlng, dlat = lng2_rad - lng1_rad, lat2_rad - lat1_rad
                        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng/2)**2
                        distancia = R * (2 * atan2(sqrt(a), sqrt(1-a)))
                        
                        return round(distancia, 2)
                        
                except (ValueError, TypeError):
                    pass
        
        return None

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
            # Obtener la instancia actual si estamos en una actualización
            instance = getattr(self, 'instance', None)
            
            # Buscar barberías con el mismo nombre
            same_name_barbers = User.objects.filter(barberia__0__name_barber=name_barber)
            
            # Si estamos actualizando (instance existe) y encontramos barberías con el mismo nombre
            if same_name_barbers.exists():
                # Si no es la misma barbería (o si es creación), lanzar error
                if not instance or str(same_name_barbers.first().id) != str(instance.id):
                    raise serializers.ValidationError({
                        "name_barber": "Ya existe una barbería con este nombre."
                    })
        
        return value
    
    def create(self, validated_data):
        # Verificar si el usuario ya existe (por email)
        email = validated_data.get('email')
        existing_user = None
    
        # Guardar referencia a la imagen para limpieza en caso de error
        profile_imagen = validated_data.get('profile_imagen')
        
        if profile_imagen:
            print(f"Profile imagen name: {getattr(profile_imagen, 'name', 'No name')}")
    
        if email:
            try:
                existing_user = User.objects.get(email=email)
            except User.DoesNotExist:
                pass
        
        # Si el usuario existe y se autenticó con Google, actualizarlo
        if existing_user:
            # Verificar autenticación social (forma correcta)
            from social_django.models import UserSocialAuth
            social_auth_exists = UserSocialAuth.objects.filter(user=existing_user, provider='google-oauth2').exists()
            
            if social_auth_exists:
                # Actualizar usuario existente
                instance = existing_user
                
                # Procesar imagen de perfil si se proporciona
                profile_imagen = validated_data.get('profile_imagen')
                if profile_imagen and hasattr(profile_imagen, 'file'):  # Es un archivo, no un public_id
                    # Configurar Cloudinary
                    cloudinary.config(
                        cloud_name=config('CLOUDINARY_PROFILE_CLOUD_NAME'),
                        api_key=config('CLOUDINARY_PROFILE_API_KEY'),
                        api_secret=config('CLOUDINARY_PROFILE_API_SECRET')
                    )
                    
                    # Subir imagen
                    upload_result = cloudinary.uploader.upload(
                        profile_imagen,
                        folder="profile_images/"
                    )
                    validated_data['profile_imagen'] = upload_result['public_id']
                
                # Procesar datos de barbería
                barberia_data = validated_data.pop('barberia', [])
                
                # NORMALIZAR DATOS DE BARBERÍA (igual que para nuevos usuarios)
                for barberia_item in barberia_data:
                    # 🔑 Normalizar horario
                    if "horario" in barberia_item:
                        horario_data = barberia_item["horario"]
            
                        # si viene como dict, convertir a lista
                        if isinstance(horario_data, dict):
                            horario_data = [
                                v for k, v in sorted(horario_data.items(), key=lambda x: int(x[0]))
                            ]
            
                        # Normalizar cada item del horario
                        normalized_horario = []
                        for item in horario_data:
                            if isinstance(item, dict):
                                if "days" in item and isinstance(item["days"], dict):
                                    # convertir days a lista ordenada
                                    item["days"] = [
                                        v for k, v in sorted(item["days"].items(), key=lambda x: int(x[0]))
                                    ]
                                normalized_horario.append(item)
            
                        barberia_item["horario"] = normalized_horario
            
                    # 🔑 Convertir horas (ya son `time` por to_internal_value → reconvertir a str)
                    if "openingTime" in barberia_item and isinstance(barberia_item["openingTime"], time):
                        barberia_item["openingTime"] = barberia_item["openingTime"].strftime("%H:%M")
                    if "closingTime" in barberia_item and isinstance(barberia_item["closingTime"], time):
                        barberia_item["closingTime"] = barberia_item["closingTime"].strftime("%H:%M")
                
                # Actualizar campos del usuario (excluyendo password)
                for attr, value in validated_data.items():
                    if attr != 'password':  # No actualizar password para usuarios existentes
                        setattr(instance, attr, value)
                
                # Asignar datos de barbería
                instance.barberia = barberia_data
                instance.is_active = True  # Activar la cuenta si estaba inactiva
                instance.save()
                
                return instance
        
        # CÓDIGO PARA NUEVOS USUARIOS (sin cambios)
        # Procesar imagen de perfil MANUALMENTE con la cuenta correcta
        if profile_imagen and hasattr(profile_imagen, 'file'):
            # Configurar Cloudinary para cuenta principal
            cloudinary.config(
                cloud_name=config('CLOUDINARY_PROFILE_CLOUD_NAME'),
                api_key=config('CLOUDINARY_PROFILE_API_KEY'),
                api_secret=config('CLOUDINARY_PROFILE_API_SECRET')
            )
            
            # Subir imagen
            upload_result = cloudinary.uploader.upload(
                profile_imagen,
                folder="profile_images/"
            )
            
            # Reemplazar el archivo con el public_id
            validated_data['profile_imagen'] = upload_result['public_id']
            print(f"Imagen de perfil subida a cuenta principal: {upload_result['public_id']}")
        
        
        barberia_data = validated_data.pop('barberia', [])
        
        for barberia_item in barberia_data:
            # 🔑 Normalizar horario
            if "horario" in barberia_item:
                horario_data = barberia_item["horario"]
        
                # si viene como dict, convertir a lista
                if isinstance(horario_data, dict):
                    horario_data = [
                        v for k, v in sorted(horario_data.items(), key=lambda x: int(x[0]))
                    ]
        
                # Normalizar cada item del horario
                normalized_horario = []
                for item in horario_data:
                    if isinstance(item, dict):
                        if "days" in item and isinstance(item["days"], dict):
                            # convertir days a lista ordenada
                            item["days"] = [
                                v for k, v in sorted(item["days"].items(), key=lambda x: int(x[0]))
                            ]
                        normalized_horario.append(item)
        
                barberia_item["horario"] = normalized_horario
        
            # 🔑 Convertir horas (ya son `time` por to_internal_value → reconvertir a str)
            if "openingTime" in barberia_item and isinstance(barberia_item["openingTime"], time):
                barberia_item["openingTime"] = barberia_item["openingTime"].strftime("%H:%M")
            if "closingTime" in barberia_item and isinstance(barberia_item["closingTime"], time):
                barberia_item["closingTime"] = barberia_item["closingTime"].strftime("%H:%M")
        
        
        # Crear usuario
        user = User(**validated_data)
        
        # Solo establecer password si se proporciona (para usuarios sociales puede no venir)
        if 'password' in validated_data and validated_data['password']:
            user.set_password(validated_data["password"])
        
        user.is_active = False  # Al crear, la cuenta no está activa
        user.barberia = barberia_data  # Lista final normalizada
        
        try:
            user.save()
            return user
        except Exception as e:
            # **** LIMPIEZA COMPLETA: Eliminar todas las imágenes si hay error ****
            if 'profile_imagen' in validated_data and validated_data['profile_imagen']:
                try:
                    cloudinary.config(
                        cloud_name=config('CLOUDINARY_PROFILE_CLOUD_NAME'),
                        api_key=config('CLOUDINARY_PROFILE_API_KEY'),
                        api_secret=config('CLOUDINARY_PROFILE_API_SECRET')
                    )
                    cloudinary.uploader.destroy(validated_data['profile_imagen'])
                    print(f"Imagen de perfil eliminada: {validated_data['profile_imagen']}")
                except Exception as delete_error:
                    print(f"Error al eliminar imagen de perfil: {delete_error}")
        
            # Verificar si el error es por name_barber duplicado
            error_msg = str(e).lower()
            if "name_barber" in error_msg or "duplicate" in error_msg:
                raise serializers.ValidationError({
                    "name_barber": "Ya existe una barbería con este nombre."
                })
        
            raise serializers.ValidationError({
                "detail": f"Error al crear la barbería: {str(e)}"
            })

    def update(self, instance, validated_data):
        try:
            password = validated_data.pop('password', None)
            if password:
                instance.set_password(password)
                # Procesar imagen de perfil MANUALMENTE si hay cambios
            profile_imagen = validated_data.get('profile_imagen')
            old_profile_imagen = instance.profile_imagen
            
            if profile_imagen and profile_imagen != old_profile_imagen:
                # Configurar Cloudinary para cuenta principal
                cloudinary.config(
                    cloud_name=config('CLOUDINARY_PROFILE_CLOUD_NAME'),
                    api_key=config('CLOUDINARY_PROFILE_API_KEY'),
                    api_secret=config('CLOUDINARY_PROFILE_API_SECRET')
                )
                
                # Subir nueva imagen
                upload_result = cloudinary.uploader.upload(
                    profile_imagen,
                    folder="profile_images/"
                )
                
                # Eliminar imagen anterior si existe
                if old_profile_imagen:
                    try:
                        cloudinary.uploader.destroy(old_profile_imagen)
                        print(f"Imagen anterior eliminada: {old_profile_imagen}")
                    except Exception as delete_error:
                        print(f"Error al eliminar imagen anterior: {delete_error}")
                
                # Reemplazar con el public_id
                validated_data['profile_imagen'] = upload_result['public_id']
                print(f"Nueva imagen de perfil subida: {upload_result['public_id']}")
        
            
            barberia_data_from_request = validated_data.pop('barberia', None)
            
            if barberia_data_from_request is not None:
                # Obtener el perfil existente o crear uno nuevo
                existing_barberia = instance.barberia[0] if instance.barberia else {}
                new_barberia_data = barberia_data_from_request[0] if barberia_data_from_request else {}
                
                # *** MANEJO CORRECTO DE ACTUALIZACIÓN PARCIAL ***
                # Fusionar solo los campos que vienen en la solicitud
                merged_data = existing_barberia.copy()
                
                # Procesar campos especiales
                if 'horario' in new_barberia_data:
                    merged_data['horario'] = new_barberia_data['horario']
                
                # Convertir tiempos a string si es necesario
                for time_field in ['openingTime', 'closingTime']:
                    if time_field in merged_data and isinstance(merged_data[time_field], time):
                        merged_data[time_field] = merged_data[time_field].strftime('%H:%M')
                
                # Mantener campos protegidos
                protected_fields = ['rating', 'comments']
                for field in protected_fields:
                    if field in existing_barberia:
                        merged_data[field] = existing_barberia[field]
    

                # *** CONVERTIR OBJETOS time A STRING ANTES DE GUARDAR ***
                self._convert_time_to_string(merged_data)
                
                # Asignar los datos fusionados
                instance.barberia = [merged_data]
        
            # Actualizar otros campos
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
    
            instance.save()
            return instance
        
        except Exception as e:
            # Mostrar el error real en lugar de uno genérico
            error_message = str(e)
            print(f"Error completo: {error_message}")  # Para debugging
            raise serializers.ValidationError({
                "detail": f"Error al actualizar la barbería: {error_message}"
            })
    
    def _convert_time_to_string(self, data):
        """Convierte objetos time a string para MongoDB"""
        time_fields = ['openingTime', 'closingTime']
        
        for field in time_fields:
            if field in data and isinstance(data[field], time):
                data[field] = data[field].strftime('%H:%M')
        
        # También convertir times en horarios si existen
        if 'horario' in data and isinstance(data['horario'], list):
            for horario_item in data['horario']:
                if isinstance(horario_item, dict):
                    for time_field in time_fields:
                        if time_field in horario_item and isinstance(horario_item[time_field], time):
                            horario_item[time_field] = horario_item[time_field].strftime('%H:%M')

    

    def validate(self, data):
        # **** NUEVA VALIDACIÓN: Verificar email único ANTES de procesar imágenes ****
        email = data.get('email')
        if email:
            # Si es creación (no hay instancia) o el email está cambiando
            if not self.instance or email != self.instance.email:
                if User.objects.filter(email=email).exists():
                    raise serializers.ValidationError({
                        "email": "Ya existe un usuario con este email."
                    })
        
        # **** NUEVA VALIDACIÓN: Verificar username único ****
        username = data.get('username')
        if username:
            # Si es creación o el username está cambiando
            if not self.instance or username != self.instance.username:
                if User.objects.filter(username=username).exists():
                    raise serializers.ValidationError({
                        "username": "Ya existe un usuario con este username."
                    })
        # Validar name_barber único (solo para creación)
        if not self.instance and 'barberia' in data:
            barberia_data = data['barberia']
            if barberia_data and len(barberia_data) > 0:
                name_barber = barberia_data[0].get('name_barber')
                if name_barber and User.objects.filter(barberia__0__name_barber=name_barber).exists():
                    raise serializers.ValidationError({
                        "name_barber": "Ya existe una barbería con este nombre."
                    })
                
        # Validación para evitar modificación del email en updates
        if self.instance and 'email' in self.initial_data:
            if self.initial_data['email'] != self.instance.email:
                raise serializers.ValidationError({
                    "email": "El email no puede ser modificado. Use el endpoint de auth/email/reset/ para actualizar el email."
                })
        
        
        
        # Campos que están explícitamente definidos en este serializador y son para entrada
        expected_input_fields = {'username', 'profile_imagen', 'ubicacion_coordenadas', 'email', 'password', 'biometric', 'barberia'}
        
        # Campos de barbería que pueden venir en el nivel principal pero serán movidos
        barberia_fields = {'name_barber', 'phone', 'address', 'horario', 'openingTime', 'closingTime'}
        
        # Solo verificar campos de primer nivel, ignorar campos anidados como barberia[0][services][0][imagen][0]
        top_level_fields = set(self.initial_data.keys())
        
        # Filtrar solo campos de primer nivel (sin corchetes)
        simple_fields = {field for field in top_level_fields if '[' not in field and ']' not in field}
        
        # Excluir campos de barbería que serán procesados por to_internal_value
        simple_fields = simple_fields - barberia_fields
        
        # Encontrar campos que fueron enviados pero no son esperados por este serializer
        extra_fields = simple_fields - expected_input_fields
        
        if extra_fields:
            raise serializers.ValidationError(
                f"Campos no permitidos para barberias: {', '.join(sorted(list(extra_fields)))}. "
                f"Campos válidos para barberias: {', '.join(sorted(list(expected_input_fields)))}"
            )
        
        return data
    


#####################################################3Ubicacion coordenadas

class LocationField(serializers.JSONField):
    def to_internal_value(self, data):
        if isinstance(data, dict) and 'coordinates' in data and 'type' in data:
            if data['type'] == 'Point' and len(data['coordinates']) == 2:
                # Validar que las coordenadas sean números válidos
                lat, lng = data['coordinates']
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    return data
        raise serializers.ValidationError("Formato de ubicación inválido. Use: {'type': 'Point', 'coordinates': [lat, lng]}")
    
class BarberiaCercanaSerializer(BarberiaSerializer):
    distancia = serializers.SerializerMethodField()
    
    class Meta(BarberiaSerializer.Meta):
        fields = BarberiaSerializer.Meta.fields + ['distancia', 'city', 'address']
    
    def get_distancia(self, obj):
        # Obtener la distancia del contexto
        distancias = self.context.get('distancias', {})
        return distancias.get(obj.id, None)

##############Serializador para comentario

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
        

        # Obtener la lista actual de barberia
        barberia_list = barberia_instance.barberia if barberia_instance.barberia else []
        
        if barberia_list:  # Si hay al menos un elemento
            # Crear una copia del primer diccionario para modificarlo
            updated_barberia = dict(barberia_list[0])
            updated_barberia['rating'] = average_rating
            
            # Reemplazar el primer elemento con la versión actualizada
            barberia_list[0] = updated_barberia
        else:
            # Si no hay datos de barbería, crear una nueva entrada
            barberia_list.append({'rating': average_rating})
        
        # Actualizar el campo barberia en la instancia
        barberia_instance.barberia = barberia_list
        barberia_instance.save()

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
        expected_input_fields = {'turno', 'estado', 'dia'}
        
        initial_keys = set(self.initial_data.keys())
        
        # Encontrar campos que fueron enviados pero no son esperados por este serializer
        extra_fields = initial_keys - expected_input_fields
        
        if extra_fields:
            raise serializers.ValidationError(
                f"Campos no permitidos para comentarios: {', '.join(sorted(list(extra_fields)))}. "
                f"Campos válidos para comentarios: {', '.join(sorted(list(expected_input_fields)))}"
            )
        return data

def calcular_hora_turno(opening_time_str, closing_time_str, max_turnos, turno_num):
    """
    Devuelve el rango horario (inicio, fin) del turno solicitado.
    """
    opening_time = datetime.strptime(opening_time_str, "%H:%M")
    closing_time = datetime.strptime(closing_time_str, "%H:%M")

    # Manejar cruce de medianoche
    if closing_time <= opening_time:
        closing_time += timedelta(days=1)

    # Duración de cada turno
    total_minutes = (closing_time - opening_time).total_seconds() / 60
    duracion_turno = total_minutes / max_turnos

    # Calcular hora de inicio del turno
    turno_inicio = opening_time + timedelta(minutes=(turno_num - 1) * duracion_turno)
    turno_fin = turno_inicio + timedelta(minutes=duracion_turno)

    # Formatear para mostrar solo hora y minuto
    return turno_inicio.time().strftime("%H:%M"), turno_fin.time().strftime("%H:%M")
    
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
    hora_turno = serializers.SerializerMethodField(read_only=True)

    # Campo para la SALIDA de datos (información de la barbería)
    barberia = serializers.SerializerMethodField(read_only=True) 


    class Meta:
        model = Turnos
        # Incluye el nuevo campo 'dia' para la entrada de datos
        fields = ['id', 'cliente', 'barberia_id', 'barberia', 'turno', 'fecha_turno', 'dia', 'estado', 'hora_turno'] 
        read_only_fields = ['id', 'barberia', 'cliente', 'fecha_turno', 'estado', 'hora_turno'] # 'fecha_turno' sigue siendo de solo lectura en la salida. 'estado' también.
        extra_kwargs = {
            'estado': {'read_only': True}
        }

    def get_hora_turno(self, obj):
        try:
            barberia_data = obj.barberia.barberia[0]
            opening_time = barberia_data['openingTime']
            closing_time = barberia_data['closingTime']
            max_turnos = barberia_data['horario'][0]['turnos_max']
            turno_num = obj.turno

            inicio, fin = calcular_hora_turno(opening_time, closing_time, max_turnos, turno_num)
            return f"{inicio} - {fin}"
        except Exception as e:
            return None

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
        cliente = self.context['request'].user
        if cliente.barberia is not None:
            raise serializers.ValidationError({"detail": "Las barberías no pueden solicitar turnos."})

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
    

    def validate(self, data):
        
        # Campos que están explícitamente definidos en este serializador y son para entrada
        expected_input_fields = {'turno', 'estado', 'dia'}
        
        initial_keys = set(self.initial_data.keys())
        
        # Encontrar campos que fueron enviados pero no son esperados por este serializer
        extra_fields = initial_keys - expected_input_fields
        
        if extra_fields:
            raise serializers.ValidationError(
                f"Campos no permitidos para comentarios: {', '.join(sorted(list(extra_fields)))}. "
                f"Campos válidos para comentarios: {', '.join(sorted(list(expected_input_fields)))}"
            )
        return data

###########################################Servicio


class ServicioSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField(read_only=True) 
    barberia = serializers.SerializerMethodField(read_only=True) 
    imagenes = serializers.ListField(
        child=serializers.ImageField(),  # archivos de imagen
        write_only=True,
        required=True
    )
    precio = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        required=False, allow_null=True
    )
    MONEDAS = ["ARS","BOB","BRL","CLP","COP","CRC","CUP""DOP","USD","EUR","GTQ","GYD""HTG","HNL", "MXN", "NIO","PAB","PYG","PEN","SRD","TTD","UYU","VES"]
    moneda = serializers.ChoiceField(
        choices=MONEDAS,
        required=False, allow_null=True
    )
    imagen_urls = serializers.SerializerMethodField(read_only=True)  

    class Meta:
        model = Servicio
        fields = ['id', 'barberia', 'description', 'imagen_urls', 'imagenes', 'precio', 'moneda']

    def get_id(self, obj):
        # Retorna el _id de MongoDB como string
        return str(obj.id)
    
    def get_barberia(self, obj):
        # Retorna solo el name_barber de la barbería asociada
        if obj.barberia and obj.barberia.barberia:
            barberia_list = obj.barberia.barberia
            if len(barberia_list) > 0:
                return barberia_list[0].get('name_barber')
        return None


    def get_imagen_urls(self, obj):
        """
        Convierte cada public_id en una URL lista para frontend
        """
        return [
            cloudinary.CloudinaryImage(public_id).build_url(secure=True)
            for public_id in obj.imagen_urls
        ]

    def validate_imagenes(self, value):
        """
        Validación adicional para las imágenes
        """
        if len(value) > 4:
            raise serializers.ValidationError("No se pueden subir más de 4 imágenes")
        
        # Validar tipo MIME además de la extensión
        valid_mime_types = ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp']
        
        for image_file in value:
            # Verificar el tipo MIME real del archivo
            if hasattr(image_file, 'content_type') and image_file.content_type:
                if image_file.content_type not in valid_mime_types:
                    raise serializers.ValidationError(
                        f"Tipo de archivo no permitido: {image_file.content_type}. "
                        f"Solo se permiten imágenes (JPEG, PNG, GIF, BMP, WEBP)"
                    )
            
            # Validar tamaño máximo del archivo (opcional, 5MB máximo)
            max_size = 5 * 1024 * 1024
            if hasattr(image_file, 'size') and image_file.size > max_size:
                raise serializers.ValidationError(
                    f"La imagen {image_file.name} es demasiado grande. "
                    f"Tamaño máximo permitido: 5MB"
                )
        
        return value
    def create(self, validated_data):

        request = self.context.get('request')
        usuario = request.user
        # ✅ Validación: solo usuarios con barberia pueden crear servicios
        if not getattr(usuario, 'barberia', None):
            raise serializers.ValidationError({"detail": "Solo las barberías pueden registrar servicios."})
        imagenes = validated_data.pop('imagenes', [])
        imagen_urls = []

        try:
            for img in imagenes:
                upload_result = cloudinary.uploader.upload(
                    img,
                    folder="services_images/",
                    cloud_name=settings.SERVICIOS_CLOUDINARY['CLOUD_NAME'],
                    api_key=settings.SERVICIOS_CLOUDINARY['API_KEY'],
                    api_secret=settings.SERVICIOS_CLOUDINARY['API_SECRET']
                )
                imagen_urls.append(upload_result['public_id'])

     
            validated_data['imagen_urls'] = imagen_urls

            servicio = Servicio.objects.create(**validated_data)
            return servicio

        except Exception as e:
        # rollback si algo falla
            for url in imagen_urls:
                try:
                    public_id = url.split("/")[-1].split(".")[0]
                    cloudinary.uploader.destroy(
                        public_id,
                        cloud_name=settings.SERVICIOS_CLOUDINARY['CLOUD_NAME'],
                        api_key=settings.SERVICIOS_CLOUDINARY['API_KEY'],
                        api_secret=settings.SERVICIOS_CLOUDINARY['API_SECRET']
                    )
                except:
                    pass
            raise e
        
    def update(self, instance, validated_data):

        if 'barberia' in validated_data:
            raise serializers.ValidationError({"barberia": "No se puede cambiar la barbería de un servicio existente."})
        
        imagenes = validated_data.pop('imagenes', None)

        # Actualizar descripción
        instance.description = validated_data.get('description', instance.description)

        if imagenes:
            # 1. Borrar imágenes antiguas de Cloudinary
            for old_id in instance.imagen_urls:  # 👈 ya es public_id, úsalo directo
                try:
                    cloudinary.uploader.destroy(
                        old_id,
                        cloud_name=settings.SERVICIOS_CLOUDINARY['CLOUD_NAME'],
                        api_key=settings.SERVICIOS_CLOUDINARY['API_KEY'],
                        api_secret=settings.SERVICIOS_CLOUDINARY['API_SECRET']
                    )
                except Exception as e:
                    print(f"Error eliminando {old_id}: {e}")

            # 2. Subir nuevas imágenes
            new_ids = []
            for img in imagenes:
                upload_result = cloudinary.uploader.upload(
                    img,
                    folder="services_images/",
                    cloud_name=settings.SERVICIOS_CLOUDINARY['CLOUD_NAME'],
                    api_key=settings.SERVICIOS_CLOUDINARY['API_KEY'],
                    api_secret=settings.SERVICIOS_CLOUDINARY['API_SECRET']
                )
                new_ids.append(upload_result['public_id'])  # 👈 siempre public_id

            instance.imagen_urls = new_ids

        instance.save()
        return instance
    

    def validate(self, attrs):
        precio = attrs.get("precio")
        moneda = attrs.get("moneda")

        if precio is not None and moneda is None:
            raise serializers.ValidationError(
                {"moneda": "Debe especificar la moneda si indica un precio."}
            )
       
        # Campos que están explícitamente definidos en este serializador y son para entrada
        expected_input_fields = {'description', 'imagenes', 'precio', 'moneda'}

        # Solo verificar campos de primer nivel, ignorar campos anidados como barberia[0][services][0][imagen][0]
        top_level_fields = set(self.initial_data.keys())
        
        # Filtrar solo campos de primer nivel (sin corchetes)
        simple_fields = {field for field in top_level_fields if '[' not in field and ']' not in field}
        
        # Encontrar campos que fueron enviados pero no son esperados por este serializer
        extra_fields = simple_fields - expected_input_fields
        
        if extra_fields:
            raise serializers.ValidationError(
                f"Campos no permitidos para barberias: {', '.join(sorted(list(extra_fields)))}. "
                f"Campos válidos para barberias: {', '.join(sorted(list(expected_input_fields)))}"
            )
        return attrs


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