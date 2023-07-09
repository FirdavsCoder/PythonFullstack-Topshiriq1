from django.shortcuts import render
from datetime import datetime
from .models import User
from .models import NEW, CODE_VERIFIED, DONE, PHOTO_DONE
from shared.utility import send_email
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.generics import CreateAPIView, UpdateAPIView
from .serializers import SignUpSerializer, ChangeUserInformation, ChangePhotoSerializer, LoginSerializer,\
    LoginRefreshSerializer, LogoutSerializer, ForgotPasswordSerializer, ResetPasswordSerializer



# Create your views here.

class CreateUserApiView(CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = SignUpSerializer


class VerifyApiView(APIView):
    permission_classes = (permissions.IsAuthenticated, )

    def post(self, request, *args, **kwargs):
        user = self.request.user
        code = self.request.data.get('code')

        self.check_verify(user, code)
        return Response(
            {
                "success": "True",
                "auth_status": user.auth_status,
                "access": user.token()['access'],
                "refresh": user.token()['refresh_token']
            }
        )


    @staticmethod
    def check_verify(user, code):
        verifies = user.verify_codes.filter(expiration_time__gte=datetime.now(), code=code, is_confirmed = False)
        if not verifies.exists():
            raise ValidationError(
                {
                    "success": False,
                    "message": "Tasdiqlash kodingiz xato yoki eskirgan."
                }
            )
        else:
            verifies.update(is_confirmed = True)
        
        if user.auth_status == NEW:
            user.auth_status = CODE_VERIFIED
            user.save()
        return True
    
class GetNewVerification(APIView):
    permission_classes = (permissions.IsAuthenticated, )

    def get(self, request, *args, **kwargs):
        user = self.request.user
        self.check_verification(user)
        if user.email:
            code = user.create_verify_code()
            send_email(user.email, code)
        else:
            raise ValidationError(
                {
                    "status": False,
                    "message": "Email yoki telefon raqamingiz xato"
                }
            )
        return Response(
            {
                "success": True,
                "message": "Tasdiqlash kodingiz qaytadan yuborildi."
            }
        )
    

    @staticmethod
    def check_verification(user):
        verifies = user.verify_codes.filter(expiration_time__gte=datetime.now(), is_confirmed=False)
        if verifies.exists():
            data = {
                "success": False,
                "message":"Kodingiz hali ishlatish uchun yaroqli, iltimos kutib turing"
            }
            raise ValidationError(data)
        
class ChangeUserInformationView(UpdateAPIView):
    permission_classes = (permissions.IsAuthenticated, )
    serializer_class = ChangeUserInformation
    http_method_names = ['put', 'patch']

    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        super(ChangeUserInformationView, self).update(request, *args, **kwargs)
        return Response(
            {
                "success": True,
                "message": "Malumotlaringiz muvaffaqiyatli yangilandi.",
                "auth_status": self.request.user.auth_status 
            },
            status=200
        )
    
    def partial_update(self, request, *args, **kwargs):
        super(ChangeUserInformationView, self).partial_update(*args, **kwargs)
        return Response(
            {
                "success": True,
                "message": "Malumotlaringiz muvaffaqiyatli yangilandi.",
                "aut_status": self.request.user.aut_status 
            },
            status=200
        )
    

class ChangePhotoView(APIView):
    permission_classes = (permissions.IsAuthenticated, )
    def put(self, request, *args, **kwargs):
        serializer = ChangePhotoSerializer(data=request.data)
        if serializer.is_valid():
            return Response(
                {
                    "success": True,
                    "message": "Rasm muvaffaqiyatli o'zgartirildi."
                }
            )
        return Response(
            serializer.errors, 
            status=400
        )
    

class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

class LoginRefreshView(TokenRefreshView):
    serializer_class = LoginRefreshSerializer

class LogoutView(APIView):
    permission_classes = (permissions.IsAuthenticated, )
    serializer_class = LogoutSerializer

    def post(self, reqest, *args, **kwargs):
        serializer = self.serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh_token = self.request.data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()
            data = {
                "success": True,
                "message": "Siz tizimdan chiqib ketdingiz! Foydalanish uchun iltimos qaytadan login qiling!"
            }
            return Response(
                data=data, 
                status=205
            )
        except TokenError:
            return(Response(status=400))



class ForgotPasswordView(APIView):
    permission_classes = (permissions.AllowAny, )
    serializer_class = ForgotPasswordSerializer


    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data.get('email')
        user = serializer.validated_data.get('user')
        if email:
            code = user.create_verify_code()
            send_email(email, code)
        return Response(
            {
                "success": True,
                "message": "Tasdiqlash kodi muvaffaqiyatli yuborildi.",
                "access": user.token()['access'],
                "refresh": user.token()['refresh_token'],
                "user_statua": user.auth_status
            },
            status=200
        )
        

class ResetPasswordView(UpdateAPIView):
    permission_classes = (permissions.IsAuthenticated, )
    serializer_class = ResetPasswordSerializer
    http_method_names = ['put', 'patch']


    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        response = super(ResetPasswordView, self).update(request, *args, **kwargs)
        try:
            user = User.objects.get(id=response.data.get('id'))
        except ObjectDoesNotExist as e:
            raise NotFound(detail = "Foydalanuvchi topilmadi.")
        return Response(
            {
                "success": True,
                "message": "Parolingiz muvaffaqiyatli o'zgartirildi.",
                "access": user.token()['access'],
                "refresh": user.token()['refresh_token'],
                "user_status": user.auth_status,
                "full_name": user.full_name
            }
        )
