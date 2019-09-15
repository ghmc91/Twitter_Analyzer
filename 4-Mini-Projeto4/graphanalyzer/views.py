
# Imports
import json
import threading
from json import JSONDecodeError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.generic import ListView
from py2neo import Graph, ClientError
import secrets
from .forms import HashtagForm
import graphanalyzer.twitterManager as twitterManager
from django.views.generic.edit import FormView
import time


def index(request):
    return render(request, 'graphanalyzer/index.html')


def load_json(request):
    json_data = open('tweets.json')
    try:
        data = json.load(json_data)
        return JsonResponse(data, safe=False)
    except:
        return HttpResponse('Decoding JSON falhou')


class GraphView(FormView, ListView):
    template_name = 'graphanalyzer/graph.html'
    context_object_name = 'graph'
    form_class = HashtagForm
    thread_started = False
    my_list = []

    def get_db_call(self, x):
        return {
            'pageRank': 'CALL algo.pageRank.stream(\'Tweet\', \'Relationship\', {iterations:5}) YIELD nodeId,'
                        ' score WITH * ORDER BY score DESC LIMIT 20 RETURN nodeId, score;',
            'betweenness': 'CALL algo.betweenness.stream(\'Tweet\',\'RELATED\',{direction:\'out\'})YIELD nodeId,'
                           ' centrality RETURN nodeId,centrality order by centrality desc limit 20;',
            'closeness': 'CALL algo.closeness.stream(\'Node\', \'LINKS\') YIELD nodeId, centrality RETURN nodeId,'
                         'centrality order by centrality desc limit 20;',
        }.get(x, 1)

    def form_valid(self, form):
        if len(self.my_list) > 0:
            self.my_list[0].close_thread()
            self.my_list.pop()
        thread = TwitterThread(1, 'Twitter Thread', form)
        time.sleep(2)
        thread.start()
        self.my_list.append(thread)
        print('Número de threads ' + str(len(self.my_list)))
        return super().form_valid(form)

    def get_queryset(self):
        success_url = self.get_success_url()
        url = success_url.split("/")
        mode = url[len(url) - 1]
        mode = (self.get_db_call(mode))
        RefreshGraphThread(1, 'Refresh Thread', mode)


class TwitterThread(threading.Thread):
    def __init__(self, thread_id, name, form):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.name = name
        self.form = form

    def run(self):
        print('Starting ' + self.name)
        twitterManager.connect_to_stream(self.form.cleaned_data['hashtag'])
        print('Exiting ' + self.name)

    def close_thread(self):
        twitterManager.close_thread()


class RefreshGraphThread():
    def __init__(self, thread_id, name, mode):
        self.thread_id = thread_id
        self.name = name
        self.mode = mode
        self.run()

    def check_tweet_text(self, tweet):
        new_tweet = ''
        for idx, char in enumerate(tweet):
            if char == '"':
                new_tweet += '\\"'
            else:
                new_tweet += char
        return new_tweet

    def get_nodes(self):
        # Senha do Neo4j
        graph = Graph(password="raca1981")
        filename = 'nodes.json'
        with open(filename, 'w') as outfile:
            outfile.write('{"nodes": ')
            json.dump(graph.run('MATCH (node) RETURN (node),ID(node)').data(), outfile)
            outfile.write('}')
        tweets = '{"nodes": ['
        try:
            nodes = json.load(open(filename))

            if type(self.mode) is not int:
                try:
                    node_weights = json.dumps(graph.run(self.mode).data())
                except ClientError:
                    node_weights = 1
            else:
                node_weights = 1
            for idx, node in enumerate(nodes['nodes']):
                node['node']['nodeId'] = str(node['ID(node)'])
                if node_weights != 1:
                    weight = self.get_node_weight(int(node['node']['nodeId']), node_weights)
                else:
                    weight = 1
                node['node']['weight'] = str(weight)
                tweets += json.dumps(node['node'])
                if (idx + 1) < len(nodes['nodes']):
                    tweets += ','
            tweets += ']'
            return tweets
        except JSONDecodeError:
            print('Decoding JSON falhou')
        except IndexError:
            print('Decoding JSON falhou')

    def get_node_weight(self, node_id, node_weights):
        i = 0
        node = json.loads(json.dumps(json.loads(node_weights)[0]))
        while node['nodeId'] != node_id:
            i += 1
            node = json.loads(json.dumps(json.loads(node_weights)[i]))
        try:
            return node['score']
        except KeyError:
            return node['centrality']

    def get_links(self):
        graph = Graph(password="raca1981")
        filename = "relationships.json"
        with open(filename, 'w') as outfile:
            outfile.write('{"links": ')
            json.dump(graph.run('MATCH (n)-[r]->(m) RETURN n,r,m;').data(), outfile)
            outfile.write('}')
        links = ', "links": ['
        try:
            relationships = json.load(open(filename))
            for idx, relationship in enumerate(relationships['links']):
                links += '{"source": ' + str(relationship['n']['id']) + ', "target": ' + str(
                    relationship['m']['id']) + ', "value": 1}'
                if (idx + 1) < len(relationships['links']):
                    links += ','
            links += ']}'
            return links
        except JSONDecodeError:
            print('Decoding JSON falhou')

    def run(self):
        print('Iniciando ' + self.name)
        filename = 'tweets.json'
        with open(filename, 'w') as outfile:
            outfile.write(self.get_nodes())
            outfile.write(self.get_links())
