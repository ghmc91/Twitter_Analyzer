
# Imports
import sys
import tweepy
import time
import json
from py2neo import Graph
from py2neo.ogm import Property, GraphObject, Related

# Twitter Keys
consumer_keys = "YOUR_CONSUMER_KEY"
consumer_secrets = "YOUR_CONSUMER_SECRET_KEY"

access_tokens = "YOUR_ACCESS_TOKEN"
access_token_secrets = "YOUR_ACCESS_TOKEN_SECRETS"

# Autenticação
current_user = 0

auth = tweepy.OAuthHandler(consumer_keys, consumer_secrets)
auth.set_access_token(access_tokens, access_token_secrets)
api = tweepy.API(auth)
print(api.me())
print('\n')

tweets_list = []
following = []
followed_by = []

try:
    # Senha do Neo4j
    graph = Graph(password="YOUR_PASSWORD")
    graph.begin()
    graph.delete_all()
except:
    print('Neo4J não está iniciado, por favor, inicialize o banco de dados e tente novamente')
    sys.exit()

is_not_last_tweet = True


def change_account():
    global api, current_user, hashtag
    try:
        auth = tweepy.OAuthHandler(consumer_keys[current_user], consumer_secrets[current_user])
        auth.set_access_token(access_tokens[current_user], access_token_secrets[current_user])
        api = tweepy.API(auth)
        print(api.me())
        print('\n')
    except:
        if current_user >= 4:
            current_user = 0
        else:
            current_user = current_user + 1
        change_account()

    # Criando o Stream
    myStreamListener = MyStreamListener()
    myStream = tweepy.Stream(auth=api.auth, listener=myStreamListener)

    # Iniciando o Stream
    myStream.filter(track=[hashtag])


def check_relationships(tweetObject):
    try:
        for x in tweets_list:
            friendship = api.show_friendship(source_id=tweetObject.id, target_id=x.id)
            if friendship[0].following == True:
                print("Seguindo")
                tweetObject.Following.add(x)
            if friendship[1].followed_by == True:
                print("Seguido Por")
                x.Following.add(tweetObject)
        graph.create(tweetObject)
    except tweepy.RateLimitError:
        print("Rate Limit Error")
        global current_user
        current_user = current_user + 1
        change_account()


# Cria a classe herdando de StreamListener
class MyStreamListener(tweepy.StreamListener):
    def __init__(self, time_limit=100):
        self.start_time = time.time()
        self.limit = time_limit
        super(MyStreamListener, self).__init__()

    def on_data(self, data):
        global is_not_last_tweet
        print("Não é o último tweet :" + str(is_not_last_tweet))
        if is_not_last_tweet:
            if (time.time() - self.start_time) < self.limit:
                tweet = json.loads(data)
                tweetObject = Tweet()
                tweetObject.username = tweet['user']['screen_name']
                tweetObject.name = tweet['user']['name']
                tweetObject.time = tweet['created_at']
                tweetObject.location = tweet['user']['location']
                tweetObject.id = tweet['user']['id']
                tweetObject.profile_picture = tweet['user']['profile_image_url_https']
                tweetObject.verified = tweet['user']['verified']
                try:
                    tweetObject.tweet = tweet['extended_tweet']['full_text']
                except KeyError:
                    tweetObject.tweet = tweet['text']
                tweets_list.append(tweetObject)
                check_relationships(tweetObject)
                if (tweet['user']['verified'] == 'true'):
                    print('Verificado')
                else:
                    print('Não verificado')
                return True
            else:
                print(str(time.time() - self.start_time) + " " + str(self.limit))
                return False
        else:
            self.set_is_not_last_tweet(True)
        return True

    def on_error(self, status_code):
        print('Error raised: ' + str(status_code))

    def set_is_not_last_tweet(self, status):
        global is_not_last_tweet
        is_not_last_tweet = status
        print("Não é o último status do Tweet :" + str(is_not_last_tweet))

    def set_start_time(self):
        self.start_time = time.time()


class Tweet(GraphObject):
    __primarykey__ = "name"

    username = Property()
    name = Property()
    tweet = Property()
    time = Property()
    location = Property()
    id = Property()
    verified = Property()
    profile_picture = Property()
    Following = Related("Tweet", "FOLLOWING")
    Followed_by = Related("Tweet", "FOLLOWED_BY")


# Cria um Stream
myStreamListener = MyStreamListener()
myStreamListener.set_is_not_last_tweet(True)


def connect_to_stream(word):
    print('Tracking: ' + word)
    global myStreamListener, hashtag, myStream
    myStreamListener.set_start_time()
    hashtag = word
    graph.begin()
    graph.delete_all()
    myStream = tweepy.Stream(auth=api.auth, listener=myStreamListener)

    # Step 3: Starting a Stream
    myStream.filter(track=[word])


def close_thread():
    global myStreamListener
    myStreamListener.set_is_not_last_tweet(False)
    myStream.disconnect()
    graph.delete_all()

    print('Desconectando Thread procurando por tweets relacionados com: ' + hashtag)
