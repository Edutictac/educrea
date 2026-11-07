"""Fixed invitation emails; no API credentials or bearer links in messages or logs."""
from email.message import EmailMessage
from email.utils import formataddr
import smtplib
import ssl
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter, ValidationError

from ..config import get_settings

UNAVAILABLE = "El envío de invitaciones requiere configurar SMTP seguro, remitente, URL pública y SSO en el servidor."


def configuration():
    settings = get_settings()
    try:
        sender = str(TypeAdapter(EmailStr).validate_python(settings.smtp_from))
        public = urlsplit(settings.public_base_url)
        _ = public.port
        if (not settings.smtp_host or settings.smtp_security not in {"starttls", "ssl"}
                or public.scheme != "https" or not public.hostname or public.username or public.password
                or public.query or public.fragment or not settings.oidc_issuer or not settings.oidc_client_id
                or (settings.smtp_username and (not settings.smtp_password or not settings.smtp_password.get_secret_value().strip()))):
            raise ValueError()
    except (ValueError, ValidationError):
        raise HTTPException(503, UNAVAILABLE) from None
    return settings, sender, settings.public_base_url.rstrip('/') + '/login'


def ready():
    try:
        configuration()
        return True
    except HTTPException:
        return False


def send_invitation(email: str, days: int):
    settings, sender, url = configuration()
    message = EmailMessage()
    message['From'] = formataddr(('EduCrea', sender))
    message['To'] = email
    message['Subject'] = 'Invitación a la beta de EduCrea'
    message.set_content(
        'Te invitamos a participar en la beta de IA EduCrea.\n\n'
        f'Entra en {url} con tu cuenta EduTicTac y este mismo correo verificado. '
        'Si todavía no tienes cuenta EduTicTac, créala con esta dirección antes de entrar.\n\n'
        'La invitación habilitará la IA incluida sin configurar claves personales. '
        f'Puedes aceptarla durante los próximos {days} días.\n'
        'El uso con tu propia API sigue disponible independientemente de la beta.\n')
    transport = smtplib.SMTP_SSL if settings.smtp_security == 'ssl' else smtplib.SMTP
    try:
        kwargs = {'timeout': settings.smtp_timeout_seconds}
        if settings.smtp_security == 'ssl':
            kwargs['context'] = ssl.create_default_context()
        with transport(settings.smtp_host, settings.smtp_port, **kwargs) as smtp:
            if settings.smtp_security == 'starttls':
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            refused = smtp.send_message(message)
            if refused:
                raise smtplib.SMTPException('Invitation recipient refused')
    except (smtplib.SMTPException, OSError, ValueError):
        raise HTTPException(503, 'No se ha podido entregar la invitación al servidor de correo. Revisa la configuración e inténtalo más tarde.') from None
