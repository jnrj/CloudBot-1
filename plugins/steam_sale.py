import requests
from bs4 import BeautifulSoup
from cloudbot import hook
from cloudbot.util import colors

URL = "https://prepareyourwallet.com/"

@hook.command('sale', autohelp=False)
def prepareyourwallet():
    try:
        response = requests.get(URL)
        response.raise_for_status()
    except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError):
        return "Couldn't get sale data."

    # create soup
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')

    # scrape
    try:
        sale_name = soup.find("h2", class_="h5 mb-3 text-white").text
        start_date = soup.find("span", itemprop="startDate").text
        end_date = soup.find("span", itemprop="endDate").text
        countdown = soup.find("span", id="countdown").text
        status = soup.find("span", class_="status mb-0 mt-2 float-lg-right").text
    except AttributeError:
        return "Error."

    output = colors.parse(f"$(bold){sale_name}$(clear) - $(bold){start_date}$(clear) to $(bold){end_date}$(clear) - {countdown} [{status}]")
    return output
