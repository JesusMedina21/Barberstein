from django.http import Http404
from rest_framework import viewsets, status, generics
from api.serializers import *
import os
from datetime import date, timedelta

import json
# from django.contrib.auth.models import User # Modelo original
from api.models import *
# JWT
from rest_framework.permissions import IsAuthenticated, AllowAny

#DRF SPECTACULAR
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample, OpenApiParameter

from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from api.permissions import *
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from django.db.models import Q  #Esta importacion sirve para realizar consultas complejas a la base de datos
from djoser import signals
from djoser.conf import settings as djoser_settings
from djoser.views import UserViewSet

from math import radians, sin, cos, sqrt, atan2

from django.contrib.auth.tokens import default_token_generator
from rest_framework.views import APIView

from api.custom_email import *
from django.db.utils import IntegrityError  # 👈 Importa esta excepción
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.db import transaction
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from querystring_parser import parser
import re
from collections import defaultdict
VERCEL_API_KEY_SECRET = "ae24638ce08a743c58aea8a35931e76464d8d0a15fed29fc696cfe2bf9806f2f"

import datetime

# DRF SPECTACULAR - IMPORTACIONES COMPLETAS
from drf_spectacular.utils import (
    extend_schema, 
    extend_schema_view, 
    OpenApiExample, 
    OpenApiParameter
)
from drf_spectacular.types import OpenApiTypes  # ← IMPORTANTE
#################################################AUTH

@extend_schema(
    request=ConfirmarEmailSerializer,
    description='Confirma el cambio de email usando el UID y token del enlace'
)

