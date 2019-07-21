# -*- coding: utf-8 -*-

from base64 import b64encode
from copy import copy
import json
import re
import sys
from urlparse import parse_qsl
import urllib
from uuid import uuid4

import inputstreamhelper
import requests
import xbmc
from xbmcaddon import Addon
import xbmcgui
import xbmcplugin
import xbmcvfs

__addon__ = Addon()

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36"
MUA = "Dalvik/2.1.0 (Linux; U; Android 8.0.0; Nexus 5X Build/OPP3.170518.006)"

LISTING_CONTAINER_CONTENT_TYPE_MOVIE = 1
LISTING_CONTAINER_CONTENT_TYPE_SERIES = 2
LISTING_CONTAINER_CONTENT_TYPE_SERIES_EPISODE = 3

NON_AUTHENTICATED_OP_ID = "00000000-0000-0000-0000-000000000000"

se = __addon__.getSetting("se")
language = __addon__.getSetting("language")

mode = params = url = name = None

if language in ["0", "1"]:
    lang = "Hungarian"
    lang_code = "HUN"
    srtsubs_path = xbmc.translatePath("special://temp/hbogo.Hungarian.Forced.srt")
elif language == "2":
    lang = "English"
    lang_code = "ENG"
    srtsubs_path = xbmc.translatePath("special://temp/hbogo.English.Forced.srt")


media_path = xbmc.translatePath(__addon__.getAddonInfo("path") + "/resources/media/")

operator = __addon__.getSetting("operator")

op_ids = [
    NON_AUTHENTICATED_OP_ID,  # Anonymous NoAuthenticated
    "15276cb7-7f53-432a-8ed5-a32038614bbf",  # HBO GO webes
    "48f48c5b-e9e4-4fca-833b-2fa26fb1ad22",  # UPC Direct
    "b7728684-13d5-46d9-a9a4-97d676cdaeec",  # DIGI
    "04459649-8a90-46f1-9390-0cd5b1958a5d",  # Magyar Telekom Nyrt.
    "e71fabae-66b6-4972-9823-8743f8fcf06f",  # Telenor MyTV
    "1ca45800-464a-4e9c-8f15-8d822ad7d8a1",  # UPC Magyarország
    "f2230905-8e25-4245-80f9-fccf67a24005",  # INVITEL
    "383cd446-06fb-4a59-8d39-200a3e9bcf6f",  # Celldömölki Kábeltelevízió Kft.
    "fe106c75-293b-42e6-b211-c7446835b548",  # Eurocable – Hello Digital
    "42677aa5-7576-4dc7-9004-347b279e4e5d",  # HFC-Network Kft.
    "3a3cce31-fb19-470a-9bb5-6947c4ac9996",  # HIR-SAT 2000 Kft.
    "c6441ec8-e30f-44b6-837a-beb2eb971395",  # Jurop Telekom
    "d91341c2-3542-40d4-adab-40b644798327",  # Kabelszat 2002
    "18fb0ff5-9cfa-4042-be00-638c5d34e553",  # Klapka Lakásszövetkezet
    "97cddb59-79e3-4090-be03-89a6ae06f5ec",  # Lát-Sat Kft.
    "c48c350f-a9db-4eb6-97a6-9b659e2db47f",  # MinDig TV Extra
    "7982d5c7-63df-431d-806e-54f98fdfa36a",  # PARISAT
    "18f536a3-ecac-42f1-91f1-2bbc3e6cfe81",  # PR-TELECOM
    "adb99277-3899-439e-8bdf-c749c90493cd",  # TARR Kft
    "5729f013-f01d-4cc3-b048-fe5c91c64296",  # Vác Városi Kábeltelevízió Kft.
    "b4f422f7-5424-4116-b72d-7cede85ead4e",  # Vidanet Zrt.
    "6a52efe0-54c4-4197-8c55-86ee7a63cd04",  # HBO Development Hungary
    "f320aa2c-e40e-49c2-8cdd-1ebef2ac6f26",  # HBO GO Vip/Club Hungary
]
op_id = op_ids[int(operator)]

individualization = ""
go_token = ""
customer_id = ""
go_customer_id = ""
session_id = NON_AUTHENTICATED_OP_ID
favorites_group_id = ""

