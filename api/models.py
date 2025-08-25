from django.db import models
from django.contrib.auth.models import AbstractUser
from .mixins import AutoCleanMongoMixin, ProfileCloudinaryStorage, ServiciosCloudinaryStorage
from django.db.models.signals import pre_save
from django.dispatch import receiver
import logging # Importa logging

logger = logging.getLogger(__name__) # Inicializa el logger

from django.db import models
from django.conf import settings # Importar settings para AUTH_USER_MODEL
from datetime import datetime, timedelta

from django.core.validators import MinValueValidator, MaxValueValidator # Importa los validadores

class User(AutoCleanMongoMixin, AbstractUser):
    #aqui modifico el username para que sea obligatorio pero no unico, 
    #es decir que pueda registrar 2 usuarios con el mismo nombre
    username = models.CharField(max_length=150, unique=False, blank=False, null=False)
    #aqui tengo que indicar por exigencias de Django, que al nombre ya no ser unico
    #lo que va a identificar el usuario como ID seria el email, por lo tanto tengo que
    #sobreescribir el campo email y e identificar el email en USERNAME_FIELD y colocar el
    #REQUIRED_FIELDS a juro porque sino, el codigo no va a funcionar por exigencias del framework
    email = models.EmailField(unique=True)
    pending_email = models.EmailField(blank=True, null=True)  # Nuevo campo
    profile_imagen = models.ImageField(upload_to='profile_images/', storage=ProfileCloudinaryStorage(),  null=True, blank=True)
    #Biometric es el campo que va a necesitar los usuarios para almacenar la huella
    #y pueda iniciar sesion con la huella, biometric guarda sus credenciales como
    #email y password
    # 🔥 NUEVOS CAMPOS DE GEOLOCALIZACIÓN (para todos los usuarios)
    ubicacion_coordenadas = models.JSONField(null=True, blank=True, default=None)
    biometric = models.CharField(max_length=255, null=True, blank=True)
    barberia = models.JSONField(null=True, blank=True, default=None)

    USERNAME_FIELD = 'email' 
    REQUIRED_FIELDS = ['username']

    CLEAN_FIELDS = ['first_name', 'last_name', 'biometric', 'barberia', 'pending_email', 'profile_imagen', 'ubicacion_coordenadas']
    

    def save(self, *args, **kwargs):
        if not self.profile_imagen:  # Si está vacío
            self.profile_imagen = None  # Django lo guarda como null en vez de ""
        super().save(*args, **kwargs)
        self.mongo_clean()



    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        # Asegúrate de que no haya restricciones de unicidad
        unique_together = ()  

class Comment(models.Model):
    barberia = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comments_received',
        limit_choices_to={'barberia__isnull': False}
    )
    
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comments_made'
    )
    
    rating = models.IntegerField(
        validators=[
            MinValueValidator(1, message='El rating mínimo es 1.'),
            MaxValueValidator(5, message='El rating máximo es 5.')
        ]
    )
    description = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Comentario'
        verbose_name_plural = 'Comentarios'
        unique_together = ('barberia', 'cliente')
        ordering = ['-date']

    def __str__(self):
        # Primero, intenta obtener el nombre de la barbería del JSONField
        barber_name = self.barberia.username
        if self.barberia.barberia:
            try:
                # Accede al primer elemento de la lista y luego a la clave 'name_barber'
                barber_name = self.barberia.barberia[0].get('name_barber', self.barberia.username)
            except (KeyError, IndexError):
                # En caso de que no exista la clave o el índice, usa el nombre de usuario
                pass

        return f"Comentario del cliente {self.cliente.first_name} {self.cliente.last_name}, para la Barberia {barber_name} - Calificacion: {self.rating}"