class ConfirmarEmail(APIView):
    def post(self, request, *args, **kwargs):
        serializer = ConfirmarEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.user
        token = serializer.validated_data['token']
        new_email = serializer.validated_data["new_email"]

        if not default_token_generator.check_token(user, token):
            return Response(
                {"token": "Token inválido o expirado"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=new_email).exists():
            return Response(
                {"new_email": ["Este correo electrónico ya está en uso."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Guardamos directamente en los nuevos campos
        user.pending_email = new_email
        user.email_change_token = default_token_generator.make_token(user)
        user.save()

        email_context = {
            'user': user,
            'new_email': new_email,
            'old_email': user.email,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': user.email_change_token
        }

        activation_email = CustomEmailReset(request, email_context)
        activation_email.send(to=[new_email])

        return Response(
            {"detail": "Se ha enviado un correo de confirmación al nuevo email"},
            status=status.HTTP_200_OK
        )


@extend_schema(
    request=ActivarEmailSerializer,
    description='Confirma el nuevo email usando el UID y token del enlace'
)
class CustomUserViewSet(UserViewSet):
    def activation(self, request, *args, **kwargs):
        # Lógica de activación manual
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user
        user.is_active = True
        user.save()

        # Enviar correo personalizado
        CustomActivationConfirmEmail(context={'user': user}).send(to=user.email)

        return Response(
            {"detail": "¡Cuenta activada con éxito! Bienvenido a Barberstein."},
            status=status.HTTP_200_OK
        )
@extend_schema(
    request=ActivarNuevoEmailSerializer,
    description='Confirma el nuevo email usando el UID y token del enlace'
)
class ActivarNuevoEmailView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = ActivarNuevoEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.user

        if not user.pending_email:
            return Response(
                {"detail": "No hay cambio de email pendiente"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not default_token_generator.check_token(user, serializer.validated_data['token']):
            return Response(
                {"token": "Token inválido o expirado"},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_email = user.pending_email
        old_email = user.email
        
        try:
            with transaction.atomic():
                user.email = new_email
                user.pending_email = None
                user.email_change_token = None
                user.save()
        except IntegrityError:
            return Response(
                {"detail": "Este correo electrónico ya está en uso"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enviar notificaciones
        email_context = {
            'user': user,
            'new_email': new_email,
            'email': new_email,  # Añade esto para el template
            'old_email': old_email
        }

        confirmation_email = CustomActivationNewEmail(request, email_context)
        confirmation_email.send(to=[new_email])

        notification_email = CustomOldEmailNotification(request, email_context)
        notification_email.send(to=[old_email])

        return Response(
            {"detail": "Email cambiado exitosamente"},
            status=status.HTTP_200_OK
        )
###################################3333333#Cliente###############################################

@extend_schema_view(
    list=extend_schema(tags=['Clientes'],
        summary="Obtener datos de todos los clientes",),
    retrieve=extend_schema(tags=['Clientes'],
       summary="Obtener datos de mi cuenta",),
    create=extend_schema(
        tags=['Clientes'],
        summary="Crear cuenta de cliente",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'first_name': {'type': 'string'},
                    'last_name': {'type': 'string'},
                    'username': {'type': 'string'},
                    'email': {'type': 'string', 'format': 'email'},
                    'password': {'type': 'string', 'format': 'password'},
                    'profile_imagen': {'type': 'string', 'format': 'binary'},
                    'biometric': {'type': 'string'},
                    'ubicacion_coordenadas': {  # ✅ ESTA ES LA CORRECCIÓN
                        'type': 'object',
                        'properties': {
                            'type': {'type': 'string', 'example': 'Point'},
                            'coordinates': {
                                'type': 'array',
                                'items': {'type': 'number'},
                                'example': [-16.4897, -68.1193]
                            }
                        },
                        'required': ['type', 'coordinates']
                    }
                },
                'required': ['first_name', 'last_name', 'username', 'email', 'password']
            }
        },
        responses={201: ClienteSerializer}
    ),
    methods=['POST'], tags=['Clientes'], 
    update=extend_schema(exclude=True),  # Oculta el método PUT (update)
    partial_update=extend_schema(
        tags=['Clientes'],
        summary="Editar mi cuenta",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'first_name': {'type': 'string'},
                    'last_name': {'type': 'string'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'biometric': {'type': 'string'},
                    'profile_imagen': {'type': 'string'},
                    'ubicacion_coordenadas': { 
                        'type': 'object',
                        'properties': {
                            'type': {'type': 'string', 'example': 'Point'},
                            'coordinates': {
                                'type': 'array',
                                'items': {'type': 'number'},
                                'example': [-16.4897, -68.1193]
                            }
                        }
                    }
                },
                'required': []
            }
        }
    ),    
    destroy=extend_schema(tags=['Clientes'],
        summary="Eliminar mi cuenta",),
)

class ClienteViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(barberia__isnull=True)
    serializer_class = ClienteSerializer

    # 1. Indica que el campo de búsqueda es 'id' (el PK de tu modelo User)
    lookup_field = 'id' 
    # 2. Especifica la expresión regular para un ObjectId de 24 caracteres hexadecimales
    lookup_value_regex = '[0-9a-fA-F]{24}' 

    def get_queryset(self):
        user = self.request.user
    
        if self.action == 'list':

        
            return User.objects.filter((Q(barberia__isnull=True) | Q(barberia=[])) & Q(is_active=True) & Q(is_staff=False)  )
    
        return super().get_queryset()


    def get_permissions(self):
        if self.action == 'create': # Esta linea significa que el endpoint register lo pueda usar cualquiera
            return [AllowAny()]  # Permitir registro sin autenticación
        elif self.action == 'list':
            # Permitir que CUALQUIER usuario AUTENTICADO acceda a la lista
            return [IsAuthenticated()] 
        elif self.action in ['retrieve', 'partial_update', 'destroy']:  
            # Permitir acceso a retrieve, update y destroy solo si el usuario está autenticado
           
            # Y que el resto de metodos usen IsAuthenticated que significa JWT y el IsSelf que significa
            # que el mismo usuario pueda acceder a su propio recurso, ejemplo el usuario 1 solo acceda al endpoint 1 
            return [IsAuthenticated(), MiUsuarioLogin()]  # 👈 Requiere autenticación y que sea el mismo usuario 
        #El IsAuthenticated es creado automaticamente por Django, MiUsuario es creado manualmente
        return [IsAuthenticated()]
    
    @extend_schema(tags=['Cliente'])
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Usa el serializador para crear el usuario
        user = serializer.save()  # Esto llamará al método create del serializador
        
        # ***** NUEVA LÓGICA PARA ENVIAR EL CORREO DE ACTIVACIÓN *****
        signals.user_registered.send(
            sender=self.__class__, user=user, request=self.request
        )
        if djoser_settings.SEND_ACTIVATION_EMAIL:
            context = {"user": user}
            djoser_settings.EMAIL.activation(self.request, context).send([user.email])
        # ************************************************************
        
        return Response(ClienteSerializer(user).data, status=status.HTTP_201_CREATED)
   
    def update(self, request, *args, **kwargs):
        if not kwargs.get('partial', False):
            return Response(
                {"detail": "Método PUT no permitido. Use PATCH en su lugar."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs) 


###################################3333333#Barberias###############################################

###Con este codigo puedo crear barberias con body multiplataform en Postman
def dict_to_list(data):
    """
    Convierte dicts con claves '0','1','2' en listas reales.
    """
    if isinstance(data, dict):
        # convierte todas las claves a str para comparar
        keys = list(data.keys())
        if all(str(k).isdigit() for k in keys):
            return [dict_to_list(data[k]) for k in sorted(keys, key=lambda x: int(x))]
        else:
            return {k: dict_to_list(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [dict_to_list(v) for v in data]
    else:
        return data

    
def nested_dict():
    return defaultdict(nested_dict)

def querydict_to_nested(data):
    result = nested_dict()

    for key, value in data.items():
        parts = re.split(r'\[|\]', key)
        parts = [p for p in parts if p != '']  # limpia vacíos
        d = result
        for p in parts[:-1]:
            d = d[p]
        d[parts[-1]] = value

    return dict(result)

@extend_schema(tags=['Barberias'], summary="Agregar campos de barberia a cuenta registrada con Google")
class ConvertGoogleUserToBarberiaView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        request=ConvertToBarberiaSerializer,
        responses={200: BarberiaSerializer},
        description='Convertir usuario de Google en barbería'
    )
    def post(self, request):
        user = request.user
        
        # Verificar que el usuario se autenticó con Google
        social_auth = user.social_auth.filter(provider='google-oauth2').first()
        if not social_auth:
            return Response(
                {"detail": "Este usuario no se autenticó con Google"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que no sea ya una barbería
        if user.barberia:
            return Response(
                {"detail": "El usuario ya es una barbería"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Usar el serializador específico para conversión
        serializer = ConvertToBarberiaSerializer(
            data=request.data,
            context={'user': user, 'request': request}
        )
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Devolver los datos con el serializador de barbería completo
            barberia_serializer = BarberiaSerializer(user, context={'request': request})
            return Response(barberia_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
@extend_schema_view(
    list=extend_schema(tags=['Barberias'],
        summary="Obtener datos de todas las barberias",),
    retrieve=extend_schema(tags=['Barberias'], 
       summary="Obtener datos de mi barberia",),
    create=extend_schema(
        tags=['Barberias'],
       summary="Crear cuenta de barberia",
       request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'email': {'type': 'string', 'format': 'email'},
                    'password': {'type': 'string'},
                    'profile_imagen': {'type': 'string'},
                    'ubicacion_coordenadas': { 
                        'type': 'object',
                        'properties': {
                            'type': {'type': 'string', 'example': 'Point'},
                            'coordinates': {
                                'type': 'array',
                                'items': {'type': 'number'},
                                'example': [-16.4897, -68.1193]
                            }
                        }
                    },
                    'biometric': {'type': 'string'},
                    'barberia': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name_barber': {'type': 'string'},
                                'phone': {'type': 'string'},
                                'address': {'type': 'string'},
                                'horario': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'turnos_max': {'type': 'integer'},
                                            'days': {
                                                'type': 'array',
                                                'items': {'type': 'string'}
                                            }
                                        }
                                    }
                                },
                                'openingTime': {'type': 'string'},
                                'closingTime': {'type': 'string'}
                            }
                        }
                    }
                },
                'required': []
            }
        }
       ),
    methods=['POST'], tags=['Barberias'], 
    update=extend_schema(exclude=True),  # Oculta el método PUT (update)
    partial_update=extend_schema(
        tags=['Barberias'],
        summary="Editar mi barbería",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'profile_imagen': {'type': 'string'},
                    'ubicacion_coordenadas': { 
                        'type': 'object',
                        'properties': {
                            'type': {'type': 'string', 'example': 'Point'},
                            'coordinates': {
                                'type': 'array',
                                'items': {'type': 'number'},
                                'example': [-16.4897, -68.1193]
                            }
                        }
                    },
                    'biometric': {'type': 'string'},
                    'barberia': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name_barber': {'type': 'string'},
                                'phone': {'type': 'string'},
                                'address': {'type': 'string'},
                                'horario': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'turnos_max': {'type': 'integer'},
                                            'days': {
                                                'type': 'array',
                                                'items': {'type': 'string'}
                                            }
                                        }
                                    }
                                },
                                'openingTime': {'type': 'string'},
                                'closingTime': {'type': 'string'}
                            }
                        }
                    }
                },
                'required': []
            }
        }
    ),
    destroy=extend_schema(tags=['Barberias'],
        summary="Eliminar mi barberia",),
)

