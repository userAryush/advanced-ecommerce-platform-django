from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password
from .models import Product
from .serializers import *
from rest_framework.viewsets import ModelViewSet
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token



@api_view(['POST'])
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

class ProductViewSet(ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    
    
    
    