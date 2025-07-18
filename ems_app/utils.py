from django.core.mail import send_mail
from django.conf import settings
from .models import Product
from rest_framework.response import Response
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password
from .serializers import *
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAdminUser,IsAuthenticated,AllowAny
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied



@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    data = request.data.copy()
    not_hashed_password = data.get('password')
    hased_password = make_password(not_hashed_password)
    data['password'] = hased_password

    user_serializer = UserSerializer(data=data)

    if user_serializer.is_valid():
        user = user_serializer.save()
        user_role = user.user_role

        group_id = None

        if user_role == 'supplier':
            group_id = 2
        elif user_role == 'customer':
            group_id = 3
        elif user_role == 'delivery':
            group_id = 4

        if group_id:
            try:
                group = Group.objects.get(id=group_id)
                user.groups.add(group)
            except Group.DoesNotExist:
                return Response({'error': 'Group does not exist!'}, status=400)

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
@permission_classes([AllowAny])
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


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_dashboard_analytics(request):
    # Calculate total revenue from completed payments
    completed_payments = Payment.objects.filter(status='completed')
    total_revenue = 0
    for payment in completed_payments:
        total_revenue += payment.amount

    # Calculate order counts
    all_orders = Order.objects.all()
    total_orders = 0
    pending_orders = 0
    delivered_orders = 0
    cancelled_orders = 0

    for order in all_orders:
        total_orders += 1
        if order.status == 'checkout_pending':
            pending_orders += 1
        elif order.status == 'delivered':
            delivered_orders += 1
        elif order.status == 'cancelled':
            cancelled_orders += 1

    # Calculate top suppliers
    supplier_sales = {}  # Dictionary to store total sales for each supplier

    order_items = OrderItem.objects.all()
    for item in order_items:
        if item.product and item.product.supplier:
            supplier = item.product.supplier
            supplier_id = supplier.id
            supplier_name = supplier.user.full_name
            item_sales = item.price * item.quantity

            if supplier_id not in supplier_sales:
                supplier_sales[supplier_id] = {
                    'supplier_id': supplier_id,
                    'supplier_name': supplier_name,
                    'total_sales': 0
                }

            supplier_sales[supplier_id]['total_sales'] += item_sales

    def get_total_sales(supplier):
        return supplier['total_sales']
    # Convert to list and sort by total sales
    top_suppliers_list = list(supplier_sales.values())

    top_suppliers_list.sort(key=get_total_sales, reverse=True)

    top_suppliers = top_suppliers_list[:5]  # Get top 5

    return Response({
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'delivered_orders': delivered_orders,
        'cancelled_orders': cancelled_orders,
        'top_suppliers': top_suppliers,
    })
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supplier_dashboard_analytics(request):
    user = request.user

    # Check if user is a supplier
    if user.user_role != 'supplier':
        return Response({'detail': 'You are not a supplier.'}, status=403)

    supplier = user.supplier

    # Total products
    products = Product.objects.filter(supplier=supplier)
    total_products = 0
    total_stock = 0
    low_stock_products = 0

    for product in products:
        total_products += 1
        total_stock += product.stock_quantity
        if product.stock_quantity < 5:
            low_stock_products += 1

    # Calculate revenue generated
    order_items = OrderItem.objects.filter(product__supplier=supplier, order__payment_status='paid')
    revenue_generated = 0

    for item in order_items:
        item_total = item.price * item.quantity
        revenue_generated += item_total

    # Orders pending
    pending_order_items = OrderItem.objects.filter(product__supplier=supplier, order__status='ordered')
    orders_pending = 0

    for item in pending_order_items:
        orders_pending += 1

    # Return the analytics data
    return Response({
        'total_products': total_products,
        'total_stock': total_stock,
        'low_stock_products': low_stock_products,
        'revenue_generated': revenue_generated,
        'orders_pending': orders_pending,
    })
    
@api_view(['GET'])
@permission_classes([AllowAny])
def group_id(request):
    group_objs = Group.objects.all()
    serializer_class = GroupSerializer(group_objs, many=True)
    return Response(serializer_class.data)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_delivery_as_delivered(request, delivery_pk):
    user = request.user

    try:
        delivery = Delivery.objects.get(id=delivery_pk)
    except Delivery.DoesNotExist:
        return Response({'detail': 'Delivery not found.'})

    # Ensure only assigned personnel can update
    if delivery.delivery_personnel is None or delivery.delivery_personnel.user != user:
        raise PermissionDenied('You are not assigned to this delivery.')

    # Hardcode the status!
    delivery.delivery_status = 'delivered'
    delivery.delivered_date = timezone.now()

    # Update parent order status too
    delivery.order.status = 'delivered'
    delivery.order.save()
    delivery.save()
    
    customer_email = delivery.order.customer.user.email
    subject = f"Order {delivery.order.id}"
    body = (
        f"Dear {delivery.order.customer.user.full_name},\n\n"
        f"Your Order has been delivered!\n"

        f"- Aryush Ecom"
    )
    send_notification_email(subject, body, [customer_email])

    return Response({'detail': f'Delivery #{delivery.id} marked as delivered.','order_id': delivery.order.id,})