class BarberiaViewSet(viewsets.ModelViewSet):
    queryset = User.objects.exclude(barberia=None)
    serializer_class = BarberiaSerializer

    # 1. Indica que el campo de búsqueda es 'id' (el PK de tu modelo User)
    lookup_field = 'id' 
    # 2. Especifica la expresión regular para un ObjectId de 24 caracteres hexadecimales
    lookup_value_regex = '[0-9a-fA-F]{24}' 

    parser_classes = [JSONParser, FormParser, MultiPartParser]

    ##Aqui indico que barberias quiero ver...
    def get_queryset(self):
        user = self.request.user
        
        # Query base: solo barberías activas
        queryset = User.objects.filter(
            barberia__isnull=False, 
            is_active=True
        ).exclude(barberia=[])
        
        # Ordenar por proximidad si el usuario tiene coordenadas
        if self.action == 'list' and user.is_authenticated:
            if hasattr(user, 'ubicacion_coordenadas') and user.ubicacion_coordenadas:
                try:
                    # Extraer coordenadas del usuario
                    user_coords = user.ubicacion_coordenadas.get('coordinates', [])
                    if len(user_coords) == 2:
                        user_lng, user_lat = user_coords
                        
                        # 🔥 SEPARAR barberías CON y SIN coordenadas
                        barberias_con_coordenadas = []
                        barberias_sin_coordenadas = []
                        
                        for barberia in queryset:
                            # Obtener el rating para todas las barberías
                            rating = 0
                            if barberia.barberia and isinstance(barberia.barberia, list) and len(barberia.barberia) > 0:
                                rating = barberia.barberia[0].get('rating', 0)
                            
                            if (barberia.ubicacion_coordenadas and 
                                barberia.ubicacion_coordenadas.get('coordinates')):
                                
                                barberia_coords = barberia.ubicacion_coordenadas['coordinates']
                                if len(barberia_coords) == 2:
                                    barberia_lng, barberia_lat = barberia_coords
                                    
                                    # Calcular distancia
                                    distancia = self.calcular_distancia(
                                        user_lat, user_lng, barberia_lat, barberia_lng
                                    )
                                    
                                    barberias_con_coordenadas.append({
                                        'barberia': barberia,
                                        'distancia': distancia,
                                        'rating': rating
                                    })
                                    continue
                            
                            # Si no tiene coordenadas, agregar a la lista sin coordenadas
                            barberias_sin_coordenadas.append({
                                'barberia': barberia,
                                'distancia': None,
                                'rating': rating
                            })
                        
                        # 🔥 ORDENAR barberías CON coordenadas por distancia (más cercanas primero)
                        barberias_con_coordenadas.sort(key=lambda x: x['distancia'])
                        
                        # 🔥 ORDENAR barberías SIN coordenadas por rating (mejores primero)
                        barberias_sin_coordenadas.sort(key=lambda x: x['rating'], reverse=True)
                        
                        # 🔥 COMBINAR: primero las con coordenadas, luego las sin coordenadas
                        resultado_final = barberias_con_coordenadas + barberias_sin_coordenadas
                        
                        return [item['barberia'] for item in resultado_final]
                        
                except (ValueError, TypeError, AttributeError) as e:
                    print(f"Error calculando distancias: {e}")
                    # Si hay error, continuar con ordenamiento por rating para todas
        
            # 🔥 FALLBACK: Ordenar todas las barberías por rating si no hay coordenadas o hay error
            barberias_con_rating = []
            
            for barberia in queryset:
                rating = 0
                if barberia.barberia and isinstance(barberia.barberia, list) and len(barberia.barberia) > 0:
                    rating = barberia.barberia[0].get('rating', 0)
                    
                barberias_con_rating.append({
                    'barberia': barberia,
                    'rating': rating
                })
            
            barberias_con_rating.sort(key=lambda x: x['rating'], reverse=True)
            return [item['barberia'] for item in barberias_con_rating]
        
        # Si no está autenticado o no es list, devolver queryset normal
        return queryset
                
        
    
    #por si quiero que solamente las mismas barberias vean su info
    #def get_permissions(self):
    #    if self.action == 'create': # Esta linea significa que el endpoint register lo pueda usar cualquiera
    #        return [AllowAny()]  # Permitir registro sin autenticación
    #    elif self.action in ['retrieve', 'partial_update', 'destroy']:  
    #        # Permitir acceso a retrieve, update y destroy solo si el usuario está autenticado
    #       
    #        # Y que el resto de metodos usen IsAuthenticated que significa JWT y el IsSelf que significa
    #        # que el mismo usuario pueda acceder a su propio recurso, ejemplo el usuario 1 solo acceda al endpoint 1 
    #        return [IsAuthenticated(), MiBarberia()]  # 👈 Requiere autenticación y que sea el mismo usuario 
    #    #El IsAuthenticated es creado automaticamente por Django, MiUsuario es creado manualmente
    #    return [IsAuthenticated()]


    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]  # Permitir registro sin autenticación
        elif self.action == 'retrieve':  
            # Permitir a cualquier usuario autenticado ver detalles de cualquier barbería
            return [IsAuthenticated()]
        elif self.action in ['partial_update', 'destroy']:
            # Solo el dueño puede actualizar o eliminar
            return [IsAuthenticated(), MiBarberia()]
        return [IsAuthenticated()]
    

    @extend_schema(tags=['Barberia'])
    def create(self, request, *args, **kwargs):
        # Verificar si el usuario ya existe (autenticación social)
        email = request.data.get('email')
        if email and request.user.is_anonymous:
            try:
                existing_user = User.objects.get(email=email)
                # Si el usuario existe y es social, proceder con actualización
                if hasattr(existing_user, 'social_auth'):
                    serializer = self.get_serializer(
                        existing_user, 
                        data=request.data, 
                        partial=True
                    )
                    serializer.is_valid(raise_exception=True)
                    user = serializer.save()
                    
                    return Response(
                        BarberiaSerializer(user).data, 
                        status=status.HTTP_200_OK
                    )
            except User.DoesNotExist:
                pass

        if request.content_type.startswith("multipart/form-data") or request.content_type.startswith("application/x-www-form-urlencoded"):
            raw_data = querydict_to_nested(request.data)
            data = dict_to_list(raw_data)
        else:
            data = request.data
    
        # 🔑 Normaliza internamente solo dentro de barberia
        barberia = data.get("barberia")
        if barberia:
            if "services" in barberia and isinstance(barberia["services"], dict):
                barberia["services"] = [v for k, v in sorted(barberia["services"].items(), key=lambda x: int(x[0]))]
            if "horario" in barberia and isinstance(barberia["horario"], dict):
                barberia["horario"] = [v for k, v in sorted(barberia["horario"].items(), key=lambda x: int(x[0]))]
                for h in barberia["horario"]:
                    if "days" in h and isinstance(h["days"], dict):
                        h["days"] = [v for k, v in sorted(h["days"].items(), key=lambda x: int(x[0]))]
    
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
    
        signals.user_registered.send(
            sender=self.__class__, user=user, request=self.request
        )
        if djoser_settings.SEND_ACTIVATION_EMAIL:
            context = {"user": user}
            djoser_settings.EMAIL.activation(self.request, context).send([user.email])
    
        return Response(BarberiaSerializer(user).data, status=status.HTTP_201_CREATED)

        
    def update(self, request, *args, **kwargs):
        if not kwargs.get('partial', False):
            return Response(
                {"detail": "Método PUT no permitido. Use PATCH en su lugar."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs) 
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='lat', 
                type=OpenApiTypes.FLOAT, 
                location=OpenApiParameter.QUERY,
                description='Latitud del usuario'
            ),
            OpenApiParameter(
                name='lng', 
                type=OpenApiTypes.FLOAT, 
                location=OpenApiParameter.QUERY,
                description='Longitud del usuario'
            ),
            OpenApiParameter(
                name='radius', 
                type=OpenApiTypes.FLOAT, 
                location=OpenApiParameter.QUERY,
                description='Radio de búsqueda en kilómetros (default: 10)'
            ),
            OpenApiParameter(
                name='city', 
                type=OpenApiTypes.STR, 
                location=OpenApiParameter.QUERY,
                description='Filtrar por ciudad'
            )
        ],
        tags=['Barberias']
    )
    @action(detail=False, methods=['get'], url_path='cercanas')
    def barberias_cercanas(self, request):
        """
        Obtener barberías cercanas a una ubicación
        """
        # Obtener parámetros de la query
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius = float(request.query_params.get('radius', 10))  # Radio default: 10km
        city = request.query_params.get('city')
        
        # Validar parámetros
        if not lat or not lng:
            return Response(
                {"error": "Se requieren parámetros lat y lng"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_lat = float(lat)
            user_lng = float(lng)
        except ValueError:
            return Response(
                {"error": "Latitud y longitud deben ser números válidos"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Query base: solo barberías activas
        queryset = User.objects.filter(
            barberia__isnull=False, 
            is_active=True
        ).exclude(barberia=[])
        
        # Filtrar por ciudad si se especifica
        if city:
            queryset = queryset.filter(city__iexact=city)
        
        # Si tenemos coordenadas, calcular distancias
        barberias_con_distancia = []
        
        for barberia in queryset:
            if barberia.location and barberia.location.get('coordinates'):
                barberia_lat, barberia_lng = barberia.location['coordinates']
                
                # Calcular distancia (fórmula Haversine)
                distancia_km = self.calcular_distancia(
                    user_lat, user_lng, barberia_lat, barberia_lng
                )
                
                # Solo incluir barberías dentro del radio
                if distancia_km <= radius:
                    barberias_con_distancia.append({
                        'barberia': barberia,
                        'distancia_km': round(distancia_km, 2)
                    })
        
        # Ordenar por distancia
        barberias_con_distancia.sort(key=lambda x: x['distancia_km'])
        
        # Paginación
        page = self.paginate_queryset(barberias_con_distancia)
        if page is not None:
            serializer = BarberiaCercanaSerializer(
                [item['barberia'] for item in page], 
                many=True,
                context={'distancias': {item['barberia'].id: item['distancia_km'] for item in page}}
            )
            return self.get_paginated_response(serializer.data)
        
        serializer = BarberiaCercanaSerializer(
            [item['barberia'] for item in barberias_con_distancia],
            many=True,
            context={'distancias': {item['barberia'].id: item['distancia_km'] for item in barberias_con_distancia}}
        )
        
        return Response(serializer.data)
    
    def calcular_distancia(self, lat1, lng1, lat2, lng2):
        """Calcula distancia entre dos puntos usando fórmula Haversine"""
        
        R = 6371  # Radio de la Tierra en km
        
        lat1_rad = radians(lat1)
        lng1_rad = radians(lng1)
        lat2_rad = radians(lat2)
        lng2_rad = radians(lng2)
        
        dlng = lng2_rad - lng1_rad
        dlat = lat2_rad - lat1_rad
        
        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
        
###################################3333333#Comentariose###############################################

@extend_schema_view(
    list=extend_schema(
        tags=['Comentarios'],
        summary="Obtener todos los comentarios que he realizado",
        ),
    retrieve=extend_schema(
        #Retrieve son las consultas Get con ID
        tags=['Comentarios'], 
        summary="Obtener un comentario en especifico",
        ),
    create=extend_schema(
        tags=['Comentarios'],
        summary="Crear comentario para una barberia",
        request=CommentSerializer, 
    ), 
    methods=['POST'], tags=['Comentarios'], 
    update=extend_schema(exclude=True),  # Oculta el método PUT (update)
    partial_update=extend_schema(
        tags=['Comentarios'],
        summary="Editar mi comentario",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'rating': {'type': 'number'},
                    'description': {'type': 'string'},
                },
                'required': []
            }
        }
    ),   
    destroy=extend_schema(tags=['Comentarios'], 
        summary="Eliminar mi comentario",
        ),
)

class ComentarioViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    lookup_field = 'id'
    lookup_value_regex = '[0-9a-fA-F]{24}' 


    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options'] # Excluye 'put'

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # lista general de comentarios del usuario
        if not self.request.user.is_staff and self.action == 'list':
            queryset = queryset.filter(cliente=self.request.user)
        return queryset


    # --- NUEVA ACCIÓN PERSONALIZADA PARA COMENTARIOS DE BARBERÍA ---
    @extend_schema(
        summary="Obtener todos los comentarios de una barbería específica",
        #description="Lista todos los comentarios para una barbería dada por su ID.",
        parameters=[
            {
                "name": "barber_id",
                "type": "string",
                "required": True,
                #"description": "ID de la barbería",
                "in": "path"
            }
        ],
        tags=['Comentarios'] # Asegúrate de que tenga el mismo tag para agrupar
    )
    @action(detail=False, methods=['get'], url_path='barberia/(?P<barber_id>[0-9a-fA-F]{24})')
    def by_barberia(self, request, barber_id=None):
        try:
            barberia_instance = User.objects.get(id=barber_id, barberia__isnull=False)
            comments = Comment.objects.filter(barberia=barberia_instance)
            serializer = self.get_serializer(comments, many=True)
            return Response(serializer.data)
        except (User.DoesNotExist, ValueError):
            raise Http404("Barbería no encontrada o ID inválido.")

    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj


    def get_permissions(self):
        if self.action == 'create':
            # Permitir que cualquier usuario autenticado cree un comentario 
            return [IsAuthenticated()] 
        elif self.action == 'list':
            # Permitir que cualquier usuario autenticado lea comentario 
            return [IsAuthenticated()]
        elif self.action in ['retrieve', 'partial_update', 'destroy']:  
            # Permitir que cualquier usuario autenticado pueda modificar su propio comentario 
            return [IsAuthenticated(), MiUsuario()]  
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer) # This calls serializer.save()
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
###··············####################################################3Turnos    

