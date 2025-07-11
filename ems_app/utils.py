from django.core.mail import send_mail
from django.conf import settings
from .models import Product
from rest_framework.response import Response
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password
from .serializers import *
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token


@api_view(['POST','GET'])
def register(request):
    data = request.data.copy()
    raw_password = data.get('password')
    data['password'] = make_password(raw_password)

    user_serializer = UserSerializer(data=data)

    if user_serializer.is_valid():
        user = user_serializer.save()
        user_role = user.user_role

        profile_data = {
            'phone': data.get('phone'),
            'address': data.get('address')
        }

        if user_role == 'customer':
            customer_serializer = CustomerSerializer(data=profile_data)
            if customer_serializer.is_valid():
                customer_serializer.save(user=user)
                return Response({'message': 'Customer created!', 'data': customer_serializer.data}, status=201)
            else:
                return Response(customer_serializer.errors, status=400)

        elif user_role == 'supplier':
            supplier_serializer = SupplierSerializer(data=profile_data)
            if supplier_serializer.is_valid():
                supplier_serializer.save(user=user)
                return Response({'message': 'Supplier created!', 'data': supplier_serializer.data}, status=201)
            else:
                return Response(supplier_serializer.errors, status=400)

        elif user_role == 'delivery':
            delivery_serializer = DeliveryPersonnelSerializer(data=profile_data)
            if delivery_serializer.is_valid():
                delivery_serializer.save(user=user)
                return Response({'message': 'Delivery Personnel created!', 'data': delivery_serializer.data}, status=201)
            else:
                return Response(delivery_serializer.errors, status=400)

        elif user_role == 'admin':
            return Response({'error': 'Admin accounts must be created by system administrators.'}, status=403)

        else:
            return Response({'error': 'Invalid user role'}, status=400)

    else:
        return Response(user_serializer.errors, status=400)


@api_view(['POST'])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    
    user = authenticate(request, email=email, password=password) #if matched returns user object else None
    
    if user == None:
        return Response({'error': 'Invalid credentials!'})
    else:
        #create token
        token,_ = Token.objects.get_or_create(user=user)
        return Response(token.key)  

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
    
def low_stock_emailing(product):
    if product.stock_quantity < 5:  # double check
        supplier_email = product.supplier.user.email
        subject = f"Low Stock Alert: {product.product_name}"
        body = (
            f"Dear {product.supplier.user.full_name},\n\n"
            f"The stock for '{product.product_name}' is low.\n"
            f"Remaining quantity: {product.stock_quantity}.\n"
            f"Please restock soon.\n\n"
            f"- Aryush Ecom"
        )
        send_notification_email(subject, body, [supplier_email])
        
@csrf_exempt
def check_all_products_for_low_stock(request):
    if request.method == "POST":
        low_stock_products = Product.objects.filter(stock_quantity__lt=5)
        for product in low_stock_products:
            low_stock_emailing(product)

        if low_stock_products.exists():
            return JsonResponse({'detail': 'Low stocks found and emailed'})
        else:
            return JsonResponse({'detail': 'All stocks are up to date!'})

def create_notification(user, message):
    Notification.objects.create(user=user, message=message)