class Turnos(models.Model):
    barberia = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'barberia__isnull': False},
        related_name='barberia_turno',
    )
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cliente_turno',
    )
    turno = models.IntegerField(
        validators=[
            MinValueValidator(1, message='El turno mínimo es 1.'),
            MaxValueValidator(100, message='El turno máximo es 100.')
        ]
    )
    fecha_turno = models.DateField()
    estado = models.CharField(max_length=1, choices=(
        ('R', 'Reservado'),
        ('C', 'Cancelado'),
    ), default='R') # Añade 'default' aquí
    @staticmethod
    def calcular_fecha_turno(dia_seleccionado):
        """Devuelve la fecha del próximo día seleccionado, ajustando para la hora de cierre."""
        today = datetime.now().date()
        now = datetime.now().time()

        dias = {
            'lunes': 0, 'martes': 1, 'miercoles': 2, 'jueves': 3, 'viernes': 4, 'sabado': 5, 'domingo': 6
        }
        
        dia_del_week_int = dias.get(dia_seleccionado.lower())
        
        if dia_del_week_int is None:
            raise ValueError("Día de la semana no válido.")

        dias_a_sumar = (dia_del_week_int - today.weekday() + 7) % 7
        if dias_a_sumar == 0:
            # Si el día seleccionado es hoy, revisa si ya pasó la hora de cierre
            # Esta lógica se manejará en el serializador.
            return today
        
        return today + timedelta(days=dias_a_sumar)
    

    class Meta:
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'
        unique_together = ('barberia', 'turno', 'fecha_turno')  # Asegura que no haya duplicados
        ordering = ['fecha_turno', 'turno']

    def __str__(self):
        return f"Turno  N° {self.turno} para el cliente {self.cliente.first_name} {self.cliente.last_name}, en la Barberia {self.barberia.username}. Estado del turno: {self.get_estado_display()}"


class Servicio(AutoCleanMongoMixin, models.Model):
    
    barberia = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='barberia_servicio',
        limit_choices_to={'barberia__isnull': False}
    )
    description = models.TextField()
    imagen_urls = models.JSONField(default=list)
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=True,blank=True)# Opciones de moneda
    MONEDAS = [
        ("ARS", "Peso argentino"),            
        ("BOB", "Boliviano"),              
        ("BRL", "Real brasileño"),          
        ("CLP", "Peso chileno"),            
        ("COP", "Peso colombiano"),        
        ("CRC", "Colón costarricense"),       
        ("CUP", "Peso cubano"),          
        ("DOP", "Peso dominicano"),          
        ("USD", "Dólar estadounidense"),         
        ("EUR", "Euro"),                    
        ("GTQ", "Quetzal guatemalteco"),      
        ("GYD", "Dólar guyanés"),        
        ("HTG", "Gourde haitiano"),         
        ("HNL", "Lempira hondureño"),       
        ("MXN", "Peso mexicano"),
        ("NIO", "Córdoba nicaragüense"),             
        ("PAB", "Balboa panameño"),        
        ("PYG", "Guaraní paraguayo"),              
        ("PEN", "Sol peruano"),                    
        ("SRD", "Dólar surinamés"),                 
        ("TTD", "Dólar de Trinidad y Tobago"),         
        ("UYU", "Peso uruguayo"),                 
        ("VES", "Bolívar venezolano"),
    ]
    moneda = models.CharField(
        max_length=3,
        choices=MONEDAS,
        null=True,
        blank=True
    )

    CLEAN_FIELDS = ['precio', 'moneda']
    COLLECTION_NAME = "api_servicio"
    
    class Meta:
        verbose_name = 'Servicio'
        verbose_name_plural = 'Servicios'

    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.mongo_clean()
    
    def __str__(self):
        # Primero, intenta obtener el nombre de la barbería del JSONField
        barber_name = self.barberia.username
        if self.barberia.barberia:
            try:
                # Accede al primer elemento de la lista y luego a la clave 'name_barber'
                barber_name = self.barberia.barberia[0].get('name_barber', self.barberia.username)
            except (KeyError, IndexError):
                # En caso de que no exista la clave o el índice, usa el nombre de usuario
                pass

        return f"Servicio: {self.description}. De la Barberia: {barber_name}"