loggedin_headers = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.hbogo.hu/",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.hbogo.hu",
    "X-Requested-With": "XMLHttpRequest",
    "GO-Language": "HUN",
    "GO-requiredPlatform": "CHBR",
    "GO-Token": "",
    "GO-SessionId": "",
    "GO-swVersion": "4.8.0",
    "GO-CustomerId": "",
    "Connection": "keep-alive",
    "Accept-Encoding": "",
}


def store_individualization():
    # individualization es customerId eltarolasa
    global individualization
    global customer_id

    individualization = __addon__.getSetting("individualization")
    sys.stderr.write(individualization)
    if not individualization:
        individualization = str(uuid4())
        __addon__.setSetting("individualization", individualization)

    customer_id = __addon__.getSetting("customerId")
    if not customer_id:
        customer_id = str(uuid4())
        __addon__.setSetting("customerId", customer_id)


def store_favgroup(favgroupid):
    # FavoritesGroupId eltarolasa
    global favorites_group_id

    favorites_group_id = __addon__.getSetting("FavoritesGroupId")
    if not favorites_group_id:
        __addon__.setSetting("FavoritesGroupId", favgroupid)
        favorites_group_id = favgroupid


def get_favorite_group():
    # lejatszasi lista id lekerdezes
    global favorites_group_id

    response = requests.get(
        "https://huapi.hbogo.eu/v7/Settings/json/HUN/COMP", headers=loggedin_headers
    )
    jsonrsp = response.json()

    favorites_group_id = jsonrsp["FavoritesGroupId"]
    store_favgroup(favorites_group_id)


def login():
    # belepes
    global session_id
    global go_token
    global customer_id
    global go_customer_id
    global individualization
    global loggedin_headers
    global favorites_group_id

    operator = __addon__.getSetting("operator")
    username = __addon__.getSetting("username")
    password = __addon__.getSetting("password")
    customer_id = __addon__.getSetting("customerId")
    individualization = __addon__.getSetting("individualization")
    favorites_group_id = __addon__.getSetting("FavoritesGroupId")

    if not all((individualization, customer_id)):
        store_individualization()

    if not favorites_group_id:
        get_favorite_group()

    if not all((username, password)):
        xbmcgui.Dialog().ok(
            "Hiba", "Kérlek add meg a beállításoknál a belépési adatokat!"
        )
        __addon__.openSettings("Accunt")
        xbmc.executebuiltin("Container.Refresh")
        login()

    headers = {
        "Origin": "https://gateway.hbogo.eu",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "hu,en-US;q=0.9,en;q=0.8",
        "User-Agent": UA,
        "GO-Token": "",
        "Accept": "application/json",
        "GO-SessionId": "",
        "Referer": "https://gateway.hbogo.eu/signin/form",
        "Connection": "keep-alive",
        "GO-CustomerId": NON_AUTHENTICATED_OP_ID,
        "Content-Type": "application/json",
    }

    # TODO: a gatewayes hivasok helyett lehet vissza lehet alni a bulgar verziora, de jelenleg igy tuti mukodik
    # a linkek a weboldalrol lettek kiszedve
    if operator == "1":
        url = "https://api.ugw.hbogo.eu/v3.0/Authentication/HUN/JSON/HUN/COMP"
    else:
        url = "https://hugwapi.hbogo.eu/v2.1/Authentication/json/HUN/COMP"

    data_obj = {
        "Action": "L",
        "AppLanguage": None,
        "ActivationCode": None,
        "AllowedContents": [],
        "AudioLanguage": None,
        "AutoPlayNext": False,
        "BirthYear": 1,
        "CurrentDevice": {
            "AppLanguage": "",
            "AutoPlayNext": False,
            "Brand": "Chromium",
            "CreatedDate": "",
            "DeletedDate": "",
            "Id": NON_AUTHENTICATED_OP_ID,
            "Individualization": individualization,
            "IsDeleted": False,
            "LastUsed": "",
            "Modell": "62",
            "Name": "",
            "OSName": "Ubuntu",
            "OSVersion": "undefined",
            "Platform": "COMP",
            "SWVersion": "2.4.2.4025.240",
            "SubtitleSize": "",
        },
        "CustomerCode": "",
        "DebugMode": False,
        "DefaultSubtitleLanguage": None,
        "EmailAddress": username,
        "FirstName": "",
        "Gender": 0,
        "Id": NON_AUTHENTICATED_OP_ID,
        "IsAnonymus": True,
        "IsPromo": False,
        "Language": "HUN",
        "LastName": "",
        "Nick": "",
        "NotificationChanges": 0,
        "OperatorId": op_id,
        "OperatorName": "",
        "OperatorToken": "",
        "ParentalControl": {
            "Active": False,
            "Password": "",
            "Rating": 0,
            "ReferenceId": NON_AUTHENTICATED_OP_ID,
        },
        "Password": password,
        "PromoCode": "",
        "ReferenceId": NON_AUTHENTICATED_OP_ID,
        "SecondaryEmailAddress": "",
        "SecondarySpecificData": None,
        "ServiceCode": "",
        "SubscribeForNewsletter": False,
        "SubscState": None,
        "SubtitleSize": "",
        "TVPinCode": "",
        "ZipCode": "",
    }

    data = json.dumps(data_obj)
    response = requests.post(url, headers=headers, data=data)

    jsonrspl = response.json()

    if jsonrspl.get("ErrorMessage"):
        xbmcgui.Dialog().ok("Login Hiba!", jsonrspl["ErrorMessage"])

    customer_id = jsonrspl["Customer"]["CurrentDevice"]["Id"]
    individualization = jsonrspl["Customer"]["CurrentDevice"]["Individualization"]

    session_id = jsonrspl["SessionId"]
    if session_id == NON_AUTHENTICATED_OP_ID:
        xbmcgui.Dialog().ok("Login Hiba!", "Ellenőrizd a belépési adatokat!")
        __addon__.openSettings("Accunt")
        xbmc.executebuiltin("Action(Back)")
    else:
        go_token = jsonrspl["Token"]
        go_customer_id = jsonrspl["Customer"]["Id"]

        loggedin_headers["GO-SessionId"] = str(session_id)
        loggedin_headers["GO-Token"] = str(go_token)
        loggedin_headers["GO-CustomerId"] = str(go_customer_id)


