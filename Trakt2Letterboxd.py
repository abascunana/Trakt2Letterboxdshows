""" Trakt2Letterboxd """
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json
import time
import csv
import os.path
import webbrowser


class TraktImporter(object):
    """ Trakt Importer """

    def __init__(self):
        self.api_root = 'https://api.trakt.tv'
        self.api_clid = 'b04da548cc9df60510eac7ec1845ab98cebd8008a9978804a981bff7e73ab270'
        self.api_clsc = 'a880315fba01a5e5f0ad7de12b7872e36826a9359b2f419122a24dee1b2cb600'
        self.api_token = None
        self.api_headers = { 'Content-Type': 'application/json' }


    def authenticate(self):
        """ Authenticates the user and grabs an API access token if none is available. """

        if self.__decache_token():
            return True

        dev_code_details = self.__generate_device_code()

        self.__show_auth_instructions(dev_code_details)

        got_token = self.__poll_for_auth(dev_code_details['device_code'],
                                         dev_code_details['interval'],
                                         dev_code_details['expires_in'] + time.time())

        if got_token:
            self.__encache_token()
            return True

        return False

    def __decache_token(self):
        if not os.path.isfile("t_token"):
            return False

        token_file = open("t_token", 'r')
        self.api_token = token_file.read()
        token_file.close()
        return True

    def __encache_token(self):
        token_file = open("t_token", 'w')
        token_file.write(self.api_token)
        token_file.close()

    @staticmethod
    def __delete_token_cache():
        os.remove("t_token")

    def __generate_device_code(self):
        """ Generates a device code for authentication within Trakt. """

        url = self.api_root + '/oauth/device/code'
        data = """{{"client_id": "{0}"}}""".format(self.api_clid).encode('utf8')

        request = Request(url, data, self.api_headers)

        response_body = urlopen(request).read()
        return json.loads(response_body)

    @staticmethod
    def __show_auth_instructions(details):
        message = ("\nGo to {0} on your web browser and enter the below user code there:\n\n"
                   "{1}\n\nAfter you have authenticated and given permission;"
                   "come back here to continue.\n"
                  ).format(details['verification_url'], details['user_code'])
        print(message)

    def __poll_for_auth(self, device_code, interval, expiry):
        """ Polls for authorization token """
        url = self.api_root + '/oauth/device/token'
        data = """{{ "code":          "{0}",
                     "client_id":     "{1}",
                     "client_secret": "{2}" }}
                       """.format(device_code, self.api_clid, self.api_clsc).encode('utf8')

        request = Request(url, data, self.api_headers)

        response_body = ""
        should_stop = False

        print("Waiting for authorization.", end=' ')

        while not should_stop:
            time.sleep(interval)

            try:
                response_body = urlopen(request).read()
                should_stop = True
            except HTTPError as err:
                if err.code == 400:
                    print(".", end=' ')
                else:
                    print("\n{0} : Authorization failed, please try again. Script will now quit.".format(err.code))
                    should_stop = True

            should_stop = should_stop or (time.time() > expiry)

        if response_body:
            response_dict = json.loads(response_body)
            if response_dict and 'access_token' in response_dict:
                print("Authenticated!")
                self.api_token = response_dict['access_token']
                print("Token:" + self.api_token)
                return True

        # Errored.
        return False

    def get_movie_list(self, list_name):
        """ Get movie list of the user. """
        print("Getting " + list_name)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.api_token,
            'trakt-api-version': '2',
            'trakt-api-key': self.api_clid
        }

        extracted_movies = []
        page_limit = 1
        page = 1

        while page <= page_limit:
            request = Request(self.api_root + '/sync/' + list_name + '/all?page={0}'.format(page),
                              headers=headers)
            try:
                response = urlopen(request)

                page_limit = int(response.info()['X-Pagination-Page-Count'])
                print("Completed page {0} of {1}".format(page, page_limit))
                page = page + 1

                response_body = response.read()
                if response_body:
                    extracted_movies.extend(self.__extract_fields(json.loads(response_body)))
            except HTTPError as err:
                if err.code == 401 or err.code == 403:
                    print("Auth Token has expired.")
                    self.__delete_token_cache() # This will regenerate token on next run.
                print("{0} An error occured. Please re-run the script".format(err.code))
                quit()

        return extracted_movies

    @staticmethod
    def __extract_fields(movies):
        extracted_data = []
        for item in movies:
            if item['type'] == 'movie':
                extracted_data.append({
                    'WatchedDate': item.get('watched_at', ''),
                    'tmdbID': item['movie']['ids']['tmdb'],
                    'imdbID': item['movie']['ids']['imdb'],
                    'Title': item['movie']['title'],
                    'Year': item['movie']['year'],
                    'Title Show': "movie"
                })
            else:
                extracted_data.append({
                    'WatchedDate': item.get('watched_at', ''),
                    'tmdbID': item['episode']['ids']['tmdb'],
                    'imdbID': item['episode']['ids']['imdb'],
                    'Title': item['episode']['title'],
                    'Year': item['show']['year'],
                    'Title Show': item['show']['title']
                })
        return extracted_data

    

def write_csv(history, filename):
    """ Write Letterboxd format CSV """
    if history:
        with open(filename, 'w', encoding='utf8') as fil:
            writer = csv.DictWriter(fil, list(history[0].keys()))
            writer.writeheader()
            writer.writerows(history)
        return True

    return False

def run():
    """Get set go!"""

    print("Initializing...")

    importer = TraktImporter()
    if importer.authenticate():
        history = importer.get_movie_list('history')
        if write_csv(history, "trakt-exported-history-shows.csv"):
            print("\nYour history has been exported and saved to the file 'trakt-exported-history.csv-shows'.")
        else:
            print("\nEmpty results, nothing to generate.")
        webbrowser.open('https://letterboxd.com/import/', new=2)
if __name__ == '__main__':
    run()
