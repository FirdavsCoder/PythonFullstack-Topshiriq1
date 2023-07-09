from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from django.db.models import Q
from rest_framework.fields import empty
from .models import User, UserConfirmation
from .models import NEW, CODE_VERIFIED, DONE, PHOTO_DONE
from shared.utility import send_email, check_user_type
from django.contrib.auth import authenticate
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from django.core.validators import FileExtensionValidator
from rest_framework.generics import get_object_or_404
from django.contrib.auth.models import update_last_login
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer


class SignUpSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only = True)

    def __init__(self, *args, **kwargs):
        super(SignUpSerializer, self).__init__(*args, **kwargs)
        self.fields['email'] = serializers.CharField(required = True)


    class Meta:
        model = User
        fields = (
            "id",
            "auth_status"
        )
        extra_kwargs = {
            'auth_status': {'read_only': True, 'required': True}
        }

    
    def create(self, validated_data):
        user = super(SignUpSerializer, self).create(validated_data)
        code = user.create_verify_code()
        send_email(user.email, code)
        user.save()
        return user
    

    def validate(self, attrs):
        super(SignUpSerializer, self).validate(attrs)
        data = self.auth_validate(attrs)
        return data


    @staticmethod
    def auth_validate(data):
        user_input = str(data.get('email')).lower()
        if user_input:
            data = {
                "email": user_input,
            }
            return data
        else:
            return ValidationError(
                {
                    "success": False,
                    "message": "Email kiritilishi shart"
                }
            )
        
    def validate_email(self, value):
        value = value.lower()
        if value and User.objects.filter(email=value).exists():
            raise ValidationError(
                {
                    "success": False,
                    "message": "Ushbu email allaqachon olingan"
                }
            )
        return value
    
    def to_representation(self, instance):
        data = super(SignUpSerializer, self).to_representation(instance)
        data.update(instance.token())
        return data
    


class ChangeUserInformation(serializers.Serializer):
    first_name = serializers.CharField(write_only = True, required = True)
    last_name = serializers.CharField(write_only = True, required = True)
    username = serializers.CharField(write_only = True, required = True)
    password = serializers.CharField(write_only = True, required = True)
    confirm_password = serializers.CharField(write_only = True, required = True)

    def validate(self, data):
        password = data.get('password', None)
        confirm_password = data.get("confirm_password", None)

        if password != confirm_password:
            raise ValidationError(
                {
                    "success": False,
                    "message": "Siz kiritgan parollar bir biriga mos emas."
                }
            )
        
        if password:
            validate_password(password)
            validate_password(confirm_password)

        return data
    def validate(self, data):
        password = data.get("password", None)
        confirm_password = data.get("confirm_password", None)

        if password != confirm_password:
            raise ValidationError({
                "success": False,
                "message": "Sizning parolingiz va tasdiqlash parolingiz bir biriga mos emas"
            })

        if password:
            validate_password(password)
            validate_password(confirm_password)

        return data
    
    def validate_username(self, username):
        if len(username) < 5 or len(username) > 30:
            raise ValidationError(
                {
                    "success": False,
                    "message": "Username uzunligi 5 va 30 oraligida bo'lishi kerak"
                }
            )
        if username.isdigit():
            raise ValidationError(
                {
                    "success": False,
                    "message": "Username faqat sonlardan iborat bo'lmasligi talab etiladi"
                }
            )
        return username
    
    def validate_first_name(self, first_name):
        if len(first_name) < 5 or len(first_name) > 30:
            raise ValidationError(
                {
                    "success": False,
                    "message": "Ismingiz uzunligi 5 va 30 oralig'ida bo'lishi kerak"
                }
            )

        if first_name.isdigit():
            raise ValidationError(
                {
                    "success": False,
                    "message": "Ismingiz faqat raqamlardan tashkil topmasligi kerak."
                }
            )
        return first_name
    
    def validate_last_name(self, last_name):
        if len(last_name) < 5 or len(last_name) > 30:
            raise ValidationError({
                "success": False,
                "message": "Familiyangiz uzunligi 5 va 30 oraligida bo'lishi kerak"
            })
        
        if last_name.isdigit():
            raise ValidationError(
                {
                    "success": False,
                    "message": "Familiyangiz faqat raqamlardan tashkil topmasligi kerak ."
                }
            )
        return last_name
    

    def update(self, instance, validated_data):
        instance.first_name = validated_data.get('first_name')
        instance.last_name = validated_data.get('last_name')
        instance.username = validated_data.get('username')
        instance.password = validated_data.get('password')

        if validated_data.get('password'):
            instance.set_password(validated_data.get('password'))

        if instance.auth_status == CODE_VERIFIED:
            instance.auth_status = DONE
        
        instance.save()
        return instance
    

