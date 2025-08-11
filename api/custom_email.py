from djoser import email
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives

class CustomPasswordResetEmail(email.PasswordResetEmail):
    template_name = 'email/password_reset/body.html'

    def get_context_data(self):
        context = super().get_context_data()
        context.update({
            'site_name': "Barberstein",
            'domain': settings.DOMAIN,
            'protocol': settings.PROTOCOL,
            'support_email': "soporte@barberstein.com",
            'app_name': "Barberstein",
            'contact_phone': "+123456789",
        })
        return context

    def send(self, to, *args, **kwargs):
        context = self.get_context_data()
        
        # Renderiza manualmente los contenidos
        subject = render_to_string('email/password_reset/subject.txt', context)
        subject = subject.strip()  # Elimina espacios y saltos de línea
        body_html = render_to_string('email/password_reset/body.html', context)
        
        # Configura el correo manualmente
        from_email = settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER
        
        # Asegúrate de que 'to' sea un string, no una lista
        if isinstance(to, (list, tuple)):
            to = to[0]  # Toma el primer elemento si es una lista
            
        email_message = EmailMultiAlternatives(
            subject=subject,
            from_email=from_email,
            to=[to]  # Aquí sí pasamos una lista
        )
        email_message.attach_alternative(body_html, "text/html")
        email_message.send()

class CustomUsernameResetEmail(email.UsernameResetEmail):
    template_name = 'email/email_reset/body.html'

    def get_context_data(self):
        context = super().get_context_data()
        context.update({
            'site_name': "Barberstein",
            'domain': settings.DOMAIN,
            'protocol': settings.PROTOCOL,
            'support_email': "soporte@barberstein.com",
            'app_name': "Barberstein",
            'contact_phone': "+123456789",
        })
        return context

    def send(self, to, *args, **kwargs):
        context = self.get_context_data()
        
        # Renderiza manualmente los contenidos
        subject = render_to_string('email/email_reset/subject.txt', context)
        subject = subject.strip()  # Elimina espacios y saltos de línea
        body_html = render_to_string('email/email_reset/body.html', context)
        
        # Configura el correo manualmente
        from_email = settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER
        
        # Asegúrate de que 'to' sea un string, no una lista
        if isinstance(to, (list, tuple)):
            to = to[0]  # Toma el primer elemento si es una lista
            
        email_message = EmailMultiAlternatives(
            subject=subject,
            from_email=from_email,
            to=[to]  # Aquí sí pasamos una lista
        )
        email_message.attach_alternative(body_html, "text/html")
        email_message.send()


class ActivationEmail(email.ActivationEmail):
    template_name = "email/activation/body.html"

    def get_context_data(self):
        context = super().get_context_data()
        context.update({
            'site_name': "Barberstein",
            'domain': settings.DOMAIN,
            'protocol': settings.PROTOCOL,
            'support_email': "soporte@barberstein.com",
            'app_name': "Barberstein",
            'contact_phone': "+123456789",
        })
        return context

    def send(self, to, *args, **kwargs):
        context = self.get_context_data()
        
        # Renderiza manualmente los contenidos
        subject = render_to_string('email/activation/subject.txt', context)
        subject = subject.strip()  # Elimina espacios y saltos de línea
        body_html = render_to_string('email/activation/body.html', context)
        
        # Configura el correo manualmente
        from_email = settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER
        
        # Asegúrate de que 'to' sea un string, no una lista
        if isinstance(to, (list, tuple)):
            to = to[0]  # Toma el primer elemento si es una lista
            
        email_message = EmailMultiAlternatives(
            subject=subject,
            from_email=from_email,
            to=[to]  # Aquí sí pasamos una lista
        )
        email_message.attach_alternative(body_html, "text/html")
        email_message.send()

class CustomPasswordChangedConfirmationEmail(email.PasswordChangedConfirmationEmail):
    template_name = 'email/password_confirm/body.html'

    def get_context_data(self):
        context = super().get_context_data()
        context.update({
            'site_name': "Barberstein",
            'domain': settings.DOMAIN,
            'protocol': settings.PROTOCOL,
            'support_email': "soporte@barberstein.com",
            'app_name': "Barberstein",
            'contact_phone': "+123456789",
        })
        return context

    def send(self, to, *args, **kwargs):
        context = self.get_context_data()
        
        subject = render_to_string('email/password_confirm/subject.txt', context)
        subject = subject.strip()
        body_html = render_to_string('email/password_confirm/body.html', context)
        
        from_email = settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER
        
        if isinstance(to, (list, tuple)):
            to = to[0]
            
        email_message = EmailMultiAlternatives(
            subject=subject,
            from_email=from_email,
            to=[to]
        )
        email_message.attach_alternative(body_html, "text/html")
        email_message.send()

class CustomEmailChangedConfirmationEmail(email.UsernameChangedConfirmationEmail):
    template_name = 'email/email_confirm/body.html'

    def get_context_data(self):
        context = super().get_context_data()
        context.update({
            'site_name': "Barberstein",
            'domain': settings.DOMAIN,
            'protocol': settings.PROTOCOL,
            'support_email': "soporte@barberstein.com",
            'app_name': "Barberstein",
            'contact_phone': "+123456789",
            'new_email': self.context.get('new_email', '')
        })
        return context

    def send(self, to, *args, **kwargs):
        context = self.get_context_data()
        
        subject = render_to_string('email/email_confirm/subject.txt', context)
        subject = subject.strip()
        body_html = render_to_string('email/email_confirm/body.html', context)
        
        from_email = settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER
        
        if isinstance(to, (list, tuple)):
            to = to[0]
            
        email_message = EmailMultiAlternatives(
            subject=subject,
            from_email=from_email,
            to=[to]
        )
        email_message.attach_alternative(body_html, "text/html")
        email_message.send()