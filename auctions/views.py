from django.urls import reverse
from django.db.models import Max
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, login, logout
from zeep import Client
from rest_framework.response import Response
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer

from .models import User, Category, AuctionListing, Bid, Comment


def index(request):
    obj = AuctionListing.objects.filter(active=True)
    return render(request, "auctions/index.html", {
        "objects": obj
    })


def all(request):
    obj = AuctionListing.objects.all()
    return render(request, "auctions/index.html", {
        "objects": obj
    })


def login_view(request):
    if request.method == "POST":

        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Se verifica la autenticacion de usuario
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "auctions/login.html", {
                "message": "Datos invalidos usuario y password."
            })
    else:
        return render(request, "auctions/login.html")


@login_required
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "auctions/register.html", {
                "message": "Las contrase??as deben coincidir."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "auctions/register.html", {
                "message": "Nombre de usuario ya existente!"
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "auctions/register.html")


@login_required
def createListing(request):
    if request.method == 'POST':
        title = request.POST["title"]
        description = request.POST["description"]
        startBid = request.POST["startBid"]
        type_vehiculo = request.POST["type_vehiculo"]
        model = request.POST["model"]
        year = request.POST["year"]
        category = Category.objects.get(id=request.POST["category"])
        user = request.user
        imageUrl = request.POST["url"]
        if imageUrl == '':
            imageUrl = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/300px-No_image_available.svg.png"
        listing = AuctionListing.objects.create(
            name=title, category=category, date=timezone.now(), startBid=startBid, type_vehiculo=type_vehiculo, model=model, year=year, description=description, user=user, imageUrl=imageUrl, active=True)
        listing.save()
        return HttpResponseRedirect(reverse("index"))
    return render(request, "auctions/createListing.html", {
        'categories': Category.objects.all()
    })


def details(request, id):
    item = AuctionListing.objects.get(id=id)
    bids = Bid.objects.filter(auctionListing=item)
    comments = Comment.objects.filter(auctionListing=item)
    value = bids.aggregate(Max('bidValue'))['bidValue__max']
    bid = None
    if value is not None:
        bid = Bid.objects.filter(bidValue=value)[0]
    return render(request, "auctions/details.html", {
        'item': item,
        'bids': bids,
        'comments': comments,
        'bid': bid
    })


def categories(request):
    if request.method == 'POST':
        category = request.POST["category"]
        new_category, created = Category.objects.get_or_create(
            name=category.lower())
        if created:
            new_category.save()
        else:
            messages.warning(request, "Categoria ya existe!")
        return HttpResponseRedirect(reverse("categories"))
    return render(request, "auctions/categories.html", {
        'categories': Category.objects.all()
    })


def filter(request, name):
    category = Category.objects.get(name=name)
    obj = AuctionListing.objects.filter(category=category)
    return render(request, "auctions/index.html", {
        "objects": obj
    })


@api_view(('GET',))
def tipo_cambio(request):
    wsdl = 'http://www.banguat.gob.gt/variables/ws/TipoCambio.asmx?WSDL'
    client = Client(wsdl)
    response = client.service.TipoCambioDia()
    return Response({"data": response['CambioDolar']['VarDolar'][0]['referencia']})


@login_required
def comment(request, id):
    if request.method == 'POST':
        auctionListing = AuctionListing.objects.get(id=id)
        user = request.user
        commentValue = request.POST["content"].strip()
        if(commentValue != ""):
            comment = Comment.objects.create(date=timezone.now(
            ), user=user, auctionListing=auctionListing, commentValue=commentValue)
            comment.save()
        return HttpResponseRedirect(reverse("details", kwargs={'id': id}))
    return HttpResponseRedirect(reverse("index"))


@login_required
def bid(request, id):
    if request.method == 'POST':
        auctionListing = AuctionListing.objects.get(id=id)
        bidValue = request.POST["bid"]
        args = Bid.objects.filter(auctionListing=auctionListing)
        value = args.aggregate(Max('bidValue'))['bidValue__max']
        if value is None:
            value = 0
        if float(bidValue) < auctionListing.startBid or float(bidValue) <= value:
            messages.warning(
                request, f'Oferta superior a: {max(value, auctionListing.startBid)}!')
            return HttpResponseRedirect(reverse("details", kwargs={'id': id}))
        user = request.user
        bid = Bid.objects.create(
            date=timezone.now(), user=user, bidValue=bidValue, auctionListing=auctionListing)
        bid.save()
    return HttpResponseRedirect(reverse("details", kwargs={'id': id}))


@login_required
def end(request, itemId):
    auctionListing = AuctionListing.objects.get(id=itemId)
    user = request.user
    if auctionListing.user == user:
        auctionListing.active = False
        auctionListing.save()
        messages.success(
            request, f'Subasta de  {auctionListing.name} cerrada con ??xito!')
    else:
        messages.info(
            request, 'No estas autorizado a finalizar este listado!')
    return HttpResponseRedirect(reverse("details", kwargs={'id': itemId}))


@login_required
def watchlist(request):
    if request.method == 'POST':
        user = request.user
        auctionListing = AuctionListing.objects.get(id=request.POST["item"])
        if request.POST["status"] == '1':
            user.watchlist.add(auctionListing)
        else:
            user.watchlist.remove(auctionListing)
        user.save()
        return HttpResponseRedirect(
            reverse("details", kwargs={'id': auctionListing.id}))
    return HttpResponseRedirect(reverse("index"))


@login_required
def watch(request):
    user = request.user
    obj = user.watchlist.all()
    return render(request, "auctions/index.html", {
        "objects": obj
    })