def categories():
    # kategoria
    global favorites_group_id

    add_directory("Keresés...", "search", "", 4, "")

    if not favorites_group_id:
        get_favorite_group()

    if favorites_group_id:
        add_directory(
            "Lejátszási listád",
            "https://huapi.hbogo.eu/v7/CustomerGroup/json/HUN/COMP/%s/-/-/-/1000/-/-/false"
            % (favorites_group_id),
            "",
            1,
            media_path + "FavoritesFolder.png",
        )

    response = requests.get(
        "https://huapi.hbogo.eu/v5/Groups/json/HUN/COMP", headers=loggedin_headers
    )
    jsonrsp = response.json()

    if jsonrsp.get("ErrorMessage"):
        xbmcgui.Dialog().ok("Hiba", jsonrsp["ErrorMessage"])

    for item in jsonrsp.get("Items"):
        if not item.get("ObjectUrl"):
            # if the item has no URL we shouldn't display it
            continue
        add_directory(
            item.get("Name", "Ismeretlen kategória").encode("utf-8", "ignore"),
            item.get("ObjectUrl").replace(
                "/0/{sort}/{pageIndex}/{pageSize}/0/0", "/0/0/1/1024/0/0"
            ),
            "",
            1,
            media_path + "DefaultFolder.png",
        )


def list_add_movie_link(item):
    # if it's a movie: # add_link(ou, plot, ar, imdb, bu, cast, director, writer, duration, genre, name, on, py, mode)
    plot = item["Abstract"].encode("utf-8", "ignore")

    if item.get("AvailabilityTo"):
        plot += " A film megtekinthető: %s" % (
            item["AvailabilityTo"].encode("utf-8", "ignore")
        )

    object_url = item["ObjectUrl"]
    age_rating = item["AgeRating"]
    imdb = item["ImdbRate"]
    background_url = item["BackgroundUrl"]
    cast = [item["Cast"].split(", ")][0]
    director = item["Director"]
    writer = item["Writer"]
    duration = item["Duration"]
    genre = item["Genre"]
    name = item["Name"].encode("utf-8", "ignore")
    original_name = item["OriginalName"]
    production_year = item["ProductionYear"]

    add_link(
        object_url,
        plot,
        age_rating,
        imdb,
        background_url,
        cast,
        director,
        writer,
        duration,
        genre,
        name,
        original_name,
        production_year,
        5,
    )
    # xbmc.log('GO: FILMI: DUMP: ' + item['ObjectUrl'], xbmc.LOGNOTICE)


