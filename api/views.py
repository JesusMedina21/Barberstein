from django.http import Http404
from rest_framework import viewsets, status, generics
from api.serializers import *
import os
from datetime import date, timedelta

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


from django.contrib.auth.tokens import default_token_generator
from rest_framework.views import APIView

from api.custom_email import *

VERCEL_API_KEY_SECRET = "ae24638ce08a743c58aea8a35931e76464d8d0a15fed29fc696cfe2bf9806f2f"

#################################################AUTH

@extend_schema(
    request=EmailCambiadoSerializer,
    description='Confirma el cambio de email usando el UID y token del enlace'
)

class EmailCambiadoView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = EmailCambiadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.user
        token = serializer.validated_data['token']
        new_email = serializer.validated_data["new_email"]
        
        if not default_token_generator.check_token(user, token):
            return Response(
                {"token": "Token inválido o expirado"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Guardar el email antiguo temporalmente
        old_email = user.email
        
        # Cambiar el email
        user.email = new_email
        user.save()

        # Enviar confirmación al NUEVO email
        email_context = {
            'user': user,
            'new_email': new_email,
            'old_email': old_email
        }
        
        confirmation_email = CustomEmailChangedConfirmationEmail(request, email_context)
        confirmation_email.send(to=[new_email])

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
    create=extend_schema(tags=['Clientes'],
        summary="Crear cuenta de cliente",),
    methods=['POST'], tags=['Clientes'], 
    update=extend_schema(exclude=True),  # Oculta el método PUT (update)
    partial_update=extend_schema(tags=['Clientes'],
        summary="Editar mi cuenta",),
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

            return User.objects.filter(Q(barberia__isnull=True) | Q(barberia=[]))
    
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

@extend_schema_view(
    list=extend_schema(tags=['Barberias'],
        summary="Obtener datos de todas las barberias",),
    retrieve=extend_schema(tags=['Barberias'], 
       summary="Obtener datos de mi barberia",),
    create=extend_schema(tags=['Barberias'],
       summary="Crear cuenta de barberia",),
    methods=['POST'], tags=['Barberias'], 
    update=extend_schema(exclude=True),  # Oculta el método PUT (update)
    partial_update=extend_schema(tags=['Barberias'], 
        summary="Editar mi barberia",),
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


    def get_queryset(self):
        user = self.request.user
    
        if self.action == 'list':

            return User.objects.filter(barberia__isnull=False).exclude(barberia=[])
    
    
        return super().get_queryset()



    def get_permissions(self):
        if self.action == 'create': # Esta linea significa que el endpoint register lo pueda usar cualquiera
            return [AllowAny()]  # Permitir registro sin autenticación
        elif self.action in ['retrieve', 'partial_update', 'destroy']:  
            # Permitir acceso a retrieve, update y destroy solo si el usuario está autenticado
           
            # Y que el resto de metodos usen IsAuthenticated que significa JWT y el IsSelf que significa
            # que el mismo usuario pueda acceder a su propio recurso, ejemplo el usuario 1 solo acceda al endpoint 1 
            return [IsAuthenticated(), MiBarberia()]  # 👈 Requiere autenticación y que sea el mismo usuario 
        #El IsAuthenticated es creado automaticamente por Django, MiUsuario es creado manualmente
        return [IsAuthenticated()]

    @extend_schema(tags=['Barberia'])
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        
        # ***** NUEVA LÓGICA PARA ENVIAR EL CORREO DE ACTIVACIÓN *****
        signals.user_registered.send(
            sender=self.__class__, user=user, request=self.request
        )
        if djoser_settings.SEND_ACTIVATION_EMAIL:
            context = {"user": user}
            djoser_settings.EMAIL.activation(self.request, context).send([user.email])
        # ************************************************************
        
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
    partial_update=extend_schema(tags=['Comentarios'] ,
        summary="Editar mi comentario",),
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
    
    # ¡AÑADE ESTE MÉTODO!
    def get_serializer_class(self):
        if self.action in ['partial_update', 'update']: # 'update' para PUT completo si lo usas
            return CommentUpdateSerializer
        return self.serializer_class # Retorna el CommentSerializer por defecto para otras acciones

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
        queryset = super().get_queryset()
        
        # lista general de comentarios del usuario
        if not self.request.user.is_staff and self.action == 'list':
            queryset = queryset.filter(cliente=self.request.user)
        return queryset

    def get_permissions(self):
        if self.action == 'create':
            # Permitir que cualquier usuario autenticado cree un turno
            return [IsAuthenticated()] 
        elif self.action == 'list':
            # Permitir que cualquier usuario autenticado lea turnos
            return [IsAuthenticated()]
        elif self.action in ['retrieve', 'partial_update', 'destroy']:  
            # Permitir que cualquier usuario autenticado pueda modificar su propio turno
            return [IsAuthenticated(), MiUsuario()]  
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
                {"detail": "Tu cuenta no está activa. Por favor, revisa tu correo electrónico para activarla."},
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



@extend_schema(
    tags=['Turnos'],
    summary="Eliminar turnos antiguos",
    description="Endpoint para eliminar turnos antiguos. Solo accesible con un token secreto."
)     
@api_view(['GET'])
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
