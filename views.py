from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Count
from .models import Survey, Question, Option, Response
from .forms import CustomUserCreationForm
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Max
from .models import Profile 
import logging
from django.db import IntegrityError

import logging
from django.db import IntegrityError

logger = logging.getLogger(__name__)

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                role = form.cleaned_data.get('role')
                
                # Print form data for debugging
                print(f"Form data: {form.cleaned_data}")
                
                # Create a new Profile instance for the user
                profile = Profile.objects.create(user=user, role=role)
                
                login(request, user)
                if role == 'creator':
                    return redirect('creator_dashboard')
                else:
                    return redirect('taker_dashboard')
            except IntegrityError as e:
                # Log the error
                logger.error(f"IntegrityError during registration: {str(e)}")
                # Print the error for immediate visibility in the console
                print(f"IntegrityError: {str(e)}")
                # Add error message to the form
                form.add_error(None, f"An error occurred during registration: {str(e)}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

# # User Authentication Views
# def register_view(request):
#     print("user 13:")
#     if request.method == 'POST':
#         form = CustomUserCreationForm(request.POST)
#         print("user 16:")
#         print(form.is_valid())
#         print(dir(form))
#         print(form.error_class)
#         print(form.errors.as_data())
#         print(form.error_messages)
#         print(form.has_error)
#         if form.is_valid():
#             print("user17:")
#             user = form.save()
            
#             role = form.cleaned_data.get('role')
#             # Create a new Profile instance for the user
#             profile = Profile.objects.create(user=user, role=role)
#             login(request, user)
#             if role == 'creator':
#                 return redirect('creator_dashboard')
#             else:
#                 return redirect('taker_dashboard')
            
#     else:
#         print("user 32:")
#         form = CustomUserCreationForm()
#     return render(request, 'register.html', {'form': form})

from django.contrib import messages

from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse

def login_view(request):
    print(request)
    if request.method == 'POST':
        
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                print("user:")
                print(user)
                messages.success(request, f"Welcome back, {username}!")
                if user.profile.role == 'creator':
                    return redirect(reverse('creator_dashboard'))
                else:
                    return redirect(reverse('taker_dashboard'))
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from .models import Survey, Response

@login_required
@login_required
def creator_dashboard(request):
    if request.user.profile.role != 'creator':
        return redirect('taker_dashboard')
    surveys = Survey.objects.filter(creator=request.user).annotate(
        response_count=Count('response')
    )
    context = {
        'draft_surveys': surveys.filter(status='draft'),
        'published_surveys': surveys.filter(status='published'),
        'closed_surveys': surveys.filter(status='closed'),
        'republished_surveys': surveys.filter(status='republished'),
        'total_surveys': surveys.count(),
    }
    return render(request, 'creator_dashboard.html', context)

# for taker dashboard
@login_required
def taker_dashboard(request):
    if request.user.profile.role != 'taker':
        return redirect('creator_dashboard')
    
    available_surveys = Survey.objects.filter(status__in=['published', 'republished'])
    
    completed_surveys = Survey.objects.filter(
        response__user=request.user
    ).distinct().annotate(
        completion_date=Max('response__created_at')
    ).values('id', 'title', 'status', 'completion_date')
    
    context = {
        'available_surveys': available_surveys,
        'completed_surveys': completed_surveys,
    }
    return render(request, 'taker_dashboard.html', context)

# create_survey
@login_required
def create_survey(request):
    if request.user.profile.role != 'creator':
        return HttpResponseForbidden("Only Survey Creators can create surveys.")
    
    if request.method == 'POST':
        print("Form data:", request.POST)

        survey = Survey.objects.create(
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            creator=request.user,
            status='draft'
        )
        question_texts = request.POST.getlist('question_text[]')
        question_types = request.POST.getlist('question_type[]')
        options = request.POST.getlist('options[]')

        print("Questions:", question_texts)
        print("Question Types:", question_types)
        print("Options:", options)

        options_per_question = len(options) // len(question_texts)

        for i, q_text in enumerate(question_texts):
            question = Question.objects.create(
                survey=survey,
                text=q_text,
                question_type=question_types[i]
            )
            
            start_index = i * options_per_question
            end_index = start_index + options_per_question
            question_options = options[start_index:end_index]

            unique_options = set()
            for option_text in question_options:
                stripped_option = option_text.strip().lower()
                if stripped_option and stripped_option not in unique_options:
                    Option.objects.create(
                        question=question,
                        text=option_text.strip()
                    )
                    unique_options.add(stripped_option)
                    print(f"Added option: {option_text.strip()} to question: {q_text}")

        print(f"Survey '{survey.title}' created successfully with questions and options.")
        return redirect('edit_survey', survey_id=survey.id)
    
    return render(request, 'create_survey.html')

# edit_survey
@login_required
def edit_survey(request, survey_id):
    survey = get_object_or_404(Survey, id=survey_id, creator=request.user)

    if request.method == 'POST':
        print("Form data:", request.POST)  
        
        if 'delete_question' in request.POST:
            question_id = request.POST['delete_question']
            print("Deleting question ID:", question_id)
            if question_id.isdigit():
                Question.objects.filter(id=question_id).delete()
    
        elif 'delete_option' in request.POST:
            option_id = request.POST['delete_option']
            print("Deleting option ID:", option_id)
            if option_id.isdigit():
                Option.objects.filter(id=option_id).delete()
        
        elif 'new_question_text' in request.POST:
            new_question_text = request.POST['new_question_text']
            new_question_type = request.POST['new_question_type']
            Question.objects.create(survey=survey, text=new_question_text, question_type=new_question_type)
            print(f"Added new question: {new_question_text}")

        question_texts = request.POST.getlist('question_text[]')
        question_types = request.POST.getlist('question_type[]')
        
        if len(question_texts) < 5:
            messages.error(request, "You need at least 5 questions to publish the survey.")
            return redirect('edit_survey', survey_id=survey.id)
        
        questions = survey.questions.all()
        
    else:
        questions = survey.questions.all()  

    return render(request, 'edit_survey.html', {'survey': survey, 'questions': questions})

# publish_survey
@login_required
def publish_survey(request, survey_id):
    if request.user.profile.role != 'creator':
        return HttpResponseForbidden("Only Survey Creators can publish surveys.")
    survey = get_object_or_404(Survey, id=survey_id, creator=request.user, status='draft')
    if survey.questions.count() >= 5:
        survey.status = 'published'
        survey.save()
    return redirect('manage_surveys')

@login_required
def close_survey(request, survey_id):
    if request.user.profile.role != 'creator':
        return HttpResponseForbidden("Only Survey Creators can close surveys.")
    survey = get_object_or_404(Survey, id=survey_id, creator=request.user, status='published')
    survey.status = 'closed'
    survey.save()
    return redirect('manage_surveys')

@login_required
def manage_surveys(request):
    if request.user.profile.role != 'creator':
        return HttpResponseForbidden("Only Survey Creators can manage surveys.")
    surveys = Survey.objects.filter(creator=request.user).annotate(response_count=Count('response'))
    context = {
        'draft_surveys': surveys.filter(status='draft'),
        'published_surveys': surveys.filter(status='published'),
        'closed_surveys': surveys.filter(status='closed'),
        'total_surveys': surveys.count(),
    }
    return render(request, 'creator_dashboard.html', context)

@login_required
def view_survey_results(request, survey_id):
    survey = get_object_or_404(Survey, id=survey_id)

    if not (request.user.profile.role == 'creator' or (request.user.profile.role == 'taker' and survey.status == 'republished')):
        return HttpResponseForbidden("You do not have permission to view survey results.")
    
    questions = survey.questions.all()
    results = []
    for question in questions:
        options = question.options.all()
        option_counts = Response.objects.filter(question=question) \
                        .values('selected_option') \
                        .annotate(count=Count('selected_option'))
        
        total_responses = sum(item['count'] for item in option_counts)
        count_mapping = {item['selected_option']: item['count'] for item in option_counts}
        
        question_result = {
            'question': question.text,
            'options': [
                {
                    'text': option.text,
                    'count': count_mapping.get(option.id, 0),
                    'percentage': (count_mapping.get(option.id, 0) / total_responses * 100) if total_responses > 0 else 0
                }
                for option in options
            ]
        }
        results.append(question_result)
    
    return render(request, 'view_survey_results.html', {
        'survey': survey,
        'results': results,
        'total_responses': total_responses
    })
    
# Survey Taker Views
@login_required
def list_available_surveys(request):
    if request.user.profile.role != 'taker':
        return HttpResponseForbidden("Only Survey Takers can view available surveys.")
    
    available_surveys = Survey.objects.filter(status__in=['published', 'republished'])
    print("Available Surveys:", available_surveys)  # Debugging line

    return render(request, 'available_surveys.html', {'surveys': available_surveys})

# take_survey_2
@login_required
def take_survey(request, survey_id):
    if request.user.profile.role != 'taker':
        return HttpResponseForbidden("Only Survey Takers can take surveys.")
    survey = get_object_or_404(Survey, id=survey_id, status='published')
    questions = Question.objects.filter(survey=survey)

    # Check if the user has already completed this survey
    if Response.objects.filter(survey=survey, user=request.user).exists():
        return HttpResponseForbidden("You have already completed this survey.")

    if request.method == 'POST':
        print("Questions and their options:")
        for question in questions:
            print(f"Question: {question.text}, Options: {[option.text for option in question.options.all()]}")
            option_id = request.POST.get(f'question_{question.id}')
            if option_id:
                option = Option.objects.get(id=option_id)
                Response.objects.create(
                    survey=survey,
                    user=request.user,
                    question=question,
                    selected_option=option
                )
        return redirect('survey_completed', survey_id=survey.id)

    return render(request, 'take_survey.html', {'survey': survey, 'questions': questions})

# survey_Completed
@login_required
def survey_completed(request, survey_id):
    if request.user.profile.role != 'taker':
        return HttpResponseForbidden("Only Survey Takers can complete surveys.")
    
    survey = get_object_or_404(Survey, id=survey_id)
    responses = Response.objects.filter(survey=survey, user=request.user)

    return render(request, 'survey_completed.html', {
        'survey': survey,
        'responses': responses,
    })

# republish survey
@login_required
def republish_survey(request, survey_id):
    print(f"Attempting to republish survey with ID: {survey_id}")
    
    if request.user.profile.role != 'creator':
        print(f"User {request.user.username} is not a creator. Access denied.")
        return HttpResponseForbidden("Only Survey Creators can republish surveys.")
    
    try:
        survey = get_object_or_404(Survey, id=survey_id, creator=request.user)
        print(f"Found survey: {survey.title}, current status: {survey.status}")
        
        if survey.status == 'closed':
            survey.status = 'republished'
            survey.save()
            print(f"Survey status updated to: {survey.status}")
        else:
            print(f"Survey status is not 'closed'. Current status: {survey.status}")
        
        print("Redirecting to manage_surveys")
        return redirect('manage_surveys')
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        # Handle the error appropriately 

# for home
from django.shortcuts import render

def home(request):
    return render(request, 'home.html')  
