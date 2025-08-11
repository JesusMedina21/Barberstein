from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework import permissions
"""
Este CODIGO ES SOLAMENTE PARA QUE USUARIOS SI SON ADMINS puedan obtener 
las listas de todos los usuarios, eliminar o editar todos los usuarios
O para que un usuario solamente pueda editar su propia informacion 
"""


class MiUsuarioLogin(BasePermission):

    def has_object_permission(self, request, view, obj):
        # Permite a superusuarios/staff cualquier acción
        if request.user.is_superuser or request.user.is_staff:
            return True
            
        # Permite al dueño de su propia cuenta cualquier acción
        return obj.id == request.user.id


class MiUsuario(BasePermission):
    

    def has_object_permission(self, request, view, obj):
        # Permite a superusuarios/staff cualquier acción
        if request.user.is_superuser or request.user.is_staff:
            return True
            
        # Permite al dueño de su propia cuenta cualquier acción
        return str(obj.cliente.id) == str(request.user.id)
    
class MiBarberia(BasePermission):
    def has_object_permission(self, request, view, obj):
        # Permite a superusuarios/staff cualquier acción
        if request.user.is_superuser or request.user.is_staff:
            return True
            
        # Permite al dueño de su propia cuenta cualquier acción
        return str(obj.id) == str(request.user.id)  # 👈 Cambio clave aquí