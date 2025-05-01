from django.shortcuts import render

def profile(request):
    # You can access the logged-in user with request.user
    return render(request, 'profile.html', {'user': request.user})