def list_add_series_episode(item):
    # If it's a series episode: # add_link(ou, plot, ar, imdb, bu, cast, director, writer, duration, genre, name, on, py, mode)
    plot = item["Abstract"].encode("utf-8", "ignore")
    if item.get("AvailabilityTo"):
        plot += " Az epizód megtekinthető: %s" % (
            item["AvailabilityTo"].encode("utf-8", "ignore")
        )

    object_url = item["ObjectUrl"]
    age_rating = item["AgeRating"]
    imdb = item["ImdbRate"]
    background_url = item["BackgroundUrl"]
    cast = [item["Cast"].split(", ")][0]
    director = item["Director"]
    writer = item["Writer"]
    duration = item["Duration"]
    genre = item["Genre"]
    name = "%s - %s. ÉVAD %s. RÉSZ" % (
        item.get("SeriesName", "Ismeretlen cím").encode("utf-8"),
        item.get("SeasonIndex"),
        item.get("Index"),
    )
    original_name = item["OriginalName"]
    production_year = item["ProductionYear"]

    add_link(
        object_url,
        plot,
        age_rating,
        imdb,
        background_url,
        cast,
        director,
        writer,
        duration,
        genre,
        name,
        original_name,
        production_year,
        5,
    )


def list_add_series(item):
    # If it's a series
    name = item["Name"].encode("utf-8", "ignore")
    object_url = item["ObjectUrl"]
    abstract = item["Abstract"].encode("utf-8", "ignore")
    mode = 2
    background_url = item["BackgroundUrl"]
    add_directory(name, object_url, abstract, mode, background_url)


def list_add_subcategory(item):
    add_directory(
        item["Name"].encode("utf-8", "ignore"),
        item["ObjectUrl"],
        "",
        1,
        media_path + "DefaultFolder.png",
    )


def listing(url):
    # lista
    global session_id
    global loggedin_headers

    if session_id == NON_AUTHENTICATED_OP_ID:
        login()

    response = requests.get(url, headers=loggedin_headers)
    jsonrsp = response.json()

    if jsonrsp.get("ErrorMessage"):
        xbmcgui.Dialog().ok("Hiba", jsonrsp["ErrorMessage"])
    # If there is a subcategory / genres
    if len(jsonrsp["Container"]) > 1:
        for container in jsonrsp["Container"]:
            list_add_subcategory(container)
    else:
        items = jsonrsp["Container"][0].get("Contents", {}).get("Items")

        for item in items:
            content_type = item["ContentType"]

            if (
                content_type == LISTING_CONTAINER_CONTENT_TYPE_MOVIE
            ):  # 1 = MOVIE/EXTRAS, 2 = SERIES(serial), 3 = SERIES(episode)
                list_add_movie_link(item)

            elif content_type == LISTING_CONTAINER_CONTENT_TYPE_SERIES_EPISODE:
                list_add_series_episode(item)

            else:
                list_add_series(item)


def season_add_season(item):
    if not item.get("ObjectUrl"):
        return
    add_directory(
        item["Name"].encode("utf-8", "ignore"),
        item["ObjectUrl"],
        item["Abstract"].encode("utf-8", "ignore"),
        3,
        item["BackgroundUrl"],
    )


# evadok
def season(url):
    response = requests.get(url, headers=loggedin_headers)
    jsonrsp = response.json()

    if jsonrsp.get("ErrorMessage"):
        xbmcgui.Dialog().ok("Hiba", jsonrsp["ErrorMessage"])

    items = jsonrsp.get("Parent", {}).get("ChildContents", {}).get("Items")
    for item in items:
        season_add_season(item)


def episode_add_episode(item):
    if not item.get("ObjectUrl"):
        return
    # add_link(ou, plot, ar, imdb, bu, cast, director, writer, duration, genre, name, on, py, mode)
    plot = item["Abstract"].encode("utf-8", "ignore")
    if item.get("AvailabilityTo"):
        plot += " Az epizód megtekinthető: %s" % (
            item["AvailabilityTo"].encode("utf-8", "ignore")
        )

    object_url = item["ObjectUrl"]
    age_rating = item["AgeRating"]
    imdb = item["ImdbRate"]
    background_url = item["BackgroundUrl"]
    cast = [item["Cast"].split(", ")][0]
    director = item["Director"]
    writer = item["Writer"]
    duration = item["Duration"]
    genre = item["Genre"]
    name = "%s - %s. ÉVAD %s. RÉSZ" % (
        item.get("SeriesName", "Ismeretlen cím").encode("utf-8"),
        item.get("SeasonIndex"),
        item.get("Index"),
    )
    original_name = item["OriginalName"]
    production_year = item["ProductionYear"]

    add_link(
        object_url,
        plot,
        age_rating,
        imdb,
        background_url,
        cast,
        director,
        writer,
        duration,
        genre,
        name,
        original_name,
        production_year,
        5,
    )