@extend_schema_view(
    list=extend_schema(
        tags=['Turnos'],
        summary="Obtener la lista de todos mis turnos",
    ),
    retrieve=extend_schema(
        tags=['Turnos'],
        summary="Obtener los detalles de un turno específico",
    ),
    create=extend_schema(
        tags=['Turnos'],
        summary="Reservar un nuevo turno",
        request=TurnoSerializer,
    ),
    update=extend_schema(exclude=True),  # Oculta el método PUT (update)
    partial_update=extend_schema(
        tags=['Turnos'],
        summary="Actualizar un turno existente",
    ),
    destroy=extend_schema(
        tags=['Turnos'],
        summary="Eliminar un turno",
    ),
)

class TurnoViewSet(viewsets.ModelViewSet):
    queryset = Turnos.objects.all()
    serializer_class = TurnoSerializer 
    permission_classes = [IsAuthenticated]

    lookup_field = 'id'
    lookup_value_regex = '[0-9a-fA-F]{24}' 


    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options'] # Excluye 'put'

    def get_serializer_class(self):
        # 💡 Modifica este método para usar el serializador de actualización
        if self.action in ['partial_update', 'update']:
            return TurnoUpdateSerializer
        return TurnoSerializer

    def get_queryset(self):
        # 💡 MODIFICA ESTA FUNCIÓN COMPLETA
        user = self.request.user

        # Si el usuario es un staff (admin), le mostramos todo
        if user.is_staff:
            return Turnos.objects.all()
        # Si el usuario es una barbería, le mostramos todos los turnos que tiene asignados
        elif user.barberia is not None:
            return Turnos.objects.filter(barberia=user)
        # Si el usuario es un cliente, le mostramos todos los turnos que ha solicitado
        else:
            return Turnos.objects.filter(cliente=user)

    def get_permissions(self):
        if self.action == 'create':
            # Permitir que cualquier usuario autenticado cree un turno
            return [IsAuthenticated()] 
        elif self.action == 'list':
            # Permitir que cualquier usuario autenticado lea turnos
            return [IsAuthenticated()]
        elif self.action in ['retrieve', 'partial_update', 'destroy']:  
            # Permitir que cualquier usuario autenticado pueda modificar su propio turno
            return [IsAuthenticated(), EsClienteOBarberoDelTurno()]  
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer) # This calls serializer.save()
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

        
    
    @extend_schema(
        tags=['Turnos'],
        summary="Endpoint para conocer cuales son los turnos disponibles",
    ) 
    @action(detail=False, methods=['get'], url_path='disponibles/(?P<barber_id>[0-9a-fA-F]{24})')
    def turnos_disponibles(self, request, barber_id=None):
        """
        Devuelve todos los turnos libres de todos los días que trabaja la barbería.
        """
        try:
            barberia_instance = User.objects.get(id=barber_id, barberia__isnull=False)
        except User.DoesNotExist:
            raise Http404("Barbería no encontrada")

        barberia_data = barberia_instance.barberia[0]
        dias_laborables = barberia_data['horario'][0]['days']
        max_turnos = barberia_data['horario'][0]['turnos_max']

        # --- Reordenar los días según el día de hoy ---
        hoy = datetime.datetime.now().strftime("%A").lower()  # ej: "thursday"
        
        # Mapeo inglés -> español
        map_dias = {
            "monday": "lunes",
            "tuesday": "martes",
            "wednesday": "miercoles",
            "thursday": "jueves",
            "friday": "viernes",
            "saturday": "sabado",
            "sunday": "domingo"
        }
        dia_actual = map_dias[hoy]
    
        if dia_actual in dias_laborables:
            idx = dias_laborables.index(dia_actual)
            dias_laborables = dias_laborables[idx:] + dias_laborables[:idx]
    
        resultados = []

        for dia in dias_laborables:
            try:
                fecha_turno = Turnos.calcular_fecha_turno(dia.lower())
            except KeyError:
                continue  # Saltar días inválidos

            # Obtener los turnos ocupados para esa fecha
            turnos_ocupados = Turnos.objects.filter(
                barberia=barberia_instance,
                fecha_turno=fecha_turno
            ).values_list('turno', flat=True)

            # Todos los turnos posibles
            todos_los_turnos = list(range(1, max_turnos + 1))
            turnos_libres = [t for t in todos_los_turnos if t not in turnos_ocupados]

            # Calcular la hora de cada turno
            disponibilidad = []
            for t in turnos_libres:
                inicio, fin = calcular_hora_turno(
                    barberia_data['openingTime'],
                    barberia_data['closingTime'],
                    max_turnos,
                    t
                )
                disponibilidad.append({
                    "turno": t,
                    "hora": f"{inicio} - {fin}"
                })

            resultados.append({
                "dia": dia,
                "fecha_turno": fecha_turno.strftime("%d/%m/%Y"),
                "disponibles": disponibilidad
            })

        return Response({
            "barberia": barberia_data['name_barber'],
            "turnos_por_dia": resultados
        })


