import httplib2
import facebook
import twitter

from django.conf import settings
from django.utils import simplejson as json

from friends.contrib.suggestions.backends.runners import AsyncRunner
from friends.contrib.suggestions.settings import RUNNER
from friends.contrib.suggestions.models import FriendshipSuggestion


# determine the base class based on what type of importing should be done
if issubclass(RUNNER, AsyncRunner):
    from celery.task import Task
else:
    Task = object


class BaseImporter(Task):

    def run(self, credentials, persistance):
        status = {
            "imported": 0,
            "total": 0,
            "suggestions": 0,
        }

        # save imported contacts
        for contact in self.get_contacts(credentials):
            status = persistance.persist(contact, status, credentials)

        # find suggestions using all user imported contacts
        status["suggestions"] = FriendshipSuggestion.objects.create_suggestions_for_user_using_imported_contacts(credentials["user"])
        return status


GOOGLE_CONTACTS_URI = "http://www.google.com/m8/feeds/contacts/default/full?alt=json&max-results=1000"

class GoogleImporter(BaseImporter):

    def get_contacts(self, credentials):
        h = httplib2.Http()
        response, content = h.request(GOOGLE_CONTACTS_URI, headers={
            "Authorization": 'AuthSub token="%s"' % credentials["authsub_token"]
        })

        if response.status != 200:
            return

        results = json.loads(content)
        for person in results["feed"]["entry"]:
            for email in person.get("gd$email", []):
                yield {
                    "name": person["title"]["$t"],
                    "email": email["address"],
                }


class FacebookImporter(BaseImporter):

    def get_contacts(self, credentials):
        graph = facebook.GraphAPI(credentials["facebook_token"])
        friends = graph.get_connections("me", "friends")
        for friend in friends["data"]:
            yield {
                "name": friend["name"],
                "email": "",
            }


class TwitterImporter(BaseImporter):
    def get_contacts(self, credentials):
        api = twitter.Api(
            consumer_key=settings.OAUTH_ACCESS_SETTINGS["twitter"]["keys"]["KEY"],
            consumer_secret=settings.OAUTH_ACCESS_SETTINGS["twitter"]["keys"]["SECRET"],
            access_token_key=credentials["twitter_token"].key,
            access_token_secret=credentials["twitter_token"].secret
        )
        friends = api.GetFriends()
        for friend in friends:
            yield {
                "name": friend.name,
                "email": "",
            }