def episode(url):
    # epizodok
    response = requests.get(url, headers=loggedin_headers)
    jsonrsp = response.json()

    if jsonrsp.get("ErrorMessage"):
        xbmcgui.Dialog().ok("Hiba", jsonrsp["ErrorMessage"])

    items = jsonrsp.get("ChildContents", {}).get("Items")
    for item in items:
        episode_add_episode(item)


def play(url):
    # lejatszas
    global go_token
    global individualization
    global customer_id
    global go_customer_id
    global session_id
    global loggedin_headers

    if session_id == NON_AUTHENTICATED_OP_ID:
        login()

    if se == "true":
        try:
            # http://huapi.hbogo.eu/player50.svc/Content/json/HUN/COMP/
            # http://huapi.hbogo.eu/player50.svc/Content/json/HUN/APPLE/
            # http://huapi.hbogo.eu/player50.svc/Content/json/HUN/SONY/
            play_headers = copy(loggedin_headers)
            play_headers["User-Agent"] = MUA
            response = requests.get(
                "http://huapi.hbogo.eu/v5/Content/json/HUN/MOBI/" + cid,
                headers=play_headers,
            )
            jsonrsps = response.json()

            try:
                if jsonrsps["Subtitles"][0]["Code"] == lang_code:
                    slink = jsonrsps["Subtitles"][0]["Url"]
                elif jsonrsps["Subtitles"][1]["Code"] == lang_code:
                    slink = jsonrsps["Subtitles"][1]["Url"]
                data = requests.get(slink, headers=loggedin_headers).text

                subs = re.compile(
                    r'<p[^>]+begin="([^"]+)\D(\d+)"[^>]+end="([^"]+)\D(\d+)"[^>]*>([\w\W]+?)</p>'
                ).findall(data)
                row = 0
                buffer = ""
                for sub in subs:
                    row = row + 1
                    buffer += str(row) + "\n"
                    buffer += (
                        "%s,%03d" % (sub[0], int(sub[1]))
                        + " --> "
                        + "%s,%03d" % (sub[2], int(sub[3]))
                        + "\n"
                    )
                    buffer += (
                        urllib.unquote_plus(sub[4])
                        .replace("<br/>", "\n")
                        .replace("<br />", "\n")
                        .replace("\r\n", "")
                        .replace("&lt;", "<")
                        .replace("&gt;", ">")
                        .replace("\n    ", "")
                        .strip()
                    )
                    buffer += "\n\n"
                    sub = "true"
                    with open(srtsubs_path, "w") as subfile:
                        subfile.write(buffer)

                if sub != "true":
                    raise Exception()

            except:
                sub = "false"
        except:
            sub = "false"

    purchase_payload = (
        '<Purchase xmlns="go:v5:interop"><AllowHighResolution>true</AllowHighResolution><ContentId>'
        + cid
        + "</ContentId><CustomerId>"
        + go_customer_id
        + "</CustomerId><Individualization>"
        + individualization
        + "</Individualization><OperatorId>"
        + op_id
        + "</OperatorId><ClientInfo></ClientInfo><IsFree>false</IsFree><UseInteractivity>false</UseInteractivity></Purchase>"
    )

    purchase_headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "",
        "Accept-Language": "en-US,en;q=0.8",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "GO-CustomerId": str(go_customer_id),
        "GO-requiredPlatform": "CHBR",
        "GO-SessionId": str(session_id),
        "GO-swVersion": "4.7.4",
        "GO-Token": str(go_token),
        "Host": "huapi.hbogo.eu",
        "Referer": "https://hbogo.hu/",
        "Origin": "https://www.hbogo.hu",
        "User-Agent": UA,
    }

    response = requests.post(
        "https://huapi.hbogo.eu/v5/Purchase/Json/HUN/COMP",
        data=purchase_payload,
        headers=purchase_headers,
    )
    jsonrspp = response.json()

    if jsonrspp.get("ErrorMessage"):
        xbmcgui.Dialog().ok("Hiba", jsonrspp["ErrorMessage"])

    media_url = jsonrspp["Purchase"]["MediaUrl"] + "/Manifest"
    player_session_id = jsonrspp["Purchase"]["PlayerSessionId"]
    x_dt_auth_token = jsonrspp["Purchase"]["AuthToken"]

    dt_custom_data = b64encode(
        json.dumps(
            {
                "userId": go_customer_id,
                "sessionId": player_session_id,
                "merchant": "hboeurope",
            }
        )
    )

    li = xbmcgui.ListItem(iconImage=thumbnail, thumbnailImage=thumbnail, path=media_url)
    if se == "true" and sub == "true":
        li.setSubtitles([srtsubs_path])
    license_server = "https://lic.drmtoday.com/license-proxy-widevine/cenc/"
    license_headers = urllib.urlencode(
        {
            "dt-custom-data": dt_custom_data,
            "x-dt-auth-token": x_dt_auth_token,
            "Origin": "https://www.hbogo.hu",
            "Content-Type": "",
        }
    )
    license_key = license_server + "|" + license_headers + "|R{SSM}|JBlicense"

    protocol = "ism"
    drm = "com.widevine.alpha"
    is_helper = inputstreamhelper.Helper(protocol, drm=drm)
    is_helper.check_inputstream()
    li.setProperty("inputstreamaddon", "inputstream.adaptive")
    li.setProperty("inputstream.adaptive.manifest_type", protocol)
    li.setProperty("inputstream.adaptive.license_type", drm)
    li.setProperty("inputstream.adaptive.license_data", "ZmtqM2xqYVNkZmFsa3Izag==")
    li.setProperty("inputstream.adaptive.license_key", license_key)

    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)


