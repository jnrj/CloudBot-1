from datetime import datetime
from datetime import timedelta
import requests
from cloudbot import hook
from cloudbot.bot import bot
from cloudbot.util import colors, web

# config
KEY = bot.config.get_api_key("itad")
REGION = 'br2'
COUNTRY = 'BR'
SHOPS = ','.join(['steam', 'gog', 'nuuvem', 'greenmangaming'])
SINCE_MONTHS = 3 # how many months to check for previous sales in historical data
SINCE = str(int(datetime.now().timestamp()) - SINCE_MONTHS * 30 * 24 * 60 * 60)
API_URL = 'https://api.isthereanydeal.com'

# formats value in brl
def format_to_brl(currency):
    """returns formatted currency"""
    formatted_brl = 'R$ {:,.2f}'.format(currency)
    formatted_brl = formatted_brl.translate(str.maketrans(',.', '.,'))
    return formatted_brl

def get_game_data(session, results, index=1):
    """returns final formatted result"""
    results_len = len(results)
    plain = results[index - 1]['plain']
    title = results[index - 1]['title']

    # build output
    output = '[{}/{}] $(bold){}$(clear) '.format(index, results_len, title)

    # set params for requests
    params = {"key": KEY, "region": REGION, "country": COUNTRY, "plains": plain}
    params_prices = {**params, "shops": SHOPS}
    params_history = {**params, "since": SINCE, "new": 1}

    # set urls
    game_prices = '{}/v01/game/prices/'.format(API_URL)
    game_overview = '{}/v01/game/overview/'.format(API_URL)
    game_history = '{}/v01/game/lowest/'.format(API_URL)

    # get game data
    try:
        # get prices
        game_prices_request = session.get(game_prices, params=params_prices)
        print(game_prices_request.url)
        game_prices_request.raise_for_status()

        # to get lowest of all time
        game_overview_request = session.get(game_overview, params=params)
        print(game_overview_request.url)
        game_overview_request.raise_for_status()

        # to get recent low
        game_history_request = session.get(game_history, params=params_history)
        print(game_history_request.url)
        game_history_request.raise_for_status()

    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as err:
        print(err)       
        return "Could not get game info."

    game_prices_json = game_prices_request.json()
    game_overview_json = game_overview_request.json()
    game_history_json = game_history_request.json()

    # recent low price dict
    if 'price' in game_history_json['data'][plain]:
        recent_low_dict = {
            'price': game_history_json['data'][plain]['price'],
            'date': game_history_json['data'][plain]['added'],
            'store': game_history_json['data'][plain]['shop']['name'],
            'diff': timedelta(seconds=int(datetime.now().timestamp()) - game_history_json['data'][plain]['added']).days
        }
    else:
        recent_low_dict = None

    # game url
    game_info_url = web.try_shorten('https://isthereanydeal.com/game/{}/info'.format(plain))

    # game exists but not in the selected store
    if not game_prices_json['data'][plain]['list']:
        output += "No data about this game with the selected stores. More info: {}".format(game_info_url)
        return colors.parse(output)

    game_price_list = game_prices_json['data'][plain]['list']
    game_recent_low = game_overview_json['data'][plain]['lowest']

    # lowest price dict
    historical_dict = {
        'price': game_recent_low['price'],
        'date': game_recent_low['recorded_formatted'],
        'store': game_recent_low['store']
    }

    # create prices list with data for each game
    prices_list = [({'store': i['shop']['name'],
                     'price_cut': i['price_cut'],
                     'price_old': i['price_old'],
                     'price_new': i['price_new'],
                     'drm': i['drm'],
                     'url': i['url']}) for i in game_price_list]

    # format price data
    prices_string = ''
    for i in prices_list:
        if i['price_cut'] > 0:
            price_cut = ' ($(dgreen, bold)-{}%$(clear), was $(bold){}$(clear))'.format(i['price_cut'],
                                                                                       format_to_brl(i['price_old']))
        else:
            price_cut = '{}%'.format(i['price_cut'])
        prices_string += '⦁ {}: $(bold){}$(clear){} '.format(i['store'],
                                                             format_to_brl(i['price_new']),
                                                             price_cut if i['price_cut'] > 0 else '')

    # all time low string
    historical_string = '[All time low: $(bold){}$(clear) on $(bold){}$(clear), {}]'.format(format_to_brl(historical_dict['price']),
                                                                                            historical_dict['store'],
                                                                                            historical_dict['date'])
    # las x months string
    recent_string = '[Last {}{}: $(bold){}$(clear) on $(bold){}$(clear), {} {} ago]'.format(SINCE_MONTHS if SINCE_MONTHS > 1 else '',
                                                                                            ' months' if SINCE_MONTHS > 1 else 'month',
                                                                                            format_to_brl(recent_low_dict['price']),
                                                                                            recent_low_dict['store'], recent_low_dict['diff'],
                                                                                            'days' if recent_low_dict['diff'] > 1 else 'day')

    # final output
    output += '{}{} {} - {}'.format(prices_string, historical_string,
                                    '' if recent_low_dict is None else recent_string,
                                    game_info_url)

    return colors.parse(output)

@hook.command('isthereanydeal', 'itad', autohelp=True)
def isthereanydeal(text):
    """<game title>[, index] - Returns the game entry from isthereanydeal.com"""
    cleaned_query = text.strip()  
    split_query = cleaned_query.split(',')
    cleaned_split_query = [i.strip() for i in split_query]
    actual_query = ' '.join(cleaned_split_query)
    index = 1

    if len(cleaned_split_query) > 1 and cleaned_split_query[-1].isdigit():
        actual_query = ' '.join(cleaned_split_query[:-1])
        index = abs(int(cleaned_split_query[-1]))

    # returns first item if index < 1
    if index < 1:
        index = 1

    # create sessions and get results in json data
    session = requests.Session()
    search_url = '{}/v02/search/search/?key={}&q={}'.format(API_URL, KEY, actual_query)
    try:
        search_request = session.get(search_url)
        print(search_request.url)
        search_request.raise_for_status()
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
        return "Could not get game info."
    
    search_results_json = search_request.json()

    # some queries can return error
    if 'error' in search_results_json:
        return "Invalid query"
    
    results = search_results_json['data']['results']

    # some queries have no results
    if not results:
        return 'No results for "{}".'.format(actual_query)

    # return last item if index > total items
    if index > len(results):
        index = len(results)

    game_data = get_game_data(session, results, index)

    return game_data
    