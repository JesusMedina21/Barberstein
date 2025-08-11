from django.contrib import admin
from django.contrib.auth.models import Group
from .models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

class UserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput)
    make_admin = forms.BooleanField(
        label='Admin',
        required=False,
        help_text='Obtiene todos los permisos de la API y sus usuarios'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'is_active', 'make_admin')

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        
        if self.cleaned_data['make_admin']:
            user.is_staff = True
            user.is_superuser = True
        
        if commit:
            user.save()
        return user

class UserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = '__all__'

class UserAdmin(BaseUserAdmin):
    add_form = UserCreationForm
    form = UserChangeForm  # Añade el formulario para edición
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 
                      'is_active', 'make_admin'),
        }),
    )
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información personal', {'fields': ('email', 'biometric')}),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        """
        Usa el formulario especial para creación pero el estándar para edición
        """
        defaults = {}
        if obj is None:  # Es creación
            defaults['form'] = self.add_form
        else:  # Es edición
            defaults['form'] = self.form
            
        defaults.update(kwargs)
        form = super().get_form(request, obj, **defaults)
        
        # Solo añade el evento onchange para el campo make_admin si existe
        if 'make_admin' in form.base_fields:
            form.base_fields['make_admin'].widget.attrs.update({
                'class': 'admin-checkbox',
                'onchange': 'toggleAdminStatus(this)'
            })
            
        return form

    class Media:
        js = ('admin/js/user_admin.js',)


admin.site.register(User, UserAdmin)
admin.site.unregister(Group)