SEARCH_CONTENT_TYPE_MOVIE = 1
SEARCH_CONTENT_TYPE_MOVIE_ALT = 7
SEARCH_CONTENT_TYPE_SERIES = 2
SEARCH_CONTENT_TYPE_SERIES_EPISODE = 3


def search_add_movie(item):
    if not item.get("ObjectUrl"):
        return
    object_url = item["ObjectUrl"]
    plot = item["Abstract"].encode("utf-8", "ignore")
    age_rating = item["AgeRating"]
    imdb = item["ImdbRate"]
    background_url = item["BackgroundUrl"]
    cast = [item["Cast"].split(", ")][0]
    director = item["Director"]
    writer = item["Writer"]
    duration = item["Duration"]
    genre = item["Genre"]
    name = item["Name"].encode("utf-8", "ignore")
    original_name = item["OriginalName"]
    production_year = item["ProductionYear"]

    add_link(
        object_url,
        plot,
        age_rating,
        imdb,
        background_url,
        cast,
        director,
        writer,
        duration,
        genre,
        name,
        original_name,
        production_year,
        5,
    )


def search_add_series_episode(item):
    if not item.get("ObjectUrl"):
        return
    object_url = item["ObjectUrl"]
    plot = item["Abstract"].encode("utf-8", "ignore")
    age_rating = item["AgeRating"]
    imdb = item["ImdbRate"]
    background_url = item["BackgroundUrl"]
    cast = [item["Cast"].split(", ")][0]
    director = item["Director"]
    writer = item["Writer"]
    duration = item["Duration"]
    genre = item["Genre"]
    name = "%s %s" % (
        item.get("SeriesName").encode("utf-8"),
        item.get("Name").encode("utf-8"),
    )
    original_name = item["OriginalName"]
    production_year = item["ProductionYear"]

    add_link(
        object_url,
        plot,
        age_rating,
        imdb,
        background_url,
        cast,
        director,
        writer,
        duration,
        genre,
        name,
        original_name,
        production_year,
        5,
    )


def search_add_series(item):
    if not item.get("ObjectUrl"):
        return
    name = item["Name"].encode("utf-8", "ignore")
    object_url = item["ObjectUrl"]
    plot = item["Abstract"].encode("utf-8", "ignore")
    background_url = item["BackgroundUrl"]
    add_directory(name, object_url, plot, 2, background_url)


