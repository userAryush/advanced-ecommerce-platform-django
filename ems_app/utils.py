from django.core.mail import send_mail
from django.conf import settings

def send_notification_email(subject, body, recipient_list):
    """
    Send an email notification.
    :param subject: Email subject
    :param body: Email body
    :param recipient_list: List of recipient email addresses
    """
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        recipient_list,
        fail_silently=False  # Use True to prevent exceptions, but False is better for debugging
    )
    
