import csv, json
from django.conf import settings
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, views, generics
from django.middleware.csrf import get_token
from rest_framework.permissions import AllowAny

from twilio.twiml.messaging_response import MessagingResponse

from django.contrib.auth import authenticate, login
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator, api_view, permission_classes

from .models import Member, AdminProfile
from .serializers import MemberSerializer, AdminProfileSerializer

class MemberListAPIView(APIView):
    def get(self, request):
        members = Member.objects.all()
        serializer = MemberSerializer(members, many=True)
        return Response(serializer.data)
    
    #Submitting the Members form to the database
    def post(self, request):
        data = request.data

        # Confirming all keys are filled before submission
        if not all(key in data for key in ['name', 'gender', 'year_of_birth', 'email_address', 'country', 'county', 'sub_county', 'phone_number']):
            return Response({'error': 'Required fields are missing'}, status=status.HTTP_400_BAD_REQUEST)

        member = Member.objects.create(
            name=data['name'],
            gender=data['gender'],
            year_of_birth=data['year_of_birth'],
            email_address=data['email_address'],
            country=data['country'],
            county=data['county'],
            sub_county=data['sub_county'],
            phone_number=data['phone_number'],
        )

        subject = 'Thank you for registering as a SPH member'
        message = f'Hey {member.name},\n\n' \
          f'Thank you for registering as a member at Swahilipot Hub! We are excited to have you on board. Through this email, ' \
          f'you will be receiving updates on events happening at Swahilipot Hub and general information from various departments.\n\n' \
          f'Regards,\n' \
          f'Chris Mwalimo.'
        from_email = 'ciscoplayroom@gmail.com'
        recipient_list = [member.email_address]

        send_mail(subject, message, from_email, recipient_list, fail_silently=False)


        return Response({'message': 'Data received successfully'}, status=status.HTTP_201_CREATED)

class MemberDetailAPIView(APIView):
    def get(self, request, member_id):
        member = Member.objects.get(pk=member_id)
        serializer = MemberSerializer(member)
        return Response(serializer.data)

    def put(self, request, member_id):
        member = Member.objects.get(pk=member_id)
        serializer = MemberSerializer(member, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, member_id):
        member = Member.objects.get(pk=member_id)
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class AdminProfileListCreateView(generics.ListCreateAPIView):
    queryset = AdminProfile.objects.all()
    serializer_class = AdminProfileSerializer

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(user=user)

    def get_queryset(self):
        user = self.request.user
        return AdminProfile.objects.filter(user=user)
    
class ExportCSVView(View):
    def get(self, request, *args, **kwargs):
        data = Member.objects.all() 

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="members_data.csv"'

        writer = csv.writer(response)
        writer.writerow(['Member ID', 'Name', 'Gender', 'Year of Birth', 'Phone Number', 'Email Address', 'Country', 'County', 'Sub County'])

        for row in data:
            writer.writerow([row.member_id, row.name, row.gender, row.year_of_birth, row.phone_number, row.email_address,
                             row.country, row.county, row.sub_county]) 

        return response

#@method_decorator(csrf_exempt, name='dispatch')
class SendEmailToMembersView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            # member_emails = Member.objects.values_list('email_address', flat=True)
            if request.method == 'POST':
                email = request.POST.get('email_address')
                subject = request.POST.get('subject')
                message = request.POST.get('message')

                if not subject or not message:
                    raise ValueError('Subject and message cannot be empty')
            
                send_mail(
                    subject, 
                    message,
                    'ciscoplayroom@gmail.com', 
                    [email], 
                    fail_silently=False
                )

                return JsonResponse({'success': True, 'message': 'Emails sent successfully to members'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

class AdminRegistrationAPIView(generics.CreateAPIView):
    queryset = AdminProfile.objects.all()
    serializer_class = AdminProfileSerializer

    def create(self, request, *args, **kwargs):
        admin_profile_serializer = AdminProfileSerializer(data=request.data)
        if admin_profile_serializer.is_valid():
            admin_profile_serializer.save()
            return Response(admin_profile_serializer.data, status=status.HTTP_201_CREATED)
        return Response(admin_profile_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({'success': True, 'isAdmin': user.is_staff})  # Return data to the frontend
        else:
            return JsonResponse({'success': False, 'message': 'Invalid credentials'})

    return JsonResponse({'success': False, 'message': 'Invalid request'})


@csrf_exempt
def send_sms(request):
    if request.method == 'POST':
        to_number = request.POST.get('to_number')
        message_body = request.POST.get('message_body')
        
        send_sms_with_twilio(to_number, message_body)

        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

def send_sms_with_twilio(to_number, message_body):
    from twilio.rest import Client

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    message = client.messages.create(
        body=message_body,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=to_number
    )

def csrf_token(request):
    csrf_token = get_token(request)
    return JsonResponse({'csrfToken': csrf_token})

@api_view(['POST'])
@permission_classes([AllowAny])
def register_member(request):
    # Validate reCAPTCHA token
    recaptcha_token = request.data.get('recaptchaValue')
    if not recaptcha_token:
        return Response({'error': 'reCAPTCHA token is missing'}, status=status.HTTP_400_BAD_REQUEST)

    # Make a request to reCAPTCHA API to verify the token
    # Use your reCAPTCHA secret key for authentication
    # Check reCAPTCHA documentation for details: https://developers.google.com/recaptcha/docs/verify
    recaptcha_url = 'https://www.google.com/recaptcha/api/siteverify'
    recaptcha_secret_key = settings.RECAPTCHA_SECRET_KEY
    recaptcha_response = requests.post(recaptcha_url, data={
        'secret': recaptcha_secret_key,
        'response': recaptcha_token,
    })

    if not recaptcha_response.json().get('success'):
        return Response({'error': 'reCAPTCHA verification failed'}, status=status.HTTP_400_BAD_REQUEST)

    # Continue processing the form data and register the member
    # ...

    return Response({'success': 'Member registered successfully'}, status=status.HTTP_201_CREATED)