def search():
    search_string = urllib.unquote_plus(__addon__.getSetting("lastsearch"))
    keyb = xbmc.Keyboard(search_string, "Filmek, sorozatok keresése...")
    keyb.doModal()
    if not keyb.isConfirmed():
        exit()
    search_text = urllib.quote_plus(keyb.getText())
    if not search_text:
        add_directory("Nincs találat", "", "", "", media_path + "DefaultFolderBack.png")
    else:
        __addon__.setSetting("lastsearch", search_text)

        response = requests.get(
            "https://huapi.hbogo.eu/v5/Search/Json/HUN/COMP/%s/0"
            % (search_text.encode("utf-8")),
            headers=loggedin_headers,
        )
        jsonrsp = response.json()

        if jsonrsp.get("ErrorMessage"):
            xbmcgui.Dialog().ok("Hiba", jsonrsp["ErrorMessage"])

        br = 0
        items = jsonrsp["Container"][0]["Contents"]["Items"]
        for item in items:
            if (
                item["ContentType"] == SEARCH_CONTENT_TYPE_MOVIE
                or item["ContentType"] == SEARCH_CONTENT_TYPE_MOVIE_ALT
            ):  # 1,7 = MOVIE/EXTRAS, 2 = SERIES(serial), 3 = SERIES(episode)
                # Ако е филм    # add_link(ou, plot, ar, imdb, bu, cast, director, writer, duration, genre, name, on, py, mode)
                search_add_movie(item)
            elif item["ContentType"] == SEARCH_CONTENT_TYPE_SERIES_EPISODE:
                # Ако е Epizód на сериал    # add_link(ou, plot, ar, imdb, bu, cast, director, writer, duration, genre, name, on, py, mode)
                search_add_series_episode(item)
            else:
                search_add_series(item)
                # Ако е сериал
            br = br + 1
        if br == 0:
            add_directory(
                "Nincs találat", "", "", "", media_path + "DefaultFolderBack.png"
            )


def add_link(
    ou, plot, ar, imdb, bu, cast, director, writer, duration, genre, name, on, py, mode
):
    cid = ou.rsplit("/", 2)[1]

    u = (
        sys.argv[0]
        + "?"
        + urllib.urlencode(
            {"url": url, "mode": str(mode), "name:": name, "cid": cid, "thumbnail": bu}
        )
    )

    liz = xbmcgui.ListItem(name, iconImage=bu, thumbnailImage=bu)
    liz.setArt({"thumb": bu, "poster": bu, "banner": bu, "fanart": bu})
    liz.setInfo(
        type="Video",
        infoLabels={
            "plot": plot,
            "mpaa": str(ar) + "+",
            "rating": imdb,
            "cast": cast,
            "director": director,
            "writer": writer,
            "duration": duration,
            "genre": genre,
            "title": name,
            "originaltitle": on,
            "year": py,
        },
    )
    liz.addStreamInfo("video", {"width": 1280, "height": 720})
    liz.addStreamInfo("video", {"aspect": 1.78, "codec": "h264"})
    liz.addStreamInfo("audio", {"codec": "aac", "channels": 2})
    liz.setProperty("IsPlayable", "true")
    ok = xbmcplugin.addDirectoryItem(
        handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=False
    )
    return ok


def add_directory(name, url, plot, mode, iconimage):
    u = (
        sys.argv[0]
        + "?"
        + urllib.urlencode({"url": url, "mode": str(mode), "name": name})
    )

    liz = xbmcgui.ListItem(
        name, iconImage="DefaultFolder.png", thumbnailImage=iconimage
    )
    liz.setInfo(type="Video", infoLabels={"Title": name, "Plot": plot})

    ok = xbmcplugin.addDirectoryItem(
        handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True
    )

    return ok


MODE_LISTING = 1
MODE_SEASON = 2
MODE_EPISODE = 3
MODE_SEARCH = 4
MODE_PLAY = 5
MODE_SILENT_REGISTER = 6
MODE_LOGIN = 7


if __name__ == "__main__":
    params = dict(parse_qsl(sys.argv[2].replace("?", "")))

    url = params.get("url")
    name = params.get("name")
    thumbnail = params.get("thumbnail")
    mode = int(params.get("mode", "0"))
    cid = params.get("cid")

    if not mode or not url:
        categories()

    elif mode == MODE_LISTING:
        listing(url)

    elif mode == MODE_SEASON:
        season(url)

    elif mode == MODE_EPISODE:
        episode(url)

    elif mode == MODE_SEARCH:
        search()

    elif mode == MODE_PLAY:
        play(url)

    elif mode == MODE_SILENT_REGISTER:
        store_individualization()

    elif mode == MODE_LOGIN:
        login()

    xbmcplugin.endOfDirectory(int(sys.argv[1]))

# vim: sw=2:ts=2:noexpandtab