class ChangePhotoSerializer(serializers.Serializer):
    photo = serializers.ImageField(
        validators = [
            FileExtensionValidator(
                allowed_extensions=[
                    "jpg",
                    "jpeg",
                    "png"
                ]
            )
        ]
    )
    def update(self, instance, validated_data):
        photo = validated_data.get('photo')
        if photo:
            instance.photo = photo
            instance.auth_status = PHOTO_DONE
            instance.save()
        return instance
    


class LoginSerializer(TokenObtainPairSerializer):
    def __init__(self, *args, **kwargs):
        super(LoginSerializer, self).__init__(*args, **kwargs)
        self.fields['userinput'] = serializers.CharField(required = True)
        self.fields['username'] = serializers.CharField(required = False, read_only = True)

    def auth_validate(self, data):
        user_input = data.get('userinput')
        if check_user_type(user_input=user_input) == "email":
            user = self.user.get(email__iexact = user_input)
            username = user.username
        elif check_user_type(user_input=user_input) == "username":
            username = user_input
        else:
            raise ValidationError(
                {
                    "success": False,
                    "message": "Siz email yoki username kiritishingiz kerak!"
                }
            )
        authentications_kwargs = {
            self.username_field: username,
            "password": data['password']
        }
        current_user = User.objects.filter(username__iexact = username).first()
        if current_user is not None and current_user.auth_status in [NEW, CODE_VERIFIED]:
            raise ValidationError(
                {
                    "success": False,
                    "message": "Siz hali to'liq ro'yxatdan o'tmagansiz"
                }
            )
        user = authenticate(**authentications_kwargs)
        if user is not None:
            self.user = user
        else:
            raise ValidationError(
                {
                    'success': False,
                    'message': "Login yoki parol xato kiritildi, Iltimos tekshirib qaytadan kiriting!"
                }
            )
    
    def validate(self, data):
        self.auth_validate(data)
        if self.user.auth_status not in [DONE, PHOTO_DONE]:
            raise PermissionDenied("Kechirasiz siz login qila olmaysiz. Ruxsatingiz yo'q!")
        data = self.user.token()
        data['auth_status'] = self.user.auth_status
        data['full_name'] = self.user.full_name
        return data
    
    def get_user(self, **kwargs):
        users = User.objects.filter(**kwargs)
        if not users.exists():
            raise ValidationError(
                {
                    "success": False,
                    "message": "Aktiv akkaunt topilmadi!"
                }
            )
        return users.first()


class LoginRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        access_token_instance = AccessToken(data['access'])
        user_id = access_token_instance['user_id']
        user = get_object_or_404(User, id=user_id)
        update_last_login(None, user)
        return data
    

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()



class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.CharField(write_only = True, required = True)
    def validate(self, attrs):
        email_input = attrs.get('email')
        if email_input is None:
            raise ValidationError(
                {
                    "success": False,
                    "message": "Email kiritilishi shart!"
                }
            )
        user = User.objects.filter(Q(email=email_input))
        if not user.exists():
            raise NotFound(detail="Foydalanuvchi topilmadi! Iltimos tekshirib qaytadan urinib ko'ring!")
        attrs['user'] = user.first()
        return attrs
    

class ResetPasswordSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only = True)
    password = serializers.CharField(min_length = 8, required = True, write_only = True)
    confirm_password = serializers.CharField(min_length = 8, required = True, write_only = True)

    class Meta:
        model = User
        fields = (
            "id",
            "password",
            "confirm_password"
        )


    def validate(self, attrs):
        password = attrs.get('password')
        confirm_password = attrs.get("confirm_password")

        if password != confirm_password:
            raise ValidationError(
                {
                    "success": False,
                    "message": "Siz kiritgan parollar bir-biriga mos emas!"
                }
            )
        if password:
            validate_password(password)
        return attrs
    
    def update(self, instance, validated_data):
        password = validated_data.pop("password")
        instance.set_password(password)
        return super(ResetPasswordSerializer, self).update(instance, validated_data)
    
