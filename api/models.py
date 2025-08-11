from django.db import models
from django.contrib.auth.models import AbstractUser
from .mixins import AutoCleanMongoMixin  # Ajusta ruta si es necesario

import logging # Importa logging

logger = logging.getLogger(__name__) # Inicializa el logger

from django.db import models
from django.conf import settings # Importar settings para AUTH_USER_MODEL
from datetime import datetime, timedelta

from django.core.validators import MinValueValidator, MaxValueValidator # Importa los validadores

class User(AutoCleanMongoMixin, AbstractUser):
    #Biometric es el campo que va a necesitar los usuarios para almacenar la huella
    #y pueda iniciar sesion con la huella, biometric guarda sus credenciales como
    #email y password
    biometric = models.CharField(max_length=255, null=True, blank=True)
    #aqui modifico el username para que sea obligatorio pero no unico, 
    #es decir que pueda registrar 2 usuarios con el mismo nombre
    username = models.CharField(max_length=150, unique=True, blank=False, null=False)
    #aqui tengo que indicar por exigencias de Django, que al nombre ya no ser unico
    #lo que va a identificar el usuario como ID seria el email, por lo tanto tengo que
    #sobreescribir el campo email y e identificar el email en USERNAME_FIELD y colocar el
    #REQUIRED_FIELDS a juro porque sino, el codigo no va a funcionar por exigencias del framework
    email = models.EmailField(unique=True)
    barberia = models.JSONField(null=True, blank=True, default=None)

    USERNAME_FIELD = 'email' 
    REQUIRED_FIELDS = ['username']

    CLEAN_FIELDS = ['first_name', 'last_name', 'biometric', 'barberia']
    

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.mongo_clean()  # 👈 limpieza automática

    class Meta:
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
        unique_together = ('barberia', 'cliente')
        ordering = ['-date']

    def __str__(self):
        return f"Comentario de {self.cliente.username} para {self.barberia.username} - Rating: {self.rating}"


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
        unique_together = ('barberia', 'turno', 'fecha_turno')  # Asegura que no haya duplicados
        ordering = ['fecha_turno', 'turno']
    def __str__(self):
        return f"Turno {self.turno} para {self.cliente.username} en {self.barberia.username} - Estado: {self.estado}"


      