@extend_schema(
    tags=['Turnos'],
    summary="Endpoint para eliminar turnos antiguos automaticamente",
    description="Endpoint para eliminar turnos antiguos. Solo accesible con un token secreto."
)     
@api_view(['DELETE'])
@permission_classes([AllowAny])
def delete_old_turnos_view(request, token):
    """
    Endpoint para eliminar turnos antiguos.
    Solo accesible con un token secreto.
    """
    if token != VERCEL_API_KEY_SECRET:
        return Response({'detail': 'Token de autenticación inválido.'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        ayer = date.today() - timedelta(days=1)
        turnos_a_borrar = Turnos.objects.filter(fecha_turno__lte=ayer)
        num_turnos_borrados = turnos_a_borrar.count()
        turnos_a_borrar.delete()

        return Response({
            'detail': f'Se eliminaron {num_turnos_borrados} turnos antiguos.',
            'count': num_turnos_borrados
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({'detail': f'Ocurrió un error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    


##########################Servicios

@extend_schema_view(
    list=extend_schema(
        tags=['Servicios'],
        summary="Obtener todos los servicios que he publicado",
        ),
    retrieve=extend_schema(
        #Retrieve son las consultas Get con ID
        tags=['Servicios'], 
        summary="Obtener un servicio en especifico",
        ),
    create=extend_schema(
        tags=['Servicios'],
        summary="Publicar servicios de mi barberia",
        request=ServicioSerializer, 
    ), 
    methods=['POST'], tags=['Servicios'], 
    update=extend_schema(exclude=True),  # Oculta el método PUT (update)
    partial_update=extend_schema(
        tags=['Servicios'],
        summary="Editar mi servicio",
    ),   
    destroy=extend_schema(tags=['Servicios'], 
        summary="Eliminar mi servicio",
        ),
)

class ServicioViewSet(viewsets.ModelViewSet):
    queryset = Servicio.objects.all()
    serializer_class = ServicioSerializer
    permission_classes = [IsAuthenticated]

    lookup_field = 'id'
    lookup_value_regex = '[0-9a-fA-F]{24}' 


    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options'] # Excluye 'put'

    @extend_schema(
        summary="Obtener todos los servicios de una barbería específica",
        #description="Lista todos los comentarios para una barbería dada por su ID.",
        parameters=[
            {
                "name": "barber_id",
                "type": "string",
                "required": True,
                #"description": "ID de la barbería",
                "in": "path"
            }
        ],
        tags=['Servicios'] # Asegúrate de que tenga el mismo tag para agrupar
    )
    # --- NUEVA ACCIÓN PERSONALIZADA PARA SERVICIOS DE BARBERÍA ---
    @action(detail=False, methods=['get'], url_path='barberia/(?P<barber_id>[0-9a-fA-F]{24})')
    def by_barberia(self, request, barber_id=None):
        """
        Obtener todos los servicios de una barbería específica
        """
        try:
            barberia_instance = User.objects.get(id=barber_id, barberia__isnull=False)
            servicios = Servicio.objects.filter(barberia=barberia_instance)
            serializer = self.get_serializer(servicios, many=True)
            return Response(serializer.data)
        except (User.DoesNotExist, ValueError):
            raise Http404("Barbería no encontrada o ID inválido.")

    def perform_create(self, serializer):
        serializer.save(barberia=self.request.user)  # barbería autenticada


    def get_object(self):
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj


    def get_permissions(self):
        if self.action == 'create':
            # Permitir que cualquier usuario autenticado cree un comentario 
            return [IsAuthenticated()] 
        elif self.action == 'list':
            # Permitir que cualquier usuario autenticado lea comentario 
            return [IsAuthenticated()]
        elif self.action in ['partial_update', 'destroy']:  
            # Permitir que cualquier usuario autenticado pueda modificar su propio comentario 
            return [IsAuthenticated(), MiServicio()]  
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer) # This calls serializer.save()
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
###################################3333333#LOGIN###############################################
@extend_schema(tags=['Login'], summary="Iniciar sesion",)
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        if not user.is_active:
            return Response(
                {"detail": "Tu cuenta no esta activa porque no has confirmado tu email. Por favor, revisa tu correo electrónico para activarla."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        # ----------------------------------
        
        # Generar tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'refresh': str(refresh),
            'token': str(refresh.access_token),
        }, status=status.HTTP_200_OK)

###################################3333333#TOKEN##############################################
@extend_schema(tags=['Token'], request=RefreshTokenSerializer, summary="Reiniciar token",)
class TokenRefreshView(generics.GenericAPIView):
    serializer_class = RefreshTokenSerializer  # 👈 Serializador creado manualmente


    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh = serializer.validated_data.get('refresh')

        if refresh:
            try:
                token = RefreshToken(refresh)
                access_token = token.access_token
                return Response({'token': str(access_token)}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': 'Token inválido'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'error': 'Se requiere el token de refresco'}, status=status.HTTP_400_BAD_REQUEST)

