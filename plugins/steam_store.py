import re
import requests
from cloudbot import hook
from cloudbot.util import web, formatting
from cloudbot.util.http import parse_soup

# CONSTANTS
STEAM_RE = re.compile(r'.*://store.steampowered.com/app/([0-9]+)?.*', re.I)
API_URL = "http://store.steampowered.com/api/appdetails/"
STORE_URL = "http://store.steampowered.com/app/{}/"
REVIEWS_API_URL = "https://store.steampowered.com/appreviews/{}?json=1&language=all"
COUNTRY_CODE = "BR" # ISO-3166 alpha-2
SESSION = requests.Session()

# OTHER FUNCTIONS
def format_game(SESSION, app_id, show_url=True):
    """
    Takes a Steam Store app ID and returns a formatted string with data about that app ID
    :type app_id: string
    :return: string
    """
    params = {'appids': app_id, 'cc': COUNTRY_CODE}

    try:
        request = SESSION.get(API_URL, params=params, timeout=15)
        request.raise_for_status()
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as err:
        return "Could not get game info: {}".format(err)

    data = request.json()
    game = data[app_id]["data"]

    # basic info
    out = ["\x02{}\x02".format(game["name"])]

    desc = " ".join(formatting.strip_html(game["about_the_game"]).split())
    out.append(formatting.truncate(desc, 75))

    # rating/steam reviews
    try:
        response = SESSION.get(REVIEWS_API_URL.format(app_id))
        response.raise_for_status()
        
        data = response.json()
        steam_rating = data['query_summary']['review_score_desc']
        
        game_rating = ["\x02{}\x02".format(steam_rating)]

    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
        pass

    # metacritic rating
    try:
        metacritic_score = game['metacritic']['score']

        green = '00,03' # 60+
        yellow = '00,07' # 40-59+
        red = '00,04' # 0-39

        if metacritic_score > 74:
            color = green
        elif metacritic_score > 49:
            color = yellow
        else:
            color = red

        metacritic_score_formatted = ("\x03{} {} \x03".format(color, metacritic_score))
        game_rating.append(metacritic_score_formatted)

    except KeyError:
        # some thing have no metacritic score
        pass
    
    out.append("{}".format(" ".join(game_rating)))    

    # genres
    try:
        genres = ", ".join([g['description'] for g in game["genres"]])
        out.append("\x02{}\x02".format(genres))
    except KeyError:
        # some things have no genre
        pass

    # release date
    if game['release_date']['coming_soon']:
        out.append("coming \x02{}\x02".format(game['release_date']['date']))
    else:
        out.append("released \x02{}\x02".format(game['release_date']['date']))

    # pricing
    if game['is_free']:
        out.append("\x02free\x02")
    elif not game.get("price_overview"):
        # game has no pricing, it's probably not released yet
        pass
    else:
        price = game['price_overview']

        if not price['initial_formatted']:
            out.append("\x02{}\x02".format(price['final_formatted']))
        else:
            price_now = "{}".format(price['final_formatted'])
            price_original = "{}".format(price['initial_formatted'])

            out.append("\x02{}\x02 (was \x02{}\x02)".format(price_now, price_original))

    if show_url:
        url = web.try_shorten(STORE_URL.format(game['steam_appid']))
        out.append(url)

    return " - ".join(out)


# HOOK FUNCTIONS

@hook.command()
def steam(text, reply):
    """<query>[, index] - Search for specified game/trailer/DLC"""

    term = text.strip().lower()
    index = 1

    splitted = text.split(",")

    if len(splitted) > 1 and splitted[1].strip().isdigit():
        term = text.split(",")[0]
        index = abs(int(text.split(",")[1]))

    params = {'term': term}

    try:
        request = SESSION.get("http://store.steampowered.com/search/", params=params)
        request.raise_for_status()
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as err:
        reply("Could not get game info: {}".format(err))
        raise

    soup = parse_soup(request.text, from_encoding="utf-8")
    result = soup.find_all('a', {'class': 'search_result_row'})

    if not result:
        return "No game found."

    appid_list = []
    i = 0
    while len(appid_list) < 10 and i < len(result):
        if result[i].has_attr('data-ds-appid'):
            appid_list.append(result[i]['data-ds-appid'])
        i += 1

    if index > len(appid_list):
        index = len(appid_list)

    if index <= 0:
        index = 1

    app_id = appid_list[index - 1]
    return "[{}/{}] {}".format(index, len(appid_list), format_game(SESSION, app_id))


@hook.regex(STEAM_RE)
def steam_url(match):
    app_id = match.group(1)
    return format_game(SESSION, app_id, show_url=False)
